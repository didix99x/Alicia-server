"""RPG de mesa — Alicia como mestra.

Regras simplificadas, inspiradas no SRD 5.2 (Creative Commons CC-BY-4.0, ver CREDITOS.md).
Os DADOS são rolados aqui, pelo código (módulo `secrets`), nunca pela IA. A IA só narra o resultado.
Estado das mesas guardado em dados/rpg_salas.json (gravado só quando algo muda: leve para o HD).
"""
import json
import random
import re
import secrets
import time
from pathlib import Path

ARQ = Path(__file__).resolve().parents[2] / "dados" / "rpg_salas.json"
ARQ.parent.mkdir(exist_ok=True)
MAX_JOGADORES = 5


# ---------------- Dados (justos, no servidor) ----------------
def rolar(expr: str, modo: str = "normal"):
    """Rola 'NdM+K'. modo: normal | vantagem | desvantagem (só vale para 1d20).
    Devolve dict com a expressão, os dados, o total e o modo."""
    m = re.fullmatch(r"\s*(\d{0,2})d(4|6|8|10|12|20|100)\s*([+-]\s*\d+)?\s*", expr or "")
    if not m:
        raise ValueError("Use algo como d20, 2d6+3 (dados: d4, d6, d8, d10, d12, d20).")
    n, lados, bonus = int(m.group(1) or 1), int(m.group(2)), int((m.group(3) or "0").replace(" ", ""))
    if n > 20:
        raise ValueError("No máximo 20 dados de uma vez.")
    dados = [secrets.randbelow(lados) + 1 for _ in range(n)]
    usados = dados
    if n == 1 and lados == 20 and modo in ("vantagem", "desvantagem"):
        dados = [secrets.randbelow(20) + 1, secrets.randbelow(20) + 1]
        usados = [max(dados) if modo == "vantagem" else min(dados)]
    return {"expr": expr.strip(), "dados": dados, "modo": modo, "bonus": bonus,
            "total": sum(usados) + bonus, "natural": usados[0] if n == 1 and lados == 20 else None}


def mod(v):
    return (v - 10) // 2


# ---------------- Personagens prontos (nível 1) ----------------
def _p(nome, classe, especie, attrs, pv, ca, pericias, equip, magias, historia, atq, dano):
    return {"nome": nome, "classe": classe, "especie": especie, "nivel": 1, "xp": 0, "atributos": attrs,
            "pv": pv, "pv_max": pv, "ca": ca, "pericias": pericias, "equipamento": equip, "magias": magias,
            "historia": historia, "ataque": atq, "dano": dano, "condicoes": []}


PERSONAGENS = [
    _p("Brenna Ferrolho", "Guerreira", "Humana", dict(FOR=16, DES=12, CON=15, INT=10, SAB=12, CAR=9), 12, 17,
       ["Atletismo", "Percepção"], ["Espada longa", "Escudo", "Cota de malha", "Mochila de aventureira"], [],
       "Ex-guarda de caravanas que jurou nunca mais perder um companheiro.", 5, "1d8+3"),
    _p("Elarion Luzia", "Mago", "Elfo", dict(FOR=8, DES=14, CON=13, INT=16, SAB=12, CAR=10), 7, 12,
       ["Arcanismo", "História"], ["Cajado", "Grimório", "Bolsa de componentes"],
       ["Raio de Fogo (truque, 1d10)", "Mísseis Mágicos (3 dardos de 1d4+1)", "Escudo Arcano"],
       "Bibliotecário curioso demais, expulso da torre por ler o livro proibido.", 5, "1d10"),
    _p("Pipo Passoleve", "Ladino", "Halfling", dict(FOR=8, DES=17, CON=12, INT=13, SAB=10, CAR=14), 9, 14,
       ["Furtividade", "Prestidigitação", "Persuasão"], ["Adaga x2", "Arco curto", "Ferramentas de ladrão"], [],
       "Filho de padeiros que descobriu que fechaduras são mais divertidas que pães.", 5, "1d6+3 (+1d6 ataque furtivo)"),
    _p("Irmã Dagna Pedraforte", "Clériga", "Anã", dict(FOR=14, DES=10, CON=14, INT=10, SAB=16, CAR=12), 10, 18,
       ["Medicina", "Intuição"], ["Maça", "Escudo sagrado", "Cota de malha"],
       ["Chama Sagrada (truque, 1d8)", "Curar Ferimentos (1d8+3)", "Bênção"],
       "Cuida de uma capela no meio da montanha e de qualquer um que bata à porta.", 4, "1d6+2"),
    _p("Vesper Lírio", "Bardo", "Tiferino", dict(FOR=9, DES=14, CON=13, INT=11, SAB=10, CAR=16), 9, 13,
       ["Atuação", "Enganação", "Persuasão"], ["Rapieira", "Alaúde", "Roupas de palco"],
       ["Zombaria Cruel (truque, 1d4)", "Palavra de Cura (1d4+3)", "Sono"],
       "Cantora de taverna com chifres e dívidas, procurando a canção perfeita.", 4, "1d8+2"),
    _p("Gorrok Quebra-Galho", "Bárbaro", "Orc", dict(FOR=17, DES=13, CON=16, INT=8, SAB=11, CAR=10), 15, 14,
       ["Atletismo", "Sobrevivência"], ["Machado grande", "Dois machados de mão", "Pele de urso"], [],
       "Lenhador de poucas palavras. Quando se irrita, a floresta inteira ouve.", 5, "1d12+3"),
]

