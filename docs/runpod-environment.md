# Runpod template environment

Synced to account template **Ideogram 4 Image ComfyUI One-Click** (`uhvnoz8ypz`) on 2026-10-30.

[Open template](https://console.runpod.io/deploy?template=uhvnoz8ypz)

Image: `ghcr.io/acdevmedia/ideogram-comfyui:4`. Container disk: **200 GB**. Workspace: `/workspace`. Template service: `8188/http` (ComfyUI) and `3923/http` (copyparty). The gateway port 8000 is used by the Hub/Serverless listing only and is not exposed by the Pod template. No persistent volume is requested; `volumeInGb` is 0 and storage is temporary.

`config/runpod-template.json` holds the Pod defaults. `.runpod/template-source.json` records the account source. `.runpod/hub.json` exposes the same values through Hub inputs or fixed values. `.runpod/tests.json` uses the same defaults for readiness tests. `.runpod/test_template_sync.py` fails if any of those four files, this document or the README drift apart.

## Credentials

The file browser on port 3923 signs in with Runpod Secrets `COPYPARTY_USERNAME` and `COPYPARTY_SECRET`, which the template maps to `COPYPARTY_USERNAME` and `COPYPARTY_PASSWORD`.

Create Runpod Secret `HUGGINGFACE_TOKEN` with a Hugging Face read token, using the account that accepted the gated model agreements for both `ideogram-ai/ideogram-4-nf4-diffusers` and `fal/ideogram-v4-instant`. The two agreements are separate; accepting one does not grant access to the other. Secret references are passed through unchanged; no credential values are stored in this repository or baked into the image.

## Template variables

### `COPYPARTY_USERNAME`

Default: `{{ RUNPOD_SECRET_COPYPARTY_USERNAME }}`.

Username for the output file browser on port 3923, from Runpod Secret `COPYPARTY_USERNAME`.

### `COPYPARTY_PASSWORD`

Default: `{{ RUNPOD_SECRET_COPYPARTY_SECRET }}`.

Password for the output file browser, from Runpod Secret `COPYPARTY_SECRET`. Without both values the file browser does not start; ComfyUI is unaffected.

### `HF_TOKEN`

Default: `{{ RUNPOD_SECRET_HUGGINGFACE_TOKEN }}`.

Hugging Face read token supplied through the Runpod Secret HUGGINGFACE_TOKEN. Required; both gated repository agreements must be accepted by the same account before first boot.

### `HF_HOME`

Default: `/workspace/.cache/huggingface`.

Hugging Face cache and metadata directory on container storage.

### `MODEL_MODE`

Default: `both`.

Which checkpoints the first boot downloads: `both`, `base` or `distilled`. The distilled path still needs the base repository's shared encoder, tokenizer and VAE components, so `distilled` does not skip the base download entirely.

### `STUDIO_VERSION`

Default: `4`.

Baked profile identity, matching `versions/4/`. Changing it at runtime does not install another model generation.

### `PORT`

Default: `8000`.

Gateway HTTP and WebSocket port served by `.runpod/handler.py`. ComfyUI itself stays on 8188.

### `PORT_HEALTH`

Default: `8001`.

Readiness port. `/ping` returns 503 until ComfyUI reports device information, then 200.

## Hub additions and differences

The Pod template and the Hub listing build from the same Dockerfile and the same defaults. The Hub listing runs the readiness test in `.runpod/tests.json` on a 48 GB L40S with CUDA 12.8–13.0; that test establishes that the service starts and answers, not that generation quality is acceptable. A Serverless browser session requires exactly one active worker and authenticated HTTP and WebSocket access, as described in `.runpod/README.md`.

Workflow defaults apply to newly installed workflow files; existing user edits in `/workspace` are preserved across restarts.

## Account template metadata

Visibility: public. No custom entrypoint or start command is set; the image entrypoint supervises ComfyUI through the gateway handler. `startJupyter` and `startSsh` are false. SSH starts inside the container only when `PUBLIC_KEY` is supplied, and the template does not expose port 2222.
