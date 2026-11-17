"""Alicia Server — painel web (FastAPI).

Login, status real do servidor, arquivos, chave da NVIDIA e monitor de acessos.
Nunca registramos senhas, chaves nem conteúdo de arquivos.
"""
import asyncio
import random
import re
import json
import logging.handlers
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

import psutil
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError
from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from itsdangerous import BadSignature, TimestampSigner

from . import alicia_ponte, rpg

RAIZ = Path(__file__).resolve().parents[2]            # alicia-server/
DADOS = Path(os.environ.get("ALICIA_DADOS", r"C:\AliciaServer\Alicia Server"))
ENV_FILE = RAIZ / ".env"                              # único lugar da chave NVIDIA
USERS_FILE = RAIZ / "painel" / "usuarios.json"        # ignorado pelo Git (*.json de dados)
LOG_DIR = RAIZ / "logs"
LOG_DIR.mkdir(exist_ok=True)
WEB = Path(__file__).parent / "web"
PASTAS = ["Documentos", "Filmes", "Séries", "Jogos", "Música"]
for p in PASTAS:
    (DADOS / p).mkdir(parents=True, exist_ok=True)

# ---------- Monitor de acessos: arquivo com rotação (cuidado com o HD) ----------
_h = logging.handlers.RotatingFileHandler(LOG_DIR / "acessos.log", maxBytes=2_000_000,
                                          backupCount=15, encoding="utf-8")
_h.setFormatter(logging.Formatter("%(message)s"))
_log = logging.getLogger("alicia.acessos")
_log.setLevel(logging.INFO)
_log.addHandler(_h)
_log.propagate = False


def registrar(servico, quem, ip, o_que, resultado="ok", tipo="info"):
    """Grava uma linha JSON no log. tipo: info | ok | aviso | erro | seguranca."""
    linha = {"t": datetime.now().strftime("%d/%m %H:%M:%S"), "ts": time.time(), "servico": servico,
             "quem": quem, "ip": ip, "o_que": o_que, "resultado": resultado, "tipo": tipo}
    _log.info(json.dumps(linha, ensure_ascii=False))


# ---------- Usuários, sessões e bloqueio de tentativas ----------
ph = PasswordHasher()
SEGREDO = (ENV_FILE.read_text(encoding="utf-8") if ENV_FILE.exists() else "")
SEGREDO_FILE = RAIZ / "painel" / ".segredo"
if not SEGREDO_FILE.exists():
    SEGREDO_FILE.write_text(os.urandom(32).hex())
assinador = TimestampSigner(SEGREDO_FILE.read_text())
falhas = {}  # ip -> (qtd, bloqueado_ate)


def usuarios():
    return json.loads(USERS_FILE.read_text(encoding="utf-8-sig")) if USERS_FILE.exists() else {}


CONFIG_PAINEL = RAIZ / "dados" / "config_painel.json"
(RAIZ / "dados").mkdir(exist_ok=True)


