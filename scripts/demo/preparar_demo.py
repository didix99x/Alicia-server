import json, sys, os, time
from pathlib import Path
from argon2 import PasswordHasher
D=Path(sys.argv[1]); dados=D/"Dados"/"Alicia Server"
(D/"painel"/"usuarios.json").write_text(json.dumps({"demo":{"hash":PasswordHasher().hash("demo-demo-123"),"admin":True},"visitante":{"hash":"","admin":False,"convidado":True}}),encoding="utf-8")
# biblioteca de música de exemplo (nomes inventados, sem capas: o painel desenha blocos coloridos)
faixas={"Rock":{"Banda Exemplo":["Estrada Sem Fim","Noite de Verão","Relâmpago"],"Os Faróis":["Cidade Dormindo","Luz do Farol"]},
"Eletrônica":{"DJ Aurora":["Pulso","Horizonte Neon","Amanhecer Digital","Órbita"],"Cósmica":["Estrelas em Fila","Gravidade Zero"]},
"MPB":{"Maré Mansa":["Samba da Lua","Rio de Janeiro Azul","Violão ao Vento"],"Clara Brisa":["Quintal","Chuva Fina"]},
"Jazz":{"Trio Estrela":["Café às Seis","Esquina","Meia-Luz"]},
"Pop":{"Lua Cheia":["Dançar de Novo","Verão Infinito","Coração em Cores"]}}
idx={}; n=0
for g,arts in faixas.items():
    for a,ts in arts.items():
        for t in ts:
            n+=1; vid=("DEMO%07d"%n)[:11]
            pasta=dados/"Música"/g/a; pasta.mkdir(parents=True,exist_ok=True); arq=pasta/(t+".m4a"); arq.write_bytes(b"demo")
            idx[vid]={"titulo":t,"artista":a,"genero":g,"capa":"","arquivo":str(arq.relative_to(dados)),"em":"2026-11-17","duracao":150+n*7}
(D/"dados"/"musica_indice.json").write_text(json.dumps(idx,ensure_ascii=False),encoding="utf-8")
# jogos de exemplo (arquivos vazios com nomes inventados)
jogos={"Super Nintendo":[("Aventura do Cavaleiro",".sfc"),("Corrida das Estrelas",".sfc"),("Labirinto de Cristal",".smc"),("Pirata Espacial",".sfc"),("Ninja da Lua",".sfc"),("Reino dos Slimes",".sfc")],
"Nintendo":[("Pulo Pixel",".nes"),("Torre Mágica",".nes"),("Robô Aventureiro",".nes")],
"Nintendo 64":[("Kart Turbo 3D",".z64"),("Floresta Encantada",".z64")],
"Game Boy Advance":[("Monstros de Bolso",".gba"),("Tática Real",".gba"),("Plataforma Neon",".gba")],
"PlayStation":[("Corrida Noturna",".chd"),("Lenda dos Dragões",".chd")]}
for c,l in jogos.items():
    (dados/"Jogos"/c).mkdir(parents=True,exist_ok=True)
    for nome,ext in l: (dados/"Jogos"/c/(nome+ext)).write_bytes(b"demo")
for pasta in ("Documentos","Filmes","Séries"): (dados/pasta).mkdir(exist_ok=True)
(dados/"Documentos"/"Relatório.pdf").write_bytes(b"%PDF-demo"); (dados/"Documentos"/"Receitas").mkdir(exist_ok=True)
print("demo pronta:", n, "músicas")
