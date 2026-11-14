#!/usr/bin/env python3
"""Названия кампании, техники, акторов и инструментов в файле процедуры: стоят под номером, в словарях
campaign, technique, actor, tool. Тем же видом пишутся ссылки в файлах техник (parent, tactics) и кампаний
(associated_campaigns): скрипт без аргументов проходит и их.

    python scripts/procedure_names.py [КОРЕНЬ]          # все процедуры в campaigns/ и unpublished/campaigns/
    python scripts/procedure_names.py <файл.yml> [...]  # только эти файлы
    python scripts/procedure_names.py --check [...]     # ничего не писать, код 1 - если есть расхождения

Названия нужны читателю файла: без них не видно, о какой кампании и технике текст и что значит номер.
Названия - копии `name` из файлов кампании (описание в той же папке), техники, актора и инструмента;
источник правды - эти файлы. Руками достаточно написать номер: `technique: T0023`, `tool: S0017` или
списком; скрипт перепишет поле в словарь «номер: название». Файл в прежнем виде (поля campaign_name,
technique_name, actor_name, tool_name) скрипт переводит в новый.
Словарь, а не комментарий YAML: stamp_meta.py после merge переписывает файл дампером, комментарии он теряет.
Порядок полей - kbformat.FIELD_ORDER. CI гонит скрипт после stamp_meta.py на всех процедурах; автор - при
создании файла и после переименования кампании или техники. В папке кампании с частичной выкладкой
(git sparse-checkout) нужны techniques/, actors/, tools/ и своя папка campaigns/<C>; кампании из
unpublished/ ищутся и в campaigns/ корня.
"""
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbformat  # noqa: E402

LANGS = ("en", "uk", "ru")
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


def linked_names(root, doc):
    """Словари «номер: название» для actor и tool; None - поле пустое; ошибка - нет файла сущности.
    На входе годятся словарь, список номеров и один номер строкой."""
    out, problems = {}, []
    for field, sub, what in (("actor", "actors", "актора"), ("tool", "tools", "инструмента")):
        ids = kbformat.as_list(doc.get(field))
        if not ids:
            out[field] = None
            continue
        names = {}
        for one in ids:
            n = name_of(os.path.join(root, sub, f"{one}.yml"))
            if not n:
                problems.append(f"нет файла {what} {one}")
            names[one] = n
        out[field] = names
    return out, problems


def process(root, path, check):
    cn, tn, problem = expected(root, path)
    if problem:
        return "error", problem
    doc = kbformat.load_yaml(path)
    if not isinstance(doc, dict):
        return "error", "YAML не читается"
    linked, problems = linked_names(root, doc)
    if problems:
        return "error", "; ".join(problems)
    cid, tid = PROC_RE.match(os.path.basename(path)).groups()
    # название стоит под номером: campaign, technique, actor, tool - словари «номер: название»
    want = {"campaign": {cid: cn}, "technique": {tid: tn}, **linked}

    def same(a, b):   # у словаря «номер: название» важен и порядок номеров
        return a == b and (not isinstance(a, dict) or not isinstance(b, dict) or list(a) == list(b))

    legacy = [f for f in kbformat.LEGACY_NAME_FIELDS if f in doc]
    if not legacy and all(same(doc.get(k), v) for k, v in want.items()) and list(doc) == list(kbformat.order_fields(doc)):
        return "ok", None
    if check:
        return "diff", "названия отстают от файлов кампании/техники/актора/инструмента: python scripts/procedure_names.py"
    for f in legacy:
        doc.pop(f)
    doc.update(want)
    with open(path, "w", encoding="utf-8") as f:
        f.write(kbformat.dump_yaml(kbformat.order_fields(doc)))
    return "written", None


# ссылки в файлах техник и кампаний: поле -> папка сущностей
ENTITY_REFS = {"technique": (("parent", "techniques"), ("tactics", "tactics")),
               "campaign": (("associated_campaigns", "campaigns"),)}


def entity_files(root):
    """Файлы техник и описания кампаний в корне и в unpublished/."""
    out = []
    for base in ("", "unpublished"):
        out += glob.glob(os.path.join(root, base, "techniques", "*.yml"))
        for path in glob.glob(os.path.join(root, base, "campaigns", "**", "*.yml"), recursive=True):
            if re.fullmatch(r"C\d{4}\.yml", os.path.basename(path)):
                out.append(path)
    return sorted(out)


def entity_name(root, sub, ident):
    """name сущности по номеру; кампания ищется по всем папкам campaigns/ и unpublished/campaigns/."""
    if sub != "campaigns":
        for base in ("", "unpublished"):
            n = name_of(os.path.join(root, base, sub, f"{ident}.yml"))
            if n:
                return n
        return None
    for base in ("campaigns", os.path.join("unpublished", "campaigns")):
        for path in glob.glob(os.path.join(root, base, "**", ident, f"{ident}.yml"), recursive=True):
            n = name_of(path)
            if n:
                return n
    return None


def process_entity(root, path, check):
    """Техника или кампания: parent, tactics, associated_campaigns - словари «номер: название»."""
    doc = kbformat.load_yaml(path)
    if not isinstance(doc, dict) or doc.get("type") not in ENTITY_REFS:
        return "ok", None
    want, problems = {}, []
    for field, sub in ENTITY_REFS[doc["type"]]:
        ids = kbformat.as_list(doc.get(field))
        if not ids:
            continue
        names = {}
        for one in ids:
            n = entity_name(root, sub, one)
            if not n and isinstance(doc.get(field), dict) and isinstance(doc[field].get(one), dict):
                n = doc[field][one]   # файла сущности нет в частичной выкладке - название уже стоит, оставляем
            if not n:
                problems.append(f"нет файла {one} ({field})")
            names[one] = n
        want[field] = names
    if problems:
        return "error", "; ".join(problems)
    if all(isinstance(doc.get(k), dict) and doc[k] == v and list(doc[k]) == list(v) for k, v in want.items()):
        return "ok", None
    if check:
        return "diff", "названия в ссылках отстают от файлов сущностей: python scripts/procedure_names.py"
    doc.update(want)
    with open(path, "w", encoding="utf-8") as f:
        f.write(kbformat.dump_yaml(doc))
    return "written", None


def main(argv):
    check = "--check" in argv
    args = [a for a in argv if a != "--check"]
    files = [a for a in args if a.endswith(".yml")]
    root = find_root(os.path.dirname(files[0]) if files else (args[0] if args else os.path.join(os.path.dirname(__file__), "..")))
    if not root:
        sys.exit("не нашёл корень базы знаний (папку techniques/)")
    entities = []
    if not files:
        files = procedure_files(root)
        entities = entity_files(root)
    else:   # названные файлы: процедуры - по имени, остальное - техники и кампании
        entities = [f for f in files if not PROC_RE.match(os.path.basename(f))]
        files = [f for f in files if PROC_RE.match(os.path.basename(f))]
    counts, bad = {}, []
    for path in files:
        status, msg = process(root, os.path.abspath(path), check)
        counts[status] = counts.get(status, 0) + 1
        if msg:
            bad.append(f"{os.path.relpath(path, root)}: {msg}")
    print(f"процедур: {len(files)}; " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items())))
    ecounts = {}
    for path in entities:
        status, msg = process_entity(root, os.path.abspath(path), check)
        ecounts[status] = ecounts.get(status, 0) + 1
        if msg:
            bad.append(f"{os.path.relpath(path, root)}: {msg}")
    if entities:
        print(f"техник и кампаний: {len(entities)}; " + ", ".join(f"{k}: {v}" for k, v in sorted(ecounts.items())))
    for b in bad:
        print(" -", b)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
