"""
bilstm_model.py  (pra)
────────────────────────
Module 2 of the PRA pipeline.

Defines the FraudBiLSTM architecture and provides a cached singleton
loader for inference. Architecture matches the PDF spec exactly:

  Input:  (batch, 30, 15)
  Layer1: BiLSTM(15 → 64×2 = 128)  + dropout(0.3)
  Layer2: BiLSTM(128 → 64×2 = 128)
  last:   h2[:, -1, :]              shape (batch, 128)
  fc1:    Linear(128 → 64)  + ReLU
  fc2:    Linear(64  → 1)   + sigmoid × 100

Returns:
  bilstm_score : float  0-100   (fraud probability × 100)
  hidden_state : Tensor (batch, 128)  — used as RAG L3/L2 query vector

Why BiLSTM over Transformer:
  - Bidirectionality lets a probe (early tx) be reinterpreted when a
    strike follows later — essential for TY-12 and TY-07 patterns.
  - Transformers overfit on small fraud datasets (<500 confirmed cases)
    and exceed the 8ms p99 latency budget.
  - BiLSTM with TorchScript JIT achieves <2ms inference.
"""

from __future__ import annotations

import torch
import torch.nn as nn
import torch.nn.functional as F
import numpy as np

from et_service.pattern_agent.constants import (
    SEQUENCE_LENGTH,
    FEATURE_DIM,
    BILSTM_HIDDEN_SIZE,
    BILSTM_DROPOUT,
    BILSTM_FC1_SIZE,
    BILSTM_MODEL_PATH,
)

# ── Model definition ───────────────────────────────────────────────────────────

class FraudBiLSTM(nn.Module):
    """
    Two-layer bidirectional LSTM fraud pattern classifier.

    Architecture is intentionally simple and matches the PDF spec exactly
    so that the training script (train_bilstm.py) and the inference path
    use identical graph definitions.
    """

    def __init__(self):
        super().__init__()
        # Layer 1: 15 features → 64 per direction → 128 output
        self.bilstm1 = nn.LSTM(
            input_size=FEATURE_DIM,
            hidden_size=BILSTM_HIDDEN_SIZE,
            num_layers=1,
            bidirectional=True,
            batch_first=True,
        )
        # Layer 2: 128 → 64 per direction → 128 output
        self.bilstm2 = nn.LSTM(
            input_size=BILSTM_HIDDEN_SIZE * 2,   # 128 from layer 1
            hidden_size=BILSTM_HIDDEN_SIZE,
            num_layers=1,
            bidirectional=True,
            batch_first=True,
        )
        self.dropout = nn.Dropout(BILSTM_DROPOUT)
        self.fc1     = nn.Linear(BILSTM_HIDDEN_SIZE * 2, BILSTM_FC1_SIZE)
        self.fc2     = nn.Linear(BILSTM_FC1_SIZE, 1)

    def forward(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """
        Parameters:
          x : (batch, SEQUENCE_LENGTH, FEATURE_DIM)

        Returns:
          score       : (batch, 1)  float in [0, 100]
          last_hidden : (batch, 128) — detached; used as RAG query vector
        """
        h1, _  = self.bilstm1(x)            # (batch, 30, 128)
        h1     = self.dropout(h1)
        h2, _  = self.bilstm2(h1)            # (batch, 30, 128)

        last   = h2[:, -1, :]                # last time step: (batch, 128)
        out    = F.relu(self.fc1(last))      # (batch, 64)
        score  = torch.sigmoid(self.fc2(out)) * 100   # (batch, 1)  → [0, 100]

        return score, last.detach()


# ── Singleton model loader ─────────────────────────────────────────────────────

_model: FraudBiLSTM | None = None
_device: torch.device | None = None


def _load_model() -> tuple[FraudBiLSTM, torch.device]:
    """Loads (or returns cached) model. Uses CPU; GPU optional."""
    global _model, _device
    if _model is None:
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        model  = FraudBiLSTM().to(device)
        try:
            state = torch.load(BILSTM_MODEL_PATH, map_location=device)
            model.load_state_dict(state)
            print(f"[BiLSTM] Model loaded from {BILSTM_MODEL_PATH} on {device}")
        except FileNotFoundError:
            print(f"[BiLSTM] WARN — model file not found at {BILSTM_MODEL_PATH}. "
                  "Running with random weights. Run train_bilstm.py --mode=synthetic first.")
        model.eval()
        _model  = model
        _device = device
    return _model, _device


# ── Public inference function ──────────────────────────────────────────────────

def run_inference(matrix: np.ndarray) -> dict:
    """
    Runs a single (30 × 15) matrix through the BiLSTM.

    Parameters:
      matrix — np.ndarray shape (SEQUENCE_LENGTH, FEATURE_DIM), float32

    Returns dict with:
      bilstm_score  : float    0–100
      hidden_state  : np.ndarray shape (128,)  — the last-step hidden vector
                      used as the query for RAG L3 and L2 retrieval
    """
    model, device = _load_model()

    # Add batch dimension → (1, 30, 15)
    tensor = torch.from_numpy(matrix).unsqueeze(0).to(device)

    with torch.no_grad():
        score, hidden = model(tensor)

    bilstm_score = float(score.squeeze().cpu().item())
    hidden_state = hidden.squeeze(0).cpu().numpy()   # shape (128,)

    return {
        'bilstm_score': round(bilstm_score, 2),
        'hidden_state': hidden_state,
    }
