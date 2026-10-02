#!/usr/bin/env python3
"""Async generation queue for long jobs (Seedance video etc.) via the existing relay Worker.

Why: the sandbox proxy cuts every api.cloudflare.com request at ~30 s and *.workers.dev is blocked,
so video generations cannot be awaited directly. We reuse the user's existing `rare-earth-v3-relay`
Worker (approved by the user; we never deploy/modify Workers). Its CRON-QUEUE path needs no hook secret:

    client  --KV PUT-->  job:<minuteBucket>:<jobId>  = {"model", "input"}
    relay cron (every minute) runs exactly the jobs of its own minute bucket with env.AI.run,
    deletes the job key, writes state:<jobId> (running) and then
        res:<jobId>   = {state: done|error, via: "cron", model, result, media:[{url,key,chunks,bytes,type}], t0, t1}
        media:<jobId>:<n>[:<chunk>]   (mirrored output files, 20 MB chunks, TTL 21 days)
    client  --KV GET-->  res:/media:  (Cloudflare KV REST API on api.cloudflare.com)

All our job ids start with "rewind/" so they never collide with the earlier projects' keys.

CLI:
    python3 tools/gen.py submit SPEC.json [SPEC2.json ...]   # spec = {model, input, tag, notes, [est_usd]}
    python3 tools/gen.py status [ID ...]
    python3 tools/gen.py collect [ID ...]                    # download finished media -> assets/gen/<tag>_<id>.<ext>
    python3 tools/gen.py wait ID [ID ...] [--timeout=1800]    # poll until done, then collect
    python3 tools/gen.py requeue ID                          # re-queue a job whose cron minute was missed
    python3 tools/gen.py estimate SPEC.json                  # cost estimate only, nothing submitted

In spec inputs any string "file:<path>" (relative to the repo root) is replaced by a data: URI at
submit time, e.g. "reference_audios": ["file:assets/tests/ref_audio_40s_5s.mp3"]. Seedance 2.5 accepts
data URIs for image / last_frame_image / reference_images / reference_videos / reference_audios, so no
hosting is needed. The whole job (with data URIs) must fit in one KV value (< 25 MiB).
"""
import base64
import fcntl
import glob
import json
import mimetypes
import os
import ssl
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from contextlib import contextmanager

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ACC = "78885e7db58a4c34423a7e62c8471b75"
API = f"https://api.cloudflare.com/client/v4/accounts/{ACC}"
RELAY = "rare-earth-v3-relay"                       # existing Worker, cron "* * * * *", bindings AI + JOBS
NS = os.environ.get("GEN_KV_NS", "5f8f1f387d37449a949ee68625bdc310")   # its JOBS namespace (rare-earth-v3-jobs)
PREFIX = "rewind/"
OUT = os.path.join(ROOT, "assets", "gen")
MANIFEST = os.path.join(OUT, "manifest.json")
CATALOG = os.path.join(ROOT, "docs", "gen_catalog")
PER_BUCKET = int(os.environ.get("GEN_PER_MINUTE", "2"))   # jobs started per cron minute (RE used 2)
LEAD_MIN = 2              # first bucket = now + 2 min (KV list is eventually consistent, ~60 s)
MAX_JOB_BYTES = 24 * 1024 * 1024
CA = "/root/.ccr/ca-bundle.crt"
_CTX = ssl.create_default_context(cafile=CA) if os.path.exists(CA) else ssl.create_default_context()


