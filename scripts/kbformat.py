"""Формат файлов базы знаний: запись YAML и преобразование прозы.

Общее для копирования таблицы в файлы и для загрузчика экспортёра.

Проза в файле: Markdown в блоке `|`, одна фраза - одна строка, абзацы через пустую строку.
Текст ячейки таблицы: абзацы через `\n` (сайт рисует `<br>` по nl2br), фраз по строкам нет.
Преобразование обратимо:
  ячейка -> файл: абзац (строка ячейки) отделяется пустой строкой, пустые строки ячейки не
                  переносятся; внутри абзаца фразы разводятся одиночным `\n`;
  файл -> ячейка: `\n\n` -> `\n`, оставшиеся одиночные `\n` -> пробел.
"""
import re

import yaml

# ---------------------------------------------------------------- YAML

class _Dumper(yaml.SafeDumper):
    pass


def _str_representer(dumper, value):
    if "\n" in value:
        # блок `|`: многострочная проза; хвостовые пробелы в строках YAML не переживёт
        value = "\n".join(line.rstrip() for line in value.split("\n"))
        return dumper.represent_scalar("tag:yaml.org,2002:str", value, style="|")
    return dumper.represent_scalar("tag:yaml.org,2002:str", value)


_Dumper.add_representer(str, _str_representer)


def dump_yaml(data) -> str:
    return yaml.dump(data, Dumper=_Dumper, allow_unicode=True, sort_keys=False,
                     width=10**9, default_flow_style=False)


# Порядок полей в начале файла процедуры: кампания сразу за id, дальше техника,
# народ, акторы и инструменты; у каждой ссылки название стоит под номером - человек видит, о чём текст,
# не открывая другие файлы. Поля, которых тут нет, идут дальше в том порядке, в каком были.
FIELD_ORDER = ("type", "id", "campaign", "created", "modified", "version", "technique", "people", "actor", "tool")
# прежний вид процедуры: названия отдельными полями; procedure_names.py переносит их под номера
LEGACY_NAME_FIELDS = ("campaign_name", "technique_name", "actor_name", "tool_name")


def order_fields(doc: dict) -> dict:
    ordered = {k: doc[k] for k in FIELD_ORDER if k in doc}
    ordered.update({k: v for k, v in doc.items() if k not in ordered})
    return ordered


def ref_id(v):
    """Номер из поля-ссылки с одним значением (technique, campaign): «T0023» или {«T0023»: название} -> «T0023»."""
    ids = as_list(v)
    return ids[0] if ids else None


def as_list(v):
    """Номера из поля-ссылки процедуры (campaign, technique, actor, tool): словарь «номер: название»,
    список номеров или один номер строкой -> список номеров в том же порядке."""
    if v is None or v == "":
        return []
    if isinstance(v, dict):
        return [str(k) for k in v]
    items = list(v) if isinstance(v, (list, tuple)) else [v]
    return [str(i.get("id") or "") if isinstance(i, dict) else i for i in items]


def load_yaml(path):
    with open(path, encoding="utf-8") as f:
        return yaml.safe_load(f)


# ---------------------------------------------------------------- сноски

# тот же размотанный паттерн, что в экспортёре: скобки внутри ключа до двух уровней
_P0 = r"[^()]+"
_P3 = r"\((?:[^()]+|\([^()]*\))*\)"
CIT_RE = re.compile(r"\((?:Citation|citation|Цитата):\s*((?:" + _P0 + r"|" + _P3 + r")*?)\s*\)")


def citation_keys(text: str) -> list[str]:
    return [m.group(1).strip() for m in CIT_RE.finditer(text or "")]


def replace_citations(text: str, mapping) -> tuple[str, list[str]]:
    """Ключи «Название Год» -> номера материалов; mapping(key) -> номер или None.

    Возвращает (текст, список ненайденных ключей)."""
    missing = []

    def repl(m):
        key = m.group(1).strip()
        if re.fullmatch(r"\d+", key):
            return f"(Citation: {key})"
        num = mapping(key)
        if num is None:
            missing.append(key)
            return m.group(0)
        return f"(Citation: {num})"

    return CIT_RE.sub(repl, text or ""), missing


# ---------------------------------------------------------------- проза

