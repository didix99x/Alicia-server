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


_ult_atividade = {}   # (usuário, página/jogo) -> quando foi registrado pela última vez (evita repetir linhas)


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
    if (p.startswith(("/api/logs", "/static", "/ejs", "/api/musica/audio", "/api/jogos/arquivo", "/api/jogos/capa", "/api/jogos/imagem", "/api/jogos/save", "/api/alicia/imagem", "/api/status"))
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
            titulo = item.get("Name", "?")
            if item.get("SeriesName"):
                titulo = f"{item['SeriesName']} — {titulo}"
            if id_ not in _jf_vistos or _jf_vistos[id_]["item"] != item.get("Id"):
                if id_ in _jf_vistos:
                    _jf_fim(_jf_vistos[id_])
                conv = (s.get("PlayState") or {}).get("PlayMethod", "?")
                _jf_vistos[id_] = {"item": item.get("Id"), "titulo": titulo, "quem": s.get("UserName") or "-", "ip": s.get("RemoteEndPoint") or "-", "t0": time.time(), "pausado": False}
                registrar("FILME", _jf_vistos[id_]["quem"], _jf_vistos[id_]["ip"],
                          f"COMEÇOU a assistir '{titulo}' em {s.get('DeviceName', '?')} ({'convertendo vídeo, pesa no notebook' if conv == 'Transcode' else 'direto, sem converter'})",
                          "ok", "aviso" if conv == "Transcode" else "ok")
            pausado = bool((s.get("PlayState") or {}).get("IsPaused"))
            v = _jf_vistos[id_]
            if pausado != v["pausado"]:
                v["pausado"] = pausado
                registrar("FILME", v["quem"], v["ip"], f"{'pausou' if pausado else 'continuou'} '{titulo}'", "ok", "info")
        for k in [k for k in _jf_vistos if k not in agora]:
            _jf_fim(_jf_vistos.pop(k))


def _jf_fim(v):
    seg = int(time.time() - v["t0"])
    registrar("FILME", v["quem"], v["ip"], f"PAROU de assistir '{v['titulo']}' (viu cerca de {seg // 60} min)", "ok", "info")

async def _vigia():
    psutil.cpu_percent(interval=None)
    while True:
        try:
            await asyncio.to_thread(_vigiar_uma_vez)
        except Exception:
            pass
        await asyncio.sleep(10)


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


_conv_ativa = {"rodando": False, "atual": "", "senha": []}
_senhas_rar = {}       # nome do .rar -> senha digitada pelo dono (só na memória; nunca vai para disco nem para o log)
EXT_ROM = {".cue", ".bin", ".iso", ".img", ".chd", ".pbp", ".sfc", ".smc", ".nes", ".gba", ".gb", ".gbc", ".z64", ".n64", ".v64", ".fds"}
SETE_ZIP = Path(r"C:\Program Files\7-Zip\7z.exe")


def _extrair(rar: Path, destino: Path):
    """Descompacta com o 7-Zip (lê .rar com ou sem senha); sem ele, tenta o tar do Windows. Retorna (ok, precisa_senha)."""
    import subprocess
    if SETE_ZIP.exists():
        senha = _senhas_rar.get(rar.name, "")
        r = subprocess.run([str(SETE_ZIP), "x", "-y", f"-p{senha}", f"-o{destino}", str(rar)], capture_output=True, timeout=3600, stdin=subprocess.DEVNULL)
        saida = (r.stdout + r.stderr).decode("utf-8", "ignore").lower()
        return r.returncode == 0, ("password" in saida or "wrong" in saida) and r.returncode != 0
    r = subprocess.run(["tar", "-xf", str(rar), "-C", str(destino)], capture_output=True, timeout=3600)
    return r.returncode == 0, False


def _limpa_nome(t: str) -> str:
    t = re.sub(r"[\[\(].*?[\]\)]", " ", t.replace("_", " "))
    t = re.sub(r"[\\/:*?\"<>|]", " ", t)
    return re.sub(r"\s+", " ", t).strip(" -") or "Jogo"


def _empacotar(raiz: Path, base: str, console_dir: Path) -> list:
    """Procura jogos dentro de uma pasta (.cue + .bin, .iso, .sfc…) e cria um .zip simples por jogo/disco em console_dir.
    Jogo de vários discos vira uma entrada por disco ('Nome - CD 1', 'Nome - CD 2'). Devolve os nomes criados."""
    import zipfile
    achados = [p for p in raiz.rglob("*") if p.is_file() and p.suffix.lower() in EXT_ROM]
    cues = [p for p in achados if p.suffix.lower() == ".cue"]
    jogos = []                                            # (arquivos, dica de nome)
    usados = set()
    def disco(t):
        m = re.search(r"cd\s*0?(\d)|dis[ck]o?\s*0?(\d)", t, re.I)
        return next((g for g in m.groups() if g), None) if m else None

    for cue in sorted(cues):
        txt = cue.read_text(encoding="utf-8", errors="ignore")
        nomes_ref = re.findall(r'FILE\s+"([^"\r\n]+)"\s+\w+', txt, re.I) or re.findall(r'FILE\s+(\S+)\s+\w+', txt, re.I)
        bins = []
        for nr in nomes_ref:
            alvo_ = next((x for x in cue.parent.iterdir() if x.name.lower() == nr.lower()), None)
            if alvo_ is None:                                   # a .cue aponta para um nome que não existe: acha o .bin certo da mesma pasta
                livres = [x for x in cue.parent.iterdir() if x.suffix.lower() == ".bin" and x not in usados and x not in bins]
                alvo_ = (next((x for x in livres if x.stem.lower() == cue.stem.lower()), None)
                         or next((x for x in livres if disco(x.stem) and disco(x.stem) == disco(cue.stem)), None)
                         or (livres[0] if len(livres) == 1 else None))
                if alvo_ is not None:
                    txt = txt.replace(nr, alvo_.name)           # corrige o nome dentro do .cue
            if alvo_ is not None:
                bins.append(alvo_)
        usados.update(bins)
        jogos.append(([(cue, txt)] + bins, f"{cue.parent.name} {cue.stem}"))
    for p in achados:
        if p.suffix.lower() not in (".cue", ".bin") and p not in usados:
            jogos.append(([p], p.stem))
    nomes = []
    for i, (arqs, dica) in enumerate(jogos, 1):
        nome = _limpa_nome(base)
        if len(jogos) > 1:
            nome += f" - CD {disco(dica) or i}"
        alvo = console_dir / f"{nome}.zip"
        if alvo.exists():
            continue
        parcial = alvo.with_suffix(".parcial")
        with zipfile.ZipFile(parcial, "w", zipfile.ZIP_STORED, allowZip64=True) as z:
            for p in arqs:
                if isinstance(p, tuple):
                    z.writestr(p[0].name, p[1])                 # o .cue já corrigido
                else:
                    z.write(p, p.name)
        parcial.replace(alvo)
        for capa in list(raiz.rglob("*.jpg")) + list(raiz.rglob("*.png")):
            if re.search(r"capa|cover|box", capa.stem, re.I):
                shutil.copy(capa, console_dir / f"{nome}{capa.suffix.lower()}")
                break
        nomes.append(alvo.name)
    return nomes


def _converter_rars():
    """Deixa os jogos prontos para o emulador: .rar viram .zip e PASTAS com .bin/.cue (jogos já descompactados) também.
    Os originais vão para Jogos/Originais_rar (pode apagar depois para liberar espaço). .rar com senha esperam a senha no painel."""
    if _conv_ativa["rodando"]:
        return
    _conv_ativa["rodando"] = True
    try:
        import tempfile
        originais = JOGOS_DIR / "Originais_rar"
        for pasta in list(CONSOLES):
            cdir = JOGOS_DIR / pasta
            for sub in sorted(x for x in cdir.iterdir() if x.is_dir()):          # jogos já descompactados em pastas
                _conv_ativa["atual"] = sub.name
                try:
                    nomes = _empacotar(sub, sub.name, cdir)
                    if nomes:
                        originais.mkdir(exist_ok=True)
                        destino = originais / sub.name
                        if destino.exists():
                            destino = originais / f"{sub.name}_{int(time.time())}"
                        shutil.move(str(sub), str(destino))
                        registrar("JOGOS", "-", "-", f"organizou a pasta '{sub.name}': {', '.join(nomes)}", "ok", "ok")
                except Exception as e:
                    registrar("JOGOS", "-", "-", f"erro ao organizar a pasta '{sub.name}': {str(e)[:80]}", "erro", "erro")
            for rar in sorted(cdir.glob("*.rar")):
                if any(x["arquivo"] == rar.name for x in _conv_ativa["senha"]) and rar.name not in _senhas_rar:
                    continue                                   # já sabemos que pede senha e ela ainda não foi informada
                _conv_ativa["senha"] = [x for x in _conv_ativa["senha"] if x["arquivo"] != rar.name]
                nome = _limpa_nome(rar.stem)
                _conv_ativa["atual"] = nome
                tmp = Path(tempfile.mkdtemp(prefix="conv_", dir=JOGOS_DIR))
                try:
                    ok, pede_senha = _extrair(rar, tmp)
                    if pede_senha:
                        _conv_ativa["senha"].append({"pasta": pasta, "arquivo": rar.name, "nome": nome, "errada": rar.name in _senhas_rar})
                        _senhas_rar.pop(rar.name, None)
                        continue
                    nomes = _empacotar(tmp, nome, cdir) if ok else []
                    if not nomes:
                        registrar("JOGOS", "-", "-", f"não consegui abrir '{rar.name}' (precisa ter .bin/.cue ou o arquivo do jogo dentro)", "erro", "erro")
                        rar.rename(rar.with_suffix(".rar.erro"))
                        continue
                    originais.mkdir(exist_ok=True)
                    rar.replace(originais / rar.name)
                    _senhas_rar.pop(rar.name, None)
                    registrar("JOGOS", "-", "-", f"converteu '{rar.name}' em {', '.join(nomes)}", "ok", "ok")
                except Exception as e:
                    registrar("JOGOS", "-", "-", f"erro ao converter '{rar.name}': {str(e)[:80]}", "erro", "erro")
                finally:
                    shutil.rmtree(tmp, ignore_errors=True)
    finally:
        _conv_ativa["rodando"] = False
        _conv_ativa["atual"] = ""

@app.post("/api/jogos/senha")
async def jogos_senha(request: Request):
    """Senha de um .rar protegido; usada só para descompactar (guardada só na memória)."""
    u = exigir_login(request)
    c = await request.json()
    pasta, arq = str(c.get("pasta", "")), str(c.get("arquivo", ""))
    if pasta not in CONSOLES or "/" in arq or "\\" in arq or not (JOGOS_DIR / pasta / arq).is_file():
        raise HTTPException(404, "Arquivo não encontrado.")
    _senhas_rar[arq] = str(c.get("senha", ""))[:200]
    registrar("JOGOS", u, ip_de(request), f"informou a senha do arquivo '{arq}' (a senha não é guardada)", "ok", "info")
    if not _conv_ativa["rodando"]:
        __import__("threading").Thread(target=_converter_rars, daemon=True).start()
    return {"ok": True}

@app.get("/api/jogos")
async def jogos_lista(request: Request):
    exigir_login(request)
    await asyncio.to_thread(_organizar_jogos)
    if not _conv_ativa["rodando"] and any((r.is_dir() or r.name not in {x["arquivo"] for x in _conv_ativa["senha"]} or r.name in _senhas_rar) for c in CONSOLES for r in (JOGOS_DIR / c).iterdir() if r.is_dir() or r.suffix.lower() == ".rar"):
        __import__("threading").Thread(target=_converter_rars, daemon=True).start()
    favs = set(_ler_favoritos(exigir_login(request)))
    out = []
    for pasta, (nucleo, nome, cor, exts) in CONSOLES.items():
        itens = []
        for f in sorted((JOGOS_DIR / pasta).iterdir(), key=lambda x: x.name.lower()):
            if f.is_file() and f.suffix.lower() in exts:
                capa = next((f"{f.stem}{e}" for e in (".png", ".jpg", ".jpeg") if (f.parent / f"{f.stem}{e}").exists()), None)
                itens.append({"arquivo": f.name, "nome": _nome_bonito(f), "capa": capa})
        for it in itens:
            it["fav"] = f"{pasta}/{it['arquivo']}" in favs
        out.append({"pasta": pasta, "nome": nome, "cor": cor, "jogos": itens, "jogadores": JOGADORES.get(pasta, 1), "emulador": _info_emulador(pasta, nucleo), "convertendo": _conv_ativa["atual"] if _conv_ativa["rodando"] else "", "pede_senha": [x for x in _conv_ativa["senha"] if x["pasta"] == pasta]})
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
    ch = (u, pasta, arquivo)
    if time.time() - _ult_atividade.get(ch, 0) > 300:
        _ult_atividade[ch] = time.time()
        registrar("JOGOS", u, ip_de(request), f"salvou o progresso de '{_nome_bonito(Path(arquivo))}' ({pasta})", "ok", "info")
    return {"ok": True}


@app.post("/api/jogos/inicio")
async def jogos_inicio(request: Request):
    u = exigir_login(request)
    c = await request.json()
    pasta = str(c.get("pasta", "")) if str(c.get("pasta", "")) in CONSOLES else "?"
    registrar("JOGOS", u, ip_de(request), f"ABRIU o jogo '{_nome_bonito(Path(str(c.get('arquivo', ''))[:100]))}' ({pasta})", "ok", "ok")
    return {"ok": True}


@app.post("/api/jogos/fim")
async def jogos_fim(request: Request):
    u = exigir_login(request)
    c = await request.json()
    seg = max(0, min(int(c.get("segundos", 0) or 0), 86400))
    pasta = str(c.get("pasta", "")) if str(c.get("pasta", "")) in CONSOLES else "?"
    registrar("JOGOS", u, ip_de(request), f"FECHOU o jogo '{_nome_bonito(Path(str(c.get('arquivo', ''))[:100]))}' ({pasta}) depois de {seg // 60} min {seg % 60:02d} s", "ok", "info")
    return {"ok": True}


PAGINAS_REG = {"inicio": "Início", "alicia": "Alicia", "arquivos": "Arquivos", "filmes": "Filmes e Séries", "jogos": "Jogos", "musica": "Música", "rpg": "RPG",
               "servidor": "Servidor", "registros": "Registros", "config": "Configurações"}


@app.post("/api/atividade")
async def atividade(request: Request):
    """O painel avisa quando alguém troca de página, para o monitor mostrar 'fulano abriu Filmes'."""
    u = exigir_login(request)
    p = str((await request.json()).get("pagina", ""))
    if p in PAGINAS_REG and time.time() - _ult_atividade.get((u, p), 0) > 20:
        _ult_atividade[(u, p)] = time.time()
        registrar("PÁGINA", u, ip_de(request), f"abriu a página {PAGINAS_REG[p]}", "ok", "info")
    return {"ok": True}


@app.get("/api/jogos/capa")
async def jogos_capa(request: Request, pasta: str, arquivo: str):
    exigir_login(request)
    return FileResponse(_arquivo_jogo(pasta, arquivo))


# ----- Favoritos, capas automáticas e informações dos emuladores -----
EMULADORES = {  # pasta -> (nome do emulador, desempenho, descrição curta, pasta de capas do libretro)
    "Nintendo": ("FCEUmm", "leve", "Roda em qualquer aparelho.", "Nintendo - Nintendo Entertainment System"),
    "Super Nintendo": ("Snes9x", "leve", "Roda em qualquer aparelho.", "Nintendo - Super Nintendo Entertainment System"),
    "Nintendo 64": ("Mupen64Plus-Next", "pesado", "Pede celular/TV box forte ou computador.", "Nintendo - Nintendo 64"),
    "Game Boy Advance": ("mGBA", "leve", "Roda em qualquer aparelho.", "Nintendo - Game Boy Advance"),
    "Game Boy": ("Gambatte", "leve", "Roda em qualquer aparelho.", "Nintendo - Game Boy Color"),
    "PlayStation": ("PCSX-ReARMed", "médio", "Melhor com a BIOS (opcional) em Jogos/BIOS.", "Sony - PlayStation"),
}
CAPAS_DIR = JOGOS_DIR / "Capas"
CAPAS_DIR.mkdir(exist_ok=True)


def _info_emulador(pasta: str, nucleo: str) -> dict:
    nome, desemp, dica, _ = EMULADORES[pasta]
    arq = {"nes": "fceumm", "snes": "snes9x", "n64": "mupen64plus_next", "gba": "mgba", "gb": "gambatte", "psx": "pcsx_rearmed"}.get(nucleo, nucleo)
    nucleo_ok = EJS_DIR.exists() and any((EJS_DIR / "cores").glob(f"{arq}-*"))
    bios = None
    if pasta == "PlayStation":
        bios = any((JOGOS_DIR / "BIOS" / n).exists() for n in ("scph5501.bin", "scph1001.bin", "scph5500.bin", "scph5502.bin", "SCPH5501.BIN", "SCPH1001.BIN"))
    return {"nome": nome, "nucleo": nucleo, "desempenho": desemp, "dica": dica, "pronto": bool(nucleo_ok), "bios": bios}


def _arq_fav(u: str) -> Path:
    return RAIZ / "dados" / f"jogos_fav_{re.sub(r'[^a-z0-9_-]', '', u.lower())}.json"


def _ler_favoritos(u: str) -> list:
    try:
        return json.loads(_arq_fav(u).read_text(encoding="utf-8-sig"))
    except Exception:
        return []


@app.post("/api/jogos/favorito")
async def jogos_favorito(request: Request):
    u = exigir_login(request)
    c = await request.json()
    pasta, arq = str(c.get("pasta", "")), str(c.get("arquivo", ""))
    _arquivo_jogo(pasta, arq)
    favs = _ler_favoritos(u)
    chave = f"{pasta}/{arq}"
    marcar = bool(c.get("fav", chave not in favs))
    favs = [x for x in favs if x != chave] + ([chave] if marcar else [])
    _arq_fav(u).write_text(json.dumps(favs, ensure_ascii=False), encoding="utf-8")
    return {"ok": True, "fav": marcar}


def _chave_titulo(n: str) -> str:
    n = re.sub(r"[\[\(].*?[\]\)]", " ", n).lower()
    m = re.match(r"^(.*?),\s*(the|a|an)\b(.*)$", n)          # "Legend of Zelda, The - X" -> "the legend of zelda - x"
    if m:
        n = f"{m.group(2)} {m.group(1)}{m.group(3)}"
    n = n.replace("&", " and ")
    return re.sub(r"[^a-z0-9]+", "", n)


def _lista_capas(pasta: str) -> dict:
    """Lista pública de capas (libretro-thumbnails) do console, guardada 30 dias: {chave_titulo: [nomes de arquivo]}."""
    import urllib.request, urllib.parse, html as _html
    cache = CAPAS_DIR / f"_lista_{_slug(pasta)}.json"
    if cache.exists() and time.time() - cache.stat().st_mtime < 30 * 86400:
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            pass
    url = "https://thumbnails.libretro.com/" + urllib.parse.quote(EMULADORES[pasta][3]) + "/Named_Boxarts/"
    try:
        pag = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "AliciaServer"}), timeout=40).read().decode("utf-8", "ignore")
    except Exception:
        return json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else {}
    out = {}
    for h_ in re.findall(r'href="([^"]+\.png)"', pag):
        nome = _html.unescape(urllib.parse.unquote(h_))
        out.setdefault(_chave_titulo(nome[:-4]), []).append(nome)
    cache.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
    return out


