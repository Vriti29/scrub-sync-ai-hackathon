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
      <header className="flex flex-wrap items-center justify-between gap-5 border-b border-white/10 pb-6">
        <div>
          <p className="text-sm font-semibold tracking-[0.25em] text-zinc-500">
            TEAM HTTP200 · DATAFORGE · RIME TRACK
          </p>
          <h1 className="mt-3 text-4xl font-black tracking-tight lg:text-5xl">
            ScrubSync <span className="text-zinc-500">AI</span>
          </h1>
        </div>
        <div className="text-right">
          <p className="font-mono text-lg text-zinc-200">Voice assistant</p>
          <p className="mt-1 text-sm text-zinc-500">
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
            <span className="text-sm font-semibold text-zinc-300">
              Pre-sterile terminal provisioning secret
            </span>
            <input
              type="password"
              value={secret}
              onChange={(event) => setSecret(event.target.value)}
              autoComplete="off"
              required
              disabled={terminal.connecting}
              className="rounded-xl border border-white/10 bg-black/40 px-4 py-3 text-lg text-zinc-100 outline-none transition placeholder:text-zinc-600 focus:border-white/40"
            />
          </label>
          <button type="submit" disabled={terminal.connecting} className="btn-primary">
            {terminal.connecting ? "Connecting…" : "Arm hands-free terminal"}
          </button>
          <p className="w-full text-sm text-zinc-500">
            Arm the terminal, then ask anything by voice — health, recipes,
            cricket scores, personal advice, and more. Interrupt anytime.
          </p>
        </form>
      )}

      {terminal.error && (
        <div
          role="alert"
          className="mt-6 rounded-xl border border-white/20 bg-white/[0.04] p-5 text-xl text-zinc-100 backdrop-blur-xl"
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
            <p className="mt-4 min-h-8 text-xl text-zinc-100">
              {terminal.transcript ||
                terminal.tool ||
                "Ask anything — health, food, sports, advice…"}
            </p>
            <div className="mt-5 h-px w-full bg-white/10" />
            <p className="mt-5 text-sm font-semibold uppercase tracking-wider text-zinc-500">
              Intended speech, not a word-level heard transcript
            </p>
            <p className="mt-2 min-h-7 text-xl text-zinc-300">
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

      <div className="mt-6 pb-20 text-sm text-zinc-600">
        <p>
          Hands busy. Eyes busy. Voice required. Stale epochs have no playback authority.
        </p>
      </div>

      {terminal.connected && (
        <button
          onClick={() => void terminal.disconnect()}
          className="disarm-fab"
          aria-label="Disarm terminal"
          title="Disarm terminal"
        >
          <svg
            width="16"
            height="16"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
            strokeLinecap="round"
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M12 2v10" />
            <path d="M18.4 6.6a9 9 0 1 1-12.77.04" />
          </svg>
          Disarm terminal
        </button>
      )}
    </main>
  );
}