# ---------------- Campanhas originais (escritas para este projeto, sem direitos de terceiros) ----------------
INIM = {
    "morcego": {"nome": "Morcego-Sino", "pv": 9, "ca": 12, "ataque": 3, "dano": "1d6+1", "xp": 50},
    "esqueleto": {"nome": "Esqueleto Guardião", "pv": 13, "ca": 13, "ataque": 4, "dano": "1d6+2", "xp": 100},
    "sacristao": {"nome": "Sacristão Sem Rosto", "pv": 24, "ca": 14, "ataque": 5, "dano": "1d8+3", "xp": 200},
    "capanga": {"nome": "Capanga da Feira", "pv": 11, "ca": 12, "ataque": 3, "dano": "1d6+1", "xp": 50},
    "mercador": {"nome": "Mercador das Sombras", "pv": 26, "ca": 14, "ataque": 5, "dano": "1d8+3", "xp": 200},
}
CAMPANHAS = {
    "sino": {
        "titulo": "A Cripta do Sino Quebrado",
        "resumo": "Um vilarejo ouve um sino que não existe. A origem está numa cripta sob a capela abandonada.",
        "capitulos": [
            {"titulo": "O sino fantasma", "local": "Vila de Pedrinha", "cena": "À noite, todos ouvem um sino. A anciã Maud pede ajuda: o sino da capela foi roubado há anos. Há pegadas de cera até a capela.", "inimigos": []},
            {"titulo": "A capela vazia", "local": "Capela abandonada", "cena": "Sob o altar há uma escada para a cripta. Morcegos de bronze rondam o salão.", "inimigos": ["morcego", "morcego"]},
            {"titulo": "O sacristão", "local": "Cripta", "cena": "O Sacristão Sem Rosto guarda o sino partido. Ele pode ser vencido à força ou convencido a descansar (quem fala a verdade sobre o passado dele ganha vantagem).", "inimigos": ["esqueleto", "sacristao"]},
        ],
        "finais": {"misericordia": "O sino é consertado e o sacristão descansa. A vila canta de paz.", "forca": "O sino é destruído; a vila fica em silêncio, aliviada e um pouco assustada.", "ganancia": "O bronze é vendido; o sino passa a tocar sozinho, à noite, em outra cidade."},
    },
    "feira": {
        "titulo": "O Mercado das Sombras",
        "resumo": "Uma feira que só aparece à meia-noite vende lembranças. Alguém roubou a memória de uma criança.",
        "capitulos": [
            {"titulo": "A feira aparece", "local": "Praça de Vale Alto", "cena": "Barracas surgem do nada. Uma mãe implora: a filha Lia esqueceu o próprio nome.", "inimigos": []},
            {"titulo": "Os corredores", "local": "Feira da meia-noite", "cena": "Capangas guardam a barraca de memórias. Dá para lutar, subornar ou enganar.", "inimigos": ["capanga", "capanga"]},
            {"titulo": "O Mercador", "local": "Barraca preta", "cena": "O Mercador das Sombras oferece um trato: devolve a memória em troca de uma lembrança feliz de alguém do grupo.", "inimigos": ["mercador"]},
        ],
        "finais": {"misericordia": "O grupo oferece uma lembrança e Lia volta a sorrir; o mercador some pensativo.", "forca": "O Mercador é derrotado; as memórias voltam, mas a feira nunca mais aparece.", "ganancia": "O grupo guarda as memórias para si; Lia ganha um nome novo e a vila nunca mais confia neles."},
    },
}

