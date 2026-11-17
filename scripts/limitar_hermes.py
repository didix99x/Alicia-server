import os
from pathlib import Path
f = Path(os.environ["LOCALAPPDATA"]) / "hermes" / "config.yaml"
t = f.read_text(encoding="utf-8")
if "\napi_server:" not in t.split("platform_toolsets:")[-1] or "platform_toolsets:" not in t:
    t += "\n# Alicia Server: o Hermes acessado pelo painel NÃO tem terminal nem arquivos (não apaga seus arquivos nem mexe no sistema).\nplatform_toolsets:\n  api_server: [web, skills, todo, cronjob]\n"
    f.write_text(t, encoding="utf-8"); print("limite aplicado")
