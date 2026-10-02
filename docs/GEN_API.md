# Generative media via the Cloudflare API: reference

Verified 2026-10-02 from this sandbox. Helper: `tools/cf.py`. Test outputs: `assets/tests/`.
Full input/output schemas, prices and examples for every media model are in `docs/gen_catalog/*.json`
(index: `docs/gen_catalog/INDEX.tsv`). They were copied from the `cloudflare/cloudflare-docs` GitHub repo
(`src/content/catalog-models`, commit d6f7377, 2026-10-01) because developers.cloudflare.com is blocked
by the egress proxy.

## Account and auth
- Account: `78885e7db58a4c34423a7e62c8471b75` ("Jadewang@gmail.com's Account"). The token is valid. The proxy injects it, so send no auth header.
- Allowed: Workers AI, unified `/ai/run`, and the `workers/scripts` list.
- Denied (Authentication error): `ai-gateway/gateways`, `r2/buckets`, `GET ai/runs/{id}`.
- CA bundle: `/root/.ccr/ca-bundle.crt`. curl picks it up automatically, and `cf.py` sets it explicitly.

## Two endpoints
1. **Unified catalog** (third-party: `bytedance/*`, `xai/*`, `elevenlabs/*`, `google/*`, `runwayml/*`, ...). These are billed through Unified Billing.
   ```bash
   curl -sS -X POST https://api.cloudflare.com/client/v4/accounts/$ACCT/ai/run \
     -H 'content-type: application/json' \
     -d '{"model":"xai/grok-imagine-image","input":{"prompt":"...","aspect_ratio":"16:9","response_format":"b64_json"}}'
   # -> {"result":{"state":"Completed","result":{"image":"https://ai-gateway-outputs....r2.cloudflarestorage.com/...presigned"}},"success":true}
   ```
   Media comes back as presigned R2 URLs (sometimes `data:` URIs). Download them promptly because they expire.
   Inputs (images, audio, video) can be HTTPS URLs or `data:<mime>;base64,...` URIs (`cf.to_data_uri(path)`).
2. **Workers AI** (`@cf/...`): `POST /ai/run/@cf/<model>`, with the body being the input itself. Schemas are at `GET /ai/models/schema?model=@cf/...`.
   `/ai/models/search` lists only 69 `@cf` models. The third-party catalog is not listed by any API route.

## HARD LIMIT in this sandbox: about 30 s per request
The sandbox's auth-injecting proxy returns `HTTP 502 "upstream request failed"` at about 30.0 s. This was reproduced with a slow LLM call.
- Images (6 s), TTS (3 s), music (4 s) and ASR (1–11 s) work fine.
- **Video generation cannot complete synchronously from here.** The Seedance 2.5 test died at 30.5 s. That job may still have run, and been billed, upstream (about $0.51).
- Background mode works: add `"options":{"background":true,"webhookUrl":"https://..."}` to the `/ai/run` body. It returns at once with
  `202 {"result":{"runId":"...","state":"Running"}}`. The result is delivered only as a POST to `webhookUrl`
  (`{id,state,result,error,provider,model,usage}`). Delivery is best effort with no retry, and the URL must be public HTTPS.
  There is no status-poll endpoint usable with this token, so **without a webhook the output is lost**.
- WebSocket mode on `/ai/run` was rejected (HTTP 400). The proxy most likely strips `Upgrade`.
- **Fix needed for video:** a small relay Worker on the account, either as a webhook receiver plus KV/DO store, or one that calls `env.AI.run`
  itself and holds the result for us to poll. The account already has Workers named `orbital-sunrise-relay` and
  `rare-earth-*-relay` (fetch + cron) from earlier projects, which almost certainly do exactly this. Their source was
  not inspected; ask the user before reusing one or deploying a new one.

