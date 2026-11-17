r"""Copia as variáveis do .env único do projeto para o .env do Hermes (que fica em %LOCALAPPDATA%\hermes).
O .env do projeto é a fonte; este script só espelha. Rode como usuário normal."""
import os, secrets
from pathlib import Path
raiz = Path(__file__).resolve().parents[1]
proj = raiz / ".env"
dest = Path(os.environ["LOCALAPPDATA"]) / "hermes" / ".env"
def ler(f):
    d = {}
    if f.exists():
        for l in f.read_text(encoding="utf-8").splitlines():
            if "=" in l and not l.lstrip().startswith("#"):
                k, v = l.split("=", 1); d[k.strip()] = v.strip()
    return d
P = ler(proj)
if not P.get("API_SERVER_KEY"):                       # chave interna painel<->Hermes
    P["API_SERVER_KEY"] = secrets.token_urlsafe(32)
P.setdefault("API_SERVER_ENABLED", "true"); P.setdefault("API_SERVER_HOST", "127.0.0.1"); P.setdefault("API_SERVER_PORT", "8642")
proj.write_text("\n".join(f"{k}={v}" for k, v in P.items()) + "\n", encoding="utf-8")
H = ler(dest)
for k in ("NVIDIA_API_KEY", "NVIDIA_BASE_URL", "API_SERVER_ENABLED", "API_SERVER_KEY", "API_SERVER_HOST", "API_SERVER_PORT"):
    if P.get(k): H[k] = P[k]
    else: H.pop(k, None) if k.startswith("NVIDIA") else None
if P.get("ALICIA_MODO_TESTE") == "1":  # modo de teste: Hermes fala com o modelo falso, a chave real não é tocada
    H["NVIDIA_BASE_URL"] = "http://127.0.0.1:9099/v1"; H["NVIDIA_API_KEY"] = "chave-de-teste-falsa"
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text("\n".join(f"{k}={v}" for k, v in H.items()) + "\n", encoding="utf-8")
print("sincronizado:", sorted(k for k in H if k in P))