def _melhor_capa(nomes: list) -> str:
    def nota(n):
        return (0 if "(USA" in n else 1 if "(World" in n else 2 if "(Europe" in n else 3, len(n))
    return sorted(nomes, key=nota)[0]


def _buscar_capa(pasta: str, arquivo: str) -> Path | None:
    import difflib, urllib.request, urllib.parse
    destino = CAPAS_DIR / pasta / (Path(arquivo).stem + ".png")
    if destino.exists():
        return destino
    falha = CAPAS_DIR / pasta / (Path(arquivo).stem + ".sem")
    if falha.exists() and time.time() - falha.stat().st_mtime < 7 * 86400:
        return None
    destino.parent.mkdir(parents=True, exist_ok=True)
    lista = _lista_capas(pasta)
    chave = _chave_titulo(Path(arquivo).stem)
    achado = lista.get(chave)
    if not achado and chave and lista:
        perto = difflib.get_close_matches(chave, list(lista), n=1, cutoff=0.9)
        achado = lista.get(perto[0]) if perto else None
    if achado:
        url = "https://thumbnails.libretro.com/" + urllib.parse.quote(EMULADORES[pasta][3]) + "/Named_Boxarts/" + urllib.parse.quote(_melhor_capa(achado))
        try:
            dados = urllib.request.urlopen(urllib.request.Request(url, headers={"User-Agent": "AliciaServer"}), timeout=30).read()
            if len(dados) > 500:
                destino.write_bytes(dados)
                return destino
        except Exception:
            pass
    if lista:                                   # só marca como "sem capa" se a lista chegou; sem internet tenta de novo depois
        falha.write_text("sem capa", encoding="utf-8")
    return None