## Video models (unified)
| model | $/s (480p / 720p) | max len | res | key inputs |
|---|---|---|---|---|
| `bytedance/seedance-2.5` | 0.1028 / 0.2312 (video-ref input: 0.4304 / 0.9676) | **4–30 s**, or -1 = auto | 480p, 720p | prompt ≤2000, `image` (first frame), `last_frame_image`, `reference_images` ≤30, `reference_videos` ≤10 (≤30 s total), `reference_audios` ≤10 (≤30 s total), `generate_audio`, `seed` (not reproducible), `output_format` mp4/mov, `use_virtual_avatar` |
| `bytedance/seedance-2.0` | 0.07 / 0.15 (1080p 0.37, 4k 0.78) | 4–12 s | up to 4k | `image`, `last_frame_image`, `reference_images` 1–4, `reference_video` (single), no audio ref |
| `bytedance/seedance-2.0-fast` | 0.06 / 0.12 | 4–12 s | 480p, 720p | same as 2.0 |
| `bytedance/seedance-2.0-mini` | 0.04 / 0.09 | 4–12 s | 480p, 720p | as 2.0, plus `reference_audio` (background music only) |
| `xai/grok-imagine-video` | 0.05 / 0.07 | 1–15 s | 480p, 720p (`size` up to 1920x1080) | `_operation` generate/edit/extend, `image:{url}`, `video:{url}`, `reference_images:[{url}]` ≤10, **`output:{upload_url}` REQUIRED** |
| `xai/grok-imagine-video-1.5-preview` | 0.08 / 0.14 | 1–15 s | same | same |
| `pruna/p-video-avatar` | 0.025 (720p), 0.045 (1080p) | | 720p, 1080p | **`image` + `audio` = explicit lip-sync** (portrait first frame, audio drives the mouth) |
| `pruna/p-video-replace` | 0.03 / 0.06 | | | swap 1–3 identity images into a source video (keeps its motion and audio) |
| others | | | | `google/veo-3.1(-fast)` (≤8 s), `runwayml/gen-4.5`, `runwayml/aleph-2` (video-to-video edit, ≤30 s in), `minimax/hailuo-2.3`, `minimax/h3`, `alibaba/wan-3.0`, `vidu/q3-*`, `pixverse/v6`, `lightricks/ltx-2-5-fast`, `black-forest-labs/flux-3-video`, `black-forest-labs/flux-video-upscale` (1.5–3x, ≤20 s) |

There is no Kling model in the catalog.

### Seedance 2.5 answers
- (a) Reference images for character and set consistency: yes, `reference_images`, up to 30.
  Realistic faces may hit ByteDance face/deepfake detection. `use_virtual_avatar:true` routes AI-generated characters through ByteDance's virtual avatar library.
- (b) Reference audio: yes, `reference_audios`, up to 10 clips totalling ≤30 s. Audio-only input with no image is allowed. The docs describe it
  as multimodal reference ("audio + video generated together"). They do not explicitly promise phoneme-level lip-sync, and this
  was not verified (the test was cut by the 30 s proxy limit). For guaranteed lip-sync use `pruna/p-video-avatar` (image + audio).
- (c) First and last frame: yes, `image` and `last_frame_image`. In that mode aspect ratio is forced to adaptive.
- (d) Aspect ratios: 16:9, 4:3, 1:1, 3:4, 9:16, 21:9, adaptive (default). Resolution is 480p or 720p only. Frame rate is fixed at 24 fps.
  Duration is an integer 4–30, or -1 for auto. Editing a reference video only allows -1.
  `camera_fixed` has no effect.
- **Schema gotcha:** the validator lists `duration, resolution, aspect_ratio, fps, camera_fixed, watermark, output_format,
  use_virtual_avatar` as *required* and sets `additionalProperties:false`. Send all of them, as below:
  ```json
  {"prompt":"...","reference_images":["data:image/jpeg;base64,..."],"reference_audios":["data:audio/mpeg;base64,..."],
   "duration":5,"resolution":"480p","aspect_ratio":"16:9","fps":24,"camera_fixed":false,"watermark":false,
   "output_format":"mp4","use_virtual_avatar":false,"generate_audio":false}
  ```
  The output is `{"video": "<presigned mp4 url>"}`. At 720p and 16:9 that means 1280x720, which needs upscaling for the 1080p deliverable. `flux-video-upscale` is one option.

### Grok Imagine (Zero Data Retention account)
- Image models require `response_format:"b64_json"`. `url` gives "ZDR teams do not have access to URL format". It still returns a gateway R2 URL, which is fine.
- **Video models require `output.upload_url`**, a presigned PUT URL that we supply ("ZDR teams must provide output.upload_url"). The video is
  written there, so we need a bucket or Worker endpoint. R2 is not accessible with this token.

## Image models (all synchronous and fast)
- `xai/grok-imagine-image` costs $0.02, about 6 s, 1280x720 for 16:9 (tested). `-quality` costs $0.05 with up to 10 per request. `-image-2.0` costs $0.04 with ≤5 reference images (`images:[{url}]`), plus `mask` for inpainting.
- `bytedance/seedream-5-pro` costs $0.045 with ≤10 refs. Others: `google/nano-banana-pro` (`image_input[]`, 1K–4K), `openai/gpt-image-2*`, `black-forest-labs/flux-2-*`, `flux-1-kontext-*` (editing), `recraft/*` (incl. vector/SVG), `krea/*`, `pruna/p-image-edit`.
- Workers AI: `@cf/black-forest-labs/flux-1-schnell` returns `{"image": "<b64 jpeg>"}` at 1024², about 2 s, $0.000011/neuron (≈173 neurons) (tested). Also `flux-2-dev`, `flux-2-klein-4b/9b`, `leonardo/phoenix-1.0`, `lucid-origin`, `sdxl-lightning`, `sd-v1-5-inpainting`.