# ----------------------------------------------------------------------------- http / kv
def _req(method, url, data=None, headers=None, timeout=28):
    headers = dict(headers or {})
    tok = os.environ.get("CLOUDFLARE_API_TOKEN")
    if tok:
        headers["Authorization"] = f"Bearer {tok}"
    req = urllib.request.Request(url, data=data, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            return r.status, r.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def _kv_url(key):
    return f"{API}/storage/kv/namespaces/{NS}/values/{urllib.parse.quote(key, safe='')}"


def kv_get(key, raw=False, tries=3):
    for a in range(tries):
        try:
            st, b = _req("GET", _kv_url(key), timeout=28 if not raw else 60)
        except Exception as e:  # noqa: BLE001  (resets / proxy hiccups)
            if a == tries - 1:
                raise
            time.sleep(3 * (a + 1)); continue
        if st == 404:
            return None
        if st == 200:
            return b if raw else json.loads(b.decode())
        if a == tries - 1:
            raise RuntimeError(f"kv get {key} -> {st}: {b[:300]!r}")
        time.sleep(3 * (a + 1))


def kv_put(key, body: bytes):
    st, b = _req("PUT", _kv_url(key), body, {"Content-Type": "application/octet-stream"}, timeout=60)
    if st != 200:
        raise RuntimeError(f"kv put {key} -> {st}: {b[:300]!r}")


def kv_delete(key):
    _req("DELETE", _kv_url(key))


# ----------------------------------------------------------------------------- manifest (locked)
@contextmanager
def locked():
    """Exclusive lock around every read-modify-write of the manifest (parallel collectors raced in RE)."""
    os.makedirs(OUT, exist_ok=True)
    with open(MANIFEST + ".lock", "w") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            m = json.load(open(MANIFEST)) if os.path.exists(MANIFEST) else {}
            m.setdefault("relay", {"worker": RELAY, "kv_namespace": NS, "prefix": PREFIX})
            m.setdefault("jobs", {})
            yield m
            m["total_est_usd"] = round(sum(j.get("est_usd") or 0 for j in m["jobs"].values()
                                           if j.get("state") != "rejected"), 4)
            m["total_est_usd_done"] = round(sum(j.get("est_usd") or 0 for j in m["jobs"].values()
                                                if j.get("state") == "done"), 4)
            tmp = MANIFEST + ".tmp"
            with open(tmp, "w") as f:
                json.dump(m, f, indent=1)
            os.replace(tmp, MANIFEST)
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN)


def read_manifest():
    with locked() as m:
        return json.loads(json.dumps(m))


# ----------------------------------------------------------------------------- catalog / cost
def catalog(model):
    p = os.path.join(CATALOG, model.replace("/", "-") + ".json")
    return json.load(open(p)) if os.path.exists(p) else None


def estimate(model, inp):
    """Rough USD estimate from the catalog's pricing table. Returns (usd or None, explanation)."""
    c = catalog(model)
    if not c or not isinstance(c.get("pricing"), dict):
        return None, "no catalog pricing"
    p = c["pricing"]
    if "Per image" in p:
        n = inp.get("n") or inp.get("num_images") or 1
        return round(p["Per image"] * n, 4), f"{n} x {p['Per image']}/image"
    dur = inp.get("duration", inp.get("seconds"))
    if dur in (None, -1, "-1"):
        dur = 15  # 'auto' -> assume 15 s (upper-ish guess); actual unknown until done
    dur = float(dur)
    res = str(inp.get("resolution") or inp.get("size") or "")
    has_vid = bool(inp.get("reference_videos") or inp.get("video") or inp.get("reference_video"))
    cand = []
    if res:
        if any(" video input" in k or " non-video input" in k for k in p):
            cand.append(f"@{res} {'video' if has_vid else 'non-video'} input (per second)")
        if inp.get("generate_audio"):
            cand.append(f"@{res} w/ audio (per second)")
        cand.append(f"@{res} (per second)")
    cand.append("Default (per second)")
    for k in cand:
        if k in p:
            return round(p[k] * dur, 4), f"{dur:g}s x {p[k]} ({k})"
    return None, f"unrecognised pricing keys {list(p)}"


def validate(model, inp):
    c = catalog(model)
    if not c:
        return
    try:
        import jsonschema
    except ImportError:
        return
    sch = c.get("schema", {}).get("input")
    if sch:
        jsonschema.validate(inp, sch)


# Seedance 2.5's validator marks these as required (additionalProperties:false); fill sane defaults.
DEFAULTS = {
    "bytedance/seedance-2.5": {"duration": 5, "resolution": "480p", "aspect_ratio": "16:9", "fps": 24,
                               "camera_fixed": False, "watermark": False, "output_format": "mp4",
                               "use_virtual_avatar": False, "generate_audio": False},
}


