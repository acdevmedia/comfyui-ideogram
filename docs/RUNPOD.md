# Runpod deployment

Use the repository [README](../README.md) for the Ideogram 4 setup. Publish `ghcr.io/acdevmedia/ideogram-comfyui:4` through GitHub Actions, then run `python3 scripts/create-runpod-template.py` to create or update the Ideogram template. Use `--dry-run` to review its payload. The script matches the single account template by name; the Eros, Sulphur and FLUX templates are not touched.
