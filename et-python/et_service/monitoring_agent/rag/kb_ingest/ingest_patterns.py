"""
ingest_patterns.py
──────────────────
One-time script to seed the L3_typologies ChromaDB collection
with fraud pattern typology documents.

Each typology describes a known fraud technique with its
characteristic signals, allowing the RAG layer to match
transactions against established attack patterns.

Run before TMA goes live:
  python -m et_service.monitoring_agent.rag.kb_ingest.ingest_patterns

Idempotent — uses upsert, safe to run multiple times.
"""

import sys
import os
from sentence_transformers import SentenceTransformer

_SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.abspath(os.path.join(_SCRIPT_DIR, '..', '..', '..', '..'))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from et_service.monitoring_agent.rag.vector_store import (
    upsert_vector_documents, collection_count, COLLECTIONS
)

# ── Fraud typology patterns ────────────────────────────────────────────────────

TYPOLOGIES = [
    {
        "id": "TYPO-001-ACCOUNT-TAKEOVER",
        "text": (
            "Account Takeover (ATO): An attacker gains unauthorised access to "
            "a legitimate customer's account through phishing, credential stuffing, "
            "or SIM swapping. Key indicators: transactions at unusual hours "
            "(especially late night), large payments to new recipients never "
            "seen before, rapid succession of transfers (velocity burst), "
            "amount significantly above customer's normal range (high z-score), "
            "and behaviour diverging sharply from established profile. "
            "Risk: CRITICAL. Typical loss: Rs 20,000 to Rs 5,00,000."
        ),
        "metadata": {
            "typology": "account_takeover",
            "key_signals": "unusual_hour,new_recipient,velocity_burst,high_z_score",
            "risk_level": "CRITICAL",
        },
    },
    {
        "id": "TYPO-002-STRUCTURING-SMURFING",
        "text": (
            "Structuring / Smurfing: Deliberately breaking a large transaction "
            "into multiple smaller ones to avoid regulatory reporting thresholds. "
            "Key indicators: multiple transactions with amounts just below "
            "Rs 10,000 or Rs 50,000 thresholds (e.g., Rs 9,500 or Rs 49,500), "
            "transactions to multiple different recipients within a short period, "
            "exceeding daily volume threshold, and round or near-round amounts. "
            "This violates PMLA 2002 structuring provisions. "
            "Risk: HIGH. Regulatory reporting required."
        ),
        "metadata": {
            "typology": "structuring",
            "key_signals": "near_threshold,multiple_recipients,daily_volume_exceeded",
            "risk_level": "HIGH",
        },
    },
    {
        "id": "TYPO-003-MONEY-MULE",
        "text": (
            "Money Mule: An account used as an intermediary to launder "
            "illicit funds. The account holder may be complicit or unknowing. "
            "Key indicators: dormant account suddenly reactivated with large "
            "deposits followed by immediate withdrawals or transfers, cold start "
            "profile or minimal transaction history, funds moved to new "
            "recipients rapidly, and amounts significantly above historical norm. "
            "Risk: CRITICAL. Law enforcement referral required."
        ),
        "metadata": {
            "typology": "money_mule",
            "key_signals": "cold_start,large_amount,rapid_movement,new_recipient",
            "risk_level": "CRITICAL",
        },
    },
    {
        "id": "TYPO-004-VELOCITY-ATTACK",
        "text": (
            "Velocity Attack: Automated or semi-automated execution of multiple "
            "transactions in rapid succession. Often seen in compromised accounts "
            "where the attacker scripts transfers before detection. "
            "Key indicators: more than 3 transactions within 1 hour (velocity burst), "
            "transfers to multiple new recipients, amounts may individually be small "
            "but aggregate total is significant, and execution at unusual hours. "
            "Risk: HIGH. Account lock recommended immediately."
        ),
        "metadata": {
            "typology": "velocity_attack",
            "key_signals": "velocity_burst,multiple_new_recipients,unusual_hour",
            "risk_level": "HIGH",
        },
    },
    {
        "id": "TYPO-005-SOCIAL-ENGINEERING",
        "text": (
            "Social Engineering / Phishing-Induced Transfer: Customer is "
            "manipulated into voluntarily initiating a payment to a fraudster. "
            "Unlike ATO, the customer's own credentials and device are used. "
            "Key indicators: single large transfer to new recipient, amount "
            "significantly above average (high z-score), may occur during "
            "normal business hours (distinguishing from ATO), and customer "
            "may describe urgency or pressure. "
            "Risk: MEDIUM-HIGH. Harder to detect than ATO due to legitimate session."
        ),
        "metadata": {
            "typology": "social_engineering",
            "key_signals": "new_recipient,high_z_score,large_amount",
            "risk_level": "MEDIUM-HIGH",
        },
    },
    {
        "id": "TYPO-006-FIRST-PARTY-FRAUD",
        "text": (
            "First-Party Fraud: The account holder themselves commits fraud, "
            "typically by depositing funds, transferring them out, then "
            "disputing the original deposit or claiming account compromise. "
            "Key indicators: new account with minimal history (cold start), "
            "large deposit immediately followed by large withdrawal to "
            "external account, amount near account limits or regulatory "
            "thresholds, and single new recipient. "
            "Risk: HIGH. Claim investigation required."
        ),
        "metadata": {
            "typology": "first_party_fraud",
            "key_signals": "cold_start,large_amount,near_threshold,new_recipient",
            "risk_level": "HIGH",
        },
    },
    {
        "id": "TYPO-007-DORMANT-EXPLOITATION",
        "text": (
            "Dormant Account Exploitation: A rarely-used or inactive account "
            "suddenly shows high-value activity. May indicate account takeover "
            "or recruitment as a money mule. "
            "Key indicators: no transactions for 3+ months then sudden burst, "
            "cold start profile despite account age, large amounts relative to "
            "historical activity, transfers to unfamiliar recipients, and "
            "activity at unusual hours. "
            "Risk: HIGH. Enhanced due diligence required per RBI guidelines."
        ),
        "metadata": {
            "typology": "dormant_exploitation",
            "key_signals": "cold_start,large_amount,new_recipient,unusual_hour",
            "risk_level": "HIGH",
        },
    },
    {
        "id": "TYPO-008-ROUND-TRIPPING",
        "text": (
            "Round-Tripping / Layering: Funds circulated through multiple "
            "accounts to obscure origin. Customer sends money to recipient A, "
            "who sends to B, who returns to original sender or a related account. "
            "Key indicators: repeated transactions of identical or near-identical "
            "amounts, round number amounts (Rs 5,000, Rs 10,000, Rs 50,000), "
            "new recipients who then become senders, and high daily frequency. "
            "Risk: HIGH. AML investigation required."
        ),
        "metadata": {
            "typology": "round_tripping",
            "key_signals": "round_number,high_frequency,new_recipients",
            "risk_level": "HIGH",
        },
    },
]


def ingest():
    """Seeds the L3_typologies collection with fraud pattern documents."""
    collection_name = COLLECTIONS['L3']

    ids       = [t['id'] for t in TYPOLOGIES]
    documents = [t['text'] for t in TYPOLOGIES]
    metadatas = [t['metadata'] for t in TYPOLOGIES]

    # Generate embeddings from typology text using SentenceTransformer
    encoder = SentenceTransformer("all-MiniLM-L6-v2")
    embeddings = encoder.encode(documents).tolist()

    upsert_vector_documents(collection_name, ids, embeddings, documents, metadatas)

    count = collection_count(collection_name)
    print(f"✅ L3_typologies seeded with {count} fraud typology patterns.")


if __name__ == '__main__':
    ingest()
    ingest()