def config_painel():
    try:
        return json.loads(CONFIG_PAINEL.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def visitante_ativo():
    return bool(config_painel().get("visitante", True))   # ligado por padrão


def eh_convidado(nome):
    return bool(usuarios().get(nome or "", {}).get("convidado"))


def usuario_da_sessao(request: Request):
    tok = request.cookies.get("alicia_sessao")
    if not tok:
        return None
    try:
        nome, quando = assinador.unsign(tok, max_age=60 * 60 * 24 * 14, return_timestamp=True)
        nome = nome.decode()
    except BadSignature:
        return None
    if eh_convidado(nome) and (not visitante_ativo() or time.time() - quando.timestamp() > 60 * 60 * 24):
        return None   # visitante: a sessão vale 24 h e acaba na hora se o administrador desligar a entrada de visitantes
    return nome


# O visitante só usa Jogos, Música, Filmes e RPG. Nada de arquivos, registros, chave, usuários, Hermes nem Alicia.
BLOQUEADO_PARA_VISITANTE = ("/api/arquivos", "/api/logs", "/api/nvidia", "/api/usuarios", "/api/senha", "/api/hermes",
                            "/api/verificar", "/api/filmes/enviar", "/api/alicia/conversar", "/api/alicia/voz", "/api/alicia/musica", "/api/visitante/config")


def ip_de(request: Request):
    return request.client.host if request.client else "?"


def exigir_login(request: Request):
    u = usuario_da_sessao(request)
    if not u:
        raise HTTPException(401, "Faça login para continuar.")
    return u


# ---------- Chave da NVIDIA (.env) ----------
def ler_env():
    d = {}
    if ENV_FILE.exists():
        for l in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if "=" in l and not l.strip().startswith("#"):
                k, v = l.split("=", 1)
                d[k.strip()] = v.strip()
    return d


def gravar_env(chave):
    d = ler_env()
    d["NVIDIA_API_KEY"] = chave
    ENV_FILE.write_text("\n".join(f"{k}={v}" for k, v in d.items()) + "\n", encoding="utf-8")
    # Permissão: só o usuário atual e o Sistema leem o arquivo.
    subprocess.run(["icacls", str(ENV_FILE), "/inheritance:r", "/grant:r",
                    f"{os.environ.get('USERNAME', '')}:F", "SYSTEM:F"], capture_output=True)


def aplicar_env_nos_servicos():
    """Copia o .env único para o Hermes e reinicia o gateway dele (a tarefa de inicialização o sobe de novo em ~10 s)."""
    import sys
    subprocess.run([sys.executable, str(RAIZ / "scripts" / "sync_env.py")], capture_output=True, timeout=30)
    for p in psutil.process_iter(["pid", "cmdline"]):
        c = " ".join(p.info["cmdline"] or [])
        if "gateway" in c and ("hermes" in c.lower()):
            try:
                p.terminate()
            except Exception:
                pass


def mascarar(chave):
    return "" if not chave else (chave[:6] + "****…" + chave[-4:] if len(chave) > 12 else "****")


def testar_chave(chave):
    """Chamada mínima (lista de modelos). Devolve (estado, mensagem). Nunca inclui a chave."""
    # A lista de modelos é pública (responde 200 até sem chave), então o teste real é um chat mínimo (1 token).
    corpo = json.dumps({"model": "nvidia/nemotron-3-ultra-550b-a55b", "max_tokens": 1,
                        "messages": [{"role": "user", "content": "oi"}]}).encode()
    req = urllib.request.Request("https://integrate.api.nvidia.com/v1/chat/completions", data=corpo,
                                 headers={"Authorization": f"Bearer {chave}", "Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=60)
        return "ok", "A chave funciona."
    except urllib.error.HTTPError as e:
        if e.code in (401, 403):
            return "invalida", "A chave é inválida. Confira se copiou inteira."
        if e.code == 429:
            return "cota", "A cota da chave acabou. Tente mais tarde."
        return "erro", f"A NVIDIA respondeu com erro {e.code}."
    except Exception:
        return "erro", "Não consegui falar com a NVIDIA. Veja a internet do servidor."


# ---------- App ----------
app = FastAPI(title="Alicia Server", docs_url=None, redoc_url=None)


@app.middleware("http")
async def monitor(request: Request, call_next):
    t0 = time.time()
    p = request.url.path
    quem = usuario_da_sessao(request)
    if quem and p.startswith(BLOQUEADO_PARA_VISITANTE) and eh_convidado(quem):
        registrar("SEGURANÇA", quem, ip_de(request), f"visitante tentou acessar {p}", "negado", "seguranca")
        return JSONResponse({"detail": "Essa parte é só para os moradores da casa."}, status_code=403)
    resp = await call_next(request)
    if (p.startswith(("/api/logs", "/static", "/ejs", "/api/musica/audio", "/api/jogos/arquivo", "/api/jogos/capa", "/api/jogos/save", "/api/alicia/imagem", "/api/status"))
            or request.query_params.get("silencio")):
        return resp  # evita encher o log com o próprio monitor
    ms = int((time.time() - t0) * 1000)
    tipo = "ok" if resp.status_code < 400 else ("seguranca" if resp.status_code in (401, 403, 429) else "erro")
    registrar("PAINEL", usuario_da_sessao(request) or "-", ip_de(request),
              f"{request.method} {p}", f"{resp.status_code} {ms}ms", tipo)
    return resp


@app.post("/api/login")
async def login(request: Request):
    ip = ip_de(request)
    qtd, ate = falhas.get(ip, (0, 0))
    if ate > time.time():
        registrar("LOGIN", "-", ip, "tentativa durante bloqueio", "bloqueado", "seguranca")
        raise HTTPException(429, f"Muitas tentativas. Aguarde {int(ate - time.time())} segundos.")
    corpo = await request.json()
    nome, senha = str(corpo.get("usuario", "")).strip().lower(), str(corpo.get("senha", ""))
    u = usuarios().get(nome)
    try:
        if not u or u.get("convidado"):
            raise VerifyMismatchError()
        ph.verify(u["hash"], senha)
    except VerifyMismatchError:
        qtd += 1
        falhas[ip] = (qtd, time.time() + 300 if qtd >= 5 else 0)
        registrar("LOGIN", nome or "-", ip, "senha errada" + (" — IP bloqueado por 5 min" if qtd >= 5 else ""),
                  "falhou", "seguranca")
        raise HTTPException(401, "Usuário ou senha incorretos.")
    falhas.pop(ip, None)
    registrar("LOGIN", nome, ip, "entrou", "ok", "ok")
    r = JSONResponse({"usuario": nome, "admin": u.get("admin", False)})
    r.set_cookie("alicia_sessao", assinador.sign(nome).decode(), httponly=True, samesite="lax",
                 max_age=60 * 60 * 24 * 14)
    return r


@app.get("/api/publico")
async def publico():
    return {"visitante": visitante_ativo()}


@app.post("/api/visitante")
async def entrar_visitante(request: Request):
    if not visitante_ativo():
        raise HTTPException(403, "A entrada como visitante está desligada.")
    d = usuarios()
    if "visitante" not in d:
        d["visitante"] = {"hash": "", "admin": False, "convidado": True}
        USERS_FILE.write_text(json.dumps(d, indent=1), encoding="utf-8")
    registrar("LOGIN", "visitante", ip_de(request), "entrou como visitante", "ok", "aviso")
    r = JSONResponse({"usuario": "visitante", "admin": False, "convidado": True})
    r.set_cookie("alicia_sessao", assinador.sign("visitante").decode(), httponly=True, samesite="lax", max_age=60 * 60 * 24)
    return r


@app.post("/api/visitante/config")
async def visitante_config(request: Request):
    u = exigir_admin(request)
    c = config_painel()
    c["visitante"] = bool((await request.json()).get("ativo"))
    CONFIG_PAINEL.write_text(json.dumps(c), encoding="utf-8")
    registrar("SEGURANÇA", u, ip_de(request), "entrada de visitante " + ("LIGADA" if c["visitante"] else "DESLIGADA"), "ok", "aviso")
    return {"visitante": c["visitante"]}


@app.post("/api/logout")
async def logout(request: Request):
    registrar("LOGIN", usuario_da_sessao(request) or "-", ip_de(request), "saiu", "ok", "info")
    r = JSONResponse({"ok": True})
    r.delete_cookie("alicia_sessao")
    return r


def exigir_admin(request: Request):
    u = exigir_login(request)
    if not usuarios().get(u, {}).get("admin"):
        raise HTTPException(403, "Só o administrador pode fazer isso.")
    return u


@app.get("/api/eu")
async def eu(request: Request):
    u = exigir_login(request)
    return {"usuario": u, "admin": bool(usuarios().get(u, {}).get("admin")), "convidado": eh_convidado(u), "visitante_ativo": visitante_ativo()}


# ----- Usuários e senhas -----
def _gravar_usuarios(d):
    USERS_FILE.write_text(json.dumps(d, indent=1), encoding="utf-8")


@app.get("/api/usuarios")
async def usuarios_lista(request: Request):
    exigir_admin(request)
    return [{"usuario": n, "admin": bool(v.get("admin"))} for n, v in usuarios().items() if not v.get("convidado")]


@app.post("/api/usuarios")
async def usuarios_criar(request: Request):
    adm = exigir_admin(request)
    c = await request.json()
    nome = re.sub(r"[^a-z0-9_.-]", "", str(c.get("usuario", "")).strip().lower())[:30]
    senha = str(c.get("senha", ""))
    if len(nome) < 3:
        raise HTTPException(400, "O nome precisa ter pelo menos 3 letras ou números (sem espaços).")
    if len(senha) < 6:
        raise HTTPException(400, "A senha precisa ter pelo menos 6 caracteres.")
    d = usuarios()
    d[nome] = {"hash": ph.hash(senha), "admin": bool(c.get("admin"))}
    _gravar_usuarios(d)
    registrar("SEGURANÇA", adm, ip_de(request), f"criou/atualizou o usuário {nome}", "ok", "aviso")
    return {"ok": True}


@app.delete("/api/usuarios")
async def usuarios_apagar(request: Request, nome: str):
    adm = exigir_admin(request)
    d = usuarios()
    if nome == adm:
        raise HTTPException(400, "Você não pode apagar a si mesmo.")
    if nome not in d:
        raise HTTPException(404, "Usuário não encontrado.")
    del d[nome]
    _gravar_usuarios(d)
    registrar("SEGURANÇA", adm, ip_de(request), f"apagou o usuário {nome}", "ok", "aviso")
    return {"ok": True}


@app.post("/api/senha")
async def trocar_senha(request: Request):
    u = exigir_login(request)
    c = await request.json()
    d = usuarios()
    try:
        ph.verify(d[u]["hash"], str(c.get("atual", "")))
    except Exception:
        raise HTTPException(400, "A senha atual está errada.")
    if len(str(c.get("nova", ""))) < 6:
        raise HTTPException(400, "A senha nova precisa ter pelo menos 6 caracteres.")
    d[u]["hash"] = ph.hash(str(c["nova"]))
    _gravar_usuarios(d)
    registrar("SEGURANÇA", u, ip_de(request), "trocou a própria senha", "ok", "aviso")
    return {"ok": True}


@app.get("/api/status")
async def status(request: Request):
    exigir_login(request)
    disco = shutil.disk_usage(DADOS)
    temp = None
    try:
        t = psutil.sensors_temperatures()  # normalmente indisponível no Windows
        temp = next(iter(t.values()))[0].current if t else None
    except Exception:
        pass
    rede = psutil.net_io_counters()
    return {
        "cpu": psutil.cpu_percent(interval=None),
        "ram": psutil.virtual_memory().percent,
        "disco": round(disco.used / disco.total * 100, 1),
        "disco_livre_gb": round(disco.free / 1e9),
        "temperatura": temp,
        "ligado_ha_h": round((time.time() - psutil.boot_time()) / 3600, 1),
        "rede_enviado": rede.bytes_sent, "rede_recebido": rede.bytes_recv,
        "chave_nvidia": bool(ler_env().get("NVIDIA_API_KEY")),
        "servicos": servicos(), "jogando_agora": jogando_agora(), "enderecos": enderecos(),
    }


def enderecos():
    """IPs úteis para acessar o servidor (rede de casa e rede privada Tailscale)."""
    out = {}
    try:
        for nome, ends in psutil.net_if_addrs().items():
            for a in ends:
                if a.family == 2 and not a.address.startswith(("127.", "169.254.")):
                    out["tailscale" if "tailscale" in nome.lower() else "casa"] = a.address
    except Exception:
        pass
    return {k: f"http://{v}:8080" for k, v in out.items()}


def porta_aberta(porta):
    import socket
    with socket.socket() as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", porta)) == 0


def servico_win(nome):
    try:
        return psutil.win_service_get(nome).status() == "running"
    except Exception:
        return False


def servicos():
    est = lambda ok: "ligado" if ok else "parado"
    return [{"nome": "Painel", "estado": "ligado"},
            {"nome": "Alicia/Hermes", "estado": est(porta_aberta(8642))},
            {"nome": "Jellyfin", "estado": est(porta_aberta(8096))},
            {"nome": "Rede privada (Tailscale)", "estado": est(servico_win("Tailscale"))},
            {"nome": "Administração remota (SSH)", "estado": est(servico_win("sshd"))},
            {"nome": "Jogos (no navegador)", "estado": est(EJS_DIR.exists())},{"nome": "Música", "estado": "ligado"},
            {"nome": "RPG", "estado": "ligado"}]


# ---------- Vigia: alertas do sistema e acessos do Jellyfin no monitor ----------
_jf_vistos = {}
_alerta_ate = {}


def _alerta(chave, texto):
    if _alerta_ate.get(chave, 0) < time.time():
        _alerta_ate[chave] = time.time() + 600  # no máximo 1 aviso a cada 10 min por tipo
        registrar("SISTEMA", "-", "-", texto, "alerta", "aviso")


_sun_pos = {"p": None}


def _vigiar_sunshine():
    """Lê só o final novo do log do Sunshine e avisa o monitor quando alguém conecta/desconecta ou abre o jogo."""
    f = Path(r"C:\Program Files\Sunshine\config\sunshine.log")
    try:
        tam = f.stat().st_size
        if _sun_pos["p"] is None or tam < _sun_pos["p"]:
            _sun_pos["p"] = tam
            return
        with open(f, encoding="utf-8", errors="ignore") as fh:
            fh.seek(_sun_pos["p"])
            novo = fh.read()
            _sun_pos["p"] = fh.tell()
    except OSError:
        return
    for l in novo.splitlines():
        if "CLIENT CONNECTED" in l:
            registrar("JOGOS", "-", "-", "aparelho conectou ao streaming", "ok", "ok")
        elif "CLIENT DISCONNECTED" in l:
            registrar("JOGOS", "-", "-", "aparelho desconectou do streaming", "ok", "info")


def jogando_agora():
    return any(p.info["name"] and p.info["name"].lower() == "retroarch.exe" for p in psutil.process_iter(["name"]))


def _vigiar_uma_vez():
    if psutil.cpu_percent(interval=None) > 90:
        _alerta("cpu", "CPU acima de 90%")
    if psutil.virtual_memory().percent > 90:
        _alerta("ram", "memória acima de 90%")
    if shutil.disk_usage(DADOS).used / shutil.disk_usage(DADOS).total > 0.9:
        _alerta("disco", "disco quase cheio")
    _vigiar_sunshine()
    if _alerta_ate.get("smart_check", 0) < time.time():          # saúde do HD: confere de hora em hora
        _alerta_ate["smart_check"] = time.time() + 3600
        s = saude_disco()
        if s and s != "Healthy":
            registrar("SISTEMA", "-", "-", f"ALERTA: o HD informou saúde '{s}'. Faça backup e troque o disco.", "alerta", "seguranca")
    chave = ler_env().get("JELLYFIN_API_KEY")
    if chave:
        try:
            req = urllib.request.Request("http://127.0.0.1:8096/Sessions", headers={"Authorization": f'MediaBrowser Token="{chave}"'})
            sess = json.loads(urllib.request.urlopen(req, timeout=5).read())
        except Exception:
            return
        agora = set()
        for s in sess:
            item = s.get("NowPlayingItem")
            if not item:
                continue
            id_ = s.get("Id")
            agora.add(id_)
            if _jf_vistos.get(id_) != item.get("Id"):
                _jf_vistos[id_] = item.get("Id")
                conv = (s.get("PlayState") or {}).get("PlayMethod", "?")
                registrar("JELLYFIN", s.get("UserName") or "-", s.get("RemoteEndPoint") or "-",
                          f"começou a assistir '{item.get('Name', '?')}' em {s.get('DeviceName', '?')} ({conv})",
                          "ok", "aviso" if conv == "Transcode" else "ok")
        for k in [k for k in _jf_vistos if k not in agora]:
            _jf_vistos.pop(k)


async def _vigia():
    psutil.cpu_percent(interval=None)
    while True:
        try:
            await asyncio.to_thread(_vigiar_uma_vez)
        except Exception:
            pass
        await asyncio.sleep(20)


@app.on_event("startup")
async def _iniciar_vigia():
    asyncio.create_task(_vigia())


# ----- Arquivos (sempre dentro de DADOS; bloqueia saída da pasta) -----
def caminho_seguro(rel: str) -> Path:
    p = (DADOS / rel.lstrip("/\\")).resolve()
    if DADOS.resolve() not in [p, *p.parents]:
        raise HTTPException(400, "Caminho inválido.")
    return p


@app.get("/api/arquivos")
async def listar(request: Request, caminho: str = ""):
    u = exigir_login(request)
    p = caminho_seguro(caminho)
    if not p.is_dir():
        raise HTTPException(404, "Essa pasta não existe.")
    itens = [{"nome": f.name, "pasta": f.is_dir(), "tamanho": f.stat().st_size if f.is_file() else 0}
             for f in sorted(p.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower()))]
    return {"caminho": caminho, "itens": itens}


@app.post("/api/arquivos/enviar")
async def enviar(request: Request, caminho: str = "", arquivo: UploadFile = File(...)):
    u = exigir_login(request)
    destino = caminho_seguro(caminho) / Path(arquivo.filename).name
    with open(destino, "wb") as f:
        shutil.copyfileobj(arquivo.file, f)
    registrar("ARQUIVOS", u, ip_de(request), f"enviou {destino.name}", "ok", "ok")
    return {"ok": True}


@app.get("/api/arquivos/baixar")
async def baixar(request: Request, caminho: str, baixar: int = 0, silencio: int = 0):
    u = exigir_login(request)
    p = caminho_seguro(caminho)
    if not p.is_file():
        raise HTTPException(404, "Arquivo não encontrado.")
    if not silencio:
        registrar("ARQUIVOS", u, ip_de(request), f"{'baixou' if baixar else 'abriu'} {p.name}", "ok", "info")
    return FileResponse(p, filename=p.name if baixar else None)


@app.post("/api/arquivos/pasta")
async def nova_pasta(request: Request):
    u = exigir_login(request)
    c = await request.json()
    nome = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", str(c.get("nome", ""))).strip(" .")[:80]
    if not nome:
        raise HTTPException(400, "Escreva um nome para a pasta.")
    (caminho_seguro(str(c.get("caminho", ""))) / nome).mkdir(exist_ok=True)
    registrar("ARQUIVOS", u, ip_de(request), f"criou a pasta {nome}", "ok", "info")
    return {"ok": True}


@app.delete("/api/arquivos")
async def apagar(request: Request, caminho: str):
    u = exigir_login(request)
    p = caminho_seguro(caminho)
    if p in [caminho_seguro(x) for x in PASTAS] or not p.exists():
        raise HTTPException(400, "Essa pasta não pode ser apagada.")
    # Lixeira em vez de apagar de vez: mais seguro.
    lixo = DADOS / ".lixeira"
    lixo.mkdir(exist_ok=True)
    shutil.move(str(p), str(lixo / f"{int(time.time())}_{p.name}"))
    registrar("ARQUIVOS", u, ip_de(request), f"apagou {p.name} (foi para a lixeira)", "ok", "aviso")
    return {"ok": True}


# ----- Chave NVIDIA -----
@app.get("/api/nvidia")
async def nvidia_estado(request: Request):
    exigir_login(request)
    return {"mascarada": mascarar(ler_env().get("NVIDIA_API_KEY", ""))}


@app.post("/api/nvidia/testar")
async def nvidia_testar(request: Request):
    u = exigir_login(request)
    chave = (await request.json()).get("chave") or ler_env().get("NVIDIA_API_KEY", "")
    if not chave:
        return {"estado": "vazia", "mensagem": "Cole a chave primeiro."}
    estado, msg = await asyncio.to_thread(testar_chave, chave.strip())
    registrar("NVIDIA", u, ip_de(request), "testou a chave", estado, "ok" if estado == "ok" else "erro")
    return {"estado": estado, "mensagem": msg}


@app.post("/api/nvidia/salvar")
async def nvidia_salvar(request: Request):
    u = exigir_login(request)
    chave = ((await request.json()).get("chave") or "").strip()
    if not chave.startswith("nvapi-"):
        raise HTTPException(400, "Essa chave não parece certa: ela começa com nvapi-.")
    gravar_env(chave)
    await asyncio.to_thread(aplicar_env_nos_servicos)
    registrar("NVIDIA", u, ip_de(request), "salvou nova chave e reiniciou o Hermes", "ok", "aviso")
    return {"mascarada": mascarar(chave)}


# ----- Jogos no navegador (EmulatorJS): o jogo roda no aparelho de quem joga; o servidor só entrega o jogo e guarda o save -----
JOGOS_DIR = DADOS / "Jogos"
EJS_DIR = Path(os.environ.get("ALICIA_EJS", r"C:\AliciaServer\emulatorjs\data"))
CONSOLES = {  # pasta -> (núcleo do EmulatorJS, nome bonito, cor, extensões aceitas)
    "Nintendo": ("nes", "Nintendo", "#e11d48", {".nes", ".zip", ".7z"}),
    "Super Nintendo": ("snes", "Super Nintendo", "#7c3aed", {".sfc", ".smc", ".zip", ".7z"}),
    "Nintendo 64": ("n64", "Nintendo 64", "#16a34a", {".z64", ".n64", ".v64", ".zip", ".7z"}),
    "Game Boy Advance": ("gba", "Game Boy Advance", "#2563eb", {".gba", ".zip", ".7z"}),
    "Game Boy": ("gb", "Game Boy e Game Boy Color", "#ca8a04", {".gb", ".gbc", ".zip", ".7z"}),
    "PlayStation": ("psx", "PlayStation", "#475569", {".cue", ".chd", ".iso", ".pbp", ".zip", ".7z"}),
}
for _c in CONSOLES:
    (JOGOS_DIR / _c).mkdir(parents=True, exist_ok=True)
(JOGOS_DIR / "BIOS").mkdir(exist_ok=True)
(JOGOS_DIR / "Saves").mkdir(exist_ok=True)
if EJS_DIR.exists():
    app.mount("/ejs", StaticFiles(directory=EJS_DIR), name="ejs")


def _nome_bonito(arq: Path):
    n = re.sub(r"[\[\(].*?[\]\)]", "", arq.stem).replace("_", " ").strip()
    return n or arq.stem


EXT_CONSOLE = {".nes": "Nintendo", ".fds": "Nintendo", ".unf": "Nintendo", ".sfc": "Super Nintendo", ".smc": "Super Nintendo", ".fig": "Super Nintendo", ".swc": "Super Nintendo",
               ".z64": "Nintendo 64", ".n64": "Nintendo 64", ".v64": "Nintendo 64", ".gba": "Game Boy Advance", ".gb": "Game Boy", ".gbc": "Game Boy",
               ".cue": "PlayStation", ".chd": "PlayStation", ".pbp": "PlayStation", ".iso": "PlayStation"}
_det_cache = {}


def _console_do_jogo(f: Path, pasta: str) -> str:
    """Descobre o console pelo próprio arquivo (extensão ou o que há dentro do .zip), não pela pasta em que ele foi colocado."""
    c = EXT_CONSOLE.get(f.suffix.lower())
    if c:
        return c
    if f.suffix.lower() == ".zip":
        chave = (str(f), f.stat().st_mtime)
        if chave not in _det_cache:
            achado = pasta
            try:
                import zipfile
                with zipfile.ZipFile(f) as z:
                    for n in z.namelist():
                        c2 = EXT_CONSOLE.get(Path(n).suffix.lower())
                        if c2:
                            achado = c2
                            break
            except Exception:
                pass
            _det_cache[chave] = achado
        return _det_cache[chave]
    return pasta


def _organizar_jogos():
    """Põe cada jogo na pasta do console certo (ex.: um jogo de SNES colocado em NES vai para SNES)."""
    for pasta, (_, _, _, exts) in CONSOLES.items():
        for f in list((JOGOS_DIR / pasta).iterdir()):
            if f.is_file() and f.suffix.lower() in exts:
                c = _console_do_jogo(f, pasta)
                if c != pasta and c in CONSOLES:
                    dest = JOGOS_DIR / c / f.name
                    if dest.exists():
                        dest = JOGOS_DIR / c / f"{f.stem} (1){f.suffix}"
                    shutil.move(str(f), str(dest))
                    for ext in (".png", ".jpg", ".jpeg"):      # a capa acompanha o jogo
                        cp = f.parent / f"{f.stem}{ext}"
                        if cp.exists():
                            shutil.move(str(cp), str(dest.with_suffix(ext)))
                    registrar("JOGOS", "-", "-", f"'{f.name}' era de {c} e foi movido de {pasta} para {c}", "ok", "info")


@app.get("/api/jogos")
async def jogos_lista(request: Request):
    exigir_login(request)
    await asyncio.to_thread(_organizar_jogos)
    out = []
    for pasta, (nucleo, nome, cor, exts) in CONSOLES.items():
        itens = []
        for f in sorted((JOGOS_DIR / pasta).iterdir(), key=lambda x: x.name.lower()):
            if f.is_file() and f.suffix.lower() in exts:
                capa = next((f"{f.stem}{e}" for e in (".png", ".jpg", ".jpeg") if (f.parent / f"{f.stem}{e}").exists()), None)
                itens.append({"arquivo": f.name, "nome": _nome_bonito(f), "capa": capa})
        out.append({"pasta": pasta, "nome": nome, "cor": cor, "jogos": itens})
    return out

def _arquivo_jogo(pasta: str, arquivo: str) -> Path:
    if pasta not in CONSOLES:
        raise HTTPException(404, "Console desconhecido.")
    p = (JOGOS_DIR / pasta / arquivo).resolve()
    if (JOGOS_DIR / pasta).resolve() not in p.parents or not p.is_file():
        raise HTTPException(404, "Jogo não encontrado.")
    return p


@app.get("/api/jogos/arquivo")
async def jogos_arquivo(request: Request, pasta: str, arquivo: str):
    exigir_login(request)
    return FileResponse(_arquivo_jogo(pasta, arquivo))


@app.get("/api/jogos/bios")
async def jogos_bios(request: Request, pasta: str):
    """BIOS do console (se você colocou em Jogos/BIOS). Procura pelo nome do console ou arquivos comuns do PS1."""
    exigir_login(request)
    if pasta == "PlayStation":
        for n in ("scph5501.bin", "scph1001.bin", "scph5500.bin", "scph5502.bin", "SCPH5501.BIN", "SCPH1001.BIN"):
            if (JOGOS_DIR / "BIOS" / n).exists():
                return FileResponse(JOGOS_DIR / "BIOS" / n)
    raise HTTPException(404, "Sem BIOS.")


def _arq_save(u: str, pasta: str, arquivo: str) -> Path:
    _arquivo_jogo(pasta, arquivo)
    d = JOGOS_DIR / "Saves" / u / pasta
    d.mkdir(parents=True, exist_ok=True)
    return d / (Path(arquivo).stem + ".state")


@app.get("/api/jogos/save")
async def jogos_save_ler(request: Request, pasta: str, arquivo: str):
    u = exigir_login(request)
    f = _arq_save(u, pasta, arquivo)
    if not f.exists():
        raise HTTPException(404, "Sem save.")
    return FileResponse(f)


@app.post("/api/jogos/save")
async def jogos_save_gravar(request: Request, pasta: str, arquivo: str):
    u = exigir_login(request)
    dados = await request.body()
    if not 1000 < len(dados) < 60_000_000:
        raise HTTPException(400, "Save inválido.")
    f = _arq_save(u, pasta, arquivo)
    tmp = f.with_suffix(".tmp")
    tmp.write_bytes(dados)
    tmp.replace(f)  # troca atômica: nunca fica um save pela metade
    return {"ok": True}


@app.post("/api/jogos/inicio")
async def jogos_inicio(request: Request):
    u = exigir_login(request)
    c = await request.json()
    registrar("JOGOS", u, ip_de(request), f"abriu '{str(c.get('arquivo', ''))[:60]}' ({str(c.get('pasta', ''))[:6]}) no navegador", "ok", "ok")
    return {"ok": True}


@app.get("/api/jogos/capa")
async def jogos_capa(request: Request, pasta: str, arquivo: str):
    exigir_login(request)
    return FileResponse(_arquivo_jogo(pasta, arquivo))


@app.get("/jogar")
async def jogar_pagina(request: Request):
    if not usuario_da_sessao(request):
        return FileResponse(WEB / "index.html")  # sem login: volta para a tela de entrada
    return FileResponse(WEB / "jogar.html")


@app.get("/api/jogos/info")
async def jogos_info(request: Request, pasta: str):
    exigir_login(request)
    if pasta not in CONSOLES:
        raise HTTPException(404, "Console desconhecido.")
    return {"nucleo": CONSOLES[pasta][0], "emulador_instalado": EJS_DIR.exists()}


# ----- Hermes (administração) -----
@app.post("/api/hermes/reiniciar")
async def hermes_reiniciar(request: Request):
    u = exigir_admin(request)
    await asyncio.to_thread(aplicar_env_nos_servicos)
    registrar("SISTEMA", u, ip_de(request), "reiniciou o Hermes", "ok", "aviso")
    return {"ok": True}


@app.get("/api/hermes/info")
async def hermes_info(request: Request):
    exigir_login(request)
    env = ler_env()
    base = f"http://127.0.0.1:{env.get('API_SERVER_PORT', '8642')}"
    cab = {"Authorization": f"Bearer {env.get('API_SERVER_KEY', '')}"}

    def pega(caminho):
        try:
            with urllib.request.urlopen(urllib.request.Request(base + caminho, headers=cab), timeout=8) as r:
                return json.loads(r.read())
        except Exception:
            return None
    skills, jobs = await asyncio.gather(asyncio.to_thread(pega, "/v1/skills"), asyncio.to_thread(pega, "/api/jobs"))
    nomes = lambda d, *chaves: [str(x.get("name") or x.get("id") or x) if isinstance(x, dict) else str(x)
                                for x in (next((d[k] for k in chaves if isinstance(d, dict) and k in d), d) if d else [])][:50]
    return {"skills": nomes(skills, "skills", "data"), "tarefas": nomes(jobs, "jobs", "data")}


# ----- Verificar tudo -----
def saude_disco():
    """Saúde do HD (SMART resumido pelo Windows). Devolve 'Healthy', 'Warning', 'Unhealthy' ou None."""
    try:
        r = subprocess.run(["powershell", "-NoProfile", "-Command", "(Get-PhysicalDisk | Select -First 1).HealthStatus"],
                           capture_output=True, text=True, timeout=20)
        return r.stdout.strip() or None
    except Exception:
        return None


def _verificar(env, usuario):
    res = []
    add = lambda nome, ok, dica="": res.append({"nome": nome, "ok": ok, "dica": "" if ok else dica})
    add("Painel", True)
    add("Disco (saúde do HD)", saude_disco() == "Healthy", "O disco avisou problema. Faça backup agora e troque o HD.")
    add("Jellyfin (filmes)", porta_aberta(8096), "Reinicie o serviço JellyfinServer (veja PROBLEMAS.md).")
    add("Jogos (emulador no navegador)", EJS_DIR.exists(), "Falta a pasta do emulador (C:\\AliciaServer\\emulatorjs). Veja JOGOS.md.")
    add("Rede privada (Tailscale)", servico_win("Tailscale"), "Instale/ligue o Tailscale e faça o login.")
    add("Hermes (cérebro)", porta_aberta(8642), "O Hermes não está ligado; reinicie o notebook ou a tarefa AliciaServer-Hermes.")
    chave = env.get("NVIDIA_API_KEY", "")
    if not chave:
        add("Chave da NVIDIA", False, "Coloque a chave em Configurações.")
    else:
        est, msg = testar_chave(chave)
        add("Chave da NVIDIA", est == "ok", msg)
        if est == "ok":
            sistema = alicia_ponte.montar_sistema(usuario.capitalize(), "normal", False, "Oi")
            ok, resp = alicia_ponte.perguntar_hermes(env, "", sistema, "Diga oi em uma frase.")
            add("Alicia responde pelo Hermes", ok and len(resp) > 0, resp if not ok else "Sem resposta.")
            ok2, resp2 = alicia_ponte.perguntar_hermes(env, "", alicia_ponte.montar_sistema(usuario.capitalize(), "normal", True, "Oi"),
                                                       "Diga oi em uma frase.")
            add("Personalidade e modo sem filtro funcionam", ok2 and len(resp2) > 0, resp2 if not ok2 else "Sem resposta.")
            ok3, resp3 = alicia_ponte.perguntar_hermes(env, "", rpg.MESTRA, "Narre em uma frase a entrada numa taverna.")
            add("RPG: mestra narra", ok3 and len(resp3) > 0, resp3 if not ok3 else "Sem resposta.")
    add("RPG: dados do servidor", 1 <= rpg.rolar("d20")["total"] <= 20)
    return res


@app.post("/api/verificar")
async def verificar(request: Request):
    u = exigir_login(request)
    res = await asyncio.to_thread(_verificar, ler_env(), u)
    registrar("SISTEMA", u, ip_de(request), "rodou Verificar tudo", f"{sum(r['ok'] for r in res)}/{len(res)} ok", "info")
    return res


# ----- Alicia (conversa pelo Hermes) -----
@app.get("/api/alicia/opcoes")
async def alicia_opcoes(request: Request):
    exigir_login(request)
    return {"personalidades": alicia_ponte.personalidades()}


@app.post("/api/alicia/conversar")
async def alicia_conversar(request: Request):
    u = exigir_login(request)
    corpo = await request.json()
    texto = str(corpo.get("texto", "")).strip()[:2000]
    if not texto:
        raise HTTPException(400, "Escreva alguma coisa para a Alicia.")
    env = ler_env()
    if not env.get("NVIDIA_API_KEY") and env.get("ALICIA_MODO_TESTE") != "1":
        # Sem chave: aviso amigável, nada quebra.
        return {"sem_chave": True, "texto": "A Alicia ainda não tem cérebro. Coloque a chave da NVIDIA em Configurações.",
                "expressao": "pensando"}
    sistema = alicia_ponte.montar_sistema(u.capitalize(), str(corpo.get("personalidade", "normal")),
                                          bool(corpo.get("sem_filtro")), texto)
    t0 = time.time()
    ok, resp = await asyncio.to_thread(alicia_ponte.perguntar_hermes, env, f"painel-{u}", sistema, texto)
    # Registro: só metadados, nunca o conteúdo da conversa.
    registrar("ALICIA", u, ip_de(request), "conversa com o Hermes", f"{'ok' if ok else 'erro'} {int((time.time()-t0)*1000)}ms",
              "ok" if ok else "erro")
    if not ok:
        return {"erro": True, "texto": resp, "expressao": "serio"}
    expressao, limpo = alicia_ponte.separar_expressao(resp)
    return {"texto": limpo, "expressao": expressao}


# ----- Alicia toca música: "toca Linkin Park", "coloca algo animado"... -----
import unicodedata as _ud


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", "".join(c for c in _ud.normalize("NFD", (s or "").lower()) if _ud.category(c) != "Mn")).strip()


_VERBOS = r"(?:toca|toque|tocar|coloca|coloque|colocar|poe|bota|bote|quero ouvir|quero escutar|vou querer ouvir|ouvir|escutar|reproduz|reproduza|manda|mande)"
_PARADAS = {"pra", "para", "mim", "por", "favor", "ai", "agora", "uma", "um", "a", "o", "as", "os", "musica", "musicas", "som", "faixa", "cancao",
            "aquela", "essa", "esse", "de", "da", "do", "das", "dos", "eu", "ouvir", "tocar", "escutar", "me", "pro", "pra"}
_GENERICO = {"", "algo", "alguma", "alguma coisa", "qualquer", "qualquer coisa", "qualquer uma", "algo bom", "algo animado", "alguma musica"}


def extrair_consulta(texto: str):
    """Se a mensagem é um pedido de música, devolve o que foi pedido ('' = qualquer coisa). Senão, None."""
    n = re.sub(r"^(?:oi |ei |ola )?alicia[, ]*", "", _norm(texto)).strip(" ,.!?")
    m = re.match(rf"^(?:por favor[, ]*|pode |poderia |voce pode |me )*{_VERBOS}\b(.*)$", n)
    if not m:
        return None
    pal = m.group(1).strip(" ,.!?").split()
    while pal and pal[0] in _PARADAS:        # tira "uma música do/da..." do começo, sem mexer no nome do artista
        pal.pop(0)
    while pal and pal[-1] in _PARADAS | {"favor"}:
        pal.pop()
    return " ".join(pal)


_RUINS = re.compile(r"\b(horas?|hours?|full album|album completo|mix|playlist|compilation|coletanea|as melhores|best of|greatest hits)\b", re.I)


def achar_musica(consulta: str):
    """(faixas, origem). Primeiro a biblioteca do servidor; se não houver, o YouTube."""
    idx = _indice()
    todas = [(v, i) for v, i in idx.items() if (DADOS / i["arquivo"]).exists()]
    mk = lambda v, i: {"id": v, "titulo": i["titulo"], "canal": i["artista"], "capa": i["capa"], "genero": i["genero"], "duracao": i.get("duracao", 0)}
    if consulta in _GENERICO:
        if todas:
            random.shuffle(todas)
            return [mk(v, i) for v, i in todas[:20]], "biblioteca"
        consulta = "musicas populares brasil"
    tokens = [t for t in _norm(consulta).split() if t not in _PARADAS]
    if tokens and todas:
        pontos = []
        for v, i in todas:
            alvo = _norm(f"{i['titulo']} {i['artista']} {i['genero']}")
            if all(t in alvo for t in tokens):
                pontos.append((2 if all(t in _norm(i["artista"]) for t in tokens) else 1, v, i))
        if pontos:
            artista = [x for x in pontos if x[0] == 2]
            if artista:                                       # pediu um artista: toca as músicas dele, embaralhadas
                lista = [mk(v, i) for _, v, i in artista]
                random.shuffle(lista)
                return lista[:25], "biblioteca"
            return [mk(v, i) for _, v, i in pontos[:5]], "biblioteca"
    achados = _buscar_youtube(consulta)
    bons = [t for t in achados if not _RUINS.search(t["titulo"]) or _RUINS.search(consulta)]
    return (bons or achados)[:1], "youtube"


@app.post("/api/alicia/musica")
async def alicia_musica(request: Request):
    u = exigir_login(request)
    c = await request.json()
    texto = str(c.get("texto", "")).strip()[:300]
    env = ler_env()
    if c.get("so_resposta"):                 # 2ª etapa: a música já está tocando; aqui a Alicia só comenta no jeito dela
        t = c.get("faixa") or {}
        faixas, origem = [t], "comentario"
    else:
        consulta = extrair_consulta(texto)
        if consulta is None:
            return {"nao_e_musica": True}
        try:
            faixas, origem = await asyncio.to_thread(achar_musica, consulta)
        except Exception:
            faixas, origem = [], "erro"
        registrar("MÚSICA", u, ip_de(request), "a Alicia foi pedida para tocar música", "ok" if faixas else "nada", "info")
        if not faixas:
            return {"texto": "Não achei essa música. Quer tentar outro nome?", "expressao": "pensando", "faixas": []}
        t = faixas[0]
    padrao = f"Tocando {t['titulo']}" + (f", de {t['canal']}." if t.get("canal") and t["canal"].lower() not in t["titulo"].lower() else ".")
    resposta, expressao = padrao, "feliz"
    if c.get("so_achar"):                    # 1ª etapa: devolve já a música (rápido) para o painel começar a tocar
        return {"texto": padrao, "expressao": expressao, "faixas": faixas, "origem": origem}
    if env.get("NVIDIA_API_KEY"):
        sistema = alicia_ponte.montar_sistema(u.capitalize(), str(c.get("personalidade", "normal")), bool(c.get("sem_filtro")), texto) + (
            f"\n\n[AÇÃO JÁ FEITA PELO SERVIDOR] A música já está tocando: \"{t['titulo']}\" ({t.get('canal', '')}). "
            "Responda em UMA frase curta, no seu jeito, avisando que colocou para tocar. Não invente nada além disso.")
        ok, resp = await asyncio.to_thread(alicia_ponte.perguntar_hermes, env, f"painel-{u}", sistema, texto, 60)
        if ok and resp.strip():
            expressao, resposta = alicia_ponte.separar_expressao(resp)
    return {"texto": resposta, "expressao": expressao, "faixas": faixas, "origem": origem}


@app.post("/api/alicia/voz")
async def alicia_voz(request: Request):
    exigir_login(request)
    c = await request.json()
    texto = alicia_ponte.preparar_fala(str(c.get("texto", "")))[:700]
    if not texto:
        raise HTTPException(400, "Nada para falar.")
    try:
        dados = await alicia_ponte.gerar_voz(texto, str(c.get("expressao", "feliz")))
    except Exception:
        raise HTTPException(502, "Não consegui gerar a voz agora (precisa de internet).")
    return Response(dados, media_type="audio/mpeg")


@app.get("/api/alicia/imagem/{nome}")
async def alicia_imagem(nome: str):
    arq = RAIZ / "alicia" / "assets" / f"{nome}.png"
    if nome not in {"feliz", "serio", "surpresa", "pensando", "bravo"} or not arq.exists():
        raise HTTPException(404, "Imagem não encontrada.")
    return FileResponse(arq)


# ----- Música (estilo Spotify): toca NO APARELHO de quem usa, pelo player oficial do YouTube. O servidor só busca e guarda playlists. -----
_cache_busca = {}


def _buscar_youtube(q: str):
    """Só METADADOS (título, canal, capa). Nada é baixado; o som vem do player oficial do YouTube no seu aparelho."""
    import yt_dlp
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True, "skip_download": True, "noplaylist": True}) as y:
        r = y.extract_info(f"ytsearch20:{q}", download=False)
    out = []
    for e in r.get("entries", []):
        if e and e.get("id") and len(e["id"]) == 11:
            out.append({"id": e["id"], "titulo": e.get("title", "")[:140], "canal": (e.get("channel") or e.get("uploader") or "")[:80],
                        "capa": f"https://i.ytimg.com/vi/{e['id']}/mqdefault.jpg"})
    return _so_incorporaveis(out)


