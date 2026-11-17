"""Modo Servidor do Alicia Server (terminal de controle do notebook).

Liga e desliga um modo em que o notebook só cuida do essencial para o servidor rodar:
  - plano de energia próprio: nunca dorme, tampa fechada não faz nada, disco sempre ligado, a TELA NUNCA APAGA;
  - painel, Hermes, Jellyfin, Tailscale, SSH e monitor passam a ter prioridade;
  - os outros programas abertos ficam com prioridade baixa (nada é fechado sem você pedir);
  - serviços do Windows dispensáveis (indexação, atualização, impressão, Xbox, telemetria…) são pausados.
O "desligar" devolve tudo exatamente como estava.

Só funciona NO PRÓPRIO NOTEBOOK (sessão local): é recusado por SSH, área de trabalho remota ou qualquer
acesso de outro aparelho. Não existe botão nem rota para isso no painel de propósito.

Uso:  python modo_servidor.py            (terminal interativo: ligar, desligar, status, apps, admin, ajuda)
      python modo_servidor.py ligar|desligar|status
"""
import ctypes
import json
import os
import re
import socket
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import psutil

RAIZ = Path(__file__).resolve().parents[1]
ESTADO = RAIZ / "dados" / "modo_servidor.json"
LOG = RAIZ / "logs" / "acessos.log"
os.system("")  # cores ANSI no console do Windows
for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8")
    except Exception:
        pass

V, A, R, C, N, D = "\033[92m", "\033[93m", "\033[91m", "\033[96m", "\033[1m", "\033[90m"
FIM = "\033[0m"

SERVICOS_PAUSAR = ["SysMain", "WSearch", "DiagTrack", "wuauserv", "Spooler", "XblAuthManager", "XblGameSave", "XboxNetApiSvc",
                   "MapsBroker", "WerSvc", "TabletInputService", "lfsvc", "RetailDemo", "Fax"]
ESSENCIAIS_CMD = ("uvicorn", "hermes", "monitor.py", "modo_servidor.py", "jellyfin")
ESSENCIAIS_NOME = {"jellyfin.exe", "ffmpeg.exe", "tailscaled.exe", "tailscale-ipn.exe", "tailscale.exe", "sshd.exe", "robocopy.exe", "emulatorjs"}
# nunca mexer na prioridade destes (sistema, terminais e ferramentas de desenvolvimento)
PROTEGIDOS = {"system", "system idle process", "registry", "smss.exe", "csrss.exe", "wininit.exe", "winlogon.exe", "services.exe", "lsass.exe", "svchost.exe",
              "dwm.exe", "explorer.exe", "fontdrvhost.exe", "conhost.exe", "cmd.exe", "powershell.exe", "pwsh.exe", "windowsterminal.exe", "wscript.exe",
              "python.exe", "pythonw.exe", "node.exe", "claude.exe", "claude", "code.exe", "sihost.exe", "taskhostw.exe", "ctfmon.exe", "searchhost.exe",
              "startmenuexperiencehost.exe", "shellexperiencehost.exe", "textinputhost.exe", "runtimebroker.exe", "securityhealthsystray.exe"}
APPS_FECHAR = ["chrome.exe", "msedge.exe", "firefox.exe", "brave.exe", "opera.exe", "spotify.exe", "discord.exe", "steam.exe", "steamwebhelper.exe",
               "onedrive.exe", "teams.exe", "ms-teams.exe", "telegram.exe", "whatsapp.exe", "skype.exe", "epicgameslauncher.exe"]
PORTAS = [("Painel", 8080), ("Hermes (Alicia)", 8642), ("Jellyfin (filmes)", 8096)]
SERVICOS_ESSENCIAIS = [("Tailscale (rede privada)", "Tailscale"), ("SSH", "sshd"), ("Jellyfin", "JellyfinServer")]


def agora():
    return datetime.now().strftime("%d/%m %H:%M:%S")


def log(o_que, tipo="aviso"):
    """Escreve no mesmo registro do painel, para aparecer no monitor."""
    try:
        linha = {"t": agora(), "ts": time.time(), "servico": "SISTEMA", "quem": "notebook", "ip": "local", "o_que": o_que, "resultado": "ok", "tipo": tipo}
        with open(LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(linha, ensure_ascii=False) + "\n")
    except Exception:
        pass


def eh_admin():
    try:
        return bool(ctypes.windll.shell32.IsUserAnAdmin())
    except Exception:
        return False


