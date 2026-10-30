"""Runpod LB entrypoint: supervise ComfyUI and proxy HTTP/WebSocket traffic."""
import asyncio
import contextlib
import os
import signal
import sys

from aiohttp import ClientError, ClientSession, ClientTimeout, WSMsgType, web

UPSTREAM = 'http://127.0.0.1:8188'
HOP_HEADERS = {'connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization',
               'te', 'trailer', 'transfer-encoding', 'upgrade', 'content-length'}


async def readiness(request):
    try:
        async with request.app['client'].get(UPSTREAM + '/system_stats', timeout=ClientTimeout(total=5)) as response:
            if response.status == 200:
                stats = await response.json()
                if stats.get('devices'):
                    return web.json_response({'status': 'ready'})
    except (ClientError, OSError, asyncio.TimeoutError, ValueError):
        pass
    return web.json_response({'status': 'initializing'}, status=503)


async def smoke_test(request):
    payload = await request.json()
    payload = payload.get('input', payload)
    if payload != {'healthcheck': True}:
        raise web.HTTPBadRequest(text='Only {"healthcheck": true} is supported; use the ComfyUI API for generation.')
    response = await readiness(request)
    if response.status != 200:
        return response
    return web.json_response({'status': 'COMPLETED', 'output': {'comfyui': 'ready'}})


async def relay(source, target):
    async for message in source:
        if message.type == WSMsgType.TEXT:
            await target.send_str(message.data)
        elif message.type == WSMsgType.BINARY:
            await target.send_bytes(message.data)
        elif message.type in (WSMsgType.CLOSE, WSMsgType.CLOSED, WSMsgType.ERROR):
            break


async def proxy(request):
    client = request.app['client']
    url = UPSTREAM + request.raw_path
    headers = {k: v for k, v in request.headers.items() if k.lower() not in HOP_HEADERS}
    if request.headers.get('Upgrade', '').lower() == 'websocket':
        async with client.ws_connect(url, headers=headers, autoping=True) as upstream:
            socket = web.WebSocketResponse()
            await socket.prepare(request)
            tasks = [asyncio.create_task(relay(socket, upstream)), asyncio.create_task(relay(upstream, socket))]
            try:
                await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            finally:
                for task in tasks:
                    task.cancel()
                await asyncio.gather(*tasks, return_exceptions=True)
                await socket.close()
            return socket
    try:
        async with client.request(request.method, url, headers=headers, data=request.content,
                                  allow_redirects=False) as upstream:
            response = web.StreamResponse(status=upstream.status, headers={
                k: v for k, v in upstream.headers.items() if k.lower() not in HOP_HEADERS})
            await response.prepare(request)
            async for chunk in upstream.content.iter_chunked(1024 * 1024):
                await response.write(chunk)
            await response.write_eof()
            return response
    except (ClientError, OSError, asyncio.TimeoutError):
        raise web.HTTPServiceUnavailable(text='ComfyUI is starting; retry after model provisioning.')


def create_app(client):
    app = web.Application(client_max_size=1024 ** 3)
    app['client'] = client
    app.router.add_get('/ping', readiness)
    app.router.add_post('/runsync', smoke_test)
    app.router.add_post('/', smoke_test)
    app.router.add_route('*', '/{path:.*}', proxy)
    return app


async def main():
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)
    process = await asyncio.create_subprocess_exec(*sys.argv[1:], start_new_session=True)
    async with ClientSession(timeout=ClientTimeout(total=None, sock_connect=10), auto_decompress=False) as client:
        runner = web.AppRunner(create_app(client))
        await runner.setup()
        for port in {int(os.getenv('PORT', '8000')), int(os.getenv('PORT_HEALTH', '8001'))}:
            await web.TCPSite(runner, '0.0.0.0', port).start()
        waiter = asyncio.create_task(process.wait())
        stopper = asyncio.create_task(stop.wait())
        try:
            await asyncio.wait([waiter, stopper], return_when=asyncio.FIRST_COMPLETED)
        finally:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(process.pid, signal.SIGTERM)
            try:
                await asyncio.wait_for(asyncio.shield(waiter), timeout=30)
            except asyncio.TimeoutError:
                with contextlib.suppress(ProcessLookupError):
                    os.killpg(process.pid, signal.SIGKILL)
                await waiter
            stopper.cancel()
            await runner.cleanup()
    return process.returncode if not stop.is_set() else 0


if __name__ == '__main__':
    sys.exit(asyncio.run(main()))
