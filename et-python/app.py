from flask import Flask
from flask_cors import CORS
import secrets
import os
import shutil
import threading

from db import ensure_tables_exist
from et_api.register_routes import register_bp
from et_api.auth_routes     import auth_bp
from et_api.otp_routes      import otp_bp
from et_api.account_routes  import account_bp
from et_api.payment_routes  import payment_bp
from et_api.pattern_routes  import pattern_bp   # PRA — Pattern Recognition Agent
from et_api.raa_routes      import raa_bp       # RAA — Risk Assessment Agent
from et_api.aba_routes      import aba_bp       # ABA — Alert & Block Agent
from et_api.admin_routes    import admin_bp     # Admin — Dashboard & Authentication
from et_api.cla_routes      import cla_bp       # CLA — Citation & Legal Archive Agent

app = Flask(__name__)

# ── Session configuration ─────────────────────────────────────────────────────
app.config['SECRET_KEY']                = secrets.token_hex(32)
app.config['SESSION_COOKIE_SECURE']     = False   # True in production (HTTPS)
app.config['SESSION_COOKIE_HTTPONLY']   = True
app.config['SESSION_COOKIE_SAMESITE']   = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = 3600 * 8  # 8 hours

CORS(app, resources={
    r"/api/*": {
        "origins":         ["http://localhost:5173", "http://localhost:5174"],
        "methods":         ["GET", "POST", "PUT", "OPTIONS"],
        "allow_headers":   ["Content-Type"],
        "supports_credentials": True,
    }
})

# ── Register blueprints ───────────────────────────────────────────────────────
app.register_blueprint(register_bp)
app.register_blueprint(auth_bp)
app.register_blueprint(otp_bp)
app.register_blueprint(account_bp)
app.register_blueprint(payment_bp, url_prefix='/api')
app.register_blueprint(pattern_bp, url_prefix='/api')
app.register_blueprint(raa_bp,     url_prefix='/api')
app.register_blueprint(aba_bp,     url_prefix='/api')  # ABA — Alert & Block Agent
app.register_blueprint(admin_bp)   # Admin — No prefix, includes /api/admin/* and /goadmin
app.register_blueprint(cla_bp)     # CLA — Includes /api/cla/*

# ── Bootstrap DB schema ───────────────────────────────────────────────────────
ensure_tables_exist()


# ═════════════════════════════════════════════════════════════════════════════
# STARTUP BOOTSTRAP
# All functions below run SYNCHRONOUSLY before the Flask server accepts
# any requests. Order matters:
#   1. BERT model      — needed by TMA RAG and RAA RAG
#   2. ChromaDB KB     — must be populated before TMA/RAA use it
#   3. Isolation Forest — TMA ML layer
#   4. PRA poller      — must be running before TMA fires pattern alerts
#   5. RAA poller      — must be running before PRA marks pra_processed=1
# ═════════════════════════════════════════════════════════════════════════════

# Absolute path to the ChromaDB persistence directory
_BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
_CHROMA_DIR = os.path.join(_BASE_DIR, 'chroma_db')
_MODELS_DIR = os.path.join(_BASE_DIR, 'models')


# ── Step 1: Pre-load BERT model ───────────────────────────────────────────────

def _preload_bert_model():
    """
    Pre-loads SentenceTransformer synchronously so the first transaction
    doesn't incur an 8-second cold-load delay.
    """
    try:
        print("[Startup] Pre-loading SentenceTransformer model (all-MiniLM-L6-v2)...")
        from et_service.monitoring_agent.rag.vector_store import _get_sentence_ef
        model = _get_sentence_ef()
        _ = model("Test transaction Rs 50000")   # warm-up encoding
        print("[OK] SentenceTransformer pre-loaded successfully")
    except Exception as e:
        print(f"[ERROR] FATAL: Could not pre-load BERT model: {e}")
        raise


# ── Step 2: ChromaDB KB — self-healing bootstrap ──────────────────────────────