MESTRA = """[VOCÊ É A MESTRA DE UM RPG DE MESA]
Você é a Alicia, mestra do jogo. Narre em português do Brasil, com a sua personalidade (expressiva, analítica, um pouco sarcástica quando cabe),
em no máximo 4 frases curtas por resposta. NUNCA role dados nem invente resultados de dados: use apenas os resultados fornecidos abaixo.
Reaja às escolhas livres dos jogadores, peça uma rolagem (ex.: "role Percepção, d20") quando a ação for incerta, e não contradiga o estado da partida.
Comece a resposta com uma tag de expressão: [FELIZ], [SERIO], [SURPRESA], [PENSANDO] ou [BRAVO]."""


# ---------------- Estado das mesas ----------------
salas = {}


def carregar():
    if ARQ.exists():
        salas.update(json.loads(ARQ.read_text(encoding="utf-8")))


def salvar():
    ARQ.write_text(json.dumps(salas, ensure_ascii=False), encoding="utf-8")


def _log(sala, quem, texto, tipo="fala"):
    sala["log"].append({"t": time.strftime("%H:%M"), "quem": quem, "texto": texto, "tipo": tipo})
    del sala["log"][:-400]


def criar_sala(dono: str, campanha: str):
    if campanha not in CAMPANHAS:
        raise ValueError("Campanha desconhecida.")
    while True:
        cod = "".join(random.choice("ABCDEFGHJKLMNPQRSTUVWXYZ23456789") for _ in range(4))
        if cod not in salas:
            break
    salas[cod] = {"codigo": cod, "dono": dono, "campanha": campanha, "cap": 0, "jogadores": {}, "log": [],
                  "resumo": "", "combate": None, "pontos": {"misericordia": 0, "forca": 0, "ganancia": 0}, "fim": False, "criada": time.time()}
    _log(salas[cod], "Mesa", f"Mesa criada: {CAMPANHAS[campanha]['titulo']}. {CAMPANHAS[campanha]['resumo']}", "sistema")
    salvar()
    return salas[cod]


def entrar(codigo: str, usuario: str, indice_personagem: int):
    s = salas.get(codigo.upper())
    if not s:
        raise ValueError("Não achei essa mesa. Confira o código.")
    if usuario not in s["jogadores"] and len(s["jogadores"]) >= MAX_JOGADORES:
        raise ValueError("A mesa já tem 5 jogadores.")
    if any(j["indice"] == indice_personagem and u != usuario for u, j in s["jogadores"].items()):
        raise ValueError("Esse personagem já foi escolhido por outra pessoa.")
    ficha = json.loads(json.dumps(PERSONAGENS[indice_personagem]))
    s["jogadores"].setdefault(usuario, {"indice": indice_personagem, "ficha": ficha})
    _log(s, "Mesa", f"{usuario} entrou como {ficha['nome']} ({ficha['classe']}).", "sistema")
    salvar()
    return s


def rolagem(sala, usuario, expr, motivo="", modo="normal"):
    r = rolar(expr, modo)
    txt = f"🎲 {usuario} rolou {r['expr']}{' (' + modo + ')' if modo != 'normal' else ''}: {r['dados']}" \
          f"{' ' + format(r['bonus'], '+d') if r['bonus'] else ''} = {r['total']}{' — ' + motivo if motivo else ''}"
    _log(sala, "Dados", txt, "dado")
    salvar()
    return r