def _so_incorporaveis(itens):
    """Tira os vídeos que o dono não deixa tocar fora do YouTube (o oEmbed responde 401/403 para eles)."""
    from concurrent.futures import ThreadPoolExecutor

    def ok(t):
        try:
            urllib.request.urlopen(f"https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v={t['id']}&format=json", timeout=6)
            return True
        except urllib.error.HTTPError as e:
            return e.code not in (401, 403, 404)
        except Exception:
            return True   # sem resposta: deixa passar (o player pula sozinho se não tocar)
    with ThreadPoolExecutor(8) as ex:
        res = list(ex.map(ok, itens))
    return [t for t, v in zip(itens, res) if v]


@app.get("/api/musica/buscar")
async def musica_buscar(request: Request, q: str):
    u = exigir_login(request)
    q = q.strip()[:100]
    if len(q) < 2:
        raise HTTPException(400, "Digite pelo menos 2 letras.")
    m = re.search(r"(?:v=|youtu\.be/|embed/|shorts/)([\w-]{11})", q)
    if m:  # colou um link: toca direto
        return [{"id": m.group(1), "titulo": "Link do YouTube", "canal": "", "capa": f"https://i.ytimg.com/vi/{m.group(1)}/mqdefault.jpg"}]
    if q.lower() not in _cache_busca:
        try:
            _cache_busca[q.lower()] = await asyncio.to_thread(_buscar_youtube, q)
        except Exception:
            raise HTTPException(502, "Não consegui buscar agora. Tente de novo ou cole o link do vídeo.")
        if len(_cache_busca) > 100:
            _cache_busca.pop(next(iter(_cache_busca)))
    registrar("MÚSICA", u, ip_de(request), "buscou músicas", "ok", "info")   # só registra que buscou, não o texto
    return _cache_busca[q.lower()]


