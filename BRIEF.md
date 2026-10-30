# IDEOGRAM 4 bundle maintenance brief

Build the Runpod ComfyUI bundle for `acdevmedia/comfyui-ideogram`, publishing `ghcr.io/acdevmedia/ideogram-comfyui:4`, the `4.0.0` version tag and immutable `sha-<commit>` tags through GitHub Actions. Do not build Docker images locally; this workstation has neither the storage nor the CPU budget.

Use the latest downloadable open-weight Ideogram family. As of 2026-10-30 that is Ideogram 4: `ideogram-ai/ideogram-4-nf4-diffusers` for the undistilled base and `fal/ideogram-v4-instant` for the distilled checkpoint, both at pinned revisions. Ideogram 4.5 is hosted-API only and has no published weights; do not label the package 4.5 until weights exist. Both repositories are gated and gated separately: the Hugging Face account that owns the deployed token must accept each agreement before first boot.

All current version assets live under `versions/4/`. Each model generation gets its own profile directory and its own container major tag; rebuilds keep the family tag and always add a new commit tag.

Keep the prompt panel simple — scene, style, exact text, background, composition — building the structured caption locally, with `raw_json` available for full control. Keep the sampling panel tweakable, and keep the initial-noise multiplier default at 2.0 with the local flow-compatible LCM step, which is an experimental adaptation of the community approach rather than a guarantee about filtering or output quality. Text-to-image and image editing must share the same loaded pipeline, VAE and text encoder. Do not include credentials, model weights or runtime artifacts in the repository or the image context.

Use source validation locally, image build plus CPU graph-schema checks in Actions, and real Runpod GPU generation before claiming runtime behaviour or output quality. Paid GPU validation is opt-in through the `gpu_smoke` dispatch input. `README.md` and `docs/VALIDATION.md` describe the current deployment state.
