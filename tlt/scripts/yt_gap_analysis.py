"""
yt_gap_analysis.py
------------------
Competitor gap analysis for TLT videos using DataForSEO YouTube SERP API.

For each TLT video:
  1. Derives a search keyword from the video title
  2. Hits DataForSEO YouTube SERP → top 10 results
  3. Scores competitor weakness (low views + old upload = weak = opportunity)
  4. Checks if TLT is already ranking in top 10
  5. Outputs a ranked opportunity report

Opportunity score (0-100):
  - High search result views avg → lower score (strong competition)
  - Low result views avg → higher score (weak competition = gap)
  - TLT already ranking #1-3 → skip (already winning)
  - TLT not ranking at all → bonus points (untapped)

Usage:
  python3 tlt/scripts/yt_gap_analysis.py
  python3 tlt/scripts/yt_gap_analysis.py --limit 10   # test on 10 videos
  python3 tlt/scripts/yt_gap_analysis.py --out tlt/reports/gap_report.md
"""

import argparse
import json
import math
import os
import time
import urllib.request
from pathlib import Path
from datetime import datetime

ROOT        = Path(__file__).parent.parent.parent
JSON_DIR    = ROOT / "tlt" / "json-res"
REPORTS_DIR = ROOT / "tlt" / "reports"

TOKEN = os.environ.get("DATAFORSEO_TOKEN", "bmlzaGNoYXkuc290MDEwMDc3QHB3aW9pLmNvbToyMjg1MzAwMzIyZmNlMTUy")
API_URL = "https://api.dataforseo.com/v3/serp/youtube/organic/live/advanced"

TLT_CHANNEL_NAMES = {"the literature talks", "literature tops", "theliteraturetalks"}

# ── Keyword derivation ────────────────────────────────────────────────────────

def derive_keyword(title: str) -> str:
    """Strip channel branding noise and derive a clean search keyword from title."""
    import re
    # Remove common TLT suffixes/prefixes
    title = re.sub(r'\|.*$', '', title)          # drop everything after |
    title = re.sub(r'part\s*\d+', '', title, flags=re.I)
    title = re.sub(r'class\s*(\d+)', r'class \1', title, flags=re.I)
    title = re.sub(r'[^\w\s]', '', title)        # remove punctuation
    title = re.sub(r'\s+', ' ', title).strip()
    words = title.split()[:8]                    # max 8 words
    keyword = ' '.join(words).lower()
    # Append "hindi explanation" if not already there — matches Indian search intent
    if 'hindi' not in keyword and 'explanation' not in keyword:
        keyword += ' explanation hindi'
    return keyword


# ── DataForSEO call ───────────────────────────────────────────────────────────

def fetch_serp(keyword: str) -> list[dict]:
    payload = json.dumps([{
        "keyword": keyword,
        "location_code": 2356,   # India
        "language_code": "en",
        "device": "desktop",
        "block_depth": 10,
    }]).encode()

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={"Authorization": "Basic " + TOKEN, "Content-Type": "application/json"},
    )
    resp = urllib.request.urlopen(req, timeout=30)
    data = json.loads(resp.read())

    if data.get("status_code") != 20000:
        raise RuntimeError(f"API error: {data.get('status_message')}")

    items = data["tasks"][0]["result"][0].get("items", [])
    return [i for i in items if i.get("type") == "youtube_video"]


# ── Opportunity scoring ───────────────────────────────────────────────────────