def _arq_musica(u):
    return RAIZ / "dados" / f"musica_{u}.json"


@app.get("/api/musica/biblioteca")
async def musica_biblioteca(request: Request):
    u = exigir_login(request)
    f = _arq_musica(u)
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"curtidas": [], "playlists": {}}


@app.post("/api/musica/biblioteca")
async def musica_salvar(request: Request):
    u = exigir_login(request)
    d = await request.json()
    lim = lambda l: [{k: str(t.get(k, ""))[:140] for k in ("id", "titulo", "canal", "capa")} for t in l[:500]]
    limpo = {"curtidas": lim(d.get("curtidas", [])),
             "playlists": {str(n)[:40]: lim(v) for n, v in list((d.get("playlists") or {}).items())[:30]}}
    _arq_musica(u).write_text(json.dumps(limpo, ensure_ascii=False), encoding="utf-8")
    return {"ok": True}


@app.post("/api/musica/tocando")
async def musica_tocando(request: Request):
    u = exigir_login(request)
    registrar("MÚSICA", u, ip_de(request), f"tocando: {str((await request.json()).get('titulo', ''))[:80]}", "ok", "info")
    return {"ok": True}

# ----- Música: biblioteca NO SERVIDOR. Tudo que toca é guardado em Música/<Gênero>/<Artista>/, e o aparelho toca daí (decisão do usuário; ver DECISOES.md) -----
NODE_EXE = next(iter(Path(r"C:\AliciaServer\hermes\tools").glob("node-*/node.exe")), None)
MUSICA_DIR = DADOS / "Música"
INDICE_MUSICA = RAIZ / "dados" / "musica_indice.json"
_trava_musica = __import__("threading").Lock()
_baixando = {}


