#!/usr/bin/env python3
"""Scrape lululemon.com.au We Made Too Much (women + men) with Playwright.

Why Playwright, not requests: plain HTTP requests to lululemon.com.au get
HTTP 403 from Akamai ("Access Denied"). A real browser loads the pages fine,
so this scraper drives headless Chromium.

Output:
  data/deals.json  {scannedAt, sources, total, deals: [...]}
  data/top10.json  same shape, first 10 deals only

Each deal: {name, gender, category, salePrice, originalPrice, saving,
discountPct, url, colour}

Rules (same as the Muse monitor this migrates):
  * Sort by saving (AUD) desc, then discountPct desc.
  * Merge colour variants of the same product: dedupe key is the product
    URL with the ?color= query stripped; keep the variant with the
    largest saving.
  * Size is never filtered.
  * If a page is blocked or yields no discounted products, exit non-zero
    and DO NOT overwrite existing data files (the site keeps last good data).

Usage:
  python scraper/scrape.py [--config config.json]
      [--executable-path /path/to/chrome] [--headed]
  Env: PLAYWRIGHT_BROWSERS_PATH can point at a pre-installed browser
  store; --executable-path uses a system Chrome/Chromium instead.
"""

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = ROOT / "config.json"
DATA_DIR = ROOT / "data"

PRICE_RE = re.compile(r"A\$\s*([\d,]+(?:\.\d{2})?)")

# JS run inside the page: find every product link, then walk up to a
# container that holds prices. Selectors on lululemon change often, so
# this scans the DOM generically instead of depending on one class name.
EXTRACT_JS = """
() => {
  const seen = new Map();
  for (const a of document.querySelectorAll('a[href*="/en-au/p/"]')) {
    const href = a.getAttribute('href') || '';
    if (!href.includes('/en-au/p/')) continue;
    // Walk up at most 6 levels looking for a container with a price.
    let node = a, container = null;
    for (let i = 0; i < 6 && node; i++) {
      if (/A\\$/.test(node.textContent || '')) { container = node; break; }
      node = node.parentElement;
    }
    if (!container) continue;
    const text = container.textContent || '';
    const prices = [...text.matchAll(/A\\$\\s*([\\d,]+(?:\\.\\d{2})?)/g)]
      .map(m => parseFloat(m[1].replace(/,/g, '')))
      .filter(n => Number.isFinite(n) && n > 0);
    if (prices.length < 2) continue; // need sale + struck-through original
    const sale = Math.min(...prices);
    const original = Math.max(...prices);
    if (original <= sale) continue;
    const img = a.querySelector('img') || container.querySelector('img');
    const name = (a.getAttribute('aria-label')
      || (img && img.getAttribute('alt'))
      || a.textContent || '').trim().replace(/\\s+/g, ' ').slice(0, 200);
    if (!name) continue;
    const url = new URL(href, location.origin).href;
    const colour = new URL(url).searchParams.get('color') || null;
    // Category is not reliably in the card; best effort from breadcrumbs
    // is skipped — category is filled from the gender page if unknown.
    const key = url.split('?')[0];
    const prev = seen.get(key);
    if (!prev || (original - sale) > (prev.originalPrice - prev.salePrice)) {
      seen.set(key, {name, salePrice: sale, originalPrice: original, url, colour});
    }
  }
  return [...seen.values()];
}
"""


def load_config(path):
    with open(path, encoding="utf-8") as f:
        cfg = json.load(f)
    cfg.setdefault("minSavingAud", 30)
    cfg.setdefault("minDiscountPct", 25)
    cfg.setdefault("maxItemsPerGender", 600)
    cfg.setdefault("sources", {
        "women": "https://www.lululemon.com.au/en-au/c/women-we-made-too-much/n16o10z8mhd",
        "men": "https://www.lululemon.com.au/en-au/c/men-we-made-too-much/n18mhdznrqw",
    })
    return cfg


