"""
build_preview.py
----------------
Scan pipeline outputs and emit a single self-contained HTML previewer at
tlt/preview/index.html (with a manifest.json sibling). One row per N2 slug,
columns/tabs per artifact (audio, video, N2 JSON, overview, summary, notes,
quiz, ...). Designed to grow as new pipeline nodes land — register new
artifact types in ARTIFACTS below.

Usage:
  python tlt/scripts/build_preview.py
  python -m http.server 8765 --directory .   # then open http://localhost:8765/tlt/preview/
"""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TLT = ROOT / "tlt"
PREVIEW_DIR = TLT / "preview"

# (label, kind, search roots+globs). Paths in manifest are RELATIVE TO REPO ROOT
# so the previewer can fetch them from a single http.server rooted at ROOT.
ARTIFACTS = [
    ("audio",    "audio", [(TLT / "audios",            "{slug}_full.mp3"),
                           (TLT / "audios",            "{slug}.mp3")]),
    ("video",    "video", [(ROOT / "remotion/outputs", "{slug}_full.mp4"),
                           (ROOT / "remotion/outputs", "{slug}.mp4")]),
    ("n2",       "json",  [(TLT / "n2",                "{slug}_n2.json")]),
    ("overview", "md",    [(TLT / "processed/overview","{slug}_*_summary.md")]),
    ("summary",  "md",    [(TLT / "processed/summary", "{slug}_*_summary.md")]),
    ("notes",    "md",    [(TLT / "processed/notes",   "{slug}_*_summary.md")]),
    ("quiz",     "json",  [(TLT / "processed/quiz",    "{slug}_*_quiz.json")]),
    ("yt-meta",  "json",  [(TLT / "processed/optimized_metadata", "{slug}_*.json")]),
    ("chapters", "json",  [(TLT / "processed/chapters", "{slug}_*.json")]),
    ("thumbnail","image", [(ROOT / "remotion/outputs", "{slug}_thumbnail.png")]),
]


def find_artifact(slug: str, roots):
    for root, pattern in roots:
        if not root.exists():
            continue
        matches = list(root.glob(pattern.format(slug=slug)))
        if matches:
            return matches[0].relative_to(ROOT).as_posix()
    return None


def discover_items():
    """Source of truth = N2 dir. Each *_n2.json is one item."""
    n2_dir = TLT / "n2"
    if not n2_dir.exists():
        return []
    items = []
    for p in sorted(n2_dir.glob("*_n2.json")):
        slug = p.stem.removesuffix("_n2")
        try:
            n2 = json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            continue
        item = {
            "slug": slug,
            "title": n2.get("title", slug),
            "source": n2.get("source", "?"),
            "language": n2.get("language", "?"),
            "duration_seconds": n2.get("duration_seconds", 0),
            "word_count": (n2.get("transcript") or {}).get("word_count", 0),
            "artifacts": {},
        }
        for label, kind, roots in ARTIFACTS:
            path = find_artifact(slug, roots)
            if path:
                item["artifacts"][label] = {"kind": kind, "path": path}
        items.append(item)
    return items


