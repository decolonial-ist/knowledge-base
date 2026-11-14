#!/usr/bin/env python3
"""Механическая проверка базы знаний (CI и локально): форма файлов, ссылки, сноски.

    .venv/bin/python scripts/validate.py [КОРЕНЬ]        # по умолчанию - корень репозитория

Проверяет:
  1. каждый файл - по своей JSON Schema из schema/ (обязательные поля, типы, форматы, лишние поля);
     имя файла совпадает с полем id;
  2. ссылки существуют: тактики техник, родитель подтехники, кампания/техника/актор/инструмент
     процедуры, родитель кампании; список procedures кампании совпадает с файлами процедур;
     campaign, technique, actor, tool процедуры - словари «номер: название», название равно name кампании,
     техники, актора и инструмента;
  3. сноски: в трёх языках одной прозы - одинаковый набор; сноски дат кампании - номера. Номер, которого
     ещё нет в реестре архива (registry.json с archive.decolonial.ist или локальный файл через KB_REGISTRY),
     не ошибка, а строка в отчёте: карточка источника выходит на витрину после merge. Сноска не по номеру - ссылка, библиография словами или файл
     в sources/ - это источник на приёмке в архиве: PR не мержится, пока источнику не выдан номер.
Содержание прозы не проверяет: это чекеры и люди. Код возврата 1 = есть ошибки.
"""
import glob
import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbformat  # noqa: E402

try:
    import jsonschema
except ImportError:  # pragma: no cover
    sys.exit("нужен пакет jsonschema: .venv/bin/pip install jsonschema")

KINDS = ("tactics", "techniques", "actors", "tools", "campaigns", "procedures")
FLAT = ("tactics", "techniques", "actors", "tools")
LANGS = ("en", "uk", "ru")


def load_registry_ids():
    """Номера карточек архива: KB_REGISTRY=<файл> или registry.json с сайта архива."""
    import json
    src = os.environ.get("KB_REGISTRY") or "https://archive.decolonial.ist/registry.json"
    if src.startswith("http"):
        import urllib.request
        with urllib.request.urlopen(src, timeout=60) as r:
            reg = json.load(r)
    else:
        reg = json.load(open(src, encoding="utf-8"))
    return {str(m["id"]) for m in reg["materials"]}


def _dates_to_str(v):
    """YAML читает 2026-10-24 как дату; схема проверяет её строкой ISO."""
    import datetime as dt
    if isinstance(v, (dt.date, dt.datetime)):
        return v.isoformat()[:10]
    if isinstance(v, dict):
        return {k: _dates_to_str(x) for k, x in v.items()}
    if isinstance(v, list):
        return [_dates_to_str(x) for x in v]
    return v


def _read(path):
    try:
        return _dates_to_str(kbformat.load_yaml(path))
    except Exception as e:  # YAML не разобрался - тоже ошибка формы
        return e


def load_all(root, layout_errors):
    """campaigns/ обходится деревом: C1193/C1193.yml - кампания, C1193.T*.yml рядом - процедуры, C*/ - эпизоды."""
    data = {k: {} for k in KINDS}
    for kind in FLAT:
        for path in sorted(glob.glob(os.path.join(root, kind, "*.yml"))):
            data[kind][path] = _read(path)
    parent_of, campaign_of = {}, {}

    def walk(d, parent):
        for name in sorted(os.listdir(d)):
            path = os.path.join(d, name)
            if os.path.isdir(path):
                if not re.fullmatch(r"C\d{4}", name):
                    layout_errors.append(f"{os.path.relpath(path, root)}: папка не похожа на кампанию (CNNNN)")
                    continue
                own = os.path.join(path, f"{name}.yml")
                if not os.path.isfile(own):
                    layout_errors.append(f"{os.path.relpath(path, root)}: нет файла описания {name}.yml")
                else:
                    data["campaigns"][own] = _read(own)
                    parent_of[name] = parent
                walk(path, name)
            elif name.endswith(".yml"):
                if d == os.path.join(root, "campaigns"):
                    layout_errors.append(f"{os.path.relpath(path, root)}: файл вне папки кампании")
                elif re.fullmatch(rf"{os.path.basename(d)}\.T\d{{4}}(\.\d{{3}})?\.yml", name):
                    data["procedures"][path] = _read(path)
                    campaign_of[path] = os.path.basename(d)
                elif name != f"{os.path.basename(d)}.yml":
                    layout_errors.append(f"{os.path.relpath(path, root)}: лишний файл в папке кампании")
    if os.path.isdir(os.path.join(root, "campaigns")):
        walk(os.path.join(root, "campaigns"), None)
    return data, parent_of, campaign_of


