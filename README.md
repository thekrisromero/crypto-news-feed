# crypto-news-feed

Self-hosted RSS aggregator for the **Crypto Custody & Treasury Weekly Briefing**. A GitHub Action fetches RSS feeds every 4 hours and commits a curated `data/latest.json` to this repo. The downstream Claude scheduled task does a sparse git clone of just that JSON to build the Monday briefing.

## Why this exists

The Claude desktop app (Cowork) runs scheduled tasks in a sandbox with a strict network allowlist. Crypto news domains aren't on it, but `github.com` is — so we let GitHub Actions (which has unrestricted internet) do the fetching, and we pull the result via git.

## What's in here

```
.
├── .github/workflows/fetch-news.yml   # runs every 4h, commits data/latest.json
├── scripts/fetch_feeds.py             # the fetcher (Python + feedparser)
├── feeds.json                         # source list + filter keywords (edit to customize)
├── requirements.txt                   # Python deps for the Action
└── data/
    ├── latest.json                    # most recent run (consumed by Claude)
    └── archive/YYYY-MM-DD.json        # daily snapshots
```

## One-time setup

1. **Create a public GitHub repo.** Repo name `crypto-news-feed` is fine. Public is required so Claude's sandbox can clone it without authentication.

2. **Push these files.** From the parent folder on your Mac:
   ```bash
   cd "/Users/kromero/Documents/Claude/Projects/Crypto Research/crypto-news-feed"
   git init -b main
   git add .
   git commit -m "Initial commit"
   git remote add origin https://github.com/<your-username>/crypto-news-feed.git
   git push -u origin main
   ```

3. **Enable GitHub Actions.** On your repo page → **Actions** tab → if prompted, click "I understand my workflows, go ahead and enable them."

4. **Trigger the first run manually.** Actions tab → "Fetch crypto news" → "Run workflow" → "Run workflow". Wait ~1 minute. You should see a new commit appear with `data/latest.json` populated.

5. **Tell Claude the repo URL.** Open the Claude desktop app and message me with:
   ```
   My news feed repo is at https://github.com/<your-username>/crypto-news-feed
   ```
   I'll update the scheduled task to point at it.

## Customizing the source list

Edit `feeds.json` to add/remove feeds or tune the filter keywords. Push the change; the Action automatically re-runs on every push.

- `feeds[]` — list of RSS feed URLs with name, tier, and topic tags
- `lookback_days` — how many days back to include items (default 8)
- `max_items_per_feed` — cap per feed to avoid noisy outlets dominating
- `filter_keywords_negative` — case-insensitive substrings; items matching are dropped
- `filter_keywords_priority` — case-insensitive substrings; matches boost the item's `relevance_score`

## Cost

Free. GitHub Actions gives 2,000 free minutes/month on private repos; this workflow uses ~5 minutes per run, ~6 runs/day = ~900 minutes/month. Public repos have unlimited free minutes.

## Failure modes

- **A feed URL changes or 404s** → the script logs a warning and continues; that source is silently dropped for the run. Check Actions logs to spot persistent failures.
- **GitHub Actions disabled** → the Monday briefing will use stale data (last successful commit). Re-enable Actions in repo Settings.
- **You change feeds.json badly** → the push triggers a run; if it fails, the previous `data/latest.json` stays in place (no destructive overwrite).
