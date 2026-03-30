"""
ingest_cases.py  (shared_rag/kb_ingest)
────────────────────────────────────────
Seeds the L2_fraud_cases ChromaDB collection with synthetic historical cases.
Moved from et_service/monitoring_agent/rag/kb_ingest/ingest_cases.py.

Key fixes maintained:
  [FIX-1] L2 embeddings use encode_features_for_l2() (128-d feature projection),
           NOT SentenceTransformer text embeddings.
  [FIX-2] Each case carries 'confirmed_risk_score' for rag_layer._score_l2().

Run before any agent goes live:
  python -m et_service.shared_rag.kb_ingest.ingest_cases

Idempotent — uses upsert.
"""

import sys
import os

_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, '..', '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from et_service.shared_rag.vector_store import (
    upsert_vector_documents, collection_count, COLLECTIONS
)
from et_service.shared_rag.encoders import encode_features_for_l2

# Import the canonical FRAUD_CASES list from the TMA ingest module.
# This is the single source of truth — the TMA already has correct
# features and confirmed_risk_score metadata applied (FIX-1 / FIX-2).
from et_service.monitoring_agent.rag.kb_ingest.ingest_cases import FRAUD_CASES


def ingest():
    """Seeds the L2_fraud_cases collection with historical fraud cases."""
    collection_name = COLLECTIONS['L2']
    ids       = [c['id'] for c in FRAUD_CASES]
    documents = [c['text'] for c in FRAUD_CASES]
    metadatas = [c['metadata'] for c in FRAUD_CASES]
    embeddings = [encode_features_for_l2(c['features']) for c in FRAUD_CASES]

    upsert_vector_documents(collection_name, ids, embeddings, documents, metadatas)
    count = collection_count(collection_name)
    print(f"✅ L2_fraud_cases seeded with {count} historical cases.")


if __name__ == '__main__':
    ingest()
