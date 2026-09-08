import type { VoiceState } from "../hooks/useLiveKitAudio";

// Monochromatic system: states read through brightness + glow intensity,
// not hue. Dimmer/quieter = idle, brighter/stronger = active.
const states: Record<
  VoiceState,
  { label: string; color: string; glow: string }
> = {
  offline: {
    label: "Terminal offline",
    color: "border-zinc-800 text-zinc-600",
    glow: "none"
  },
  listening: {
    label: "Listening",
    color: "border-zinc-500 text-zinc-300",
    glow: "0 0 70px rgb(255 255 255 / 10%)"
  },
  user: {
    label: "ScrubSync listening",
    color: "border-zinc-300 text-zinc-100",
    glow: "0 0 90px rgb(255 255 255 / 18%)"
  },
  tool: {
    label: "ScrubSync thinking",
    color: "border-zinc-400 text-zinc-200",
    glow: "0 0 90px rgb(255 255 255 / 14%)"
  },
  speaking: {
    label: "ScrubSync speaking",
    color: "border-white text-white",
    glow: "0 0 110px rgb(255 255 255 / 26%)"
  },
  error: {
    label: "Attention required",
    color: "border-zinc-200 border-dashed text-zinc-100",
    glow: "0 0 80px rgb(255 255 255 / 20%)"
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
        className={`beacon flex h-64 w-64 items-center justify-center rounded-full border-[6px] bg-white/[0.02] backdrop-blur-sm ${appearance.color} ${
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