#!/usr/bin/env python3
"""
summarize.py — Run summary generation for all pending videos in TRACKER.md.

Usage:
    python3 tlt/scripts/summarize.py               # all pending, sequential
    python3 tlt/scripts/summarize.py --limit=3     # first 3 only
    python3 tlt/scripts/summarize.py --id=VIDEO_ID # specific video
    python3 tlt/scripts/summarize.py --dry-run     # show pending, don't run
    python3 tlt/scripts/summarize.py --parallel=4  # run 4 Claude calls at once
"""

import re, sys, json, time, subprocess, threading
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime

# ── Paths ──────────────────────────────────────────────────────────────────
BASE        = Path(__file__).resolve().parents[2]
TLT         = BASE / "tlt"
JSON_DIR    = TLT / "json-res"
SUMMARY_DIR = TLT / "processed" / "summaries"
TRACKER     = TLT / "TRACKER.md"

# ── Args ───────────────────────────────────────────────────────────────────
LIMIT      = 0
FILTER_ID  = None
DRY_RUN    = False
PARALLEL   = 1
for arg in sys.argv[1:]:
    if arg.startswith("--limit="):    LIMIT     = int(arg.split("=")[1])
    if arg.startswith("--id="):       FILTER_ID = arg.split("=")[1]
    if arg == "--dry-run":            DRY_RUN   = True
    if arg.startswith("--parallel="): PARALLEL  = int(arg.split("=")[1])

# ── Colors ─────────────────────────────────────────────────────────────────
GREEN  = "\033[0;32m"
YELLOW = "\033[1;33m"
RED    = "\033[0;31m"
BLUE   = "\033[0;34m"
CYAN   = "\033[0;36m"
GREY   = "\033[0;37m"
BOLD   = "\033[1m"
NC     = "\033[0m"

def ts():               return f"{GREY}[{datetime.now().strftime('%H:%M:%S')}]{NC}"
def tag_det(label):     return f"{GREY}[DET]{NC} {label}"
def tag_ai(label):      return f"{BLUE}[AI ]{NC} {label}"

# ── Thread-safe print with immediate flush ─────────────────────────────────
_print_lock = threading.Lock()

def tprint(msg=""):
    with _print_lock:
        print(msg, flush=True)

# ── Active jobs tracker (for live status line) ─────────────────────────────
_active_lock = threading.Lock()
_active_jobs = {}   # vid → {"title": ..., "started": time, "step": ...}

def job_start(vid, title):
    with _active_lock:
        _active_jobs[vid] = {"title": title, "started": time.time(), "step": "starting"}

def job_step(vid, step):
    with _active_lock:
        if vid in _active_jobs:
            _active_jobs[vid]["step"] = step

def job_end(vid):
    with _active_lock:
        _active_jobs.pop(vid, None)

def print_active_status():
    with _active_lock:
        if not _active_jobs: return
        lines = [f"\n  {CYAN}── Active jobs ──{NC}"]
        for vid, info in _active_jobs.items():
            elapsed = time.time() - info["started"]
            title   = info["title"][:42]
            step    = info["step"]
            lines.append(f"  {CYAN}⟳{NC} {title:<44} [{step}]  {elapsed:.0f}s elapsed")
        tprint("\n".join(lines))

# ── Step logger ────────────────────────────────────────────────────────────
class StepLog:
    def __init__(self, vid):
        self.vid   = vid
        self.steps = []

    def record(self, step, kind, duration_s, result, detail=""):
        self.steps.append({
            "step": step, "kind": kind,
            "duration": duration_s, "result": result, "detail": detail
        })

    def render(self):
        det_time = sum(s["duration"] for s in self.steps if s["kind"] == "DET")
        ai_time  = sum(s["duration"] for s in self.steps if s["kind"] == "AI")
        lines = []
        lines.append(f"\n  {GREY}{'Step':<30} {'Type':<5} {'Time':>7}  Result{NC}")
        lines.append(f"  {GREY}{'─'*62}{NC}")
        for s in self.steps:
            kind_label = f"{GREY}DET{NC}" if s["kind"] == "DET" else f"{BLUE}AI {NC}"
            result_sym = f"{GREEN}✓{NC}" if s["result"] else f"{RED}✗{NC}"
            detail     = f"  {GREY}{s['detail']}{NC}" if s["detail"] else ""
            lines.append(f"  {s['step']:<30} {kind_label}   {s['duration']:>5.1f}s  {result_sym}{detail}")
        lines.append(f"  {GREY}{'─'*62}{NC}")
        lines.append(f"  {GREY}DET: {det_time:.1f}s  |  AI: {ai_time:.1f}s  |  Total: {det_time+ai_time:.1f}s{NC}")
        return "\n".join(lines)

