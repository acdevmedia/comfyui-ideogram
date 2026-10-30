# Same pinned Runpod/CUDA foundation as the Eros and Sulphur packages.
FROM runpod/comfyui:1.4.1-comfyuiv0.35.0-cuda12.8@sha256:d411ebacf3fdbc98ded7f78f06ac12aae20c08041cde79ab08173c156d04aae5
SHELL ["/bin/bash", "-euo", "pipefail", "-c"]
RUN python3 -m pip install --no-cache-dir --upgrade --index-url https://download.pytorch.org/whl/cu128 \
    'torch==2.11.0+cu128' 'torchvision==0.26.0+cu128' 'torchaudio==2.11.0+cu128'
RUN mkdir -p /opt/acdev/ComfyUI && curl -fsSL https://github.com/Comfy-Org/ComfyUI/archive/b5a432157de6b8884f81104cd02926adf4d597e4.tar.gz | tar xz --strip-components=1 -C /opt/acdev/ComfyUI
RUN python3 -m pip install --no-cache-dir -r /opt/acdev/ComfyUI/requirements.txt \
    'huggingface_hub==2.3.0' 'transformers==5.21.0' 'diffusers==0.42.0' 'accelerate==1.13.0' 'bitsandbytes==0.49.2' 'outlines==1.3.3'
COPY custom_nodes/acdev_studio /opt/acdev/ComfyUI/custom_nodes/acdev_studio
COPY scripts /opt/acdev/scripts
COPY config /opt/acdev/config
COPY versions /opt/acdev/versions
COPY frontend/image-gallery/ /opt/acdev/ComfyUI/web/extensions/ACDEV-IDEOGRAM4-image-gallery/
COPY .runpod/handler.py /opt/acdev/handler.py
RUN python3 /opt/acdev/scripts/patch-comfyui-proxy-guard.py /opt/acdev/ComfyUI/server.py
RUN chmod +x /opt/acdev/scripts/*.sh && python3 /opt/acdev/scripts/check-build.py
ARG VCS_REF=development
RUN printf '%s\n' "$VCS_REF" > /opt/acdev/image-commit && python3 -m pip freeze > /opt/acdev/python-lock.txt
ENV PYTHONWARNINGS=ignore::FutureWarning PYTHONUNBUFFERED=1 HF_HOME=/workspace/.cache/huggingface STUDIO_VERSION=4 MODEL_MODE=both PORT=8000 PORT_HEALTH=8001
EXPOSE 8188 8000 8001 2222
ENTRYPOINT ["python3", "/opt/acdev/handler.py", "/opt/acdev/scripts/start.sh"]
