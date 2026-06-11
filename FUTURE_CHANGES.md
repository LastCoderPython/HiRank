# Future Changes — Deferred Upgrades for RankRoute

This file documents upgrades that are deferred until trigger conditions (from structured miss logs) justify the engineering cost.

---

## Priority Overview

| Priority | Description | When |
|----------|-------------|------|
| P0 | Blocks existing functionality — fix first | Triggered by log signal |
| P1 | Significant improvement, moderate effort | Triggered by log signal |
| P2 | Nice-to-have, optimizes cost/quality | Triggered by budget/scale |
| P3 | Exploratory — no immediate need | When adjacent work lands |

---

## P0: httpx-based Subpage Discovery (Coverage Gap)

**Estimated effort:** ~2 hours  
**Trigger:** ChromaDB misses concentrated on fee/placement/hostel pages

The weekly cron scrape only hits 14 hardcoded homepage URLs. College subpages (e.g., `aec.ac.in/fees`, `jec.ac.in/placements`) are never ingested. This is the root cause of the 20%+ miss rate on fee/placement/hostel queries.

**Approach:**
1. Use httpx to fetch each known homepage
2. Parse `<a>` tags to discover same-domain subpage links
3. Filter for page-type-relevant paths (fee, placement, hostel, admission, etc.)
4. Ingest discovered subpages into ChromaDB

**Escalation:** If httpx is blocked by anti-bot, promote to P1 and use Scrapling.

## P1: Scrapling Spider Integration (Anti-bot Escalation)

**Estimated effort:** 1-2 days  
**Trigger:** httpx-based subpage discovery gets blocked by anti-bot measures

Scrapling is a headless-browser-aware scraping library designed for modern JavaScript-heavy sites with anti-bot protections.

**Key capabilities relevant to RankRoute:**
- **Adaptive tracking:** Scrapling automatically selects the best HTTP client (httpx, curl_cffi, cloudscraper) and can fall back to Playwright for JS-rendered pages
- **AutoScraper:** Single-call page extraction with markdown output, stripping nav/footer boilerplate
- **Spider:** Parallel crawling with depth control, URL filtering, and optional JS rendering via Playwright
- **Element targeting:** CSS selectors for specific page sections (fee tables, placement stats, notice boards)

**Integration points:**

| Component | Current | With Scrapling |
|-----------|---------|----------------|
| Fetcher | httpx (naive) | AutoScraper / Spider with auto-fallback |
| URL discovery | Manual list | Spider crawl with depth=1, same-domain filter |
| Content extraction | Full-page text | Targeted element extraction per page_type |
| JS rendering | None | Optional Playwright fallback |

**Implementation sketch:**
```python
from scrapling import AutoScraper

scraper = AutoScraper()
result = scraper.get("https://college.ac.in/fees")
if result and result.status == 200:
    markdown = result.body.markdown  # Clean markdown with boilerplate stripped
```

**Why deferred:** The current naive httpx may work fine for most college websites. Scrapling should only be introduced if httpx demonstrably fails.

## P1: Extended Weekly Cron (Self-healed URL Refresh)

**Estimated effort:** ~10 minutes  
**Trigger:** Self-healed URLs in ChromaDB > 10 and still growing

Self-healed URLs (ingested via Tavily fallback during live sessions) are never re-scraped. Over time, these accumulate stale data.

**Fix:** In the weekly cron script, instead of only the 14 hardcoded URLs, query ChromaDB for all distinct `source_url` values and ingest them all.

**When to act:** Check ChromaDB count of unique `source_url` values. If > 24 (14 original + 10 self-healed), the gap is growing and this should be done.

## P2: Daily Refresh Infrastructure

**Estimated effort:** ~2 hours  
**Trigger:** User complaints about stale data during counseling season (May–August)

College data changes rapidly during admission season. Weekly refresh may not be enough for fee notices, counseling dates, and seat matrices.

**Approach:**
1. Add a daily cron job running at 6 AM
2. Only re-ingest URLs whose `scraped_at` is > 24 hours old
3. Use ChromaDB metadata query to find stale URLs: `where: {"scraped_at": {"$lt": cutoff_iso}}`

## P2: Content-diffing Optimization

**Estimated effort:** ~3 hours  
**Trigger:** Embedding API costs become significant or weekly cron latency > 10 minutes

Currently every scrape re-ingests even if content hasn't changed. Content-diffing would:
1. Fetch the page
2. Chunk it
3. Compare chunk hashes with stored `content_hash` in ChromaDB
4. Only upsert chunks that differ

**Deferred because:** At current scale (14 URLs, ~100 chunks), re-embedding costs are negligible ($0.001/week with Voyage).

## P2: Search Fallback Cost Elimination

**Estimated effort:** ~1 hour per option  
**Trigger:** Tavily costs exceed budget threshold

Current search fallback options:

| Option | Cost | Quality |
|--------|------|---------|
| Google CSE | Free (10K queries/day) | High |
| DuckDuckGo | Free (rate-limited) | Medium |
| SearXNG | Self-hosted | High |
| Tavily (current) | $7-24/month | High |

**Recommendation:** Switch to Google CSE first. It's free (up to 10K queries/day), requires minimal code change (swap the search API client), and has comparable quality.

## P3: Full-text Search Index

**Estimated effort:** ~1 week  
**Trigger:** Users need keyword-based search (e.g., "mention scholarship in any page")

ChromaDB only supports semantic search. For keyword lookup (e.g., finding all mentions of "scholarship"), a full-text search index is needed.

**Options:**
- **SQLite FTS5** — Free, zero-infrastructure, good enough for 10K documents
- **Meilisearch** — Self-hosted, fast, typo-tolerant, good for production-scale

## P3: College Data Version History

**Estimated effort:** ~4 days  
**Trigger:** Users ask for "what did the website say last week?"

ChromaDB doesn't natively support versioned collections. Options:
- Store versions as separate collections (e.g., `college_web_docs_v1`, `college_web_docs_v2`)
- Use SQLite temporal tables alongside ChromaDB
- Append version metadata and filter at query time

---

## How to Use This File

1. Check structured miss logs weekly for trigger conditions
2. When a trigger condition is met, promote that item to active work
3. After completing an upgrade, move the entry to `CHANGELOG_PRODUCTION.md`
4. Re-evaluate priorities quarterly
