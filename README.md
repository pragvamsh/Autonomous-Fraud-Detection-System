# 🦅 EagleTrust Bank — Autonomous Fraud Detection System & Response Network

> An enterprise-grade, multi-agent AI fraud detection system for Indian banking — detecting suspicious transactions in real-time, assessing risk using ML and RAG, and executing automated responses without human intervention.

---

## 📋 Project Overview

**EagleTrust Bank** is a **multi-agent AI pipeline** built for autonomous fraud detection in Indian banking environments. It monitors transactions continuously, detects suspicious patterns, assesses regulatory risk, and executes responses — all without manual intervention.

The system is powered by a **pipeline of 5 specialized AI agents**, each handling a distinct phase of detection and response:

| Agent | Name | Role |
|-------|------|------|
| **TMA** | Transaction Monitoring Agent | Real-time behavioral analysis |
| **PRA** | Pattern Recognition Agent | Cross-customer trend detection |
| **RAA** | Risk Assessment Agent | Regulatory scoring & fusion |
| **ABA** | Alert & Block Agent | Verdict execution & notifications |
| **CLA** | Compliance Logging Agent | Case archival & knowledge feedback |

---

## 🚀 Key Features

- ⚡ **Real-time detection** — Full pipeline completes in ~4–6 seconds
- 🧠 **RAG-powered knowledge** — ChromaDB with 4-layer retrieval (fraud cases, regulations, typologies, dynamic weights)
- 🤖 **5 autonomous agents** — Each agent runs independently and asynchronously
- 📋 **RBI/PMLA compliance** — Automatic CTR/STR report generation
- 🔄 **Self-learning** — System improves with every confirmed fraud case
- 🔐 **Zero cold-start** — Behavior profiles built over 90-day rolling window

---

## 🏗️ Architecture Overview

```
POST /api/payment/initiate  →  Returns immediately (async pipeline starts)
                                          │
                    ┌─────────────────────▼─────────────────────┐
                    │   STAGE 1: TMA — Transaction Monitoring   │
                    │   Behavior Profile → Anomaly Features →   │
                    │   Isolation Forest ML → ChromaDB RAG →    │
                    │   Decision Engine → fraud_alert row       │
                    └─────────────────────┬─────────────────────┘
                                          │
                    ┌─────────────────────▼─────────────────────┐
                    │   STAGE 2: PRA — Pattern Recognition      │
                    │   Temporal Analyzer (EWM) → Network       │
                    │   Fan-Out → Typology Matching → Score     │
                    └─────────────────────┬─────────────────────┘
                                          │
                    ┌─────────────────────▼─────────────────────┐
                    │   STAGE 3: RAA — Risk Assessment          │
                    │   Intelligence Aggregation → Customer Tier│
                    │   5-Dim Scoring → RAG Fusion → STR/CTR    │
                    │   Action Package → ABA dispatch           │
                    └─────────────────────┬─────────────────────┘
                                          │
                    ┌─────────────────────▼─────────────────────┐
                    │   STAGE 4: ABA — Alert & Block            │
                    │   Gateway Control → Execute Verdict →     │
                    │   Notify Customer → Freeze Account →      │
                    │   File Regulatory Reports → Create Case   │
                    └─────────────────────┬─────────────────────┘
                                          │
                    ┌─────────────────────▼─────────────────────┐
                    │   STAGE 5: CLA — Compliance Logging       │
                    │   Evidence Archive → STR/CTR Docs →       │
                    │   RAG Feedback Loop (knowledge update)    │
                    └───────────────────────────────────────────┘
```

---

## 🤖 The 5 Agents — Deep Dive

### Agent 1 — TMA (Transaction Monitoring Agent)

Triggered immediately after a payment is committed. Runs a 7-stage pipeline:

1. **Build Profile** — Fetch 90-day transaction history, compute mean/std/max
2. **Extract Anomaly Features** — 15 signals including Z-score, velocity, recipient newness, time-of-day, day-of-week
3. **ML Scoring** — Isolation Forest model outputs a score in the range 0–100
4. **RAG Retrieval** — Queries ChromaDB across 4 collections (fraud cases, regulatory rules, typologies, dynamic weights)
5. **Score Fusion** — Combines ML and RAG scores with adaptive weights
6. **Decision Engine** — Outputs ALLOW / FLAG / ALERT / BLOCK
7. **Response Executor** — Writes a `fraud_alert` row if score ≥ 40

**Output example:**
```
decision     : FLAG
tma_score    : 56
anomaly_flags: High Z-score, Unusual recipient
confidence   : 0.87
```

