import type { VoiceState } from "../hooks/useLiveKitAudio";

const states: Record<
  VoiceState,
  { label: string; color: string; glow: string }
> = {
  offline: {
    label: "Terminal offline",
    color: "border-slate-600 text-slate-400",
    glow: "none"
  },
  listening: {
    label: "Listening",
    color: "border-cyan-400 text-cyan-300",
    glow: "0 0 70px rgb(34 211 238 / 25%)"
  },
  user: {
    label: "Surgeon speaking",
    color: "border-emerald-400 text-emerald-300",
    glow: "0 0 90px rgb(52 211 153 / 30%)"
  },
  tool: {
    label: "Clinical tool active",
    color: "border-amber-400 text-amber-300",
    glow: "0 0 90px rgb(251 191 36 / 30%)"
  },
  speaking: {
    label: "Rime speaking",
    color: "border-violet-400 text-violet-300",
    glow: "0 0 90px rgb(167 139 250 / 30%)"
  },
  error: {
    label: "Attention required",
    color: "border-rose-400 text-rose-300",
    glow: "0 0 70px rgb(251 113 133 / 25%)"
  }
};

export function StatusBeacon({ state }: { state: VoiceState }) {
  const appearance = states[state];
  return (
    <section
      className="flex flex-col items-center justify-center gap-8 py-8"
      aria-label={`Voice status: ${appearance.label}`}
    >
      <div
        className={`beacon flex h-64 w-64 items-center justify-center rounded-full border-[10px] ${appearance.color} ${
          state !== "offline" ? "beacon-active" : ""
        }`}
        style={{ boxShadow: appearance.glow }}
      >
        <div className="text-center">
          <div className="text-6xl font-black tracking-tight">200</div>
          <div className="mt-3 text-xs font-semibold tracking-[0.3em]">
            VOICE NATIVE
          </div>
        </div>
      </div>
      <h2 className={`text-center text-3xl font-bold ${appearance.color}`}>
        {appearance.label}
      </h2>
    </section>
  );
}