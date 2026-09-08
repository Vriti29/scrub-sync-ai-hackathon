import type { ClinicalResult } from "../hooks/useLiveKitAudio";

export function MetricReadout({
  result
}: {
  result: ClinicalResult | null;
}) {
  if (!result) {
    return (
      <section className="panel flex min-h-80 flex-col justify-center">
        <p className="eyebrow">Latest authorized result</p>
        <p className="mt-8 text-4xl font-semibold text-slate-300">
          Awaiting voice request
        </p>
        <p className="mt-6 text-lg text-slate-400">
          “Check electrolytes.” Then interrupt: “Check blood gas pH instead.”
        </p>
      </section>
    );
  }

  const potassium = result.panel === "electrolytes";
  const metric = potassium ? result.potassium : result.ph;
  if (!metric) return null;

  return (
    <section className="panel min-h-80" aria-label="Synthetic clinical result">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <p className="eyebrow">
          {potassium ? "Potassium · K+" : "Arterial blood gas · pH"}
        </p>
        <span className="rounded border border-amber-700 px-3 py-1 text-sm font-bold text-amber-300">
          SYNTHETIC DEMO
        </span>
      </div>
      <div className="mt-7 flex flex-wrap items-baseline gap-5">
        <span className="font-mono text-[clamp(5rem,10vw,9rem)] font-black leading-none tracking-tighter text-white">
          {potassium ? metric.value.toFixed(1) : metric.value.toFixed(2)}
        </span>
        <span className="font-mono text-3xl text-slate-300">
          {metric.unit}
        </span>
      </div>
      <div className="mt-7 inline-block rounded-lg bg-rose-500/15 px-5 py-3 text-2xl font-extrabold tracking-wide text-rose-300">
        {metric.flag}
      </div>
      {!potassium && result.pco2 && (
        <p className="mt-5 font-mono text-2xl text-slate-200">
          pCO₂ {result.pco2.value} {result.pco2.unit}
        </p>
      )}
      <p className="mt-5 text-sm text-slate-400">
        Fixture flag, not a validated diagnostic or treatment recommendation.
      </p>
    </section>
  );
}