def _limpa(nome: str, padrao: str) -> str:
    n = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", nome or "").strip(" .")
    return (n or padrao)[:80]


def _indice():
    return json.loads(INDICE_MUSICA.read_text(encoding="utf-8")) if INDICE_MUSICA.exists() else {}


def _salvar_indice(i):
    tmp = INDICE_MUSICA.with_suffix(".tmp")
    tmp.write_text(json.dumps(i, ensure_ascii=False), encoding="utf-8")
    tmp.replace(INDICE_MUSICA)


def _artista(info: dict) -> str:
    limpa = lambda s: re.sub(r"\s*-\s*Topic$|VEVO$|\s*Official$", "", (s or "").split(",")[0].strip(), flags=re.I)
    a = limpa(info.get("artist") or info.get("creator"))
    canal = limpa(info.get("channel") or info.get("uploader"))
    t = info.get("title") or ""
    if not a:
        if canal and canal.lower() in t.lower():
            a = canal                                    # o canal é o próprio artista (caso mais comum)
        elif re.search(r"\s[-–]\s", t):
            a = re.split(r"\s[-–]\s", t)[0]               # "Artista - Música"
        else:
            a = canal
    return _limpa(a, "Artista desconhecido")


def _titulo(info: dict, artista: str, vid: str) -> str:
    t = info.get("track") or info.get("title") or vid
    t = re.sub(r"\s*[\[\(].*?(official|video|lyric|audio|4k|hd|upgrade).*?[\]\)]", "", t, flags=re.I)
    t = re.sub(r"\s[-–]\s*" + re.escape(artista) + r"\s*$", "", t, flags=re.I)        # tira "- Artista" do fim
    t = re.sub(r"^" + re.escape(artista) + r"\s[-–]\s*", "", t, flags=re.I)           # tira "Artista -" do começo
    return _limpa(t, vid)