def dedupe_key(url):
    """Strip query (colour) so colour variants of one product merge."""
    parsed = urlparse(url)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def scrape_gender(page, gender, url, cap):
    page.goto(url, wait_until="domcontentloaded", timeout=90000)
    page.wait_for_timeout(4000)
    # Dismiss a cookie/consent banner if one appears (best effort).
    for label in ("Accept", "Accept All", "Got it", "Close"):
        try:
            btn = page.get_by_role("button", name=label, exact=False).first
            if btn.is_visible(timeout=2000):
                btn.click(timeout=3000)
                page.wait_for_timeout(1000)
                break
        except Exception:
            pass

    # Click "View more" until it disappears. 40 items per load.
    clicks = 0
    while clicks < 20:  # 40 + 20*40 = 840, above the 600 cap
        try:
            btn = page.get_by_role("button", name=re.compile(r"view more", re.I)).first
            if not btn.is_visible(timeout=3000):
                break
            before = page.evaluate("() => document.querySelectorAll('a[href*=\"/en-au/p/\"]').length")
            btn.click(timeout=5000)
            page.wait_for_timeout(3000)
            after = page.evaluate("() => document.querySelectorAll('a[href*=\"/en-au/p/\"]').length")
            clicks += 1
            if after <= before:
                break  # no new items loaded; assume end of list
            if after >= cap:
                break
        except Exception as e:
            print(f"[{gender}] View more stopped: {e}", file=sys.stderr)
            break

    raw = page.evaluate(EXTRACT_JS)
    deals = []
    for item in raw:
        saving = round(item["originalPrice"] - item["salePrice"], 2)
        pct = round(saving / item["originalPrice"] * 100, 1) if item["originalPrice"] else 0.0
        deals.append({
            "name": item["name"],
            "gender": gender,
            "category": "Sale",
            "salePrice": item["salePrice"],
            "originalPrice": item["originalPrice"],
            "saving": saving,
            "discountPct": pct,
            "url": item["url"],
            "colour": item.get("colour"),
        })
    return deals


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=str(DEFAULT_CONFIG))
    ap.add_argument("--executable-path", default=None,
                    help="Path to a system Chrome/Chromium binary to use instead of the Playwright-bundled one.")
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    cap = int(cfg["maxItemsPerGender"])

    all_deals = []
    with sync_playwright() as p:
        launch_kwargs = {"headless": not args.headed}
        if args.executable_path:
            launch_kwargs["executable_path"] = args.executable_path
        browser = p.chromium.launch(**launch_kwargs)
        try:
            ctx = browser.new_context(
                user_agent=("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                            "AppleWebKit/537.36 (KHTML, like Gecko) "
                            "Chrome/126.0.0.0 Safari/537.36"),
                viewport={"width": 1440, "height": 900},
                locale="en-AU",
            )
            page = ctx.new_page()
            for gender, url in cfg["sources"].items():
                print(f"Scraping {gender}: {url}")
                deals = scrape_gender(page, gender, url, cap)
                print(f"  -> {len(deals)} discounted products")
                all_deals.extend(deals)
        finally:
            browser.close()

    # Merge colour variants across pages (dedupe key strips ?color=).
    merged = {}
    for d in all_deals:
        key = dedupe_key(d["url"])
        prev = merged.get(key)
        if prev is None or d["saving"] > prev["saving"]:
            merged[key] = d
    deals = sorted(merged.values(),
                   key=lambda d: (-d["saving"], -d["discountPct"], d["name"]))

    if not deals:
        print("ERROR: no discounted products found — page may be blocked "
              "(Akamai 403) or the layout changed. Existing data files "
              "were NOT overwritten.", file=sys.stderr)
        return 1

    scanned_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    payload = {
        "scannedAt": scanned_at,
        "sources": cfg["sources"],
        "total": len(deals),
        "deals": deals,
    }
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    (DATA_DIR / "deals.json").write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    top10 = dict(payload, total=min(10, len(deals)), deals=deals[:10])
    (DATA_DIR / "top10.json").write_text(json.dumps(top10, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(deals)} deals; top saving A${deals[0]['saving']}: {deals[0]['name']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
