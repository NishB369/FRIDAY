import { z } from "zod";

export const wordSchema = z.object({
  word: z.string(),
  startSec: z.number(),
  endSec: z.number(),
});

export const transcriptKaraokeSchema = z.object({
  words: z.array(wordSchema),
  totalDurationSec: z.number(),
  fps: z.number().default(30),
  wordsPerScreen: z.number().default(18),
  bgColor: z.string().default("#F5F4F0"),
  textActive: z.string().default("#1A1A1A"),
  textPast: z.string().default("#AAAAAA"),
  textFuture: z.string().default("#CCCCCC"),
  fontSize: z.number().default(52),
  fontFamily: z.string().default("Georgia, 'Times New Roman', serif"),
});

export type Word = z.infer<typeof wordSchema>;
export type TranscriptKaraokeProps = z.infer<typeof transcriptKaraokeSchema>;