_generos_cache = {}


def _genero(artista: str, titulo: str) -> str:
    """Pede o gênero à Alicia/Hermes (uma palavra). Sem chave ou com erro: 'Sem gênero'. Guarda por artista para economizar."""
    if artista in _generos_cache:
        return _generos_cache[artista]
    env = ler_env()
    g = "Sem gênero"
    if env.get("NVIDIA_API_KEY"):
        ok, resp = alicia_ponte.perguntar_hermes(
            env, "", "Você classifica músicas. Responda SOMENTE com UMA palavra em português do Brasil que seja o gênero musical "
            "(ex.: Rock, Pop, Rap, Eletrônica, Sertanejo, Funk, MPB, Jazz, Clássica, Metal, Reggae, Trilha sonora). Sem pontuação, sem explicação.",
            f"Artista: {artista}. Música: {titulo}.", timeout=45)
        if ok:
            palavra = re.sub(r"[^\wÀ-ÿ ]", "", alicia_ponte.separar_expressao(resp)[1].splitlines()[0] if resp.strip() else "").strip()
            if 2 <= len(palavra) <= 24:
                g = palavra.capitalize()
    _generos_cache[artista] = g
    return g


def _baixar_audio(vid: str) -> Path:
    idx = _indice()
    if vid in idx and (DADOS / idx[vid]["arquivo"]).exists():
        return DADOS / idx[vid]["arquivo"]
    trava = _baixando.setdefault(vid, __import__("threading").Lock())
    with trava:
        idx = _indice()
        if vid in idx and (DADOS / idx[vid]["arquivo"]).exists():
            return DADOS / idx[vid]["arquivo"]
        if shutil.disk_usage(DADOS).used / shutil.disk_usage(DADOS).total > 0.92:
            raise RuntimeError("disco quase cheio")
        import yt_dlp
        tmp_dir = RAIZ / "dados" / "musica_tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        info = None
        for fmt in ("bestaudio[ext=m4a]/bestaudio", "bestaudio"):      # alguns vídeos só liberam um dos formatos
            opts = {"quiet": True, "no_warnings": True, "noplaylist": True, "format": fmt, "retries": 3,
                    "outtmpl": str(tmp_dir / f"{vid}.%(ext)s")}
            if NODE_EXE:
                opts["js_runtimes"] = {"node": {"path": str(NODE_EXE)}}   # o YouTube exige um interpretador JS
            try:
                with yt_dlp.YoutubeDL(opts) as y:
                    info = y.extract_info(f"https://www.youtube.com/watch?v={vid}", download=True)
                break
            except Exception:
                continue
        arq = next(iter(tmp_dir.glob(f"{vid}.*")), None)
        if not info or not arq:
            raise RuntimeError("não baixou")
        artista = _artista(info)
        titulo = _titulo(info, artista, vid)
        genero = _genero(artista, titulo)
        pasta = MUSICA_DIR / _limpa(genero, "Sem gênero") / artista
        pasta.mkdir(parents=True, exist_ok=True)
        destino = pasta / f"{titulo}{arq.suffix}"
        if destino.exists():
            destino = pasta / f"{titulo} [{vid}]{arq.suffix}"
        shutil.move(str(arq), str(destino))
        with _trava_musica:
            idx = _indice()
            idx[vid] = {"titulo": titulo, "artista": artista, "genero": genero, "capa": f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg",
                        "arquivo": str(destino.relative_to(DADOS)), "em": time.strftime("%Y-%m-%d"), "duracao": int(info.get("duration") or 0)}
            _salvar_indice(idx)
        registrar("MÚSICA", "-", "-", f"guardou no servidor: {artista} — {titulo} ({genero})", "ok", "info")
        return destino