## Audio
- ElevenLabs TTS: `elevenlabs/eleven-v3` ($0.0001/char) supports audio tags such as `[whispering]`, plus `eleven-multilingual-v2`, `eleven-turbo-v2-5` and `eleven-flash-v2-5`.
  Input is `{text, voice_id, output_format:"mp3_44100_128", voice_settings, seed}` and output is `{audio:url}`. Tested with voice `JBFqnCBsd6RMkjVDRZzb`, about 3 s.
- `elevenlabs/music-v2` costs $0.0025/s, 3 s–10 min. Input is `{prompt, music_length_ms, force_instrumental, seed, composition_plan}`. It also works as a
  makeshift SFX generator: a 4 s "tape rewind whoosh" was tested at 48 kHz.
- **There is no ElevenLabs Sound Effects model** (`elevenlabs/sound-effects` and variants give "Model not found"). The only other route is
  gateway passthrough (`gateway.ai.cloudflare.com/.../elevenlabs`), which needs our own `xi-api-key`.
- Other options: `minimax/music-2.6`, `minimax/speech-2.8-*`, `xai/grok-tts`, `openai/tts-1(-hd)`, `inworld/tts-*`, `google/gemini-3.1-flash-tts`,
  `@cf/deepgram/aura-2-en`, `@cf/myshell-ai/melotts`.

## Transcription with word timestamps (all tested on a 20 s clip of the song at 40–60 s)
- `@cf/openai/whisper-large-v3-turbo`: input `{"audio":"<base64>", "language":"en"}`. Returns `segments[].words[{word,start,end}]` in **seconds**, plus `vtt`. Took 10 s.
  It output repeated "stop, stop, stop… Rewind ×5", which could be the chopped vocals or could be hallucination. Grok and AssemblyAI gave only the sung line.
  Consider `vad_filter:true`, `condition_on_previous_text:false` and `initial_prompt` set to the lyrics.
- `xai/grok-stt`: input `{"file":"data:audio/mpeg;base64,...","language":"en"}` (≤25 MB via the gateway). Returns `words[{text,start,end}]` in seconds. Took 0.7 s at $0.0017/min. Cleanest result.
- `assemblyai/universal-3.5-pro`: input `{"audio_url":"data:...","language_code":"en","keyterms_prompt":[...]}`. Returns `words[{text,start,end,confidence}]` in **ms**. Took 11 s at $0.0035/min.
- Also available: `@cf/openai/whisper` (word timestamps), `@cf/deepgram/nova-3`, `openai/gpt-4o-transcribe`, `assemblyai/universal-3-pro`.
- For forced alignment of the known lyrics, feed the lyrics as prompt or keyterms and then align locally.

## Depth and segmentation
- **No hosted depth-estimation or segmentation model** exists in either catalog. `runwayml/aleph-2` (video-to-video edit) could be
  prompted to render a depth or matte pass, but that is unverified and expensive at $0.336/s.
- Local fallback: `pip` works (pypi.org is reachable) and `cv2` 5.0 is installed. huggingface.co and download.pytorch.org are **blocked**, but
  MiDaS weights on GitHub releases (`github.com/isl-org/MiDaS/releases/download/v3_1/...`) and MediaPipe models on
  `storage.googleapis.com/mediapipe-models/...` (selfie and multiclass segmenter) return 200. The machine has 4 CPUs, 15 GB RAM and no GPU.

## Python
```python
import sys; sys.path.insert(0, "tools")
from cf import run_model, save_media, to_data_uri, submit_background
r = run_model("xai/grok-imagine-image", {"prompt": "...", "aspect_ratio": "16:9", "response_format": "b64_json"})
save_media(r, "assets/tests/foo")            # -> foo.jpg
r = run_model("xai/grok-stt", {"file": to_data_uri("clip.mp3"), "language": "en"}); r["words"]
submit_background("bytedance/seedance-2.5", payload, webhook_url="https://<relay>/hook")   # video
```
CLI: `python3 tools/cf.py MODEL '<json input>' OUT_PREFIX`.

## Test log (assets/tests/)
| file | model | result |
|---|---|---|
| grok_imagine_image.jpg | xai/grok-imagine-image | OK, 6.5 s, 1280x720 |
| flux_schnell.jpg | @cf/black-forest-labs/flux-1-schnell | OK, 1.7 s, 1024² |
| eleven_v3_tts.mp3 | elevenlabs/eleven-v3 | OK, 3.4 s |
| eleven_music_sfx.mp3 | elevenlabs/music-v2 (4 s SFX) | OK, 4.2 s |
| whisper_turbo_clip.json / grok_stt_clip.json / assemblyai_clip.json | ASR | OK, word timestamps |
| (no file) | bytedance/seedance-2.5, 480p, 5 s, reference_audios | 502 at 30.5 s, the proxy timeout. Possibly billed |
| (no file) | xai/grok-imagine-video, i2v, 480p, 4 s | 400: ZDR requires output.upload_url (not billed) |
