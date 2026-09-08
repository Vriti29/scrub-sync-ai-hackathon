import type { ClinicalResult } from "../hooks/useLiveKitAudio";

export function MetricReadout({
  result
}: {
  result: ClinicalResult | null;
}) {
  if (!result) {
    return (
      <section style={{"display": "none"}} className="flex min-h-80 flex-col justify-center rounded-2xl border border-zinc-800/80 bg-zinc-900/30 p-8 backdrop-blur-md shadow-xl">
        <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
          <span className="font-mono text-xs uppercase tracking-widest text-cyan-400">
            Telemetry Vitals · EHR Core
          </span>
          <span className="rounded bg-zinc-800 px-2 py-0.5 font-mono text-[10px] text-zinc-400">
            DEMO-001 SYNTHETIC
          </span>
        </div>

        <div className="my-6">
          <p className="text-3xl font-bold tracking-tight text-zinc-100">
            Awaiting Voice Request
          </p>
          <p className="mt-2 text-sm text-zinc-400">
            Speak a clinical order or vital panel check to populate real-time diagnostics:
          </p>
        </div>

        {/* Quick Suggestion Chips */}
        <div className="flex flex-wrap gap-2 pt-2 border-t border-zinc-800/60">
          <span className="rounded-lg border border-cyan-500/20 bg-cyan-950/30 px-3 py-1.5 font-mono text-xs text-cyan-300">
            "Check electrolytes for DEMO-001"
          </span>
          <span className="rounded-lg border border-zinc-700/60 bg-zinc-800/40 px-3 py-1.5 font-mono text-xs text-zinc-300">
            "Check arterial blood gas pH"
          </span>
        </div>
      </section>
    );
  }

  const potassium = result.panel === "electrolytes";
  const metric = potassium ? result.potassium : result.ph;
  if (!metric) return null;

  const isAcidosis = !potassium && metric.value < 7.35;

  return (
    <section
      className="min-h-80 rounded-2xl border border-cyan-500/30 bg-zinc-900/40 p-8 backdrop-blur-md shadow-2xl relative overflow-hidden"
      aria-label="Synthetic clinical result"
    >
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-zinc-800/80 pb-3">
        <span className="font-mono text-xs uppercase tracking-widest text-cyan-400">
          {potassium ? "Serum Electrolyte Panel · K+" : "Arterial Blood Gas Analysis · pH"}
        </span>
        <span className="rounded-full border border-cyan-500/30 bg-cyan-950/60 px-3 py-1 font-mono text-[10px] font-bold uppercase tracking-wider text-cyan-300">
          Synthetic OR Record
        </span>
      </div>

      <div className="mt-6 flex flex-wrap items-baseline gap-4">
        <span className="font-mono text-[clamp(4.5rem,8vw,8rem)] font-black leading-none tracking-tighter text-white drop-shadow-[0_0_25px_rgba(255,255,255,0.2)]">
          {potassium ? metric.value.toFixed(1) : metric.value.toFixed(2)}
        </span>
        <span className="font-mono text-2xl font-semibold text-zinc-400">
          {metric.unit}
        </span>
      </div>

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <div
          className={`inline-flex items-center gap-2 rounded-xl px-4 py-2 font-mono text-lg font-black tracking-wide ${
            isAcidosis
              ? "bg-rose-500/20 border border-rose-500/60 text-rose-300 shadow-[0_0_20px_rgba(244,63,94,0.25)]"
              : "bg-emerald-500/20 border border-emerald-500/60 text-emerald-300"
          }`}
        >
          <span className={`h-2 w-2 rounded-full ${isAcidosis ? "bg-rose-500 animate-ping" : "bg-emerald-400"}`} />
          {metric.flag}
        </div>

        {!potassium && result.pco2 && (
          <div className="rounded-xl border border-zinc-700/60 bg-zinc-800/50 px-4 py-2 font-mono text-lg text-zinc-200">
            pCO₂ <span className="font-bold text-white">{result.pco2.value}</span> {result.pco2.unit}
          </div>
        )}
      </div>

      <p className="mt-6 font-mono text-[11px] text-zinc-500 border-t border-zinc-800/60 pt-3">
        Synthetic test fixture · High-fidelity OR demonstrator only.
      </p>
    </section>
  );
}