def _resolve_files(v):
    if isinstance(v, str) and v.startswith("file:"):
        p = v[5:]
        p = p if os.path.isabs(p) else os.path.join(ROOT, p)
        mt = mimetypes.guess_type(p)[0] or "application/octet-stream"
        if p.endswith(".mp3"):
            mt = "audio/mpeg"
        return f"data:{mt};base64," + base64.b64encode(open(p, "rb").read()).decode()
    if isinstance(v, list):
        return [_resolve_files(x) for x in v]
    if isinstance(v, dict):
        return {k: _resolve_files(x) for k, x in v.items()}
    return v


def _summ(v):
    if isinstance(v, str) and v.startswith("data:"):
        return f"<data {v[5:].split(';')[0]} {len(v)//1024}KB>"
    if isinstance(v, list):
        return [_summ(x) for x in v]
    if isinstance(v, dict):
        return {k: _summ(x) for k, x in v.items()}
    return v


# ----------------------------------------------------------------------------- commands
def _pick_bucket(m):
    now = int(time.time() // 60) + LEAD_MIN
    used = {}
    for j in m["jobs"].values():
        if j.get("state") == "queued":
            used[j["bucket"]] = used.get(j["bucket"], 0) + 1
    b = now
    while used.get(b, 0) >= PER_BUCKET:
        b += 1
    return b


def submit(spec_path):
    spec = json.load(open(spec_path))
    model, tag = spec["model"], spec.get("tag", "job")
    if model.startswith("xai/grok-imagine-video"):
        raise SystemExit("Grok Imagine video needs output.upload_url (ZDR account); the relay has no upload "
                         "endpoint, so it is NOT supported here. See docs/GEN_OPS.md.")
    inp = {**DEFAULTS.get(model, {}), **spec["input"]}
    raw_inp = _resolve_files(inp)
    validate(model, raw_inp)
    est, why = estimate(model, inp)
    if spec.get("est_usd") is not None:
        est, why = float(spec["est_usd"]), "from spec"
    body = json.dumps({"model": model, "input": raw_inp}).encode()
    if len(body) > MAX_JOB_BYTES:
        raise SystemExit(f"job is {len(body)/2**20:.1f} MiB; KV value limit is 25 MiB. Shrink/re-encode refs.")
    short = uuid.uuid4().hex[:10]
    jid = f"{PREFIX}{tag}-{short}"
    with locked() as m:
        bucket = _pick_bucket(m)
        kv_put(f"job:{bucket}:{jid}", body)   # inside the lock so two submitters never overfill a bucket
        m["jobs"][jid] = {"id": short, "job": jid, "tag": tag, "model": model, "notes": spec.get("notes", ""),
                          "spec_file": os.path.relpath(os.path.abspath(spec_path), ROOT),
                          "input": _summ(inp), "est_usd": est, "est_basis": why,
                          "state": "queued", "bucket": bucket, "submitted": time.time(),
                          "bytes": len(body)}
    eta = bucket * 60 - time.time()
    print(f"{jid}  queued for cron minute {bucket} (starts in ~{eta:.0f}s)  est ${est} [{why}]", flush=True)
    return jid


def _find(m, ident):
    if ident in m["jobs"]:
        return ident
    hits = [k for k, j in m["jobs"].items() if j["id"] == ident or k.endswith(ident)]
    if len(hits) != 1:
        raise SystemExit(f"unknown/ambiguous job {ident}: {hits}")
    return hits[0]


def refresh(jid):
    """Look at KV and update the manifest state for one job. Returns the res record (or None)."""
    rec = kv_get("res:" + jid)
    now = time.time()
    with locked() as m:
        j = m["jobs"][jid]
        if j["state"] in ("done", "error", "collected_error"):
            return rec
        if rec is not None:
            j["state_relay"] = rec.get("state")
            if rec.get("t0") and rec.get("t1"):
                j["gen_secs"] = round((rec["t1"] - rec["t0"]) / 1000, 1)
                j["started"] = rec["t0"] / 1000
            j["finished"] = (rec.get("t1") or now * 1000) / 1000
            j["latency_secs"] = round(j["finished"] - j["submitted"], 1)
            if rec.get("state") != "done":
                j["state"] = "error"
                j["error"] = (rec.get("error") or json.dumps(rec))[:1500]
                j["est_usd_note"] = "errored runs are normally not billed"
            else:
                j["state"] = "ready"
            return rec
        st = kv_get("state:" + jid)
        if st:
            j["state"] = "running"
            j["started"] = st.get("t0", 0) / 1000
        elif now > j["bucket"] * 60 + 600:
            j["state"] = "stale"     # cron minute passed >10 min ago, nothing started: try `requeue`
    return None


def _ext(data, ctype):
    h = data[:16]
    if h[4:8] == b"ftyp":
        return ".mov" if h[8:10] == b"qt" else ".mp4"
    if h[:3] == b"\xff\xd8\xff":
        return ".jpg"
    if h[:8] == b"\x89PNG\r\n\x1a\n":
        return ".png"
    if h[:4] == b"RIFF":
        return ".webp" if data[8:12] == b"WEBP" else ".wav"
    if h[:3] == b"ID3" or h[:2] in (b"\xff\xfb", b"\xff\xf3", b"\xff\xf2"):
        return ".mp3"
    return mimetypes.guess_extension((ctype or "").split(";")[0]) or ".bin"


def _ffprobe(path):
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries",
                        "format=duration,size:stream=codec_type,codec_name,width,height,r_frame_rate,nb_frames",
                        "-of", "json", path], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(f"ffprobe failed: {r.stderr[:300]}")
    d = json.loads(r.stdout)
    info = {"duration": round(float(d["format"].get("duration", 0)), 3), "bytes": int(d["format"].get("size", 0)),
            "streams": [{k: s.get(k) for k in ("codec_type", "codec_name", "width", "height", "r_frame_rate", "nb_frames")
                         if s.get(k) is not None} for s in d.get("streams", [])]}
    if not any(s["codec_type"] in ("video", "audio") for s in info["streams"]):
        raise RuntimeError("no audio/video stream")
    return info