def score_opportunity(results: list[dict], tlt_video_id: str) -> dict:
    """
    Returns:
      tlt_rank       : int | None  (1-indexed, None if not in top 10)
      top3_avg_views : int
      opportunity    : int  (0-100, higher = bigger gap = more opportunity)
      gap_reason     : str
    """
    if not results:
        return {"tlt_rank": None, "top3_avg_views": 0, "opportunity": 50, "gap_reason": "No results found"}

    tlt_rank = None
    for i, r in enumerate(results):
        vid_id = r.get("video_id", "")
        channel = r.get("channel_name", "").lower()
        if vid_id == tlt_video_id or any(name in channel for name in TLT_CHANNEL_NAMES):
            tlt_rank = i + 1
            break

    # Top 3 competitor average views (excluding TLT)
    competitor_views = [
        r.get("views_count", 0) or 0
        for r in results[:5]
        if r.get("video_id") != tlt_video_id
        and not any(name in (r.get("channel_name") or "").lower() for name in TLT_CHANNEL_NAMES)
    ][:3]

    top3_avg = int(sum(competitor_views) / len(competitor_views)) if competitor_views else 0

    # Score: lower competitor views = higher opportunity
    # 0-1k views avg    → 90-100 (gold mine)
    # 1k-10k            → 70-90  (strong gap)
    # 10k-50k           → 50-70  (moderate)
    # 50k-200k          → 30-50  (competitive)
    # 200k+             → 0-30   (saturated)
    if top3_avg == 0:
        base_score = 85
    elif top3_avg < 1000:
        base_score = 90
    elif top3_avg < 10000:
        base_score = int(90 - (math.log10(top3_avg) - 3) * 20)
    elif top3_avg < 50000:
        base_score = int(70 - (math.log10(top3_avg) - 4) * 20)
    elif top3_avg < 200000:
        base_score = int(50 - (math.log10(top3_avg) - 4.7) * 15)
    else:
        base_score = max(0, int(30 - math.log10(top3_avg) * 3))

    # Bonus: TLT not ranking → untapped
    if tlt_rank is None:
        base_score = min(100, base_score + 10)
        gap_reason = f"TLT not in top 10 — competitors avg {top3_avg:,} views"
    elif tlt_rank <= 3:
        base_score = max(0, base_score - 30)  # already winning, less urgent
        gap_reason = f"TLT ranks #{tlt_rank} — already competitive"
    else:
        gap_reason = f"TLT ranks #{tlt_rank} — can be pushed higher"

    return {
        "tlt_rank": tlt_rank,
        "top3_avg_views": top3_avg,
        "opportunity": max(0, min(100, base_score)),
        "gap_reason": gap_reason,
    }