HTML = r"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>TLT Pipeline Preview</title>
<script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
<style>
  :root { --bg:#0f0f10; --panel:#1a1a1c; --line:#2a2a2e; --fg:#e8e8e8; --mut:#888; --acc:#ffb454; }
  * { box-sizing: border-box; }
  body { margin:0; font:14px -apple-system,BlinkMacSystemFont,sans-serif; background:var(--bg); color:var(--fg); display:flex; height:100vh; }
  #sidebar { width:300px; border-right:1px solid var(--line); overflow-y:auto; flex:none; }
  #sidebar h1 { font-size:13px; padding:14px 16px; margin:0; color:var(--mut); text-transform:uppercase; letter-spacing:.08em; border-bottom:1px solid var(--line); }
  .item { padding:12px 16px; cursor:pointer; border-bottom:1px solid var(--line); }
  .item:hover { background:var(--panel); }
  .item.active { background:var(--panel); border-left:3px solid var(--acc); padding-left:13px; }
  .item .t { font-weight:600; font-size:13px; line-height:1.3; }
  .item .m { color:var(--mut); font-size:11px; margin-top:4px; }
  #main { flex:1; display:flex; flex-direction:column; min-width:0; }
  #tabs { display:flex; gap:0; border-bottom:1px solid var(--line); background:var(--panel); overflow-x:auto; }
  .tab { padding:10px 16px; cursor:pointer; color:var(--mut); border-bottom:2px solid transparent; white-space:nowrap; font-size:13px; }
  .tab:hover { color:var(--fg); }
  .tab.active { color:var(--acc); border-bottom-color:var(--acc); }
  .tab.missing { opacity:.35; cursor:not-allowed; }
  #view { flex:1; overflow:auto; padding:24px; }
  audio, video { max-width:100%; background:#000; border-radius:6px; }
  video { max-height:70vh; }
  pre { background:var(--panel); padding:16px; border-radius:6px; overflow:auto; font:12px ui-monospace,monospace; }
  .md { max-width:780px; line-height:1.65; }
  .md h1, .md h2, .md h3 { color:var(--acc); margin-top:1.5em; }
  .md h1 { font-size:22px; } .md h2 { font-size:18px; } .md h3 { font-size:15px; }
  .md hr { border:none; border-top:1px solid var(--line); margin:1.5em 0; }
  .md code { background:var(--panel); padding:2px 6px; border-radius:3px; font-size:12px; }
  .md pre code { background:none; padding:0; }
  .md blockquote { border-left:3px solid var(--acc); padding-left:12px; color:var(--mut); margin:0; }
  .empty { color:var(--mut); padding:40px; text-align:center; }
  .pathline { color:var(--mut); font-size:11px; margin-bottom:14px; font-family:ui-monospace,monospace; }
</style>
</head>
<body>
<div id="sidebar"><h1>Pipeline items (<span id="count">0</span>)</h1><div id="list"></div></div>
<div id="main">
  <div id="tabs"></div>
  <div id="view"><div class="empty">Select an item from the left.</div></div>
</div>
<script>
let ARTIFACT_ORDER = [], manifest = [], current = null, currentTab = null;

async function load() {
  const data = await (await fetch('manifest.json')).json();
  manifest = data.items;
  ARTIFACT_ORDER = data.artifact_order;
  const list = document.getElementById('list');
  document.getElementById('count').textContent = manifest.length;
  manifest.forEach((it, i) => {
    const el = document.createElement('div');
    el.className = 'item';
    el.innerHTML = `<div class="t">${escapeHtml(it.title)}</div>
      <div class="m">${it.source} · ${it.duration_seconds}s · ${it.word_count} words</div>`;
    el.onclick = () => select(i);
    list.appendChild(el);
  });
  if (manifest.length) select(0);
}

function select(i) {
  current = manifest[i];
  document.querySelectorAll('.item').forEach((el, j) => el.classList.toggle('active', j===i));
  const tabs = document.getElementById('tabs');
  tabs.innerHTML = '';
  const available = ARTIFACT_ORDER.filter(k => current.artifacts[k]);
  ARTIFACT_ORDER.forEach(k => {
    const has = !!current.artifacts[k];
    const t = document.createElement('div');
    t.className = 'tab' + (has ? '' : ' missing');
    t.textContent = k;
    if (has) t.onclick = () => showTab(k);
    tabs.appendChild(t);
  });
  if (available.length) showTab(available[0]);
  else document.getElementById('view').innerHTML = '<div class="empty">No artifacts for this item yet.</div>';
}

async function showTab(k) {
  currentTab = k;
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.textContent===k));
  const view = document.getElementById('view');
  const a = current.artifacts[k];
  const url = '../../' + a.path;  // preview/index.html → repo root
  const pathLine = `<div class="pathline">${a.path}</div>`;
  if (a.kind === 'audio')      view.innerHTML = pathLine + `<audio src="${url}" controls></audio>`;
  else if (a.kind === 'video') view.innerHTML = pathLine + `<video src="${url}" controls></video>`;
  else if (a.kind === 'image') view.innerHTML = pathLine + `<img src="${url}" style="max-width:100%;border-radius:6px;">`;
  else if (a.kind === 'json') {
    const txt = await (await fetch(url)).text();
    let pretty; try { pretty = JSON.stringify(JSON.parse(txt), null, 2); } catch { pretty = txt; }
    view.innerHTML = pathLine + `<pre>${escapeHtml(pretty)}</pre>`;
  } else if (a.kind === 'md') {
    const txt = await (await fetch(url)).text();
    view.innerHTML = pathLine + `<div class="md">${marked.parse(txt)}</div>`;
  }
}

function escapeHtml(s) { return s.replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c])); }
load();
</script>
</body>
</html>
"""


def main():
    PREVIEW_DIR.mkdir(parents=True, exist_ok=True)
    items = discover_items()
    payload = {
        "artifact_order": [label for label, _, _ in ARTIFACTS],
        "items": items,
    }
    (PREVIEW_DIR / "manifest.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (PREVIEW_DIR / "index.html").write_text(HTML, encoding="utf-8")
    print(f"✓ {len(items)} items")
    for it in items:
        present = ", ".join(it["artifacts"].keys()) or "(no artifacts)"
        print(f"  · {it['slug']:<55} [{present}]")
    print(f"\nopen: cd {ROOT} && python3 -m http.server 8765 → http://localhost:8765/tlt/preview/")


if __name__ == "__main__":
    main()
