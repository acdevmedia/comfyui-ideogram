# Ideogram 4 Image ComfyUI One-Click

[![Runpod](https://api.runpod.io/badge/acdevmedia/comfyui-ideogram)](https://console.runpod.io/hub/listing/acdevmedia/comfyui-ideogram)

Ideogram 4: local base and fal Instant distilled image generation inside ComfyUI. Version 4 is the latest downloadable open-weight Ideogram family verified for this package; hosted Ideogram 4.5 is not included.

Container: **`ghcr.io/acdevmedia/ideogram-comfyui:4`**. Image releases also receive a version tag (`4.0.0`) and an immutable `sha-<commit>` tag. Source pins, model revisions and checksums live under `versions/4/`. New model generations get their own profile and container major tag; rebuilds retain the model family tag and always get a new commit tag.

## Start on Runpod

1. Sign in to Hugging Face and accept the model access agreements for each linked repository using the account that owns your token:
   - [ideogram-ai/ideogram-4-nf4-diffusers](https://huggingface.co/ideogram-ai/ideogram-4-nf4-diffusers)
   - [fal/ideogram-v4-instant](https://huggingface.co/fal/ideogram-v4-instant)
   Agreements apply separately to each repository. Accepting one does not grant access to the others.
2. Create a Hugging Face **read** token and add it to Runpod Secrets as **HUGGINGFACE_TOKEN**. The template maps this secret to `HF_TOKEN`; do not paste credentials into public template fields.
3. Create/update the template with `python3 scripts/create-runpod-template.py`. Use `--dry-run` to review its payload. This small API helper reads the ignored local `.env`; it does not build an image or download models.
4. Launch on a **48 GB** GPU with a **200 GB container disk** and no persistent volume. **L40S** and **A40** are both validated; the L40S is roughly twice as fast for this workload, and **RTX A6000** is the other 48 GB option. Peak residency is about 25 GB on the distilled path: an 18.6 GB BF16 transformer plus the shared 5.5 GB text encoder and VAE. A 24 GB card is not enough; an 80 GB A100 is not required and costs several times as much. First boot downloads the pinned weights into `/workspace/ComfyUI/models`.
5. Open **Connect → HTTP 8188 / ComfyUI**. The template exposes ComfyUI only; the service reports Ready once the weights finish downloading. If the Connect link returns **HTTP 403**, open a blank tab and paste `https://<pod-id>-8188.proxy.runpod.net` into the address bar — see Troubleshooting. No additional installation is required.
6. In the workflow sidebar, choose the base or distilled workflow, edit the prompt and shot settings, and click Queue. Save generated images before deleting/replacing the Pod.

Storage is temporary. The template does not attach a network volume. First-boot downloads are resumable, existing workflow edits are preserved, and no model weights or credentials are baked into the container.

## Simple workflows

- **01 Base Text to Image:** a plain prompt, Magic Prompt on, running the official **4.0 Default 20** preset against the quantized NF4 conditional and unconditional branches.
- **03–04 Image Edit / Variation:** upload a picture and describe the desired final image; adjust edit strength to preserve more or less of the source.
- **02 Distilled Text to Image:** fal Instant's BF16, eight-step, single-branch checkpoint; guidance must remain 1.0. Distillation does not mean NF4/FP8 quantization.

Type a plain-English prompt and press Queue. **Magic Prompt** is on by default: Ideogram's own prompt enhancer rewrites your sentence into the structured JSON caption the model was trained on, including bounding-box layout, and generation is schema-constrained so the caption is always valid. Nothing else is required, and no JSON is involved.

A plain sentence is never sent to the model raw. With Magic Prompt off, the node wraps it in a minimal valid caption so the model still receives the format it was trained on; if Magic Prompt returns something unusable, the node logs what came back and falls back to that same wrapper rather than rendering a blank frame. The caption actually used is returned as the node's second output, so you can always see what the model was given.

Magic Prompt runs locally through a 1.2 GB generative head grafted onto the text encoder that is already loaded, so it adds no second model and makes no API call. It is reproducible from the seed. Turning it off sends your text to the model unchanged, which the model's authors advise against because it was trained only on structured captions.

### Advanced: writing the caption yourself

**10 Advanced Structured Caption** adds the caption builder for anyone who wants explicit control, and the simple workflows never show it. It emits the published schema in the exact key order the upstream caption verifier checks, and exposes:

- **scene** → `high_level_description`; **background** → the environment, required by the schema.
- **elements** → one per line. A bare line is an object with no box; otherwise pipe-separated:

  ```
  obj  | y_min,x_min,y_max,x_max | description                     | #HEX,#HEX
  text | y_min,x_min,y_max,x_max | THE WORDS | description         | #HEX,#HEX
  ```

  Boxes are `[y_min, x_min, y_max, x_max]` in **normalized 0–1000** coordinates from the top left, independent of canvas size. Use `-` to omit one.
- **aesthetics**, **lighting**, **medium**, **photo_or_art_style**, **color_palette** → `style_description`, supplied together or left entirely empty.
- **raw_json** → paste a complete caption and bypass the builder.

Malformed boxes, palettes and partial style groups are rejected locally, before anything reaches a paid GPU. Schema reference: [Ideogram 4 prompting guide](https://github.com/ideogram-oss/ideogram-4/blob/main/docs/prompting.md).

The settings panel exposes a sampler preset, dimensions, seed, steps, guidance, sampler, initial-noise multiplier, schedule mean/spread and text token limit. Canvas defaults to **1280 × 720**.

**Sampler presets** carry Ideogram's official per-step guidance schedule, whose final low-guidance "polish" steps are part of the schedule rather than an extra stage:

| Preset | Steps | Guidance schedule | mu | std |
| --- | --- | --- | --- | --- |
| `4.0 Default 20` (default) | 20 | 18 × 7.0, then 2 × 3.0 | 0.0 | 1.75 |
| `4.0 Quality 48` | 48 | 45 × 7.0, then 3 × 3.0 | 0.0 | 1.5 |
| `4.0 Turbo 12` | 12 | 11 × 7.0, then 1 × 3.0 | 0.5 | 1.75 |
| `custom` | yours | constant `guidance` | yours | yours |

A preset owns its step count, mu and std, because the schedule's length must equal the step count. `custom` applies a constant guidance scale instead, which is what the earlier releases did at every step; that is a deviation from the reference configuration and degrades output noticeably at high step counts.

The **initial-noise multiplier** defaults to **1.0**, the value the flow schedule expects. Raising it starts sampling at a higher variance than training, which is an [experimental community adaptation](https://www.reddit.com/r/StableDiffusion/comments/1tz4fnf/ideogram_4_a_solution_for_removing_the_annoying/) rather than a supported setting, and it visibly degrades structure and text rendering. The `lcm` sampler is likewise experimental and intended for few-step runs; `euler` is the default and matches the reference pipeline. These controls affect local sampling only.

**There is no negative prompt.** Ideogram 4's pipeline takes none: its unconditional branch is built from zeroed inputs rather than from encoded negative text, so there is no channel to put one in. Describe what you do want in the structured caption.

The distilled path uses the [checkpoint author's documented zero-parameter unconditional compatibility module](https://huggingface.co/fal/ideogram-v4-instant), with no effective CFG branch. It is not bit-exact with fal's optimized hosted runtime. Only one pipeline is retained when switching modes. These Diffusers nodes run in the ComfyUI process and use the selected GPU; they do not expose separate ComfyUI model-loader sockets.

Prompt inspiration: [EvoLinkAI's curated examples](https://github.com/EvoLinkAI/awesome-ideogram-4.0-prompts). The packaged demonstration prompt is original. Official model notes: [Ideogram open weights](https://huggingface.co/ideogram-ai), [Ideogram inference code](https://github.com/ideogram-oss/ideogram-4). Check the model agreement for permitted use; the downloadable checkpoints use the Ideogram non-commercial model license.

## Seeds

The seed widget carries ComfyUI's standard **control after generate** control, set to `randomize` in every packaged workflow, so each run uses a new seed. Set it to `fixed` to reproduce an exact image, or `increment` to walk a series. Earlier releases pinned the seed at 42 with the control disabled, which made every run of a workflow produce the same picture.

## Image preview ribbon

A strip of recent output images sits along the bottom of the ComfyUI window and refreshes as each queued graph finishes, so you can queue a long batch and watch it fill.

Click any thumbnail to open the viewer. **Left and right arrow keys** move through the batch, **space** picks the current image, **D** downloads it and **Escape** closes. The tick in the corner of a thumbnail picks it without opening the viewer. **Download picked** then saves just those files, which is the point: queue fifty, skim them, keep the three that worked.

Picks live for the session and are never uploaded. The ribbon reads the recent `/history` entries through ComfyUI's own `/view` endpoint, skips transient previews, and never scans the output directory.

## Environment variables

- `HF_TOKEN`: Hugging Face read credential, mapped to `{{ RUNPOD_SECRET_HUGGINGFACE_TOKEN }}`. Required; access must be approved for each gated repository.
- `HF_HOME=/workspace/.cache/huggingface`: Hugging Face cache/metadata location.
- `MODEL_MODE=both`: download both variants. `base` limits first-boot downloads. Ideogram `distilled` still needs the base repository's shared encoder, tokenizer and VAE components.
- `STUDIO_VERSION=4`: baked profile identity; changing this does not install another model generation.
- `PORT=8000`: gateway HTTP port used by the Runpod Hub/Serverless listing. The Pod template does not expose it; Pod users reach ComfyUI directly on 8188.
- `PORT_HEALTH=8001`: readiness service used by the Hub listing; `/ping` returns 503 until ComfyUI responds with device information. Not exposed by the Pod template.
- `OMP_NUM_THREADS=8`, `MKL_NUM_THREADS=8`: runtime CPU-thread defaults; override to match the Pod's allocated CPU quota.
- `PUBLIC_KEY`: optional SSH public key for diagnostics. When present, the container starts SSH on port 2222; the template does not expose this port. The disposable Actions test exposes it only for its ephemeral key.

`RUNPOD_API_KEY` and `GITHUB_PACKAGES_PAT` are local deployment credentials only; never pass them into the worker container. GitHub Actions uses repository secrets for Runpod validation. The account's existing GHCR registry authorization is supplied separately to disposable test Pods where required.

## Build, validate and update

All container builds and runtime tests run in **GitHub Actions**. Do not build on the local workstation. Push to `develop` or `main`, or dispatch the build workflow. Paid GPU tests are opt-in through the `gpu_smoke` dispatch input; ordinary pushes build and run CPU checks only. The workflow runs source checks, builds on an Actions runner, starts a CPU-only ComfyUI service inside the build to verify graph schemas, then publishes the image. When dispatched with `gpu_smoke=true`, it launches a disposable 48 GB L40S Pod using that exact image digest (override with `VALIDATION_GPU_TYPES`) and generates a 512×512 image and an image-edit result with each checkpoint, grouping each pair to keep that model loaded. Validation checks dimensions, pixel variance and entropy; these detect blank outputs, not artistic quality. PNGs, system metadata and results are uploaded as Actions artifacts. A `finally` block and an unconditional cleanup step delete the test Pod.

The package must be public on GHCR for anonymous template users; account registry credentials can support private validation. Configure Actions secrets `RUNPOD_API_KEY` and, if needed, `RUNPOD_REGISTRY_AUTH_ID`. The `.runpod` listing uses the same image build and environment defaults; its required readiness test does not replace the GPU generation tests. For Serverless browser use, keep exactly one active worker and supply Runpod authentication on HTTP and WebSocket requests. The Pod template is the straightforward browser deployment.

Build and GPU-validation status must be confirmed in Actions before treating a revision as tested. Captured package versions are stored in `/opt/acdev/python-lock.txt` inside each image. To update a model generation, add a new version profile, regenerate its workflow defaults and manifests, update the corresponding container tags, and repeat the remote tests. No runtime dependency upgrades or branch-head model downloads occur during Pod startup.

## Image editing and model reuse

Local Ideogram 4 does not provide the hosted 4.5 instruction/Precise Edit model. These workflows perform **image-to-image reconstruction and variation** using the same loaded model, VAE and text encoder as generation. The source is VAE-encoded, normalized into the pipeline latent format, blended with noise at a shortened schedule, and denoised toward the caption. It is not a dedicated instruction-following or masked-inpainting model. Describe the desired final scene rather than assuming localized semantic changes will be exact.

`edit_strength=0.5` is the starting point: lower values retain more source structure; 1.0 approaches a fresh generation, and 0 returns the resized source. The initial-noise multiplier also affects the preservation/change balance. Use Euler with noise 1.0 for a reference-style comparison. The global pipeline cache reuses one loaded base or distilled pipeline for generation and editing; changing the variant releases the old pipeline before loading the other.

## Troubleshooting

- **Connect opens ComfyUI with HTTP 403:** ComfyUI's browser-origin guard rejects cross-site page navigations, and a link clicked from the Runpod dashboard or any other site counts as cross-site. This image patches the guard at build time to permit only a safe top-level `GET /` navigation; cross-site API, WebSocket, form and subresource requests stay blocked. On a Pod built from an older digest, open a blank tab and paste `https://<pod-id>-8188.proxy.runpod.net` into the address bar, which the browser sends as a same-origin navigation.
- **Connect shows ERR_INVALID_RESPONSE:** the same 403, returned with a body the browser cannot render. Treat it as the entry above.
- **ComfyUI does not become ready:** first boot downloads the pinned weights before ComfyUI starts. Check the Pod logs; the service answers only after it reports device information.
- **Out of GPU memory:** use a 48 GB card. A 24 GB card cannot hold the distilled path.