@app.get("/api/musica/audio/{vid}")
async def musica_audio(vid: str, request: Request):
    exigir_login(request)
    if not re.fullmatch(r"[\w-]{11}", vid):
        raise HTTPException(400, "Vídeo inválido.")
    try:
        arq = await asyncio.to_thread(_baixar_audio, vid)
    except Exception as ex:
        print("ERRO áudio:", type(ex).__name__, str(ex)[:200], file=__import__("sys").stderr, flush=True)
        raise HTTPException(502, "Não consegui pegar o áudio dessa música agora.")
    tipo = {".m4a": "audio/mp4", ".webm": "audio/webm", ".opus": "audio/ogg", ".mp3": "audio/mpeg"}.get(arq.suffix.lower(), "audio/mp4")
    return FileResponse(arq, media_type=tipo)   # o FileResponse aceita pular para qualquer ponto da música


@app.get("/api/musica/proxima")
async def musica_proxima(request: Request, id: str, vistos: str = ""):
    """Rádio automática: escolhe outra música do MESMO GÊNERO da que acabou de tocar (primeiro da biblioteca; se não houver, busca mais)."""
    exigir_login(request)
    if not re.fullmatch(r"[\w-]{11}", id):
        raise HTTPException(400, "Vídeo inválido.")
    ja = {v for v in vistos.split(",") if re.fullmatch(r"[\w-]{11}", v)} | {id}
    idx = _indice()
    atual = idx.get(id)
    genero = (atual or {}).get("genero")
    if genero and genero != "Sem gênero":
        lib = [v for v, i in idx.items() if i["genero"] == genero and v not in ja and (DADOS / i["arquivo"]).exists()]
        if lib:
            v = random.choice(lib)
            i = idx[v]
            return {"id": v, "titulo": i["titulo"], "canal": i["artista"], "capa": i["capa"], "origem": "biblioteca"}
    consulta = f"melhores músicas de {genero}" if genero and genero != "Sem gênero" else (f"{atual['artista']} mix" if atual else "músicas populares")
    try:
        achados = await asyncio.to_thread(_buscar_youtube, consulta)
    except Exception:
        raise HTTPException(502, "Não consegui achar a próxima música agora.")
    # prefere vídeos de música de verdade (evita coletâneas de horas)
    achados = [t for t in achados if t["id"] not in ja]
    if not achados:
        raise HTTPException(404, "Não achei mais músicas desse gênero.")
    t = random.choice(achados[:8])
    return {**t, "origem": "busca"}


@app.get("/api/musica/servidor")
async def musica_servidor(request: Request):
    """A biblioteca guardada no servidor: por artista, por gênero, todas as músicas e as adicionadas há pouco."""
    exigir_login(request)
    idx = _indice()
    mk = lambda v, i: {"id": v, "titulo": i["titulo"], "canal": i["artista"], "capa": i["capa"], "genero": i["genero"],
                       "duracao": i.get("duracao", 0), "em": i.get("em", "")}
    todas = [mk(v, i) for v, i in idx.items() if (DADOS / i["arquivo"]).exists()]
    por_artista, por_genero = {}, {}
    for t in todas:
        por_artista.setdefault(t["canal"], []).append(t)
        por_genero.setdefault(t["genero"], []).append(t)
    return {"artistas": dict(sorted(por_artista.items(), key=lambda x: x[0].lower())),
            "generos": dict(sorted(por_genero.items(), key=lambda x: x[0].lower())),
            "musicas": sorted(todas, key=lambda t: t["titulo"].lower()),
            "recentes": list(reversed(todas))[:24], "total": len(todas)}

# ----- Filmes e séries: envio organizado pelo painel (nomes no padrão que o Jellyfin entende) -----
_ultimo_refresh = {"t": 0}


def _jellyfin_atualizar():
    chave = ler_env().get("JELLYFIN_API_KEY")
    if not chave or time.time() - _ultimo_refresh["t"] < 20:
        return
    _ultimo_refresh["t"] = time.time()
    try:
        urllib.request.urlopen(urllib.request.Request("http://127.0.0.1:8096/Library/Refresh", data=b"", method="POST",
                                                      headers={"Authorization": f'MediaBrowser Token="{chave}"'}), timeout=10)
    except Exception:
        pass


