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
        <p className="mt-8 text-4xl font-semibold text-zinc-200">
          Awaiting voice request
        </p>
        <p className="mt-6 text-lg text-zinc-500">
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
        <span className="rounded-full border border-white/15 bg-white/[0.04] px-3 py-1 text-xs font-bold uppercase tracking-wider text-zinc-300">
          Synthetic demo
        </span>
      </div>
      <div className="mt-7 flex flex-wrap items-baseline gap-5">
        <span className="font-mono text-[clamp(5rem,10vw,9rem)] font-black leading-none tracking-tighter text-white">
          {potassium ? metric.value.toFixed(1) : metric.value.toFixed(2)}
        </span>
        <span className="font-mono text-3xl text-zinc-400">
          {metric.unit}
        </span>
      </div>
      <div className="mt-7 inline-block rounded-lg border border-white/20 bg-white/[0.06] px-5 py-3 text-2xl font-extrabold tracking-wide text-white">
        {metric.flag}
      </div>
      {!potassium && result.pco2 && (
        <p className="mt-5 font-mono text-2xl text-zinc-200">
          pCO₂ {result.pco2.value} {result.pco2.unit}
        </p>
      )}
      <p className="mt-5 text-sm text-zinc-500">
        Fixture flag, not a validated diagnostic or treatment recommendation.
      </p>
    </section>
  );
}