def _ensure_chromadb_healthy():
    """
    Verifies the ChromaDB client is functional.

    If the client raises a RustBindingsAPI error (version mismatch between
    the installed chromadb package and the persisted chroma_db folder),
    the corrupted folder is deleted and recreated so ingest can rebuild it.

    Returns True if the client is healthy, False if it had to be rebuilt.
    """
    try:
        from et_service.monitoring_agent.rag.vector_store import collection_count, COLLECTIONS
        # Try a benign count — this will throw if the client is broken
        collection_count(COLLECTIONS['L1'])
        return True
    except Exception as e:
        err = str(e)
        # RustBindingsAPI error = chromadb version mismatch
        # Path-as-error = corrupted persist directory
        if ('RustBindingsAPI' in err or 'bindings' in err.lower()
                or _CHROMA_DIR in err or 'tenant' in err.lower()):
            print(f"[Startup] [WARN]  ChromaDB client error detected: {err[:120]}")
            print(f"[Startup] Rebuilding ChromaDB from scratch at: {_CHROMA_DIR}")
            try:
                if os.path.exists(_CHROMA_DIR):
                    shutil.rmtree(_CHROMA_DIR)
                    print(f"[Startup] Deleted corrupted chroma_db folder.")
                os.makedirs(_CHROMA_DIR, exist_ok=True)
                print(f"[Startup] Created fresh chroma_db folder.")
                return False   # signal: all collections need re-ingest
            except Exception as rebuild_err:
                print(f"[Startup] [ERROR] Could not rebuild chroma_db folder: {rebuild_err}")
                raise
        else:
            # Unknown error — surface it
            print(f"[Startup] [ERROR] Unexpected ChromaDB error: {e}")
            raise


def _ensure_kb_populated():
    """
    Checks each ChromaDB collection and re-ingests if empty.

    Called every startup — ingest functions are idempotent (they upsert,
    so running them on a populated collection is a safe no-op).

    Collections checked:
      L1 — regulatory rules   (ingest_regulatory.py)
      L2 — fraud cases        (ingest_cases.py)
      L3 — typology patterns  (ingest_patterns.py)
    """
    try:
        from et_service.monitoring_agent.rag.vector_store import collection_count, COLLECTIONS
    except Exception as e:
        print(f"[Startup] [ERROR] Cannot import vector_store: {e}")
        return

    # ── L1 Regulatory ────────────────────────────────────────────────────────
    try:
        l1_count = collection_count(COLLECTIONS['L1'])
        if l1_count == 0:
            print("[Startup] [WARN]  L1_regulatory is empty — running ingest_regulatory...")
            try:
                from et_service.monitoring_agent.rag.kb_ingest.ingest_regulatory import ingest
                ingest()
                new_count = collection_count(COLLECTIONS['L1'])
                print(f"[Startup] [OK] L1_regulatory populated ({new_count} documents).")
            except Exception as e:
                print(f"[Startup] [ERROR] L1 ingest failed: {e}")
                import traceback; traceback.print_exc()
        else:
            print(f"[Startup] [OK] L1_regulatory — {l1_count} documents (OK).")
    except Exception as e:
        print(f"[Startup] [ERROR] L1 count check failed: {e}")

    # ── L2 Fraud Cases ────────────────────────────────────────────────────────
    try:
        l2_count = collection_count(COLLECTIONS['L2'])
        if l2_count == 0:
            print("[Startup] [WARN]  L2_fraud_cases is empty — running ingest_cases...")
            try:
                from et_service.monitoring_agent.rag.kb_ingest.ingest_cases import ingest
                ingest()
                new_count = collection_count(COLLECTIONS['L2'])
                print(f"[Startup] [OK] L2_fraud_cases populated ({new_count} documents).")
            except Exception as e:
                print(f"[Startup] [ERROR] L2 ingest failed: {e}")
                import traceback; traceback.print_exc()
        else:
            print(f"[Startup] [OK] L2_fraud_cases — {l2_count} documents (OK).")
    except Exception as e:
        print(f"[Startup] [ERROR] L2 count check failed: {e}")

    # ── L3 Typologies ─────────────────────────────────────────────────────────
    try:
        l3_count = collection_count(COLLECTIONS['L3'])
        if l3_count == 0:
            print("[Startup] [WARN]  L3_typologies is empty — running ingest_patterns...")
            try:
                from et_service.monitoring_agent.rag.kb_ingest.ingest_patterns import ingest
                ingest()
                new_count = collection_count(COLLECTIONS['L3'])
                print(f"[Startup] [OK] L3_typologies populated ({new_count} documents).")
            except Exception as e:
                print(f"[Startup] [ERROR] L3 ingest failed: {e}")
                import traceback; traceback.print_exc()
        else:
            print(f"[Startup] [OK] L3_typologies — {l3_count} documents (OK).")
    except Exception as e:
        print(f"[Startup] [ERROR] L3 count check failed: {e}")


def _bootstrap_kb():
    """
    Full ChromaDB bootstrap sequence:
      1. Health-check the client — rebuild folder if corrupted
      2. Populate any empty collections
    """
    print("[Startup] Checking ChromaDB knowledge base...")
    client_healthy = _ensure_chromadb_healthy()
    if not client_healthy:
        print("[Startup] ChromaDB was rebuilt — all collections will be re-ingested.")
    _ensure_kb_populated()


