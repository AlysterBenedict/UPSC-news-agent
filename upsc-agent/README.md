# UPSC Daily Newspaper Digest — Multi-Agent AI System

A **production-grade, multi-agent pipeline** that generates a 30–50+ page UPSC-focused PDF digest daily from scraped news articles and delivers it by email at 8 AM IST.

## Architecture

```
Scraper Output (435 articles/day)
        │
        ▼
┌─────────────────────────────────────────────────────┐
│                 LangGraph Pipeline                  │
│                                                     │
│  Ingest → Normalize → Dedup/Cluster → Analyze(LLM) │
│  → Verify(LLM) → Map UPSC → Write Sections(LLM)   │
│  → Assemble HTML → Render PDF → Email → Audit      │
│                                                     │
│  ✓ SQLite checkpointing                             │
│  ✓ Incremental processing (1 cluster at a time)     │
│  ✓ Anti-hallucination verification                  │
│  ✓ Source traceability                              │
└─────────────────────────────────────────────────────┘
        │
        ▼
   A4 PDF (30-50+ pages)
   → Email to sharonrishithas@gmail.com
```

## Tech Stack

| Component        | Technology                                      |
|------------------|-------------------------------------------------|
| Orchestration    | LangGraph (stateful graph with checkpointing)   |
| LLM              | NVIDIA NIM Nemotron via OpenAI-compatible API    |
| Embeddings       | sentence-transformers (all-MiniLM-L6-v2, local)  |
| Clustering       | scikit-learn AgglomerativeClustering              |
| Schemas          | Pydantic v2                                       |
| HTML Templates   | Jinja2                                            |
| PDF Rendering    | WeasyPrint                                        |
| Scheduling       | APScheduler (8 AM IST daily)                      |
| Email            | Gmail SMTP                                        |
| Logging          | structlog (JSON structured)                       |

## Setup

### 1. Prerequisites
```bash
# Ensure conda env exists
conda activate upsc-digest
```

### 2. Install Dependencies
```bash
cd upsc-agent
pip install -r requirements.txt
```

### 3. Configure Environment
```bash
# Copy and edit .env
cp .env.example .env
# Edit .env with your credentials:
# - NIM_API_KEY (your NVIDIA NIM key)
# - SMTP_PASS (Gmail App Password — generate at https://myaccount.google.com/apppasswords)
```

### 4. Gmail App Password
To send emails via Gmail, you need an **App Password**:
1. Go to https://myaccount.google.com/apppasswords
2. Generate a new app password for "Mail"
3. Put that 16-character password in `.env` as `SMTP_PASS`

## Usage

### Run Full Pipeline (Today)
```bash
conda create --name upsc-digest python=3.11
conda activate upsc-digest
cd upsc-agent
python main.py run
```

### Run for Specific Date
```bash
python main.py run --date 2026-06-09
```

### Start Daily Scheduler (8 AM IST)
```bash
python main.py schedule
```

### Render PDF Only (from existing run)
```bash
python main.py render-only --run-id digest_2026-06-09_abc12345
```

### Send Existing PDF
```bash
python main.py deliver-only --pdf output/UPSC_Digest_2026-06-09.pdf --date 2026-06-09
```

## Project Structure

