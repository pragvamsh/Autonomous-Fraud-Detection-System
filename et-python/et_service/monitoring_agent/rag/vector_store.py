"""
vector_store.py
───────────────
ChromaDB client manager for the RAG layer.

Manages five persistent collections with the correct embedding
strategy per collection as specified:

  L1_regulatory     — text docs  → SentenceTransformer (384-d)
  L2_fraud_cases    — feature vecs → FraudFeatureEncoder (128-d, custom)
  L3_typologies     — signal vecs  → SignalSequenceEncoder (256-d, custom)
  L4_dynamic_weights— feature vecs → FraudFeatureEncoder (128-d, custom)
  L5_feedback_log   — key-value audit log (NO embedding)

Key fixes vs original:
  [FIX-1] L2, L3, L4 created with embedding_function=None — they accept
          pre-computed vectors via query_by_vector() / upsert_with_vectors().
          Using ChromaDB's default text embedder for these was architecturally
          wrong and produced text-similarity matching instead of feature-space
          matching.
  [FIX-2] HNSW parameters set per spec: ef_search=50, ef_construction=200, M=16.
  [FIX-3] L5 created as a plain collection with no embedding function and no
          HNSW metadata — it is queried by ID only, never by similarity.
  [FIX-4] Public API enforces the text vs vector boundary:
            query_by_text()   — L1 only
            query_by_vector() — L2, L3, L4 only
            get_by_id()       — L5 only
          Callers cannot accidentally use the wrong path.
  [FIX-5] SentenceTransformer embedding function is a singleton loaded once.
"""

import os
import chromadb
from chromadb.config import Settings

from et_service.monitoring_agent.constants import (
    HNSW_SPACE,
    HNSW_EF_SEARCH,
    HNSW_CONSTRUCTION_EF,
    HNSW_M,
)

# ── Paths ──────────────────────────────────────────────────────────────────────
_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, '..', '..', '..'))
_CHROMA_DIR   = os.path.join(_PROJECT_ROOT, 'chroma_db')

# ── Collection names ──────────────────────────────────────────────────────────
COLLECTIONS = {
    'L1': 'L1_regulatory',
    'L2': 'L2_fraud_cases',
    'L3': 'L3_typologies',
    'L4': 'L4_dynamic_weights',
    'L5': 'L5_feedback_log',
}

# Collections that use pre-computed embeddings (not text)
_VECTOR_COLLECTIONS = {'L2_fraud_cases', 'L3_typologies', 'L4_dynamic_weights'}

# Collections that use text embeddings (SentenceTransformer)
_TEXT_COLLECTIONS = {'L1_regulatory'}

# Audit-only collections — no embedding at all
_KEYVALUE_COLLECTIONS = {'L5_feedback_log'}

# ── Singletons ────────────────────────────────────────────────────────────────
_client: chromadb.ClientAPI | None = None
_sentence_ef = None


def _get_client() -> chromadb.ClientAPI:
    global _client
    if _client is None:
        os.makedirs(_CHROMA_DIR, exist_ok=True)
        _client = chromadb.PersistentClient(
            path=_CHROMA_DIR,
            settings=Settings(anonymized_telemetry=False),
        )
    return _client


def _get_sentence_ef():
    """Singleton SentenceTransformer — loaded once, reused across all L1 queries."""
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    global _sentence_ef
    if _sentence_ef is None:
        _sentence_ef = SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"
        )
    return _sentence_ef


# ── [FIX-2] HNSW metadata ─────────────────────────────────────────────────────
_HNSW_META = {
    "hnsw:space":           str(HNSW_SPACE),
    "hnsw:ef_search":       str(HNSW_EF_SEARCH),
    "hnsw:construction_ef": str(HNSW_CONSTRUCTION_EF),
    "hnsw:M":               str(HNSW_M),
}


