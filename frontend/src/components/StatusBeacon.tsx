import type { VoiceState } from "../hooks/useLiveKitAudio";

const states: Record<
  VoiceState,
  { label: string; border: string; text: string; glow: string; badgeBg: string }
> = {
  offline: {
    label: "Terminal Offline",
    border: "border-zinc-800/80 bg-zinc-950/40",
    text: "text-zinc-600",
    glow: "none",
    badgeBg: "bg-zinc-800 text-zinc-500"
  },
  listening: {
    label: "Waiting ...",
    border: "border-cyan-500/50 bg-cyan-950/20",
    text: "text-cyan-300",
    glow: "0 0 60px rgba(6, 182, 212, 0.25)",
    badgeBg: "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
  },
  user: {
    label: "ScrubSync listening",
    border: "border-emerald-400 bg-emerald-950/25",
    text: "text-emerald-300",
    glow: "0 0 80px rgba(52, 211, 153, 0.35)",
    badgeBg: "bg-emerald-500/20 text-emerald-300 border border-emerald-500/40"
  },
  tool: {
    label: "ScrubSync thinking",
    border: "border-amber-400/80 bg-amber-950/20",
    text: "text-amber-300",
    glow: "0 0 70px rgba(251, 191, 36, 0.3)",
    badgeBg: "bg-amber-500/20 text-amber-300 border border-amber-500/40"
  },
  speaking: {
    label: "ScrubSync Speaking",
    border: "border-cyan-400 bg-cyan-900/30",
    text: "text-cyan-100",
    glow: "0 0 100px rgba(6, 182, 212, 0.45)",
    badgeBg: "bg-cyan-400 text-black font-semibold"
  },
  error: {
    label: "Safety Fallback Triggered",
    border: "border-rose-500/80 border-dashed bg-rose-950/25",
    text: "text-rose-300",
    glow: "0 0 70px rgba(244, 63, 94, 0.35)",
    badgeBg: "bg-rose-500/20 text-rose-300 border border-rose-500/40"
  }
};

export function StatusBeacon({ state }: { state: VoiceState }) {
  const current = states[state];
  const isOnline = state !== "offline";
  const isActive = state === "speaking" || state === "user" || state === "tool";
  // Symmetric waveform heights used when the beacon is actively engaged.
  const waveHeights = ["h-3", "h-6", "h-9", "h-11", "h-9", "h-6", "h-3"];

  return (
    <section
      className="flex flex-col items-center justify-center gap-6 rounded-2xl border border-zinc-800/60 bg-zinc-900/20 p-8 backdrop-blur-md shadow-2xl"
      aria-label={`Voice status: ${current.label}`}
    >
      <div
        className={`relative flex h-64 w-64 items-center justify-center rounded-full border-[5px] transition-all duration-300 ${current.border}`}
        style={{ boxShadow: current.glow }}
      >
        {/* Subtle Ambient Pulse Ring */}
        {isOnline && (
          <div className="absolute inset-0 rounded-full animate-ping opacity-20 border border-cyan-400" />
        )}

        <div className="relative z-10 flex flex-col items-center gap-4">
          {/* Gradient microphone icon — breathes while online */}
          <svg
            width="58"
            height="58"
            viewBox="0 0 24 24"
            fill="none"
            aria-hidden="true"
            className={`drop-shadow-[0_0_12px_rgba(6,182,212,0.5)] ${
              isOnline ? "animate-pulse" : "opacity-50"
            }`}
          >
            <defs>
              <linearGradient id="beaconMicGrad" x1="0" y1="0" x2="1" y2="1">
                <stop offset="0%" stopColor="#22d3ee" />
                <stop offset="100%" stopColor="#34d399" />
              </linearGradient>
            </defs>
            <path
              d="M12 15.5a3.25 3.25 0 0 1-3.25-3.25V5a3.25 3.25 0 0 1 6.5 0v7.25A3.25 3.25 0 0 1 12 15.5Z"
              stroke="url(#beaconMicGrad)"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
            <path
              d="M18.5 12.25a6.5 6.5 0 0 1-13 0M12 18.75V22M8.5 22h7"
              stroke="url(#beaconMicGrad)"
              strokeWidth="1.6"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>

          {/* State-reactive gradient equalizer */}
          <div className="flex h-12 items-end justify-center gap-1.5">
            {waveHeights.map((h, i) => (
              <span
                key={i}
                className={[
                  "w-1.5 rounded-full bg-gradient-to-t from-cyan-500 via-cyan-300 to-emerald-300 transition-all duration-300",
                  isActive ? h : "h-1.5 opacity-25",
                  state === "speaking"
                    ? "animate-bounce"
                    : isActive
                      ? "animate-pulse"
                      : ""
                ].join(" ")}
                style={{ animationDelay: `${i * 80}ms` }}
              />
            ))}
          </div>
        </div>
      </div>

      <div className="flex flex-col items-center gap-2">
        <div className="flex items-center gap-2">
          <span className={`h-2.5 w-2.5 rounded-full ${isOnline ? "bg-emerald-400 animate-pulse" : "bg-rose-500"}`} />
          <h2 className={`font-mono text-xl font-bold tracking-wide ${current.text}`}>
            {current.label}
          </h2>
        </div>
        <span className="font-mono text-[11px] text-zinc-500 uppercase tracking-wider">
          {state === "speaking" ? "PCM 24000Hz · High Priority Stream" : "Sub-ms Zero-Pop Gating Ready"}
        </span>
      </div>
    </section>
  );
}
