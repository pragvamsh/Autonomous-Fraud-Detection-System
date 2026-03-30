"""
Citation Archiver — Converts ChromaDB RAG citations into MySQL cla_citations

Syncs citations from ChromaDB collections (L1, L2, L3) into the cla_citations
table so they can be referenced in STR filings with permanent IDs and traceability.
"""

import hashlib
import json
from typing import List, Dict, Any, Optional
from et_dao.cla_dao import insert_citation, get_citation_by_id
from et_service.shared_rag.vector_store import query_by_text, COLLECTIONS


def _generate_citation_id(content: str, category: str) -> str:
    """
    Generates a unique citation_id from content hash + category.
    Format: CIT-{category}-{hash[:8]}
    """
    hash_hex = hashlib.sha256(content.encode('utf-8')).hexdigest()[:8]
    return f"CIT-{category[0]}-{hash_hex}"


def archive_citation_from_rag(
    rag_result: Dict[str, Any],
    category: str,  # 'REGULATORY', 'PRECEDENT', 'TYPOLOGY'
    source_layer: str  # 'L1', 'L2', 'L3'
) -> Optional[str]:
    """
    Archives a single RAG result as a citation in cla_citations.
    Returns citation_id on success, None on failure.

    Expected rag_result structure (from ChromaDB query):
    {
        'metadatas': [[{...}]],
        'documents': [['text content']],
        'distances': [[float]]
    }
    """
    if not rag_result or not rag_result.get('documents'):
        return None

    try:
        # Extract first result
        docs = rag_result['documents']
        metas = rag_result.get('metadatas', [[]])

        if not docs or not docs[0]:
            return None

        content = docs[0][0] if isinstance(docs[0], list) else docs[0]
        metadata = metas[0][0] if (metas and metas[0]) else {}

        # Generate citation ID
        citation_id = _generate_citation_id(content, category)

        # Check if already exists
        existing = get_citation_by_id(citation_id)
        if existing:
            return citation_id

        # Extract title from metadata or truncate content
        title = metadata.get('title', metadata.get('name', content[:100]))

        # Extract tags from metadata
        tags = metadata.get('tags', [])
        if isinstance(tags, str):
            tags = [tags]

        # Determine severity
        severity = metadata.get('severity', 'MEDIUM')

        # Insert into cla_citations
        success = insert_citation(
            citation_id=citation_id,
            category=category,
            source_layer=source_layer,
            title=title,
            content=content,
            tags=tags,
            severity=severity
        )

        return citation_id if success else None

    except Exception as e:
        print(f"[citation_archiver] Error archiving citation: {e}")
        return None


def archive_l1_regulatory(query_text: str, n_results: int = 3) -> List[str]:
    """
    Queries L1_regulatory collection and archives top results as REGULATORY citations.
    Returns list of citation_ids.
    """
    try:
        results = query_by_text('L1_regulatory', query_text, n_results=n_results)
        citation_ids = []

        if not results or not results.get('documents'):
            return citation_ids

        docs = results['documents'][0] if isinstance(results['documents'][0], list) else results['documents']
        metas = results.get('metadatas', [[]])[0] if results.get('metadatas') else []

        for idx, doc in enumerate(docs):
            metadata = metas[idx] if idx < len(metas) else {}
            rag_result = {
                'documents': [[doc]],
                'metadatas': [[metadata]],
                'distances': [[results.get('distances', [[]])[0][idx] if results.get('distances') else 0]]
            }
            citation_id = archive_citation_from_rag(rag_result, 'REGULATORY', 'L1')
            if citation_id:
                citation_ids.append(citation_id)

        return citation_ids
    except Exception as e:
        print(f"[citation_archiver] Error archiving L1: {e}")
        return []


def archive_l2_precedents(query_text: str, n_results: int = 3) -> List[str]:
    """
    Queries L2_fraud_cases and archives top results as PRECEDENT citations.
    Returns list of citation_ids.
    """
    try:
        # For L2, we need to use query_by_vector with a text embedding
        from et_service.shared_rag.vector_store import get_sentence_transformer
        model = get_sentence_transformer()
        query_vec = model.encode(query_text).tolist()

        from et_service.shared_rag.vector_store import query_by_vector
        results = query_by_vector('L2_fraud_cases', [query_vec], n_results=n_results)

        citation_ids = []

        if not results or not results.get('documents'):
            return citation_ids

        docs = results['documents'][0] if isinstance(results['documents'][0], list) else results['documents']
        metas = results.get('metadatas', [[]])[0] if results.get('metadatas') else []

        for idx, doc in enumerate(docs):
            metadata = metas[idx] if idx < len(metas) else {}
            rag_result = {
                'documents': [[doc]],
                'metadatas': [[metadata]],
                'distances': [[results.get('distances', [[]])[0][idx] if results.get('distances') else 0]]
            }
            citation_id = archive_citation_from_rag(rag_result, 'PRECEDENT', 'L2')
            if citation_id:
                citation_ids.append(citation_id)

        return citation_ids
    except Exception as e:
        print(f"[citation_archiver] Error archiving L2: {e}")
        return []


