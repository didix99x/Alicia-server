"""Ponte Alicia <-> Hermes.

A personalidade, as personalidades de tom e a camada "sem filtro" vêm do código original da Alicia
(alicia/alicia_core). O Hermes é o cérebro (memória, ferramentas, agenda) via API local.
"""
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

RAIZ = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(RAIZ / "alicia"))
from alicia_core.prompts import PromptEngine          # noqa: E402
from alicia_core.unfiltered import UnfilteredMode      # noqa: E402

EXPRESSOES = {"FELIZ": "feliz", "SERIO": "serio", "SURPRESA": "surpresa", "PENSANDO": "pensando", "BRAVO": "bravo"}
_cfg = SimpleNamespace(unf_sarcasm=4, unf_profanity=2, unf_fire_back=True, unf_custom_instructions="")
_sem_filtro = UnfilteredMode(_cfg)
DIAS = ["segunda", "terça", "quarta", "quinta", "sexta", "sábado", "domingo"]


def personalidades():
    return [{"id": k, "nome": v["label"], "desc": v["desc"]} for k, v in PromptEngine.PERSONALITIES.items()]


def separar_expressao(texto: str):
    """Tira a tag [FELIZ] etc. do início e devolve (expressao, texto limpo)."""
    m = re.match(r"\s*\[(\w+)\]\s*", texto)
    if m and m.group(1).upper() in EXPRESSOES:
        return EXPRESSOES[m.group(1).upper()], texto[m.end():].strip()
    return "feliz", texto.strip()


def montar_sistema(usuario: str, personalidade: str, sem_filtro: bool, ultima_fala: str) -> str:
    agora = datetime.now()
    extra = ""
    _sem_filtro.set_enabled(bool(sem_filtro))
    if sem_filtro:
        # Camada original da Alicia; se detectar sofrimento real do usuário, ela troca por acolhimento sozinha.
        extra = _sem_filtro.overlay("chat", ultima_fala).system
    return PromptEngine.chat_system_prompt(
        user_name=usuario, now_text=f"{DIAS[agora.weekday()]}, {agora:%d/%m/%Y %H:%M}",
        memories=[], recalled=[], personality=personalidade, extra_layer=extra)


def perguntar_hermes(env: dict, sessao: str, sistema: str, texto: str, timeout=180):
    """Envia a mensagem ao gateway do Hermes. Devolve (ok, texto_ou_erro)."""
    url = f"http://127.0.0.1:{env.get('API_SERVER_PORT', '8642')}/v1/chat/completions"
    corpo = json.dumps({"model": "hermes-agent", "messages": [
        {"role": "system", "content": sistema}, {"role": "user", "content": texto}]}).encode("utf-8")
    cab = {"Content-Type": "application/json", "Authorization": f"Bearer {env.get('API_SERVER_KEY', '')}"}
    if sessao:                       # sem sessão = chamada avulsa (o RPG manda o próprio resumo da história)
        cab["X-Hermes-Session-Id"] = sessao
    req = urllib.request.Request(url, data=corpo, headers=cab)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return True, json.loads(r.read())["choices"][0]["message"]["content"]
    except urllib.error.HTTPError as e:
        return False, f"O cérebro respondeu com erro {e.code}. Veja se a chave da NVIDIA está certa."
    except Exception:
        return False, "Não consegui falar com o cérebro (Hermes). Ele pode estar iniciando; tente de novo em um minuto."


# ---------- Voz da Alicia (a mesma voz neural feminina do projeto original: Francisca, pt-BR) ----------
VOZ = "pt-BR-FranciscaNeural"
PROSODIA = {"feliz": (6, 4, 0), "serio": (0, 0, 0), "surpresa": (10, 8, 5), "pensando": (-8, -2, -3), "bravo": (8, -3, 8)}   # ritmo %, tom Hz, volume %
_EMOJI = re.compile("[\U00010000-\U0010ffff\u2600-\u27bf\ufe0f]")


def preparar_fala(texto: str) -> str:
    """O que de fato deve ser falado: sem tags, emojis, markdown nem links; pausas mais naturais."""
    t = re.sub(r"\[[^\]]*\]", "", texto or "")
    t = re.sub(r"\*[^*]*\*", "", t).replace("*", "")
    t = re.sub(r"```.*?```", " ", t, flags=re.DOTALL).replace("`", "").replace("_", " ")
    t = re.sub(r"https?://\S+", "link", t)
    t = _EMOJI.sub("", t)
    t = re.sub(r"\s*[—–]\s*", ", ", t)
    t = re.sub(r"([!?])\1+", r"\1", t)
    t = re.sub(r"\.{4,}", "...", t)
    return re.sub(r"\s+", " ", t).strip()


async def gerar_voz(texto: str, expressao: str = "feliz") -> bytes:
    import edge_tts
    import random
    r, p, v = PROSODIA.get(expressao, (0, 0, 0))
    r += random.choice((-2, -1, 0, 1, 2)); p += random.choice((-1, 0, 1))      # pequena variação para nunca soar igual
    com = edge_tts.Communicate(texto, VOZ, rate=f"{r:+d}%", pitch=f"{p:+d}Hz", volume=f"{v:+d}%")
    dados = b""
    async for pedaco in com.stream():
        if pedaco["type"] == "audio":
            dados += pedaco["data"]
    if not dados:
        raise RuntimeError("sem áudio")
    return dados