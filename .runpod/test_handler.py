import asyncio, importlib.util, json
from pathlib import Path
from aiohttp import ClientSession, web
from aiohttp.test_utils import TestServer, TestClient

async def check(directory):
    path=Path(directory)/'.runpod/handler.py'
    spec=importlib.util.spec_from_file_location('handler',path);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
    ready=False
    async def stats(r):return web.json_response({'devices':[{'type':'cuda'}]} if ready else {},status=200 if ready else 503)
    async def echo(r):return web.Response(body=await r.read(),headers={'X-Test':'yes'})
    async def ws(r):
        s=web.WebSocketResponse();await s.prepare(r)
        async for msg in s:
            if isinstance(msg.data,str):await s.send_str(msg.data)
            else:await s.send_bytes(msg.data)
        return s
    upstream=web.Application(client_max_size=1024**3);upstream.router.add_get('/system_stats',stats);upstream.router.add_get('/ws',ws);upstream.router.add_route('*','/echo',echo)
    async with TestServer(upstream) as server, ClientSession(auto_decompress=False) as session:
        m.UPSTREAM=str(server.make_url('')).rstrip('/')
        async with TestClient(TestServer(m.create_app(session))) as client:
            assert (await client.get('/ping')).status==503
            assert (await client.post('/runsync',json={'input':{'healthcheck':True}})).status==503
            ready=True
            assert (await client.get('/ping')).status==200
            r=await client.post('/runsync',json={'input':{'healthcheck':True}});assert (await r.json())['status']=='COMPLETED'
            assert (await client.post('/',json={'healthcheck':True})).status==200
            assert (await client.post('/runsync',json={'input':{'bad':True}})).status==400
            data=b'video-content'*100000
            r=await client.put('/echo?name=test',data=data);assert await r.read()==data;assert r.headers['X-Test']=='yes'
            async with client.ws_connect('/ws') as socket:
                await socket.send_str('progress');assert (await socket.receive()).data=='progress'
                await socket.send_bytes(b'preview');assert (await socket.receive()).data==b'preview'
    for name in ['hub.json','tests.json']:json.loads((path.parent/name).read_text())
    print(directory+': PASS readiness transitions, Hub smoke payload, input rejection, HTTP upload/download, text/binary WebSockets, JSON')
async def main():
 await check(str(Path(__file__).resolve().parents[1]))
asyncio.run(main())
