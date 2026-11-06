#!/usr/bin/env python3
"""Названия кампании и техники в файле процедуры: ставит и обновляет поля campaign_name и technique_name.

    python scripts/procedure_names.py [КОРЕНЬ]          # все процедуры в campaigns/ и unpublished/campaigns/
    python scripts/procedure_names.py <файл.yml> [...]  # только эти файлы
    python scripts/procedure_names.py --check [...]     # ничего не писать, код 1 - если есть расхождения

Куратор 06.11.2026: «без названия техники не понятно о чем текст. человеку сложно будет редактировать
и оставаться в фокусе»; «и название кампании тоже добавь». Поля - копии `name` из файла кампании
(описание в той же папке) и файла техники; источник правды - эти файлы, поля в процедуре производные.
Поле, а не комментарий YAML: stamp_meta.py после merge переписывает файл дампером, комментарии он теряет.
Порядок полей - kbformat.FIELD_ORDER (campaign_name сразу за id, technique_name сразу за technique).
CI гонит скрипт после stamp_meta.py на всех процедурах; домен - при создании файла и после
переименования кампании или техники. В папке кампании с частичной выкладкой (git sparse-checkout)
нужны techniques/ и своя папка campaigns/<C>; кампании из unpublished/ ищутся и в campaigns/ корня.
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbformat  # noqa: E402

LANGS = ("ru", "en", "uk")
PROC_RE = re.compile(r"^(C\d{4})\.(T\d{4}(?:\.\d{3})?)\.yml$")


def find_root(start):
    """Корень репозитория: папка, где лежат techniques/ (и schema/)."""
    d = os.path.abspath(start)
    while True:
        if os.path.isdir(os.path.join(d, "techniques")):
            return d
        parent = os.path.dirname(d)
        if parent == d:
            return None
        d = parent


def procedure_files(root):
    out = []
    for base in ("campaigns", os.path.join("unpublished", "campaigns")):
        for path in glob.glob(os.path.join(root, base, "**", "*.yml"), recursive=True):
            if PROC_RE.match(os.path.basename(path)):
                out.append(path)
    return sorted(out)


def name_of(path):
    doc = kbformat.load_yaml(path) if os.path.isfile(path) else None
    name = (doc or {}).get("name") if isinstance(doc, dict) else None
    return {l: str((name or {}).get(l) or "") for l in LANGS} if isinstance(name, dict) else None


def campaign_name(root, proc_path, cid):
    """Описание кампании - в папке процедуры; для unpublished/ - там же или в campaigns/ корня."""
    for d in (os.path.dirname(proc_path), os.path.join(root, "campaigns", cid)):
        n = name_of(os.path.join(d, f"{cid}.yml"))
        if n:
            return n
    return None


def expected(root, proc_path):
    m = PROC_RE.match(os.path.basename(proc_path))
    if not m:
        return None, None, "имя файла не похоже на процедуру"
    cid, tid = m.groups()
    cn = campaign_name(root, proc_path, cid)
    tn = name_of(os.path.join(root, "techniques", f"{tid}.yml"))
    missing = [x for x, v in (("кампании " + cid, cn), ("техники " + tid, tn)) if not v]
    return cn, tn, ("нет файла " + " и ".join(missing)) if missing else None


def process(root, path, check):
    cn, tn, problem = expected(root, path)
    if problem:
        return "error", problem
    doc = kbformat.load_yaml(path)
    if not isinstance(doc, dict):
        return "error", "YAML не читается"
    if doc.get("campaign_name") == cn and doc.get("technique_name") == tn and list(doc) == list(kbformat.order_fields(doc)):
        return "ok", None
    if check:
        return "diff", "названия отстают от файлов кампании/техники: python scripts/procedure_names.py"
    doc["campaign_name"], doc["technique_name"] = cn, tn
    with open(path, "w", encoding="utf-8") as f:
        f.write(kbformat.dump_yaml(kbformat.order_fields(doc)))
    return "written", None


def main(argv):
    check = "--check" in argv
    args = [a for a in argv if a != "--check"]
    files = [a for a in args if a.endswith(".yml")]
    root = find_root(os.path.dirname(files[0]) if files else (args[0] if args else os.path.join(os.path.dirname(__file__), "..")))
    if not root:
        sys.exit("не нашёл корень базы знаний (папку techniques/)")
    if not files:
        files = procedure_files(root)
    counts, bad = {}, []
    for path in files:
        status, msg = process(root, os.path.abspath(path), check)
        counts[status] = counts.get(status, 0) + 1
        if msg:
            bad.append(f"{os.path.relpath(path, root)}: {msg}")
    print(f"процедур: {len(files)}; " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    for b in bad:
        print(" -", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
