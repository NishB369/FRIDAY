import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { TranscriptKaraokeProps } from "./schema";

const FONT = "'Helvetica Neue', Helvetica, Arial, sans-serif";
const SCREEN_FADE = 20;

export const TranscriptKaraoke: React.FC<TranscriptKaraokeProps> = ({
  words,
  fps,
  wordsPerScreen,
  totalDurationSec,
}) => {
  const frame = useCurrentFrame();
  const currentSec = frame / fps;

  // ── Active word ─────────────────────────────────────────────────────────────
  let activeIndex = -1;
  for (let i = 0; i < words.length; i++) {
    if (currentSec >= words[i].startSec && currentSec < words[i].endSec) {
      activeIndex = i;
      break;
    }
  }
  if (activeIndex === -1) {
    for (let i = words.length - 1; i >= 0; i--) {
      if (currentSec >= words[i].endSec) {
        activeIndex = i;
        break;
      }
    }
  }

  // ── How far through the active word (0→1) ───────────────────────────────────
  const activeWord = activeIndex !== -1 ? words[activeIndex] : null;
  const wordDuration = activeWord
    ? Math.max(0.05, activeWord.endSec - activeWord.startSec)
    : 1;
  const wordProgress = activeWord
    ? Math.min(1, (currentSec - activeWord.startSec) / wordDuration)
    : 0;

  // ── Screen window ───────────────────────────────────────────────────────────
  const screenIndex = activeIndex <= 0 ? 0 : Math.floor(activeIndex / wordsPerScreen);
  const windowStart = screenIndex * wordsPerScreen;
  const windowEnd = Math.min(windowStart + wordsPerScreen, words.length);
  const visibleWords = words.slice(windowStart, windowEnd);

  // ── Screen fade-in ──────────────────────────────────────────────────────────
  const screenFirstWord = words[windowStart];
  const screenStartFrame = screenFirstWord
    ? Math.round(screenFirstWord.startSec * fps)
    : 0;
  const screenOpacity = interpolate(
    frame - screenStartFrame,
    [0, SCREEN_FADE],
    [0, 1],
    { extrapolateLeft: "clamp", extrapolateRight: "clamp" }
  );

  // ── Progress bar ─────────────────────────────────────────────────────────────
  const progress = interpolate(currentSec, [0, totalDurationSec], [0, 100], {
    extrapolateRight: "clamp",
  });

  return (
    <AbsoluteFill style={{ backgroundColor: "#F2F1EE" }}>

      {/* Text block — vertically centered, left-aligned, constrained width */}
      <div
        style={{
          position: "absolute",
          top: 0,
          bottom: 0,
          left: 0,
          right: 0,
          padding: "0 110px",
          display: "flex",
          alignItems: "center",
          opacity: screenOpacity,
        }}
      >
        <p
          style={{
            fontFamily: FONT,
            fontSize: 112,
            fontWeight: 300,
            lineHeight: 1.25,
            letterSpacing: "-0.04em",
            margin: 0,
            color: "#111",
            maxWidth: 1400,
          }}
        >
          {visibleWords.map((w, i) => {
            const g = windowStart + i;
            const isPastOrActive = g <= activeIndex;
            const isNext = g === activeIndex + 1;

            // Opacity model — matches reference:
            // past + active = dark (1.0)
            // next word = smoothly lifting from ghost to semi (0.22 → 0.45) as active word nears end
            // rest future = ghost (0.22)
            let opacity: number;

            if (isPastOrActive) {
              if (g === activeIndex) {
                // Active word fades in from ghost as it starts
                opacity = interpolate(wordProgress, [0, 0.25], [0.22, 1], {
                  extrapolateLeft: "clamp",
                  extrapolateRight: "clamp",
                });
              } else {
                opacity = 1;
              }
            } else if (isNext) {
              // Gently lifts as active word approaches its end
              opacity = interpolate(wordProgress, [0.6, 1], [0.22, 0.42], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });
            } else {
              opacity = 0.22;
            }

            return (
              <React.Fragment key={g}>
                <span style={{ opacity, display: "inline" }}>{w.word}</span>
                {i < visibleWords.length - 1 && (
                  <span style={{ opacity: isPastOrActive ? 1 : 0.22 }}>{" "}</span>
                )}
              </React.Fragment>
            );
          })}
        </p>
      </div>

      {/* Hairline progress at bottom */}
      <div
        style={{
          position: "absolute",
          bottom: 0,
          left: 0,
          height: 2,
          width: `${progress}%`,
          backgroundColor: "#111",
          opacity: 0.1,
        }}
      />

    </AbsoluteFill>
  );
};
