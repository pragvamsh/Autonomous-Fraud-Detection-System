"""
ingest_regulatory.py
────────────────────
One-time script to seed the L1_regulatory ChromaDB collection
with Indian banking compliance rules (RBI / PMLA / FEMA).

Run before TMA goes live:
  python -m et_service.monitoring_agent.rag.kb_ingest.ingest_regulatory

Idempotent — uses upsert, safe to run multiple times.
"""

import sys
import os

# Ensure project root is on sys.path for imports
_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, '..', '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from et_service.monitoring_agent.rag.vector_store import (
    upsert_text_documents, collection_count, COLLECTIONS
)

# ── Regulatory rule documents ─────────────────────────────────────────────────
# Each document represents a specific compliance rule or threshold.
# The text is written in a style that maximises embedding similarity
# when the encoder builds queries about amounts and thresholds.

REGULATORY_RULES = [
    {
        "id": "RBI-CTR-10K",
        "text": (
            "Cash Transaction Report (CTR): All cash transactions of Rs 10,00,000 "
            "(ten lakh rupees) and above, or series of integrally connected cash "
            "transactions within a month totalling Rs 10,00,000, must be reported "
            "to the Financial Intelligence Unit (FIU-IND) within 15 days. "
            "This applies to both single transactions and aggregate amounts."
        ),
        "metadata": {
            "rule_type": "reporting_threshold",
            "threshold_amount": 1000000,
            "source": "RBI Master Direction on KYC",
            "severity": "HIGH",
        },
    },
    {
        "id": "RBI-STR-SUSPICIOUS",
        "text": (
            "Suspicious Transaction Report (STR): Banks must report any transaction "
            "where there are reasonable grounds to suspect that the transaction "
            "involves proceeds of crime, regardless of the amount. Indicators include "
            "unusual patterns, structuring to avoid thresholds, transactions "
            "inconsistent with customer profile, and rapid movement of funds."
        ),
        "metadata": {
            "rule_type": "suspicious_activity",
            "source": "PMLA Act 2002, Section 12",
            "severity": "CRITICAL",
        },
    },
    {
        "id": "RBI-STRUCTURING",
        "text": (
            "Structuring Detection: Multiple transactions deliberately kept just "
            "below reporting thresholds (e.g., Rs 9,999 or Rs 49,999) to avoid "
            "triggering Cash Transaction Reports are considered structuring. "
            "This is a violation under PMLA and must be flagged as suspicious. "
            "Look for amounts in the Rs 9,000-9,999 and Rs 49,000-49,999 ranges."
        ),
        "metadata": {
            "rule_type": "structuring",
            "source": "PMLA Rules 2005",
            "severity": "HIGH",
        },
    },
    {
        "id": "RBI-HIGH-VALUE-50K",
        "text": (
            "High Value Transaction Monitoring: Transactions above Rs 50,000 "
            "require enhanced due diligence. For new customers or customers with "
            "fewer than 3 months of history, transactions above Rs 50,000 to "
            "new recipients should be flagged for additional verification. "
            "Banks must maintain records of all transactions above Rs 50,000."
        ),
        "metadata": {
            "rule_type": "reporting_threshold",
            "threshold_amount": 50000,
            "source": "RBI Circular on Enhanced Due Diligence",
            "severity": "MEDIUM",
        },
    },
    {
        "id": "RBI-RAPID-MOVEMENT",
        "text": (
            "Rapid Fund Movement: Multiple transactions executed in quick "
            "succession (more than 3 transactions within 1 hour) may indicate "
            "automated or scripted fraud attacks. This pattern is especially "
            "suspicious when combined with new recipients or large amounts. "
            "Banks should implement velocity checks and flag burst patterns."
        ),
        "metadata": {
            "rule_type": "velocity_rule",
            "source": "RBI Guidelines on Digital Payment Security",
            "severity": "HIGH",
        },
    },
    {
        "id": "RBI-UNUSUAL-HOURS",
        "text": (
            "Unusual Hour Transactions: Transactions conducted during unusual "
            "hours (midnight to 5 AM) that deviate significantly from a "
            "customer's established pattern warrant additional scrutiny. "
            "This is especially relevant for high-value transfers to new "
            "recipients during off-hours."
        ),
        "metadata": {
            "rule_type": "time_rule",
            "source": "RBI Fraud Risk Management Framework",
            "severity": "MEDIUM",
        },
    },
    {
        "id": "PMLA-KYC-VERIFICATION",
        "text": (
            "KYC Verification Requirements: For transactions exceeding "
            "Rs 10,000 to new recipients, banks must verify the customer's "
            "KYC is up to date. Expired or incomplete KYC combined with "
            "high-value transfers is a critical risk indicator. Minor account "
            "holders (under 18) require guardian authorisation for all payments."
        ),
        "metadata": {
            "rule_type": "kyc_rule",
            "source": "RBI KYC Master Direction 2016",
            "severity": "MEDIUM",
        },
    },
    {
        "id": "RBI-DORMANT-REACTIVATION",
        "text": (
            "Dormant Account Reactivation: An account with no transactions "
            "for 12 months or more that suddenly resumes activity — especially "
            "with large outgoing transfers — must be flagged for review. "
            "This pattern is associated with account takeover and money mule "
            "recruitment."
        ),
        "metadata": {
            "rule_type": "dormant_account",
            "source": "RBI Master Circular on Inoperative Accounts",
            "severity": "HIGH",
        },
    },
    {
        "id": "RBI-CROSS-BORDER-FEMA",
        "text": (
            "Cross-Border Transaction Limits: Under FEMA guidelines, "
            "individual remittances up to USD 250,000 per financial year are "
            "permitted under the Liberalised Remittance Scheme (LRS). "
            "Domestic transactions that appear to structure amounts for "
            "potential cross-border transfer should be monitored."
        ),
        "metadata": {
            "rule_type": "cross_border",
            "source": "FEMA Act 1999, LRS Guidelines",
            "severity": "MEDIUM",
        },
    },
    {
        "id": "RBI-DAILY-VOLUME-LIMIT",
        "text": (
            "Daily Transaction Volume Monitoring: If a customer's daily "
            "transaction volume exceeds twice their average daily volume "
            "over the past 90 days, the excess transactions require enhanced "
            "monitoring. This rule catches sudden spikes in transactional "
            "behaviour that may indicate account compromise."
        ),
        "metadata": {
            "rule_type": "volume_rule",
            "source": "RBI Digital Payment Security Controls",
            "severity": "MEDIUM",
        },
    },
]


def ingest():
    """Seeds the L1_regulatory collection with compliance rules."""
    collection_name = COLLECTIONS['L1']

    ids       = [r['id'] for r in REGULATORY_RULES]
    documents = [r['text'] for r in REGULATORY_RULES]
    metadatas = [r['metadata'] for r in REGULATORY_RULES]

    upsert_text_documents(collection_name, ids, documents, metadatas)

    count = collection_count(collection_name)
    print(f"✅ L1_regulatory seeded with {count} regulatory rules.")


if __name__ == '__main__':
    ingest()
