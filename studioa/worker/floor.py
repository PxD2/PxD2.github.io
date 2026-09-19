#!/usr/bin/env python3
"""Studio A floor — run on the 5080. No UI. Git holds the pages; this box cuts film."""
from __future__ import annotations

import json, os, re, sys, threading, time, uuid, base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "can"
JOBS = ROOT / "jobs"
INBOX = Path(os.environ.get("STUDIOA_INBOX", str(ROOT / "inbox")))
BIBLE = Path(os.environ.get("STUDIOA_BIBLE", str(ROOT / "bible")))
PORT = int(os.environ.get("STUDIOA_PORT", "8189"))
HOST = os.environ.get("STUDIOA_HOST", "0.0.0.0")
GIT = os.environ.get("STUDIOA_GIT", "")

OUT.mkdir(exist_ok=True)
JOBS.mkdir(exist_ok=True)
INBOX.mkdir(exist_ok=True)

lock = threading.Lock()
state: dict = {"jobs": {}, "gpu": None}


def gpu_info():
    try:
        import torch
        if not torch.cuda.is_available():
            return {"ok": False, "error": "CUDA not visible"}
        i = torch.cuda.current_device()
        p = torch.cuda.get_device_properties(i)
        return {
            "ok": True,
            "name": torch.cuda.get_device_name(i),
            "vram_gb": round(p.total_memory / 1024**3, 1),
            "index": i,
        }
    except Exception as e:
        return {"ok": False, "error": str(e)[:200]}


def slate(script: str) -> list[dict]:
    blocks = [b.strip() for b in re.split(r"\n\s*\n", script.strip()) if b.strip()]
    shots = []
    for b in blocks:
        line = b.split("\n")[0][:80]
        shots.append({
            "title": line[:60],
            "prompt": "Pixar-quality 3D CGI children's film, original, not Toy Story. 1770s North Carolina Piedmont. " + re.sub(r"\s+", " ", b)[:400],
            "sec": 10,
        })
    return shots[:48] or [{"title": "Take", "prompt": script[:400], "sec": 10}]


def save_data_url(url: str, dest: Path):
    m = re.match(r"data:(image/[\w+.-]+);base64,(.+)$", url, re.S)
    if not m:
        return False
    dest.write_bytes(base64.b64decode(m.group(2)))
    return True


