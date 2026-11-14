#!/usr/bin/env python3
"""Текст ячейки из файла базы знаний - для чекеров, LanguageTool и скиллов.

    python scripts/kb_text.py campaigns/C1193/C1193.T0023.yml [ru|en|uk]   # по умолчанию ru

Печатает прозу так, как её увидит сайт: фразы абзаца склеены пробелами, абзацы разделены
переносом строки, сноски (Citation: N) на месте. Чекеры оптики, переводов и редких слов
кормить этим выводом (сохранить в файл или через pipe)."""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbformat  # noqa: E402

path = sys.argv[1]
lang = sys.argv[2] if len(sys.argv) > 2 else "ru"
doc = kbformat.load_yaml(path)
print(kbformat.block_to_cell((doc.get("description") or {}).get(lang, "")))