@app.post("/api/filmes/enviar")
async def filmes_enviar(request: Request, tipo: str, nome: str = "", temporada: int = 1, arquivo: UploadFile = File(...)):
    u = exigir_login(request)
    ext = Path(arquivo.filename).suffix.lower()
    if ext not in (".mkv", ".mp4", ".avi", ".mov", ".m4v", ".wmv", ".webm", ".srt", ".ass", ".vtt"):
        raise HTTPException(400, "Formato não suportado. Use .mkv, .mp4, .avi, .mov (e legendas .srt).")
    base = Path(re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", Path(arquivo.filename).name))
    if tipo == "filme":
        # Jellyfin: Filmes/Nome do Filme (Ano)/Nome do Filme (Ano).mkv
        pasta = DADOS / "Filmes" / _limpa(base.stem, "Filme")
    elif tipo == "serie":
        if not nome.strip():
            raise HTTPException(400, "Escreva o nome da série.")
        # Jellyfin: Séries/Nome da Série/Season 01/Nome S01E01.mkv
        pasta = DADOS / "Séries" / _limpa(nome, "Série") / f"Season {max(1, min(temporada, 99)):02d}"
    else:
        raise HTTPException(400, "Escolha Filme ou Série.")
    pasta.mkdir(parents=True, exist_ok=True)
    destino = pasta / base.name
    with open(destino, "wb") as f:
        shutil.copyfileobj(arquivo.file, f)
    registrar("ARQUIVOS", u, ip_de(request), f"enviou {tipo}: {base.name}", "ok", "ok")
    await asyncio.to_thread(_jellyfin_atualizar)
    return {"ok": True, "pasta": str(pasta.relative_to(DADOS))}


# ----- RPG -----
def _sala_do_jogador(codigo, u):
    s = rpg.salas.get(codigo.upper())
    if not s:
        raise HTTPException(404, "Não achei essa mesa. Confira o código.")
    if u not in s["jogadores"] and u != s["dono"]:
        raise HTTPException(403, "Você ainda não entrou nessa mesa.")
    return s


def _vista(s):
    """Estado da mesa para o navegador (sem nada secreto)."""
    camp = rpg.CAMPANHAS[s["campanha"]]
    return {"codigo": s["codigo"], "dono": s["dono"], "campanha": camp["titulo"], "capitulo": s["cap"] + 1,
            "capitulos": len(camp["capitulos"]), "fim": s["fim"], "log": s["log"][-60:], "combate": s["combate"] and {
                "turno_de": s["combate"]["ordem"][s["combate"]["turno"] % len(s["combate"]["ordem"])]["id"],
                "inimigos": [{"id": e["id"], "nome": e["nome"], "pv": e["pv"], "pv_max": e["pv_max"]} for e in s["combate"]["inimigos"]]},
            "jogadores": {u: {"ficha": j["ficha"]} for u, j in s["jogadores"].items()}}


@app.get("/api/rpg/info")
async def rpg_info(request: Request):
    exigir_login(request)
    return {"personagens": [{"indice": i, **{k: p[k] for k in ("nome", "classe", "especie", "pv", "ca", "historia", "pericias", "equipamento", "magias")}} for i, p in enumerate(rpg.PERSONAGENS)],
            "campanhas": [{"id": k, "titulo": v["titulo"], "resumo": v["resumo"]} for k, v in rpg.CAMPANHAS.items()]}


@app.post("/api/rpg/sala")
async def rpg_criar(request: Request):
    u = exigir_login(request)
    try:
        s = rpg.criar_sala(u, (await request.json()).get("campanha", ""))
    except ValueError as e:
        raise HTTPException(400, str(e))
    registrar("RPG", u, ip_de(request), f"criou a mesa {s['codigo']}", "ok", "ok")
    return {"codigo": s["codigo"]}


@app.post("/api/rpg/entrar")
async def rpg_entrar(request: Request):
    u = exigir_login(request)
    c = await request.json()
    try:
        s = rpg.entrar(str(c.get("codigo", "")), u, int(c.get("personagem", 0)))
    except (ValueError, IndexError) as e:
        raise HTTPException(400, str(e))
    registrar("RPG", u, ip_de(request), f"entrou na mesa {s['codigo']}", "ok", "ok")
    return _vista(s)


@app.get("/api/rpg/sala/{codigo}")
async def rpg_ver(codigo: str, request: Request):
    return _vista(_sala_do_jogador(codigo, exigir_login(request)))


@app.post("/api/rpg/sala/{codigo}/dado")
async def rpg_dado(codigo: str, request: Request):
    u = exigir_login(request)
    s = _sala_do_jogador(codigo, u)
    c = await request.json()
    try:
        r = rpg.rolagem(s, u, str(c.get("expr", "d20")), str(c.get("motivo", ""))[:60], c.get("modo", "normal"))
    except ValueError as e:
        raise HTTPException(400, str(e))
    registrar("RPG", u, ip_de(request), f"rolou {r['expr']} na mesa {s['codigo']} = {r['total']}", "ok", "info")
    return r


@app.post("/api/rpg/sala/{codigo}/falar")
async def rpg_falar(codigo: str, request: Request):
    u = exigir_login(request)
    s = _sala_do_jogador(codigo, u)
    texto = str((await request.json()).get("texto", "")).strip()[:500]
    if not texto:
        raise HTTPException(400, "Escreva o que você faz ou diz.")
    if texto.startswith("//"):                       # bate-papo da mesa, a mestra não responde
        rpg._log(s, u, texto[2:].strip()); rpg.salvar()
        return _vista(s)
    rpg._log(s, u, texto)
    rpg.registrar_escolha(s, texto)
    env = ler_env()
    if not env.get("NVIDIA_API_KEY") and env.get("ALICIA_MODO_TESTE") != "1":
        rpg._log(s, "Alicia", "A Alicia ainda não tem cérebro. Coloque a chave da NVIDIA em Configurações.", "sistema")
        rpg.salvar()
        return _vista(s)
    ok, resp = await asyncio.to_thread(alicia_ponte.perguntar_hermes, env, "", rpg.contexto_para_mestra(s, u, texto), texto)
    registrar("RPG", u, ip_de(request), f"mestra narrou na mesa {s['codigo']}", "ok" if ok else "erro", "ok" if ok else "erro")
    _, limpo = alicia_ponte.separar_expressao(resp)
    rpg._log(s, "Alicia", limpo if ok else resp, "narracao" if ok else "sistema")
    if rpg.precisa_resumir(s):                       # custo da API: resume a história antiga em vez de reenviar tudo
        ok2, res = await asyncio.to_thread(alicia_ponte.perguntar_hermes, env, "", "Resuma em até 5 frases, em português, os fatos importantes desta aventura.",
                                           (s["resumo"] + "\n" + "\n".join(f"{x['quem']}: {x['texto']}" for x in s["log"][-25:]))[:3000])
        if ok2:
            s["resumo"] = alicia_ponte.separar_expressao(res)[1][:900]
    rpg.salvar()
    return _vista(s)


@app.post("/api/rpg/sala/{codigo}/combate")
async def rpg_combate(codigo: str, request: Request):
    u = exigir_login(request)
    s = _sala_do_jogador(codigo, u)
    c = await request.json()
    try:
        if c.get("acao") == "iniciar":
            rpg.iniciar_combate(s)
        elif c.get("acao") == "atacar":
            rpg.atacar(s, u, str(c.get("alvo", "")))
        elif c.get("acao") == "capitulo" and u == s["dono"]:
            rpg.avancar_capitulo(s)
        else:
            raise ValueError("Ação desconhecida.")
    except (ValueError, KeyError) as e:
        raise HTTPException(400, str(e))
    registrar("RPG", u, ip_de(request), f"{c.get('acao')} na mesa {s['codigo']}", "ok", "info")
    return _vista(s)


# ----- Registros ao vivo -----
def ultimas(n=200):
    f = LOG_DIR / "acessos.log"
    if not f.exists():
        return []
    return [json.loads(l) for l in f.read_text(encoding="utf-8").splitlines()[-n:] if l.strip()]


@app.get("/api/logs")
async def logs(request: Request, n: int = 200):
    exigir_login(request)
    return ultimas(min(n, 1000))


@app.get("/api/logs/ao-vivo")
async def logs_ao_vivo(request: Request):
    exigir_login(request)

    async def gerar():
        f = LOG_DIR / "acessos.log"
        pos = f.stat().st_size if f.exists() else 0
        while not await request.is_disconnected():
            if f.exists() and f.stat().st_size > pos:
                with open(f, encoding="utf-8") as fh:
                    fh.seek(pos)
                    for l in fh.read().splitlines():
                        yield f"data: {l}\n\n"
                    pos = fh.tell()
            elif f.exists() and f.stat().st_size < pos:
                pos = 0  # arquivo girou
            await asyncio.sleep(1)  # leve para o HD e a CPU

    return StreamingResponse(gerar(), media_type="text/event-stream")


@app.get("/")
async def inicio():
    versao = str(int(max((WEB / n).stat().st_mtime for n in ("app.js", "p_a.js", "p_b.js", "app.css", "index.html") if (WEB / n).exists())))
    html = (WEB / "index.html").read_text(encoding="utf-8").replace("__V__", versao)
    return Response(html, media_type="text/html", headers={"Cache-Control": "no-cache"})


app.mount("/static", StaticFiles(directory=WEB), name="static")
registrar("SISTEMA", "-", "-", "painel iniciou", "ok", "ok")



