# ── Read TRACKER ───────────────────────────────────────────────────────────
def get_pending_from_file_ref():
    content = TRACKER.read_text()
    in_fr   = False
    pending = []

    # also build vid→title map from Video Tracker table
    title_map = {}
    in_vt = False
    for line in content.split("\n"):
        if line.strip() == "## Video Tracker": in_vt = True; continue
        if in_vt and line.strip() == "---": in_vt = False; continue
        if in_vt and re.match(r'^\|\s*\d+\s*\|', line):
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) >= 3:
                # col 2 = title, col 2 = json filename (contains vid)
                m = re.search(r'[A-Za-z0-9_-]{11}', parts[2])
                if m: title_map[m.group(0)] = parts[1]

    for line in content.split("\n"):
        if line.strip() == "## File Reference": in_fr = True; continue
        if in_fr and line.strip() == "---": break
        if in_fr and re.match(r'^\|\s*\d+\s*\|', line):
            parts = [p.strip() for p in line.split("|")[1:-1]]
            if len(parts) < 5: continue
            row_num = parts[0]
            vid_m   = re.match(r'`([A-Za-z0-9_-]{11})`', parts[1])
            if not vid_m: continue
            vid          = vid_m.group(1)
            summary_path = parts[4].strip()
            if summary_path.startswith("`processed/summaries/"):
                fname = summary_path.strip("`").replace("processed/summaries/", "")
                if not (SUMMARY_DIR / fname).exists():
                    title = title_map.get(vid, vid)
                    pending.append({"row": row_num, "vid": vid, "summary_file": fname, "title": title})
    return pending

# ── Find JSON ──────────────────────────────────────────────────────────────
def find_json(vid):
    for f in JSON_DIR.iterdir():
        if vid in f.name:
            return f
    return None

# ── Batch TRACKER update ───────────────────────────────────────────────────
_tracker_lock = threading.Lock()

def flush_tracker_updates(vids_done):
    with _tracker_lock:
        content = TRACKER.read_text()
        lines   = content.split("\n")
        in_vt   = False
        new     = []
        for line in lines:
            if line.strip() == "## Video Tracker": in_vt = True
            if in_vt and line.strip() == "---" and "Video Tracker" not in line: in_vt = False
            if in_vt and re.match(r'^\|', line):
                for vid in vids_done:
                    if vid in line:
                        parts = line.split("|")
                        if len(parts) >= 8:
                            parts[7] = " ✅ "
                            line = "|".join(parts)
                        break
            new.append(line)
        TRACKER.write_text("\n".join(new))

