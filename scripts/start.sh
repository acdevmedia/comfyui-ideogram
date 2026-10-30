#!/usr/bin/env bash
set -Eeuo pipefail
mkdir -p /workspace/logs /workspace/ComfyUI/{models,input,output,user/default/workflows}
# ComfyUI colourises its log unconditionally, with no TTY check, so the escape codes end up
# in captured logs as literal junk. Strip them before the console and the log file.
exec > >(sed -u $'s/\033\[[0-9;]*[A-Za-z]//g' | tee -a /workspace/logs/studio-startup.log) 2>&1
if [[ -n "${PUBLIC_KEY:-}" ]]; then
  install -d -m 700 /root/.ssh /run/sshd
  printf '%s\n' "$PUBLIC_KEY" > /root/.ssh/authorized_keys
  chmod 600 /root/.ssh/authorized_keys
  ssh-keygen -A
  /usr/sbin/sshd -p 2222
fi
export OMP_NUM_THREADS=${OMP_NUM_THREADS:-8} MKL_NUM_THREADS=${MKL_NUM_THREADS:-8}
python3 -c 'import torch; assert torch.cuda.is_available(), "An NVIDIA CUDA GPU is required"; print("GPU:",torch.cuda.get_device_name(0),"Torch:",torch.__version__,"CUDA:",torch.version.cuda)'
ln -sfn /opt/acdev/ComfyUI/custom_nodes /workspace/ComfyUI/custom_nodes
python3 /opt/acdev/scripts/download-models.py
python3 - <<'PY'
import json,shutil
from pathlib import Path
p=json.loads(Path('/opt/acdev/config/profile.json').read_text())
for workflow in (Path('/opt/acdev/versions')/p['version']/'workflows').glob('*.json'):
 target=Path('/workspace/ComfyUI/user/default/workflows')/(p['kind']+'-'+p['version']+'-'+workflow.name)
 if not target.exists():shutil.copyfile(workflow,target)
PY
cd /opt/acdev/ComfyUI
exec python3 main.py --listen 0.0.0.0 --port 8188 --base-directory /workspace/ComfyUI --disable-auto-launch --use-pytorch-cross-attention
