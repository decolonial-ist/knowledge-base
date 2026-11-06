#!/usr/bin/env python3
"""Порядок языков в файлах базы: en, uk, ru - русский последним (куратор 06.11.2026: «чтобы русскоговорящие
чувствовали что это не для них и они тут не первый читатель»; остальные - по алфавиту).

    python scripts/lang_order.py [КОРЕНЬ]          # все .yml базы (tactics, techniques, actors, tools, campaigns, unpublished)
    python scripts/lang_order.py <файл.yml> [...]  # только эти файлы
    python scripts/lang_order.py --check [...]     # ничего не писать, код 1 - если порядок не тот

Переставляет ключи во всех словарях, где ключи - только коды языков (name, description, campaign_name,
technique_name, элементы contributors). Содержимое не меняет: словарь после перестановки равен прежнему,
поэтому stamp_meta.py такую правку изменением не считает. CI гонит скрипт после stamp_meta.py, домены -
при создании файла (валидатор порядок не проверяет).
"""
import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbformat  # noqa: E402

ORDER = ("en", "uk", "ru")
KINDS = ("tactics", "techniques", "actors", "tools", "campaigns")


def reorder(v):
    if isinstance(v, dict):
        if v and set(v) <= set(ORDER):
            return {k: v[k] for k in ORDER if k in v}
        return {k: reorder(x) for k, x in v.items()}
    if isinstance(v, list):
        return [reorder(x) for x in v]
    return v


def files_of(root):
    out = []
    for base in list(KINDS) + [os.path.join("unpublished", k) for k in KINDS]:
        out += glob.glob(os.path.join(root, base, "**", "*.yml"), recursive=True)
    return sorted(out)


def main(argv):
    check = "--check" in argv
    args = [a for a in argv if a != "--check"]
    files = [a for a in args if a.endswith(".yml")]
    if not files:
        root = os.path.abspath(args[0] if args else os.path.join(os.path.dirname(__file__), ".."))
        files = files_of(root)
    changed, bad = 0, []
    for path in files:
        doc = kbformat.load_yaml(path)
        new = kbformat.dump_yaml(reorder(doc))
        if new == open(path, encoding="utf-8").read():
            continue
        if check:
            bad.append(path)
            continue
        with open(path, "w", encoding="utf-8") as f:
            f.write(new)
        changed += 1
    print(f"файлов: {len(files)}; переставлено: {changed}; не в порядке: {len(bad)}")
    for b in bad:
        print(" -", os.path.relpath(b))
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
