"""Формат файлов базы знаний: запись YAML и преобразование прозы.

Общее для копирования таблицы в файлы и для загрузчика экспортёра
(WORK/framework/KNOWLEDGE_BASE_REPO_DESIGN_2026-11-02.md, раздел 5).

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
# Сокращения перед числами (гг., вв., тыс., с., стр., рис., табл., №, vol., p.) сюда не входят: разрыв ищется
# только перед заглавной, а «1994-1996 гг. Затем…» - настоящий конец фразы (04.11: «рис. Жертва» не делилось).
_ABBR_RE = re.compile(r"(?:^|[\s(«„\"'])(?:" + _ABBR + r")\.$", re.IGNORECASE)
# инициал: одиночная заглавная с точкой («А.», «Е. Н.»)
_INITIAL_RE = re.compile(r"(?:^|[\s(«„\"'])[А-ЯЁІЇЄҐA-Z]\.$")
# место разрыва: конец фразы, пробелы, начало следующей с заглавной или кавычки
# закрывающая кавычка или скобка считается концом фразы только после знака конца («labels.” The…»);
# «“subhumans,” “militants,”» - перечень, не разрыв (04.11)
_BREAK_RE = re.compile(
    r"(?:(?<=[.!?…])|(?<=[.!?…][»\"”)\]])|(?<=[.!?…][»\"”)\]][»\"”)\]]))\s+(?=[А-ЯЁІЇЄҐA-Z«„\"“])"
)


def split_sentences(paragraph: str) -> list[str]:
    """Абзац -> фразы. Ошибочный разрыв безвреден: загрузчик склеит строки пробелом.

    Сноски на время разбивки прячутся за метки: внутри ключа «Название Год» бывают
    точки и заглавные, рвать его нельзя."""
    cits = []

    def hide(m):
        cits.append(m.group(0))
        return f"\x00{len(cits) - 1}\x00"

    masked = CIT_RE.sub(hide, paragraph)
    out, start = [], 0
    for m in _BREAK_RE.finditer(masked):
        before = masked[start:m.start()]
        if _ABBR_RE.search(before) or _INITIAL_RE.search(before):
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
    return "\n".join(" ".join(line.strip() for line in p.split("\n")).strip() for p in paras)
