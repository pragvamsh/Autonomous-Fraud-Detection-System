"""
Term Glossary — User-friendly translations for technical fraud detection terms.

Used in PDF generation to make reports understandable for end users and admins.
Maps technical anomaly flags, typology codes, and verdicts to plain English.
"""

# ═══════════════════════════════════════════════════════════════════════════════
# ANOMALY FLAG TRANSLATIONS
# ═══════════════════════════════════════════════════════════════════════════════

ANOMALY_FLAG_TRANSLATIONS = {
    "EXTREME_AMOUNT_DEVIATION": {
        "title": "Extreme Amount Deviation",
        "description": "This transaction amount is significantly higher than your usual spending pattern (more than 3 standard deviations from your average).",
        "severity": "HIGH"
    },
    "HIGH_AMOUNT_DEVIATION": {
        "title": "High Amount Deviation",
        "description": "This transaction amount is notably higher than your typical transactions (more than 2 standard deviations from your average).",
        "severity": "MEDIUM"
    },
    "EXCEEDS_PERSONAL_MAX": {
        "title": "Exceeds Personal Maximum",
        "description": "This transaction exceeds the highest single transaction you have ever made.",
        "severity": "MEDIUM"
    },
    "EXCEEDS_DAILY_VOLUME_THRESHOLD": {
        "title": "Daily Spending Limit Exceeded",
        "description": "Your total transactions today significantly exceed your normal daily spending pattern.",
        "severity": "MEDIUM"
    },
    "LARGE_AMOUNT_10X_AVERAGE": {
        "title": "Unusually Large Amount",
        "description": "This transaction is more than 10 times your average transaction amount.",
        "severity": "HIGH"
    },
    "STRUCTURING_SIGNAL_NEAR_THRESHOLD": {
        "title": "Potential Structuring Pattern",
        "description": "The transaction amount is suspiciously close to regulatory reporting thresholds, which may indicate an attempt to avoid detection.",
        "severity": "HIGH"
    },
    "NEW_RECIPIENT_NEVER_TRANSACTED": {
        "title": "New Recipient",
        "description": "You have never sent money to this recipient before.",
        "severity": "LOW"
    },
    "UNUSUAL_HOUR": {
        "title": "Unusual Transaction Time",
        "description": "This transaction occurred outside your typical active hours.",
        "severity": "LOW"
    },
    "LATE_NIGHT_TRANSACTION": {
        "title": "Late Night Transaction",
        "description": "This transaction occurred during late night hours (12 AM - 5 AM), which is statistically associated with higher fraud risk.",
        "severity": "MEDIUM"
    },
    "VELOCITY_BURST": {
        "title": "Rapid Transaction Burst",
        "description": "Multiple transactions were made in quick succession (more than 3 transactions within 1 hour).",
        "severity": "HIGH"
    },
    "HIGH_DAILY_FREQUENCY": {
        "title": "High Transaction Frequency",
        "description": "You have made an unusually high number of transactions today (more than 10).",
        "severity": "MEDIUM"
    },
    "HIGH_RISK_COMPOSITE: large_amount + new_recipient": {
        "title": "High-Risk Combination",
        "description": "This combines two risk factors: a large transaction sent to a recipient you have never transacted with before.",
        "severity": "HIGH"
    },
    "HIGH_RISK_COMPOSITE: late_night + new_recipient": {
        "title": "Late Night to Unknown Recipient",
        "description": "A late-night transaction to a recipient you have never used before raises additional concern.",
        "severity": "HIGH"
    },
    "ROUND_NUMBER_AMOUNT": {
        "title": "Round Number Amount",
        "description": "The transaction is for a round number amount (e.g., Rs 10,000, Rs 50,000), which is sometimes associated with suspicious activity.",
        "severity": "LOW"
    },
    "DORMANT_ACCOUNT_ACTIVITY": {
        "title": "Dormant Account Reactivated",
        "description": "This account had little or no activity for an extended period before this transaction.",
        "severity": "MEDIUM"
    },
    "RAPID_FUND_MOVEMENT": {
        "title": "Rapid Fund Movement",
        "description": "Funds are being moved quickly through the account shortly after being received.",
        "severity": "HIGH"
    },
    "HIGH_RISK_RECIPIENT": {
        "title": "High-Risk Recipient",
        "description": "The recipient account has been previously associated with suspicious activity.",
        "severity": "HIGH"
    },
    "GEOGRAPHIC_ANOMALY": {
        "title": "Geographic Anomaly",
        "description": "The transaction location is unusual compared to your typical activity pattern.",
        "severity": "MEDIUM"
    },
    "SPLIT_TRANSACTION_PATTERN": {
        "title": "Split Transaction Pattern",
        "description": "Multiple smaller transactions appear to be split from what would normally be a single larger transaction.",
        "severity": "HIGH"
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# TYPOLOGY EXPLANATIONS
# ═══════════════════════════════════════════════════════════════════════════════

TYPOLOGY_EXPLANATIONS = {
    "TY-001": {
        "name": "Structuring / Smurfing",
        "explanation": "Breaking up large amounts into smaller transactions to avoid regulatory reporting thresholds. This is a common money laundering technique where transactions are deliberately kept below Rs 2,00,000 to evade Cash Transaction Reports (CTR)."
    },
    "TY-002": {
        "name": "Rapid Movement of Funds",
        "explanation": "Money moving quickly through multiple accounts within a short timeframe, often indicating an attempt to obscure the source of funds and make tracing difficult."
    },
    "TY-003": {
        "name": "High-Risk Jurisdiction Transfers",
        "explanation": "Transactions involving countries or regions known for weak anti-money laundering controls or high corruption indices."
    },
    "TY-004": {
        "name": "Unusual Transaction Patterns",
        "explanation": "Transaction behavior that does not match normal customer activity or stated business purpose. This includes sudden changes in transaction volume, frequency, or recipients."
    },
    "TY-005": {
        "name": "Money Mule Activity",
        "explanation": "Account appears to be used as an intermediary to move illicit funds. Money mules often receive funds and quickly transfer them elsewhere, sometimes unknowingly participating in fraud."
    },
    "TY-006": {
        "name": "Trade-Based Money Laundering",
        "explanation": "Using trade transactions (over/under invoicing, multiple invoicing) to disguise illegal money transfers as legitimate business transactions."
    },
    "TY-007": {
        "name": "Beneficial Owner Concealment",
        "explanation": "Attempts to hide the true owner or controller of funds through complex corporate structures, nominees, or shell companies."
    },
    "TY-008": {
        "name": "Round-Tripping",
        "explanation": "Money leaving and returning to the same source through a complex path of transactions to appear legitimate. Often used to create false documentation or justify the source of funds."
    },
    "TY-009": {
        "name": "Identity Fraud / Synthetic Accounts",
        "explanation": "Account created using false, stolen, or synthetic identity information. These accounts are often used as conduits for fraudulent transactions."
    },
    "TY-010": {
        "name": "High-Value Cash Equivalents",
        "explanation": "Transactions involving high-value items that can be easily converted to cash such as gift cards, precious metals, or cryptocurrency."
    },
    "TY-011": {
        "name": "Layering Activity",
        "explanation": "Complex series of financial transactions designed to distance funds from their criminal source. Multiple transfers between accounts make the audit trail difficult to follow."
    },
    "TY-012": {
        "name": "Account Takeover Fraud",
        "explanation": "Unauthorized access to a legitimate customer's account to conduct fraudulent transactions. Often involves compromised credentials or social engineering."
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# VERDICT EXPLANATIONS
# ═══════════════════════════════════════════════════════════════════════════════

VERDICT_EXPLANATIONS = {
    "ALLOW": {
        "title": "Transaction Approved",
        "description": "The transaction was processed normally. No significant risk indicators were detected by our fraud detection system.",
        "color": "#4caf50"  # Green
    },
    "FLAG": {
        "title": "Flagged for Monitoring",
        "description": "The transaction was allowed but has been flagged for monitoring. Some unusual patterns were detected that warrant observation but do not require immediate action.",
        "color": "#F5A623"  # Gold
    },
    "ALERT": {
        "title": "Alert - Review Required",
        "description": "The transaction triggered multiple risk indicators and requires review by a compliance analyst. The transaction may have been held pending investigation.",
        "color": "#F6AD55"  # Orange
    },
    "BLOCK": {
        "title": "Transaction Blocked",
        "description": "The transaction was blocked due to high risk of fraudulent activity. Multiple severe risk indicators were detected. The customer's account may have been temporarily frozen pending investigation.",
        "color": "#E53E3E"  # Red
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# SCORE EXPLANATIONS
# ═══════════════════════════════════════════════════════════════════════════════

SCORE_EXPLANATIONS = {
    "tma_score": {
        "name": "Transaction Monitoring Score",
        "description": "The initial risk score assigned by the Transaction Monitoring Agent (TMA). This score is based on anomaly detection analysis comparing the transaction against the customer's historical behavior.",
        "range": "0-100 (higher = more risk)"
    },
    "pra_verdict": {
        "name": "Pattern Recognition Verdict",
        "description": "The verdict from the Pattern Recognition Agent (PRA). This agent analyzes behavioral patterns across the customer's transaction history using deep learning models to detect sophisticated fraud patterns.",
        "values": "ALLOW / ESCALATE / BLOCK"
    },
    "pattern_score": {
        "name": "Pattern Match Score",
        "description": "How closely the transaction matches known fraud patterns. Higher scores indicate stronger similarity to previously identified fraudulent behavior.",
        "range": "0-100 (higher = stronger pattern match)"
    },
    "bilstm_score": {
        "name": "Deep Learning Confidence",
        "description": "The confidence score from our BiLSTM (Bidirectional Long Short-Term Memory) deep learning model. This neural network analyzes sequential transaction patterns.",
        "range": "0-100 (higher = more suspicious)"
    },
    "final_raa_score": {
        "name": "Final Risk Assessment Score",
        "description": "The aggregated risk score from the Risk Assessment Agent (RAA). This is the final determination that combines all signals from TMA, PRA, regulatory guidelines, and historical precedents.",
        "range": "0-100 (higher = more risk)"
    },
    "customer_tier": {
        "name": "Customer Risk Tier",
        "description": "The customer's baseline risk classification based on account history, verification level, and transaction patterns.",
        "values": "LOW / STANDARD / MEDIUM / HIGH"
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# AGENT EXPLANATIONS (for Glossary section)
# ═══════════════════════════════════════════════════════════════════════════════

AGENT_EXPLANATIONS = {
    "TMA": {
        "name": "Transaction Monitoring Agent",
        "description": "The first line of defense that analyzes each transaction in real-time. It compares the transaction against the customer's historical behavior to detect anomalies such as unusual amounts, times, or recipients."
    },
    "PRA": {
        "name": "Pattern Recognition Agent",
        "description": "Uses advanced machine learning models to detect complex fraud patterns that may not be visible in individual transactions. It analyzes sequences of transactions to identify sophisticated schemes like structuring or layering."
    },
    "RAA": {
        "name": "Risk Assessment Agent",
        "description": "The final decision-maker that aggregates all signals from TMA, PRA, regulatory guidelines, and historical fraud cases. It determines the overall risk level and recommends the appropriate action (Allow, Flag, Alert, or Block)."
    },
    "ABA": {
        "name": "Action & Blocking Agent",
        "description": "Executes the recommended actions such as blocking transactions, freezing accounts, creating fraud cases, or triggering regulatory filings (STR/CTR)."
    },
    "CLA": {
        "name": "Citation & Legal Archive Agent",
        "description": "Manages regulatory documentation, generates Suspicious Transaction Reports (STR) and Cash Transaction Reports (CTR), and maintains citation libraries for compliance."
    },
}


# ═══════════════════════════════════════════════════════════════════════════════
# HELPER FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

def translate_anomaly_flag(flag_code: str) -> dict:
    """
    Translates a technical anomaly flag code to user-friendly text.

    Args:
        flag_code: The technical flag code (e.g., "VELOCITY_BURST")

    Returns:
        Dict with 'title', 'description', and 'severity', or default if not found.
    """
    return ANOMALY_FLAG_TRANSLATIONS.get(flag_code, {
        "title": flag_code.replace("_", " ").title(),
        "description": f"An anomaly was detected: {flag_code}",
        "severity": "MEDIUM"
    })


def translate_typology(typology_code: str) -> dict:
    """
    Translates a typology code to user-friendly explanation.

    Args:
        typology_code: The typology code (e.g., "TY-001")

    Returns:
        Dict with 'name' and 'explanation', or default if not found.
    """
    return TYPOLOGY_EXPLANATIONS.get(typology_code, {
        "name": f"Unknown Typology ({typology_code})",
        "explanation": "This transaction matches a fraud pattern that requires further investigation."
    })


def get_verdict_info(verdict: str) -> dict:
    """
    Gets the user-friendly explanation for a verdict.

    Args:
        verdict: The verdict code (e.g., "BLOCK")

    Returns:
        Dict with 'title', 'description', and 'color'.
    """
    return VERDICT_EXPLANATIONS.get(verdict.upper(), {
        "title": verdict,
        "description": f"Verdict: {verdict}",
        "color": "#718096"
    })


def get_score_explanation(score_name: str) -> dict:
    """
    Gets the explanation for a score metric.

    Args:
        score_name: The score name (e.g., "tma_score")

    Returns:
        Dict with 'name', 'description', and 'range' or 'values'.
    """
    return SCORE_EXPLANATIONS.get(score_name, {
        "name": score_name.replace("_", " ").title(),
        "description": f"A risk assessment metric: {score_name}",
        "range": "varies"
    })