---

### Agent 2 — PRA (Pattern Recognition Agent)

Triggered after TMA, only when TMA decision is not ALLOW. Detects cross-customer trends:

1. **Temporal Analyzer** — Exponential Weighted Moving Average (EWM) risk trends over the past 7 days
2. **Network Analyzer** — Checks fan-out: how many distinct customers are sending to the same recipient
3. **Typology Retrieval** — Queries ChromaDB `L3_typologies` collection to identify fraud patterns (e.g., Money Mule, SIM Swap, Account Takeover)
4. **Score Aggregation** — Combines temporal + network + typology signals

> **Fast-escalation rule:** If `pra_score ≥ 75`, PRA triggers ABA immediately — bypassing RAA to stop the transaction faster.

**Output example:**
```
pra_decision   : ALERT
pra_score      : 62
typology       : Money Mule Network
network_risk   : HIGH
pattern_matches: 3
```

---

### Agent 3 — RAA (Risk Assessment Agent)

Background poller (every 500ms) that picks up alerts with `pra_processed=1` and runs an 8-stage regulatory scoring pipeline:

1. **Intelligence Aggregator** — Merge TMA + PRA results
2. **Customer Tier Classifier** — Assigns T1 (Low) → T4 (Critical) based on history, volume, and alerts
3. **5-Dimension Scorer** — Scores across 5 regulatory dimensions, each 0–20 points:
   - D1: Transaction Velocity
   - D2: Typology Match
   - D3: Customer Risk Tier
   - D4: Regulatory Flags (RBI/PMLA triggers)
   - D5: Anomaly Signal Strength
   - `Score_A = D1 + D2 + D3 + D4 + D5` (0–100)
4. **RAG Retrieval** — Queries L2 (k=15), L1 (k=3), L3 collections; weighted at 50/20/30 respectively
5. **Score Fusion** — `final_score = (Score_A × 0.60) + (Score_B × 0.40)` with floor adjustments
6. **Regulatory Engine** — Checks CTR threshold (> ₹10 lakh) and STR threshold (score ≥ 70 + amount > ₹50k)
7. **Action Package Builder** — Constructs a structured action package for ABA
8. **DB Write-back** — Updates `fraud_alerts` row with `raa_verdict` and `raa_score`

**Output example:**
```
raa_verdict  : BLOCK
raa_score    : 78
customer_tier: T3
d1-d5 scores : [18, 16, 14, 15, 15]
file_str     : true
gateway_action: STOPPED
```

---

### Agent 4 — ABA (Alert & Block Agent)

Executes the verdict received from RAA (or PRA fast-escalation). Runs 7 execution stages:

1. **Package Loader** — Reads the action package
2. **Gateway Controller** — Routes to payment gateway: APPROVE / APPROVE_AFTER_CONFIRM / HELD / STOPPED
3. **Action Executor** — Reverses transactions if verdict is BLOCK
4. **Notification Engine** — Queues SMS and email alerts to customer and bank
5. **Account Controller** — Freezes account if decision is BLOCK (`account_frozen = 1`)
6. **Regulatory Router** — Files STR/CTR reports to FIU-IND portal
7. **Case Manager** — Creates a fraud case entry for CLA with `PENDING_REVIEW` status

---

### Agent 5 — CLA (Compliance Logging Agent)

Background processor that archives evidence and improves system knowledge:

1. **Case Processor** — Fetches and contextualizes the fraud case
2. **Citation Archiver** — Stores evidence PDFs (payment detail, customer profile, transaction timeline, RAG reasoning)
3. **STR/CTR Generator** — Generates Indian FIU-IND format compliance documents
4. **Feedback Handler** — When a case is marked `CONFIRMED_FRAUD`:
   - Adds to `L2_fraud_cases` collection
   - Updates `L4_dynamic_weights` to improve future fusion accuracy
   - Logs to `L5_feedback_log`

> This closes the learning loop — every confirmed case makes the system smarter.

---

## 🧠 RAG Layer — ChromaDB 4-Layer Knowledge Base

Jatayu uses **Retrieval-Augmented Generation (RAG)** to combine ML predictions with a structured knowledge base stored in **ChromaDB** (open-source vector database).

### The 4 Collections