# ── Process one video ──────────────────────────────────────────────────────
def process_video(item, index, total):
    vid          = item["vid"]
    summary_file = item["summary_file"]
    row          = item["row"]
    title        = item.get("title", vid)
    short_title  = title[:48] if len(title) > 48 else title
    log          = StepLog(vid)

    job_start(vid, short_title)

    tprint(f"\n{'─'*56}")
    tprint(f"{ts()} {BOLD}[{index}/{total}]{NC} {CYAN}{short_title}{NC}")
    tprint(f"         {GREY}vid:{NC} {vid}  {GREY}row:{NC} {row}")
    tprint(f"         {GREY}out:{NC} {summary_file[:60]}")

    # ── Step A [DET]: Find JSON ────────────────────────────────────────────
    job_step(vid, "finding JSON")
    t         = time.time()
    json_file = find_json(vid)
    dur       = time.time() - t

    if not json_file:
        tprint(f"{ts()}   {RED}✗ [DET]{NC} JSON not found — skipping")
        log.record("Find JSON", "DET", dur, False, "file missing")
        tprint(log.render())
        job_end(vid)
        return {"vid": vid, "success": False, "log": log}

    tprint(f"{ts()}   {GREEN}✓ [DET]{NC} JSON found  {GREY}{json_file.name[:50]}{NC}  ({dur:.2f}s)")
    log.record("Find JSON", "DET", dur, True, json_file.name[:50])

    # ── Step B [DET]: Validate transcript ─────────────────────────────────
    job_step(vid, "reading transcript")
    t = time.time()
    try:
        data       = json.loads(json_file.read_text())
        transcript = data.get("transcript", {})
        has_tr     = transcript.get("available", False) and transcript.get("full_text")
        dur        = time.time() - t
        if has_tr:
            wc       = transcript.get("word_count", len(transcript["full_text"].split()))
            dur_secs = data.get("duration_seconds", 0)
            mins     = round(dur_secs / 60) if dur_secs else "?"
            tprint(f"{ts()}   {GREEN}✓ [DET]{NC} Transcript  {GREY}{wc:,} words / ~{mins} min video{NC}  ({dur:.2f}s)")
            log.record("Validate transcript", "DET", dur, True, f"{wc:,} words / ~{mins} min video")
        else:
            tprint(f"{ts()}   {YELLOW}→ [DET]{NC} No transcript — will use title + description  ({dur:.2f}s)")
            log.record("Validate transcript", "DET", dur, True, "unavailable")
    except Exception as e:
        dur = time.time() - t
        tprint(f"{ts()}   {RED}✗ [DET]{NC} JSON parse error: {e}")
        log.record("Validate transcript", "DET", dur, False, str(e))
        tprint(log.render())
        job_end(vid)
        return {"vid": vid, "success": False, "log": log}

    # ── Step C [AI]: Claude CLI ────────────────────────────────────────────
    job_step(vid, "Claude generating...")
    json_rel    = f"json-res/{json_file.name}"
    summary_rel = f"processed/summaries/{summary_file}"
    prompt      = (
        f"Read the file {json_rel} and generate a comprehensive educational summary "
        f"following the instructions in CLAUDE.md. Write the output to {summary_rel}."
    )
    tprint(f"{ts()}   {BLUE}… [AI ]{NC} Claude started  {GREY}→ {summary_rel[-50:]}{NC}")
    ai_start = time.time()

    result = subprocess.run(
        ["claude", "-p", prompt, "--allowedTools", "Read,Write",
         "--no-session-persistence", "--output-format", "text"],
        cwd=str(TLT), capture_output=True, text=True, stdin=subprocess.DEVNULL
    )
    dur = time.time() - ai_start

    if result.returncode == 0 and (SUMMARY_DIR / summary_file).exists():
        size_kb = (SUMMARY_DIR / summary_file).stat().st_size / 1024
        tprint(f"{ts()}   {GREEN}✓ [AI ]{NC} Summary done  {GREY}{size_kb:.1f}KB in {dur:.1f}s{NC}")
        log.record("Claude summary", "AI", dur, True, f"{size_kb:.1f}KB")
        tprint(log.render())
        job_end(vid)
        return {"vid": vid, "success": True, "log": log}
    else:
        tprint(f"{ts()}   {RED}✗ [AI ]{NC} Claude failed  ({dur:.1f}s)")
        if result.stderr:
            tprint(f"         {GREY}{result.stderr[:300]}{NC}")
        log.record("Claude summary", "AI", dur, False, result.stderr[:80] if result.stderr else "")
        tprint(log.render())
        job_end(vid)
        return {"vid": vid, "success": False, "log": log}