def so_no_notebook():
    """Recusa qualquer acesso que não seja o teclado e a tela do próprio notebook. Devolve o motivo da recusa ou None."""
    if os.environ.get("SSH_CONNECTION") or os.environ.get("SSH_CLIENT") or os.environ.get("SSH_TTY"):
        return "acesso por SSH"
    if os.environ.get("SESSIONNAME", "Console").upper().startswith("RDP"):
        return "área de trabalho remota"
    try:
        sid = ctypes.c_ulong()
        ctypes.windll.kernel32.ProcessIdToSessionId(os.getpid(), ctypes.byref(sid))
        if sid.value != ctypes.windll.kernel32.WTSGetActiveConsoleSessionId():
            return "sessão que não é a do console do notebook"
    except Exception:
        pass
    try:
        p = psutil.Process()
        while p:
            if p.name().lower() in ("sshd.exe", "sshd-session.exe", "mstsc.exe", "rdpclip.exe"):
                return "acesso remoto"
            p = p.parent()
    except Exception:
        pass
    return None


def ler_estado():
    try:
        return json.loads(ESTADO.read_text(encoding="utf-8-sig"))
    except Exception:
        return {}


def gravar_estado(e):
    ESTADO.parent.mkdir(exist_ok=True)
    ESTADO.write_text(json.dumps(e, ensure_ascii=False, indent=1), encoding="utf-8")


def sh(*a, **k):
    return subprocess.run(list(a), capture_output=True, text=True, encoding="utf-8", errors="ignore", **k)


def guid_ativo():
    m = re.search(r"([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})", sh("powercfg", "/getactivescheme").stdout)
    return m.group(1) if m else None


# ---------------- energia ----------------
def energia_ligar():
    antigo = guid_ativo()
    novo = None
    for base in ("8c5e7fda-e8bf-4a96-9a85-a6e23a8c635c", antigo):      # tenta partir de "Alto desempenho"; senão, do plano atual
        if not base:
            continue
        m = re.search(r"([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12})", sh("powercfg", "/duplicatescheme", base).stdout)
        if m:
            novo = m.group(1)
            break
    if not novo:
        return antigo, None
    sh("powercfg", "/changename", novo, "Alicia Servidor", "Modo servidor do Alicia Server (apague com 'desligar')")
    sh("powercfg", "/setactive", novo)
    for p in ("standby-timeout-ac", "standby-timeout-dc", "hibernate-timeout-ac", "hibernate-timeout-dc", "disk-timeout-ac", "disk-timeout-dc"):
        sh("powercfg", "/change", p, "0")
    sh("powercfg", "/change", "monitor-timeout-ac", "0")                                  # a tela nunca apaga
    sh("powercfg", "/change", "monitor-timeout-dc", "0")
    for modo in ("/setacvalueindex", "/setdcvalueindex"):
        sh("powercfg", modo, novo, "SUB_BUTTONS", "LIDACTION", "0")                       # tampa fechada: nada
        sh("powercfg", modo, novo, "SUB_PROCESSOR", "PROCTHROTTLEMIN", "20")
        sh("powercfg", modo, novo, "SUB_PROCESSOR", "PROCTHROTTLEMAX", "100")
        sh("powercfg", modo, novo, "2a737441-1930-4402-8d77-b2bebba308a3", "48e6b7a6-50f5-4782-a5d4-53bb8f07e226", "0")   # USB nunca dorme
    sh("powercfg", "/setactive", novo)
    return antigo, novo


def energia_desligar(e):
    if e.get("energia_anterior"):
        sh("powercfg", "/setactive", e["energia_anterior"])
    if e.get("energia_nova"):
        sh("powercfg", "/delete", e["energia_nova"])


# ---------------- prioridades ----------------
def eh_essencial(p):
    try:
        nome = (p.name() or "").lower()
        if nome in ESSENCIAIS_NOME:
            return True
        if nome.startswith("python") or nome == "node.exe" or nome in ("cmd.exe", "wscript.exe"):
            cmd = " ".join(p.cmdline()).lower()
            return any(x in cmd for x in ESSENCIAIS_CMD) or "emulatorjs" in cmd
    except Exception:
        pass
    return False


def prioridades_ligar():
    eu = psutil.Process().username()
    subiu, desceu = 0, []
    for p in psutil.process_iter(["name", "username", "nice", "create_time"]):
        try:
            if p.info["username"] != eu:
                continue
            if eh_essencial(p):
                if p.nice() == psutil.NORMAL_PRIORITY_CLASS:
                    p.nice(psutil.ABOVE_NORMAL_PRIORITY_CLASS)
                    subiu += 1
            elif (p.info["name"] or "").lower() not in PROTEGIDOS and p.pid != os.getpid() and p.nice() == psutil.NORMAL_PRIORITY_CLASS:
                p.nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
                desceu.append([p.pid, p.info["create_time"]])
        except (psutil.Error, OSError):
            pass
    return subiu, desceu


