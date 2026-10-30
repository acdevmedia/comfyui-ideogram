#!/usr/bin/env python3
"""Allow RunPod's cross-site link navigation without allowing cross-site API calls."""
from __future__ import annotations

import argparse
from pathlib import Path

ORIGINAL = """        if 'Sec-Fetch-Site' in request.headers:
            sec_fetch_site = request.headers['Sec-Fetch-Site']
            if sec_fetch_site == 'cross-site':
                return web.Response(status=403)
"""

PATCHED = """        if 'Sec-Fetch-Site' in request.headers:
            sec_fetch_site = request.headers['Sec-Fetch-Site']
            if sec_fetch_site == 'cross-site':
                # RunPod opens the Pod's proxy URL from its dashboard. Permit
                # only a top-level GET of ComfyUI's root page; keep denying
                # cross-site API, websocket, form, and subresource requests.
                safe_runpod_navigation = (
                    request.method == 'GET'
                    and request.path == '/'
                    and request.headers.get('Sec-Fetch-Mode') == 'navigate'
                    and request.headers.get('Sec-Fetch-Dest') == 'document'
                )
                if not safe_runpod_navigation:
                    return web.Response(status=403)
"""


def patch_text(source: str) -> tuple[str, bool]:
    if PATCHED in source:
        return source, False
    if source.count(ORIGINAL) != 1:
        raise ValueError("Pinned ComfyUI origin guard did not match exactly once; refusing an unsafe patch.")
    return source.replace(ORIGINAL, PATCHED, 1), True


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("server_py", type=Path)
    args = parser.parse_args()
    source = args.server_py.read_text(encoding="utf-8")
    updated, changed = patch_text(source)
    if changed:
        args.server_py.write_text(updated, encoding="utf-8")
        print("[startup] Applied RunPod proxy navigation exception to ComfyUI's origin guard.", flush=True)
    else:
        print("[startup] RunPod proxy navigation exception is already applied.", flush=True)


if __name__ == "__main__":
    main()