_sem_capas = __import__("threading").BoundedSemaphore(3)


@app.get("/api/jogos/imagem")
async def jogos_imagem(request: Request, pasta: str, arquivo: str):
    """Capa do jogo: a que você enviou (mesmo nome) ou a oficial da caixa, buscada uma vez e guardada no servidor."""
    exigir_login(request)
    jogo = _arquivo_jogo(pasta, arquivo)
    for e in (".png", ".jpg", ".jpeg"):
        if jogo.with_suffix(e).exists():
            return FileResponse(jogo.with_suffix(e), headers={"Cache-Control": "max-age=86400"})

    def _faz():
        with _sem_capas:
            return _buscar_capa(pasta, arquivo)
    p = await asyncio.to_thread(_faz)
    if not p:
        raise HTTPException(404, "Sem capa.")
    return FileResponse(p, headers={"Cache-Control": "max-age=604800"})

# ----- Multiplayer: quem abre o jogo ("anfitrião") transmite a tela para os amigos e recebe os controles deles -----
# O jogo roda só no aparelho do anfitrião (WebRTC); o servidor apenas apresenta os aparelhos uns aos outros (sinalização) e lista as salas.
JOGADORES = {"Nintendo": 2, "Super Nintendo": 2, "Nintendo 64": 4, "PlayStation": 2, "Game Boy": 1, "Game Boy Advance": 1}
SALAS = {}   # código -> {"host": ws, "usuario", "pasta", "arquivo", "nome", "max", "guests": {id: {"ws","nome","slot"}}}
_LETRAS = "ABCDEFGHJKLMNPQRSTUVWXYZ"


