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
      <footer className="grid gap-4 rounded-2xl border border-slate-700 bg-slate-900/80 p-6 md:grid-cols-2 xl:grid-cols-4">
        <div>
          <p className="eyebrow">Active TTS engine</p>
          <p className="mt-2 text-xl font-bold text-violet-300">Rime</p>
          <p className="mt-1 font-mono text-sm text-slate-300">
            mist / amber / pcm_24000
          </p>
        </div>
        <div>
          <p className="eyebrow">Orchestration model</p>
          <p className="mt-2 text-xl font-bold">Qwen 2.5</p>
          <p className="mt-1 text-sm text-slate-400">
            {connected ? "LiveKit WebRTC connected" : "Transport offline"}
          </p>
        </div>
        <div>
          <p className="eyebrow">Active epoch ID</p>
          <p className="mt-2 font-mono text-4xl font-bold text-cyan-300">
            #{epoch}
          </p>
        </div>
        <div>
          <p className="eyebrow">Last interruption cutoff</p>
          <p className="mt-2 font-mono text-3xl font-bold text-emerald-300">
            {cutoffMs === null ? "Not measured" : `${cutoffMs.toFixed(1)} ms`}
          </p>
          <p className="mt-1 text-xs text-slate-400">
            Local energy-onset → graph mute; excludes device output latency.
          </p>
          <p className="mt-2 font-mono text-xs text-slate-400">
            Last receipt: {renderedMs.toFixed(0)} ms non-silent rendering
          </p>
        </div>
      </footer>
    );
  }