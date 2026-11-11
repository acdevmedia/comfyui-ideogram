"""Verify the real ComfyUI HTTP server advertises and serves our seed controls."""
import json
import urllib.request


def verify_frontend(base='http://127.0.0.1:18188'):
    import subprocess
    import sys
    from pathlib import Path
    scripts = Path(__file__).resolve().parent
    subprocess.run([sys.executable, str(scripts / 'audit-seeds.py')], check=True)
    for name in ('test_workflow_dimensions.py', 'test_workflow_frame.py'):
        if (scripts / name).is_file():
            subprocess.run([sys.executable, str(scripts / name)], check=True)
    with urllib.request.urlopen(base + '/extensions', timeout=10) as response:
        extensions = json.load(response)
    path = '/extensions/acdev_workflow_defaults/main.js'
    assert path in extensions, ('Seed controls are missing from /extensions', extensions)
    with urllib.request.urlopen(base + path, timeout=10) as response:
        source = response.read().decode()
    assert 'ACDEV.WorkflowSeedDefaults' in source and 'prepareSeeds' in source
    print('PASS: ComfyUI advertises and serves workflow seed controls.', flush=True)


if __name__ == '__main__':
    import argparse
    import subprocess
    import tempfile
    import time
    parser = argparse.ArgumentParser()
    parser.add_argument('--comfy-root', required=True)
    args = parser.parse_args()
    with tempfile.TemporaryFile(mode='w+') as log:
        proc = subprocess.Popen(['python3', 'main.py', '--cpu', '--listen', '127.0.0.1', '--port', '18188'],
                                cwd=args.comfy_root, stdout=log, stderr=subprocess.STDOUT)
        try:
            for _ in range(180):
                if proc.poll() is not None:
                    raise RuntimeError('ComfyUI exited before the extension check')
                try:
                    with urllib.request.urlopen('http://127.0.0.1:18188/extensions', timeout=2):
                        break
                except OSError:
                    time.sleep(1)
            else:
                raise TimeoutError('ComfyUI extension check timed out')
            verify_frontend()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=20)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
            if proc.returncode not in (0, -15):
                log.seek(0)
                print(log.read())