def _corrige_candidatos(obj, ip: str):
    """O navegador esconde o IP local atrás de um nome .local; troca pelo IP real que o servidor enxerga (funciona em casa e via Tailscale)."""
    def troca(t):
        return re.sub(r"[0-9a-fA-F-]{8,}\.local", ip, t) if isinstance(t, str) else t
    if isinstance(obj, dict):
        for k in ("candidate", "sdp"):
            if k in obj:
                obj[k] = troca(obj[k])
        if isinstance(obj.get("cand"), dict):
            obj["cand"]["candidate"] = troca(obj["cand"].get("candidate"))
        if isinstance(obj.get("sdp"), dict):
            obj["sdp"]["sdp"] = troca(obj["sdp"].get("sdp"))
    return obj


async def _envia(ws, dado):
    try:
        await ws.send_json(dado)
    except Exception:
        pass


@app.get("/api/multi/salas")
async def multi_salas(request: Request):
    exigir_login(request)
    return [{"codigo": c, "nome": s["nome"], "pasta": s["pasta"], "arquivo": s["arquivo"], "host": s["usuario"],
             "jogadores": 1 + len(s["guests"]), "max": s["max"]} for c, s in SALAS.items()]


@app.get("/multi")
async def multi_pagina(request: Request):
    if not usuario_da_sessao(request):
        return FileResponse(WEB / "index.html")
    return FileResponse(WEB / "multi.html")


from starlette.websockets import WebSocket, WebSocketDisconnect


@app.websocket("/ws/multi")
async def ws_multi(ws: WebSocket):
    user = usuario_da_sessao(ws)
    if not user:
        await ws.close(code=4401)
        return
    await ws.accept()
    ip = ws.client.host if ws.client else "?"
    codigo = meu_id = None
    try:
        ini = await asyncio.wait_for(ws.receive_json(), timeout=20)
        if ini.get("t") == "host":
            pasta, arq = str(ini.get("pasta", "")), str(ini.get("arquivo", ""))
            if pasta not in CONSOLES or JOGADORES.get(pasta, 1) < 2:
                await _envia(ws, {"t": "erro", "msg": "Esse console não tem multiplayer."}); return
            _arquivo_jogo(pasta, arq)
            if len(SALAS) >= 8:
                await _envia(ws, {"t": "erro", "msg": "Já há salas demais abertas."}); return
            codigo = "".join(random.choice(_LETRAS) for _ in range(4))
            while codigo in SALAS:
                codigo = "".join(random.choice(_LETRAS) for _ in range(4))
            nome = _nome_bonito(Path(arq))
            SALAS[codigo] = {"host": ws, "usuario": user, "pasta": pasta, "arquivo": arq, "nome": nome, "max": JOGADORES[pasta], "guests": {}}
            registrar("JOGOS", user, ip, f"ABRIU a sala multiplayer {codigo} do jogo '{nome}' ({pasta}, até {JOGADORES[pasta]} jogadores)", "ok", "ok")
            await _envia(ws, {"t": "sala", "codigo": codigo, "max": JOGADORES[pasta]})
            while True:
                m = await ws.receive_json()
                if m.get("t") == "sinal" and m.get("para") in SALAS[codigo]["guests"]:
                    await _envia(SALAS[codigo]["guests"][m["para"]]["ws"], {"t": "sinal", "d": _corrige_candidatos(m.get("d") or {}, ip)})
        elif ini.get("t") == "guest":
            codigo = str(ini.get("sala", "")).upper().strip()
            sala = SALAS.get(codigo)
            if not sala:
                await _envia(ws, {"t": "erro", "msg": "Sala não encontrada. Ela pode ter sido fechada."}); return
            livres = [n for n in range(1, sala["max"]) if n not in {g["slot"] for g in sala["guests"].values()}]
            if not livres:
                await _envia(ws, {"t": "erro", "msg": "A sala está cheia."}); return
            meu_id = "g" + "".join(random.choice(_LETRAS) for _ in range(5))
            slot = livres[0]
            sala["guests"][meu_id] = {"ws": ws, "nome": user, "slot": slot}
            registrar("JOGOS", user, ip, f"ENTROU como jogador {slot + 1} na sala {codigo} de {sala['usuario']} ('{sala['nome']}')", "ok", "ok")
            await _envia(ws, {"t": "ok", "slot": slot, "nome": sala["nome"], "pasta": sala["pasta"], "host": sala["usuario"]})
            await _envia(sala["host"], {"t": "entrou", "id": meu_id, "slot": slot, "nome": user})
            while True:
                m = await ws.receive_json()
                if m.get("t") == "sinal" and codigo in SALAS:
                    await _envia(SALAS[codigo]["host"], {"t": "sinal", "de": meu_id, "d": _corrige_candidatos(m.get("d") or {}, ip)})
    except (WebSocketDisconnect, asyncio.TimeoutError, RuntimeError, ValueError):
        pass
    finally:
        sala = SALAS.get(codigo or "")
        if sala and sala["host"] is ws:
            SALAS.pop(codigo, None)
            for g in list(sala["guests"].values()):
                await _envia(g["ws"], {"t": "fim", "msg": "O anfitrião fechou o jogo."})
                try:
                    await g["ws"].close()
                except Exception:
                    pass
            registrar("JOGOS", user, ip, f"FECHOU a sala multiplayer {codigo}", "ok", "info")
        elif sala and meu_id in sala["guests"]:
            sala["guests"].pop(meu_id, None)
            await _envia(sala["host"], {"t": "saiu", "id": meu_id})
            registrar("JOGOS", user, ip, f"SAIU da sala multiplayer {codigo}", "ok", "info")

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