def collect_one(jid):
    rec = refresh(jid)
    m = read_manifest()
    j = m["jobs"][jid]
    if j["state"] != "ready" or rec is None:
        return j["state"]
    media = rec.get("media") or []
    if not media:   # nothing mirrored: try the result URLs directly (R2 presigned is reachable; provider CDNs aren't)
        res = rec.get("result") or {}
        media = [{"url": v} for v in (res.values() if isinstance(res, dict) else []) if isinstance(v, str) and v.startswith("http")]
    paths, probes, errs = [], [], []
    for i, f in enumerate(media):
        data = None
        if f.get("key"):
            n = f.get("chunks", 1)
            parts = [kv_get(f["key"] if n == 1 else f"{f['key']}:{c}", raw=True) for c in range(n)]
            if all(p is not None for p in parts):
                data = b"".join(parts)
        if data is None and f.get("url"):
            try:
                st, data = _req("GET", f["url"], timeout=120)
                data = data if st == 200 else None
            except Exception:  # noqa: BLE001
                data = None
        if data is None:
            errs.append(f"file {i}: {f.get('error') or 'not retrievable'}"); continue
        if f.get("bytes") and len(data) != f["bytes"]:
            errs.append(f"file {i}: size {len(data)} != {f['bytes']}"); continue
        p = os.path.join(OUT, f"{j['tag']}_{j['id']}{'' if len(media) == 1 else f'_{i}'}{_ext(data, f.get('type'))}")
        with open(p + ".part", "wb") as fh:
            fh.write(data)
        os.replace(p + ".part", p)
        try:
            probes.append(_ffprobe(p) if not p.endswith((".jpg", ".png", ".webp")) else {"bytes": len(data)})
        except Exception as e:  # noqa: BLE001
            errs.append(f"{p}: {e}"); continue
        paths.append(os.path.relpath(p, ROOT))
    with locked() as m:
        j = m["jobs"][jid]
        j["files"], j["probe"] = paths, probes
        if errs:
            j["collect_errors"] = errs
        j["state"] = "done" if paths and not errs else ("done_partial" if paths else "collected_error")
        j["collected"] = time.time()
        res = rec.get("result")
        if isinstance(res, dict) and res.get("usage"):
            j["usage"] = res["usage"]
        # refine the estimate with the real output duration for per-second models
        if probes and probes[0].get("duration") and "s x " in (j.get("est_basis") or ""):
            rate = float(j["est_basis"].split(" x ")[1].split(" ")[0])
            billed = j["input"].get("duration")
            if billed in (-1, None):
                j["est_usd"] = round(rate * probes[0]["duration"], 4)
                j["est_basis"] += f" -> refined on actual {probes[0]['duration']}s"
        state = j["state"]
    print(f"{jid}: {state} {paths} {errs or ''}", flush=True)
    return state


