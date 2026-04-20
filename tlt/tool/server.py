"""
FRIDAY TVA Console — local web tool for audio → Hinglish pipeline.

Pipeline (fast mode, no render):
  N1 trim (ffmpeg)
  N2 groq whisper (context-aware prompt + validation + 1x retry)
  N3 claude haiku hinglish transliteration

Run:
  export GROQ_API_KEY=...
  export ANTHROPIC_API_KEY=...
  .venv/bin/python tlt/tool/server.py
  → http://localhost:8765
"""
import asyncio
import json
import os
import re
import subprocess
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, UploadFile, Form, File
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse, FileResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent.parent
TOOL_DIR = Path(__file__).parent
STATIC_DIR = TOOL_DIR / "static"
WORK_DIR = TOOL_DIR / "jobs"
WORK_DIR.mkdir(parents=True, exist_ok=True)

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
FORM_LABEL = {
    "poem": "कविता", "novel": "उपन्यास", "short story": "कहानी",
    "essay": "निबंध", "theory": "साहित्यिक सिद्धांत", "play": "नाटक",
}

app = FastAPI()
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

JOBS: dict[str, dict] = {}  # job_id → {queue, result, done}


# ---- pipeline helpers -----------------------------------------------------
def build_prompt(ctx: dict, tighter: bool = False) -> str:
    form_hi = FORM_LABEL.get(ctx.get("form", "").lower(), "पाठ")
    title = ctx["title"]; author = ctx["author"]
    nouns = (ctx.get("nouns") or "").strip()
    noun_list = [n.strip() for n in nouns.split(",") if n.strip()] if nouns else []
    if tighter:
        return ("यह हिंदी और अंग्रेजी मिक्स साहित्य व्याख्यान है। "
                f"{form_hi}: {title}, लेखक {author}। उर्दू शब्द भी मौजूद हैं।")
    nouns_clause = ""
    if noun_list:
        nouns_clause = " " + ", ".join(noun_list[:4]) + " जैसे नाम आते हैं।"
    return ("यह हिंदी और अंग्रेजी मिक्स साहित्य व्याख्यान है। "
            f"{form_hi}: {title}, लेखक {author}।"
            f"{nouns_clause}"
            " उर्दू शब्द भी मौजूद हैं।")


