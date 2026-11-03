#!/usr/bin/env python3
"""Механическая проверка базы знаний (CI и локально): форма файлов, ссылки, сноски.

    .venv/bin/python scripts/validate.py [КОРЕНЬ]        # по умолчанию - корень репозитория

Проверяет (WORK/framework/KNOWLEDGE_BASE_REPO_DESIGN_2026-11-02.md, раздел 7, пп. 1-3):
  1. каждый файл - по своей JSON Schema из schema/ (обязательные поля, типы, форматы, лишние поля);
     имя файла совпадает с полем id;
  2. ссылки существуют: тактики техник, родитель подтехники, кампания/техника/актор/инструмент
     процедуры, родитель кампании; список procedures кампании совпадает с файлами процедур;
  3. сноски (Citation: N) ведут на карточку N в реестре архива (registry.json с archive.decolonial.ist
     или локальный файл через KB_REGISTRY); в трёх языках одной прозы - одинаковый набор сносок;
     сноски дат кампании тоже существуют. Сноска не по номеру - ссылка, библиография словами или файл
     в sources/ - это источник на приёмке у Архивариуса: PR не мержится, пока он не выдаст номер.
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
LANGS = ("ru", "en", "uk")


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

    def check_prose(path, prose):
        if not isinstance(prose, dict):
            return
        sets = {}
        for lang in LANGS:
            keys = kbformat.citation_keys(prose.get(lang) or "")
            for k in keys:
                if re.fullmatch(r"\d+", k):
                    if k not in materials:
                        err(path, f"сноска на номер, которого нет в архиве: {k}")
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

    def check_cit_list(path, lst, field):
        for k in lst or []:
            if str(k) not in materials:
                err(path, f"{field}: сноска на несуществующий материал: {k}")

    # 2-3. ссылки и сноски
    for path, t in data["techniques"].items():
        if not isinstance(t, dict):
            continue
        for ta in t.get("tactics") or []:
            if ta not in tactics:
                err(path, f"тактика {ta} не существует")
        if t.get("parent") and t["parent"] not in techniques:
            err(path, f"родитель {t['parent']} не существует")
        if "." in str(t.get("id")) and not t.get("parent"):
            err(path, "у подтехники нет поля parent")
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
        if p.get("technique") not in techniques:
            err(path, f"техника {p.get('technique')} не существует")
        if p.get("actor") and p["actor"] not in actors:
            err(path, f"актор {p['actor']} не существует")
        if p.get("tool") and p["tool"] not in tools:
            err(path, f"инструмент {p['tool']} не существует")
        if f"{cid}.{p.get('technique')}" != str(p.get("id")):
            err(path, f"id должен быть «{cid}.{p.get('technique')}» (кампания.техника)")
        if cid in campaigns and campaigns[cid].get("people") != p.get("people"):
            err(path, f"народ процедуры не совпадает с народом кампании {cid}")
        check_prose(path, p.get("description"))
    for path, c in data["campaigns"].items():
        if not isinstance(c, dict):
            continue
        for a in c.get("associated_campaigns") or []:
            if a not in campaigns:
                err(path, f"связанная кампания {a} не существует")
        if parent_of.get(str(c.get("id"))) and campaigns[parent_of[str(c["id"])]].get("people") != c.get("people"):
            err(path, f"народ эпизода не совпадает с народом родителя {parent_of[str(c['id'])]}")
        check_cit_list(path, c.get("first_seen_citation"), "first_seen_citation")
        check_cit_list(path, c.get("last_seen_citation"), "last_seen_citation")
        check_prose(path, c.get("description"))

    # 4. unpublished/ - то, чего на сайте нет (куратор 03.11: «unpublished ок. переноси туда»):
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
        unp_counts = {k: len(v) for k, v in unp_data.items() if v}

    counts = {k: len(v) for k, v in data.items()}
    print("файлов:", counts, "| карточек в архиве:", len(materials))
    if unp_counts:
        print("unpublished/ (не на сайте, проверена только форма):", unp_counts)
    if pending:
        print(f"\nИСТОЧНИКИ НА ПРИЁМКЕ У АРХИВАРИУСА: {len(pending)} (PR ждёт номера карточек)")
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