def prioridades_desligar(e):
    n = 0
    for pid, criado in e.get("baixados", []):
        try:
            p = psutil.Process(pid)
            if abs(p.create_time() - criado) < 1:
                p.nice(psutil.NORMAL_PRIORITY_CLASS)
                n += 1
        except (psutil.Error, OSError):
            pass
    for p in psutil.process_iter(["name"]):                       # os essenciais também voltam ao normal
        try:
            if eh_essencial(p) and p.nice() == psutil.ABOVE_NORMAL_PRIORITY_CLASS:
                p.nice(psutil.NORMAL_PRIORITY_CLASS)
        except (psutil.Error, OSError):
            pass
    return n


# ---------------- serviços do Windows ----------------
def servico_rodando(nome):
    try:
        return psutil.win_service_get(nome).status() == "running"
    except Exception:
        return False


def servicos_pausar():
    parados = []
    for nome in SERVICOS_PAUSAR:
        if servico_rodando(nome):
            sh("net", "stop", nome, "/y")
            if not servico_rodando(nome):
                parados.append(nome)
    return parados


def servicos_voltar(nomes):
    voltou = []
    for nome in nomes:
        sh("net", "start", nome)
        if servico_rodando(nome):
            voltou.append(nome)
    return voltou


# ---------------- essenciais ----------------
def porta_ok(porta):
    with socket.socket() as s:
        s.settimeout(0.6)
        return s.connect_ex(("127.0.0.1", porta)) == 0


def garantir_essenciais():
    """Confere (e liga, se estiver parado) painel, Hermes, Jellyfin, Tailscale e SSH. Devolve linhas para mostrar."""
    linhas = []
    for nome, porta in PORTAS:
        ok = porta_ok(porta)
        if not ok and porta in (8080, 8642):
            sh("schtasks", "/run", "/tn", "AliciaServer-Painel" if porta == 8080 else "AliciaServer-Hermes")
            time.sleep(6)
            ok = porta_ok(porta)
        linhas.append((nome, ok))
    for nome, svc in SERVICOS_ESSENCIAIS:
        existe = True
        try:
            psutil.win_service_get(svc)
        except Exception:
            existe = False
        if not existe:
            continue
        ok = servico_rodando(svc)
        if not ok and eh_admin():
            sh("net", "start", svc)
            ok = servico_rodando(svc)
        linhas.append((nome, ok))
    return linhas


# ---------------- comandos ----------------
def mostra_essenciais(linhas):
    for nome, ok in linhas:
        print(f"   {V + '●' if ok else R + '○'}{FIM} {nome:<26}{'funcionando' if ok else R + 'PARADO' + FIM}")


def cmd_ligar(args):
    e = ler_estado()
    if e.get("ligado"):
        print(f"{A}O modo servidor já está ligado desde {e.get('desde_txt')}.{FIM} Use 'status' para ver ou 'desligar' para voltar ao normal.")
        return
    print(f"{N}Ligando o modo servidor…{FIM}")
    antigo, novo = energia_ligar()
    print(f" {V}✓{FIM} Energia: nunca dorme, tampa fechada não faz nada, disco sempre ligado, a tela nunca apaga." if novo else f" {R}✗{FIM} Não consegui criar o plano de energia.")
    subiu, baixados = prioridades_ligar()
    print(f" {V}✓{FIM} Prioridade: {subiu} processo(s) do servidor acelerado(s); {len(baixados)} outro(s) programa(s) em prioridade baixa.")
    parados = []
    if eh_admin():
        parados = servicos_pausar()
        print(f" {V}✓{FIM} Windows: {len(parados)} serviço(s) dispensável(is) pausado(s)" + (f" ({', '.join(parados)})." if parados else "."))
    else:
        print(f" {A}!{FIM} Serviços do Windows NÃO foram pausados: falta permissão de administrador. Digite {N}admin{FIM} para reabrir este terminal com permissão e ligue de novo.")
    print(f" {C}Conferindo o essencial:{FIM}")
    mostra_essenciais(garantir_essenciais())
    gravar_estado({"ligado": True, "desde": time.time(), "desde_txt": agora(), "boot": psutil.boot_time(), "energia_anterior": antigo, "energia_nova": novo,
                   "servicos": parados, "baixados": baixados})
    log(f"MODO SERVIDOR LIGADO no notebook ({len(baixados)} programas em prioridade baixa, {len(parados)} serviços do Windows pausados)")
    if "apps" not in args and "--apps" not in args:
        print(f"\n{D}Dica: 'apps' lista navegadores e programas abertos que você pode fechar para liberar mais memória.{FIM}")
    if "apps" in args or "--apps" in args:
        cmd_apps([])


