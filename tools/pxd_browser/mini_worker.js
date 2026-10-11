/* PXD Mini worker: a small language model running inside the browser, off the page's main thread.
 * Runtime and weights are served by the PXD Gateway (/mini-assets/), so it runs with no internet.
 * Messages in:  {type: "load", assets, model, device: "auto"|"webgpu"|"wasm", dtypes: {webgpu, wasm}, threads}
 *               {type: "run", id, messages, max_new_tokens}
 * Messages out: {type: "status", state, text, progress?, device?} · {type: "token", id, text} · {type: "done", id, text, tokens, ms} · {type: "error", id?, text}
 * engine "test" (used only by automated tests): no model, a fixed rule-based reply.
 */
let gen = null, tok = null, TextStreamer = null, engine = "model";

function status(state, text, extra) { postMessage(Object.assign({ type: "status", state, text }, extra || {})); }

async function load(m) {
  if (m.engine === "test") { engine = "test"; status("ready", "Test engine (no model)", { device: "none" }); return; }
  status("loading", "Loading the runtime…");
  const T = await import(m.assets + "runtime/transformers.min.js");
  TextStreamer = T.TextStreamer;
  T.env.allowRemoteModels = false;                 // never reach the internet
  T.env.allowLocalModels = true;
  T.env.localModelPath = m.assets + "models/";
  T.env.backends.onnx.wasm.wasmPaths = m.assets + "runtime/";
  T.env.backends.onnx.wasm.numThreads = Math.max(1, Math.min(m.threads || 2, navigator.hardwareConcurrency || 2));
  let device = m.device === "auto" ? ((self.navigator && navigator.gpu && await navigator.gpu.requestAdapter().catch(() => null)) ? "webgpu" : "wasm") : m.device;
  const files = {};
  const progress = p => {
    if (p.status === "progress" && p.file) { files[p.file] = [p.loaded || 0, p.total || 0];
      const t = Object.values(files).reduce((a, b) => [a[0] + b[0], a[1] + b[1]], [0, 0]);
      status("loading", "Loading " + m.model + "…", { progress: t[1] ? t[0] / t[1] : 0 }); }
  };
  try {
    gen = await T.pipeline("text-generation", m.model, { device, dtype: m.dtypes[device], progress_callback: progress });
  } catch (e) {
    if (device !== "webgpu") throw e;
    device = "wasm"; status("loading", "WebGPU unavailable here, using the CPU…");
    gen = await T.pipeline("text-generation", m.model, { device, dtype: m.dtypes.wasm, progress_callback: progress });
  }
  tok = gen.tokenizer;
  status("ready", m.model + " on " + (device === "webgpu" ? "the GPU (WebGPU)" : "the CPU"), { device });
}

function testReply(messages) {
  const u = messages[messages.length - 1].content;
  const text = u.replace(/^[^:]*:\s*/, "").trim();
  if (/^rewrite as one clear instruction/i.test(u)) return text.split(/[.!?]/)[0].trim() + ".";
  if (/summari[sz]e/i.test(u)) return text.split(/(?<=[.!?])\s/)[0];
  if (/title/i.test(u)) return text.split(/\s+/).slice(0, 6).join(" ");
  if (/garble/i.test(u)) return "the the the the the the the the the the";
  return "Done: " + text.slice(0, 120);
}

async function run(m) {
  const t0 = performance.now();
  if (engine === "test") {
    const text = testReply(m.messages);
    for (const w of text.split(/(\s+)/)) postMessage({ type: "token", id: m.id, text: w });
    postMessage({ type: "done", id: m.id, text, tokens: text.split(/\s+/).length, ms: Math.round(performance.now() - t0) });
    return;
  }
  if (!gen) throw new Error("model not loaded");
  let out = "", n = 0;
  const streamer = new TextStreamer(tok, { skip_prompt: true, skip_special_tokens: true,
    callback_function: t => { out += t; n++; postMessage({ type: "token", id: m.id, text: t }); } });
  const res = await gen(m.messages, { max_new_tokens: m.max_new_tokens || 160, do_sample: false, repetition_penalty: 1.15, streamer });
  const last = res[0].generated_text;
  const text = (Array.isArray(last) ? last[last.length - 1].content : String(last)).trim() || out.trim();
  postMessage({ type: "done", id: m.id, text, tokens: n, ms: Math.round(performance.now() - t0) });
}

let chain = Promise.resolve();   // one job at a time: the cap is part of the design
onmessage = e => {
  const m = e.data;
  chain = chain.then(() => (m.type === "load" ? load(m) : run(m))).catch(err => postMessage({ type: "error", id: m.id, text: String(err && err.message || err) }));
};
