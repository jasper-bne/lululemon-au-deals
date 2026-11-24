# Lululemon AU — Biggest Savings

A GitHub Pages monitor for lululemon.com.au **We Made Too Much**
(women + men). **Muse** scans the sale pages every 6 hours (its browser
loads the site fine), ranks products by dollars saved (AUD), pushes the
results to `data/`, and a deploy-only GitHub Actions workflow publishes
the static Top list to GitHub Pages.

No WhatsApp push — that cannot be done from GitHub Actions without a
third-party messaging service, so it was deliberately left out of this
migration. The Muse version of this monitor still has WhatsApp pushes.

## How it works

1. Muse scans both We Made Too Much pages in its browser, clicks
   **View more** until the list ends (40 items per load), and extracts
   name, gender, category, sale price, struck-through original price,
   product URL and colour for each item.
2. Colour variants of the same product are merged (largest saving wins).
   Saving = original − sale; discount % is calculated, because the site
   does not show it. The list is sorted by saving desc, then discount %.
3. Results go to `data/deals.json` (full list) and `data/top10.json`.
4. Pushing `data/*.json` triggers the deploy-only workflow
   (`.github/workflows/update-deals.yml`), which copies the data into
   `site/` and deploys Pages.
5. `site/` is a static page (no build step) that renders `deals.json`
   with gender/category checkbox filters and a search box. Size is never
   filtered.

## Why not scrape in Actions?

GitHub Actions runner IPs are blocked by lululemon/Akamai: run #1 failed
on `net::ERR_HTTP2_PROTOCOL_ERROR`, run #2 timed out (90s × 3 retries)
on both gender pages with 0 deals found. The old Playwright scraper was
removed from this repo on 2026-11-24 — it is no longer run by any
workflow.

## Setup

1. Create a **public** repo named `lululemon-au-deals` under `jasper-bne`
   (GitHub Pages on the free plan needs a public repo) and push this
   project to `main`.
2. In the repo, go to **Settings → Pages → Build and deployment** and
   select **GitHub Actions** as the source.
3. Push fresh `data/deals.json` + `data/top10.json` (Muse does this
   every 6 hours) to populate the first scan and publish the site.
4. The site will be at `https://jasper-bne.github.io/lululemon-au-deals/`.

## Configuration

There is nothing to configure in this repo. Check frequency (every
6 hours), the saving/discount thresholds and the watched categories all
live in the Muse monitor's dashboard — this repo only stores the
published data and the static site.

## Honest limitation

Plain HTTP requests to lululemon.com.au return **HTTP 403 from Akamai**,
and GitHub Actions runner IPs are blocked/timed out even with a real
browser (see "Why not scrape in Actions?" above). That is why scanning
happens in Muse. If a Muse scan is blocked, the site keeps showing the
last good data — check the Muse monitor's last scan time on the page.

## Verified snapshot

`docs/verified-top11-2026-11-24.md` is a reference snapshot of the Top 11
from a manual browser check on 2026-11-24. It is **not** live data.
