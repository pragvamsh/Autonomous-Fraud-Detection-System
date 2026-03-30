"""
CLA DAO — Citation & Legal Archive Agent Database Access Layer

Manages database operations for:
  - cla_citations   : Citation library (regulatory, precedents, typologies)
  - cla_archive     : Archived STR filings with citation lineage
  - fraud_cases     : Case retrieval for CLA processing
  - regulatory_queue: STR/CTR filing status updates
"""

import json
from datetime import datetime
from typing import Optional, List, Dict, Any
from db import get_db_connection

# ═════════════════════════════════════════════════════════════════════════════
# CITATION LIBRARY — Write + Read
# ═════════════════════════════════════════════════════════════════════════════

def insert_citation(
    citation_id: str,
    category: str,  # 'REGULATORY', 'PRECEDENT', 'TYPOLOGY'
    source_layer: Optional[str],  # 'L1', 'L2', 'L3', etc.
    title: str,
    content: str,
    tags: Optional[List[str]] = None,
    severity: str = 'MEDIUM'
) -> bool:
    """
    Inserts a new citation into cla_citations.
    Returns True on success, False on failure.
    """
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        tags_json = json.dumps(tags) if tags else None
        cursor.execute("""
            INSERT INTO cla_citations
                (citation_id, category, source_layer, title, content, tags, severity)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (citation_id, category, source_layer, title, content, tags_json, severity))
        conn.commit()
        return True
    except Exception as e:
        print(f"[cla_dao] insert_citation error: {e}")
        return False
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_citation_by_id(citation_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a citation by citation_id.
    Returns dict or None.
    """
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM cla_citations WHERE citation_id = %s
        """, (citation_id,))
        row = cursor.fetchone()
        if row and row.get('tags'):
            row['tags'] = json.loads(row['tags'])
        return row
    except Exception as e:
        print(f"[cla_dao] get_citation_by_id error: {e}")
        return None
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_citations_by_category(category: str, limit: int = 50) -> List[Dict[str, Any]]:
    """
    Retrieves citations by category (REGULATORY, PRECEDENT, TYPOLOGY).
    Returns list of citation dicts.
    """
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM cla_citations
            WHERE category = %s
            ORDER BY severity DESC, created_at DESC
            LIMIT %s
        """, (category, limit))
        rows = cursor.fetchall()
        for row in rows:
            if row.get('tags'):
                row['tags'] = json.loads(row['tags'])
        return rows
    except Exception as e:
        print(f"[cla_dao] get_citations_by_category error: {e}")
        return []
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# ARCHIVE OPERATIONS — STR Filings
# ═════════════════════════════════════════════════════════════════════════════

