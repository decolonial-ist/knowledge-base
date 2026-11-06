#!/usr/bin/env python3
"""Копия мастер-таблицы Google в файлы базы знаний. Таблицу не трогает.

Устройство файлов - WORK/framework/KNOWLEDGE_BASE_REPO_DESIGN_2026-11-02.md, раздел 5.

    .venv/bin/python scripts/copy_from_sheet.py --out ~/tmp/knowledge-base [--allow-missing-citations]

Читает листы читающим ключом (~/tmp/colonial-sheet-automation/reader-key.json), пишет:
  tactics/ techniques/ actors/ tools/ campaigns/<C>/<C>.yml + campaigns/<C>/<C>.<T>.yml
Карточки материалов не пишет: они в архиве; «Список материалов» читается только для перевода ключей сносок в номера.
После копии прогнать scripts/procedure_names.py: поля campaign_name / technique_name процедур копия не пишет.
Опубликованное («to be published» = TRUE) - в --out, остальное - в --out/unpublished той же раскладкой
(куратор 03.11: «unpublished ок. переноси туда»; сайт и экспортёр эту папку не читают). Отчёт - COPY_REPORT.md в --out.
Таблица с 03.11 только для чтения, её известные ошибки чинятся при копии (FIXES).
Папки сущностей в --out перед записью очищаются; scripts/ и schema/ не трогаются.

Сноски «(Citation: Название Год)» переводятся в номера материалов. Ключ, которого нет
в «Списке материалов», останавливает копирование (список в отчёте); --allow-missing-citations
оставляет такие маркеры как есть.
"""
import argparse
import collections
import datetime as dt
import os
import re
import shutil
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbformat  # noqa: E402

SPREADSHEET_ID = "1Y698opD_q76wdCji-Rz_KW6CztQBkptKr45slxzAf_E"
READER_KEY = os.path.expanduser("~/tmp/colonial-sheet-automation/reader-key.json")
ENTITY_DIRS = ("tactics", "techniques", "actors", "tools", "campaigns")

# народ: лист кампаний, лист процедур, слаг (как у матриц сайта)
PEOPLES = [
    {"slug": "nokhchi", "campaigns": "Кампании Нохчи", "procs": "Процедуры Нохчи"},
    {"slug": "ukrainians", "campaigns": "Кампании Украина", "procs": "Процедуры Украина"},
]
# «Колонизированный народ» листа материалов Архивариус ведёт землями («Чечня»); в файле - слаг народа
PEOPLE_SLUG = {"Нохчи": "nokhchi", "Нохчи (Чеченцы)": "nokhchi", "Чеченцы": "nokhchi", "Чечня": "nokhchi",
               "Украинцы": "ukrainians", "Украина": "ukrainians", "ukraina": "ukrainians", "Несколько": "several"}
SHEET_TECHS, SHEET_TACTICS = "Техники | Techniques", "Тактики | Tactics"
SHEET_GROUPS, SHEET_TOOLS, SHEET_MATERIALS = "Акторы | Groups", "Инструменты | Tools", "Список материалов"
OLD_TACTIC_ALIASES = {"нейтрализация защиты": "ослабление защиты"}
LANGS = ("en", "uk", "ru")

report = collections.defaultdict(list)


# ---------------------------------------------------------------- чтение таблицы

