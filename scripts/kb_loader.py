"""Загрузчик базы знаний для экспортёра: файлы -> таблицы тех же листов, что отдавала Google.

Экспортёр (colonial_stix) после `load_tab()` ничего не знает об источнике: он получает
DataFrame с колонками листа. Этот модуль собирает такие DataFrame из YAML-файлов, чтобы
бандлы из файлов совпадали с бандлами из таблицы побайтно. Обратные преобразования:
  проза файла -> текст ячейки (kbformat.block_to_cell);
  (Citation: 1068) -> (Citation: Название Год) по карточкам архива (registry.json);
  даты ISO -> «D Month YYYY»; тактики по ID -> русские имена; контрибьюторы -> «a; b».
Когда экспортёр переучится на номера сносок и ISO-даты, эти шаги уйдут.
"""
import datetime as dt
import glob
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbformat  # noqa: E402

LANGS = ("ru", "en", "uk")
PEOPLE_BY_SHEET = {"Кампании Нохчи": "nokhchi", "Процедуры Нохчи": "nokhchi",
                   "Кампании Украина": "ukrainians", "Процедуры Украина": "ukrainians"}

HEADERS = {
    "Тактики | Tactics": ["to be published", "ID", "STIX ID", "name (ru)", "name (en)", "name (uk)",
                          "description (ru)", "description (en)", "description (uk)", "shortname", "order",
                          "created", "last modified", "domain"],
    "Техники | Techniques": ["to be published", "ID", "name (ru)", "name (en)", "name (uk)", "description (ru)",
                             "description (en)", "description (uk)", "tactics", "contributors (ru)",
                             "contributors (en)", "contributors (uk)", "url", "created", "last modified", "domain",
                             "version", "is sub-technique", "platforms", "sub-technique of", "relationship citations"],
    "Акторы | Groups": ["to be published", "ID", "STIX ID", "name (ru)", "name (en)", "name (uk)", "description (ru)",
                        "description (en)", "description (uk)", "contributors (ru)", "contributors (en)",
                        "contributors (uk)", "url", "created", "last modified", "domain", "version",
                        "associated groups", "associated groups citations", "relationship citations"],
    "Инструменты | Tools": ["to be published", "ID", "STIX ID", "name (ru)", "name (en)", "name (uk)",
                            "description (ru)", "description (en)", "description (uk)", "contributors (ru)",
                            "contributors (en)", "contributors (uk)", "url", "created", "last modified", "domain",
                            "version", "platforms", "aliases", "type", "relationship citations"],
    "campaigns": ["to be published", "ID", "STIX ID", "name (ru)", "name (en)", "name (uk)", "description (ru)",
                  "description (en)", "description (uk)", "contributors (ru)", "contributors (en)", "contributors (uk)",
                  "url", "created", "last modified", "domain", "version", "associated campaigns",
                  "associated campaigns citations", "first seen", "first seen citation", "last seen",
                  "last seen citation", "relationship citations", "sub-campaign of"],
    "procedures": ["to be published", "source ID", "source name (ru)", "source group id", "source group name (ru)",
                   "source tool id", "source tool name (ru)", "target technique ID", "target technique name (ru)",
                   "mapping description (ru)", "mapping description (en)", "mapping description (uk)",
                   "contributors (ru)", "contributors (en)", "contributors (uk)", "created", "last modified"],
    "Список материалов": ["to be published", "Название", "Год Публикации", "Автор", "выходные данные",
                          "архивный шифр", "PDF/DJVU?", "DOC/TXT/MD/FB2/EPUB/HTML?", "Колонизированный народ",
                          "url", "разрешена ли публикация", "основание, разрешающее публикацию",
                          "цитируется в базе", "должно быть в нашем архиве?", "ЗАДАЧА НА ПУБЛИКАЦИЮ В АРХИВ",
                          "ссылка на документ в архиве decolonial.ist", "ID"],
}


REGISTRY_URL = "https://archive.decolonial.ist/registry.json"
REGISTRY_DEFAULT = os.environ.get("KB_REGISTRY") or REGISTRY_URL   # локальный файл - только для отладки
def load_registry(path=None):
    """Карточки архива из registry.json сайта (или клона): {id: {title, year, author, source, card, ...}}.
    Выходные данные и шифр берутся из полей imprint / shelfmark реестра, когда Архивариус их добавит (NOTICE 03.11)."""
    import json
    path = path or REGISTRY_DEFAULT
    if path.startswith("http"):
        import urllib.request
        with urllib.request.urlopen(path, timeout=60) as r:
            reg = json.load(r)
    else:
        reg = json.load(open(path, encoding="utf-8"))
    mats = {m["id"]: dict(m) for m in reg["materials"]}
    return mats