def insert_archive(
    filing_id: str,
    case_id: str,
    alert_id: int,
    customer_id: str,
    filing_type: str,  # 'CTR' or 'STR'
    str_content: Dict[str, Any],
    citations_used: List[str],
    pdf_path: Optional[str] = None,
    filed_by: str = 'CLA_AUTO'
) -> bool:
    """
    Archives an STR/CTR filing with citation lineage.
    Returns True on success.
    """
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        str_json = json.dumps(str_content)
        citations_json = json.dumps(citations_used)
        filed_at = datetime.utcnow()

        cursor.execute("""
            INSERT INTO cla_archive
                (filing_id, case_id, alert_id, customer_id, filing_type,
                 str_content, citations_used, pdf_path, filed_at, filed_by)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        """, (filing_id, case_id, alert_id, customer_id, filing_type,
              str_json, citations_json, pdf_path, filed_at, filed_by))
        conn.commit()
        return True
    except Exception as e:
        print(f"[cla_dao] insert_archive error: {e}")
        return False
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_archive_by_filing_id(filing_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves an archived filing by filing_id.
    Returns dict or None.
    """
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM cla_archive WHERE filing_id = %s
        """, (filing_id,))
        row = cursor.fetchone()
        if row:
            if row.get('str_content'):
                row['str_content'] = json.loads(row['str_content'])
            if row.get('citations_used'):
                row['citations_used'] = json.loads(row['citations_used'])
        return row
    except Exception as e:
        print(f"[cla_dao] get_archive_by_filing_id error: {e}")
        return None
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_filing_by_case_id(case_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves the latest filing for a given case_id.
    Returns dict or None.

    Used when admin clicks "PDF" on a case row — gets the most recent filing.
    """
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM cla_archive
            WHERE case_id = %s
            ORDER BY archived_at DESC
            LIMIT 1
        """, (case_id,))
        row = cursor.fetchone()
        if row:
            if row.get('str_content'):
                row['str_content'] = json.loads(row['str_content'])
            if row.get('citations_used'):
                row['citations_used'] = json.loads(row['citations_used'])
        return row
    except Exception as e:
        print(f"[cla_dao] get_filing_by_case_id error: {e}")
        return None
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_archive_by_case_id(case_id: str) -> List[Dict[str, Any]]:
    """
    Retrieves all archived filings for a given case_id.
    Returns list of archive dicts (may be empty).
    """
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM cla_archive
            WHERE case_id = %s
            ORDER BY archived_at DESC
        """, (case_id,))
        rows = cursor.fetchall()
        for row in rows:
            if row.get('str_content'):
                row['str_content'] = json.loads(row['str_content'])
            if row.get('citations_used'):
                row['citations_used'] = json.loads(row['citations_used'])
        return rows
    except Exception as e:
        print(f"[cla_dao] get_archive_by_case_id error: {e}")
        return []
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()





# ═════════════════════════════════════════════════════════════════════════════
# FRAUD CASES — CLA Consumption
# ═════════════════════════════════════════════════════════════════════════════

def get_unclaimed_cases(limit: int = 10) -> List[Dict[str, Any]]:
    """
    Retrieves fraud_cases where cla_consumed = 0.
    Returns list of case dicts.
    """
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM fraud_cases
            WHERE cla_consumed = 0
            ORDER BY priority, created_at
            LIMIT %s
        """, (limit,))
        rows = cursor.fetchall()
        for row in rows:
            if row.get('evidence_pack'):
                row['evidence_pack'] = json.loads(row['evidence_pack'])
        return rows
    except Exception as e:
        print(f"[cla_dao] get_unclaimed_cases error: {e}")
        return []
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def mark_case_consumed(case_id: str) -> bool:
    """
    Marks a fraud_case as consumed by CLA (cla_consumed = 1).
    Returns True on success.
    """
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE fraud_cases
            SET cla_consumed = 1
            WHERE case_id = %s
        """, (case_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"[cla_dao] mark_case_consumed error: {e}")
        return False
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_case_by_id(case_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a fraud_case by case_id.
    Returns dict or None.
    """
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM fraud_cases WHERE case_id = %s
        """, (case_id,))
        row = cursor.fetchone()
        if row and row.get('evidence_pack'):
            row['evidence_pack'] = json.loads(row['evidence_pack'])
        return row
    except Exception as e:
        print(f"[cla_dao] get_case_by_id error: {e}")
        return None
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# REGULATORY QUEUE — STR/CTR Filings
# ═════════════════════════════════════════════════════════════════════════════

def get_filing_by_id(filing_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a regulatory_queue row by filing_id.
    Returns dict or None.
    """
    conn = get_db_connection()
    if not conn:
        return None
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM regulatory_queue WHERE filing_id = %s
        """, (filing_id,))
        row = cursor.fetchone()
        if row and row.get('draft_content'):
            row['draft_content'] = json.loads(row['draft_content'])
        return row
    except Exception as e:
        print(f"[cla_dao] get_filing_by_id error: {e}")
        return None
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def update_filing_status(
    filing_id: str,
    status: str,
    approved_by: Optional[str] = None
) -> bool:
    """
    Updates the status of a regulatory_queue filing.
    Returns True on success.
    """
    conn = get_db_connection()
    if not conn:
        return False
    try:
        cursor = conn.cursor()
        if approved_by:
            cursor.execute("""
                UPDATE regulatory_queue
                SET status = %s, approved_by = %s, approved_at = NOW()
                WHERE filing_id = %s
            """, (status, approved_by, filing_id))
        else:
            cursor.execute("""
                UPDATE regulatory_queue
                SET status = %s
                WHERE filing_id = %s
            """, (status, filing_id))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"[cla_dao] update_filing_status error: {e}")
        return False
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


def get_all_filings(limit: int = 100) -> List[Dict[str, Any]]:
    """
    Retrieves all regulatory_queue filings (for admin dashboard).
    Returns list of filing dicts.
    """
    conn = get_db_connection()
    if not conn:
        return []
    try:
        cursor = conn.cursor(dictionary=True)
        cursor.execute("""
            SELECT * FROM regulatory_queue
            ORDER BY created_at DESC
            LIMIT %s
        """, (limit,))
        rows = cursor.fetchall()
        for row in rows:
            if row.get('draft_content'):
                row['draft_content'] = json.loads(row['draft_content'])
        return rows
    except Exception as e:
        print(f"[cla_dao] get_all_filings error: {e}")
        return []
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()


# ═════════════════════════════════════════════════════════════════════════════
# ADMIN DASHBOARD QUERIES
# ═════════════════════════════════════════════════════════════════════════════

def get_dashboard_stats() -> Dict[str, Any]:
    """
    Returns aggregated statistics for the admin dashboard.
    """
    conn = get_db_connection()
    if not conn:
        return {}
    try:
        cursor = conn.cursor(dictionary=True)

        # Pending STR count
        cursor.execute("""
            SELECT COUNT(*) as pending_str
            FROM regulatory_queue
            WHERE type = 'STR' AND status = 'PENDING_APPROVAL'
        """)
        pending_str = cursor.fetchone()['pending_str']

        # Filed STR count
        cursor.execute("""
            SELECT COUNT(*) as filed_str
            FROM regulatory_queue
            WHERE type = 'STR' AND status = 'FILED'
        """)
        filed_str = cursor.fetchone()['filed_str']

        # Pending CTR count
        cursor.execute("""
            SELECT COUNT(*) as pending_ctr
            FROM regulatory_queue
            WHERE type = 'CTR' AND status = 'PENDING_APPROVAL'
        """)
        pending_ctr = cursor.fetchone()['pending_ctr']

        # Open fraud cases
        cursor.execute("""
            SELECT COUNT(*) as open_cases
            FROM fraud_cases
            WHERE status IN ('OPEN', 'INVESTIGATING')
        """)
        open_cases = cursor.fetchone()['open_cases']

        # Total citations
        cursor.execute("""
            SELECT COUNT(*) as total_citations
            FROM cla_citations
        """)
        total_citations = cursor.fetchone()['total_citations']

        return {
            'pending_str': pending_str,
            'filed_str': filed_str,
            'pending_ctr': pending_ctr,
            'open_cases': open_cases,
            'total_citations': total_citations
        }
    except Exception as e:
        print(f"[cla_dao] get_dashboard_stats error: {e}")
        return {}
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()