| Collection | Type | Purpose | Updated By |
|------------|------|---------|-----------|
| `L1_regulatory` | Text-based | RBI/PMLA/FIU-IND compliance rules | KB ingest scripts |
| `L2_fraud_cases` | Vector (384-dim) | Historical confirmed fraud cases | CLA (on CONFIRMED_FRAUD) |
| `L3_typologies` | Vector | FIU-IND fraud typology patterns | KB ingest scripts |
| `L4_dynamic_weights` | Meta | ML vs RAG accuracy calibration | Monthly adaptive update |

### How RAG Scoring Works

Each transaction's 15 anomaly features are encoded into a vector using **Sentence Transformers**. This vector is used to query all 4 collections simultaneously:

- **L2** contributes 50% of the RAG score (historical case similarity)
- **L1** contributes 20% (regulatory rule alignment)
- **L3** contributes 30% (typology pattern match)

The result (`Score_B`) is fused with the ML score (`Score_A`) using weights from `L4_dynamic_weights`, defaulting to 60% ML / 40% RAG.

---

## 🗄️ Database Schema (MySQL)

The system uses 7 core tables:

| Table | Purpose |
|-------|---------|
| `customers` | Customer identity and KYC status |
| `customer_accounts` | Account balances and freeze status |
| `transactions` | All debit/credit transactions |
| `fraud_alerts` | Central alert record across all 3 agents |
| `action_packages` | Verdict and execution instructions for ABA |
| `fraud_cases` | Case records for investigation and archival |
| `cla_archive` | PDF evidence paths and document types |

The `fraud_alerts` table acts as the **backbone** of the pipeline — each agent reads and writes to it, advancing the row through its lifecycle.

---

## 🔧 Technology Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | React + Vite | Customer dashboard and pipeline visualization |
| **Backend** | Flask 3.0 | REST API and agent orchestration |
| **ML Model** | scikit-learn | Isolation Forest anomaly detection |
| **Embeddings** | Sentence Transformers | Feature vectorization for ChromaDB |
| **Vector DB** | ChromaDB 0.4+ | 4-layer RAG knowledge retrieval |
| **SQL DB** | MySQL | Transaction and alert persistence |
| **Auth** | JWT + bcrypt | Stateless authentication |
| **Async** | Python Threading | Background agent polling |
| **Utils** | NumPy, Joblib | Numerical computation and model I/O |

---

## 📁 Project Structure

```
Jatayu/
├── et-python/                        # Backend
│   ├── app.py                        # Flask entry point + agent daemon startup
│   ├── db.py                         # MySQL connection pool
│   ├── requirements.txt
│   ├── et_api/
│   │   ├── payment_routes.py         # POST /api/payment/initiate
│   │   ├── otp_routes.py             # OTP send and verify
│   │   └── ...
│   ├── et_service/
│   │   ├── payment_service.py        # Payment transaction processor
│   │   ├── monitoring_agent/         # TMA — Transaction Monitoring Agent
│   │   ├── pattern_agent/            # PRA — Pattern Recognition Agent
│   │   ├── raa/                      # RAA — Risk Assessment Agent
│   │   ├── aba/                      # ABA — Alert & Block Agent
│   │   ├── cla/                      # CLA — Case & Legal Agent
│   │   └── shared_rag/               # ChromaDB RAG layer (shared across agents)
│   │       ├── rag_layer.py          # Core retrieval logic
│   │       └── kb_ingest/            # Scripts to seed knowledge base
│   ├── et_dao/                       # Database query layer
│   ├── et_model/                     # Shared data models
│   ├── chroma_db/                    # ChromaDB persistent storage
│   ├── cla_archive/                  # Case evidence PDFs
│   └── models/
│       └── isolation_forest_v1.pkl   # Trained anomaly detection model
├── et-web/                           # Frontend
│   ├── src/
│   │   ├── pages/
│   │   │   └── PaymentPage.jsx       # Payment UI + live pipeline visualization
│   │   ├── components/               # Reusable UI components
│   │   └── api.js                    # Axios API client
│   └── package.json
└── README.md
```

---

## 🚀 Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- MySQL 8.0+

### 1. Clone the Repository

```bash
git clone https://github.com/pragvamsh/Autonomous-Fraud-Detection-System.git
cd Autonomous-Fraud-Detection-System
```

### 2. Backend Setup

```bash
cd et-python
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
```

### 3. Configure Environment

Create a `.env` file in `et-python/`:

```
DB_HOST=localhost
DB_PORT=3306
DB_NAME=jatayu_db
DB_USER=root
DB_PASSWORD=your_password
JWT_SECRET=your_jwt_secret
```

### 4. Initialize the Database

```bash
mysql -u root -p < et-python/db_schema.sql
```

### 5. Seed the ChromaDB Knowledge Base