# ── Main ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="Limit to N videos (for testing)")
    parser.add_argument("--out", type=str, default=None, help="Output markdown file path")
    parser.add_argument("--from-cache", type=str, default=None, help="Skip API calls, reformat from saved JSON results file")
    args = parser.parse_args()

    # ── Load from cache or hit API ─────────────────────────────────────────────
    if args.from_cache:
        cache_path = Path(args.from_cache)
        with open(cache_path) as f:
            results_all = json.load(f)
        slugs = results_all  # for count display
        total_cost = 0.0
        print(f"Loaded {len(results_all)} results from cache: {cache_path}\n")
        results_all.sort(key=lambda x: x.get("opportunity", 0), reverse=True)
    else:
        slugs = sorted(JSON_DIR.glob("*.json"))
        if args.limit:
            slugs = slugs[:args.limit]

        print(f"Running gap analysis on {len(slugs)} TLT videos...\n")

        results_all = []
        total_cost = 0.002 * len(slugs)  # $0.002 per call

        # Cache file — written after every single item so a crash loses nothing
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)
        cache_out = REPORTS_DIR / f"gap_results_{datetime.now().strftime('%Y-%m-%d')}.json"

        for i, path in enumerate(slugs):
            with open(path) as f:
                data = json.load(f)

            title    = data.get("title", path.stem)
            video_id = data.get("video_id", "")
            keyword  = derive_keyword(title)

            print(f"[{i+1}/{len(slugs)}] {title[:55]}")
            print(f"         Keyword: {keyword}")

            try:
                serp = fetch_serp(keyword)
                score = score_opportunity(serp, video_id)

                top_competitor = next(
                    (r for r in serp if r.get("video_id") != video_id
                     and not any(n in (r.get("channel_name") or "").lower() for n in TLT_CHANNEL_NAMES)),
                    None
                )

                results_all.append({
                    "title":           title,
                    "video_id":        video_id,
                    "keyword":         keyword,
                    "tlt_rank":        score["tlt_rank"],
                    "top3_avg_views":  score["top3_avg_views"],
                    "opportunity":     score["opportunity"],
                    "gap_reason":      score["gap_reason"],
                    "top_competitor":  top_competitor.get("channel_name", "?") if top_competitor else "?",
                    "top_comp_views":  top_competitor.get("views_count", 0) if top_competitor else 0,
                    "top_comp_title":  top_competitor.get("title", "")[:65] if top_competitor else "",
                })

                print(f"         Score: {score['opportunity']}/100 — {score['gap_reason']}")

            except Exception as e:
                print(f"         ERROR: {e}")
                results_all.append({"title": title, "video_id": video_id, "keyword": keyword,
                                     "opportunity": 0, "gap_reason": f"Error: {e}"})

            # Write cache immediately after every item — crash-safe
            cache_out.write_text(json.dumps(results_all, ensure_ascii=False, indent=2))

            time.sleep(0.5)  # rate limiting
            print()

        results_all.sort(key=lambda x: x.get("opportunity", 0), reverse=True)
        cache_out.write_text(json.dumps(results_all, ensure_ascii=False, indent=2))
        print(f"Raw results cached → {cache_out}")

    # ── Report ────────────────────────────────────────────────────────────────
    def clean(s: str, maxlen: int = 60) -> str:
        """Strip pipes (break markdown tables) and truncate."""
        return s.replace("|", "-").strip()[:maxlen]

    def action_label(r: dict) -> str:
        rank = r.get("tlt_rank")
        score = r.get("opportunity", 0)
        if rank is None:
            return "Upload / re-title to enter SERP"
        elif rank <= 3:
            return "Already winning — maintain"
        elif rank <= 10:
            return "Optimise title + thumbnail to reach top 3"
        else:
            return f"Ranking #{rank} — fix title & description"

    lines = [
        "# TLT YouTube Gap Analysis",
        f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')} · Videos analysed: {len(slugs)} · Est. cost: ${total_cost:.2f}",
        "",
        "**Score guide:** 80-100 = gold mine (weak competition), 60-79 = strong gap, 40-59 = moderate, <40 = saturated",
        "",
        "## Top 20 Opportunities",
        "",
        "| # | Score | TLT Rank | Comp Avg Views | Action | Video |",
        "|---|-------|----------|----------------|--------|-------|",
    ]

    for i, r in enumerate(results_all[:20]):
        rank_str = f"#{r['tlt_rank']}" if r.get("tlt_rank") else "Not ranking"
        title = clean(r['title'], 55)
        action = action_label(r)
        lines.append(
            f"| {i+1} | **{r.get('opportunity', 0)}/100** | {rank_str} | "
            f"{r.get('top3_avg_views', 0):,} | {action} | {title} |"
        )

    lines += ["", "---", "", "## Full Detail — Top 10 Opportunities", ""]

    for i, r in enumerate(results_all[:10]):
        rank_str = f"#{r['tlt_rank']}" if r.get("tlt_rank") else "Not in top 10"
        score = r.get("opportunity", 0)
        comp_views = r.get("top3_avg_views", 0)

        if score >= 80:
            tier = "GOLD MINE"
        elif score >= 60:
            tier = "STRONG GAP"
        elif score >= 40:
            tier = "MODERATE"
        else:
            tier = "SATURATED"

        lines += [
            f"### {i+1}. {r['title'][:80]}",
            f"**[{tier}]** · Score: {score}/100 · TLT rank: {rank_str} · Competitor avg views: {comp_views:,}",
            "",
            f"- **Search keyword used:** `{r['keyword']}`",
            f"- **Why it's a gap:** {r.get('gap_reason', '')}",
            f"- **Recommended action:** {action_label(r)}",
            f"- **Top competitor:** {r.get('top_competitor', '?')} — *\"{r.get('top_comp_title', '')}\"* ({r.get('top_comp_views', 0):,} views)",
            "",
        ]

    lines += [
        "---",
        "",
        "## Deprioritise — Saturated Topics",
        "",
        "| Video | Competitor Avg Views | Reason |",
        "|-------|---------------------|--------|",
    ]

    for r in results_all[-10:]:
        if r.get("opportunity", 0) < 25:
            lines.append(
                f"| {clean(r['title'], 50)} | {r.get('top3_avg_views', 0):,} | {r.get('gap_reason', '')} |"
            )

    report = "\n".join(lines)
    print("\n" + "="*60)
    print(report[:3000])

    # Write to file
    out_path = Path(args.out) if args.out else REPORTS_DIR / f"gap_report_{datetime.now().strftime('%Y-%m-%d')}.md"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report, encoding="utf-8")
    print(f"\nFull report → {out_path}")


if __name__ == "__main__":
    main()
