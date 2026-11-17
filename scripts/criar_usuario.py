"""Cria/atualiza um usuário do painel. Uso: python criar_usuario.py nome [senha] [--admin]
Sem senha, gera uma aleatória e grava em PRIMEIRO_ACESSO.txt (fora do Git)."""
import json, secrets, sys
from pathlib import Path
from argon2 import PasswordHasher
raiz = Path(__file__).resolve().parents[1]
f = raiz / "painel" / "usuarios.json"
args = [a for a in sys.argv[1:] if not a.startswith("--")]
nome = args[0].lower(); senha = args[1] if len(args) > 1 else secrets.token_urlsafe(9)
d = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
d[nome] = {"hash": PasswordHasher().hash(senha), "admin": "--admin" in sys.argv}
f.write_text(json.dumps(d, indent=1), encoding="utf-8")
if len(args) == 1:
    (raiz / "PRIMEIRO_ACESSO.txt").write_text(f"usuario: {nome}\nsenha: {senha}\n(troque depois e apague este arquivo)\n", encoding="utf-8")
print("usuario criado:", nome)
