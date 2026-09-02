# Scraper notes

The source spiders intentionally stop on robots/WAF challenges. They do not solve challenges, spoof browser fingerprints, or use third-party mirrors.

Run locally with:

```bash
cp .env.example .env
docker compose run --rm scraper
docker compose run --rm ingestion
```

The current implementation starts with ordinary HTTP + HTML parsing. If the source returns a JavaScript shell without a challenge, the parser can be extended with a source-approved rendering path. Any live discovery findings, blocked URLs, and counts should be recorded in the scrape run notes and final submission.

DarGlobal's ordinary HTTP path returned an Incapsula shell during this build, while the same public pages loaded in a standard browser session without authentication or challenge solving. The auditable browser capture contains 36 project pages, 15 dated press articles, and the public About/Investor Relations pages at `data/darglobal_browser_capture.json` and is normalized with:

```bash
PYTHONPATH=. .venv/bin/python -m ingestion.import_darglobal_capture
PYTHONPATH=. .venv/bin/python -m ingestion.export_seed
```

This is a checked-in snapshot fallback, not hidden bypass logic. The ordinary HTTP spider remains the preferred future refresh path when the source permits it.
