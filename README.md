# IDEOGRAM 4 ComfyUI Studio

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
4. Launch on an NVIDIA **A100 80 GB**, with a **200 GB container disk** and no persistent volume. First boot downloads the pinned weights into `/workspace/ComfyUI/models`.
5. Open **Connect → HTTP 8000 / ComfyUI** after `/ping` becomes ready. HTTP 8188 reaches ComfyUI directly. No additional installation is required.
6. In the workflow sidebar, choose the base or distilled workflow, edit the prompt and shot settings, and click Queue. Save generated images before deleting/replacing the Pod.

Storage is temporary. The template does not attach a network volume. First-boot downloads are resumable, existing workflow edits are preserved, and no model weights or credentials are baked into the container.

## Simple workflows

- **01 Base Text to Image:** the official quantized NF4 conditional and unconditional branches; 48 steps, guidance 7.0.
- **03–04 Image Edit / Variation:** upload a picture and describe the desired final image; adjust edit strength to preserve more or less of the source.
- **02 Distilled Text to Image:** fal Instant's BF16, eight-step, single-branch checkpoint; guidance must remain 1.0. Distillation does not mean NF4/FP8 quantization.

The prompt panel provides scene, visual style, exact text, background and composition. It builds a structured JSON caption locally. Advanced users can paste a complete caption into `raw_json` to control object descriptions, bounding boxes and palettes. No hosted prompt rewriting service or extra API key is needed. Use a detailed scene description; this deterministic builder is not an LLM prompt upsampler.

The settings panel exposes dimensions, seed, steps, guidance, sampler, initial-noise multiplier, schedule mean/spread and text token limit. The default **noise multiplier is 2.0**, paired with a local flow-compatible **LCM** step implementation. This is an experimental adaptation of the [community noise/LCM approach](https://www.reddit.com/r/StableDiffusion/comments/1tz4fnf/ideogram_4_a_solution_for_removing_the_annoying/), not the exact third-party node chain or a guarantee about filtering or output quality. Use **Euler + noise 1.0** for a reference-style comparison. These controls affect local sampling only; they do not change hosted Ideogram API behavior.

The distilled path uses the [checkpoint author's documented zero-parameter unconditional compatibility module](https://huggingface.co/fal/ideogram-v4-instant), with no effective CFG branch. It is not bit-exact with fal's optimized hosted runtime. Only one pipeline is retained when switching modes. These Diffusers nodes run in the ComfyUI process and use the selected GPU; they do not expose separate ComfyUI model-loader sockets.

Prompt inspiration: [EvoLinkAI's curated examples](https://github.com/EvoLinkAI/awesome-ideogram-4.0-prompts). The packaged demonstration prompt is original. Official model notes: [Ideogram open weights](https://huggingface.co/ideogram-ai), [Ideogram inference code](https://github.com/ideogram-oss/ideogram-4). Check the model agreement for permitted use; the downloadable checkpoints use the Ideogram non-commercial model license.

## Environment variables

- `HF_TOKEN`: Hugging Face read credential, mapped to `{{ RUNPOD_SECRET_HUGGINGFACE_TOKEN }}`. Required; access must be approved for each gated repository.
- `HF_HOME=/workspace/.cache/huggingface`: Hugging Face cache/metadata location.
- `MODEL_MODE=both`: download both variants. `base` limits first-boot downloads. Ideogram `distilled` still needs the base repository's shared encoder, tokenizer and VAE components.
- `STUDIO_VERSION=4`: baked profile identity; changing this does not install another model generation.
- `PORT=8000`: browser/API gateway HTTP port.
- `PORT_HEALTH=8001`: readiness service; `/ping` returns 503 until ComfyUI responds with device information.
- `OMP_NUM_THREADS=8`, `MKL_NUM_THREADS=8`: runtime CPU-thread defaults; override to match the Pod's allocated CPU quota.
- `PUBLIC_KEY`: optional SSH public key for diagnostics. When present, the container starts SSH on port 2222; the template does not expose this port. The disposable Actions test exposes it only for its ephemeral key.

`RUNPOD_API_KEY` and `GITHUB_PACKAGES_PAT` are local deployment credentials only; never pass them into the worker container. GitHub Actions uses repository secrets for Runpod validation. The account's existing GHCR registry authorization is supplied separately to disposable test Pods where required.

## Build, validate and update

All container builds and runtime tests run in **GitHub Actions**. Do not build on the local workstation. Push to `develop` or `main`, or dispatch the build workflow. Paid GPU tests are opt-in through the `gpu_smoke` dispatch input; ordinary pushes build and run CPU checks only. The workflow runs source checks, builds on an Actions runner, starts a CPU-only ComfyUI service inside the build to verify graph schemas, then publishes the image. When dispatched with `gpu_smoke=true`, it launches a disposable A100 Pod using that exact image digest and generates a 512×512 image and an image-edit result with each checkpoint, grouping each pair to keep that model loaded. Validation checks dimensions, pixel variance and entropy; these detect blank outputs, not artistic quality. PNGs, system metadata and results are uploaded as Actions artifacts. A `finally` block and an unconditional cleanup step delete the test Pod.

The package must be public on GHCR for anonymous template users; account registry credentials can support private validation. Configure Actions secrets `RUNPOD_API_KEY` and, if needed, `RUNPOD_REGISTRY_AUTH_ID`. The `.runpod` listing uses the same image build and environment defaults; its required readiness test does not replace the GPU generation tests. For Serverless browser use, keep exactly one active worker and supply Runpod authentication on HTTP and WebSocket requests. The Pod template is the straightforward browser deployment.

Build and GPU-validation status must be confirmed in Actions before treating a revision as tested. Captured package versions are stored in `/opt/acdev/python-lock.txt` inside each image. To update a model generation, add a new version profile, regenerate its workflow defaults and manifests, update the corresponding container tags, and repeat the remote tests. No runtime dependency upgrades or branch-head model downloads occur during Pod startup.

## Image editing and model reuse

Local Ideogram 4 does not provide the hosted 4.5 instruction/Precise Edit model. These workflows perform **image-to-image reconstruction and variation** using the same loaded model, VAE and text encoder as generation. The source is VAE-encoded, normalized into the pipeline latent format, blended with noise at a shortened schedule, and denoised toward the caption. It is not a dedicated instruction-following or masked-inpainting model. Describe the desired final scene rather than assuming localized semantic changes will be exact.

`edit_strength=0.5` is the starting point: lower values retain more source structure; 1.0 approaches a fresh generation, and 0 returns the resized source. The initial-noise multiplier also affects the preservation/change balance. Use Euler with noise 1.0 for a reference-style comparison. The global pipeline cache reuses one loaded base or distilled pipeline for generation and editing; changing the variant releases the old pipeline before loading the other.
