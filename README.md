# Stock Weather AI — Reading the Market's Forecast

Imagine a weather report for the markets: a short, clear summary about whether a stock looks "sunny" or "stormy" based on a mix of price moves, company filings and the day's news. Stock Weather AI is a compact toolkit that collects market and news data, runs lightweight evaluations and produces per‑ticker reports you can use in experiments or pipelines.

This README explains the project's motivation, architecture, the main components in the codebase, and how to run the non-UI parts (agents, evaluation, and API). The web UI exists in `ui/` but is intentionally excluded here, this document focuses on the engine that fetches, evaluates and exposes results.

## Motivation

Building reproducible short-term signals means combining reliable structured data (price, volumes, financial statements) with noisy but valuable unstructured signals (news, headlines). Stock Weather AI provides:

- Pluggable agents to gather different inputs (financial reports, news, top movers).
- A small evaluation layer to produce comparable per-ticker outputs.
- A lightweight API that returns the generated reports so you can automate downstream workflows.

The project is opinionated but small: it's meant for research and rapid experimentation rather than production trading.

## High-level architecture

The system is composed of a few simple layers:

- Agents: responsible for fetching data (see `agents/`). There are agents for news, financial reports, and determining requested tickers (top movers).
- Toolkit: shared utilities such as caching, proxy handling, and user-agent rotation used by the agents (`toolkit/`).
- Evaluation: a small module that synthesizes agent outputs into an evaluation result for a single ticker (see `agents/evaluation.py`).
- Reports: evaluation results are written to `reports/` with a filename convention `evaluation_{TICKER}_{YYYY-MM-DD}.json`.
- API: a tiny FastAPI service (`api.py`) that reads `reports/` and returns the latest (or requested) date's reports to clients.

Flow (summary): requested tickers -> fetch news + financials -> run evaluation -> write report -> serve via API.

## Key repository components

- `agents/` — core data-gathering and evaluation logic. Files of interest:
	- `agents/agent.py`: an example orchestrator that pulls top movers, fetches news and financials, evaluates and writes reports.
	- `agents/news.py`: news collection helpers (async functions used by the orchestrator).
	- `agents/financial.py`: financial report fetching and parsing utilities.
	- `agents/requested_tickers.py`: logic that selects which tickers to process (top movers).
	- `agents/evaluation.py`: the lightweight evaluation producing the final signal/metrics for each ticker.

- `toolkit/` — helper libraries used by agents for caching, proxy management and user-agent rotation. These improve reliability when scraping external sources.

- `api.py` — a small FastAPI server exposing a `/reports` endpoint which returns JSON report files by date and a `/health` endpoint. The API scans the `reports/` directory for files matching `evaluation_{TICKER}_{YYYY-MM-DD}.json`.

- `options.py` — global runtime options and model wiring (LLM/embeddings). This module is ready to be configured from environment variables and shows how the project can integrate with LLMs and embeddings for richer analysis.

- `reports/` — output folder where evaluation results are stored. The API reads these files for clients.

## File naming and report format

Reports are stored in `reports/` and follow the naming convention:

`evaluation_{TICKER}_{YYYY-MM-DD}.json`

Each report is a JSON-like dictionary containing at least:

- ticker
- date
- news (raw or summarized entries)
- financial_report (raw or parsed data)
- evaluation (the output of `agents/evaluation.eval`)

## Running locally (engine + API)

Prerequisites

- Python 3.10+.
- The repository's Python dependencies (see `requirements.txt`).
- Environment variables for optional LLM/embedding integrations (if you want to enable them):
	- `OPENAI_API_KEY`, `OPENAI_MODEL`
	- `EMBEDDING_MODEL`, `INFINITY_API_URL` (currently only supporting local Infinity embeddings)

Install dependencies in a virtual environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Running the API

Start the FastAPI server:

```bash
# from the project root
uvicorn api:app --reload --host 0.0.0.0 --port 8000
```

The API exposes two simple endpoints:

- GET /health — quick liveness check
- GET /reports[?date=YYYY-MM-DD] — returns the reports for the given date or the latest available date. The response includes the list of available dates.

Example curl to fetch the latest reports:

```bash
curl -sS http://127.0.0.1:8000/reports | jq .
```

## Final notes

Stock Weather AI is a research-oriented scaffold. It deliberately keeps components small and modular so you can iterate quickly. The codebase contains a simple API for consumption and a set of agents that illustrate how to collect the inputs you need.

Happy experimenting and treat these signals as research tools, not trading advice.

[Github link](https://github.com/earezki/stock-weather-ai)
# stock-weather-ai
