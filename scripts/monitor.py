"""Monitor do Alicia Server (terminal do notebook).

Mostra ao vivo TUDO que as pessoas fazem no servidor: quem entrou, que página abriu,
qual jogo abriu e por quanto tempo jogou, qual filme está assistindo, que música ouve,
conversas com a Alicia, RPG, arquivos, alertas de segurança e erros.
(Senhas, chaves e o conteúdo de conversas nunca aparecem.)

Teclas:  a atividade (padrão)   j jogos   f filmes   m música   l alicia   r rpg   o arquivos
         g login   s segurança  e erros   h tudo, com cada requisição HTTP   p pausar   q sair
"""
import json
import msvcrt
import os
import shutil
import time
from collections import deque
from pathlib import Path

import psutil

LOG = Path(__file__).resolve().parents[1] / "logs" / "acessos.log"
RESET = "\033[0m"
COR = {"seguranca": "\033[1;91m", "erro": "\033[91m", "aviso": "\033[93m", "ok": "\033[92m", "info": "\033[37m"}
# serviço -> (ícone, cor, nome mostrado)
SERV = {
    "JOGOS": ("","\033[1;95m", "JOGO"), "FILME": ("","\033[1;96m", "FILME"), "JELLYFIN": ("","\033[1;96m", "FILME"),
    "MÚSICA": ("","\033[1;92m", "MÚSICA"), "ALICIA": ("","\033[1;94m", "ALICIA"), "RPG": ("","\033[1;93m", "RPG"),
    "ARQUIVOS": ("","\033[1;33m", "ARQUIVO"), "LOGIN": ("","\033[1;97m", "LOGIN"), "PÁGINA": ("","\033[36m", "PÁGINA"),
    "SEGURANÇA": ("","\033[1;91m", "SEGUR."), "NVIDIA": ("","\033[32m", "IA"), "SISTEMA": ("","\033[90m", "SISTEMA"),
    "PAINEL": ("","\033[90m", "HTTP"),
}
FILTROS = {  # tecla -> (nome, função)
    "a": ("atividade", lambda l: not (l["servico"] == "PAINEL" and l["tipo"] == "ok")),
    "j": ("jogos", lambda l: l["servico"] == "JOGOS"),
    "f": ("filmes", lambda l: l["servico"] in ("FILME", "JELLYFIN")),
    "m": ("música", lambda l: l["servico"] == "MÚSICA"),
    "l": ("alicia", lambda l: l["servico"] == "ALICIA"),
    "r": ("rpg", lambda l: l["servico"] == "RPG"),
    "o": ("arquivos", lambda l: l["servico"] == "ARQUIVOS"),
    "g": ("login", lambda l: l["servico"] == "LOGIN"),
    "s": ("segurança", lambda l: l["tipo"] == "seguranca"),
    "e": ("erros", lambda l: l["tipo"] in ("erro", "seguranca")),
    "h": ("tudo (com HTTP)", lambda l: True),
}
os.system("")  # liga cores ANSI no console do Windows


def estado_agora(recentes):
    """Quem está ativo (últimos 5 min) e o que cada um está jogando, assistindo ou ouvindo."""
    agora, ativos, jogando, vendo, ouvindo = time.time(), {}, {}, {}, {}
    for l in recentes:
        q, idade, o = l.get("quem", "-"), agora - l.get("ts", 0), l["o_que"]
        if q in ("-", ""):
            continue
        if idade <= 300:
            ativos[q] = l["ip"]
        if idade > 14400:
            continue
        if l["servico"] == "JOGOS":
            if o.startswith("ABRIU"):
                jogando[q] = o.split("'")[1] if "'" in o else "?"
            elif o.startswith("FECHOU"):
                jogando.pop(q, None)
        elif l["servico"] in ("FILME", "JELLYFIN"):
            if "COMEÇOU" in o or "começou" in o:
                vendo[q] = o.split("'")[1] if "'" in o else "?"
            elif "PAROU" in o:
                vendo.pop(q, None)
        elif l["servico"] == "MÚSICA" and o.startswith("tocando") and idade <= 600:
            ouvindo[q] = o[9:]
    return ativos, jogando, vendo, ouvindo