# ---------------- Combate por turnos (tudo decidido pelo código) ----------------
def iniciar_combate(sala):
    cap = CAMPANHAS[sala["campanha"]]["capitulos"][sala["cap"]]
    if not cap["inimigos"]:
        raise ValueError("Não há inimigos neste capítulo.")
    if not sala["jogadores"]:
        raise ValueError("Ninguém entrou na mesa ainda.")
    ini = []
    for u, j in sala["jogadores"].items():
        ini.append({"id": u, "nome": j["ficha"]["nome"], "lado": "jog", "init": rolar("d20")["total"] + mod(j["ficha"]["atributos"]["DES"])})
    inimigos = []
    for i, k in enumerate(cap["inimigos"]):
        e = dict(INIM[k]); e["id"] = f"{k}{i}"; e["pv_max"] = e["pv"]; inimigos.append(e)
        ini.append({"id": e["id"], "nome": e["nome"], "lado": "ini", "init": rolar("d20")["total"] + 1})
    ini.sort(key=lambda x: -x["init"])
    sala["combate"] = {"ordem": ini, "turno": 0, "inimigos": inimigos, "rodada": 1}
    _log(sala, "Combate", "⚔️ Combate! Iniciativa: " + ", ".join(f"{x['nome']} ({x['init']})" for x in ini), "sistema")
    salvar()
    _avancar_inimigos(sala)


def _vivos_jog(sala):
    return [(u, j) for u, j in sala["jogadores"].items() if j["ficha"]["pv"] > 0]


