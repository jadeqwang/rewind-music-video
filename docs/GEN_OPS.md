# GEN_OPS — running long generations (Seedance etc.) from this sandbox

Tool: `tools/gen.py`. Manifest: `assets/gen/manifest.json`. Outputs: `assets/gen/<tag>_<id>.<ext>`. Specs: `assets/gen/specs/`.
Model schemas and prices: `docs/gen_catalog/` (see `docs/GEN_API.md`).

## How it works (relay reuse, approved by the user)
The proxy cuts every `api.cloudflare.com` request at about 30 s, and `*.workers.dev` is blocked. So we reuse the user's existing Worker
**`rare-earth-v3-relay`**. It has the `AI` binding, KV `JOBS` = namespace `5f8f1f387d37449a949ee68625bdc310` (`rare-earth-v3-jobs`), and cron `* * * * *`.
The deployed script was read through the API and it matches `/home/user/jadeqwang/rare-earth-techno-remix` plus its v3 changes.
**We never deploy, modify or delete Workers.**

We use the relay's **cron queue**, which needs no hook secret:
1. `gen.py submit` writes `job:<minuteBucket>:rewind/<tag>-<id>` = `{model, input}` into KV through the KV REST API.
2. The cron run for exactly that minute does these steps in order: it deletes the job key, writes `state:<job>`, calls `env.AI.run(model, input)` (with no 30 s limit inside the Worker),
   mirrors the output files into `media:<job>:<n>[:<chunk>]` (20 MB chunks, TTL 21 days), and then writes `res:<job>` = `{state, result, media[], t0, t1}`.
3. `gen.py status/collect/wait` read `res:` and `media:` back from KV, write the files atomically, and check them with ffprobe.

Each run fires once at most, because a job runs only in its own minute bucket. All of our keys contain the `rewind/` prefix, so they never touch the old projects' keys.
The webhook path (`/hook/<HOOK_SECRET>/…`) is **not usable**. The secret existed only in an old session's scratchpad, and secrets can't be read back.

## Commands
```bash
python3 tools/gen.py estimate assets/gen/specs/X.json    # validate against catalog schema + cost, no spend
python3 tools/gen.py submit   assets/gen/specs/X.json [Y.json ...]   # prints job id, queues ~2 min ahead
python3 tools/gen.py status   [ID ...]                    # refresh + table + running total
python3 tools/gen.py collect  [ID ...]                    # download all finished jobs
python3 tools/gen.py wait     ID [ID ...] [--timeout=1800]
python3 tools/gen.py requeue  ID                          # only for 'stale' jobs (cron minute missed)
```
IDs can be the full job (`rewind/tag-abc123def0`) or just the 10-hex suffix.
Spec format:
```json
{"model": "bytedance/seedance-2.5", "tag": "ld_road_a", "notes": "free text", "est_usd": null,
 "input": {"prompt": "...", "reference_images": ["file:assets/sets/x.jpg"],
           "reference_audios": ["file:analysis/slices/v_040.000_5.mp3"], "duration": 5, "resolution": "720p", "aspect_ratio": "16:9"}}
```
- `"file:<path>"` (relative to the repo) is converted to a `data:` URI at submit time. Seedance 2.5 accepts data URIs for `image`,
  `last_frame_image`, `reference_images`, `reference_videos` and `reference_audios`, so **no hosting is needed**. The manifest stores only a summary like `<data audio/mpeg 110KB>`.
- Missing required Seedance 2.5 keys are filled in with defaults (`fps 24, camera_fixed false, watermark false, output_format mp4, use_virtual_avatar false,
  generate_audio false`, plus 480p/16:9/5 s if absent). The input is then validated against the catalog JSON schema (`additionalProperties:false`) **before** anything is queued.
- Throughput: two jobs per cron minute by default (`GEN_PER_MINUTE`). Buckets are assigned under the manifest lock.

## Manifest
`assets/gen/manifest.json` → `{relay, jobs: {job: {...}}, total_est_usd, total_est_usd_done}`. Each job holds
`tag, model, notes, spec_file, input (summarised), est_usd, est_basis, state, bucket, submitted, started, finished,
gen_secs (Worker-side), latency_secs (submit → result), files[], probe[] (ffprobe: duration, codec, w×h, fps)`.
Every read-modify-write runs under `fcntl.flock` on `manifest.json.lock` and is saved with tmp + rename, so parallel `collect`/`wait`/`submit` processes are safe.
States: `queued → running → ready → done` (or `error`, `stale`, `collected_error`, `done_partial`).

## Costs (catalog list prices, USD; the estimate is duration × rate)
| model | 480p | 720p | notes |
|---|---|---|---|
| bytedance/seedance-2.5 | 0.1028/s | 0.2312/s | with `reference_videos`: 0.4304 / 0.9676 per s. A 5 s 480p test costs $0.51 and a 10 s 720p plate costs $2.31 |
| bytedance/seedance-2.0(-fast/-mini) | 0.07 / 0.06 / 0.04 | 0.15 / 0.12 / 0.09 | 4–12 s. Only mini takes audio, as background music |
| pruna/p-video-avatar | | 0.025/s (1080p 0.045) | image + audio lip-sync |
For reference, Rare Earth spent about $142 on 103 Seedance runs. Errored runs are normally not billed, but a call cut by the proxy may have been. `duration:-1` is estimated
as 15 s and then corrected to the real duration on collect.

## Validation run (2026-10-02)
TEST_RESULT_PLACEHOLDER

## Limits and gotchas
- **About 2 min queue lead plus a minute bucket.** Jobs start at the next free cron minute at least 2 min ahead, because KV `list` is eventually consistent.
  Expect latency of queue lead plus generation time.
- **The job body must be under 25 MiB** (one KV value). `submit` refuses larger bodies. Re-encode references: JPEG about 1–2 MP for images, mp3 at 128–192k for ≤30 s audio.
- Reference rules (Seedance 2.5): ≤30 images, ≤10 videos (≤30 s total), ≤10 audios (≤30 s total). Image aspect ratio must be between 0.39 and 2.5. Realistic faces can trip
  ByteDance's face filter (`use_virtual_avatar:true` routes AI characters through the avatar library). Use `generate_audio:false` when the reference audio is the song, to avoid the
  copyright filter on output audio. Output is 24 fps, 854×480 or 1280×720.
- With `image`/`last_frame_image` the aspect ratio is forced to adaptive.
- **Grok Imagine video is NOT supported**: the account is ZDR, so it needs `output.upload_url` (a presigned PUT), and neither the relay nor R2 gives us one. `gen.py` refuses it. Use Seedance or Pruna instead.
- `stale` means the cron minute passed more than 10 min ago and the relay never wrote `state:`. This can happen if a cron tick was skipped. `requeue` moves it to a new minute only if the
  `job:` key is still present, so it can't double-run.
- The Worker runs scheduled jobs with a wall-time limit of about 15 min. Very long 720p 30 s jobs with many references could hit it. If they do, they finish as `error`.
- Mirrored media expire after 21 days and the presigned provider URLs expire much sooner. Always `collect` promptly. Downloaded files live in `assets/gen/`, which is not git-ignored, so never commit anything over 50 MB.
- Do not call video models synchronously through `tools/cf.py`. The proxy cuts the call at 30 s and the job may still be billed.
