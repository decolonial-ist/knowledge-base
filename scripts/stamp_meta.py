#!/usr/bin/env python3
"""Мета-поля created / modified / version: ставит CI после merge в main.

    python scripts/stamp_meta.py <файл.yml> [...]        # обычно - изменённые файлы из git diff

Роль та же, что у autostamp.gs в таблице (куратор 02.11.2026: «эти поля нужны в сайте также… гит его не
заменяет»). Для каждого файла сущности с изменённым содержимым:
  - `modified` = сегодня (UTC);
  - `version` поднимается на 0.1, если `modified` до этого была не сегодняшней (не чаще раза в день);
  - `created` ставится, если поля нет.
Автор PR эти поля не трогает; если тронул - CI их перезапишет. Карточек материалов в базе нет (они в архиве).
Файл переписывается тем же дампером, что у копии из таблицы, поэтому меняются только эти три строки.
"""
import datetime as dt
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbformat  # noqa: E402

META_KINDS = ("tactics", "techniques", "actors", "tools", "campaigns")


def bump(version):
    try:
        major, minor = str(version or "1.0").split(".")
        return f"{major}.{int(minor) + 1}"
    except ValueError:
        return "1.1"


def stamp(path, today):
    parts = os.path.normpath(os.path.abspath(path)).split(os.sep)
    if not any(k in parts for k in META_KINDS):   
        return False
    doc = kbformat.load_yaml(path)
    if not isinstance(doc, dict):
        return False
    before = dict(doc)
    if not doc.get("created"):
        doc["created"] = today
    prev = doc.get("modified")
    prev = prev if isinstance(prev, dt.date) else (dt.date.fromisoformat(str(prev)) if prev else None)
    if prev != today:
        doc["version"] = bump(doc.get("version"))
    doc["modified"] = today
    if doc == before:
        return False
    # порядок полей: id, created, modified, version, остальное как было
    ordered = {k: doc[k] for k in ("type", "id", "created", "modified", "version") if k in doc}
    ordered.update({k: v for k, v in doc.items() if k not in ordered})
    with open(path, "w", encoding="utf-8") as f:
        f.write(kbformat.dump_yaml(ordered))
    return True


def main(paths):
    today = dt.datetime.now(dt.timezone.utc).date()
    changed = [p for p in paths if p.endswith(".yml") and os.path.isfile(p) and stamp(p, today)]
    for p in changed:
        print("stamped", p)
    print(f"файлов проштамповано: {len(changed)}")


if __name__ == "__main__":
    main(sys.argv[1:])