def trim_audio(src: Path, start: int, duration: int, out: Path):
    cmd = ["ffmpeg", "-y", "-ss", str(start), "-t", str(duration), "-i", str(src), "-c", "copy", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        cmd = ["ffmpeg", "-y", "-ss", str(start), "-t", str(duration), "-i", str(src),
               "-c:a", "libmp3lame", "-b:a", "128k", str(out)]
        r = subprocess.run(cmd, capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {r.stderr[-300:]}")


def call_groq(audio: Path, prompt: str, model: str = "whisper-large-v3") -> dict:
    from groq import Groq
    key = os.environ.get("GROQ_API_KEY")
    if not key:
        raise RuntimeError("GROQ_API_KEY not set in server environment")
    client = Groq(api_key=key)
    with open(audio, "rb") as f:
        resp = client.audio.transcriptions.create(
            file=(audio.name, f.read()),
            model=model, language="hi", prompt=prompt,
            response_format="verbose_json",
            timestamp_granularities=["word", "segment"],
        )
    return resp.model_dump() if hasattr(resp, "model_dump") else json.loads(resp.model_dump_json())


def validate(data: dict, ctx: dict, duration: int) -> tuple[bool, list[str], dict]:
    issues = []
    text = data.get("text", "") or ""
    words = data.get("words") or []
    metrics = {}
    if ctx["title"].lower() not in text.lower():
        issues.append(f"title '{ctx['title']}' not found")
    non_space = re.sub(r"\s+", "", text)
    ratio = 0.0
    if non_space:
        ratio = len(DEVANAGARI_RE.findall(non_space)) / len(non_space)
    metrics["devanagari_ratio"] = round(ratio, 3)
    if ratio < 0.20:
        issues.append(f"Devanagari ratio too low ({ratio:.1%})")
    metrics["word_count"] = len(words)
    min_expected = max(10, int(duration * 1.3))
    metrics["min_expected_words"] = min_expected
    if len(words) < min_expected:
        issues.append(f"too few words ({len(words)} < {min_expected})")
    return (len(issues) == 0, issues, metrics)


def call_claude_hinglish(words: list[dict], nouns: str) -> list[dict]:
    import anthropic
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in server environment")
    client = anthropic.Anthropic(api_key=key)
    payload = "\n".join(f"{i}|{w['word']}" for i, w in enumerate(words))
    sys_extra = (f"6. Known proper nouns (use these spellings if you see a mangled match): {nouns}\n"
                 if nouns else "")
    msg = client.messages.create(
        model="claude-haiku-4-5-20251001", max_tokens=4096,
        system=("You transliterate Devanagari Hindi tokens to Hinglish (Latin-script).\n"
                "1. Preserve sound.\n"
                "2. English words already spoken in English stay English.\n"
                "3. One output per input, same index.\n"
                "4. Format: INDEX|hinglish.\n"
                "5. No extra text.\n" + sys_extra),
        messages=[{"role": "user", "content": "Convert:\n" + payload}],
    )
    out = {}
    for line in msg.content[0].text.strip().splitlines():
        if "|" in line:
            i, t = line.split("|", 1)
            try: out[int(i.strip())] = t.strip()
            except: pass
    return [
        {"word": out.get(i, w["word"]), "start": float(w["start"]), "end": float(w["end"])}
        for i, w in enumerate(words)
    ]


# ---- SSE emitter ----------------------------------------------------------
async def emit(job_id: str, event: str, data: dict):
    q = JOBS[job_id]["queue"]
    await q.put({"event": event, "data": data, "ts": time.strftime("%H:%M:%S")})


def emit_sync(job_id: str, event: str, data: dict):
    loop = JOBS[job_id]["loop"]
    asyncio.run_coroutine_threadsafe(emit(job_id, event, data), loop)


# ---- background pipeline --------------------------------------------------
def run_pipeline_sync(job_id: str, audio_path: Path, ctx: dict, start: int, duration: int, skip_hinglish: bool = False):
    job_dir = WORK_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)

    try:
        # N1: trim
        emit_sync(job_id, "step", {"id": "N1", "status": "running", "title": "Trim audio"})
        clip = job_dir / f"{ctx['slug']}_{duration}s.mp3"
        trim_audio(audio_path, start, duration, clip)
        size_kb = clip.stat().st_size / 1024
        emit_sync(job_id, "step", {"id": "N1", "status": "ok", "detail": f"{clip.name} · {size_kb:.1f} KB"})

        # N2: groq (with retry)
        prompt = build_prompt(ctx, tighter=False)
        emit_sync(job_id, "step", {"id": "N2", "status": "running", "title": "Groq Whisper",
                                   "detail": f"prompt: {prompt}"})
        data = call_groq(clip, prompt)
        ok, issues, metrics = validate(data, ctx, duration)
        retried = False
        if not ok:
            emit_sync(job_id, "log", {"msg": f"validation failed: {issues} — retrying"})
            prompt = build_prompt(ctx, tighter=True)
            data = call_groq(clip, prompt)
            ok, issues, metrics = validate(data, ctx, duration)
            retried = True
        data["_prompt_used"] = prompt
        data["_context"] = ctx
        data["_retry"] = retried
        data["_validation"] = {"ok": ok, "issues": issues, "metrics": metrics}
        (job_dir / "groq.json").write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        emit_sync(job_id, "step", {
            "id": "N2", "status": "ok" if ok else "warn",
            "detail": f"{metrics.get('word_count', 0)} words · Devanagari {metrics.get('devanagari_ratio', 0):.1%} · retry={retried}",
            "text": data.get("text", ""),
            "prompt": prompt,
        })

        # N3: hinglish (optional)
        hinglish_words, hinglish_text = [], ""
        if skip_hinglish:
            emit_sync(job_id, "step", {"id": "N3", "status": "warn", "detail": "skipped (Groq-only mode)"})
        else:
            emit_sync(job_id, "step", {"id": "N3", "status": "running", "title": "Claude Hinglish"})
            hinglish_words = call_claude_hinglish(data.get("words") or [], ctx.get("nouns") or "")
            hinglish_text = " ".join(w["word"] for w in hinglish_words)
            (job_dir / "hinglish.json").write_text(
                json.dumps({"words": hinglish_words, "text": hinglish_text, "context": ctx},
                           ensure_ascii=False, indent=2), encoding="utf-8")
            emit_sync(job_id, "step", {
                "id": "N3", "status": "ok",
                "detail": f"{len(hinglish_words)} tokens transliterated",
                "text": hinglish_text,
            })

        result = {
            "job_id": job_id,
            "context": ctx,
            "groq": {
                "words": data.get("words") or [],
                "text": data.get("text", ""),
                "duration": data.get("duration"),
                "language": data.get("language"),
                "prompt": prompt,
                "validation": data["_validation"],
                "retry": retried,
            },
            "hinglish": {"words": hinglish_words, "text": hinglish_text},
            "files": {
                "clip": str(clip.relative_to(ROOT)),
                "groq_json": str((job_dir / "groq.json").relative_to(ROOT)),
                "hinglish_json": str((job_dir / "hinglish.json").relative_to(ROOT)),
            },
        }
        JOBS[job_id]["result"] = result
        emit_sync(job_id, "done", {"result": result})
    except Exception as e:
        emit_sync(job_id, "error", {"message": str(e)})
    finally:
        JOBS[job_id]["done"] = True


# ---- routes ---------------------------------------------------------------
@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/tracker")
async def tracker():
    return FileResponse(STATIC_DIR / "tracker.html")


@app.get("/api/jobs")
async def api_jobs():
    out = []
    for d in sorted(WORK_DIR.iterdir(), key=lambda p: p.stat().st_mtime, reverse=True):
        if not d.is_dir():
            continue
        groq_p = d / "groq.json"
        hing_p = d / "hinglish.json"
        row = {
            "job_id": d.name,
            "ts": d.stat().st_mtime,
            "has_groq": groq_p.exists(),
            "has_hinglish": hing_p.exists(),
        }
        if groq_p.exists():
            try:
                g = json.loads(groq_p.read_text())
                ctx = g.get("_context") or {}
                val = g.get("_validation") or {}
                row.update({
                    "slug": ctx.get("slug"),
                    "title": ctx.get("title"),
                    "author": ctx.get("author"),
                    "form": ctx.get("form"),
                    "duration": g.get("duration"),
                    "word_count": len(g.get("words") or []),
                    "devanagari_ratio": (val.get("metrics") or {}).get("devanagari_ratio"),
                    "validation_ok": val.get("ok"),
                    "retry": g.get("_retry"),
                    "text_preview": (g.get("text") or "")[:200],
                    "text_full": g.get("text") or "",
                    "prompt_used": g.get("_prompt_used") or "",
                })
            except Exception as e:
                row["error"] = str(e)
        out.append(row)
    return out


@app.post("/run")
async def run(
    audio: UploadFile = File(...),
    slug: str = Form(...),
    title: str = Form(...),
    author: str = Form(...),
    form: str = Form(...),
    nouns: str = Form(""),
    start: int = Form(0),
    duration: int = Form(60),
    groq_only: str = Form(""),
):
    job_id = uuid.uuid4().hex[:10]
    job_dir = WORK_DIR / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    # save upload
    src = job_dir / ("upload" + Path(audio.filename or "").suffix)
    src.write_bytes(await audio.read())
    ctx = {"slug": slug, "title": title, "author": author, "form": form, "nouns": nouns}
    loop = asyncio.get_event_loop()
    JOBS[job_id] = {"queue": asyncio.Queue(), "result": None, "done": False, "loop": loop}
    skip_hinglish = bool(groq_only)
    loop.run_in_executor(None, run_pipeline_sync, job_id, src, ctx, start, duration, skip_hinglish)
    return {"job_id": job_id, "groq_only": skip_hinglish}


@app.get("/stream/{job_id}")
async def stream(job_id: str):
    if job_id not in JOBS:
        return JSONResponse({"error": "unknown job"}, status_code=404)
    job = JOBS[job_id]

    async def gen():
        yield f"event: hello\ndata: {json.dumps({'job_id': job_id})}\n\n"
        while True:
            try:
                evt = await asyncio.wait_for(job["queue"].get(), timeout=30.0)
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"
                if job["done"] and job["queue"].empty():
                    break
                continue
            payload = json.dumps(evt, ensure_ascii=False)
            yield f"event: {evt['event']}\ndata: {payload}\n\n"
            if evt["event"] in ("done", "error"):
                break

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.get("/result/{job_id}")
async def result(job_id: str):
    if job_id not in JOBS:
        return JSONResponse({"error": "unknown job"}, status_code=404)
    return JOBS[job_id].get("result") or {"pending": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="info")
