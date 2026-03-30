"""
train_bilstm.py  (pra/models)
──────────────────────────────
Offline BiLSTM training script.

Two modes as specified in the PDF:
  --mode=synthetic  Bootstrap training using the 240 L2 seed cases.
                    Expected accuracy: ~68% (adequate for soft escalation).
  --mode=real       Production training on confirmed MySQL sequences.
                    Expected accuracy: ~85-90% (after 90 days live data).

Training schedule:
  Bootstrap:    one-time before Phase 2 launch.
  Early (30-90 days): monthly or at 50 new confirmed cases.
  Production:   monthly + on precision drop >5%.

The trained model is saved as models/bilstm_v1.pt.
Old model coexists as models/bilstm_v{N-1}.pt — zero downtime.

Usage:
  python train_bilstm.py --mode=synthetic
  python train_bilstm.py --mode=real --min-cases=50
"""

from __future__ import annotations

import argparse
import os
import shutil
import json
import numpy as np
import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# ── Import PRA modules ────────────────────────────────────────────────────────
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from et_service.pattern_agent.bilstm_model import FraudBiLSTM
from et_service.pattern_agent.constants    import (
    SEQUENCE_LENGTH,
    FEATURE_DIM,
    BILSTM_MODEL_PATH,
    BOOTSTRAP_SYNTHETIC_CASES,
    RETRAIN_MIN_CASES,
)

MODELS_DIR = os.path.dirname(BILSTM_MODEL_PATH)


# ── Dataset ────────────────────────────────────────────────────────────────────

class SequenceDataset(Dataset):
    """
    Dataset of (30×15) matrices with binary labels (0=normal, 1=fraud).
    """
    def __init__(self, sequences: list[np.ndarray], labels: list[int]):
        assert len(sequences) == len(labels)
        self.X = [torch.tensor(s, dtype=torch.float32) for s in sequences]
        self.y = [torch.tensor([float(l)], dtype=torch.float32) for l in labels]

    def __len__(self):  return len(self.X)
    def __getitem__(self, i): return self.X[i], self.y[i]


# ── Training loop ──────────────────────────────────────────────────────────────

def train(
    sequences:  list[np.ndarray],
    labels:     list[int],
    epochs:     int = 30,
    batch_size: int = 32,
    lr:         float = 1e-3,
) -> FraudBiLSTM:
    device  = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model   = FraudBiLSTM().to(device)
    opt     = torch.optim.Adam(model.parameters(), lr=lr)
    loss_fn = nn.BCELoss()   # score/100 is already in [0,1] via sigmoid

    dataset    = SequenceDataset(sequences, labels)
    dataloader = DataLoader(dataset, batch_size=batch_size, shuffle=True)

    model.train()
    for epoch in range(1, epochs + 1):
        total_loss = 0.0
        for X_batch, y_batch in dataloader:
            X_batch = X_batch.to(device)
            y_batch = y_batch.to(device)
            opt.zero_grad()
            score, _ = model(X_batch)
            loss = loss_fn(score / 100.0, y_batch)
            loss.backward()
            opt.step()
            total_loss += loss.item()

        if epoch % 5 == 0:
            avg_loss = total_loss / len(dataloader)
            print(f"  Epoch {epoch:3d}/{epochs} — loss={avg_loss:.4f}")

    return model


def evaluate(model: FraudBiLSTM, sequences, labels):
    device = next(model.parameters()).device
    model.eval()
    correct = 0
    with torch.no_grad():
        for seq, label in zip(sequences, labels):
            x = torch.tensor(seq, dtype=torch.float32).unsqueeze(0).to(device)
            score, _ = model(x)
            pred = 1 if score.item() >= 50.0 else 0
            if pred == label:
                correct += 1
    acc = correct / len(labels) if labels else 0.0
    print(f"  Accuracy: {acc:.1%} ({correct}/{len(labels)})")
    return acc


# ── Synthetic bootstrap data ───────────────────────────────────────────────────