# ── Main ───────────────────────────────────────────────────────────────────
def main():
    mode = f"parallel={PARALLEL}" if PARALLEL > 1 else "sequential"

    print(f"\n{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{NC}", flush=True)
    print(f"{BOLD}  TLT Summary Runner  ·  {mode}{NC}", flush=True)
    print(f"{BOLD}  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{NC}", flush=True)
    print(f"{BOLD}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━{NC}\n", flush=True)

    t0      = time.time()
    pending = get_pending_from_file_ref()
    print(f"{ts()} {tag_det('Read TRACKER.md')}  ({time.time()-t0:.2f}s)  —  {len(pending)} pending", flush=True)

    if FILTER_ID: pending = [p for p in pending if p["vid"] == FILTER_ID]
    if LIMIT:     pending = pending[:LIMIT]

    if not pending:
        print(f"\n  {GREEN}All summaries up to date.{NC}\n", flush=True)
        return

    if DRY_RUN:
        print(f"\n  {YELLOW}Dry run — {len(pending)} videos, mode: {mode}{NC}", flush=True)
        for p in pending:
            print(f"    [{p['row']:>2}] {p['vid']}  {GREY}{p['title'][:45]}{NC}", flush=True)
        return

    # ── Batch banner ───────────────────────────────────────────────────────
    print(f"\n{CYAN}  Queued ({len(pending)} videos):{NC}", flush=True)
    for p in pending:
        print(f"  {GREY}[{p['row']:>2}]{NC} {p['vid']}  {p['title'][:50]}", flush=True)
    print(flush=True)

    # ── Run ────────────────────────────────────────────────────────────────
    wall_start  = time.time()
    session_log = []
    vids_done   = []
    total       = len(pending)

    if PARALLEL == 1:
        for i, item in enumerate(pending, 1):
            res = process_video(item, i, total)
            session_log.append(res)
            if res["success"]: vids_done.append(res["vid"])
    else:
        with ThreadPoolExecutor(max_workers=PARALLEL) as pool:
            futures = {pool.submit(process_video, item, i, total): item
                       for i, item in enumerate(pending, 1)}
            for f in as_completed(futures):
                res = f.result()
                session_log.append(res)
                if res["success"]: vids_done.append(res["vid"])
                # print active jobs status after each completion
                print_active_status()

    # ── Batch TRACKER update ───────────────────────────────────────────────
    if vids_done:
        t = time.time()
        flush_tracker_updates(vids_done)
        tprint(f"\n{ts()} {GREEN}✓ [DET]{NC} TRACKER updated — {len(vids_done)} rows flipped ✅  ({time.time()-t:.2f}s)")

    # ── Session summary ────────────────────────────────────────────────────
    wall_total = time.time() - wall_start
    processed  = sum(1 for e in session_log if e["success"])
    failed     = sum(1 for e in session_log if not e["success"])
    all_det    = sum(s["duration"] for e in session_log for s in e["log"].steps if s["kind"] == "DET")
    all_ai     = sum(s["duration"] for e in session_log for s in e["log"].steps if s["kind"] == "AI")

    print(f"\n{BOLD}{'━'*56}{NC}", flush=True)
    print(f"{BOLD}  Session Summary  ·  {datetime.now().strftime('%H:%M:%S')}{NC}", flush=True)
    print(f"{'━'*56}", flush=True)
    print(f"  {GREEN}✓ Processed : {processed}{NC}  |  {RED}✗ Failed : {failed}{NC}", flush=True)
    print(flush=True)

    # per-video result table
    print(f"  {GREY}{'Title':<46} {'Time':>7}  Size{NC}", flush=True)
    print(f"  {GREY}{'─'*62}{NC}", flush=True)
    for e in sorted(session_log, key=lambda x: x["vid"]):
        ai_steps = [s for s in e["log"].steps if s["kind"] == "AI"]
        ai_t     = ai_steps[0]["duration"] if ai_steps else 0
        detail   = ai_steps[0]["detail"] if ai_steps else "—"
        sym      = f"{GREEN}✓{NC}" if e["success"] else f"{RED}✗{NC}"
        title    = next((p["title"][:46] for p in pending if p["vid"] == e["vid"]), e["vid"])
        print(f"  {sym} {title:<46} {ai_t:>6.1f}s  {GREY}{detail}{NC}", flush=True)

    print(f"  {GREY}{'─'*62}{NC}", flush=True)
    print(flush=True)
    print(f"  Deterministic (script) : {all_det:.1f}s", flush=True)
    print(f"  Claude (AI) — total    : {all_ai:.1f}s", flush=True)
    print(f"  Wall clock             : {wall_total:.1f}s", end="", flush=True)
    if PARALLEL > 1 and wall_total > 0:
        speedup = all_ai / wall_total
        print(f"  →  {GREEN}{speedup:.1f}× speedup{NC} from parallel={PARALLEL}", end="", flush=True)
    print(flush=True)
    if all_det + all_ai > 0:
        print(f"  AI share               : {all_ai/(all_det+all_ai)*100:.0f}%", flush=True)
    print(f"{'━'*56}\n", flush=True)


if __name__ == "__main__":
    main()
