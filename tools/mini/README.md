# PXD Mini: a small helper in the browser that prompts the big models

Three tiers, one page (`/mini` on the PXD Gateway, "Mini" on PXD home):

| Tier | For | Runs | Does |
|---|---|---|---|
| **Tiny** | anything, even a 4 MB budget | no model | exact tools (counts; emails, phones, prices, dates, links; dedupe, sort, case; JSON; arithmetic; unit conversions), an answer cache, routing, briefs |
| **Mini** (Low / Medium / High power cap) | Pi 5, laptops | SmolLM2-360M or Qwen2.5-0.5B in a browser worker (CPU or WebGPU) | short writing: titles, summaries, rewrites, replies |
| **Big** | base1 (RTX 5080, 16 GB) | the models in Ollama (gpt-oss:20b, qwen, …) | real work, handed over as a condensed brief |

- **Two lanes run in parallel:** Mini in the browser, base1 on the network. The user keeps working while tasks finish.
- **Auto routing:** tools and cache first; small writing to Mini; code, plans, analysis and long material to base1. If Mini's answer looks weak (too short, repeating itself), it goes to base1 automatically.
- **Briefs:** the big model gets `TASK / OUTPUT / MATERIAL`, with duplicate lines removed and long middles trimmed. In testing, a 7,600-character paste became a 165-character brief.
- **Power cap:**
  - **Tiny:** no model.
  - **Low:** 1 CPU thread, short answers, a pause between tasks.
  - **Medium:** 2 threads or WebGPU.
  - **High:** 4 threads or WebGPU, longer answers.
  - Mini does one job at a time.
- **Offline:** the runtime and weights come from the gateway (`/mini-assets/`); the browser never reaches the internet (`allowRemoteModels = false`).

## Set up on base1 (once, with internet)
```
python tools/mini/setup_mini.py                      # transformers.js 3.8.1 (npm, SHA-512 checked) + SmolLM2-360M-Instruct
python tools/mini/setup_mini.py --model qwen2.5-0.5b # optional, a bit stronger
python tools/gateway/pxd_gateway.py ... --mini "%USERPROFILE%\PXD Gateway\mini"
```
Then open `http://base1:8790/mini` on any Pi or laptop.

**Tested here:**
- the Tiny tools, the cache, auto and manual routing
- weak-answer handoff, two lanes in parallel, brief condensing
- the gateway proxy refusing models that aren't installed
- the real transformers.js runtime loading offline in a browser worker

**Not tested:** the 360M model producing text. Hugging Face is blocked in this workspace, so run `setup_mini.py` on base1.

**Next:** the Tiny tier as MicroPython on ESP32-class boards (see PxD2/numerical-sentencing `agents/esp32_profile.py`), sending numeric (lex/COG) sentences to base1 over Lit or LoRa.