def cabecalho(nome_filtro, pausado, recentes):
    cpu, ram = psutil.cpu_percent(), psutil.virtual_memory().percent
    ativos, jogando, vendo, ouvindo = estado_agora(recentes)
    larg = shutil.get_terminal_size((100, 30)).columns
    l1 = f"\033[7m ALICIA SERVER   CPU {cpu:.0f}%   RAM {ram:.0f}%   vendo: {nome_filtro}{'   [PAUSADO]' if pausado else ''} \033[0m"
    quem = ", ".join(f"{q}" for q in ativos) or "ninguém agora"
    l2 = f"online agora: {quem}"
    ex = []
    if jogando:
        ex.append("jogando: " + ", ".join(f"{q} ({j})" for q, j in jogando.items()))
    if vendo:
        ex.append("assistindo: " + ", ".join(f"{q} ({j})" for q, j in vendo.items()))
    if ouvindo:
        ex.append("ouvindo: " + ", ".join(f"{q} ({m})" for q, m in ouvindo.items()))
    teclas = "a atividade  j jogos  f filmes  m música  l alicia  r rpg  o arquivos  g login  s segurança  e erros  h tudo  p pausar  q sair"
    return "\n".join([l1, l2] + ex + [f"\033[90m{teclas[:larg - 1]}\033[0m", "\033[90m" + "─" * min(larg - 1, 110) + RESET])


def imprimir(l):
    ic, cor, nome = SERV.get(l["servico"], ("","\033[37m", l["servico"]))
    tipo = COR.get(l["tipo"], "")
    quem = l["quem"] if l["quem"] not in ("-", "") else "sistema"
    ip = f" ({l['ip']})" if l["ip"] not in ("-", "") else ""
    res = "" if l["resultado"] in ("ok", "") else f"  → {l['resultado']}"
    print(f"\033[90m{l['t'][6:]}{RESET} {cor}{nome:<8}{RESET} \033[1m{quem}{RESET}\033[90m{ip}{RESET}  {tipo}{l['o_que']}{res}{RESET}")


def ler_linhas(pos):
    with open(LOG, encoding="utf-8") as f:
        f.seek(pos)
        brutas = f.read().splitlines()
        novo = f.tell()
    out = []
    for b in brutas:
        try:
            out.append(json.loads(b))
        except ValueError:
            pass
    return out, novo


def redesenha(nome_filtro, passa, pausado, recentes, historico):
    os.system("cls")
    print(cabecalho(nome_filtro, pausado, recentes))
    for l in [x for x in historico if passa(x)][-30:]:
        imprimir(l)


def main():
    nome, passa, pausado = FILTROS["a"][0], FILTROS["a"][1], False
    while not LOG.exists():
        time.sleep(1)
    historico = deque(maxlen=3000)
    pos = max(0, LOG.stat().st_size - 600_000)      # carrega o passado recente para mostrar o estado e as últimas linhas
    antigos, pos = ler_linhas(pos)
    historico.extend(antigos[1:] if pos and len(antigos) > 1 else antigos)
    redesenha(nome, passa, pausado, historico, historico)
    ult_cab = time.time()
    while True:
        mudou = False
        while msvcrt.kbhit():
            k = msvcrt.getwch().lower()
            if k == "q":
                return
            if k == "p":
                pausado = not pausado
                mudou = True
            elif k in FILTROS:
                nome, passa = FILTROS[k]
                mudou = True
        if LOG.stat().st_size < pos:
            pos = 0  # o arquivo girou (rotação)
        novas = []
        if LOG.stat().st_size > pos and not pausado:
            novas, pos = ler_linhas(pos)
            historico.extend(novas)
        if mudou:
            redesenha(nome, passa, pausado, historico, historico)
            ult_cab = time.time()
        else:
            for l in novas:
                if passa(l):
                    imprimir(l)
            if novas and time.time() - ult_cab > 60:      # a cada minuto atualiza o painel de cima com quem está jogando/assistindo
                redesenha(nome, passa, pausado, historico, historico)
                ult_cab = time.time()
        time.sleep(0.4)


if __name__ == "__main__":
    main()
