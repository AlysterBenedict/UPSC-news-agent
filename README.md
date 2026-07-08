# UPSC Daily Newspaper Digest — Multi-Agent AI System

A production-grade, multi-agent pipeline that aggregates news articles daily, deduplicates them, extracts detailed UPSC syllabus analyses, performs self-critiques to prevent hallucinations, and compiles a premium print-optimized A4 PDF delivered directly to email recipients by 8 AM IST. The project features a stateful command-line interface and a real-time, native desktop GUI wrapper.

---

## System Architecture

```
Scraper Output (400+ articles/day)
         │
         ▼
┌───────────────────────────────────────────────────────────────────┐
│                    LangGraph Stateful Pipeline                    │
│                                                                   │
│  [Ingest] ──► [Normalize] ──► [Cluster & Dedup] ──► [Analyze]     │
│                                                        │          │
│  [HTML Compile] ◄── [Section Write] ◄── [Verify] ◄─────┘          │
│        │                                                          │
│        ▼                                                          │
│  [Render PDF] ──► [Email Delivery] ──► [Audit logs]               │
│                                                                   │
│  ✓ Persistent SQLite Checkpointing (Resume from any step)         │
│  ✓ Dual-Gate Anti-Hallucination Self-Critique                     │
│  ✓ Cosine Similarity Embedding Clustering (sentence-transformers)  │
│  ✓ Source Provenance Traceability                                 │
└───────────────────────────────────────────────────────────────────┘
         │
         ▼
    Premium A4 PDF (30-50+ pages) ──► Email to Subscribers
```

---

## Detailed Features & Technical Implementation

### 1. Robust Multi-Source News Scraper (`scraper_test.py`)
Fetches and aggregates news content from major national dailies and government websites.
* **Mode Dispatcher:** Dispatches scraping jobs based on the target website's format:
  * `rss`: Fetches XML feeds and downloads the article body.
  * `listing`: Scrapes HTML index pages using BeautifulSoup CSS selectors to find articles.
  * `api`: Queries structured JSON endpoints (e.g. MEA's press releases, Down To Earth's story APIs).
  * `rss+web`: Combines RSS feeds with listing scraping to ensure complete coverage.
* **Date Filter:** Restricts processing to today's articles using strict timezone-aware Indian Standard Time (IST) date matching.
* **Fallback & Recovery:** Extracts text using JSON-LD metadata formats as a backup when CSS selectors fail. Uses exponential backoff retries and browser User-Agent headers to handle rate-limiting.
* **Output Destination:** Writes outputs (`scraped_articles_{date}.json` and `scrape_report_{date}.txt`) to the `zartifacts/` folder.

### 2. Stateful Graph Orchestration (LangGraph & SQLite)
Orchestrates the pipeline phases using a stateful directed acyclic graph.
* **LangGraph `StateGraph`:** Defines pipeline stages as graph nodes. Transitions are managed with a TypedDict shared state.
* **SQLite Checkpointing:** Saves a snapshot of the graph state to `checkpoints.db` after each node execution. If a step fails, the pipeline can resume execution from the last successful node.

### 3. Ingestion & Schema Validation (Pydantic)
Validates and sanitizes incoming scraper data.
* **Pydantic Validation:** Models raw articles using strict schemas to prevent schema mismatch errors from corrupt scraper formats.
* **Deterministic Tracking:** Generates a unique SHA-256 hash based on the article URL and source to deduplicate incoming items.

### 4. Dense Embeddings & Clustering (Sentence-Transformers & scikit-learn)
Groups related articles covering the same event into unique topic clusters.
* **Local Embeddings:** Encodes article titles and first 800 characters into dense vectors using a local `all-MiniLM-L6-v2` transformer model (saving API costs).
* **Agglomerative Clustering:** Performs clustering with an average-linkage metric using a cosine distance threshold of `0.35` (cosine similarity > `0.65`).
* **Primary Source Selection:** Identifies the longest article as the primary source, appending unique paragraphs from supporting articles to form a single combined cluster text.

