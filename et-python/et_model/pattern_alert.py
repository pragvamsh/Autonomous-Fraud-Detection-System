"""
pattern_alert.py
────────────────
Model class for a single Pattern Recognition Agent (PRA) evaluation result.

Flows through:
  PRA Decision Engine → PRA Response Executor → pattern_dao.save_pattern_alert()

All fields map directly to pattern_alerts table columns.
"""

import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class PatternAlert:
    """
    Represents a single pattern-level fraud evaluation produced by the
    Pattern Recognition Agent for one payment.
    """

    # ── Required — set before PRA runs ────────────────────────────────────────
    payment_id:  str
    customer_id: str

    # ── TMA context ────────────────────────────────────────────────────────────
    tma_risk_score:  Optional[int] = None
    tma_decision:    Optional[str] = None

    # ── Set by Temporal Analyser ───────────────────────────────────────────────
    temporal_score: int = 0

    # ── Set by Network Analyser ────────────────────────────────────────────────
    network_score: int = 0

    # ── Set by RAG Scorer ──────────────────────────────────────────────────────
    rag_adjustment: int = 0

    # ── Set by Decision Engine ─────────────────────────────────────────────────
    pattern_score:   int  = 0
    decision:        str  = 'ALLOW'
    pattern_types:   list = field(default_factory=list)
    network_flags:   list = field(default_factory=list)
    agent_reasoning: Optional[str] = None
    typology_code:   Optional[str] = None

    # ── Set by Response Executor after DB write ────────────────────────────────
    alert_id:   Optional[int]      = None
    created_at: Optional[datetime] = None

    # ── Properties ─────────────────────────────────────────────────────────────

    @property
    def pattern_types_json(self) -> str:
        return json.dumps(self.pattern_types)

    @property
    def network_flags_json(self) -> str:
        return json.dumps(self.network_flags)

    @property
    def fraud_flag(self) -> int:
        """1 if ALERT or BLOCK."""
        return 1 if self.decision in ('ALERT', 'BLOCK') else 0

    @property
    def agent_status(self) -> str:
        return 'PRA_EVALUATED'

    # ── Serialisation ──────────────────────────────────────────────────────────

    def to_db_dict(self) -> dict:
        """Flat dict passed to pattern_dao.save_pattern_alert()."""
        return {
            'payment_id':      self.payment_id,
            'customer_id':     self.customer_id,
            'pattern_score':   self.pattern_score,
            'temporal_score':  self.temporal_score,
            'network_score':   self.network_score,
            'rag_adjustment':  self.rag_adjustment,
            'decision':        self.decision,
            'pattern_types':   self.pattern_types_json,
            'network_flags':   self.network_flags_json,
            'agent_reasoning': self.agent_reasoning,
            'typology_code':   self.typology_code,
            'tma_risk_score':  self.tma_risk_score,
            'tma_decision':    self.tma_decision,
        }

    def to_response_dict(self) -> dict:
        """Dict safe for API responses."""
        return {
            'payment_id':      self.payment_id,
            'decision':        self.decision,
            'pattern_score':   self.pattern_score,
            'temporal_score':  self.temporal_score,
            'network_score':   self.network_score,
            'rag_adjustment':  self.rag_adjustment,
            'pattern_types':   self.pattern_types,
            'network_flags':   self.network_flags,
            'typology_code':   self.typology_code,
            'tma_risk_score':  self.tma_risk_score,
            'tma_decision':    self.tma_decision,
        }

    def __repr__(self) -> str:
        return (
            f"PatternAlert(payment={self.payment_id}, "
            f"decision={self.decision}, "
            f"score={self.pattern_score}, "
            f"temporal={self.temporal_score}, "
            f"network={self.network_score})"
        )