```
upsc-agent/
├── main.py                          # CLI entry point
├── requirements.txt                 # Python dependencies
├── .env                             # Environment config (git-ignored)
├── .env.example                     # Config template
│
├── config/
│   └── settings.py                  # Pydantic settings from .env
│
├── app/
│   ├── agents/                      # 11 pipeline agents
│   │   ├── ingestion.py             # Load & validate scraper output
│   │   ├── normalize.py             # Clean text, parse dates
│   │   ├── dedup.py                 # Embed & cluster articles
│   │   ├── analyze.py               # LLM: structured UPSC analysis
│   │   ├── verify.py                # LLM: fact-check against source
│   │   ├── map_upsc.py              # Route to GS sections
│   │   ├── write_sections.py        # LLM: write section prose
│   │   ├── assemble.py              # Compile HTML document
│   │   ├── render_pdf.py            # HTML → A4 PDF (WeasyPrint)
│   │   ├── deliver.py               # Email PDF via SMTP
│   │   └── audit.py                 # Run report generation
│   │
│   ├── graph/
│   │   ├── state.py                 # LangGraph TypedDict state
│   │   └── workflow.py              # StateGraph pipeline definition
│   │
│   ├── models/
│   │   └── schemas.py               # All Pydantic data models
│   │
│   ├── services/
│   │   ├── llm_client.py            # OpenAI-compatible LLM client
│   │   ├── embedding_client.py      # sentence-transformers embeddings
│   │   ├── storage.py               # File-based artifact storage
│   │   ├── mailer.py                # Gmail SMTP sender
│   │   └── scheduler.py             # APScheduler daily cron
│   │
│   ├── templates/
│   │   └── base.html                # Jinja2 A4 PDF template
│   │
│   └── utils/
│       ├── logging.py               # structlog configuration
│       ├── text.py                   # Boilerplate removal, cleaning
│       ├── dates.py                  # Multi-format date parsing
│       └── files.py                 # JSON/file I/O helpers
│
├── tests/
│   ├── conftest.py                  # Sample article fixtures
│   ├── test_schemas.py              # Schema validation tests
│   ├── test_normalize.py            # Normalization tests
│   └── test_dedup.py                # Clustering tests
│
├── data/                            # Run artifacts (auto-created)
│   ├── runs/                        # Per-run directories
│   │   └── digest_2026-06-09_xxxx/
│   │       ├── raw_articles.json
│   │       ├── normalized_articles.json
│   │       ├── clusters.json
│   │       ├── analysis_units/
│   │       ├── verified_units/
│   │       ├── sections/
│   │       ├── compiled_digest.html
│   │       └── run_report.json
│   ├── logs/
│   └── checkpoints.db
│
└── output/                          # Final PDFs
    └── UPSC_Digest_2026-06-09.pdf
```

## Pipeline Stages

| # | Agent           | Input                  | Output                 | LLM? |
|---|-----------------|------------------------|------------------------|------|
| 1 | Ingestion       | Scraper JSON           | Validated raw articles | No   |
| 2 | Normalization   | Raw articles           | Cleaned articles       | No   |
| 3 | Deduplication   | Normalized articles    | Article clusters       | No   |
| 4 | Analysis        | 1 cluster at a time    | AnalysisUnit JSON      | Yes  |
| 5 | Verification    | 1 unit + source text   | VerifiedUnit JSON      | Yes  |
| 6 | UPSC Mapping    | Verified units         | Section buffers        | No   |
| 7 | Section Writing | Batches of 8-12 units  | HTML fragments         | Yes  |
| 8 | Assembly        | All section fragments  | compiled_digest.html   | No   |
| 9 | PDF Render      | Compiled HTML          | A4 PDF                 | No   |
| 10| Delivery        | PDF file               | Email sent             | No   |
| 11| Audit           | Full state             | run_report.json        | No   |

## Anti-Hallucination Design

1. **Separate prompts** for analysis, verification, and writing
2. **Evidence mapping**: Every claim links to a source text span
3. **Verification gate**: Only pass/partial units proceed
4. **No-new-facts rule**: Writer cannot introduce unsupported content
5. **Source traceability**: Article IDs preserved through entire pipeline

## Debugging

### Inspect Run Artifacts
```bash
# List runs
ls data/runs/

# View a specific run
ls data/runs/digest_2026-06-09_xxxx/

# Check run report
cat data/runs/digest_2026-06-09_xxxx/run_report.json

# View analysis for a cluster
cat data/runs/digest_2026-06-09_xxxx/analysis_units/cluster_0001.json
```

### View Logs
```bash
cat data/logs/digest.log
```

### Run Tests
```bash
conda activate upsc-digest
cd upsc-agent
pytest tests/ -v
```
