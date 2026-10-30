# Validation status — Ideogram 4

## Container

Commit `baab0b7` built and published in [GitHub Actions](https://github.com/acdevmedia/comfyui-ideogram/actions). Published digest: `sha256:377841fd52b99dda1c31b9af9bb8a6edb469bbbb85f650d5f88b30fd9a9b29ec`. Source checks, pinned model metadata, graph schemas and Dockerfile parity passed.

## GPU generation — NVIDIA A40 48 GB (CI, run #4)

All four packaged graphs executed on a disposable A40 Pod (`$0.59/hr`) from digest `sha256:450a6e7f21254be299e68a1ca68fc21101c5f66349243195903001c5e1115b79`, built from the commit that adds the ComfyUI origin-guard patch and the ComfyUI-only port layout:

| Workflow | Elapsed | Result |
| --- | --- | --- |
| 01 Base Text to Image | 67.92 s | 512 × 512, entropy 9.15 |
| 03 Base Image Edit | 34.24 s | 512 × 512, entropy 8.53, differs from source |
| 02 Distilled Text to Image | 23.80 s | 512 × 512, entropy 9.08 |
| 04 Distilled Image Edit | 13.27 s | 512 × 512, entropy 9.27 |

Elapsed times include checkpoint swaps between variants, so they are not per-image generation times. PNGs, `system.json` and `validation.json` are attached to the run as the `ideogram-4-gpu-validation` artifact.

## GPU generation — NVIDIA L40S 48 GB

The same four graphs ran earlier on an L40S (`$1.09/hr`) from digest `sha256:377841fd52b99dda1c31b9af9bb8a6edb469bbbb85f650d5f88b30fd9a9b29ec`: base text-to-image 34.60 s, base edit 24.84 s, distilled text-to-image 12.86 s, distilled edit 13.46 s. The L40S is roughly twice as fast as the A40 for this workload at under twice the price.

The validation pod requests L40S, RTX A6000 and A40 with `gpuTypePriority: availability`, so the card varies per run; each record above names the card measured. An A100 80 GB is not required. Peak residency is about 25 GB on the distilled path (18.6 GB BF16 transformer plus the shared 5.5 GB text encoder and VAE); a 24 GB card is not sufficient.

## Not yet validated

The ComfyUI origin-guard patch is applied during the image build, and the build fails if the pinned `server.py` guard does not match exactly once, so the patched code is present in the published image. Its runtime effect has not been confirmed against a live Pod: no cross-site navigation has been sent to a Pod running this digest. The ComfyUI-only port layout is exercised by the run above, which provisioned with `8188/http` only and reached readiness through ComfyUI directly.

## Harness notes

Remote validation is opt-in through the `gpu_smoke` dispatch input; ordinary pushes build and run CPU checks only. `scripts/test-runpod.py --keep` leaves the Pod running for manual inspection, `--pod <id>` re-runs the matrix against a running Pod, and `--cleanup` deletes it. Pod reuse randomises seeds, because ComfyUI returns cached outputs in milliseconds for an identical prompt and seed, which would otherwise look like a passing run that never executed.

## Resolved — Magic Prompt blank render (2026-10-30)

Fixed and verified on a kept L40S-class Pod from digest
`sha256:...` built from `530300e`. All five graphs passed, including the plain-prompt
workflow that previously rendered a near-white frame:

| Workflow | Elapsed |
| --- | --- |
| 10 Advanced Structured Caption | 42.89 s |
| 01 Base Text to Image | 42.64 s |
| 03 Base Image to Image | 32.42 s |
| 02 Distilled Text to Image | 32.57 s |
| 04 Distilled Image to Image | 21.93 s |

The base poster render was inspected visually: legible masthead typography, correct subject and
composition. The enhancer ran successfully rather than falling back — the fallback logs whenever it
cannot parse a caption, and the Pod's log contains no such entry. The earlier hypothesis that the
NF4-quantized text encoder made the grafted enhancer head unusable was **wrong**; it works.

## Observed behaviour

- **Magic Prompt reduces spurious safety refusals.** On one prompt with identical settings, the
  enhancer produced an image while the plain-wrapper path returned the filter's placeholder card.
  This matches Ideogram's documentation that plain text triggers false positives more often than
  structured captions. One pair of observations, not a measured rate.
- **The enhancer adds in-image text unprompted**, which the distilled checkpoint renders as
  pseudo-words. `text_in_image` defaults off and strips those elements from the caption.

## Still unverified

The ComfyUI origin-guard patch is present in the published image and the build fails if it does not
apply, but no cross-site navigation has yet been confirmed against a live Pod running it.
