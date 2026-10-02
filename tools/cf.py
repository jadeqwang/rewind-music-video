#!/usr/bin/env python3
"""Minimal Cloudflare AI client (Workers AI + AI Gateway unified catalog).

Auth is injected by the sandbox proxy, so no API token is needed here. If you run
this elsewhere, set CLOUDFLARE_API_TOKEN and it will be sent as a Bearer token.

Two endpoints:
  * third-party catalog (bytedance/*, xai/*, elevenlabs/*, google/*, ...):
        POST /accounts/{id}/ai/run   body {"model": ..., "input": {...}}
    -> {"result": {"state": "Completed", "result": {"video"|"image"|"audio"|...}}}
       media fields are presigned R2 URLs (or data: URIs) -> download promptly.
  * Workers AI (@cf/...):
        POST /accounts/{id}/ai/run/@cf/...   body = input
    -> JSON {"result": {...}} or raw binary (e.g. flux-1-schnell returns b64 JSON,
       melotts/aura return audio bytes, sdxl returns PNG bytes).

Usage:
    from cf import run_model, save_media
    out = run_model("xai/grok-imagine-image", {"prompt": "...", "response_format": "b64_json"})
    save_media(out, "assets/tests/x")       # writes x.jpg / x.mp4 / x.mp3 ...
CLI:
    python tools/cf.py MODEL '{"prompt": "..."}' OUT_PREFIX
"""
import base64
import json
import mimetypes
import os
import sys
import time
import urllib.request
import urllib.error

ACCOUNT_ID = os.environ.get("CF_ACCOUNT_ID", "78885e7db58a4c34423a7e62c8471b75")
API = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}"
CA = "/root/.ccr/ca-bundle.crt"

import ssl
_CTX = ssl.create_default_context(cafile=CA) if os.path.exists(CA) else ssl.create_default_context()


class CFError(RuntimeError):
    pass


def _headers(extra=None):
    h = {"Content-Type": "application/json"}
    tok = os.environ.get("CLOUDFLARE_API_TOKEN")
    if tok:
        h["Authorization"] = f"Bearer {tok}"
    if extra:
        h.update(extra)
    return h


def _post(url, body, timeout, headers=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers=_headers(headers), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            return r.headers.get("content-type", ""), r.read(), dict(r.headers)
    except urllib.error.HTTPError as e:
        raise CFError(f"HTTP {e.code}: {e.read()[:2000].decode('utf-8', 'replace')}") from None


def to_data_uri(path):
    """Local file -> data URI (for image / reference_images / reference_audios / file fields)."""
    mt = mimetypes.guess_type(path)[0] or "application/octet-stream"
    with open(path, "rb") as f:
        return f"data:{mt};base64,{base64.b64encode(f.read()).decode()}"


def run_model(model, payload, timeout=900, retries=2, gateway=None, verbose=True):
    """Run a model synchronously. Returns dict (JSON result) or bytes (binary output).

    - '@cf/...' models go to /ai/run/{model} (Workers AI).
    - everything else goes to the unified /ai/run envelope endpoint.
    The gateway holds the connection until the job finishes (video: ~1-5 min),
    so there is no polling; we just use a long timeout. For the third-party
    envelope, returns the inner result dict, e.g. {"video": url}.
    """
    extra = {"cf-aig-gateway-id": gateway} if gateway else None
    if model.startswith("@cf/") or model.startswith("@hf/"):
        url, body = f"{API}/ai/run/{model}", payload
    else:
        url, body = f"{API}/ai/run", {"model": model, "input": payload}
    last = None
    for attempt in range(retries + 1):
        t0 = time.time()
        try:
            ctype, raw, hdrs = _post(url, body, timeout, extra)
        except CFError as e:
            msg = str(e)
            # don't retry user-input errors (7003 / 400)
            if "HTTP 400" in msg or "7003" in msg or attempt == retries:
                raise
            last = e
            time.sleep(5 * (attempt + 1))
            continue
        except Exception as e:  # timeouts, resets
            if attempt == retries:
                raise
            last = e
            time.sleep(5 * (attempt + 1))
            continue
        dt = time.time() - t0
        if verbose:
            print(f"[cf] {model} {dt:.1f}s ctype={ctype} req={hdrs.get('cf-aig-request-id', hdrs.get('Cf-Aig-Request-Id', ''))}",
                  file=sys.stderr)
        if "json" not in ctype:
            return raw  # binary audio/image
        d = json.loads(raw)
        if not d.get("success", True):
            raise CFError(json.dumps(d.get("errors")))
        res = d.get("result", d)
        # unified envelope: {"state": "...", "result": {...}}
        if isinstance(res, dict) and "state" in res and "result" in res:
            if res["state"] not in ("Completed", "completed", "succeeded"):
                raise CFError(f"state={res['state']}: {json.dumps(res)[:1000]}")
            return res["result"]
        return res
    raise last


_EXT = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "video/mp4": ".mp4",
        "video/quicktime": ".mov", "audio/mpeg": ".mp3", "audio/wav": ".wav", "audio/x-wav": ".wav",
        "audio/ogg": ".ogg", "audio/opus": ".opus", "application/octet-stream": ".bin"}


