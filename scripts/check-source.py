"""Lightweight checks intended for GitHub Actions, without models or GPU."""
import ast,json,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=json.loads((root/'config/profile.json').read_text())
assert len(p['comfyui_commit'])==40
for path in root.rglob('*.py'):
 if '.git' not in path.parts:ast.parse(path.read_text(),filename=str(path))
subprocess.run(['bash','-n',str(root/'scripts/start.sh')],check=True)
for path in root.rglob('*.json'):
 if '.git' not in path.parts:json.loads(path.read_text())
for m in p['models']:assert len(m['sha256'])==64 and len(m['revision'])==40 and m['size']>0
for m in p.get('snapshots',[]):assert len(m['revision'])==40
for path in (root/'versions'/p['version']/'api').glob('*.json'):
 graph=json.loads(path.read_text());assert any(n['class_type']=='SaveImage' for n in graph.values())
 for n in graph.values():
  for value in n['inputs'].values():
   if isinstance(value,list) and len(value)==2 and isinstance(value[0],str):assert value[0] in graph
assert (root/'Dockerfile').read_text()==(root/'.runpod/Dockerfile').read_text()
assert 'HF_TOKEN' not in (root/'Dockerfile').read_text()
print('PASS: source syntax, pinned model metadata, graphs and Dockerfile parity')

# Exercise quota-aware thread sizing without importing torch or requiring a GPU.
subprocess.run(["bash",str(root/"scripts/test-cpu-threads.sh")],check=True)
