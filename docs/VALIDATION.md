# Validation status — Ideogram 4

## Container

Commit `baab0b7` built and published in [GitHub Actions](https://github.com/acdevmedia/comfyui-ideogram/actions). Published digest: `sha256:377841fd52b99dda1c31b9af9bb8a6edb469bbbb85f650d5f88b30fd9a9b29ec`. Source checks, pinned model metadata, graph schemas and Dockerfile parity passed.

## GPU generation — NVIDIA L40S 48 GB

All four packaged graphs executed on a disposable L40S Pod (`$1.09/hr`) from the digest above:

| Workflow | Elapsed | Result |
| --- | --- | --- |
| 01 Base Text to Image | 34.60 s | 512 × 512, entropy 8.01 |
| 03 Base Image Edit | 24.84 s | 512 × 512, entropy 8.82, differs from source |
| 02 Distilled Text to Image | 12.86 s | 512 × 512, entropy 9.11 |
| 04 Distilled Image Edit | 13.46 s | 512 × 512, entropy 9.28 |

Checks cover dimensions, pixel variance and entropy, and for edits that the output differs from the uploaded source. They detect blank, uniform or passthrough output; they do not judge artistic quality, prompt adherence or text rendering accuracy. Each variant's generate/edit pair ran together so the checkpoint stayed loaded, confirming generation and editing share one loaded pipeline, VAE and text encoder.

Runs used the packaged defaults, including initial-noise multiplier 2.0 with the local flow-compatible LCM step. That these runs produced non-blank, high-entropy output does not establish any claim about filtering behaviour or comparative quality against the hosted service.

An earlier A100 80 GB run measured base text-to-image at 30.94 s and distilled at 10.86 s. The L40S is marginally slower and costs less, so it is the documented default. Peak residency is about 25 GB on the distilled path (18.6 GB BF16 transformer plus the shared 5.5 GB text encoder and VAE); a 24 GB card is not sufficient.

## Not yet validated

The ComfyUI origin-guard patch and the ComfyUI-only port layout landed after the digest above was built. They are verified by source tests and by patching a copy of the pinned `server.py`, but no Pod has yet been launched from an image containing them. Re-run the `gpu_smoke` dispatch against the next published digest before treating the 403 fix as confirmed in deployment.

## Harness notes

Remote validation is opt-in through the `gpu_smoke` dispatch input; ordinary pushes build and run CPU checks only. `scripts/test-runpod.py --keep` leaves the Pod running for manual inspection, `--pod <id>` re-runs the matrix against a running Pod, and `--cleanup` deletes it. Pod reuse randomises seeds, because ComfyUI returns cached outputs in milliseconds for an identical prompt and seed, which would otherwise look like a passing run that never executed.
