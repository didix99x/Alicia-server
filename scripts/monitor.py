"""Monitor de acessos do Alicia Server (terminal).

Mostra ao vivo o que está em logs/acessos.log, com cabeçalho de resumo.
Teclas: 1 painel  2 arquivos  3 login  4 nvidia  s só segurança  e só erros
        t tudo  p pausar/continuar  q sair
"""
import json
import msvcrt
import os
import time
from pathlib import Path

import psutil

LOG = Path(__file__).resolve().parents[1] / "logs" / "acessos.log"
COR = {"seguranca": "\033[1;91m", "erro": "\033[33m", "aviso": "\033[93m", "ok": "\033[92m", "info": "\033[37m"}
SERV = {"PAINEL": "\033[96m", "LOGIN": "\033[95m", "ARQUIVOS": "\033[94m", "NVIDIA": "\033[92m", "SISTEMA": "\033[90m"}
RESET = "\033[0m"
FILTROS = {"1": "PAINEL", "2": "ARQUIVOS", "3": "LOGIN", "4": "NVIDIA"}
os.system("")  # liga cores ANSI no console do Windows


def cabecalho(filtro, pausado):
    cpu, ram = psutil.cpu_percent(), psutil.virtual_memory().percent
    return (f"\033[7m ALICIA SERVER  CPU {cpu:.0f}%  RAM {ram:.0f}%  filtro: {filtro or 'tudo'}"
            f"{'  [PAUSADO]' if pausado else ''} \033[0m\n"
            "teclas: 1 painel 2 arquivos 3 login 4 nvidia | s segurança  e erros  t tudo  p pausar  q sair")


def passa(l, filtro):
    if not filtro:
        return True
    if filtro == "seguranca":
        return l["tipo"] == "seguranca"
    if filtro == "erro":
        return l["tipo"] in ("erro", "seguranca")
    return l["servico"] == filtro


def imprimir(l):
    print(f"{COR.get(l['tipo'], '')}{l['t']} {SERV.get(l['servico'], '')}{l['servico']:<9}{COR.get(l['tipo'], '')} "
          f"{l['quem']} ({l['ip']}) {l['o_que']} {l['resultado']}{RESET}")


def main():
    filtro, pausado, pos, ultimo_cab = None, False, 0, 0
    os.system("cls")
    print(cabecalho(filtro, pausado))
    while not LOG.exists():
        time.sleep(1)
    pos = max(0, LOG.stat().st_size - 4000)  # começa mostrando as últimas linhas
    while True:
        while msvcrt.kbhit():
            k = msvcrt.getwch().lower()
            if k == "q":
                return
            if k == "p":
                pausado = not pausado
            elif k in FILTROS:
                filtro = FILTROS[k]
            elif k == "s":
                filtro = "seguranca"
            elif k == "e":
                filtro = "erro"
            elif k == "t":
                filtro = None
            print(cabecalho(filtro, pausado))
        if LOG.stat().st_size < pos:
            pos = 0  # o arquivo girou (rotação)
        if not pausado and LOG.stat().st_size > pos:
            with open(LOG, encoding="utf-8") as f:
                f.seek(pos)
                for linha in f.read().splitlines():
                    try:
                        l = json.loads(linha)
                    except ValueError:
                        continue
                    if passa(l, filtro):
                        imprimir(l)
                pos = f.tell()
        time.sleep(0.5)


if __name__ == "__main__":
    main()