def cmd_desligar(_args):
    e = ler_estado()
    if not e.get("ligado"):
        print(f"{A}O modo servidor já está desligado.{FIM}")
        return
    print(f"{N}Desligando o modo servidor e devolvendo tudo ao normal…{FIM}")
    energia_desligar(e)
    print(f" {V}✓{FIM} Energia: plano anterior de volta.")
    n = prioridades_desligar(e)
    print(f" {V}✓{FIM} Prioridade: {n} programa(s) voltaram ao normal.")
    if e.get("servicos"):
        if eh_admin():
            v = servicos_voltar(e["servicos"])
            print(f" {V}✓{FIM} Windows: {len(v)} serviço(s) religado(s) ({', '.join(v)}).")
        else:
            print(f" {A}!{FIM} Sem permissão de administrador para religar: {', '.join(e['servicos'])}. Digite 'admin' e rode 'desligar' de novo (ou reinicie o notebook).")
            e["ligado"] = False
            e["servicos_pendentes"] = e["servicos"]
            gravar_estado(e)
            log("modo servidor desligado (serviços do Windows ainda pausados: faltou administrador)")
            return
    try:
        ESTADO.unlink()
    except OSError:
        pass
    log("MODO SERVIDOR DESLIGADO (tudo voltou ao normal)")
    print(f"\n{V}Pronto.{FIM} O notebook voltou ao modo normal.")


def cmd_status(_args):
    e = ler_estado()
    ligado = e.get("ligado")
    print(f" Modo servidor: {V + N + 'LIGADO' if ligado else A + 'desligado'}{FIM}" + (f" desde {e.get('desde_txt')}" if ligado else ""))
    if ligado and psutil.boot_time() > e.get("boot", 0) + 5:
        print(f" {A}!{FIM} O notebook reiniciou depois que o modo foi ligado: prioridades e serviços já voltaram ao normal. Digite 'ligar' de novo para reaplicar (ou 'desligar' para limpar).")
        e["ligado"] = False
        gravar_estado(e)
    vm = psutil.virtual_memory()
    print(f" CPU {psutil.cpu_percent(interval=0.6):.0f}%   RAM {vm.percent:.0f}% usada ({vm.available / 2**30:.1f} GB livres)   Disco {psutil.disk_usage('C:/').percent:.0f}%")
    print(f" Energia: {sh('powercfg', '/getactivescheme').stdout.split('(')[-1].strip(' )\r\n')}")
    if e.get("servicos_pendentes"):
        print(f" {A}!{FIM} Serviços ainda pausados: {', '.join(e['servicos_pendentes'])}")
    print(f" {C}Essencial:{FIM}")
    mostra_essenciais([(n, porta_ok(p)) for n, p in PORTAS] + [(n, servico_rodando(s)) for n, s in SERVICOS_ESSENCIAIS if _existe(s)])
    gordos = []
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            if not eh_essencial(p) and (p.info["name"] or "").lower() not in PROTEGIDOS:
                gordos.append((p.info["memory_info"].rss, p.info["name"]))
        except (psutil.Error, OSError):
            pass
    gordos.sort(reverse=True)
    agrup = {}
    for m, n in gordos:
        agrup[n] = agrup.get(n, 0) + m
    top = sorted(agrup.items(), key=lambda x: -x[1])[:5]
    if top:
        print(f" {D}Quem mais usa memória fora do servidor: " + ", ".join(f"{n} {m / 2**20:.0f} MB" for n, m in top) + FIM)
    print(f" Administrador: {'sim' if eh_admin() else 'não (digite admin para pausar serviços do Windows)'}")


def _existe(svc):
    try:
        psutil.win_service_get(svc)
        return True
    except Exception:
        return False