def status(ids):
    m = read_manifest()
    targets = [_find(m, i) for i in ids] if ids else [k for k, j in m["jobs"].items()
                                                      if j["state"] in ("queued", "running", "ready", "stale")]
    for jid in targets:
        refresh(jid)
    m = read_manifest()
    for jid, j in m["jobs"].items():
        if ids and jid not in targets:
            continue
        extra = j.get("files") or j.get("error", "")[:120] or ""
        lat = f"{j['latency_secs']}s" if j.get("latency_secs") else f"{time.time() - j['submitted']:.0f}s ago"
        print(f"{j['state']:<15} {jid:<40} {j['model']:<26} ${j.get('est_usd')}  {lat}  {extra}")
    print(f"total est ${m.get('total_est_usd')}  (done ${m.get('total_est_usd_done')})")


def collect(ids):
    m = read_manifest()
    targets = [_find(m, i) for i in ids] if ids else [k for k, j in m["jobs"].items()
                                                      if j["state"] in ("queued", "running", "ready", "stale")]
    return {jid: collect_one(jid) for jid in targets}


def wait(ids, timeout=1800, every=15):
    m = read_manifest()
    pending = [_find(m, i) for i in ids]
    t0 = time.time()
    while pending and time.time() - t0 < timeout:
        for jid in list(pending):
            st = collect_one(jid)
            if st not in ("queued", "running", "ready"):
                pending.remove(jid)
                if st == "stale":
                    print(f"{jid}: STALE (cron minute missed) -> run `gen.py requeue {jid}`", flush=True)
        if pending:
            print(f"  .. {len(pending)} pending, {time.time()-t0:.0f}s", file=sys.stderr, flush=True)
            time.sleep(every)
    if pending:
        raise SystemExit(f"timeout; still pending: {pending}")


def requeue(ident):
    with locked() as m:
        jid = _find(m, ident)
        j = m["jobs"][jid]
        if j["state"] not in ("stale", "queued"):
            raise SystemExit(f"{jid} is {j['state']}; only stale/queued jobs can be requeued")
        old = f"job:{j['bucket']}:{jid}"
        body = kv_get(old, raw=True)
        if body is None:
            raise SystemExit(f"{old} no longer in KV (the relay probably picked it up) - not requeuing")
        kv_delete(old)
        b = _pick_bucket(m)
        kv_put(f"job:{b}:{jid}", body)
        j.update(state="queued", bucket=b, requeued=time.time())
    print(f"{jid} requeued for minute {b}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__); sys.exit(1)
    cmd, args = sys.argv[1], [a for a in sys.argv[2:] if not a.startswith("--")]
    opts = dict(a[2:].split("=", 1) for a in sys.argv[2:] if a.startswith("--") and "=" in a)
    if cmd == "submit":
        for s in args:
            submit(s)
    elif cmd == "status":
        status(args)
    elif cmd == "collect":
        collect(args)
    elif cmd == "wait":
        wait(args, timeout=float(opts.get("timeout", 1800)))
    elif cmd == "requeue":
        requeue(args[0])
    elif cmd == "estimate":
        for s in args:
            sp = json.load(open(s))
            inp = {**DEFAULTS.get(sp["model"], {}), **sp["input"]}
            validate(sp["model"], _resolve_files(inp))
            print(s, *estimate(sp["model"], inp))
    else:
        print(__doc__); sys.exit(1)