```bash
cd et-python
python -m et_service.shared_rag.kb_ingest.ingest_regulatory
python -m et_service.shared_rag.kb_ingest.ingest_cases
python -m et_service.shared_rag.kb_ingest.ingest_patterns
```

This seeds the 3 active collections with:
- Indian RBI/PMLA/FIU-IND compliance rules
- Historical fraud case feature vectors
- FIU-IND fraud typology definitions

### 6. Start the Backend

```bash
python app.py
```

This starts:
- Flask REST API on `http://localhost:5000`
- TMA daemon (monitors new transactions)
- PRA background poller
- RAA background poller (500ms interval)
- CLA background processor

### 7. Start the Frontend

```bash
cd ../et-web
npm install
npm run dev
```

Open `http://localhost:5173` in your browser.

---

## 🔌 API Reference

### Initiate Payment

```
POST /api/payment/initiate
Authorization: Bearer <JWT_TOKEN>

Body:
{
  "recipient_account": "ACC_001",
  "amount": 250000,
  "description": "Fund transfer"
}

Response (immediate):
{
  "payment_id": "PAY_20240330_001",
  "status": "PROCESSING",
  "message": "Payment submitted. Fraud analysis running..."
}
```

### Poll Payment Status

```
GET /api/payment/status/{payment_id}

Response:
{
  "payment_id": "PAY_20240330_001",
  "decision": "ALERT",
  "tma_decision": "FLAG",
  "pra_decision": "ALERT",
  "raa_verdict": "ALERT",
  "raa_score": 68,
  "typology": "Money Mule Network",
  "requires_mfa": true
}
```

### OTP Verification (for ALERT verdicts)

```
POST /api/otp/send      → { "payment_id": "..." }
POST /api/otp/verify    → { "payment_id": "...", "otp": "123456" }
```

---

## 🎯 Example: Money Mule Detection Walkthrough

**Scenario:** Customer initiates ₹1,50,000 transfer to a new recipient at 9 PM.

**TMA Analysis:**
- Z-score: 4.5 (large amount deviation from customer history)
- Velocity: 12 transactions/hour (unusual burst)
- Recipient: NEW account with 15+ incoming transactions from other customers
- Time: Night (atypical for this customer's profile)
- → **TMA Score: 68 | Decision: FLAG**

**PRA Analysis:**
- 5 other customers sent to the same recipient in the past week (fan-out detected)
- Recipient is a HUB node (20+ customers connected)
- Typology match: **Money Mule Network** (0.89 cosine similarity)
- → **PRA Score: 75 | Decision: ALERT** → ABA triggered immediately

**ABA Execution (fast path):**
- Gateway action: APPROVE_AFTER_CONFIRM
- Customer notified: "Unusual activity detected — OTP required"
- Account not frozen (ALERT, not BLOCK)

**RAA Analysis (background):**
- D1 (Velocity): 18/20 | D2 (Typology): 16/20 | D3 (Tier T2): 14/20
- D4 (RBI flag): 15/20 | D5 (Anomaly): 15/20 → Score_A = 78
- RAG retrieval: 5 historical matches, avg similarity 0.81 → Score_B = 75
- Final: 0.6×78 + 0.4×75 = **76.8 → ALERT confirmed**

**CLA:**
- Case created: `FRAUD_2024_001234` (PENDING_REVIEW)
- Evidence archived, STR draft generated
- Awaiting analyst review

**Customer experience:** Receives OTP prompt. Can complete transaction after successful 2FA verification.

---

## 📊 Performance Metrics

| Metric | Value |
|--------|-------|
| End-to-end detection latency | ~4–6 seconds |
| False positive rate | < 8% |
| Knowledge base size | 1,000+ fraud cases, 50+ typologies |
| Regulatory rule coverage | 100% RBI/PMLA |
| Behavior profile window | 90 days rolling |

---

## 🔐 Security & Compliance

**Regulatory Coverage:**
- RBI Payment Systems Regulations
- PMLA (Prevention of Money Laundering Act 2002)
- FIU-IND reporting format (CTR/STR)

**Security Measures:**
- Bcrypt password hashing
- JWT stateless authentication
- Audit logging of all agent decisions
- Anonymous feature engineering (no raw account numbers in embeddings)
- 18-month data retention policy with deletion support

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to discuss what you'd like to change.

---

## 📄 License

This project is licensed under the MIT License.

---

<div align="center">
  <b>Built for Indian Banking · Powered by Multi-Agent AI · Compliant with RBI/PMLA</b>
</div>
