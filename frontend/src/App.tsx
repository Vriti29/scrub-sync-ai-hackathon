import { useState } from "react";
import type { FormEvent } from "react";
import { MetricReadout } from "./components/MetricReadout";
import { StatusBeacon } from "./components/StatusBeacon";
import { Telemetry } from "./components/Telemetry";
import { useLiveKitAudio } from "./hooks/useLiveKitAudio";

export default function App() {
  const terminal = useLiveKitAudio();
  const [secret, setSecret] = useState("");

  async function arm(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const provisioningSecret = secret;
    setSecret("");
    await terminal.connect(provisioningSecret);
  }

  return (
    <main className="mx-auto min-h-screen max-w-[1700px] px-6 py-8 selection:bg-cyan-500/20 lg:px-12">
      {/* Top Clinical Header */}
      <header className="flex flex-wrap items-center justify-between gap-6 border-b border-zinc-800/80 pb-6">
        <div>
          <div className="flex items-center gap-3">
            <span className="inline-flex items-center gap-1.5 rounded-md border border-cyan-500/30 bg-cyan-950/40 px-2.5 py-0.5 font-mono text-[11px] font-medium tracking-wider text-cyan-400">
              <span className="h-1.5 w-1.5 rounded-full bg-cyan-400 animate-pulse" />
              TEAM HTTP200 · RIME TRACK
            </span>
            <span className="font-mono text-xs text-zinc-500">v1.0-CLINICAL-ALPHA</span>
          </div>

          <h1 className="mt-3 text-4xl font-black tracking-tight text-zinc-100 lg:text-5xl">
            ScrubSync <span className="text-cyan-400">AI</span>
          </h1>
        </div>

        <div className="text-right">
          <div className="flex items-center justify-end gap-2">
            <span className="rounded-full bg-zinc-800 px-3 py-1 font-mono text-xs text-zinc-300 border border-zinc-700/50">
              Sub-ms Barge-In
            </span>
            <span className="rounded-full bg-zinc-800 px-3 py-1 font-mono text-xs text-zinc-300 border border-zinc-700/50">
              Zero-Leakage Memory
            </span>
          </div>
          <p className="mt-2 text-xs font-mono tracking-tight text-zinc-500">
            Clinical Telemetry & Critical Voice Engine
          </p>
        </div>
      </header>

      {/* Terminal Provisioning Form */}
      {!terminal.connected && (
        <form
          onSubmit={(event) => void arm(event)}
          className="mt-8 rounded-2xl border border-zinc-800/80 bg-zinc-900/40 p-6 shadow-xl backdrop-blur-md transition-all hover:border-zinc-700/60"
        >
          <div className="flex flex-wrap items-end gap-4">
            <label className="flex min-w-64 flex-1 flex-col gap-2">
              <span className="font-mono text-xs uppercase tracking-wider text-zinc-400">
                Pre-sterile terminal provisioning secret
              </span>
              <input
                type="password"
                value={secret}
                onChange={(event) => setSecret(event.target.value)}
                autoComplete="off"
                required
                disabled={terminal.connecting}
                placeholder="Enter room or deployment secret..."
                className="rounded-xl border border-zinc-700/70 bg-black/60 px-4 py-3 text-base text-zinc-100 outline-none transition placeholder:text-zinc-600 focus:border-cyan-500 focus:ring-1 focus:ring-cyan-500"
              />
            </label>

            <button
              type="submit"
              disabled={terminal.connecting}
              className="inline-flex items-center justify-center gap-2 rounded-xl bg-cyan-500 px-6 py-3.5 font-semibold text-black shadow-[0_0_25px_rgba(6,182,212,0.3)] transition-all hover:bg-cyan-400 hover:shadow-[0_0_35px_rgba(6,182,212,0.5)] active:scale-[0.98] disabled:opacity-50"
            >
              {terminal.connecting ? (
                <>
                  <span className="h-4 w-4 border-2 border-black border-t-transparent rounded-full animate-spin" />
                  Connecting…
                </>
              ) : (
                <>
                  <svg
                    className="h-4 w-4 text-black"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="2.5"
                    viewBox="0 0 24 24"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 18.75a6 6 0 0 0 6-6v-1.5m-6 7.5a6 6 0 0 1-6-6v-1.5m6 7.5v3.75m-3.75 0h7.5M12 15.75a3 3 0 0 1-3-3V4.5a3 3 0 1 1 6 0v8.25a3 3 0 0 1-3 3Z"
                    />
                  </svg>
                  Arm hands-free terminal
                </>
              )}
            </button>
          </div>

          <p className="mt-4 font-mono text-xs text-zinc-500">
            Arming binds local micro-VAD and low-latency WebRTC streams. Voice queries are processed locally with sub-ms zero-pop cancellation.
          </p>
        </form>
      )}

      {/* Error Alert */}
      {terminal.error && (
        <div
          role="alert"
          className="mt-6 flex items-center gap-3 rounded-xl border border-rose-500/30 bg-rose-950/20 p-4 font-mono text-sm text-rose-300 backdrop-blur-xl"
        >
          <span className="h-2 w-2 rounded-full bg-rose-500 animate-ping" />
          <span>{terminal.error}</span>
        </div>
      )}

      {/* Center Console Grid */}
      <div className="my-10 grid items-stretch gap-8 lg:grid-cols-[0.8fr_1.2fr]">
        <StatusBeacon state={terminal.state} />

        <div className="flex flex-col justify-between gap-6">
          <MetricReadout result={terminal.result} />

          <section className="flex-1 rounded-2xl border border-zinc-800/80 bg-zinc-900/30 p-6 backdrop-blur-md shadow-lg">
            <div className="flex items-center justify-between border-b border-zinc-800/80 pb-3">
              <p className="font-mono text-xs uppercase tracking-widest text-cyan-400">
                Voice pipeline · live judge’s view
              </p>
              <span className="rounded bg-zinc-800/80 px-2 py-0.5 font-mono text-[10px] text-zinc-400">
                ACTIVE-INGEST
              </span>
            </div>

            <div className="mt-4">
              <span className="font-mono text-[11px] uppercase tracking-wider text-zinc-500">
                Incoming Utterance / Tool State
              </span>
              <p className="mt-1 min-h-12 text-xl font-medium text-zinc-100">
                {terminal.transcript ||
                  terminal.tool ||
                  "Awaiting voice command (e.g. 'Check electrolytes for DEMO-001')…"}
              </p>
            </div>

            <div className="my-4 h-px w-full bg-zinc-800/60" />

            <div>
              <span className="font-mono text-[11px] uppercase tracking-wider text-zinc-500">
                Authorized Audio Output
              </span>
              <p className="mt-1 min-h-10 text-lg font-mono text-cyan-300/90">
                {terminal.intendedSpeech || "No authorized speech segment"}
              </p>
            </div>
          </section>
        </div>
      </div>

      {/* Telemetry Bar */}
      <Telemetry
        epoch={terminal.epoch}
        cutoffMs={terminal.cutoffMs}
        renderedMs={terminal.renderedMs}
        connected={terminal.connected}
      />

      <div className="mt-6 flex items-center justify-between pb-20 text-xs font-mono text-zinc-500">
        <p>Hands busy. Eyes busy. Voice required. Stale epochs have no playback authority.</p>
        <span className="text-zinc-600">SCRUB-SYNC-FAILSAFE-ACTIVE</span>
      </div>

      {/* Floating Disarm Action */}
      {terminal.connected && (
        <button
          onClick={() => void terminal.disconnect()}
          className="disarm-fab group border border-rose-500/40 bg-zinc-900/90 text-rose-400 shadow-[0_0_20px_rgba(244,63,94,0.15)] transition-all hover:border-rose-400 hover:bg-rose-500 hover:text-white hover:shadow-[0_0_30px_rgba(244,63,94,0.4)]"
          aria-label="Disarm terminal"
          title="Disarm terminal"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2.5"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
            className="transition-transform group-hover:scale-110"
          >
            <path d="M12 2v10" />
            <path d="M18.4 6.6a9 9 0 1 1-12.77.04" />
          </svg>
          <span className="font-semibold tracking-wide">Disarm terminal</span>
        </button>
      )}
    </main>
  );
}