def archive_l3_typologies(query_text: str, n_results: int = 3) -> List[str]:
    """
    Queries L3_typologies and archives top results as TYPOLOGY citations.
    Returns list of citation_ids.
    """
    try:
        # For L3, we need to use query_by_vector with a text embedding
        from et_service.shared_rag.vector_store import get_sentence_transformer
        model = get_sentence_transformer()
        query_vec = model.encode(query_text).tolist()

        from et_service.shared_rag.vector_store import query_by_vector
        results = query_by_vector('L3_typologies', [query_vec], n_results=n_results)

        citation_ids = []

        if not results or not results.get('documents'):
            return citation_ids

        docs = results['documents'][0] if isinstance(results['documents'][0], list) else results['documents']
        metas = results.get('metadatas', [[]])[0] if results.get('metadatas') else []

        for idx, doc in enumerate(docs):
            metadata = metas[idx] if idx < len(metas) else {}
            rag_result = {
                'documents': [[doc]],
                'metadatas': [[metadata]],
                'distances': [[results.get('distances', [[]])[0][idx] if results.get('distances') else 0]]
            }
            citation_id = archive_citation_from_rag(rag_result, 'TYPOLOGY', 'L3')
            if citation_id:
                citation_ids.append(citation_id)

        return citation_ids
    except Exception as e:
        print(f"[citation_archiver] Error archiving L3: {e}")
        return []


def archive_from_alert_citations(alert_citations: Dict[str, Any]) -> List[str]:
    """
    Processes alert citations from fraud_alerts and archives them.

    Expected alert_citations format (from fraud_alerts.rag_citations or raa_citations):
    {
        'L1': [...],
        'L2': [...],
        'L3': [...]
    }

    Returns list of all archived citation_ids.
    """
    all_citation_ids = []

    try:
        # Archive L1 regulatory citations
        if alert_citations.get('L1'):
            for citation_data in alert_citations['L1']:
                content = citation_data.get('text', citation_data.get('content', ''))
                if content:
                    citation_id = _generate_citation_id(content, 'REGULATORY')
                    existing = get_citation_by_id(citation_id)
                    if not existing:
                        title = citation_data.get('title', content[:100])
                        tags = citation_data.get('tags', [])
                        severity = citation_data.get('severity', 'MEDIUM')
                        success = insert_citation(
                            citation_id=citation_id,
                            category='REGULATORY',
                            source_layer='L1',
                            title=title,
                            content=content,
                            tags=tags,
                            severity=severity
                        )
                        if success:
                            all_citation_ids.append(citation_id)
                    else:
                        all_citation_ids.append(citation_id)

        # Archive L2 precedent citations
        if alert_citations.get('L2'):
            for citation_data in alert_citations['L2']:
                content = citation_data.get('text', citation_data.get('content', ''))
                if content:
                    citation_id = _generate_citation_id(content, 'PRECEDENT')
                    existing = get_citation_by_id(citation_id)
                    if not existing:
                        title = citation_data.get('title', content[:100])
                        tags = citation_data.get('tags', [])
                        severity = citation_data.get('severity', 'MEDIUM')
                        success = insert_citation(
                            citation_id=citation_id,
                            category='PRECEDENT',
                            source_layer='L2',
                            title=title,
                            content=content,
                            tags=tags,
                            severity=severity
                        )
                        if success:
                            all_citation_ids.append(citation_id)
                    else:
                        all_citation_ids.append(citation_id)

        # Archive L3 typology citations
        if alert_citations.get('L3'):
            for citation_data in alert_citations['L3']:
                content = citation_data.get('text', citation_data.get('content', ''))
                if content:
                    citation_id = _generate_citation_id(content, 'TYPOLOGY')
                    existing = get_citation_by_id(citation_id)
                    if not existing:
                        title = citation_data.get('title', content[:100])
                        tags = citation_data.get('tags', [])
                        severity = citation_data.get('severity', 'MEDIUM')
                        success = insert_citation(
                            citation_id=citation_id,
                            category='TYPOLOGY',
                            source_layer='L3',
                            title=title,
                            content=content,
                            tags=tags,
                            severity=severity
                        )
                        if success:
                            all_citation_ids.append(citation_id)
                    else:
                        all_citation_ids.append(citation_id)

        return all_citation_ids

    except Exception as e:
        print(f"[citation_archiver] Error archiving from alert citations: {e}")
        return all_citation_ids
