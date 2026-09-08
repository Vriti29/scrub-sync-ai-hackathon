export interface TelemetryProps {
  epoch: number;
  cutoffMs: number | null;
  renderedMs: number;
  connected: boolean;
}

export function Telemetry({
  epoch,
  cutoffMs,
  renderedMs,
  connected
}: TelemetryProps) {
  return (
    <footer className="grid gap-4 rounded-2xl border border-zinc-800/80 bg-zinc-900/30 p-5 backdrop-blur-xl md:grid-cols-2 xl:grid-cols-4 shadow-xl">
      {/* Metric 1 */}
      <div className="rounded-xl border border-zinc-800/80 bg-black/40 p-4">
        <p className="font-mono text-[10px] uppercase tracking-wider text-zinc-400">Active TTS Engine</p>
        <p className="mt-2 font-mono text-lg font-bold text-zinc-100 flex items-center gap-2">
          Rime
          <span className="rounded bg-cyan-950/80 border border-cyan-800/60 px-1.5 py-0.5 text-[9px] font-mono text-cyan-300">
            24kHz PCM
          </span>
        </p>
        <p className="mt-1 font-mono text-xs text-zinc-500">mist / amber</p>
      </div>

      {/* Metric 2 */}
      <div className="rounded-xl border border-zinc-800/80 bg-black/40 p-4">
        <p className="font-mono text-[10px] uppercase tracking-wider text-zinc-400">Orchestration Model</p>
        <p className="mt-2 font-mono text-lg font-bold text-zinc-100">Qwen 2.5</p>
        <div className="mt-1 flex items-center gap-1.5">
          <span className={`h-1.5 w-1.5 rounded-full ${connected ? "bg-emerald-400 animate-pulse" : "bg-zinc-600"}`} />
          <p className="font-mono text-xs text-zinc-400">
            {connected ? "LiveKit WebRTC Active" : "Transport Offline"}
          </p>
        </div>
      </div>

      {/* Metric 3 */}
      <div className="rounded-xl border border-zinc-800/80 bg-black/40 p-4">
        <p className="font-mono text-[10px] uppercase tracking-wider text-cyan-400">Active Epoch ID</p>
        <p className="mt-2 font-mono text-3xl font-black text-cyan-300 tracking-tight">
          #{epoch}
        </p>
        <p className="mt-1 font-mono text-[10px] text-zinc-500">Atomic State Machine</p>
      </div>

      {/* Metric 4 */}
      <div className="rounded-xl border border-zinc-800/80 bg-black/40 p-4">
        <div className="flex items-center justify-between">
          <p className="font-mono text-[10px] uppercase tracking-wider text-zinc-400">Interruption Cutoff</p>
          {cutoffMs !== null && (
            <span className="rounded bg-emerald-950 border border-emerald-600/60 px-1.5 py-0.5 font-mono text-[9px] text-emerald-300">
              SUB-MS GATE
            </span>
          )}
        </div>
        <p className={`mt-2 font-mono text-2xl font-black ${cutoffMs === null ? "text-zinc-500" : "text-emerald-400 drop-shadow-[0_0_12px_rgba(52,211,153,0.3)]"}`}>
          {cutoffMs === null ? "Not measured" : `${cutoffMs.toFixed(1)} ms`}
        </p>
        <p className="mt-1 font-mono text-[10px] text-zinc-500">
          Last receipt: {renderedMs.toFixed(0)} ms non-silent audio
        </p>
      </div>
    </footer>
  );
}