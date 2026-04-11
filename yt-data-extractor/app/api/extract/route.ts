import { NextRequest, NextResponse } from "next/server";
import { YoutubeTranscript } from "youtube-transcript";

const YT_API_KEY = process.env.YOUTUBE_API_KEY;
const YT_BASE = "https://www.googleapis.com/youtube/v3";

function extractVideoId(input: string): string | null {
  const patterns = [
    /(?:v=|\/shorts\/|youtu\.be\/)([a-zA-Z0-9_-]{11})/,
    /^([a-zA-Z0-9_-]{11})$/,
  ];
  for (const p of patterns) {
    const m = input.match(p);
    if (m) return m[1];
  }
  return null;
}

async function fetchMetadata(videoId: string) {
  const url = `${YT_BASE}/videos?part=snippet,statistics,contentDetails&id=${videoId}&key=${YT_API_KEY}`;
  const res = await fetch(url);
  const data = await res.json();
  if (!data.items?.length) return null;
  const item = data.items[0];
  const s = item.snippet;
  const st = item.statistics;
  const cd = item.contentDetails;

  // Parse ISO 8601 duration to seconds
  const dur = cd.duration || "PT0S";
  const durMatch = dur.match(/PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?/);
  const durationSeconds = durMatch
    ? (parseInt(durMatch[1] || "0") * 3600 +
       parseInt(durMatch[2] || "0") * 60 +
       parseInt(durMatch[3] || "0"))
    : 0;

  return {
    video_id: videoId,
    url: `https://www.youtube.com/watch?v=${videoId}`,
    title: s.title,
    channel: s.channelTitle,
    channel_id: s.channelId,
    description: s.description,
    published_at: s.publishedAt,
    upload_date: s.publishedAt?.slice(0, 10).replace(/-/g, ""),
    duration_seconds: durationSeconds,
    thumbnail: s.thumbnails?.maxres?.url || s.thumbnails?.high?.url || "",
    tags: s.tags || [],
    category_id: s.categoryId,
    view_count: parseInt(st.viewCount || "0"),
    like_count: parseInt(st.likeCount || "0"),
    comment_count: parseInt(st.commentCount || "0"),
    language: s.defaultAudioLanguage || s.defaultLanguage || null,
  };
}

async function fetchComments(videoId: string, maxResults = 50) {
  const url = `${YT_BASE}/commentThreads?part=snippet&videoId=${videoId}&maxResults=${maxResults}&order=relevance&key=${YT_API_KEY}`;
  const res = await fetch(url);
  const data = await res.json();
  if (!data.items) return [];
  return data.items.map((item: any) => {
    const c = item.snippet.topLevelComment.snippet;
    return {
      author: c.authorDisplayName,
      text: c.textDisplay,
      likes: c.likeCount,
      published_at: c.publishedAt,
      reply_count: item.snippet.totalReplyCount,
    };
  });
}

async function fetchTranscript(videoId: string) {
  try {
    const cookieHeader = process.env.YOUTUBE_COOKIES;
    const customFetch = cookieHeader
      ? (url: Parameters<typeof fetch>[0], init?: Parameters<typeof fetch>[1]) =>
          fetch(url, { ...init, headers: { ...(init?.headers ?? {}), Cookie: cookieHeader } })
      : undefined;

    const list = await YoutubeTranscript.fetchTranscript(videoId, {
      fetch: customFetch as typeof fetch,
    });
    const full_text = list.map((c) => c.text).join(" ");
    return {
      available: true,
      word_count: full_text.split(/\s+/).length,
      full_text,
      chunks: list.map((c) => ({
        text: c.text,
        offset: Math.round(c.offset / 1000),
        duration: Math.round(c.duration / 1000),
      })),
    };
  } catch {
    return { available: false, full_text: null, chunks: [] };
  }
}

export async function POST(req: NextRequest) {
  const { url } = await req.json();
  if (!url) return NextResponse.json({ error: "No URL provided" }, { status: 400 });

  const videoId = extractVideoId(url);
  if (!videoId) return NextResponse.json({ error: "Invalid YouTube URL" }, { status: 400 });

  if (!YT_API_KEY) return NextResponse.json({ error: "YOUTUBE_API_KEY not set" }, { status: 500 });

  const [metadata, comments, transcript] = await Promise.all([
    fetchMetadata(videoId),
    fetchComments(videoId),
    fetchTranscript(videoId),
  ]);

  if (!metadata) return NextResponse.json({ error: "Video not found or private" }, { status: 404 });

  return NextResponse.json({ ...metadata, comments, transcript });
}
