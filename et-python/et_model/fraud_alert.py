import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class FraudAlert:
    """
    Represents a single fraud evaluation result produced by the
    Monitoring Agent for one transaction.

    Flows through the pipeline stages:
      DecisionEngine → ResponseExecutor → monitoring_dao.save_fraud_alert()

    All fields map directly to columns in the fraud_alerts table.

    Changes vs original:
      [ADD] low_confidence_fallback — True when RAG confidence < 0.65,
            decision engine used IF-only mode with FLAG floor.
      [ADD] typology_code — best-matching FIU-IND typology from L3 retrieval.
            Carried forward to Phase 2 PRA for pattern continuity.
    """

    # ── Required — set before pipeline runs ───────────────────────────
    transaction_id: str
    customer_id:    str

    # ── Set by ML Layer ────────────────────────────────────────────────
    ml_score:       int = 0

    # ── Set by RAG Layer ───────────────────────────────────────────────
    rag_score:          Optional[int]  = None
    rag_citations:      list           = field(default_factory=list)
    rag_available:      bool           = True

    # ── Set by Decision Engine ─────────────────────────────────────────
    risk_score:             int            = 0
    decision:               str            = 'ALLOW'
    agent_reasoning:        Optional[str]  = None
    anomaly_flags_list:     list           = field(default_factory=list)
    anomaly_features:       dict           = field(default_factory=dict)
    typology_code:          Optional[str]  = None   # [ADD] best L3 match
    low_confidence_fallback: bool          = False  # [ADD] RAG conf < 0.65

    # ── Metadata flags ─────────────────────────────────────────────────
    disagreement:       bool = False
    cold_start_profile: bool = False
    fallback_mode:      bool = False   # True if RAG unavailable entirely

    # ── Set by Response Executor after DB write ────────────────────────
    alert_id:    Optional[int]      = None
    created_at:  Optional[datetime] = None

    # ── Properties ─────────────────────────────────────────────────────

    @property
    def anomaly_flags(self) -> str:
        """JSON string for fraud_alerts.anomaly_flags (JSON column)."""
        return json.dumps(self.anomaly_flags_list)

    @property
    def rag_citations_json(self) -> str:
        """JSON string for fraud_alerts.rag_citations (JSON column)."""
        return json.dumps(self.rag_citations)

    @property
    def fraud_flag(self) -> int:
        """1 if ALERT or BLOCK — written to transactions.fraud_flag."""
        return 1 if self.decision in ('ALERT', 'BLOCK') else 0

    @property
    def agent_status(self) -> str:
        """Written to transactions.agent_status after evaluation."""
        return 'EVALUATED'

    # ── Serialisation ───────────────────────────────────────────────────

    def to_db_dict(self) -> dict:
        """
        Flat dict passed to monitoring_dao.save_fraud_alert().
        Keys match fraud_alerts table column names exactly.
        """
        return {
            'transaction_id':         self.transaction_id,
            'customer_id':            self.customer_id,
            'risk_score':             self.risk_score,
            'ml_score':               self.ml_score,
            'rag_score':              self.rag_score,
            'decision':               self.decision,
            'anomaly_flags':          self.anomaly_flags,
            'feature_snapshot':       json.dumps(self.anomaly_features or {}),  # Always serialize, never NULL
            'rag_citations':          self.rag_citations_json,
            'agent_reasoning':        self.agent_reasoning,
            'disagreement':           int(self.disagreement),
            'rag_available':          int(self.rag_available),
            'cold_start_profile':     int(self.cold_start_profile),
            'fallback_mode':          int(self.fallback_mode),
            'typology_code':          self.typology_code,
            'low_confidence_fallback': int(self.low_confidence_fallback),
        }

    def to_response_dict(self) -> dict:
        """Dict safe for API responses and logs."""
        return {
            'transaction_id':          self.transaction_id,
            'decision':                self.decision,
            'risk_score':              self.risk_score,
            'ml_score':                self.ml_score,
            'rag_score':               self.rag_score,
            'anomaly_flags':           self.anomaly_flags_list,
            'rag_citations':           self.rag_citations,
            'typology_code':           self.typology_code,
            'low_confidence_fallback': self.low_confidence_fallback,
            'fallback_mode':           self.fallback_mode,
            'cold_start':              self.cold_start_profile,
        }

    def __repr__(self) -> str:
        return (
            f"FraudAlert(txn={self.transaction_id}, "
            f"decision={self.decision}, "
            f"risk={self.risk_score}, "
            f"ml={self.ml_score}, "
            f"rag={self.rag_score}, "
            f"conf_fallback={self.low_confidence_fallback})"
        )