def _fim_combate(sala):
    c = sala["combate"]
    if all(e["pv"] <= 0 for e in c["inimigos"]):
        xp = sum(e["xp"] for e in c["inimigos"])
        for _, j in _vivos_jog(sala):
            f = j["ficha"]; f["xp"] += xp
            if f["nivel"] == 1 and f["xp"] >= 300:     # subida de nível simples
                f["nivel"] = 2; f["pv_max"] += 8; f["pv"] = f["pv_max"]
                _log(sala, "Mesa", f"⭐ {f['nome']} subiu para o nível 2!", "sistema")
        _log(sala, "Combate", f"🏆 Vitória! Cada sobrevivente ganha {xp} XP.", "sistema")
        sala["combate"] = None
        return True
    if not _vivos_jog(sala):
        _log(sala, "Combate", "💀 Todos caíram. A mesa pode recomeçar o capítulo.", "sistema")
        for j in sala["jogadores"].values():
            j["ficha"]["pv"] = max(1, j["ficha"]["pv_max"] // 2)
        sala["combate"] = None
        return True
    return False


def _avancar_inimigos(sala):
    """Passa os turnos até chegar a um jogador vivo; inimigos agem sozinhos."""
    c = sala["combate"]
    for _ in range(30):
        if not c or _fim_combate(sala):
            return
        atual = c["ordem"][c["turno"] % len(c["ordem"])]
        if atual["lado"] == "jog" and next((j for u, j in sala["jogadores"].items() if u == atual["id"]), {"ficha": {"pv": 0}})["ficha"]["pv"] > 0:
            return
        if atual["lado"] == "ini":
            e = next(x for x in c["inimigos"] if x["id"] == atual["id"])
            alvos = _vivos_jog(sala)
            if e["pv"] > 0 and alvos:
                u, j = random.choice(alvos)
                ataque = rolar("d20")
                total = ataque["total"] + e["ataque"]
                if total >= j["ficha"]["ca"] or ataque["natural"] == 20:
                    dano = rolar(e["dano"])["total"]
                    j["ficha"]["pv"] = max(0, j["ficha"]["pv"] - dano)
                    _log(sala, "Combate", f"{e['nome']} ataca {j['ficha']['nome']}: d20={ataque['natural']}+{e['ataque']}={total} vs CA {j['ficha']['ca']} → acerta! {dano} de dano (PV {j['ficha']['pv']}/{j['ficha']['pv_max']}).", "dado")
                else:
                    _log(sala, "Combate", f"{e['nome']} ataca {j['ficha']['nome']}: d20={ataque['natural']}+{e['ataque']}={total} vs CA {j['ficha']['ca']} → erra.", "dado")
        c["turno"] += 1
    salvar()


def atacar(sala, usuario, alvo_id):
    c = sala["combate"]
    if not c:
        raise ValueError("Não há combate agora.")
    atual = c["ordem"][c["turno"] % len(c["ordem"])]
    if atual["id"] != usuario:
        raise ValueError(f"Não é a sua vez. Agora é {atual['nome']}.")
    e = next((x for x in c["inimigos"] if x["id"] == alvo_id and x["pv"] > 0), None)
    if not e:
        raise ValueError("Alvo inválido.")
    f = sala["jogadores"][usuario]["ficha"]
    ataque = rolar("d20")
    total = ataque["total"] + f["ataque"]
    if total >= e["ca"] or ataque["natural"] == 20:
        expr = re.match(r"[\dd+\-]+", f["dano"]).group(0)
        dano = rolar(expr)["total"] + (rolar("d6")["total"] if "furtivo" in f["dano"] else 0)
        if ataque["natural"] == 20:
            dano *= 2
        e["pv"] = max(0, e["pv"] - dano)
        _log(sala, "Combate", f"{f['nome']} ataca {e['nome']}: d20={ataque['natural']}+{f['ataque']}={total} vs CA {e['ca']} → acerta! {dano} de dano (PV {e['pv']}/{e['pv_max']}).", "dado")
    else:
        _log(sala, "Combate", f"{f['nome']} ataca {e['nome']}: d20={ataque['natural']}+{f['ataque']}={total} vs CA {e['ca']} → erra.", "dado")
    c["turno"] += 1
    _avancar_inimigos(sala)
    salvar()


# ---------------- Mestra (Hermes) ----------------
def contexto_para_mestra(sala, usuario, texto):
    camp = CAMPANHAS[sala["campanha"]]; cap = camp["capitulos"][sala["cap"]]
    grupo = "; ".join(f"{u}={j['ficha']['nome']} ({j['ficha']['classe']}) PV {j['ficha']['pv']}/{j['ficha']['pv_max']}" for u, j in sala["jogadores"].items())
    recentes = "\n".join(f"{x['quem']}: {x['texto']}" for x in sala["log"][-8:])   # só o final; o resto vira resumo
    comb = ""
    if sala["combate"]:
        comb = "COMBATE EM ANDAMENTO: " + ", ".join(f"{e['nome']} PV {e['pv']}/{e['pv_max']}" for e in sala["combate"]["inimigos"])
    return (f"{MESTRA}\n\n[CAMPANHA] {camp['titulo']} — capítulo {sala['cap'] + 1}/{len(camp['capitulos'])}: {cap['titulo']} ({cap['local']}). Cena: {cap['cena']}\n"
            f"[GRUPO] {grupo}\n[RESUMO DA HISTÓRIA ATÉ AGORA] {sala['resumo'] or '(início da aventura)'}\n{comb}\n[ÚLTIMOS EVENTOS]\n{recentes}\n\n"
            f"[AÇÃO DE {usuario.upper()}] {texto}")


def registrar_escolha(sala, texto):
    t = texto.lower()
    if any(p in t for p in ("poupar", "ajudar", "convenc", "perdo", "verdade", "conversar")):
        sala["pontos"]["misericordia"] += 1
    if any(p in t for p in ("atacar", "matar", "destruir", "quebrar")):
        sala["pontos"]["forca"] += 1
    if any(p in t for p in ("roubar", "vender", "ficar com", "pegar o tesouro")):
        sala["pontos"]["ganancia"] += 1


def avancar_capitulo(sala):
    camp = CAMPANHAS[sala["campanha"]]
    if sala["cap"] + 1 < len(camp["capitulos"]):
        sala["cap"] += 1
        c = camp["capitulos"][sala["cap"]]
        _log(sala, "Mesa", f"📖 Capítulo {sala['cap'] + 1}: {c['titulo']} — {c['cena']}", "sistema")
    else:
        fim = max(sala["pontos"], key=sala["pontos"].get)
        sala["fim"] = True
        _log(sala, "Mesa", f"🏁 FIM. {camp['finais'][fim]}", "sistema")
    salvar()


def precisa_resumir(sala):
    return len(sala["log"]) > 30 and len(sala["log"]) % 10 == 0


carregar()