def read_all():
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    creds = service_account.Credentials.from_service_account_file(
        READER_KEY, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
    svc = build("sheets", "v4", credentials=creds)
    names = [SHEET_TECHS, SHEET_TACTICS, SHEET_GROUPS, SHEET_TOOLS, SHEET_MATERIALS]
    for p in PEOPLES:
        names += [p["campaigns"], p["procs"]]
    tabs = {}
    for n in names:
        values = svc.spreadsheets().values().get(spreadsheetId=SPREADSHEET_ID, range=f"'{n}'").execute().get("values", [])
        header = [h.strip() for h in values[0]]
        rows = []
        for r in values[1:]:
            r = (r + [""] * len(header))[:len(header)]
            if any(c.strip() for c in r):
                rows.append(dict(zip(header, (c.strip() for c in r))))
        tabs[n] = rows
    return tabs


def col(row, *names):
    """Значение по первому найденному имени колонки; терпит «(uk)» и « uk»."""
    for n in names:
        if n in row:
            return row[n]
        n2 = re.sub(r"\s*\((\w+)\)$", r" \1", n)
        if n2 in row:
            return row[n2]
    return ""


def published(row):
    return col(row, "to be published").upper() == "TRUE"


# ---------------------------------------------------------------- преобразования

def iso_date(text, ctx):
    text = (text or "").strip()
    if not text:
        return None
    for fmt in ("%d %B %Y", "%d.%m.%Y", "%Y-%m-%d", "%B %d, %Y"):
        try:
            return dt.datetime.strptime(text, fmt).date()   # объект даты: в YAML без кавычек
        except ValueError:
            pass
    report["даты, которые не разобрались (оставлены строкой)"].append(f"{ctx}: {text!r}")
    return text


def version(text):
    v = (text or "").strip().replace(",", ".")
    return v if v else "1.0"


def contributors(row):
    per_lang = {l: [c.strip() for c in col(row, f"contributors ({l})").split(";") if c.strip()] for l in LANGS}
    if not per_lang["ru"]:
        return []
    out = []
    for i, ru in enumerate(per_lang["ru"]):
        item = {"ru": ru}
        for l in ("en", "uk"):
            item[l] = per_lang[l][i] if i < len(per_lang[l]) else ru
        out.append(item)
    return out


class Citations:
    def __init__(self, materials):
        self.by_key = {}
        for m in materials:
            key = f"{col(m, 'Название')} {col(m, 'Год Публикации')}".strip()
            if key:
                self.by_key[re.sub(r"\s+", " ", key)] = col(m, "ID")
        self.missing = collections.Counter()

    def lookup(self, key):
        return self.by_key.get(re.sub(r"\s+", " ", key).strip())

    def convert_texts(self, texts, ctx):
        """texts: {lang: cell}. Маркеры en/uk подменяются русскими по позиции, как делает
        экспортёр (переводчики местами переводили ключи)."""
        ru_text, missing = kbformat.replace_citations(texts.get("ru", ""), self.lookup)
        for k in missing:
            self.missing[k] += 1
            report["сноски без материала (ru)"].append(f"{ctx}: {k}")
        ru_markers = [m.group(0) for m in kbformat.CIT_RE.finditer(ru_text)]
        out = {"ru": ru_text}
        for l in ("en", "uk"):
            t = texts.get(l, "")
            if not t:
                out[l] = ""
                continue
            markers = list(kbformat.CIT_RE.finditer(t))
            if len(markers) == len(ru_markers):
                parts, last = [], 0
                for m, ru_m in zip(markers, ru_markers):
                    parts += [t[last:m.start()], ru_m]
                    last = m.end()
                parts.append(t[last:])
                out[l] = "".join(parts)
            else:
                report["сноски: число маркеров в переводе не совпадает с русским (переведены по ключу)"].append(
                    f"{ctx} [{l}]: ru {len(ru_markers)}, {l} {len(markers)}")
                t2, miss = kbformat.replace_citations(t, self.lookup)
                for k in miss:
                    report[f"сноски без материала ({l})"].append(f"{ctx}: {k}")
                out[l] = t2
        return out


def prose(row, base, cits, ctx):
    texts = {l: col(row, f"{base} ({l})") or (col(row, base) if l == "ru" else "") for l in LANGS}
    texts = cits.convert_texts(texts, ctx)
    return {l: kbformat.cell_to_block(texts[l]) for l in LANGS}


def names(row):
    return {l: col(row, f"name ({l})") or (col(row, "name") if l == "ru" else "") for l in LANGS}


def meta(row, ctx):
    return {"created": iso_date(col(row, "created"), ctx), "modified": iso_date(col(row, "last modified"), ctx),
            "version": version(col(row, "version"))}


def write(outdir, sub, ident, data):
    path = os.path.join(outdir, sub)
    os.makedirs(path, exist_ok=True)
    with open(os.path.join(path, f"{ident}.yml"), "w", encoding="utf-8") as f:
        f.write(kbformat.dump_yaml(data))


def campaign_dir(cid, parents):
    """campaigns/C1193 для кампании, campaigns/C1193/C1198 для её эпизода: родство - местом в дереве."""
    chain, seen = [cid], {cid}
    while parents.get(chain[0]) and parents[chain[0]] not in seen:
        chain.insert(0, parents[chain[0]]); seen.add(chain[0])
    return os.path.join("campaigns", *chain)


# ---------------------------------------------------------------- сущности

def do_tactics(rows, cits, outs):
    name_to_id = {}
    for r in rows:
        tid = col(r, "ID")
        if not tid:
            continue
        name_to_id[col(r, "name (ru)").strip().lower()] = tid
        data = {"type": "tactic", "id": tid, **meta(r, tid), "shortname": col(r, "shortname"),
                "order": int(col(r, "order") or 0), "name": names(r),
                "description": prose(r, "description", cits, tid)}
        write(outs[published(r)], "tactics", tid, data)
    for alias, canon in OLD_TACTIC_ALIASES.items():
        if canon in name_to_id:
            name_to_id[alias] = name_to_id[canon]
    return name_to_id


def do_techniques(rows, cits, outs, tactic_ids):
    ids = set()
    for r in rows:
        tid = col(r, "ID")
        if not tid:
            continue
        ids.add(tid)
        tactics = []
        for t in col(r, "tactics").split(","):
            t = t.strip().lower()
            if not t:
                continue
            if t in tactic_ids:
                tactics.append(tactic_ids[t])
            else:
                report["техники: тактика не найдена"].append(f"{tid}: {t}")
        data = {"type": "technique", "id": tid, **meta(r, tid)}
        parent = col(r, "sub-technique of") or (tid.rsplit(".", 1)[0] if "." in tid else "")
        if parent:
            data["parent"] = parent
        data.update({"tactics": tactics, "name": names(r), "contributors": contributors(r),
                     "description": prose(r, "description", cits, tid)})
        write(outs[published(r)], "techniques", tid, data)
    return ids


def do_actors(rows, cits, outs):
    ids = set()
    for r in rows:
        gid = col(r, "ID")
        if not gid:
            continue
        ids.add(gid)
        data = {"type": "actor", "id": gid, **meta(r, gid), "name": names(r), "contributors": contributors(r)}
        if col(r, "associated groups"):
            data["associated_groups"] = [a.strip() for a in col(r, "associated groups").split(",") if a.strip()]
        data["description"] = prose(r, "description", cits, gid)
        write(outs[published(r)], "actors", gid, data)
    return ids


def do_tools(rows, cits, outs):
    ids = set()
    for r in rows:
        sid = col(r, "ID")
        if not sid:
            continue
        ids.add(sid)
        data = {"type": "tool", "id": sid, **meta(r, sid), "kind": col(r, "type") or "tool", "name": names(r),
                "contributors": contributors(r)}
        if col(r, "aliases"):
            data["aliases"] = [a.strip() for a in col(r, "aliases").split(",") if a.strip()]
        data["description"] = prose(r, "description", cits, sid)
        write(outs[published(r)], "tools", sid, data)
    return ids


def do_materials(rows, outs):
    for r in rows:
        mid = col(r, "ID")
        if not col(r, "Название"):
            continue
        formats = []
        if col(r, "PDF/DJVU?").upper() == "TRUE":
            formats.append("pdf")
        if col(r, "DOC/TXT/MD/FB2/EPUB/HTML?").upper() == "TRUE":
            formats.append("text")
        year = col(r, "Год Публикации")
        people_raw = col(r, "Колонизированный народ")
        data = {"type": "material", "id": int(mid), "title": col(r, "Название"),
                "year": int(year) if re.fullmatch(r"\d{4}", year) else (year or None),
                "author": col(r, "Автор") or None, "imprint": col(r, "выходные данные") or None,
                "shelfmark": col(r, "архивный шифр") or None,
                "people": PEOPLE_SLUG.get(people_raw, people_raw or None),
                "url": col(r, "url") or None,
                "archive": col(r, "ссылка на документ в архиве decolonial.ist") or None,
                "formats": formats,
                "publication_allowed": col(r, "разрешена ли публикация").upper() == "TRUE",
                "publication_basis": col(r, "основание, разрешающее публикацию") or None}
        if people_raw and data["people"] == people_raw:
            report["материалы: народ без слага (оставлен как в листе)"].append(f"{mid}: {people_raw}")
        write(outs[published(r)], "materials", mid, data)


def do_people(people, tabs, cits, outs, tech_ids, actor_ids, tool_ids):
    slug = people["slug"]
    camp_rows, proc_rows = tabs[people["campaigns"]], tabs[people["procs"]]
    camp_pub = {}
    # процедуры: id = кампания.техника; без кампании - актор.техника / инструмент.техника
    merged = {}
    for r in proc_rows:
        cid, tid = col(r, "source ID").upper(), col(r, "target technique ID")
        gid, sid = col(r, "source group id"), col(r, "source tool id")
        if not tid:
            if cid or col(r, "mapping description (ru)"):
                report["процедуры: строка без техники пропущена"].append(f"{people['procs']}: {cid} {col(r, 'mapping description (ru)')[:60]}")
            continue
        if tid not in tech_ids:
            report["процедуры: техника не найдена в листе техник"].append(f"{people['procs']}: {cid} {tid}")
        if gid and gid not in actor_ids:
            report["процедуры: актор не найден"].append(f"{cid}.{tid}: {gid}")
        if sid and sid not in tool_ids:
            report["процедуры: инструмент не найден"].append(f"{cid}.{tid}: {sid}")
        if not cid:
            report["процедуры: строка без кампании пропущена (процедура живёт только в кампании)"].append(f"{people['procs']}: {gid or sid} {tid}")
            continue
        pid = f"{cid}.{tid}"
        ctx = f"{pid} ({slug})"
        texts = prose(r, "mapping description", cits, ctx)
        if pid in merged:
            prev = merged[pid]
            report["процедуры: две строки одной техники в одной кампании слиты в один файл"].append(pid)
            for l in LANGS:
                if texts[l]:
                    prev["description"][l] = (prev["description"][l] + "\n\n\n" + texts[l]).strip() if prev["description"][l] else texts[l]
            prev["_published"] = prev["_published"] and published(r)
            continue
        data = {"type": "procedure", "id": pid, **meta(r, ctx), "campaign": cid}   # campaign - только для раскладки, в файл не идёт
        data["technique"] = tid
        data["people"] = slug
        data["actor"] = gid or None
        data["tool"] = FIXES.get(("tool", data["id"]), sid or None)
        data["contributors"] = contributors(r)
        data["description"] = texts
        data["_published"] = published(r)
        merged[pid] = data
    camp_ids = set()
    parents = {}
    for r in camp_rows:
        cid = col(r, "ID").upper()
        if cid:
            camp_pub[cid] = published(r)
            if col(r, "sub-campaign of"):
                parents[cid] = col(r, "sub-campaign of").upper()
    for r in camp_rows:
        cid = col(r, "ID").upper()
        if not cid:
            continue
        camp_ids.add(cid)
        data = {"type": "campaign", "id": cid, **meta(r, cid), "people": slug}
        if col(r, "associated campaigns"):
            data["associated_campaigns"] = [a.strip().upper() for a in col(r, "associated campaigns").split(",") if a.strip()]
        data["first_seen"] = iso_date(col(r, "first seen"), cid)
        fsc = [cits.lookup(k) or k for k in kbformat.citation_keys(col(r, "first seen citation"))]
        if fsc:
            data["first_seen_citation"] = fsc
        data["last_seen"] = iso_date(col(r, "last seen"), cid)
        lsc = [cits.lookup(k) or k for k in kbformat.citation_keys(col(r, "last seen citation"))]
        if lsc:
            data["last_seen_citation"] = lsc
        data["contributors"] = contributors(r)
        data["name"] = names(r)
        data["description"] = prose(r, "description", cits, cid)
        if not data["name"]["ru"] and not data["description"]["ru"]:
            report["пустые строки кампаний (только ID, без имени и описания) - файл не пишется"].append(cid)
            continue
        write(outs[published(r)], campaign_dir(cid, parents), cid, data)
    for pid, data in merged.items():
        cid = data.pop("campaign")
        if cid not in camp_ids:
            report["процедуры: кампания не найдена в листе кампаний"].append(pid)
        pub = data.pop("_published")
        if not camp_pub.get(cid, False):
            pub = False  # процедура неопубликованной кампании не публикуется
        write(outs[pub], campaign_dir(cid, parents), pid, data)   # имя файла = id: C1193.T0023.yml
    return len(camp_ids), len(merged)


# Известные ошибки закрытой таблицы, чинятся при копии (таблица только для чтения с 03.11):
# C1122.T0147 - в колонке source tool id стоит S0008, по имени инструмента рядом верно S0012 (куратор 03.11).
FIXES = {("tool", "C1122.T0147"): "S0012"}

# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", required=True)
    ap.add_argument("--out-unpublished", help="по умолчанию <out>/unpublished")
    ap.add_argument("--allow-missing-citations", action="store_true")
    a = ap.parse_args()
    out = os.path.expanduser(a.out)
    outs = {True: out, False: os.path.expanduser(a.out_unpublished) if a.out_unpublished else os.path.join(out, "unpublished")}
    for d in outs.values():
        for sub in ENTITY_DIRS:
            shutil.rmtree(os.path.join(d, sub), ignore_errors=True)

    tabs = read_all()
    cits = Citations(tabs[SHEET_MATERIALS])
    tactic_ids = do_tactics(tabs[SHEET_TACTICS], cits, outs)
    tech_ids = do_techniques(tabs[SHEET_TECHS], cits, outs, tactic_ids)
    actor_ids = do_actors(tabs[SHEET_GROUPS], cits, outs)
    tool_ids = do_tools(tabs[SHEET_TOOLS], cits, outs)
    # карточки материалов живут в архиве (decolonial-ist/archive, registry.json), в базу знаний не копируются
    counts = {p["slug"]: do_people(p, tabs, cits, outs, tech_ids, actor_ids, tool_ids) for p in PEOPLES}

    lines = [f"# Отчёт копирования таблицы в файлы, {dt.date.today().isoformat()}", "",
             f"Тактик: {len(set(tactic_ids.values()))}, техник: {len(tech_ids)}, акторов: {len(actor_ids)}, "
             f"инструментов: {len(tool_ids)}; ключей материалов для сносок: {len(cits.by_key)}.", ""]
    for slug, (nc, np_) in counts.items():
        lines.append(f"- {slug}: кампаний {nc}, процедур {np_}")
    lines.append("")
    for k, v in report.items():
        lines += [f"## {k} ({len(v)})", ""] + [f"- {x}" for x in sorted(set(v))] + [""]
    os.makedirs(outs[True], exist_ok=True)
    with open(os.path.join(outs[True], "COPY_REPORT.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print("\n".join(lines[:8]))
    for k, v in report.items():
        print(f"{k}: {len(v)}")
    if cits.missing and not a.allow_missing_citations:
        sys.exit(f"ОСТАНОВЛЕНО: {len(cits.missing)} ключей сносок нет в «Списке материалов» - см. COPY_REPORT.md")


if __name__ == "__main__":
    main()