def load_synthetic_data() -> tuple[list, list]:
    """
    Builds 30-step sequences from the 240 L2 seed cases.
    Last N steps match the typology's signal sequence;
    first (30-N) steps are Gaussian-perturbed normal transactions.
    """
    from et_service.shared_rag.vector_store import _get_collection, COLLECTIONS
    col     = _get_collection(COLLECTIONS['L2'])
    result  = col.get(include=['metadatas'])
    records = result.get('metadatas', [])

    sequences, labels = [], []
    normal_mean = np.array([0.3, 0.1, 0.0, 0.2, 0.1, 0.0, 0.0, 0.1, 0.2,
                             0.0, 0.1, 0.3, 0.0, 0.1, 0.2, 0.15, 0.05], dtype=np.float32)
    normal_std  = np.ones(FEATURE_DIM, dtype=np.float32) * 0.05

    for r in records:
        # Fraud sequence: normal padding + fraud signal at the end
        seq = np.zeros((SEQUENCE_LENGTH, FEATURE_DIM), dtype=np.float32)
        n_fraud_steps = min(r.get('sequence_length', 5), SEQUENCE_LENGTH)
        n_normal_steps = SEQUENCE_LENGTH - n_fraud_steps

        # Normal prefix
        for i in range(n_normal_steps):
            seq[i] = np.clip(np.random.normal(normal_mean, normal_std), 0, 1)

        # Fraud suffix from stored feature vector
        stored_vec = r.get('feature_vector')
        if stored_vec is not None:
            fv = np.array(stored_vec, dtype=np.float32)
            if fv.shape == (FEATURE_DIM,):
                for i in range(n_normal_steps, SEQUENCE_LENGTH):
                    noise = np.random.normal(0, 0.02, FEATURE_DIM).astype(np.float32)
                    seq[i] = np.clip(fv + noise, 0, 1)

        sequences.append(seq)
        labels.append(1)   # all L2 seed cases are fraud

    # Generate an equal number of normal sequences
    for _ in range(len(sequences)):
        seq = np.zeros((SEQUENCE_LENGTH, FEATURE_DIM), dtype=np.float32)
        for i in range(SEQUENCE_LENGTH):
            seq[i] = np.clip(np.random.normal(normal_mean, normal_std), 0, 1)
        sequences.append(seq)
        labels.append(0)

    print(f"  Synthetic dataset: {sum(labels)} fraud + {len(labels)-sum(labels)} normal")
    return sequences, labels


# ── Real data ──────────────────────────────────────────────────────────────────

def load_real_data(min_cases: int = RETRAIN_MIN_CASES) -> tuple[list, list]:
    """Loads confirmed fraud sequences from MySQL."""
    from et_dao.pattern_dao import get_confirmed_fraud_sequences, get_normal_sequences
    fraud_seqs  = get_confirmed_fraud_sequences()
    normal_seqs = get_normal_sequences(n=len(fraud_seqs))

    if len(fraud_seqs) < min_cases:
        raise ValueError(
            f"Only {len(fraud_seqs)} confirmed fraud sequences — "
            f"minimum {min_cases} required for real-data training. "
            "Use --mode=synthetic or wait for more confirmed cases."
        )

    sequences = fraud_seqs + normal_seqs
    labels    = [1] * len(fraud_seqs) + [0] * len(normal_seqs)
    print(f"  Real dataset: {len(fraud_seqs)} fraud + {len(normal_seqs)} normal")
    return sequences, labels


# ── Model save/rotate ──────────────────────────────────────────────────────────

def save_model(model: FraudBiLSTM, path: str):
    """Rotates previous model to bilstm_v{N-1}.pt before saving new one."""
    os.makedirs(MODELS_DIR, exist_ok=True)
    if os.path.exists(path):
        # Find next rotation index
        base = path.replace('.pt', '')
        i = 1
        while os.path.exists(f"{base}_prev{i}.pt"):
            i += 1
        shutil.copy(path, f"{base}_prev{i}.pt")
        print(f"  Previous model backed up to {base}_prev{i}.pt")

    torch.save(model.state_dict(), path)
    print(f"  Model saved to {path}")


# ── CLI entrypoint ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description='Train PRA BiLSTM model')
    parser.add_argument('--mode',      choices=['synthetic', 'real'], required=True)
    parser.add_argument('--epochs',    type=int, default=30)
    parser.add_argument('--batch-size',type=int, default=32)
    parser.add_argument('--min-cases', type=int, default=RETRAIN_MIN_CASES)
    args = parser.parse_args()

    print(f"\n[TrainBiLSTM] Mode: {args.mode}")
    print("─" * 50)

    if args.mode == 'synthetic':
        print("[TrainBiLSTM] Loading synthetic bootstrap data...")
        sequences, labels = load_synthetic_data()
    else:
        print("[TrainBiLSTM] Loading real confirmed sequences from MySQL...")
        sequences, labels = load_real_data(min_cases=args.min_cases)

    # 80/20 train/test split
    n_train = int(len(sequences) * 0.8)
    train_seqs, test_seqs = sequences[:n_train], sequences[n_train:]
    train_lbls, test_lbls = labels[:n_train],    labels[n_train:]

    print(f"\n[TrainBiLSTM] Training on {len(train_seqs)} samples...")
    model = train(train_seqs, train_lbls, epochs=args.epochs, batch_size=args.batch_size)

    print(f"\n[TrainBiLSTM] Evaluating on {len(test_seqs)} samples...")
    acc = evaluate(model, test_seqs, test_lbls)

    save_model(model, BILSTM_MODEL_PATH)
    print(f"\n[TrainBiLSTM] Done. Accuracy={acc:.1%}")


if __name__ == '__main__':
    main()
