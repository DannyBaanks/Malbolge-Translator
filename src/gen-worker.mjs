// gen-worker.mjs — el generador sufre en su propio hilo; la UI ni se enterA.
import { generar, GenTimeout, GenPaused } from "./meowbolge-gen.mjs";

const pauseFlags = new Set();

if (typeof self !== "undefined" && typeof self.postMessage === "function") {
  self.onmessage = (ev) => {
    const d = ev.data || {};
    if (d.cmd === "pause") { pauseFlags.add(d.id); return; }
    if (d.cmd !== "gen") return;
    const { id, texto, ancho, deadlineMs } = d;
    const beat = setInterval(() => self.postMessage({ type: "beat", id }), 400);
    try {
      const prog = generar(texto, {
        ancho,
        deadlineMs,
        shouldPause: () => pauseFlags.has(id),
        onProgress: (p) => self.postMessage({
          type: "prog", id, i: p.i, total: p.total,
          charsDone: p.fuente.length,
        }),
      });
      self.postMessage({ type: "done", id, program: prog });
    } catch (e) {
      if (e instanceof GenPaused) {
        pauseFlags.delete(id);
        self.postMessage({ type: "paused", id, nextIndex: e.payload.nextIndex });
      } else {
        const timeout = e instanceof GenTimeout || String(e.message).startsWith("GEN_TIMEOUT");
        self.postMessage({ type: "error", id, timeout, message: String(e.message) });
      }
    } finally {
      clearInterval(beat);
    }
  };
}
