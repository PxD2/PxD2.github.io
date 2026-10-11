# PXD Operator: an offline agent that does tasks on the computer

You type what you want done. PXD Operator looks at the screen, asks your local model in Ollama for the next step, moves the mouse and keyboard (or works inside a browser), and repeats until it's done, needs you, or hits a limit. It runs on base1 with no cloud and no billed tokens.

```
pip install -r requirements.txt
python -m playwright install chromium
run_operator.bat        (or: python pxd_operator.py --model qwen2.5:14b)  →  http://127.0.0.1:8793
```

## How it sees and acts
| Surface | Sees | Acts |
|---|---|---|
| **Whole desktop** | screenshot + OCR (RapidOCR, bundled models) + Windows accessibility tree (uiautomation) | PyAutoGUI; on Linux without Tk, the operator's own XTest driver |
| **Browser** | the page's real buttons, links, fields and dropdowns (Playwright) | clicks, typing and choices on those elements directly |

Everything on screen gets a number. The model answers with one action in JSON (`click 12`, `type 7 "hello"`, `key ctrl+s`, `ask`, `done`), so text-only models can operate a screen. Vision models (qwen2.5vl) can also get the screenshot with the numbers drawn on it.

## Safety (on by default)
- **Permission:**
  - **Ask before risky steps** (default): anything that could pay, send, delete, submit, sign in, install or publish, any typing into password fields, and pressing Enter on a screen with such a button. Each pauses for your yes or no.
  - **Ask every step:** every action pauses.
  - **Don't ask:** you're trusting it.
- **No shell action exists.** It cannot run commands.
- **STOP button.** On the desktop, throwing the mouse into any screen corner halts it instantly.
- **Limits:** a step limit (40 by default), a stuck detector (3 actions that change nothing), and a stop after 3 malformed model replies.
- **Logs:** every step is saved with its screenshot in `~/PXD Operator/runs/<id>/`.
- **Network:** the control page listens on this machine only; listening on the network requires `--token`.

## Workflows
Save any finished run, then replay it. Replays find each element by its label, not its position, so a replay usually needs **no model at all**. If a label has changed, the model handles just that step. Put `{{name}}` in a workflow's typed text (in `~/PXD Operator/workflows/<name>.json`) to fill it in at run time.

## Models (Ollama, offline)
Any chat model works; JSON replies are enforced.
- **qwen2.5:14b** (Apache-2.0): a good default on the RTX 5080.
- **gpt-oss:20b** (Apache-2.0): stronger planning.
- **qwen2.5vl:7b** (Apache-2.0): add it when screenshots should be seen too.

## Tested here
- **Browser:** a full task; a risky Pay step paused and declined; asking the person and using the answer; recovery from a model answering in prose; a workflow saved and replayed with 0 model calls and a `{{shop}}` fill-in; STOP mid-run; refusal of bad input.
- **Desktop, on a virtual X screen with real OCR and real XTest input:** read the screen, typed into a field, clicked Save, confirmed the result by OCR.
- **The model was a scripted stand-in** for Ollama. Real-model quality runs on base1.
- **Not tested here:** the Windows accessibility tree.
