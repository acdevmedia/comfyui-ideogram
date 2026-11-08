# Ideogram 4 Image ComfyUI One-Click

[![Runpod](https://api.runpod.io/badge/acdevmedia/comfyui-ideogram)](https://console.runpod.io/hub/listing/acdevmedia/comfyui-ideogram)

Ideogram 4 running locally in ComfyUI: the undistilled base checkpoint and fal's Instant distilled checkpoint, with text-to-image and image-to-image in one package. Version 4 is the latest downloadable open-weight Ideogram family; hosted Ideogram 4.5 has no published weights and is not included.

Container: **`ghcr.io/acdevmedia/ideogram-comfyui:4`**, also tagged `4.0.0` and with an immutable `sha-<commit>` tag. Model revisions, checksums and workflow defaults live under `versions/4/`. A new model generation gets its own profile directory and major tag; rebuilds keep the family tag and always add a commit tag.

## Start on Runpod

1. Sign in to Hugging Face and accept the model agreement for **each** repository, using the account that owns your token. The agreements are separate; accepting one does not grant the other.
   - [ideogram-ai/ideogram-4-nf4-diffusers](https://huggingface.co/ideogram-ai/ideogram-4-nf4-diffusers)
   - [fal/ideogram-v4-instant](https://huggingface.co/fal/ideogram-v4-instant)
2. Create a Hugging Face **read** token and add it to Runpod Secrets as **HUGGINGFACE_TOKEN**. The template maps that secret to `HF_TOKEN`; never paste credentials into public template fields.
3. Create or update the template with `python3 scripts/create-runpod-template.py`, or `--dry-run` to review the payload first. It only calls the Runpod API; it builds nothing and downloads no weights.
4. Launch on a **48 GB** GPU with a **200 GB container disk** and no persistent volume. **L40S** and **A40** are both validated, the L40S roughly twice as fast; **RTX A6000** is the other 48 GB option. A 24 GB card is not enough — peak residency is about 25 GB on the distilled path, an 18.6 GB BF16 transformer plus the shared 5.5 GB text encoder and VAE. An 80 GB A100 is not required and costs several times as much.
5. Open **Connect → HTTP 8188 / ComfyUI** once the service reports Ready. First boot downloads the pinned weights into `/workspace/ComfyUI/models`, so give it several minutes.
6. Pick a workflow in the sidebar, type a prompt, press Queue.

Storage is temporary and no network volume is attached. First-boot downloads resume, your workflow edits persist across restarts, and no weights or credentials are baked into the image.

## Using it

Type a plain-English prompt and press Queue. That is the whole interface.

Ideogram 4 is trained **exclusively** on structured JSON captions, so a bare sentence is never sent to it. **Magic Prompt** — Ideogram's own enhancer, running locally — rewrites your sentence into a full caption with bounding-box layout, schema-constrained so the result is always valid. It runs on a 1.2 GB generative head grafted onto the text encoder already in memory: no second model, no API call, and reproducible from the seed.

**Leave Magic Prompt on.** Without it the model receives something close to plain text, which gives poor adherence and, in our testing, more spurious safety-filter refusals — on one prompt with identical settings, the enhancer produced an image while the un-enhanced path returned the filter's placeholder card. If you do turn it off, the node still wraps your sentence in a minimal valid caption rather than sending raw text. If the enhancer ever returns something unusable, the node logs what came back and falls back to that wrapper instead of rendering a blank frame.

Every packaged workflow shows the caption actually sent to the model in a **Caption sent to the model** panel below the settings, so you can see what the enhancer wrote, what your overrides changed, and whether a disappointing image came from the prompt or the sampler.

### Caption overrides

Three optional fields steer the caption without touching JSON. Leave any of them blank and the enhancer's own choice stands.

| Field | Blank | Set |
| --- | --- | --- |
| `text_in_image` | Removes lettering the enhancer invented, and logs it | Renders exactly these words |
| `background` | Keeps the enhancer's background | Replaces the background description |
| `style` | Keeps the enhancer's art direction | Replaces it |

`text_in_image` is blank by default and that matters: Ideogram is a typography model and its enhancer adds an in-image text element even to prompts that never mention lettering, which the distilled checkpoint renders as pseudo-words across the frame. Put your words in the field for posters and signage.

`style` replaces the art direction inside an existing style block. When a caption has no style block it folds into the summary instead, rather than inventing the aesthetics, lighting and medium the schema would otherwise demand.

### Seeds

The seed widget carries ComfyUI's standard **control after generate**, set to `randomize` in every packaged workflow, so each run differs. Set `fixed` to reproduce an exact image, or `increment` to walk a series.

## Workflows

- **01 Base Text to Image** — the quantized NF4 conditional and unconditional branches on the official `4.0 Default 20` preset.
- **02 Distilled Text to Image** — fal Instant's BF16 eight-step single-branch checkpoint. Guidance stays at 1.0. Distilled does not mean quantized.
- **03 / 04 Image to Image** — upload a picture and describe the result you want.
- **10 Advanced Structured Caption** — write the caption yourself, bounding boxes included.

## Sampler presets

Presets carry Ideogram's official per-step guidance schedule. The closing low-guidance "polish" steps are part of that schedule, not an extra stage, and a preset owns its step count, mu and std because the schedule's length must equal the step count.

| Preset | Steps | Guidance schedule | mu | std |
| --- | --- | --- | --- | --- |
| `4.0 Default 20` (default) | 20 | 18 x 7.0, then 2 x 3.0 | 0.0 | 1.75 |
| `4.0 Quality 48` | 48 | 45 x 7.0, then 3 x 3.0 | 0.0 | 1.5 |
| `4.0 Turbo 12` | 12 | 11 x 7.0, then 1 x 3.0 | 0.5 | 1.75 |
| `custom` | yours | constant `guidance` | yours | yours |

`custom` applies a constant guidance scale, which is what earlier releases did at every step. That is a deviation from the reference configuration and visibly degrades output at high step counts.

The **initial-noise multiplier** defaults to **1.0**, the variance the flow schedule expects. Raising it is an [experimental community adaptation](https://www.reddit.com/r/StableDiffusion/comments/1tz4fnf/ideogram_4_a_solution_for_removing_the_annoying/), not a supported setting, and it degrades structure and text rendering. The `lcm` sampler is likewise experimental and meant for few-step runs; `euler` is the default and matches the reference pipeline.

Canvas defaults to **1280 x 720**. Any multiple of 16 from 256 to 2048 per side is supported.

**There is no negative prompt.** Ideogram 4's pipeline accepts none — its unconditional branch is built from zeroed inputs rather than encoded negative text, so there is no channel for one. Describe what you do want.

## Image to image

Ideogram 4 has **no local edit model**. There is no instruction-following or masked-inpainting checkpoint in the open weights, so these workflows do not edit a picture the way a hosted editor does. They perform **image-to-image variation**: the source is VAE-encoded, normalized into the pipeline latent format, blended with noise at a shortened schedule, and denoised toward the caption, reusing the same loaded model, VAE and text encoder as generation. Describe the result you want rather than expecting a surgical local change.

`image_strength` defaults to 0.5. Lower keeps more of the source, 1.0 approaches a fresh generation, and 0 returns the resized source unchanged.

## Advanced: writing the caption yourself

**10 Advanced Structured Caption** exposes the builder directly, emitting the published schema in the key order the upstream caption verifier checks. The simple workflows never show it.

- **scene** maps to `high_level_description`; **background** describes the environment and is required by the schema.
- **elements** takes one per line. A bare line is an object with no box; otherwise pipe-separated:

  ```
  obj  | y_min,x_min,y_max,x_max | description                   | #HEX,#HEX
  text | y_min,x_min,y_max,x_max | THE WORDS | description       | #HEX,#HEX
  ```

  Boxes are `[y_min, x_min, y_max, x_max]` in **normalized 0-1000** coordinates from the top left, independent of canvas size. Use `-` to omit one.
- **aesthetics**, **lighting**, **medium**, **photo_or_art_style**, **color_palette** build `style_description`, supplied together or left entirely empty.
- **raw_json** takes a complete caption and bypasses the builder.

Malformed boxes, palettes and partial style groups are rejected locally, before anything reaches a paid GPU. Schema reference: [Ideogram 4 prompting guide](https://github.com/ideogram-oss/ideogram-4/blob/main/docs/prompting.md).

The distilled path uses the [checkpoint author's zero-parameter unconditional compatibility module](https://huggingface.co/fal/ideogram-v4-instant) and has no effective CFG branch. It is not bit-exact with fal's hosted runtime. Only one pipeline stays loaded; switching variant releases the other. These Diffusers nodes run inside the ComfyUI process and do not expose separate model-loader sockets.

Prompt inspiration: [EvoLinkAI's curated examples](https://github.com/EvoLinkAI/awesome-ideogram-4.0-prompts). Official notes: [Ideogram open weights](https://huggingface.co/ideogram-ai), [inference code](https://github.com/ideogram-oss/ideogram-4). The downloadable checkpoints carry the Ideogram **non-commercial** model license; check it before commercial use.

## Image preview ribbon

A strip of recent output images sits along the bottom of the window and refreshes as each queued graph finishes, so you can queue a long batch and watch it fill.

Click a thumbnail to open the viewer: arrow keys move through the batch, **space** picks, **D** downloads, **Escape** closes. The tick on a thumbnail picks without opening it. **Download picked** then saves only those files, which is the point: queue fifty, skim, keep three.

Picks last for the session and are never uploaded. The ribbon reads recent `/history` entries through ComfyUI's `/view` endpoint, skips transient previews, and never scans the output directory.

## Browse and download outputs

**Connect → HTTP 3923 / Copyparty** opens a gallery of everything in `/workspace/ComfyUI/output`, newest first. Sign in with the values of Runpod Secrets `COPYPARTY_USERNAME` and `COPYPARTY_SECRET`. Select files to download them, or a whole folder as a ZIP. It is read-only: nothing can be uploaded, changed or deleted, and if either secret is missing it stays off without affecting ComfyUI. The log is `/workspace/logs/copyparty.log`.

`zip`, `unzip` and `aws` are on the path in the terminal for moving outputs off the Pod yourself.

## Environment variables

- `HF_TOKEN`: Hugging Face read credential, mapped to `{{ RUNPOD_SECRET_HUGGINGFACE_TOKEN }}`. Required, with both gated agreements accepted.
- `COPYPARTY_USERNAME`: `{{ RUNPOD_SECRET_COPYPARTY_USERNAME }}`; login for the file browser on port 3923.
- `COPYPARTY_PASSWORD`: `{{ RUNPOD_SECRET_COPYPARTY_SECRET }}`; its password. The browser stays off without both.
- `HF_HOME=/workspace/.cache/huggingface`: Hugging Face cache and metadata location.
- `MODEL_MODE=both`: download both variants. `base` limits first-boot downloads; `distilled` still needs the base repository's shared encoder, tokenizer and VAE.
- `STUDIO_VERSION=4`: baked profile identity. Changing it does not install another model generation.
- `PORT=8000`: gateway port for the Runpod Hub/Serverless listing. The Pod template does not expose it; Pod users reach ComfyUI directly on 8188.
- `PORT_HEALTH=8001`: readiness service for the Hub listing; `/ping` returns 503 until ComfyUI reports device information. Not exposed by the Pod template.
- `OMP_NUM_THREADS=8`, `MKL_NUM_THREADS=8`: CPU-thread defaults; match them to the Pod's CPU quota.
- `PUBLIC_KEY`: optional SSH key for diagnostics. When set, the container starts SSH on 2222; the template does not expose that port.

`RUNPOD_API_KEY` and `GITHUB_PACKAGES_PAT` are local deployment credentials only and must never reach the worker container.

## Build, validate and update

All container builds and runtime tests run in **GitHub Actions**, never on a local workstation. Pushing to `develop` or `main` builds, runs source and template-parity checks, verifies graph schemas against a CPU-only ComfyUI, and publishes the image.

Paid GPU tests are opt-in through the `gpu_smoke` dispatch input. When set, Actions launches a disposable 48 GB Pod from that exact image digest (`VALIDATION_GPU_TYPES` overrides the card), renders every packaged workflow at 512 x 512, and checks dimensions, pixel variance and entropy. Those checks catch blank and passthrough output, not artistic quality. PNGs, system metadata and results upload as artifacts, and a `finally` block plus an unconditional cleanup step delete the Pod.

`scripts/test-runpod.py` also runs by hand: `--keep` leaves the Pod up for manual inspection, `--pod <id>` re-runs the matrix against a running Pod with randomised seeds, and `--cleanup` deletes it. Seeds are randomised on reuse because ComfyUI returns cached outputs in milliseconds for an identical prompt and seed, which would otherwise look like a passing run that executed nothing.

The GHCR package must stay public for anonymous template users. Configure Actions secrets `RUNPOD_API_KEY` and, if needed, `RUNPOD_REGISTRY_AUTH_ID`. Captured package versions live in `/opt/acdev/python-lock.txt` inside each image. Confirm build and GPU status in Actions before treating a revision as tested; `docs/VALIDATION.md` holds the current record.

## Troubleshooting

- **Connect opens ComfyUI with HTTP 403:** ComfyUI's browser-origin guard rejects cross-site page navigations, and a link clicked from the Runpod dashboard counts as cross-site. This image patches the guard at build time to permit only a safe top-level `GET /` navigation, leaving cross-site API, WebSocket, form and subresource requests blocked. On a Pod built from an older digest, paste `https://<pod-id>-8188.proxy.runpod.net` into a blank tab instead.
- **Connect shows ERR_INVALID_RESPONSE:** the same 403 with a body the browser cannot render. Treat it as above.
- **"Image blocked by safety filter":** the model itself renders that card. The filter is in the weights and there is no setting that disables it. Rephrasing, and leaving Magic Prompt on, is what reduces false positives.
- **Pseudo-words across the image:** the enhancer added an in-image text element. Leave `text_in_image` blank to strip it.
- **ComfyUI does not become ready:** first boot downloads the pinned weights before ComfyUI starts. Check the Pod logs; the service answers only once it reports device information.
- **Out of GPU memory:** use a 48 GB card. A 24 GB card cannot hold the distilled path.

## CPU thread sizing

CPU thread pools are sized automatically to the container CPU quota and available CPUs before PyTorch starts, avoiding host-sized pools that can throttle image scaling and export. Set `OMP_NUM_THREADS` and optionally `MKL_NUM_THREADS` to override; startup logs show the selected values. Actual speedup depends on the workload and has not been benchmarked for this revision.

### Workflow defaults

Seed controls default to randomize, including upstream controls and independent
first-pass/refinement seeds in nested panels. Random seeds use 15 digits where the
node range allows it. Use the native after-generate control, or the added seed mode
selector, to choose Fixed and enter a repeatable seed manually. These choices persist
when the workflow is saved. Model internals are folded into collapsed subgraphs and notes are
removed from packaged canvases. Inputs, editable controls and output previews remain
available. After editing or regenerating workflows, run
`python3 scripts/workflow_defaults.py` to reapply the canvas layout. These changes ship
with the next container image; existing pods need the updated image.
