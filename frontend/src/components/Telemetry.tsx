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
      <footer className="grid gap-6 rounded-2xl border border-white/10 bg-white/[0.03] p-6 backdrop-blur-xl md:grid-cols-2 xl:grid-cols-4">
        <div>
          <p className="eyebrow">Active TTS engine</p>
          <p className="mt-2 text-xl font-bold text-zinc-100">Rime</p>
          <p className="mt-1 font-mono text-sm text-zinc-400">
            mist / amber / pcm_24000
          </p>
        </div>
        <div>
          <p className="eyebrow">Orchestration model</p>
          <p className="mt-2 text-xl font-bold text-zinc-100">Qwen 2.5</p>
          <p className="mt-1 text-sm text-zinc-500">
            {connected ? "LiveKit WebRTC connected" : "Transport offline"}
          </p>
        </div>
        <div>
          <p className="eyebrow">Active epoch ID</p>
          <p className="mt-2 font-mono text-4xl font-bold text-white">
            #{epoch}
          </p>
        </div>
        <div>
          <p className="eyebrow">Last interruption cutoff</p>
          <p className="mt-2 font-mono text-3xl font-bold text-white">
            {cutoffMs === null ? "Not measured" : `${cutoffMs.toFixed(1)} ms`}
          </p>
          <p className="mt-1 text-xs text-zinc-500">
            Local energy-onset → graph mute; excludes device output latency.
          </p>
          <p className="mt-2 font-mono text-xs text-zinc-500">
            Last receipt: {renderedMs.toFixed(0)} ms non-silent rendering
          </p>
        </div>
      </footer>
    );
  }