# ── Step 3: Isolation Forest ──────────────────────────────────────────────────

def _ensure_model_trained():
    """
    Trains the Isolation Forest if the .pkl file is missing.
    Skips silently if the file already exists — training only happens once
    (or when you manually delete the file to force retraining).
    """
    model_path = os.path.join(_MODELS_DIR, 'isolation_forest.pkl')
    if os.path.exists(model_path):
        print(f"[Startup] [OK] Isolation Forest model found (OK).")
        return
    print("[Startup] [WARN]  Isolation Forest model missing — training now...")
    try:
        from et_service.monitoring_agent.training.train_model import train_and_save
        train_and_save()
        print("[Startup] [OK] Isolation Forest trained and saved.")
    except Exception as e:
        print(f"[Startup] [ERROR] Isolation Forest training failed: {e}")
        print("[Startup]    TMA will use rule-based fallback until training succeeds.")
        import traceback; traceback.print_exc()


def _warn_bilstm():
    """
    Warns if the BiLSTM model file is missing.
    Cannot auto-train BiLSTM at startup (needs sequence data).
    Prints the exact command to run.
    """
    bilstm_path = os.path.join(_MODELS_DIR, 'bilstm_v1.pt')
    if os.path.exists(bilstm_path):
        print(f"[Startup] [OK] BiLSTM model found (OK).")
    else:
        print(f"[Startup] [WARN]  BiLSTM model missing.")
        print(f"[Startup]    PRA will use random weights until you run:")
        print(f"[Startup]    python models/train_bilstm.py --mode=synthetic")


# ── Step 4 + 5 + 6 + 7: PRA, RAA, ABA, and CLA pollers ───────────────────────

def _bootstrap_pra():
    """Starts the PRA background polling thread."""
    try:
        from et_service.pattern_agent.pra_agent import start_pra_poller
        start_pra_poller()
        print("[OK] PRA poller started — background polling active (500ms interval).")
    except Exception as e:
        print(f"[ERROR] FATAL: PRA bootstrap failed: {e}")
        import traceback; traceback.print_exc()
        raise


def _bootstrap_raa():
    """Starts the RAA background polling thread."""
    try:
        from et_service.raa.raa_agent import RAAAgent
        agent = RAAAgent.create()
        print("[OK] RAAAgent started — background poller active (500ms interval).")
        name = agent._poller_thread.name if hasattr(agent, '_poller_thread') else 'N/A'
        print(f"   Poller thread: {name}")
    except Exception as e:
        print(f"[ERROR] FATAL: RAA bootstrap failed: {e}")
        import traceback; traceback.print_exc()
        raise


def _bootstrap_aba():
    """Starts the ABA background polling thread."""
    try:
        from et_service.aba.aba_agent import ABAAgent
        agent = ABAAgent.create()
        print("[OK] ABAAgent started — background poller active (500ms interval).")
        name = agent._poller_thread.name if hasattr(agent, '_poller_thread') else 'N/A'
        print(f"   Poller thread: {name}")
    except Exception as e:
        print(f"[ERROR] FATAL: ABA bootstrap failed: {e}")
        import traceback; traceback.print_exc()
        raise


def _bootstrap_cla():
    """Starts the CLA background polling thread."""
    try:
        from et_service.cla import start_cla_agent
        agent = start_cla_agent()
        print("[OK] CLAgent started — background poller active (500ms interval).")
    except Exception as e:
        print(f"[ERROR] FATAL: CLA bootstrap failed: {e}")
        import traceback; traceback.print_exc()
        raise


# ── Run all bootstrap steps synchronously ────────────────────────────────────

print("\n" + "=" * 70)
print("JATAYU SYSTEM STARTUP — Initializing ML models, KB, and agents")
print("=" * 70)

_preload_bert_model()   # Step 1 — BERT (needed by RAG layers)
_bootstrap_kb()         # Step 2 — ChromaDB health check + ingest if empty
_ensure_model_trained() # Step 3 — Isolation Forest
_warn_bilstm()          # Step 3b — BiLSTM warning if missing
_bootstrap_pra()        # Step 4 — PRA poller
_bootstrap_raa()        # Step 5 — RAA poller
_bootstrap_aba()        # Step 6 — ABA poller
_bootstrap_cla()        # Step 7 — CLA poller

print("=" * 70 + "\n")


if __name__ == '__main__':
    app.run(debug=True, port=5000)