"""PXD Mini setup: download the in-browser runtime and a small model once, on base1, for offline use.

After this, the PXD Gateway serves everything from ~/PXD Gateway/mini, so every browser on the
network runs PXD Mini with no internet and no cloud.

    python setup_mini.py                         # SmolLM2-360M-Instruct (Apache-2.0), about 400M class
    python setup_mini.py --model qwen2.5-0.5b    # Qwen2.5-0.5B-Instruct (Apache-2.0), a little larger and stronger
    python setup_mini.py --list

Runtime: @huggingface/transformers 3.8.1 (Apache-2.0) from the npm registry, checked against npm's
published SHA-512. Model: ONNX weights (4-bit for CPU and 4-bit/fp16 for WebGPU) from Hugging Face,
picked from the repository's own file list.
"""
import argparse, base64, hashlib, io, json, os, sys, tarfile, urllib.request

RUNTIME = "3.8.1"
OUT = os.path.join(os.path.expanduser("~"), "PXD Gateway", "mini")
MODELS = {
    "smollm2-360m": {"name": "SmolLM2-360M-Instruct", "repos": ["HuggingFaceTB/SmolLM2-360M-Instruct", "onnx-community/SmolLM2-360M-Instruct-ONNX"], "license": "Apache-2.0"},
    "qwen2.5-0.5b": {"name": "Qwen2.5-0.5B-Instruct", "repos": ["onnx-community/Qwen2.5-0.5B-Instruct"], "license": "Apache-2.0"},
}
BASE_FILES = ["config.json", "generation_config.json", "tokenizer.json", "tokenizer_config.json", "special_tokens_map.json"]
WANT = ["onnx/model_q4f16.onnx", "onnx/model_q4.onnx"]  # WebGPU, then CPU (WASM)


def get(url, timeout=120):
    req = urllib.request.Request(url, headers={"User-Agent": "PXD-Mini-Setup/1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def download(url, dst):
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "PXD-Mini-Setup/1"})
    with urllib.request.urlopen(req, timeout=600) as r, open(dst + ".part", "wb") as f:
        total, done = int(r.headers.get("Content-Length") or 0), 0
        while True:
            chunk = r.read(1 << 20)
            if not chunk:
                break
            f.write(chunk); done += len(chunk)
            if total:
                print(f"\r  {os.path.basename(dst)}: {done / 1e6:.0f} / {total / 1e6:.0f} MB", end="", flush=True)
    os.replace(dst + ".part", dst); print()


def runtime(out):
    meta = json.loads(get(f"https://registry.npmjs.org/@huggingface/transformers/{RUNTIME}"))
    blob = get(meta["dist"]["tarball"], timeout=600)
    algo, want = meta["dist"]["integrity"].split("-", 1)
    if algo != "sha512" or base64.b64encode(hashlib.sha512(blob).digest()).decode() != want:
        raise SystemExit("runtime download does not match npm's published SHA-512; not installing it")
    rdir = os.path.join(out, "runtime"); os.makedirs(rdir, exist_ok=True)
    keep = {"package/dist/transformers.min.js", "package/dist/ort-wasm-simd-threaded.jsep.mjs", "package/dist/ort-wasm-simd-threaded.jsep.wasm", "package/LICENSE"}
    with tarfile.open(fileobj=io.BytesIO(blob), mode="r:gz") as t:
        for m in t.getmembers():
            if m.name in keep and m.isfile():
                open(os.path.join(rdir, os.path.basename(m.name)), "wb").write(t.extractfile(m).read())
    print(f"runtime: transformers.js {RUNTIME} (verified) -> {rdir}")


def model(out, key):
    spec = MODELS[key]
    for repo in spec["repos"]:
        try:
            files = {s["rfilename"] for s in json.loads(get(f"https://huggingface.co/api/models/{repo}"))["siblings"]}
        except Exception as e:  # noqa: BLE001
            print(f"  {repo}: {e}"); continue
        onnx = [f for f in WANT if f in files]
        if not onnx:
            print(f"  {repo}: no 4-bit ONNX weights, trying the next source"); continue
        mdir = os.path.join(out, "models", spec["name"])
        for f in [f for f in BASE_FILES if f in files] + onnx + [f + "_data" for f in onnx if f + "_data" in files]:
            download(f"https://huggingface.co/{repo}/resolve/main/{f}", os.path.join(mdir, *f.split("/")))
        return {"name": spec["name"], "source": repo, "license": spec["license"],
                "dtypes": {"webgpu": "q4f16" if "onnx/model_q4f16.onnx" in onnx else "q4", "wasm": "q4" if "onnx/model_q4.onnx" in onnx else "q4f16"}}
    raise SystemExit(f"no usable ONNX source for {spec['name']}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", default="smollm2-360m", choices=list(MODELS)); ap.add_argument("--out", default=OUT)
    ap.add_argument("--list", action="store_true"); ap.add_argument("--skip-runtime", action="store_true")
    a = ap.parse_args()
    if a.list:
        for k, v in MODELS.items():
            print(f"{k:<14} {v['name']}  ({v['license']})")
        return
    os.makedirs(a.out, exist_ok=True)
    if not a.skip_runtime:
        runtime(a.out)
    info = model(a.out, a.model)
    path = os.path.join(a.out, "manifest.json")
    man = json.load(open(path)) if os.path.exists(path) else {"runtime": RUNTIME, "models": {}}
    man["runtime"] = RUNTIME; man["models"][info["name"]] = info; man.setdefault("default", info["name"])
    json.dump(man, open(path, "w"), indent=1)
    print(f"ready: {info['name']} from {info['source']}. Start the gateway and open /mini.")


if __name__ == "__main__":
    sys.exit(main())
