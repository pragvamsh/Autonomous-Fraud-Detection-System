"""
raa_action_package.py
──────────────────────
Dataclass representing the complete RAA action_package output.

This is the contract between RAA and ABA:
  - Every field ABA depends on must be present here.
  - RAA writes this to action_packages; ABA reads it.
"""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RAAActionPackage:
    # ── RAA core output ────────────────────────────────────────────────────────
    final_raa_score: float
    raa_verdict:     str          # ALLOW / SOFT_FLAG / RESTRICT / FREEZE_BLOCK
    action_required: str          # same as raa_verdict — ABA reads this
    customer_tier:   str          # T1 / T2 / T3 / T4
    score_a:         float        # Score_A after RAG multipliers
    score_b:         float        # Score_B (raw transaction danger)

    # ── Provenance from TMA + PRA ─────────────────────────────────────────────
    tma_score:         Optional[int]   = None
    pra_verdict:       Optional[str]   = None
    pattern_score:     Optional[int]   = None
    typology_code:     Optional[str]   = None
    urgency_multiplier: Optional[float] = None
    confidence:        Optional[float] = None

    # ── Regulatory outputs ────────────────────────────────────────────────────
    str_required: bool            = False
    ctr_flag:     bool            = False
    str_draft:    Optional[dict]  = None   # populated when str_required=True

    # ── Evidence pack ─────────────────────────────────────────────────────────
    all_citations:       list = field(default_factory=list)
    investigation_note:  str  = ''

    # ── Routing ──────────────────────────────────────────────────────────────
    customer_id: str = ''
    alert_id:    int = 0
    timestamp:   str = ''

    def to_dict(self) -> dict:
        """Serialises to the JSON payload written to action_packages."""
        return {
            'final_raa_score':    self.final_raa_score,
            'raa_verdict':        self.raa_verdict,
            'action_required':    self.action_required,
            'customer_tier':      self.customer_tier,
            'score_a':            self.score_a,
            'score_b':            self.score_b,
            'tma_score':          self.tma_score,
            'pra_verdict':        self.pra_verdict,
            'pattern_score':      self.pattern_score,
            'typology_code':      self.typology_code,
            'urgency_multiplier': self.urgency_multiplier,
            'confidence':         self.confidence,
            'str_required':       self.str_required,
            'ctr_flag':           self.ctr_flag,
            'str_draft':          self.str_draft,
            'all_citations':      self.all_citations,
            'investigation_note': self.investigation_note,
            'customer_id':        self.customer_id,
            'alert_id':           self.alert_id,
            'timestamp':          self.timestamp,
        }
