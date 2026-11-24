# Lululemon AU — Biggest Savings

A GitHub Actions + GitHub Pages monitor for lululemon.com.au **We Made Too Much**
(women + men). Every 6 hours it scrapes the sale pages, ranks products by
dollars saved (AUD), and publishes a static Top list to GitHub Pages.

No WhatsApp push — that cannot be done from GitHub Actions without a
third-party messaging service, so it was deliberately left out of this
migration. The Muse version of this monitor still has WhatsApp pushes.

## How it works

1. `scraper/scrape.py` (Python + Playwright) loads both We Made Too Much
   pages in headless Chromium, clicks **View more** until the list ends
   (40 items per load), and extracts name, gender, category, sale price,
   struck-through original price, product URL and colour for each item.
2. Colour variants of the same product are merged (largest saving wins).
   Saving = original − sale; discount % is calculated, because the site
   does not show it. The list is sorted by saving desc, then discount %.
3. Results go to `data/deals.json` (full list) and `data/top10.json`.
4. `site/` is a static page (no build step) that renders `deals.json`
   with gender/category checkbox filters and a search box. Size is never
   filtered.

## Setup

1. Create a **public** repo named `lululemon-au-deals` under `jasper-bne`
   (GitHub Pages on the free plan needs a public repo) and push this
   project to `main`.
2. In the repo, go to **Settings → Pages → Build and deployment** and
   select **GitHub Actions** as the source.
3. Run the workflow once manually (**Actions → Update Lululemon deals →
   Run workflow**) to populate the first scan and publish the site.
4. The site will be at `https://jasper-bne.github.io/lululemon-au-deals/`.

## Configuration

Edit `config.json`:

| Key | Default | Meaning |
| --- | --- | --- |
| `minSavingAud` | 30 | (Reference only — the site shows all deals; the Muse monitor used this as its WhatsApp threshold.) |
| `minDiscountPct` | 25 | Same as above. |
| `checkHours` | 6 | How often the workflow runs. To change it, also edit the `cron` line in `.github/workflows/update-deals.yml` (`0 */6 * * *` = every 6 hours, UTC). |

## Honest limitation

Plain HTTP requests to lululemon.com.au return **HTTP 403 from Akamai**,
which is why the scraper uses a real browser. Akamai may still block
GitHub Actions runner IPs even with Playwright. If a run is blocked,
`scrape.py` exits non-zero, **does not** overwrite the existing
`data/deals.json`, and the site keeps showing the last good data — check
the failed workflow run's log to confirm. If blocking persists, the
options are: run the scraper less often, run it from a different network,
or fall back to the Muse-hosted monitor (which uses a real browser
session that is not blocked).

## Verified snapshot

`docs/verified-top11-2026-11-24.md` is a reference snapshot of the Top 11
from a manual browser check on 2026-11-24. It is **not** live data.
