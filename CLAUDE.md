# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Headhunter** is an AI-powered job research toolkit for the Taiwan job market. It collects data from 104.com.tw and web search APIs, then generates markdown reports for Claude Code analysis via custom slash commands.

## Setup & Commands

```bash
uv sync                              # Install dependencies
uv run playwright install chromium   # Required for 104 scraping (Cloudflare bypass)
cp .env.example .env                 # Configure TAVILY_API_KEY and ANTHROPIC_API_KEY
```

### CLI Entry Points

```bash
uv run headhunter       # Research a single company (interactive: company + position + resume)
uv run search104        # Scrape 104.com.tw search results for a given URL
uv run search1111       # Scrape 1111.com.tw search results for a given URL
uv run vendor-search vendors.csv  # Batch scrape a list of companies (CSV or TXT)
```

No test suite exists — all validation is done manually via CLI runs.

## Architecture

The project follows a **collect → report → analyze** pipeline:

1. **Data collection** — Tavily web search + Playwright-based 104.com.tw scraping run in parallel (thread pools)
2. **Report generation** — Results written as timestamped markdown to `reports/`
3. **Claude analysis** — Claude Code slash commands read the reports and user's `resume/resume.md`

### Key Modules

| Module | Role |
|--------|------|
| `src/main.py` | `headhunter` entry point; orchestrates parallel Tavily + 104 scraping |
| `src/searcher.py` | `JobSearcher`: runs 5 parallel Tavily queries (intro, jobs, news, reviews, tech stack) |
| `src/scraper_104.py` | `Scraper104`: Playwright headless browser, intercepts 104 XHR API responses |
| `src/search_104.py` | `JobSearchScraper`: paginated 104 search results scraper with batch JD fetching |
| `src/search_1111.py` | `JobSearchScraper1111`: 1111.com.tw scraper; parses Nuxt SSR `__NUXT_DATA__` per page |
| `src/vendor_search.py` | Reads vendor CSV/TXT, interactively resolves ambiguous company names, batch scrapes |
| `src/report_writer.py` | Writes timestamped `reports/{company}_{position}_{YYYYMMDD_HHMM}/` markdown reports |
| `src/resume_loader.py` | Loads `resume/resume.md` for AI context |

### 104.com.tw API Endpoints (intercepted by Playwright)

- Company search: `/company/ajax/list?keyword={keyword}`
- Company content: `/api/companies/{cust_no}/content`
- Job listings: `/api/companies/{cust_no}/jobs?page={n}`

### Report Outputs

```
reports/
├── {公司}_{職位}_{timestamp}/     # headhunter output
│   ├── research_data.md           # Full research (passed to /job_research)
│   └── raw_search.json
├── search_104_{timestamp}/        # search104 output
│   ├── jobs.md                    # Job listings (passed to /job_match)
│   └── jobs.json
├── search_1111_{timestamp}/        # search1111 output
│   ├── jobs.md                    # Job listings (passed to /job_match)
│   └── jobs.json
└── vendor_search_{timestamp}/     # vendor-search output
    ├── jobs.md
    └── vendors_result.json
```

### Claude Code Slash Commands

Defined in `.claude/commands/`:
- `/job_research {research_data.md}` — Analyzes single company research against resume
- `/job_match {jobs.md}` — Ranks multiple jobs 1–5 stars against resume; keeps "碩士／博士 + 0 經驗" roles in the ranked pool when skills and domain fit are strong, and marks them as `可衝刺`

User resume lives at `resume/resume.md` (gitignored, see `resume/resume.example.md` for format).

## Environment Variables

| Variable | Required | Default |
|----------|----------|---------|
| `TAVILY_API_KEY` | Yes | — |
| `ANTHROPIC_API_KEY` | Yes | — |
| `TAVILY_MAX_RESULTS` | No | 10 |
| `CLAUDE_MODEL` | No | `claude-sonnet-4-6` |
