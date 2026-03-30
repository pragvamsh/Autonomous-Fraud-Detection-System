"""
shared_rag
──────────
Shared RAG (Retrieval-Augmented Generation) layer for all Jatayu agents.

Provides ChromaDB-backed 4-layer knowledge retrieval used by:
  - TMA (Transaction Monitoring Agent)
  - PRA (Pattern Recognition Agent)
  - RAA, ABA, CLA (future agents)

Collections:
  L1_regulatory      : RBI / PMLA compliance rules (text)
  L2_fraud_cases     : Confirmed historical fraud cases (feature vectors)
  L3_typologies      : FIU-IND fraud typology patterns (signal vectors)
  L4_dynamic_weights : Agent accuracy history for weight calibration (feature vectors)
  L5_feedback_log    : Audit log of investigation outcomes (key-value)
"""