# после этих сокращений точка не кончает фразу (ru, uk, en)
_ABBR = r"""г|т|ст|им|ул|р|д|др|пр|е|см|ср|акад|проф|ген|кап|ред|сост|пер|св|ін|пров|обл|р-н|с-ще|смт|м
|Mr|Mrs|Ms|Dr|St|ed|eds|cf|e\.g|i\.e|repr|trans|Jr|Sr|Inc|Ltd|Co|Gen|Col|Lt|Capt|Sgt|Prof|Rev|Mt|Ft|U\.S|U\.K|a\.m|p\.m
""".replace("\n", "")
# В списке только сокращения, за которыми идёт слово с заглавной («г. Грозный», «им. Ленина», «ген. Ермолов»).
# Сокращения перед числами - в _NUM_ABBR: «1994-1996 гг. Затем…» - настоящий конец фразы.
_ABBR_RE = re.compile(r"(?:^|[\s(«„\"'])(?:" + _ABBR + r")\.$", re.IGNORECASE)
# после этих сокращений точка не кончает фразу, если дальше число («1994-1996 гг. 5 мая», «т. 2», «с. 45»,
# «ф. 1, оп. 2», «10 ч. 30 мин.», «p. 12», «Dec. 11»); перед заглавной они кончают фразу
_NUM_ABBR = r"""гг|вв|в|рр|с|стр|стор|л|лл|об|оп|ф|дд|спр|арк|тт|ч|кн|вып|п|пп|рис|табл|прим|гл|разд|ок
|No|Nos|Nr|vol|vols|p|pp|para|paras|art|arts|fig|ch|sec|n|nn|fn|fol|ff
|Jan|Feb|Mar|Apr|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec
""".replace("\n", "")
_NUM_ABBR_RE = re.compile(r"(?:^|[\s(«„\"'])(?:" + _NUM_ABBR + r")\.$", re.IGNORECASE)
# инициал: одиночная заглавная с точкой («А.», «Е. Н.»)
_INITIAL_RE = re.compile(r"(?:^|[\s(«„\"'])[А-ЯЁІЇЄҐA-Z]\.$")
# кандидат в разрыв: пробелы перед заглавной, кавычкой или цифрой
_GAP_RE = re.compile(r"\s+(?=[А-ЯЁІЇЄҐA-Z«„\"“0-9])")
# текст до разрыва кончается знаком конца фразы; за ним - до двух закрывающих кавычек или скобок
# («labels.” The…»; «“subhumans,” “militants,”» - перечень, не разрыв) и сноски («…не явились!»(Citation: 711) Зелимхан…»)
_END_RE = re.compile(r"[.!?…][»\"”)\]]{0,2}(?:\x00\d+\x00)*$")
_MASK_TAIL_RE = re.compile(r"(?:\x00\d+\x00)+$")


def _quote_depth(text: str):
    """Глубина кавычек в каждой позиции; None, если кавычки в абзаце не парные.

    „…“ - вложенные кавычки ru и uk, “…” - кавычки en: “ закрывает „ и открывает в остальных случаях;
    прямая " закрывает открытую прямую и открывает в остальных случаях."""
    depth, stack = [], []
    for ch in text:
        if ch == '"':
            if stack and stack[-1] == '"':
                stack.pop()
            else:
                stack.append(ch)
        elif ch in "«„":
            stack.append(ch)
        elif ch == "“":
            if stack and stack[-1] == "„":
                stack.pop()
            else:
                stack.append(ch)
        elif ch == "»":
            if not stack or stack.pop() != "«":
                return None
        elif ch == "”":
            if not stack or stack.pop() != "“":
                return None
        depth.append(len(stack))
    return depth if not stack else None


def split_sentences(paragraph: str) -> list[str]:
    """Абзац -> фразы. Ошибочный разрыв безвреден: загрузчик склеит строки пробелом.

    Сноски на время разбивки прячутся за метки: внутри ключа «Название Год» бывают
    точки и заглавные, рвать его нельзя. Цитата в кавычках из нескольких фраз
    остаётся на строке той фразы, в которой стоит; если кавычки в абзаце
    не парные, разрыв ищется и внутри них."""
    cits = []

    def hide(m):
        cits.append(m.group(0))
        return f"\x00{len(cits) - 1}\x00"

    masked = CIT_RE.sub(hide, paragraph)
    depth = _quote_depth(masked)
    out, start = [], 0
    for m in _GAP_RE.finditer(masked):
        if depth is not None and depth[m.start()]:
            continue
        before = masked[start:m.start()]
        if not _END_RE.search(before):
            continue
        core = _MASK_TAIL_RE.sub("", before)
        if _ABBR_RE.search(core) or _INITIAL_RE.search(core):
            continue
        if masked[m.end()].isdigit() and _NUM_ABBR_RE.search(core):
            continue
        out.append(before.strip())
        start = m.end()
    tail = masked[start:].strip()
    if tail:
        out.append(tail)
    out = out or [masked.strip()]
    return [re.sub(r"\x00(\d+)\x00", lambda m: cits[int(m.group(1))], s) for s in out]


def cell_to_block(text: str) -> str:
    """Текст ячейки таблицы -> проза файла (абзацы пустой строкой, фраза на строку)."""
    text = (text or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return ""
    # лишние пустые строки ячейки (два Enter подряд) не переносятся: абзац - одна пустая строка
    paras = [p.strip() for p in text.split("\n") if p.strip()]
    return "\n\n".join("\n".join(split_sentences(p)) for p in paras)


def block_to_cell(block: str) -> str:
    """Проза файла -> текст ячейки, как он лежал в таблице."""
    block = (block or "").strip("\n")
    paras = block.split("\n\n")
    # абзацы - пустой строкой, как в таблице: сайт (markdown) делает из них <p>; один перенос дал бы <br>
    return "\n\n".join(" ".join(line.strip() for line in p.split("\n")).strip() for p in paras)


def prose_key(text: str) -> str:
    """Проза без разбивки на строки: абзацы и слова как у загрузчика, пробелы схлопнуты.

    Две прозы с одним ключом на сайте одинаковы: отличаются только места переноса строк."""
    return "\n\n".join(" ".join(p.split()) for p in block_to_cell(text).split("\n\n"))