# ----- A Alicia analisa o servidor: ela recebe os DADOS REAIS medidos pelo painel (só leitura) -----
_saude_cache = {"t": 0, "v": None}
_PERGUNTA_SERVIDOR = re.compile(r"\b(servidor|notebook|disco|hd|memoria|ram|cpu|processador|temperatura|lent[oa]|travand\w*|travou|acesso\w*|registro\w*|logs?|seguranca|invasa\w*|erros?|problemas?|saude|status|analis\w*|diagnostic\w*|backup|espaco|servicos?|uptime|desempenho|consumo|esta tudo bem|ta tudo bem|tudo certo)\b")


def _resumo_logs():
    """Resumo das últimas 24 h do monitor: contagens e os eventos que merecem atenção."""
    f = LOG_DIR / "acessos.log"
    if not f.exists():
        return None, []
    ev = []
    agora = time.time()
    for l in f.read_text(encoding="utf-8-sig", errors="ignore").splitlines()[-4000:]:
        try:
            e = json.loads(l)
        except ValueError:
            continue
        if agora - e.get("ts", 0) < 86400:
            ev.append(e)
    c = {"pedidos": sum(1 for e in ev if e["servico"] == "PAINEL"),
         "logins_ok": sum(1 for e in ev if e["servico"] == "LOGIN" and e["resultado"] == "ok"),
         "senhas_erradas": sum(1 for e in ev if e["servico"] == "LOGIN" and e["resultado"] in ("falhou", "bloqueado")),
         "visitantes": sum(1 for e in ev if "visitante" in e["o_que"] and e["servico"] == "LOGIN"),
         "erros": sum(1 for e in ev if e["tipo"] == "erro" and "favicon" not in e["o_que"]),
         "seguranca": sum(1 for e in ev if e["tipo"] == "seguranca")}
    notaveis = [e for e in ev if e["tipo"] in ("seguranca", "erro", "aviso") and "favicon" not in e["o_que"]][-6:]
    return c, notaveis


def contexto_servidor(detalhado: bool) -> str:
    disco = shutil.disk_usage(DADOS)
    vm = psutil.virtual_memory()
    L = ["[ESTADO REAL DO SERVIDOR AGORA — dados medidos pelo painel neste instante; ao falar do servidor use SÓ isto]",
         f"Hora: {time.strftime('%d/%m/%Y %H:%M')} · ligado há {round((time.time() - psutil.boot_time()) / 3600, 1)} h",
         f"Processador: {psutil.cpu_percent(interval=None)}% · Memória: {vm.percent}% ({vm.used / 1e9:.1f} de {vm.total / 1e9:.1f} GB) · "
         f"Disco: {disco.used / disco.total * 100:.1f}% usado ({disco.free / 1e9:.0f} GB livres de {disco.total / 1e9:.0f} GB)",
         "Serviços: " + "; ".join(f"{s['nome']} {s['estado']}" for s in servicos()),
         "Chave da NVIDIA: " + ("colocada" if ler_env().get("NVIDIA_API_KEY") else "AINDA NÃO colocada")]
    if not detalhado:
        return "\n".join(L)
    por_nome = {}
    for pr in psutil.process_iter(["name", "memory_info"]):
        try:
            por_nome[pr.info["name"]] = por_nome.get(pr.info["name"], 0) + pr.info["memory_info"].rss
        except Exception:
            pass
    top = sorted(por_nome.items(), key=lambda x: -x[1])[:5]
    L.append("Programas que mais usam memória: " + ", ".join(f"{n} {b / 1e6:.0f} MB" for n, b in top))
    if time.time() - _saude_cache["t"] > 600:
        _saude_cache.update(t=time.time(), v=saude_disco())
    L.append(f"Saúde do HD (SMART do Windows): {_saude_cache['v'] or 'não consegui ler'} · Temperatura: o Windows não informa neste notebook")
    try:
        idx = _indice()
        jogos = {c: sum(1 for x in (JOGOS_DIR / c).iterdir() if x.suffix.lower() in CONSOLES[c][3]) for c in CONSOLES}
        L.append(f"Biblioteca: {len(idx)} músicas guardadas · jogos: " + ", ".join(f"{c} {n}" for c, n in jogos.items() if n) )
    except Exception:
        pass
    bk = Path(os.environ.get("ALICIA_BACKUP", r"C:\AliciaServer\Backup")) / "configuracao"
    if bk.exists():
        h = (time.time() - bk.stat().st_mtime) / 3600
        L.append(f"Último backup: há {h:.0f} h (o backup fica no mesmo HD do servidor)")
    else:
        L.append("Último backup: nenhum encontrado")
    c, notaveis = _resumo_logs()
    if c:
        L.append(f"Últimas 24 h: {c['pedidos']} pedidos ao painel · {c['logins_ok']} logins · {c['senhas_erradas']} senhas erradas/bloqueios · "
                 f"{c['visitantes']} entradas de visitante · {c['erros']} erros · {c['seguranca']} eventos de segurança")
        for e in notaveis:
            L.append(f"  - {e['t']} {e['servico']} {e['quem']} ({e['ip']}): {e['o_que']} → {e['resultado']}")
    L.append("Análise: diga o que está bom, o que preocupa e o que fazer, com os números acima. Você só LÊ estes dados; não altera nada sozinha.")
    return "\n".join(L)

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
    detalhado = bool(_PERGUNTA_SERVIDOR.search(_norm(texto)))      # pergunta sobre o servidor: manda o estado completo
    sistema += "\n\n" + await asyncio.to_thread(contexto_servidor, detalhado)
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


_VERBOS = r"(?P<verbo>toca|toque|tocar|ponha|coloca|coloque|colocar|poe|bota|bote|botar|ouvir|escutar|reproduz|reproduza|reproduzir|manda|mande)"
_PREFIXOS = (r"(?:oi|ei|ola|alicia|por favor|pf|pode|poderia|podia|tem como|quero que|queria que|gostaria que|gostaria de|queria|quero|"
             r"eu quero|vou querer|vamos|bora|agora|entao|ai|e|voce|me|a gente)")
_PARADAS = {"pra", "para", "mim", "por", "favor", "ai", "agora", "uma", "um", "a", "o", "as", "os", "musica", "musicas", "som", "faixa", "cancao",
            "aquela", "essa", "esse", "de", "da", "do", "das", "dos", "eu", "ouvir", "tocar", "escutar", "me", "pro", "pra", "tocando", "tocar"}
_GENERICO = {"", "algo", "alguma", "alguma coisa", "qualquer", "qualquer coisa", "qualquer uma", "algo bom", "algo animado", "alguma musica"}
_MODAL = re.compile(r"\b(pode|poderia|podia|tem como|que tal|queria|gostaria)\b")