### 5. Structured UPSC Analysis (NVIDIA NIM Llama 3.3)
Extracts academic context from news clusters using LLMs.
* **Syllabus Mapping:** Classifies clusters against the UPSC Civil Services Syllabus (GS Paper 1, 2, 3, or 4) and tags relevant subtopics.
* **UPSC Extraction:** Formulates structured JSON outputs (`AnalysisUnit`) capturing:
  * **Core Facts:** Essential data points and events.
  * **Context:** Background information.
  * **Syllabus Relevance:** Explanation of why it's important for the exam.
  * **Key Terms:** Essential terminology.
  * **Logical Arguments:** Major viewpoints and arguments.
* **SCAN Strategy Integration:** Directs the extraction structure using a specialized administrative analysis framework:
  * **Situation (S):** Traces underlying structural problems and systemic root causes.
  * **Consequences (C):** Examines 360-degree impact on multiple stakeholders, focusing on vulnerable groups.
  * **Alternatives (A):** Weighs alternative public policy options and trade-offs.
  * **Next Step (N):** Outlines a timeline oriented action plan (Short, Mid, Long term) from a public administrator's perspective.

### 6. Dual-Gate Verification (Anti-Hallucination Guardrails)
Ensures factual accuracy by validating LLM statements against source texts.
* **Line-by-Line Critique:** Compares each statement in the analysis block against the raw article text using the LLM.
* **Verification Scoring:** Labels each claim with a verification status (`pass`, `partial`, `fail`).
* **Source Mapping:** Requires the LLM to identify the exact source text span that supports the claim. If a claim fails verification, it is deleted from the final report.

### 7. Syllabus Mapping & Section Writing (Jinja2 & NIM Llama 3.1)
Synthesizes verified inputs into cohesive study materials.
* **Routing:** Maps verified units to subject categories (National, International Relations, Economy, Opinion, etc.).
* **Section Prose Generation:** Uses Llama 3.1 to rewrite batches of 8-12 articles into cohesive, analytical sections. The output is structured to mirror UPSC answers: objective, crisp, and focused on policy implications.

### 8. Premium A4 PDF Rendering (WeasyPrint)
Generates print-ready PDFs from the compiled HTML.
* **Print CSS Rules:** Uses CSS paged media rules (`@page`) to manage margins, page numbering, running headers, and footers.
* **Document Structure:** Integrates a table of contents and inserts page break controls (`page-break-inside: avoid`) to prevent orphan headers or split tables.
* **Styling:** Uses clear typography (Georgia/Inter), subtle borders, and balanced spacing.

### 9. Real-Time Desktop App Interface (PyWebView)
Runs the pipeline within a desktop application window.
* **API Key Manager:** Saves and loads settings from `config.json`, setting `os.environ["NIM_API_KEY"]` dynamically before launching the graph.
* **Log Redirection:** Captures `stdout` and `stderr` using a queue-based `LogEmitter`. Throttles updates at a 100ms interval to prevent UI lag.
* **Native Integration:** Uses PyWebView window hooks for native file saving dialogs and default application handlers (`os.startfile`) to open generated PDFs.

### 10. PyInstaller Packaging & Self-Installation
Packages the desktop app for simple deployment.
* **Single EXE Compilation:** Bundles Python, libraries, and UI templates into a single `UPSC_Digest_Agent.exe` file.
* **Subprocess Interception:** Detects CLI scraper arguments on launch and executes the scraper in-process rather than attempting to spawn a separate python environment.
* **Start Menu & Program Files Installer:** Automatically copies the binary to local program files and registers a Start Menu shortcut on Windows.

---

## Tech Stack

| Component        | Technology                                       |
|------------------|--------------------------------------------------|
| **Orchestration** | LangGraph (Stateful graph with SQLite checkpointer) |
| **LLM Inference** | NVIDIA NIM API (Llama 3.3 70B & Llama 3.1 8B)     |
| **Local Embeddings** | Sentence-Transformers (`all-MiniLM-L6-v2`)     |
| **Clustering**   | Scikit-Learn `AgglomerativeClustering`          |
| **Validation**   | Pydantic v2                                      |
| **PDF Converter** | WeasyPrint                                       |
| **GUI Container** | PyWebView                                        |
| **CLI Parser**   | argparse                                         |
| **Logging**      | structlog (Structured JSON format)               |
| **Scheduler**    | APScheduler (APS)                                |

