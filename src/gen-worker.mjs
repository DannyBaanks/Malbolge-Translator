// gen-worker.mjs — el generador sufre en su propio hilo; la UI ni se entera.
import { generateToolkit, ToolkitPaused, ToolkitTimeout } from "./toolkit-gen.mjs";
import { generar, GenPaused, GenTimeout } from "./meowbolge-gen.mjs";

const pauseFlags = new Set();

if (typeof self !== "undefined" && typeof self.postMessage === "function") {
  self.onmessage = (ev) => {
    const d = ev.data || {};
    if (d.cmd === "pause") {
      pauseFlags.add(d.id);
      return;
    }
    if (d.cmd !== "gen") return;

    const { id, texto, ancho, deadlineMs = 20_000 } = d;
    const beat = setInterval(() => self.postMessage({ type: "beat", id }), 400);
    const started = Date.now();

    const onProgress = (p, engine) => self.postMessage({
      type: "prog",
      id,
      engine,
      i: p.i,
      total: p.total,
      charsDone: p.cells ?? p.fuente?.length ?? 0,
    });

    try {
      let program;
      let engine = "toolkit-bfs";

      try {
        // Primary generator: fast snapshot/BFS path. It turns "hola" into one
        // verified Malbolge program instead of merely reporting a safe timeout.
        const primaryBudget = Math.max(1000, Math.floor(deadlineMs * 0.8));
        program = generateToolkit(texto, {
          deadlineMs: primaryBudget,
          shouldPause: () => pauseFlags.has(id),
          onProgress: (p) => onProgress(p, engine),
        });
      } catch (e) {
        if (e instanceof ToolkitPaused) throw e;
        if (!(e instanceof ToolkitTimeout)) throw e;

        // Secondary generator preserves the older toroidal route for strings
        // where it happens to find a path the primary search does not.
        engine = "toroidal-fallback";
        const remaining = Math.max(500, deadlineMs - (Date.now() - started));
        program = generar(texto, {
          ancho,
          deadlineMs: remaining,
          shouldPause: () => pauseFlags.has(id),
          onProgress: (p) => onProgress(p, engine),
        });
      }

      self.postMessage({ type: "done", id, program, engine });
    } catch (e) {
      if (e instanceof ToolkitPaused || e instanceof GenPaused) {
        pauseFlags.delete(id);
        self.postMessage({ type: "paused", id, nextIndex: e.payload?.nextIndex ?? 0 });
      } else {
        const msg = String(e.message || e);
        const timeout = e instanceof ToolkitTimeout || e instanceof GenTimeout || msg.startsWith("GEN_TIMEOUT");
        self.postMessage({ type: "error", id, timeout, message: msg });
      }
    } finally {
      clearInterval(beat);
    }
  };
}