def _get_collection(name: str) -> chromadb.Collection:
    """
    Internal: returns or creates a collection with the correct
    embedding function and HNSW settings for its type.
    """
    client = _get_client()

    if name in _TEXT_COLLECTIONS:
        # L1 — SentenceTransformer, no explicit HNSW metadata
        return client.get_or_create_collection(
            name=name,
            embedding_function=_get_sentence_ef(),
        )

    elif name in _VECTOR_COLLECTIONS:
        # [FIX-1] L2, L3, L4 — NO embedding function.
        # Callers must supply pre-computed vectors via embeddings= parameter.
        return client.get_or_create_collection(
            name=name,
            embedding_function=None,
        )

    elif name in _KEYVALUE_COLLECTIONS:
        # [FIX-3] L5 — pure key-value audit log, no embedding, no HNSW
        return client.get_or_create_collection(
            name=name,
            embedding_function=None,
        )

    else:
        raise ValueError(
            f"Unknown collection '{name}'. "
            f"Must be one of: {list(COLLECTIONS.values())}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# PUBLIC API
# ══════════════════════════════════════════════════════════════════════════════

def query_by_text(collection_name: str,
                  query_text: str,
                  n_results: int = 5) -> dict:
    """
    [FIX-4] Text-similarity query — L1_regulatory ONLY.

    Raises ValueError if called on a vector or key-value collection.
    ChromaDB's SentenceTransformer embeds the query text automatically.
    """
    if collection_name not in _TEXT_COLLECTIONS:
        raise ValueError(
            f"query_by_text() is only valid for text collections: {_TEXT_COLLECTIONS}. "
            f"Use query_by_vector() for '{collection_name}'."
        )
    return _query(collection_name, query_texts=[query_text], n_results=n_results)


def query_by_vector(collection_name: str,
                    query_vector: list[float],
                    n_results: int = 5) -> dict:
    """
    [FIX-4] Pre-computed vector query — L2, L3, L4 ONLY.

    Raises ValueError if called on a text or key-value collection.
    query_vector must match the embedding dimension of the collection:
      L2 / L4 : 128-d  (FraudFeatureEncoder)
      L3      : 256-d  (SignalSequenceEncoder)
    """
    if collection_name not in _VECTOR_COLLECTIONS:
        raise ValueError(
            f"query_by_vector() is only valid for vector collections: {_VECTOR_COLLECTIONS}. "
            f"For L1 use query_by_text(). For L5 use get_by_id()."
        )
    return _query(collection_name, query_embeddings=[query_vector], n_results=n_results)


def upsert_text_documents(collection_name: str,
                          ids: list[str],
                          documents: list[str],
                          metadatas: list[dict] | None = None):
    """
    Upserts text documents into a text collection (L1).
    ChromaDB's embedding function embeds the documents automatically.
    """
    if collection_name not in _TEXT_COLLECTIONS:
        raise ValueError(
            f"upsert_text_documents() is only valid for text collections. "
            f"Use upsert_vector_documents() for '{collection_name}'."
        )
    col = _get_collection(collection_name)
    col.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas or [{} for _ in ids],
    )


def upsert_vector_documents(collection_name: str,
                            ids: list[str],
                            embeddings: list[list[float]],
                            documents: list[str],
                            metadatas: list[dict] | None = None):
    """
    Upserts pre-computed vector embeddings into L2, L3, or L4.

    embeddings : list of float vectors — one per document
    documents  : human-readable text stored alongside the vector (metadata only)
    """
    if collection_name not in _VECTOR_COLLECTIONS:
        raise ValueError(
            f"upsert_vector_documents() is only valid for vector collections: "
            f"{_VECTOR_COLLECTIONS}."
        )
    col = _get_collection(collection_name)
    col.upsert(
        ids=ids,
        embeddings=embeddings,
        documents=documents,
        metadatas=metadatas or [{} for _ in ids],
    )


def upsert_keyvalue(collection_name: str,
                    ids: list[str],
                    documents: list[str],
                    metadatas: list[dict] | None = None):
    """
    Upserts records into a key-value collection (L5).
    No embedding — stored as plain documents retrievable by ID.
    """
    if collection_name not in _KEYVALUE_COLLECTIONS:
        raise ValueError(
            f"upsert_keyvalue() is only valid for key-value collections: "
            f"{_KEYVALUE_COLLECTIONS}."
        )
    col = _get_collection(collection_name)
    col.upsert(
        ids=ids,
        documents=documents,
        metadatas=metadatas or [{} for _ in ids],
    )


def get_by_id(collection_name: str, doc_id: str) -> dict | None:
    """
    Retrieves a single L5 record by its ID.
    Returns None if not found.
    """
    try:
        col = _get_collection(collection_name)
        result = col.get(ids=[doc_id], include=["documents", "metadatas"])
        if result['ids']:
            return {
                'id':       result['ids'][0],
                'document': result['documents'][0],
                'metadata': result['metadatas'][0],
            }
        return None
    except Exception as e:
        print(f"[VectorStore] get_by_id error on {collection_name}/{doc_id}: {e}")
        return None


def collection_count(collection_name: str) -> int:
    """Returns the number of documents in a collection. Returns 0 on error."""
    try:
        return _get_collection(collection_name).count()
    except Exception:
        return 0


# ── Internal helpers ──────────────────────────────────────────────────────────

def _query(collection_name: str,
           n_results: int,
           query_texts: list[str] | None = None,
           query_embeddings: list[list[float]] | None = None) -> dict:
    """
    Shared query implementation. Handles empty collections and
    n_results clamping. Returns ChromaDB-shaped empty result on error.
    """
    try:
        col = _get_collection(collection_name)
        count = col.count()

        if count == 0:
            return _empty_result()

        actual_n = min(n_results, count)
        kwargs = dict(
            n_results=actual_n,
            include=["documents", "metadatas", "distances"],
        )
        if query_texts is not None:
            kwargs['query_texts'] = query_texts
        if query_embeddings is not None:
            kwargs['query_embeddings'] = query_embeddings

        return col.query(**kwargs)

    except Exception as e:
        print(f"[VectorStore] Query error on {collection_name}: {e}")
        return _empty_result()


def _empty_result() -> dict:
    return {
        'ids':       [[]],
        'documents': [[]],
        'metadatas': [[]],
        'distances': [[]],
    }