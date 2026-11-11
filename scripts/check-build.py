"""CPU-only container smoke test: boot ComfyUI and validate packaged graph schemas."""
import json,subprocess,time,urllib.request
from pathlib import Path
p=json.loads(Path('/opt/acdev/config/profile.json').read_text())
with open('/tmp/comfy-build-check.log','w') as log:
 proc=subprocess.Popen(['python3','main.py','--cpu','--listen','127.0.0.1','--port','18188'],cwd='/opt/acdev/ComfyUI',stdout=log,stderr=subprocess.STDOUT)
 try:
  for _ in range(180):
   if proc.poll() is not None:raise RuntimeError('ComfyUI exited during CPU smoke check')
   try:
    with urllib.request.urlopen('http://127.0.0.1:18188/object_info',timeout=3) as response:info=json.load(response)
    break
   except Exception:time.sleep(1)
  else:raise TimeoutError('ComfyUI CPU smoke check timed out')
  from verify_frontend import verify_frontend
  verify_frontend()
  for path in (Path('/opt/acdev/versions')/p['version']/'api').glob('*.json'):
   graph=json.loads(path.read_text())
   for node in graph.values():
    assert node['class_type'] in info,(path,node['class_type'])
    schema=info[node['class_type']]['input']
    for key in schema.get('required',{}):assert key in node['inputs'],(path,key)
   print('PASS graph schema:',path.name,flush=True)
 finally:
  proc.terminate()
  try:proc.wait(timeout=20)
  except subprocess.TimeoutExpired:proc.kill();proc.wait()
  print(Path('/tmp/comfy-build-check.log').read_text())
