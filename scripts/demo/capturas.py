import asyncio, base64, json, subprocess, sys, time, urllib.request
import websockets
D = sys.argv[1]; OUT = D + "\\img\\"
BASE = "http://127.0.0.1:8091/"
EDGE = r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe"
proc = subprocess.Popen([EDGE, "--headless=new", "--remote-debugging-port=9333", "--user-data-dir=" + D + "\\edge", "--no-first-run", "--hide-scrollbars", "about:blank"],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
time.sleep(5)
alvo = json.loads(urllib.request.urlopen("http://127.0.0.1:9333/json").read())
ws_url = [t for t in alvo if t["type"] == "page"][0]["webSocketDebuggerUrl"]

async def main():
    async with websockets.connect(ws_url, max_size=50_000_000) as ws:
        n = [0]
        async def cmd(m, **p):
            n[0] += 1; i = n[0]; await ws.send(json.dumps({"id": i, "method": m, "params": p}))
            while True:
                r = json.loads(await ws.recv())
                if r.get("id") == i: return r.get("result", {})
        async def js(code):
            r = await cmd("Runtime.evaluate", expression=code, awaitPromise=True, returnByValue=True); return r.get("result", {}).get("value")
        async def vista(w, h, mobile=False):
            await cmd("Emulation.setDeviceMetricsOverride", width=w, height=h, deviceScaleFactor=1, mobile=mobile)
        async def abre(url, espera=2.5):
            await cmd("Page.navigate", url=url); await asyncio.sleep(espera)
        async def foto(nome):
            r = await cmd("Page.captureScreenshot", format="png"); open(OUT + nome + ".png", "wb").write(base64.b64decode(r["data"])); print("ok", nome)
        async def login(user, senha):
            await js("fetch('/api/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({usuario:%r,senha:%r})}).then(r=>r.status)" % (user, senha))
        await cmd("Page.enable"); await vista(1440, 900)
        await abre(BASE, 3); await foto("01-login")
        await login("demo", "demo-demo-123")
        await js("localStorage.setItem('tour_visto','1')")
        await js("location.reload()"); await asyncio.sleep(5); await js("ir('inicio')"); await asyncio.sleep(2); await foto("02-inicio")
        await js("ir('alicia')"); await asyncio.sleep(2.5); await foto("03-alicia")
        await js("ir('musica')"); await asyncio.sleep(3); await foto("04-musica")
        await js("irMusica('artista','DJ Aurora')"); await asyncio.sleep(1.5); await foto("05-musica-artista")
        await js("irMusica('generos')"); await asyncio.sleep(1.2); await foto("06-musica-generos")
        # barra do player (só visual, com uma faixa de exemplo)
        await js("ir('musica'); irMusica('inicio'); const b=document.querySelector('#barra'); b.style.display='grid'; document.querySelector('#bTit').textContent='Horizonte Neon'; document.querySelector('#bCanal').textContent='DJ Aurora'; document.querySelector('#bPlay').textContent='⏸'; document.querySelector('#bSeek').value=380; document.querySelector('#bT0').textContent='1:12'; document.querySelector('#bT1').textContent='3:05';")
        await asyncio.sleep(1.2); await foto("07-musica-player")
        await js("document.querySelector('#barra').style.display='none'")
        await js("ir('jogos')"); await asyncio.sleep(3); await foto("08-jogos")
        await js("ir('arquivos')"); await asyncio.sleep(2); await foto("09-arquivos")
        await js("ir('rpg')"); await asyncio.sleep(2.5); await foto("10-rpg")
        await js("ir('servidor')"); await asyncio.sleep(16); await foto("11-servidor")
        await js("ir('registros')"); await asyncio.sleep(2.5); await foto("12-registros")
        # modo TV
        await vista(1920, 1080); await js("document.body.classList.add('tv'); ir('inicio')"); await asyncio.sleep(2); await foto("13-modo-tv"); await js("document.body.classList.remove('tv')")
        # celular
        await vista(390, 844, True); await js("ir('inicio')"); await asyncio.sleep(3); await foto("14-celular-inicio")
        await js("ir('musica')"); await asyncio.sleep(2.5); await foto("15-celular-musica")
        await js("ir('jogos')"); await asyncio.sleep(2.5); await foto("16-celular-jogos")
        # visitante
        await vista(1440, 900); await js("fetch('/api/logout',{method:'POST'}).then(()=>location.reload())"); await asyncio.sleep(4); await js("document.querySelector('#lgVisitante').click()"); await asyncio.sleep(3.5); await foto("17-visitante")
asyncio.run(main()); proc.terminate()