def cmd_apps(_args):
    achados = {}
    for p in psutil.process_iter(["name", "memory_info"]):
        try:
            n = (p.info["name"] or "").lower()
            if n in APPS_FECHAR:
                achados.setdefault(n, [0, []])
                achados[n][0] += p.info["memory_info"].rss
                achados[n][1].append(p)
        except (psutil.Error, OSError):
            pass
    if not achados:
        print(f" {V}Nenhum navegador ou aplicativo comum aberto.{FIM}")
        return
    print(" Abertos agora (fechar libera memória, mas o que não foi salvo nele se perde):")
    for n, (m, ps) in achados.items():
        print(f"   • {n:<22} {m / 2**20:>6.0f} MB  ({len(ps)} processo(s))")
    if input(f" {A}Fechar todos esses?{FIM} (s/N) ").strip().lower() not in ("s", "sim", "y"):
        print(" Nada foi fechado.")
        return
    fechados = []
    for n, (_, ps) in achados.items():
        for p in ps:
            try:
                p.terminate()
            except (psutil.Error, OSError):
                pass
        fechados.append(n)
    log(f"modo servidor: fechou aplicativos a pedido ({', '.join(fechados)})")
    print(f" {V}✓{FIM} Fechados: {', '.join(fechados)}")


def cmd_admin(_args):
    if eh_admin():
        print(" Este terminal já está como administrador.")
        return
    arq = Path(__file__).resolve()
    py = Path(sys.executable)
    r = ctypes.windll.shell32.ShellExecuteW(None, "runas", "cmd.exe", f'/k chcp 65001 >nul & title ALICIA - MODO SERVIDOR (administrador) & "{py}" "{arq}"', None, 1)
    if r > 32:
        print(" Abrindo uma nova janela como administrador… esta pode ser fechada.")
    else:
        print(f" {A}Você recusou o pedido de administrador.{FIM}")


def cmd_ajuda(_args):
    print(f"""
 {N}Comandos do terminal de controle{FIM}  (vale só neste notebook)
   {V}ligar{FIM}       liga o modo servidor (a tela do notebook nunca apaga)
   {V}desligar{FIM}    volta tudo ao normal
   {V}status{FIM}      mostra se está ligado, uso do notebook e o que está funcionando
   {V}apps{FIM}        lista navegadores/programas abertos e pergunta se quer fechar
   {V}admin{FIM}       reabre este terminal como administrador (necessário para pausar serviços do Windows)
   {V}limpar{FIM}      limpa a tela        {V}sair{FIM}   fecha o terminal (o modo continua como está)
""")


COMANDOS = {"ligar": cmd_ligar, "ativar": cmd_ligar, "on": cmd_ligar, "desligar": cmd_desligar, "desativar": cmd_desligar, "off": cmd_desligar,
            "status": cmd_status, "estado": cmd_status, "apps": cmd_apps, "admin": cmd_admin, "ajuda": cmd_ajuda, "help": cmd_ajuda, "?": cmd_ajuda}


def executa(linha):
    pal = [p for p in linha.lower().replace("-", " ").split() if p not in ("modo", "servidor")]
    if not pal:
        return True
    c, args = pal[0], pal[1:]
    if c in ("sair", "exit", "quit"):
        return False
    if c in ("limpar", "cls", "clear"):
        os.system("cls")
        banner()
        return True
    if c not in COMANDOS:
        print(f" {R}Não conheço '{c}'.{FIM} Digite {N}ajuda{FIM}.")
        return True
    try:
        COMANDOS[c](args)
    except (EOFError, KeyboardInterrupt):
        print()
    except Exception as ex:
        print(f" {R}Deu erro:{FIM} {ex}")
    return True


def banner():
    e = ler_estado()
    print(f"{N}{C}══ ALICIA SERVER · MODO SERVIDOR ══{FIM}   {D}terminal só para estes comandos · vale só neste notebook{FIM}")
    print(f" Estado: {V + 'LIGADO' if e.get('ligado') else A + 'desligado'}{FIM}   ·   Administrador: {'sim' if eh_admin() else 'não'}   ·   digite {N}ajuda{FIM}\n")


def main():
    motivo = so_no_notebook()
    if motivo:
        print(f"{R}Recusado:{FIM} o modo servidor só pode ser usado no próprio notebook ({motivo}).")
        log(f"tentativa de usar o modo servidor recusada ({motivo})", "seguranca")
        return 1
    if len(sys.argv) > 1:
        executa(" ".join(sys.argv[1:]))
        return 0
    try:
        ctypes.windll.kernel32.SetConsoleTitleW("ALICIA - MODO SERVIDOR" + (" (administrador)" if eh_admin() else ""))
    except Exception:
        pass
    banner()
    e = ler_estado()
    if e.get("ligado") and psutil.boot_time() > e.get("boot", 0) + 5:
        print(f" {A}!{FIM} O notebook reiniciou com o modo ligado. Digite 'status' para ver.\n")
    while True:
        try:
            linha = input(f"{N}{C}modo-servidor{FIM}{'#' if eh_admin() else '>'} ")
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not executa(linha):
            break
    return 0


if __name__ == "__main__":
    sys.exit(main())