def download(url, path_prefix, timeout=600):
    """Download URL (presigned R2 / https / data:) to path_prefix + inferred extension."""
    if url.startswith("data:"):
        head, b64 = url.split(",", 1)
        mt = head[5:].split(";")[0]
        data = base64.b64decode(b64)
    else:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as r:
            mt = r.headers.get("content-type", "application/octet-stream").split(";")[0]
            data = r.read()
    ext = os.path.splitext(path_prefix)[1] or _EXT.get(mt) or mimetypes.guess_extension(mt) or ".bin"
    path = path_prefix if os.path.splitext(path_prefix)[1] else path_prefix + ext
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)
    return path


def save_media(result, path_prefix):
    """Save every media output in a run_model() result. Returns list of written paths.

    Handles: bytes (binary response), {"image"/"video"/"audio": url|data-uri|b64},
    {"images": [...]}, Workers AI {"image": b64} and {"audio": b64}. Also writes
    path_prefix + ".json" with the non-media fields (e.g. transcripts) when present.
    """
    paths = []
    if isinstance(result, (bytes, bytearray)):
        ext = ".png" if result[:4] == b"\x89PNG" else ".jpg" if result[:2] == b"\xff\xd8" else \
            ".mp3" if result[:3] == b"ID3" or result[:2] == b"\xff\xfb" else ".wav" if result[:4] == b"RIFF" else ".bin"
        p = path_prefix + ext
        open(p, "wb").write(result)
        return [p]
    meta = {}
    for k, v in result.items():
        vals = v if isinstance(v, list) else [v]
        if k in ("image", "images", "video", "videos", "audio", "audios") and all(isinstance(x, str) for x in vals):
            for i, x in enumerate(vals):
                pre = path_prefix if len(vals) == 1 else f"{path_prefix}_{i}"
                if x.startswith(("http://", "https://", "data:")):
                    paths.append(download(x, pre))
                else:  # bare base64 (Workers AI)
                    raw = base64.b64decode(x)
                    paths += save_media(raw, pre)
        else:
            meta[k] = v
    if meta:
        with open(path_prefix + ".json", "w") as f:
            json.dump(meta, f, indent=1)
        paths.append(path_prefix + ".json")
    return paths


def schema(model):
    """Workers AI (@cf) schema only; third-party schemas live in the docs catalog (see docs/GEN_API.md)."""
    req = urllib.request.Request(f"{API}/ai/models/schema?model={model}", headers=_headers())
    with urllib.request.urlopen(req, context=_CTX) as r:
        return json.loads(r.read())["result"]


if __name__ == "__main__":
    if len(sys.argv) < 4:
        print(__doc__)
        sys.exit(1)
    out = run_model(sys.argv[1], json.loads(sys.argv[2]))
    print(json.dumps(save_media(out, sys.argv[3])))
