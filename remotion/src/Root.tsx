import React from "react";
import { Composition } from "remotion";
import { TranscriptKaraoke } from "./compositions/TranscriptKaraoke";
import { transcriptKaraokeSchema, TranscriptKaraokeProps } from "./compositions/TranscriptKaraoke/schema";

// Sample props for studio preview — one short chunk of a TLT video
const SAMPLE_WORDS = [
  { word: "hello", startSec: 0, endSec: 1 },
  { word: "everyone", startSec: 1, endSec: 2 },
  { word: "aaj", startSec: 2, endSec: 2.5 },
  { word: "hum", startSec: 2.5, endSec: 3 },
  { word: "log", startSec: 3, endSec: 3.5 },
  { word: "padenge", startSec: 3.5, endSec: 4.5 },
  { word: "A", startSec: 4.5, endSec: 5 },
  { word: "Feast", startSec: 5, endSec: 5.5 },
  { word: "on", startSec: 5.5, endSec: 6 },
  { word: "the", startSec: 6, endSec: 6.3 },
  { word: "Train", startSec: 6.3, endSec: 7 },
  { word: "ke", startSec: 7, endSec: 7.3 },
  { word: "bare", startSec: 7.3, endSec: 7.8 },
  { word: "mein", startSec: 7.8, endSec: 8.5 },
  { word: "is", startSec: 8.5, endSec: 9 },
  { word: "story", startSec: 9, endSec: 9.8 },
  { word: "mein", startSec: 9.8, endSec: 10.3 },
  { word: "kuch", startSec: 10.3, endSec: 10.8 },
  { word: "boys", startSec: 10.8, endSec: 11.5 },
  { word: "hain", startSec: 11.5, endSec: 12 },
  { word: "jo", startSec: 12, endSec: 12.4 },
  { word: "train", startSec: 12.4, endSec: 13 },
  { word: "mein", startSec: 13, endSec: 13.5 },
  { word: "travel", startSec: 13.5, endSec: 14.2 },
  { word: "kar", startSec: 14.2, endSec: 14.5 },
  { word: "rahe", startSec: 14.5, endSec: 15 },
  { word: "hain", startSec: 15, endSec: 15.8 },
  { word: "apne", startSec: 15.8, endSec: 16.4 },
  { word: "school", startSec: 16.4, endSec: 17.2 },
  { word: "wapas", startSec: 17.2, endSec: 18 },
];

const SAMPLE_DURATION = 30;

export const Root: React.FC = () => {
  return (
    <>
      <Composition
        id="TranscriptKaraoke"
        component={TranscriptKaraoke}
        schema={transcriptKaraokeSchema}
        // calculateMetadata makes durationInFrames dynamic — driven by props.totalDurationSec
        calculateMetadata={({ props }: { props: TranscriptKaraokeProps }) => ({
          durationInFrames: Math.round(props.totalDurationSec * props.fps),
          fps: props.fps,
        })}
        durationInFrames={SAMPLE_DURATION * 30}
        fps={30}
        width={1920}
        height={1080}
        defaultProps={{
          words: SAMPLE_WORDS,
          totalDurationSec: SAMPLE_DURATION,
          fps: 30,
          wordsPerScreen: 18,
          bgColor: "#F5F4F0",
          textActive: "#1A1A1A",
          textPast: "#AAAAAA",
          textFuture: "#CCCCCC",
          fontSize: 52,
          fontFamily: "Georgia, 'Times New Roman', serif",
        }}
      />
    </>
  );
};
