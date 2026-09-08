/*
 * Runs on the audio rendering thread.
 *
 * Input 0: echo-cancelled local microphone (barge-in energy gate only).
 * Remote Rime audio is played via HTMLMediaElement outside this worklet.
 *
 * This is an energy gate, not Silero and not a clinical-grade VAD.
 * Server Silero is authoritative for transcription segmentation.
 */
class DuplexGate extends AudioWorkletProcessor {
    constructor(options) {
      super();
      const config = options.processorOptions || {};
      this.threshold = Number(config.threshold) || 0.05;
      this.attackSamples = Math.ceil(sampleRate * 0.1);
      this.releaseSamples = Math.ceil(sampleRate * 0.45);
      this.holdoffSamples = 0;
      this.highSamples = 0;
      this.lowSamples = 0;
      this.speaking = false;
      this.allowed = false;
      this.segment = null;
      this.renderedNonSilentSamples = 0;
      this.counter = 0;
  
      this.port.onmessage = (event) => {
        const message = event.data;
        if (message.type === "mute") {
          this.allowed = false;
          this.report(message.disposition || "interrupted", null);
        } else if (message.type === "allow") {
          if (this.segment) {
            this.report("replaced", null);
          }
          this.segment = {
            epoch: message.epoch,
            segment_id: message.segment_id
          };
          this.renderedNonSilentSamples = 0;
          this.allowed = true;
          // Ignore brief speaker→mic coupling while agent audio starts.
          this.holdoffSamples = Math.ceil(sampleRate * 0.4);
          this.highSamples = 0;
          this.lowSamples = 0;
        } else if (message.type === "report") {
          this.report(message.disposition || "snapshot", null);
        }
      };
    }
  
    report(disposition, cutoff) {
      if (!this.segment) return;
      this.port.postMessage({
        type: "receipt",
        ...this.segment,
        disposition,
        rendered_non_silent_ms:
          (this.renderedNonSilentSamples / sampleRate) * 1000,
        local_cutoff_ms: cutoff
      });
      if (disposition !== "snapshot") {
        this.segment = null;
        this.renderedNonSilentSamples = 0;
      }
    }
  
    process(inputs, outputs) {
      const output = outputs[0][0];
      const microphone = inputs[0] && inputs[0][0];
  
      // Remote audio is not mixed here; keep output silent.
      for (let i = 0; i < output.length; i++) {
        output[i] = 0;
      }
  
      if (this.holdoffSamples > 0) {
        this.holdoffSamples = Math.max(0, this.holdoffSamples - output.length);
        this.highSamples = 0;
        this.lowSamples = 0;
        this.counter += output.length;
        if (this.counter >= sampleRate) {
          this.counter = 0;
          this.report("snapshot", null);
        }
        return true;
      }
  
      let rms = 0;
      if (microphone && microphone.length) {
        let energy = 0;
        for (let i = 0; i < microphone.length; i++) {
          energy += microphone[i] * microphone[i];
        }
        rms = Math.sqrt(energy / microphone.length);
      }
  
      if (rms >= this.threshold) {
        this.highSamples += output.length;
        this.lowSamples = 0;
      } else {
        this.lowSamples += output.length;
        if (!this.speaking) this.highSamples = 0;
      }
  
      if (!this.speaking && this.highSamples >= this.attackSamples) {
        this.speaking = true;
        this.allowed = false;
        const cutoffMs = (this.highSamples / sampleRate) * 1000;
        this.report("interrupted", cutoffMs);
        this.port.postMessage({
          type: "speech_start",
          local_cutoff_ms: cutoffMs
        });
      }
  
      if (this.speaking && this.lowSamples >= this.releaseSamples) {
        this.speaking = false;
        this.highSamples = 0;
        this.port.postMessage({ type: "speech_end" });
      }
  
      // Telemetry: mark authorized playback windows (actual PCM is in the element).
      if (this.allowed && !this.speaking) {
        this.renderedNonSilentSamples += output.length;
      }
  
      this.counter += output.length;
      if (this.counter >= sampleRate) {
        this.counter = 0;
        this.report("snapshot", null);
      }
      return true;
    }
  }
  
  registerProcessor("duplex-gate", DuplexGate);
