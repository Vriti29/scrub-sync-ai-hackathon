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
    label: "Listening for Ingest",
    border: "border-cyan-500/50 bg-cyan-950/20",
    text: "text-cyan-300",
    glow: "0 0 60px rgba(6, 182, 212, 0.25)",
    badgeBg: "bg-cyan-500/20 text-cyan-300 border border-cyan-500/40"
  },
  user: {
    label: "ScrubSync Speaking",
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

        <div className="text-center z-10">
          <div className="font-mono text-6xl font-black tracking-tight text-white drop-shadow-md">
            200
          </div>
          <div className="mt-2 font-mono text-[11px] font-bold tracking-[0.35em] text-zinc-400 uppercase">
            Voice Native
          </div>

          {/* Dynamic Audio Bars Simulation */}
          <div className="mt-4 flex items-center justify-center gap-1.5 h-6">
            <span className={`w-1 rounded-full bg-cyan-400 transition-all duration-150 ${state === "speaking" ? "h-6 animate-pulse" : state === "user" ? "h-4" : "h-1.5 opacity-30"}`} />
            <span className={`w-1 rounded-full bg-cyan-400 transition-all duration-150 ${state === "speaking" ? "h-8 animate-bounce" : state === "user" ? "h-5" : "h-1.5 opacity-30"}`} />
            <span className={`w-1 rounded-full bg-cyan-400 transition-all duration-150 ${state === "speaking" ? "h-4 animate-pulse" : state === "user" ? "h-3" : "h-1.5 opacity-30"}`} />
            <span className={`w-1 rounded-full bg-cyan-400 transition-all duration-150 ${state === "speaking" ? "h-7 animate-bounce" : state === "user" ? "h-6" : "h-1.5 opacity-30"}`} />
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