class KnowledgeBase:
    def __init__(self, root, registry=None):
        self.root = root
        self.cache = {}
        self.materials = load_registry(registry)
        self.cit_key = {mid: f"{m['title']} {m.get('year') or ''}".strip() for mid, m in self.materials.items()}
        self.tactics = {t["id"]: t for t in self._load("tactics")}
        self.techniques = {t["id"]: t for t in self._load("techniques")}
        self.actors = {a["id"]: a for a in self._load("actors")}
        self.tools = {t["id"]: t for t in self._load("tools")}
        self.campaigns, self.procedures = {}, []
        self._walk_campaigns(os.path.join(root, "campaigns"), None)

    def _walk_campaigns(self, d, parent):
        """campaigns/C1193/C1193.yml - кампания, C1193.T*.yml рядом - её процедуры, C*/ внутри - эпизоды."""
        for name in sorted(os.listdir(d)):
            path = os.path.join(d, name)
            if os.path.isdir(path) and re.fullmatch(r"C\d{4}", name):
                c = kbformat.load_yaml(os.path.join(path, f"{name}.yml"))
                c["parent"] = parent
                c["file"] = os.path.relpath(os.path.join(path, f"{name}.yml"), self.root)
                self.campaigns[name] = c
                for f in sorted(os.listdir(path)):
                    if re.fullmatch(rf"{name}\.T\d{{4}}(\.\d{{3}})?\.yml", f):
                        p = kbformat.load_yaml(os.path.join(path, f))
                        p["campaign"] = name
                        p["file"] = os.path.relpath(os.path.join(path, f), self.root)
                        self.procedures.append(p)
                self._walk_campaigns(path, name)

    def _load(self, sub):
        if sub not in self.cache:
            self.cache[sub] = [kbformat.load_yaml(p) for p in sorted(glob.glob(os.path.join(self.root, sub, "*.yml")))]
        return self.cache[sub]

    # ---- обратные преобразования

    def cell(self, block):
        text = kbformat.block_to_cell(block or "")

        def repl(m):
            key = m.group(1).strip()
            if re.fullmatch(r"\d+", key) and int(key) in self.cit_key:
                return f"(Citation: {self.cit_key[int(key)]})"
            return m.group(0)
        return kbformat.CIT_RE.sub(repl, text)

    @staticmethod
    def date(v):
        if v is None or v == "":
            return ""
        if isinstance(v, (dt.date, dt.datetime)):
            return f"{v.day} {v.strftime('%B %Y')}"
        return str(v)

    @staticmethod
    def contribs(lst, lang):
        return "; ".join(c.get(lang) or c["ru"] for c in (lst or []))

    def cit_list(self, lst):
        return "".join(f"(Citation: {self.cit_key.get(int(k), k) if str(k).isdigit() else k})" for k in (lst or []))

    def tri(self, d, base, prose=False):
        d = d or {}
        return {f"{base} ({l})": (self.cell(d.get(l)) if prose else (d.get(l) or "")) for l in LANGS}

    # ---- листы

    def rows(self, sheet):
        if sheet == "Тактики | Tactics":
            return [{"to be published": "TRUE", "ID": t["id"], **self.tri(t["name"], "name"),
                     **self.tri(t["description"], "description", True), "shortname": t["shortname"],
                     "order": str(t["order"]), "created": self.date(t.get("created")),
                     "last modified": self.date(t.get("modified")), "domain": "russia-colonialism",
                     "file": f"tactics/{t['id']}.yml"}
                    for t in self.tactics.values()]
        if sheet == "Техники | Techniques":
            out = []
            for t in self.techniques.values():
                out.append({"to be published": "TRUE", "ID": t["id"], **self.tri(t["name"], "name"),
                            **self.tri(t["description"], "description", True),
                            "tactics": ", ".join(self.tactics[x]["name"]["ru"] for x in t.get("tactics") or []),
                            **{f"contributors ({l})": self.contribs(t.get("contributors"), l) for l in LANGS},
                            "created": self.date(t.get("created")), "last modified": self.date(t.get("modified")),
                            "domain": "russia-colonialism", "version": t.get("version") or "1.0",
                            "is sub-technique": "TRUE" if t.get("parent") else "FALSE",
                            "sub-technique of": t.get("parent") or "", "file": f"techniques/{t['id']}.yml"})
            return out
        if sheet == "Акторы | Groups":
            return [{"to be published": "TRUE", "ID": a["id"], **self.tri(a["name"], "name"),
                     **self.tri(a["description"], "description", True),
                     **{f"contributors ({l})": self.contribs(a.get("contributors"), l) for l in LANGS},
                     "created": self.date(a.get("created")), "last modified": self.date(a.get("modified")),
                     "domain": "russia-colonialism", "version": a.get("version") or "1.0",
                     "associated groups": ", ".join(a.get("associated_groups") or []),
                     "file": f"actors/{a['id']}.yml"}
                    for a in self.actors.values()]
        if sheet == "Инструменты | Tools":
            return [{"to be published": "TRUE", "ID": s["id"], **self.tri(s["name"], "name"),
                     **self.tri(s["description"], "description", True),
                     **{f"contributors ({l})": self.contribs(s.get("contributors"), l) for l in LANGS},
                     "created": self.date(s.get("created")), "last modified": self.date(s.get("modified")),
                     "domain": "russia-colonialism", "version": s.get("version") or "1.0",
                     "aliases": ", ".join(s.get("aliases") or []), "type": s.get("kind") or "tool",
                     "file": f"tools/{s['id']}.yml"}
                    for s in self.tools.values()]
        if sheet == "Список материалов":
            out = []
            for m in self.materials.values():
                out.append({"to be published": "TRUE", "Название": m["title"], "Год Публикации": str(m.get("year") or ""),
                            "Автор": m.get("author") or "", "выходные данные": m.get("imprint") or "",
                            "архивный шифр": m.get("shelfmark") or "",
                            "Колонизированный народ": m.get("people") or "",
                            "url": m.get("source") or "",
                            "разрешена ли публикация": "TRUE" if m.get("published") else "FALSE",
                            "основание, разрешающее публикацию": m.get("basis") or "",
                            "ссылка на документ в архиве decolonial.ist": m.get("card") or "",
                            "ID": str(m["id"])})
            return out
        people = PEOPLE_BY_SHEET.get(sheet)
        if sheet.startswith("Кампании"):
            out = []
            for c in self.campaigns.values():
                if c.get("people") != people:
                    continue
                out.append({"to be published": "TRUE", "ID": c["id"], **self.tri(c["name"], "name"),
                            **self.tri(c["description"], "description", True),
                            **{f"contributors ({l})": self.contribs(c.get("contributors"), l) for l in LANGS},
                            "created": self.date(c.get("created")), "last modified": self.date(c.get("modified")),
                            "domain": "russia-colonialism", "version": c.get("version") or "1.0",
                            "associated campaigns": ", ".join(c.get("associated_campaigns") or []),
                            "first seen": self.date(c.get("first_seen")),
                            "first seen citation": self.cit_list(c.get("first_seen_citation")),
                            "last seen": self.date(c.get("last_seen")),
                            "last seen citation": self.cit_list(c.get("last_seen_citation")),
                            "sub-campaign of": c.get("parent") or "", "file": c.get("file", "")})
            return out
        if sheet.startswith("Процедуры"):
            out = []
            for p in self.procedures:
                if p.get("people") != people:
                    continue
                camp = self.campaigns.get(p.get("campaign") or "")
                out.append({"to be published": "TRUE", "source ID": p.get("campaign") or "",
                            "source name (ru)": camp["name"]["ru"] if camp else "",
                            "source group id": p.get("actor") or "",
                            "source group name (ru)": self.actors[p["actor"]]["name"]["ru"] if p.get("actor") in self.actors else "",
                            "source tool id": p.get("tool") or "",
                            "source tool name (ru)": self.tools[p["tool"]]["name"]["ru"] if p.get("tool") in self.tools else "",
                            "target technique ID": p["technique"],
                            "target technique name (ru)": self.techniques[p["technique"]]["name"]["ru"] if p["technique"] in self.techniques else "",
                            **self.tri(p["description"], "mapping description", True),
                            **{f"contributors ({l})": self.contribs(p.get("contributors"), l) for l in LANGS},
                            "created": self.date(p.get("created")), "last modified": self.date(p.get("modified")),
                            "file": p.get("file", "")})
            return out
        raise KeyError(f"лист «{sheet}» загрузчику неизвестен")

    def dataframe(self, sheet):
        """DataFrame как у load_tab_api: все колонки листа, пустые ячейки - NA."""
        import pandas as pd
        kind = "campaigns" if sheet.startswith("Кампании") else "procedures" if sheet.startswith("Процедуры") else sheet
        # «file» - колонка только файловой базы: путь файла сущности для кнопки «Предложить правку»
        header = HEADERS[kind] + (["file"] if kind != "Список материалов" else [])
        rows = [[r.get(h, "") for h in header] for r in self.rows(sheet)]
        df = pd.DataFrame(rows, columns=header, dtype=str)
        return df.replace("", pd.NA)
