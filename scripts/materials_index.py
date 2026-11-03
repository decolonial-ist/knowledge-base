#!/usr/bin/env python3
"""MATERIALS.md - список карточек архива для поиска номера сноски прямо на GitHub.

    python scripts/materials_index.py [registry.json | URL]   # по умолчанию - сайт архива

Собирается CI после merge в main (stamp.yml) из registry.json архива; руками не правится.
"""
import json
import os
import sys
import urllib.request

SRC = sys.argv[1] if len(sys.argv) > 1 else "https://archive.decolonial.ist/registry.json"
if SRC.startswith("http"):
    with urllib.request.urlopen(SRC, timeout=60) as r:
        reg = json.load(r)
else:
    reg = json.load(open(SRC, encoding="utf-8"))
rows = sorted(reg["materials"], key=lambda m: m["id"])
lines = ["# Материалы архива - номера для сносок", "",
         "Собирается автоматически из [registry.json](https://archive.decolonial.ist/registry.json) архива; "
         "руками не правится. В тексте: `(Citation: <номер>)`. Нет вашего источника - поставьте в сноску ссылку, "
         "библиографию словами или файл из `sources/`, номер выдаст Архивариус.", "",
         "| № | Автор | Название | Год | Карточка |", "|---|---|---|---|---|"]
for m in rows:
    t = (m.get("title") or "").replace("|", "\\|")
    a = (m.get("author") or "").replace("|", "\\|")
    lines.append(f"| {m['id']} | {a} | {t} | {m.get('year') or ''} | [{m['id']}]({m.get('card', '')}) |")
out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "MATERIALS.md")
open(out, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print(f"MATERIALS.md: {len(rows)} карточек")