def extrair_consulta(texto: str):
    """Se a mensagem é um pedido de música, devolve o que foi pedido ('' = qualquer coisa). Senão, None."""
    n = _norm(texto).strip(" ,.!?")
    sobre_musica = re.search(r"\b(musica|som|pra mim|para mim)\b", n)
    if "?" in texto and not _MODAL.search(n) and not sobre_musica:    # "você toca violão?" é pergunta, não pedido
        return None
    if not sobre_musica and re.match(r"^(?:(?:oi|ei|ola|alicia)[ ,]*)*voce (?:toca|coloca|bota|manda|escuta|ouve)\b", n):   # "você toca ..." (afirmação)
        return None
    m = re.match(rf"^(?:{_PREFIXOS}\b[ ,]*)*{_VERBOS}\b(.*)$", n)
    if not m:
        return None
    pal = m.group(2).strip(" ,.!?").split()
    while pal and pal[0] in _PARADAS:        # tira "uma música do/da..." do começo, sem mexer no nome do artista
        pal.pop(0)
    while pal and pal[-1] in _PARADAS | {"favor"}:
        pal.pop()
    consulta = " ".join(pal)
    if not consulta and m.group("verbo") in ("ouvir", "escutar") and not re.search(r"\b(musica|som|algo)\b", n):
        return None                                                  # "você consegue ouvir?" não é pedido de música
    return consulta

_RECOMENDA = re.compile(r"\b(recomend\w*|sugir\w*|sugest\w*|suger\w*|surpreend\w*|me indica\w*|indique|indica uma|descobr\w*)\b")
_NEGA = re.compile(r"nao (?:tenho|consigo|posso|sei|faco)[^.!?]{0,50}(?:tocar|musica|funcao|som)|nao tenho essa|nao consigo (?:colocar|reproduzir)|sem essa funcao")
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
    mixq = _achar_mix(consulta)                               # estilo ou humor conhecido ("pra treinar", "sertanejo", "relaxar")?
    base = []
    if tokens and todas:
        pontos = []
        for v, i in todas:
            alvo = _norm(f"{i['titulo']} {i['artista']} {i['genero']}")
            if all(t in alvo for t in tokens):
                pontos.append((2 if all(t in _norm(i["artista"]) for t in tokens) else 1, v, i))
        if pontos:
            artista = [x for x in pontos if x[0] == 2]
            escolhidas = artista or pontos
            base = [mk(v, i) for _, v, i in escolhidas]
            if not mixq or len(base) >= 5:                    # achou bastante coisa na biblioteca (ou não é um estilo): toca daí
                random.shuffle(base)
                return base[:25] if artista else base[:5], "biblioteca"
    if mixq:                                                  # biblioteca pequena nesse estilo/humor: o mix da Alicia completa
        extra = [t for t in _mix_curado(mixq[0], mixq[1], ler_env()) if t["id"] not in {b["id"] for b in base}]
        random.shuffle(extra)
        lista = base + extra[:14]
        if lista:
            return lista, "mix"
    achados = _buscar_youtube(consulta)
    bons = [t for t in achados if not _RUINS.search(t["titulo"]) or _RUINS.search(consulta)]
    return (bons or achados)[:1], "youtube"

# ----- Descobrir: estilos, humores, playlists do YouTube, recomendações e "guardar no servidor" em segundo plano -----
ESTILOS = [("Pop", "🎤", "pop hits internacional"), ("Rock", "🎸", "rock clássico melhores músicas"), ("Rap e Hip-hop", "🎧", "rap hip hop melhores músicas"),
           ("Funk", "🔊", "funk brasileiro sucessos"), ("Sertanejo", "🤠", "sertanejo sucessos"), ("MPB", "🇧🇷", "mpb clássicos"),
           ("Pagode e Samba", "🥁", "pagode samba sucessos"), ("Forró", "🪗", "forró pé de serra sucessos"), ("Eletrônica", "🎛️", "música eletrônica dance hits"),
           ("Lo-fi", "☕", "lofi beats relaxantes"), ("Jazz", "🎷", "jazz clássicos"), ("Clássica", "🎻", "música clássica melhores"),
           ("Metal", "🤘", "heavy metal clássicos"), ("Reggae", "🌴", "reggae clássicos"), ("Trilhas de games", "🎮", "trilha sonora jogos clássicos"),
           ("Anime", "🌸", "anime openings melhores"), ("Anos 80", "📼", "hits anos 80"), ("Anos 90", "💿", "hits anos 90"),
           ("Gospel", "🙏", "gospel louvor sucessos"), ("Infantil", "🧸", "músicas infantis")]
HUMORES = [("Treinar", "💪", "música para treinar academia energia"), ("Estudar", "📚", "música para estudar concentração"), ("Relaxar", "🧘", "música relaxante calma"),
           ("Dormir", "😴", "música para dormir suave"), ("Festa", "🎉", "músicas de festa animadas"), ("Trabalhar", "💻", "música para trabalhar foco"),
           ("Dirigir", "🚗", "música para viajar estrada"), ("Romântico", "💕", "músicas românticas"), ("Acordar", "🌅", "músicas para acordar animado"),
           ("Triste", "🌧️", "músicas tristes sofrência"), ("Jogar", "🕹️", "música para jogar gamer"), ("Cozinhar", "🍳", "música para cozinhar alegre")]
_slug = lambda s: re.sub(r"[^a-z0-9]+", "-", _norm(s)).strip("-")
_MIX = {_slug(n): (n, q) for n, _, q in ESTILOS + HUMORES}
_SINON = {"treino": "treinar", "academia": "treinar", "malhar": "treinar", "correr": "treinar", "estudo": "estudar", "concentrar": "estudar", "relax": "relaxar",
          "relaxante": "relaxar", "calma": "relaxar", "sono": "dormir", "balada": "festa", "trabalho": "trabalhar", "foco": "trabalhar", "viagem": "dirigir",
          "estrada": "dirigir", "romantica": "romantico", "romanticas": "romantico", "amor": "romantico", "games": "trilhas-de-games", "game": "trilhas-de-games",
          "gamer": "jogar", "hiphop": "rap-e-hip-hop", "rap": "rap-e-hip-hop", "samba": "pagode-e-samba", "pagode": "pagode-e-samba", "lofi": "lo-fi",
          "classica": "classica", "eletronica": "eletronica", "oitentas": "anos-80", "noventas": "anos-90", "sofrencia": "triste", "tristes": "triste"}
_cache_curtas = {}


def _achar_mix(consulta: str):
    """(nome, consulta de busca) se o pedido é um estilo ou humor conhecido; senão None."""
    toks = [t for t in _norm(consulta).split() if t not in _PARADAS]
    if not toks or len(toks) > 3:
        return None
    for chave in (_slug(" ".join(toks)), *[_SINON.get(t, t) for t in toks]):
        if chave in _MIX:
            return _MIX[chave]
    return None