def refs_for(job_dir: Path) -> list[Path]:
    pics = []
    for folder in (job_dir / "stocks", BIBLE):
        if folder.is_dir():
            pics += sorted(p for p in folder.iterdir() if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"})
    return pics[:5]


def render_shot(prompt: str, refs: list[Path], still_path: Path, video_path: Path) -> str:
    """Returns 'still' or 'video'. Hidden pipeline — do not expose to the hall."""
    import torch
    from PIL import Image
    from diffusers import AutoPipelineForText2Image

    device = "cuda"
    pipe = AutoPipelineForText2Image.from_pretrained(
        os.environ.get("STUDIOA_STILL_MODEL", "stabilityai/sdxl-turbo"),
        torch_dtype=torch.float16,
        variant="fp16",
    ).to(device)
    kwargs = dict(prompt=prompt, num_inference_steps=4, guidance_scale=0.0)
    if refs:
        try:
            from diffusers import StableDiffusionXLImg2ImgPipeline
            img = Image.open(refs[0]).convert("RGB").resize((1024, 576))
            i2i = StableDiffusionXLImg2ImgPipeline(**pipe.components).to(device)
            out = i2i(prompt=prompt, image=img, strength=0.55, num_inference_steps=6, guidance_scale=1.2).images[0]
        except Exception:
            out = pipe(**kwargs).images[0]
    else:
        out = pipe(**kwargs).images[0]
    out = out.resize((1280, 720))
    still_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(still_path, quality=92)
    del pipe
    torch.cuda.empty_cache()

    vmodel = os.environ.get("STUDIOA_VIDEO_MODEL", "stabilityai/stable-video-diffusion-img2vid-xt")
    try:
        from diffusers import StableVideoDiffusionPipeline
        vid = StableVideoDiffusionPipeline.from_pretrained(
            vmodel, torch_dtype=torch.float16, variant="fp16"
        ).to(device)
        frames = vid(out, decode_chunk_size=4, num_frames=25).frames[0]
        write_mp4(frames, video_path)
        del vid
        torch.cuda.empty_cache()
        return "video"
    except Exception:
        return "still"


def write_mp4(frames, dest: Path):
    import subprocess, tempfile
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        for i, fr in enumerate(frames):
            fr.save(td / f"{i:04d}.png")
        subprocess.run(
            ["ffmpeg", "-y", "-framerate", "8", "-i", str(td / "%04d.png"),
             "-c:v", "libx264", "-pix_fmt", "yuv420p", str(dest)],
            check=False, capture_output=True,
        )


def run_job(job: dict):
    jid = job["id"]
    job_dir = OUT / jid
    job_dir.mkdir(exist_ok=True)
    with lock:
        job["status"] = "on the floor"
        persist(job)
    shots = slate(job["script"])
    job["shots"] = []
    refs = refs_for(job_dir)
    try:
        for i, s in enumerate(shots[: int(os.environ.get("STUDIOA_BATCH", "6"))]):
            still = job_dir / f"{i:02d}.jpg"
            video = job_dir / f"{i:02d}.mp4"
            kind = render_shot(s["prompt"], refs, still, video)
            rec = {
                "slot": i,
                "title": s["title"],
                "prompt": s["prompt"],
                "still": f"/can/{jid}/{i:02d}.jpg",
                "video": f"/can/{jid}/{i:02d}.mp4" if kind == "video" and video.exists() else None,
                "sec": 10 if kind == "video" else 3,
            }
            job["shots"].append(rec)
            persist(job)
        job["status"] = "in the can"
    except Exception as e:
        job["status"] = "stopped"
        job["error"] = str(e)[:300]
    persist(job)
    maybe_git_push(job_dir)


def persist(job: dict):
    (JOBS / f"{job['id']}.json").write_text(json.dumps(job, indent=2), encoding="utf-8")
    with lock:
        state["jobs"][job["id"]] = job


def maybe_git_push(job_dir: Path):
    if not GIT:
        return
    import subprocess
    subprocess.run(["git", "-C", GIT, "pull", "--rebase"], capture_output=True)
    dest = Path(GIT) / "studioa" / "can" / job_dir.name
    dest.mkdir(parents=True, exist_ok=True)
    for p in job_dir.iterdir():
        dest.joinpath(p.name).write_bytes(p.read_bytes())
    subprocess.run(["git", "-C", GIT, "add", "studioa/can"], capture_output=True)
    subprocess.run(["git", "-C", GIT, "commit", "-m", f"Studio A can {job_dir.name}"], capture_output=True)
    subprocess.run(["git", "-C", GIT, "push"], capture_output=True)


def watch_inbox():
    seen = ""
    while True:
        script_p = INBOX / "script.txt"
        if script_p.exists():
            text = script_p.read_text(encoding="utf-8", errors="replace")
            if text.strip() and text != seen:
                seen = text
                job = new_job(text, [])
                stocks = INBOX / "stocks"
                if stocks.is_dir():
                    d = OUT / job["id"] / "stocks"
                    d.mkdir(parents=True, exist_ok=True)
                    for p in stocks.iterdir():
                        if p.suffix.lower() in {".jpg", ".jpeg", ".png", ".webp"}:
                            (d / p.name).write_bytes(p.read_bytes())
                threading.Thread(target=run_job, args=(job,), daemon=True).start()
        time.sleep(4)


def new_job(script: str, stocks: list[str]) -> dict:
    jid = uuid.uuid4().hex[:10]
    job = {"id": jid, "status": "queued", "script": script, "shots": []}
    d = OUT / jid / "stocks"
    d.mkdir(parents=True, exist_ok=True)
    for i, url in enumerate(stocks[:3]):
        save_data_url(url, d / f"stock-{i}.jpg")
    persist(job)
    return job


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *_a):
        return

    def cors(self):
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Headers", "content-type")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,OPTIONS")

    def send_json(self, code, obj):
        b = json.dumps(obj).encode()
        self.send_response(code)
        self.cors()
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(b)))
        self.end_headers()
        self.wfile.write(b)

    def do_OPTIONS(self):
        self.send_response(204)
        self.cors()
        self.end_headers()

    def do_GET(self):
        u = urlparse(self.path)
        if u.path == "/health":
            g = state["gpu"] or gpu_info()
            state["gpu"] = g
            return self.send_json(200, {"floor": "studio-a", **g, "jobs": len(state["jobs"])})
        if u.path in ("/", "/hall", "/hall.html"):
            hall = ROOT / "hall.html"
            data = hall.read_bytes() if hall.is_file() else b"<p>Studio A floor</p>"
            self.send_response(200)
            self.cors()
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if u.path == "/jobs":
            return self.send_json(200, {"jobs": list(state["jobs"].values())})
        m = re.match(r"^/job/([\w-]+)$", u.path)
        if m:
            job = state["jobs"].get(m.group(1))
            if not job:
                p = JOBS / f"{m.group(1)}.json"
                job = json.loads(p.read_text()) if p.exists() else None
            return self.send_json(200 if job else 404, job or {"error": "gone"})
        m = re.match(r"^/can/([\w-]+)/(.+)$", u.path)
        if m:
            f = OUT / m.group(1) / m.group(2)
            if not f.is_file() or ".." in m.group(2):
                self.send_response(404)
                self.end_headers()
                return
            mime = "image/jpeg" if f.suffix == ".jpg" else "video/mp4" if f.suffix == ".mp4" else "application/octet-stream"
            data = f.read_bytes()
            self.send_response(200)
            self.cors()
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_json(404, {"error": "no"})

    def do_POST(self):
        if urlparse(self.path).path != "/job":
            return self.send_json(404, {"error": "no"})
        n = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(n) or b"{}")
        script = str(body.get("script") or "").strip()
        if not script:
            return self.send_json(400, {"error": "Need a script."})
        job = new_job(script, list(body.get("stocks") or []))
        threading.Thread(target=run_job, args=(job,), daemon=True).start()
        self.send_json(202, {"id": job["id"], "status": job["status"]})


def main():
    state["gpu"] = gpu_info()
    threading.Thread(target=watch_inbox, daemon=True).start()
    httpd = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Studio A floor on {HOST}:{PORT}", file=sys.stderr)
    if state["gpu"].get("ok"):
        print(state["gpu"]["name"], state["gpu"]["vram_gb"], "GB", file=sys.stderr)
    else:
        print("GPU packs not loaded yet. pip install -r requirements.txt", file=sys.stderr)
    httpd.serve_forever()


if __name__ == "__main__":
    main()