def main(root):
    errors = []
    err = lambda path, msg: errors.append(f"{os.path.relpath(path, root)}: {msg}")
    # схемы лежат рядом со скриптом; у проверяемого дерева (например, неопубликованного) их может не быть
    schema_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "schema")
    schemas = {k: json.load(open(os.path.join(schema_dir, f"{k}.json"), encoding="utf-8")) for k in KINDS}
    data, parent_of, campaign_of = load_all(root, errors)

    # 1. форма
    by_id = {k: {} for k in KINDS}
    for kind, files in data.items():
        validator = jsonschema.Draft202012Validator(schemas[kind])
        for path, doc in files.items():
            if isinstance(doc, Exception):
                err(path, f"YAML не читается: {doc}")
                continue
            for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
                where = "/".join(str(p) for p in e.path) or "<корень>"
                err(path, f"схема: {where}: {e.message}")
            stem = os.path.splitext(os.path.basename(path))[0]
            if isinstance(doc, dict) and str(doc.get("id")) != stem:
                err(path, f"имя файла «{stem}» не совпадает с id «{doc.get('id')}»")
            if isinstance(doc, dict):
                by_id[kind][str(doc.get("id"))] = doc

    tactics, techniques, actors, tools = by_id["tactics"], by_id["techniques"], by_id["actors"], by_id["tools"]
    campaigns, procedures = by_id["campaigns"], by_id["procedures"]
    materials = load_registry_ids()
    pending = []   # источники на приёмке: ссылки, библиография словами, файлы в sources/
    no_card = []   # номера без карточки на витрине архива: не ошибка

    def check_prose(path, prose):
        if not isinstance(prose, dict):
            return
        sets = {}
        for lang in LANGS:
            keys = kbformat.citation_keys(prose.get(lang) or "")
            for k in keys:
                if re.fullmatch(r"\d+", k):
                    # Карточка источника выходит на витрину архива после merge, поэтому номера без
                    # карточки CI не красят. Выдан ли номер, проверяется до merge.
                    if k not in materials:
                        no_card.append((path, k))
                elif k.startswith("sources/"):
                    if not os.path.isfile(os.path.join(root, k)):
                        err(path, f"сноска на файл, которого нет в репозитории: {k}")
                    pending.append((path, k))
                else:
                    pending.append((path, k))
            if prose.get(lang):
                sets[lang] = sorted(set(keys))
        if len({tuple(v) for v in sets.values()}) > 1:
            err(path, f"разный набор сносок по языкам: { {l: len(v) for l, v in sets.items()} }")

    def check_names(path, p, cid, camp, tech):
        """campaign / technique / actor / tool процедуры - словари «номер: название», название - копия name
        связанной сущности; чинит procedure_names.py."""
        def name_of(src):
            return {l: str(src["name"].get(l) or "") for l in LANGS}

        hint = "python scripts/procedure_names.py"
        if any(f in p for f in kbformat.LEGACY_NAME_FIELDS):
            err(path, f"файл в прежнем виде (названия отдельными полями): {hint}")
            return
        want = {}
        if camp and isinstance(camp.get("name"), dict):
            want["campaign"] = {cid: name_of(camp)}
        if tech and isinstance(tech.get("name"), dict):
            want["technique"] = {tech["id"]: name_of(tech)}
        for field, known in (("actor", actors), ("tool", tools)):
            ids = kbformat.as_list(p.get(field))
            if ids and all(i in known for i in ids):
                want[field] = {i: name_of(known[i]) for i in ids}
        for field, value in want.items():
            got = p.get(field)
            if not isinstance(got, dict) or got != value or list(got) != list(value):
                err(path, f"{field}: нужен словарь «номер: название», названия - как в файлах сущностей: {hint}")

    def check_refs(path, doc, fields):
        """Ссылки в файлах техник и кампаний (тактики, родитель, связанные кампании) - словари «номер: название»,
        название - копия name сущности; чинит procedure_names.py."""
        for field, known in fields:
            ids = kbformat.as_list(doc.get(field))
            if not ids or not all(i in known and isinstance(known[i].get("name"), dict) for i in ids):
                continue
            want = {i: {l: str(known[i]["name"].get(l) or "") for l in LANGS} for i in ids}
            got = doc.get(field)
            if not isinstance(got, dict) or got != want or list(got) != list(want):
                err(path, f"{field}: нужен словарь «номер: название», названия - как в файлах сущностей: python scripts/procedure_names.py")

    def check_cit_list(path, lst, field):
        for k in lst or []:
            if not re.fullmatch(r"\d+", str(k)):
                err(path, f"{field}: сноска должна быть номером материала: {k}")
            elif str(k) not in materials:
                no_card.append((path, str(k)))

    # 2-3. ссылки и сноски
    for path, t in data["techniques"].items():
        if not isinstance(t, dict):
            continue
        for ta in kbformat.as_list(t.get("tactics")):
            if ta not in tactics:
                err(path, f"тактика {ta} не существует")
        parent = kbformat.ref_id(t.get("parent"))
        if parent and parent not in techniques:
            err(path, f"родитель {parent} не существует")
        if "." in str(t.get("id")) and not parent:
            err(path, "у подтехники нет поля parent")
        check_refs(path, t, (("tactics", tactics), ("parent", techniques)))
        check_prose(path, t.get("description"))
    for kind in ("tactics", "actors", "tools"):
        for path, d in data[kind].items():
            if isinstance(d, dict):
                check_prose(path, d.get("description"))
    for path, p in data["procedures"].items():
        if not isinstance(p, dict):
            continue
        cid = campaign_of[path]
        if cid not in campaigns:
            err(path, f"папка кампании {cid} без описания {cid}.yml")
        tid = kbformat.ref_id(p.get("technique"))
        if tid not in techniques:
            err(path, f"техника {tid} не существует")
        for actor_id in kbformat.as_list(p.get("actor")):
            if actor_id not in actors:
                err(path, f"актор {actor_id} не существует")
        for tool_id in kbformat.as_list(p.get("tool")):
            if tool_id not in tools:
                err(path, f"инструмент {tool_id} не существует")
        if f"{cid}.{tid}" != str(p.get("id")):
            err(path, f"id должен быть «{cid}.{tid}» (кампания.техника)")
        if p.get("campaign") is not None and kbformat.ref_id(p.get("campaign")) != cid:
            err(path, f"campaign должен быть {cid} - по папке, где лежит файл")
        if cid in campaigns and campaigns[cid].get("people") != p.get("people"):
            err(path, f"народ процедуры не совпадает с народом кампании {cid}")
        check_names(path, p, cid, campaigns.get(cid), techniques.get(tid))
        check_prose(path, p.get("description"))
    for path, c in data["campaigns"].items():
        if not isinstance(c, dict):
            continue
        check_refs(path, c, (("associated_campaigns", campaigns),))
        for a in kbformat.as_list(c.get("associated_campaigns")):
            if a not in campaigns:
                err(path, f"связанная кампания {a} не существует")
        if parent_of.get(str(c.get("id"))) and campaigns[parent_of[str(c["id"])]].get("people") != c.get("people"):
            err(path, f"народ эпизода не совпадает с народом родителя {parent_of[str(c['id'])]}")
        check_cit_list(path, c.get("first_seen_citation"), "first_seen_citation")
        check_cit_list(path, c.get("last_seen_citation"), "last_seen_citation")
        check_prose(path, c.get("description"))

    # 4. unpublished/ - то, чего на сайте нет:
    # та же раскладка, проверяется только форма (YAML, схема, имя файла = id); ссылки и сноски не требуются
    unp_root = os.path.join(root, "unpublished")
    unp_counts = {}
    if os.path.isdir(unp_root):
        unp_errors = []
        unp_data, _, _ = load_all(unp_root, unp_errors)
        for e in unp_errors:
            # процедура не на сайте, а её кампания на сайте: папка в unpublished/ без описания - законна
            m = re.match(r"campaigns/(?:.*/)?(C\d{4}): нет файла описания", e)
            if m and str(m.group(1)) in campaigns:
                continue
            errors.append(f"unpublished/{e}")
        for kind, files in unp_data.items():
            validator = jsonschema.Draft202012Validator(schemas[kind])
            for path, doc in files.items():
                if isinstance(doc, Exception):
                    err(path, f"YAML не читается: {doc}")
                    continue
                for e in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
                    where = "/".join(str(p) for p in e.path) or "<корень>"
                    err(path, f"схема: {where}: {e.message}")
                stem = os.path.splitext(os.path.basename(path))[0]
                if isinstance(doc, dict) and str(doc.get("id")) != stem:
                    err(path, f"имя файла «{stem}» не совпадает с id «{doc.get('id')}»")
                if kind == "procedures" and isinstance(doc, dict):
                    cid = stem.split(".")[0]
                    unp_camp = next((c for c in unp_data["campaigns"].values() if isinstance(c, dict) and c.get("id") == cid), None)
                    check_names(path, doc, cid, unp_camp or campaigns.get(cid), techniques.get(kbformat.ref_id(doc.get("technique"))))
        unp_counts = {k: len(v) for k, v in unp_data.items() if v}

    counts = {k: len(v) for k, v in data.items()}
    print("файлов:", counts, "| карточек в архиве:", len(materials))
    if unp_counts:
        print("unpublished/ (не на сайте, проверена только форма):", unp_counts)
    if no_card:
        numbers = sorted({k for _, k in no_card}, key=int)
        print(f"\nсносок на номера без карточки в архиве: {len(no_card)}, номеров: {len(numbers)} (не ошибка: карточка выходит после merge)")
        print("  " + ", ".join(numbers))
    if pending:
        print(f"\nИСТОЧНИКИ НА ПРИЁМКЕ: {len(pending)} (PR ждёт номера карточек)")
        for path, k in pending:
            print(f" - {os.path.relpath(path, root)}: (Citation: {k})")
        errors.append(f"источников без номера карточки: {len(pending)}")
    if errors:
        print(f"\nОШИБОК: {len(errors)}")
        for e in errors:
            print(" -", e)
        return 1
    print("ошибок нет")
    return 0


if __name__ == "__main__":
    sys.exit(main(os.path.abspath(sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(__file__), ".."))))