def _buscar_curtas(consulta: str, n: int = 20):
    """Busca no YouTube só metadados, descartando transmissões ao vivo e vídeos longos (coletâneas de horas)."""
    ch = (consulta, n)
    if ch in _cache_curtas and _cache_curtas[ch][0] > time.time():
        return list(_cache_curtas[ch][1])
    import yt_dlp
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": True, "skip_download": True, "noplaylist": True}) as y:
        r = y.extract_info(f"ytsearch{n + (12 if n >= 10 else 4)}:{consulta}", download=False)
    todos = []
    for e in r.get("entries", []):
        if not e or not e.get("id") or len(e["id"]) != 11 or e.get("live_status") in ("is_live", "is_upcoming"):
            continue
        todos.append({"id": e["id"], "titulo": (e.get("title") or "")[:140], "canal": (e.get("channel") or e.get("uploader") or "")[:80],
                      "capa": f"https://i.ytimg.com/vi/{e['id']}/mqdefault.jpg", "duracao": int(e.get("duration") or 0)})
    out = [t for t in todos if 0 < t["duracao"] <= 900]                 # músicas de verdade: até 15 min
    if len(out) < min(n, 8):                                            # poucas? aceita também faixas até 45 min (coletâneas curtas)
        out += [t for t in todos if 900 < t["duracao"] <= 2700 and t not in out]
    out = out[:n]
    _cache_curtas[ch] = (time.time() + 6 * 3600, out)
    if len(_cache_curtas) > 120:
        _cache_curtas.pop(next(iter(_cache_curtas)))
    return list(out)


def _playlist_youtube(url: str, limite: int = 100):
    import yt_dlp
    with yt_dlp.YoutubeDL({"quiet": True, "extract_flat": "in_playlist", "skip_download": True, "playlistend": limite}) as y:
        r = y.extract_info(url, download=False)
    out = []
    for e in (r.get("entries") or []):
        if e and e.get("id") and len(e["id"]) == 11:
            out.append({"id": e["id"], "titulo": (e.get("title") or "")[:140], "canal": (e.get("channel") or e.get("uploader") or r.get("uploader") or "")[:80],
                        "capa": f"https://i.ytimg.com/vi/{e['id']}/mqdefault.jpg", "duracao": int(e.get("duration") or 0)})
    return (r.get("title") or "Playlist do YouTube")[:80], out


def _perfil_gosto(u: str):
    from collections import Counter
    idx = _indice()
    art = Counter(i["artista"] for i in idx.values())
    gen = Counter(i["genero"] for i in idx.values() if i.get("genero") and i["genero"] != "Sem gênero")
    curtidas = []
    try:
        d = json.loads(_arq_musica(u).read_text(encoding="utf-8-sig")) if _arq_musica(u).exists() else {}
        curtidas = [f"{t.get('canal', '')} - {t.get('titulo', '')}" for t in d.get("curtidas", [])[:15]]
    except Exception:
        pass
    return [a for a, _ in art.most_common(12)], [g for g, _ in gen.most_common(5)], curtidas


def recomendar(u: str, pedido: str, env: dict):
    """Uma seleção de ~10 músicas pelo gosto do usuário (a Alicia sugere, o servidor acha no YouTube). Sem chave: um mix aleatório."""
    from concurrent.futures import ThreadPoolExecutor
    artistas, generos, curtidas = _perfil_gosto(u)
    sugestoes = []
    if env.get("NVIDIA_API_KEY"):
        gosto = (f"Artistas que ele mais ouve: {', '.join(artistas) or 'ainda nenhum'}. Gêneros: {', '.join(generos) or 'variados'}. "
                 f"Músicas que curtiu: {'; '.join(curtidas) or 'nenhuma ainda'}. Pedido dele: {pedido or 'surpreenda-me, algo de que eu goste'}.")
        ok, resp = alicia_ponte.perguntar_hermes(
            env, "", "Você é uma curadora musical. Responda SOMENTE com JSON, sem texto antes ou depois: uma lista de 10 objetos "
            '{"artista": "...", "musica": "..."} com músicas REAIS e conhecidas, em português ou internacionais conforme o gosto, '
            "misturando algumas familiares com algumas descobertas. Não repita músicas que ele já tem.", gosto, 90)
        if ok:
            m = re.search(r"\[.*\]", resp, re.S)
            try:
                sugestoes = [s for s in json.loads(m.group(0)) if isinstance(s, dict) and s.get("musica")][:10] if m else []
            except ValueError:
                sugestoes = []
    faixas = []
    if sugestoes:
        def um(s):
            try:
                r = _buscar_curtas(f"{s.get('artista', '')} {s['musica']}", 3)
                return r[0] if r else None
            except Exception:
                return None
        with ThreadPoolExecutor(5) as ex:
            faixas = [t for t in ex.map(um, sugestoes) if t]
    if len(faixas) < 5:                                       # sem chave ou sem resultado: mix aleatório de um estilo do gosto dele
        nome = random.choice(generos) if generos else None
        mix = _achar_mix(nome) if nome else None
        faixas += _buscar_curtas((mix or random.choice(ESTILOS))[1] if mix else random.choice(ESTILOS)[2], 15)
    vistos, unicas = set(), []
    for t in faixas:
        if t["id"] not in vistos:
            vistos.add(t["id"]); unicas.append(t)
    return unicas[:12]


_cache_mix = {}


def _mix_curado(nome: str, consulta: str, env: dict):
    """Mix de ~14 músicas reais escolhidas pela Alicia para a categoria (cache de 24 h). Sem chave: busca simples."""
    from concurrent.futures import ThreadPoolExecutor
    if nome in _cache_mix and _cache_mix[nome][0] > time.time():
        return list(_cache_mix[nome][1])
    faixas = []
    if env.get("NVIDIA_API_KEY"):
        ok, resp = alicia_ponte.perguntar_hermes(
            env, "", "Você é uma curadora musical. Responda SOMENTE com JSON, sem texto antes ou depois: uma lista de 14 objetos "
            '{"artista": "...", "musica": "..."} com músicas REAIS e conhecidas para a categoria pedida, com artistas variados, '
            "em português e internacionais. Prefira as versões originais.", f"Categoria: {nome} ({consulta}).", 90)
        m = re.search(r"\[.*\]", resp, re.S) if ok else None
        try:
            sug = [s for s in json.loads(m.group(0)) if isinstance(s, dict) and s.get("musica")][:14] if m else []
        except ValueError:
            sug = []

        def um(s):
            try:
                r = _buscar_curtas(f"{s.get('artista', '')} {s['musica']}", 3)
                return r[0] if r else None
            except Exception:
                return None
        if sug:
            with ThreadPoolExecutor(5) as ex:
                faixas = [t for t in ex.map(um, sug) if t]
    if len(faixas) < 8:
        faixas += _buscar_curtas(consulta, 20)
    vistos, unicas = set(), []
    for t in faixas:
        if t["id"] not in vistos:
            vistos.add(t["id"]); unicas.append(t)
    _cache_mix[nome] = (time.time() + 24 * 3600, unicas[:16])
    return list(unicas[:16])