---

## Project Structure

```
UPSC news agent/
├── scraper_test.py                  # News scraper script
├── zartifacts/                      # Scraper JSON and TXT output directory
├── upsc-app/                        # Desktop GUI App
│   ├── app_app.py                   # Desktop app GUI launcher and API bridge
│   ├── build_app.py                 # PyInstaller execution configuration
│   ├── UPSC_Digest_Agent.spec       # PyInstaller build specification
│   ├── icon.ico                     # Native application icon
│   ├── ui/                          # GUI HTML, CSS, JS frontend assets
│   │   ├── index_app.html
│   │   ├── style_app.css
│   │   └── script_app.js
│   └── app/                         # App-specific services and modules
│       ├── agents/                  # GUI-compatible agents (suffixed _app.py)
│       ├── graph/                   # GUI-compatible graph implementation
│       ├── services/                # Settings, Storage, and Mailer services
│       └── utils/                   # Logging, Date, and File utilities
│
└── upsc-agent/                      # Core CLI Pipeline
    ├── main.py                      # Core CLI main runner
    ├── requirements.txt             # Python dependencies
    ├── .env                         # Local secrets and config (git-ignored)
    ├── .env.example                 # Environment config template
    ├── config/
    │   └── settings.py              # Pydantic Settings class
    ├── app/                         # Primary pipeline code
    │   ├── agents/                  # Pipeline stage processors
    │   ├── graph/                   # Stateful graph definition
    │   ├── models/                  # Pydantic schemas (schemas.py)
    │   ├── services/                # LLM client, Embeddings, Storage, Mailer
    │   ├── templates/               # Jinja2 HTML design templates
    │   └── utils/                   # Logging, cleaning, files, syllabus
    ├── data/                        # Persistent run data and logs
    │   ├── checkpoints.db           # SQLite graph checkpoint storage
    │   ├── logs/                    # Runtime log storage
    │   └── runs/                    # Individual run data directories
    └── output/                      # Compiled output PDFs directory
```

---

## Setup & Run Guide

### 1. Configure the Environment
Clone the repository and create your local environment:
```bash
conda create --name upsc-digest python=3.11
conda activate upsc-digest
```

Navigate to `upsc-agent` and install dependencies:
```bash
cd upsc-agent
pip install -r requirements.txt
```

### 2. Configure Credentials
Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```
Fill in the configuration details:
* `NIM_API_KEY`: Obtain an API key from [NVIDIA NIM](https://build.nvidia.com).
* `SMTP_PASS`: Generate a Gmail App Password at [Google Account App Passwords](https://myaccount.google.com/apppasswords) if delivering digests via email.

---

## Usage

### Command Line Interface

* **Run the full pipeline for today:**
  ```bash
  python main.py run
  ```

* **Run the pipeline for a specific date:**
  ```bash
  python main.py run --date 2026-06-14
  ```

* **Start the 8 AM IST Daily Scheduler:**
  ```bash
  python main.py schedule
  ```

* **Skip the scraping phase and use existing JSON files:**
  ```bash
  python main.py run --skip-scrape
  ```

* **Render a PDF only from a past run:**
  ```bash
  python main.py render-only --run-id digest_2026-06-14_abcdefgh
  ```

* **Send an existing PDF file to email subscribers:**
  ```bash
  python main.py deliver-only --pdf output/UPSC_Digest_2026-06-14.pdf --date 2026-06-14
  ```

### Desktop Application

* **Run the GUI app in development mode:**
  ```bash
  cd upsc-app
  python app_app.py
  ```

* **Compile the standalone executable:**
  ```bash
  python build_app.py
  ```
  This creates a standalone executable inside `upsc-app/dist/` named `UPSC_Digest_Agent.exe`.
