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
    <main className="mx-auto min-h-screen max-w-[1800px] px-6 py-8 lg:px-12">
      <header className="flex flex-wrap items-center justify-between gap-5 border-b border-slate-800 pb-6">
        <div>
          <p className="text-sm font-bold tracking-[0.25em] text-cyan-300">
            TEAM HTTP200 · DATAFORGE · RIME TRACK
          </p>
          <h1 className="mt-3 text-4xl font-black tracking-tight lg:text-5xl">
            ScrubSync <span className="text-cyan-300">AI</span>
          </h1>
        </div>
        <div className="text-right">
          <p className="font-mono text-lg text-slate-200">Voice assistant</p>
          <p className="mt-1 text-sm text-amber-300">
            Ask anything · Live web lookup when needed · Not professional advice
          </p>
        </div>
      </header>

      {!terminal.connected && (
        <form
          onSubmit={(event) => void arm(event)}
          className="panel mt-8 flex flex-wrap items-end gap-4"
        >
          <label className="flex min-w-64 flex-1 flex-col gap-2">
            <span className="text-sm font-semibold text-slate-300">
              Pre-sterile terminal provisioning secret
            </span>
            <input
              type="password"
              value={secret}
              onChange={(event) => setSecret(event.target.value)}
              autoComplete="off"
              required
              disabled={terminal.connecting}
              className="rounded-lg border border-slate-600 bg-slate-950 px-4 py-3 text-lg outline-none focus:border-cyan-400"
            />
          </label>
          <button
            type="submit"
            disabled={terminal.connecting}
            className="rounded-lg bg-cyan-300 px-7 py-3 text-lg font-extrabold text-slate-950 disabled:opacity-50"
          >
            {terminal.connecting ? "Connecting…" : "Arm hands-free terminal"}
          </button>
          <p className="w-full text-sm text-slate-400">
            Arm the terminal, then ask anything by voice — health, recipes,
            cricket scores, personal advice, and more. Interrupt anytime.
          </p>
        </form>
      )}

      {terminal.error && (
        <div
          role="alert"
          className="mt-6 rounded-xl border border-rose-700 bg-rose-950/40 p-5 text-xl text-rose-200"
        >
          {terminal.error}
        </div>
      )}

      <div className="my-10 grid items-center gap-10 lg:grid-cols-[0.8fr_1.2fr]">
        <StatusBeacon state={terminal.state} />
        <div className="space-y-6">
          <MetricReadout result={terminal.result} />
          <section className="panel">
            <p className="eyebrow">Voice pipeline · judge’s view</p>
            <p className="mt-4 min-h-8 text-xl text-slate-200">
              {terminal.transcript ||
                terminal.tool ||
                "Ask anything — health, food, sports, advice…"}
            </p>
            <p className="mt-5 text-sm font-bold uppercase tracking-wider text-violet-300">
              Intended speech, not a word-level heard transcript
            </p>
            <p className="mt-2 min-h-7 text-xl text-slate-300">
              {terminal.intendedSpeech || "No authorized speech segment"}
            </p>
          </section>
        </div>
      </div>

      <Telemetry
        epoch={terminal.epoch}
        cutoffMs={terminal.cutoffMs}
        renderedMs={terminal.renderedMs}
        connected={terminal.connected}
      />

      <div className="mt-6 flex flex-wrap items-center justify-between gap-4 text-sm text-slate-500">
        <p>
          Hands busy. Eyes busy. Voice required. Stale epochs have no playback authority.
        </p>
        {terminal.connected && (
          <button
            onClick={() => void terminal.disconnect()}
            className="rounded border border-slate-700 px-4 py-2 text-slate-300"
          >
            Disarm terminal
          </button>
        )}
      </div>
    </main>
  );
}