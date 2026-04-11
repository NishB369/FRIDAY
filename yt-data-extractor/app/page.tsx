"use client";

import { useState } from "react";

type Comment = { author: string; text: string; likes: number; published_at: string; reply_count: number };
type Result = {
  video_id: string;
  url: string;
  title: string;
  channel: string;
  description: string;
  published_at: string;
  duration_seconds: number;
  thumbnail: string;
  tags: string[];
  view_count: number;
  like_count: number;
  comment_count: number;
  language: string | null;
  comments: Comment[];
  transcript: {
    available: boolean;
    word_count: number;
    full_text: string | null;
  };
};

function fmt(n: number) {
  if (n >= 1_000_000) return (n / 1_000_000).toFixed(1) + "M";
  if (n >= 1_000) return (n / 1_000).toFixed(1) + "K";
  return n.toString();
}

function fmtDur(s: number) {
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  const sec = s % 60;
  if (h > 0) return `${h}:${String(m).padStart(2, "0")}:${String(sec).padStart(2, "0")}`;
  return `${m}:${String(sec).padStart(2, "0")}`;
}

export default function Home() {
  const [url, setUrl] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<Result | null>(null);
  const [error, setError] = useState("");
  const [activeTab, setActiveTab] = useState<"overview" | "transcript" | "comments" | "json">("overview");
  const [copied, setCopied] = useState(false);

  async function extract() {
    if (!url.trim()) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch("/api/extract", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url: url.trim() }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.error || "Something went wrong"); return; }
      setResult(data);
      setActiveTab("overview");
    } catch {
      setError("Network error — please try again");
    } finally {
      setLoading(false);
    }
  }

  function copyJson() {
    if (!result) return;
    navigator.clipboard.writeText(JSON.stringify(result, null, 2));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const tabs = ["overview", "transcript", "comments", "json"] as const;

  return (
    <main className="min-h-screen bg-[#0a0a0a] text-[#e8e8e8]" style={{ fontFamily: "system-ui, sans-serif" }}>
      <nav className="border-b border-white/5 px-8 py-4 flex items-center justify-between">
        <div className="font-mono text-xs tracking-[3px] text-[#555] uppercase">YT Data Extractor</div>
        <div className="font-mono text-xs text-[#333] border border-white/5 px-3 py-1 rounded">
          metadata · transcript · comments
        </div>
      </nav>

      <div className="max-w-4xl mx-auto px-6 py-16">
        {!result && (
          <div className="text-center mb-12">
            <div className="text-5xl font-light text-white mb-3 tracking-tight">Extract YouTube Data</div>
            <p className="text-[#555] text-sm">Paste any YouTube URL — get metadata, transcript and comments as JSON</p>
          </div>
        )}

        <div className={`flex gap-3 ${result ? "mb-8" : "mb-4"}`}>
          <input
            value={url}
            onChange={(e) => setUrl(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && extract()}
            placeholder="https://youtube.com/watch?v=..."
            className="flex-1 bg-[#111] border border-white/[0.08] text-[#e8e8e8] px-4 py-3 rounded-lg text-sm outline-none focus:border-[#7c6aff]/60 placeholder:text-[#444] transition-colors"
          />
          <button
            onClick={extract}
            disabled={loading}
            className="bg-[#7c6aff] hover:bg-[#6a58e8] disabled:opacity-40 text-white px-6 py-3 rounded-lg text-sm font-medium transition-colors whitespace-nowrap cursor-pointer"
          >
            {loading ? "Extracting..." : "Extract"}
          </button>
        </div>

        {error && (
          <div className="bg-red-500/10 border border-red-500/20 text-red-400 px-4 py-3 rounded-lg text-sm mb-6">
            {error}
          </div>
        )}

        {loading && (
          <div className="text-center py-20 text-[#444] text-sm">
            <div className="inline-block w-5 h-5 border-2 border-white/10 border-t-[#7c6aff] rounded-full animate-spin mb-4" />
            <div>Fetching metadata, transcript and comments...</div>
          </div>
        )}

        {result && (
          <div>
            {/* Video card */}
            <div className="flex gap-5 mb-6 p-5 bg-[#111] border border-white/5 rounded-xl">
              {result.thumbnail && (
                <img src={result.thumbnail} alt="" className="w-36 rounded-lg object-cover flex-shrink-0" />
              )}
              <div className="flex-1 min-w-0">
                <div className="font-semibold text-white text-base leading-snug mb-1" style={{ display: "-webkit-box", WebkitLineClamp: 2, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                  {result.title}
                </div>
                <div className="text-[#666] text-sm mb-3">{result.channel}</div>
                <div className="flex flex-wrap gap-3 text-xs text-[#555] font-mono">
                  <span>👁 {fmt(result.view_count)}</span>
                  <span>👍 {fmt(result.like_count)}</span>
                  <span>💬 {fmt(result.comment_count)}</span>
                  <span>⏱ {fmtDur(result.duration_seconds)}</span>
                  {result.language && <span>🌐 {result.language}</span>}
                  <span>📅 {result.published_at?.slice(0, 10)}</span>
                </div>
              </div>
            </div>

            {/* Tabs */}
            <div className="flex gap-1 mb-6 border-b border-white/5">
              {tabs.map((t) => (
                <button
                  key={t}
                  onClick={() => setActiveTab(t)}
                  className={`px-4 py-2.5 text-xs font-mono uppercase tracking-wider transition-colors border-b-2 -mb-px cursor-pointer ${
                    activeTab === t ? "border-[#7c6aff] text-[#a78bfa]" : "border-transparent text-[#555] hover:text-[#888]"
                  }`}
                >
                  {t}
                  {t === "comments" && ` (${result.comments.length})`}
                  {t === "transcript" && (result.transcript.available ? ` (${fmt(result.transcript.word_count)} words)` : " (none)")}
                </button>
              ))}
              <button
                onClick={copyJson}
                className="ml-auto px-4 py-2.5 text-xs font-mono text-[#555] hover:text-[#7c6aff] transition-colors cursor-pointer"
              >
                {copied ? "✓ Copied" : "Copy JSON"}
              </button>
            </div>

            {/* Overview */}
            {activeTab === "overview" && (
              <div className="space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  {[
                    ["Video ID", result.video_id],
                    ["Channel", result.channel],
                    ["Views", fmt(result.view_count)],
                    ["Likes", fmt(result.like_count)],
                    ["Comments", fmt(result.comment_count)],
                    ["Duration", fmtDur(result.duration_seconds)],
                    ["Language", result.language || "—"],
                    ["Published", result.published_at?.slice(0, 10)],
                    ["Transcript", result.transcript.available ? `✓ ${fmt(result.transcript.word_count)} words` : "✗ Unavailable"],
                    ["Tags", result.tags.length ? result.tags.slice(0, 5).join(", ") : "—"],
                  ].map(([label, value]) => (
                    <div key={label as string} className="bg-[#111] border border-white/5 rounded-lg p-4">
                      <div className="text-[#555] text-xs font-mono uppercase tracking-wider mb-1">{label}</div>
                      <div className="text-sm text-[#ccc] truncate">{value}</div>
                    </div>
                  ))}
                </div>
                {result.description && (
                  <div className="bg-[#111] border border-white/5 rounded-lg p-4">
                    <div className="text-[#555] text-xs font-mono uppercase tracking-wider mb-2">Description</div>
                    <div className="text-sm text-[#999] leading-relaxed whitespace-pre-line" style={{ display: "-webkit-box", WebkitLineClamp: 8, WebkitBoxOrient: "vertical", overflow: "hidden" }}>
                      {result.description}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* Transcript */}
            {activeTab === "transcript" && (
              result.transcript.available ? (
                <div className="bg-[#0d0d0d] border border-white/5 rounded-lg p-5">
                  <div className="text-xs font-mono text-[#555] uppercase tracking-wider mb-4">
                    Full Transcript — {fmt(result.transcript.word_count)} words
                  </div>
                  <div className="text-sm text-[#999] leading-loose max-h-[520px] overflow-y-auto whitespace-pre-wrap">
                    {result.transcript.full_text}
                  </div>
                </div>
              ) : (
                <div className="text-center py-16 text-[#444] text-sm">No transcript available for this video</div>
              )
            )}

            {/* Comments */}
            {activeTab === "comments" && (
              <div className="space-y-3">
                {result.comments.length === 0 ? (
                  <div className="text-center py-16 text-[#444] text-sm">No comments fetched</div>
                ) : result.comments.map((c, i) => (
                  <div key={i} className="bg-[#111] border border-white/5 rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <span className="text-xs font-medium text-[#888]">{c.author}</span>
                      <div className="flex gap-3 text-xs text-[#555] font-mono">
                        {c.likes > 0 && <span>👍 {fmt(c.likes)}</span>}
                        {c.reply_count > 0 && <span>↩ {c.reply_count}</span>}
                        <span>{c.published_at?.slice(0, 10)}</span>
                      </div>
                    </div>
                    <div className="text-sm text-[#999] leading-relaxed" dangerouslySetInnerHTML={{ __html: c.text }} />
                  </div>
                ))}
              </div>
            )}

            {/* Raw JSON */}
            {activeTab === "json" && (
              <div className="bg-[#0d0d0d] border border-white/5 rounded-lg p-5 max-h-[600px] overflow-auto">
                <pre className="text-xs text-[#7ec87e] leading-relaxed font-mono">
                  {JSON.stringify(result, null, 2)}
                </pre>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