# fila para guardar músicas no servidor em segundo plano (uma por vez, devagar, para não pesar no notebook)
import queue as _queue
import threading as _threading
_fila_dl = _queue.Queue()
_dl = {"total": 0, "feitos": 0, "falhas": 0, "ativo": False}


def _worker_dl():
    while True:
        vid = _fila_dl.get()
        _dl["ativo"] = True
        try:
            _baixar_audio(vid)
            _dl["feitos"] += 1
        except Exception:
            _dl["falhas"] += 1
        if _fila_dl.empty():
            _dl["ativo"] = False
        time.sleep(1.0)


_threading.Thread(target=_worker_dl, daemon=True).start()


@app.get("/api/musica/descobrir")
async def musica_descobrir(request: Request):
    exigir_login(request)
    return {"estilos": [{"id": _slug(n), "nome": n, "emoji": e} for n, e, _ in ESTILOS],
            "humores": [{"id": _slug(n), "nome": n, "emoji": e} for n, e, _ in HUMORES]}


@app.get("/api/musica/mix")
async def musica_mix(request: Request, id: str):
    exigir_login(request)
    if id not in _MIX:
        raise HTTPException(404, "Mix não encontrado.")
    nome, consulta = _MIX[id]
    try:
        faixas = await asyncio.to_thread(_mix_curado, nome, consulta, ler_env())
    except Exception:
        raise HTTPException(502, "Não consegui montar esse mix agora. Tente de novo.")
    return {"titulo": nome, "faixas": faixas}


@app.get("/api/musica/playlist")
async def musica_playlist(request: Request, url: str):
    exigir_login(request)
    if not re.search(r"list=[\w-]+", url) or "youtu" not in url:
        raise HTTPException(400, "Cole o link de uma playlist do YouTube (precisa ter list=).")
    try:
        titulo, faixas = await asyncio.to_thread(_playlist_youtube, url)
    except Exception:
        raise HTTPException(502, "Não consegui ler essa playlist (ela pode ser privada).")
    return {"titulo": titulo, "faixas": faixas}


@app.post("/api/musica/recomendar")
async def musica_recomendar(request: Request):
    u = exigir_login(request)
    c = await request.json()
    try:
        faixas = await asyncio.to_thread(recomendar, u, str(c.get("pedido", ""))[:200], ler_env())
    except Exception:
        raise HTTPException(502, "Não consegui montar a seleção agora. Tente de novo.")
    registrar("MÚSICA", u, ip_de(request), "pediu recomendações de música", "ok" if faixas else "nada", "info")
    return {"titulo": "Seleção da Alicia para você", "faixas": faixas}


@app.post("/api/musica/guardar")
async def musica_guardar(request: Request):
    u = exigir_login(request)
    ids = [i for i in (await request.json()).get("ids", []) if isinstance(i, str) and re.fullmatch(r"[\w-]{11}", i)][:200]
    idx = _indice()
    novos = [i for i in dict.fromkeys(ids) if not (i in idx and (DADOS / idx[i]["arquivo"]).exists())]
    if not _dl["ativo"]:
        _dl.update(total=0, feitos=0, falhas=0)
    for i in novos:
        _fila_dl.put(i)
    _dl["total"] += len(novos)
    registrar("MÚSICA", u, ip_de(request), f"mandou guardar {len(novos)} músicas no servidor", "ok", "info")
    return {"enfileiradas": len(novos), "ja_guardadas": len(ids) - len(novos)}


@app.get("/api/musica/guardando")
async def musica_guardando(request: Request):
    exigir_login(request)
    return dict(_dl)

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
        n_ = _norm(texto)
        if _RECOMENDA.search(n_) and re.search(r"\b(musica|musicas|som|ouvir|escutar|banda|artista|cancao|tocar|playlist|algo novo|novidade)\b", n_):
            try:                                                # "me recomenda músicas": a Alicia monta uma seleção pelo gosto dele
                faixas, origem = await asyncio.to_thread(recomendar, u, texto, env), "recomenda"
            except Exception:
                faixas, origem = [], "erro"
            registrar("MÚSICA", u, ip_de(request), "a Alicia foi pedida para recomendar músicas", "ok" if faixas else "nada", "info")
            if not faixas:
                return {"texto": "Não consegui montar uma seleção agora. Tente de novo em instantes.", "expressao": "pensando", "faixas": []}
            consulta = ""
        else:
            consulta = extrair_consulta(texto)
            if consulta is None:
                return {"nao_e_musica": True}
            try:
                faixas, origem = await asyncio.to_thread(achar_musica, consulta)
            except Exception:
                faixas, origem = [], "erro"
        if origem != "recomenda":
            registrar("MÚSICA", u, ip_de(request), "a Alicia foi pedida para tocar música", "ok" if faixas else "nada", "info")
        if not faixas:
            return {"texto": "Não achei essa música. Quer tentar outro nome?", "expressao": "pensando", "faixas": []}
        t = faixas[0]
    padrao = f"Tocando {t['titulo']}" + (f", de {t['canal']}." if t.get("canal") and t["canal"].lower() not in t["titulo"].lower() else ".")
    if not c.get("so_resposta") and len(faixas) > 1:
        padrao = (f"Montei uma seleção de {len(faixas)} músicas pra você, começando por {t['titulo']}." if origem == "recomenda"
                  else f"{padrao[:-1]} e mais {len(faixas) - 1} na fila.")
    resposta, expressao = padrao, "feliz"
    if c.get("so_achar"):                    # 1ª etapa: devolve já a música (rápido) para o painel começar a tocar
        return {"texto": padrao, "expressao": expressao, "faixas": faixas, "origem": origem}
    if env.get("NVIDIA_API_KEY"):
        sistema = alicia_ponte.montar_sistema(u.capitalize(), str(c.get("personalidade", "normal")), bool(c.get("sem_filtro")), texto) + (
            f"\n\n[AÇÃO JÁ FEITA PELO SERVIDOR] A música já está tocando: \"{t['titulo']}\" ({t.get('canal', '')}). "
            "Responda em UMA frase curta, no seu jeito, avisando que colocou para tocar. Não invente nada além disso.")
        if c.get("modo") == "recomenda":
            aviso = (f"(O servidor montou uma seleção de {c.get('total', 'várias')} músicas pelo gosto do usuário e já começou a tocar \"{t['titulo']}\" de {t.get('canal', '')}. "
                     "Em uma frase curta e natural, no seu jeito, diga que preparou a seleção para ele, sem listar tudo.)")
        else:
            aviso = (f"(O servidor acabou de colocar a música \"{t['titulo']}\" de {t.get('canal', '')} para tocar, a pedido do usuário. "
                     "Responda em uma frase curta e natural, no seu jeito, confirmando que já está tocando.)")
        ok, resp = await asyncio.to_thread(alicia_ponte.perguntar_hermes, env, f"painel-{u}", sistema, aviso, 60)
        if ok and resp.strip():
            ex, fala = alicia_ponte.separar_expressao(resp)
            if not _NEGA.search(_norm(fala)):                       # se o modelo disser que "não tem essa função", usa a frase padrão
                expressao, resposta = ex, fala
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
    return out


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



















