#!/usr/bin/env python3
"""Экспорт базы знаний DECOLONIAL.IST в STIX 2.1 - три бандла (ru, en, uk) в dist/.

    python scripts/export_stix.py [--output dist/russia-colonialism.json] [--kb <каталог>] [--random-ids] [--now <ISO>]

Читает файлы базы знаний через kb_loader и реестр архива https://archive.decolonial.ist/registry.json
(библиография сносок). Те же бандлы собирает CI при каждом merge в main и кладёт в релиз `stix`:
https://github.com/decolonial-ist/knowledge-base/releases/download/stix/russia-colonialism.json (-en, -uk).
Сайт decolonial.ist при сборке скачивает их оттуда.

Код вырос из экспортёра Google-таблицы (colonial_stix, 2025-2026); таблица закрыта 03.11.2026,
--sheet читает её только для сравнений (нужен ключ чтения и google-api-python-client).
"""
import os
import sys
import pandas as pd
import uuid
import json
import re
from urllib.parse import urlsplit, urlunsplit, quote, unquote
from datetime import datetime, timezone
from stix2.v21 import AttackPattern, Campaign, IntrusionSet, Tool, Relationship, Identity, Bundle, CustomObject
from stix2.properties import StringProperty, ListProperty, DictionaryProperty, ReferenceProperty
# Политика кликабельности адресов, DEFAULT-DENY: кликабелен только белый список
# (hostile_domains.py; реестры — WORK/framework/WHITELIST_DRAFT.md и HOSTILE_DOMAINS.md)
from hostile_domains import is_clickable, visible

# --- Константы ---
SHEET_ID = "1Y698opD_q76wdCji-Rz_KW6CztQBkptKr45slxzAf_E"

# Домен сайта: подставляется в external_references всех объектов
SITE_BASE_URL = "https://decolonial.ist"

# Общие вкладки (одна на весь проект)
TABS = {
    "techniques": {"gid": "1589934536", "sheet": "Техники | Techniques"},
    "groups":     {"gid": "1786637573", "sheet": "Акторы | Groups"},
    "tools":      {"gid": "667175060",  "sheet": "Инструменты | Tools"},
    "sources":    {"gid": "1822320391", "sheet": "Список материалов"},
}

# Народы: у каждого — свои вкладки кампаний и процедур. Народ проставляется
# объектам из этого конфига; колонка platform в таблице больше НЕ читается.
# gid вкладки — число после #gid= в URL, когда вкладка открыта в браузере.
PEOPLES = [
    {
        "name": "Украинцы",
        "campaigns":  {"gid": "1495253412", "sheet": "Кампании Украина"},
        "procedures": {"gid": "1049395600", "sheet": "Процедуры Украина"},
    },
    {
        "name": "Нохчи (Чеченцы)",
        # gid'ы сверить в браузере (#gid= в URL вкладки): procedures взят из твоей
        # ссылки от 2026-07-09, campaigns — ВПИСАТЬ (для --xlsx режима gid не нужен)
        "campaigns":  {"gid": "17037405", "sheet": "Кампании Нохчи"},
        "procedures": {"gid": "298046596", "sheet": "Процедуры Нохчи"},
    },
]

# Языки экспорта: за один прогон пишутся три бандла — русский (OUTPUT_PATH),
# английский и украинский (суффиксы _en/_uk к имени файла). Переводы берутся из
# колонок «name (en)», «description (uk)» и т.п.; пустая ячейка -> русский текст.
# ВАЖНО: все STIX ID генерируются от РУССКИХ имён (id_cache общий на прогон),
# поэтому объекты трёх бандлов идентичны по ID и датам.
LANGS = ["ru", "en", "uk"]

# Народы (x_mitre_platforms) по языкам; значения должны совпадать со словарём
# сайта (data.people.* в attack-website/data/translations.json)
PEOPLE_I18N = {
    "Украинцы": {"ru": "Украинцы", "en": "Ukrainians", "uk": "Українці"},
    "Нохчи (Чеченцы)": {"ru": "Нохчи (Чеченцы)", "en": "Nokhchi (Chechens)", "uk": "Нохчі (Чеченці)"},
}

# Названия тактик по языкам (в таблице тактики живут только по-русски в колонке
# tactics); значения согласованы с data.tactic.*.name словаря сайта
TACTIC_I18N = {
    "легитимизация доминирования": {"en": "Legitimization of Domination", "uk": "Легітимізація домінування"},
    "подготовка к захвату": {"en": "Preparation for Seizure", "uk": "Підготовка до захоплення"},
    "захват управления": {"en": "Seizure of Governance", "uk": "Захоплення управління"},
    # TA0004: переименована в «Ослабление защиты» (переименуй и в гугл-таблице,
    # иначе RU-имя в бандле навигатора останется старым). Оба ключа — на время перехода.
    "ослабление защиты": {"en": "Defense Impairment", "uk": "Ослаблення захисту"},
    "нейтрализация защиты": {"en": "Defense Impairment", "uk": "Ослаблення захисту"},
    "закрепление": {"en": "Persistence", "uk": "Закріплення"},
    "извлечение выгоды": {"en": "Extraction of Benefits", "uk": "Отримання вигоди"},
}


def loc_people(ru_name, lang):
    return PEOPLE_I18N.get(ru_name, {}).get(lang, ru_name)


def loc_tactic(ru_name, lang):
    if lang == "ru":
        return ru_name
    return TACTIC_I18N.get(ru_name.lower().strip(), {}).get(lang, ru_name)


# Переименованные тактики: старое русское имя (может остаться в колонке tactics
# листа техник) -> текущее имя из листа «Тактики | Tactics»
OLD_TACTIC_ALIASES = {"нейтрализация защиты": "ослабление защиты"}


def sheet_version(row):
    """Версия сущности из колонки version листа (бампает autostamp/update_rows).

    Артефакты Sheets нормализуются: «1» -> «1.0», «1,1» -> «1.1»; пусто -> 1.0."""
    v = str(row.get('version', '') or '').strip().replace(',', '.')
    if not v or v.lower() == 'nan':
        return "1.0"
    if re.fullmatch(r'\d+', v):
        return f"{v}.0"
    return v if re.fullmatch(r'\d+\.\d+', v) else "1.0"

TACTICS_TAB = {"sheet": "Тактики | Tactics", "gid": "1686690875"}


def load_tactics_sheet():
    """Лист «Тактики | Tactics» -> DataFrame, либо None (фолбэк на хардкод).

    Создаётся bootstrap-скриптом ~/tmp/colonial-sheet-automation/make_tactics_sheet.py;
    после его появления лист — единственный источник тактик (имена/описания
    на трёх языках, честные created/last modified)."""
    try:
        df = load_tab(TACTICS_TAB)
        require_columns(df, ["ID", "name (ru)", "description (ru)", "shortname", "order", "created", "last modified"],
                        "Тактики | Tactics")
        return df
    except SystemExit:
        raise
    except Exception as e:
        print(f"[ТАКТИКИ] лист «Тактики | Tactics» не прочитан ({type(e).__name__}) — фолбэк на хардкод экспортера")
        return None


# Офлайн-режим: --xlsx <снимок таблицы.xlsx> читает вкладки из локального файла
# (по именам листов), --output <файл.json> меняет путь русского бандла
# (английский и украинский получают суффиксы _en/_uk).
XLSX_PATH = None
OUTPUT_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "dist", "russia-colonialism.json")   # имена - как на сайте


def output_path_for(lang):
    if lang == "ru":
        return OUTPUT_PATH
    base, ext = (OUTPUT_PATH.rsplit(".", 1) + ["json"])[:2]
    return f"{base}-{lang}.{ext}"

# Ошибки данных копятся сюда; при непустом списке экспорт падает, файл не пишется
export_errors = []

id_cache = {} # ОБЯЗАТЕЛЬНО ДОБАВИТЬ ЭТУ СТРОКУ

def safe_url(url_str):
    if not url_str or str(url_str).lower() == 'nan': 
        return ""
    p = urlsplit(str(url_str).strip())
    
    # Сначала декодируем (снимаем старые проценты), потом кодируем начисто
    safe_path = quote(unquote(p.path))
    safe_query = quote(unquote(p.query), safe="=&")
    safe_fragment = quote(unquote(p.fragment))
    
    return urlunsplit((p.scheme, p.netloc, safe_path, safe_query, safe_fragment))

def clean_name(text):
    # return re.sub(r'^([TtТт]\d+\.?\s*|\d+\.?\s*)', '', str(text)).strip()
    # внедряем поддержку сабтехник
    return re.sub(r'^([TtТт]?\d+(?:\.\d+)*\.?\s*)', '', str(text)).strip()

def get_csv_url(gid):
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={gid}"

# Читающий ключ (общий с ~/tmp/colonial-sheet-automation/read_table.py): сервис-аккаунт
# kavkaz-sheets-reader, только чтение (имя сервис-аккаунта в Google Cloud —
# оно НЕ менялось при переименовании репозитория). Если файл на месте — таблица читается
# через Sheets API (работает с закрытой таблицей); иначе фолбэк на публичный CSV.
READER_KEY_DEFAULT = os.path.expanduser("~/tmp/colonial-sheet-automation/reader-key.json")
KEY_PATH = READER_KEY_DEFAULT if os.path.exists(READER_KEY_DEFAULT) else None
_sheets_svc = None

# База знаний в файлах (knowledge-base, 02.11.2026): сущности читаются из YAML, загрузчик отдаёт
# DataFrame с колонками листа, дальше код общий. С 03.11.2026 файлы - источник правды, таблица закрыта:
# по умолчанию ~/tmp/knowledge-base (если каталог есть), --kb <каталог> - другой, --sheet - читать таблицу.
_HERE = os.path.dirname(os.path.abspath(__file__))
KB_DEFAULT = os.path.abspath(os.path.join(_HERE, ".."))        # scripts/ лежит в корне базы знаний
KB_DIR = KB_DEFAULT if os.path.isdir(os.path.join(KB_DEFAULT, "campaigns")) else None
_kb = None
# Идентификаторы STIX детерминированы: uuid5 от идентификатора сущности (TA0001, T0023, C1193, G0011,
# S0010), у связи - от типа, концов и хэша русского текста (04.11.2026: бандлы собирает CI базы знаний,
# ссылка на объект живёт от сборки к сборке). --random-ids - uuid4, как в старых бандлах;
# --now <ISO> фиксирует момент экспорта для побайтного сравнения.
STABLE_IDS = True    # --random-ids возвращает uuid4 (сравнения со старыми бандлами)
FIXED_NOW = None
KEEP_GOING = False   # --keep-going: ошибки данных печатать, бандл писать (только для сравнений)


def kb():
    global _kb
    if _kb is None:
        sys.path.insert(0, _HERE)
        import kb_loader
        _kb = kb_loader.KnowledgeBase(KB_DIR)
    return _kb


def _sheets_service():
    global _sheets_svc
    if _sheets_svc is None:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build as g_build
        creds = service_account.Credentials.from_service_account_file(
            KEY_PATH, scopes=["https://www.googleapis.com/auth/spreadsheets.readonly"])
        _sheets_svc = g_build("sheets", "v4", credentials=creds)
    return _sheets_svc


def load_tab_api(sheet_name):
    """Лист через Sheets API по читающему ключу -> DataFrame как у pd.read_csv(dtype=str)."""
    values = _sheets_service().spreadsheets().values().get(
        spreadsheetId=SHEET_ID, range=f"'{sheet_name}'").execute().get("values", [])
    if not values:
        raise RuntimeError(f"лист «{sheet_name}»: пусто")
    header = values[0]
    rows = [(r + [""] * len(header))[:len(header)] for r in values[1:]]
    df = pd.DataFrame(rows, columns=header, dtype=str)
    return df.replace("", pd.NA)  # пустые ячейки как NaN — в точности как pd.read_csv

_tab_cache = {}


def load_tab(tab):
    """tab = {"gid": ..., "sheet": ...}: Sheets API (ключ), гугл-CSV, либо лист xlsx (--xlsx).

    Кэшируется на прогон: build() зовётся трижды (по языку), таблицу читаем один раз.
    """
    if tab["sheet"] in _tab_cache:
        return _tab_cache[tab["sheet"]]
    if KB_DIR:
        df = kb().dataframe(tab["sheet"])
    elif XLSX_PATH:
        df = pd.read_excel(XLSX_PATH, sheet_name=tab["sheet"], dtype=str)
    elif KEY_PATH:
        df = load_tab_api(tab["sheet"])
    else:
        df = pd.read_csv(get_csv_url(tab["gid"]), dtype=str)
    if 'to be published' in df.columns:
        df = df[df['to be published'].astype(str).str.strip().str.upper() == 'TRUE']
    _tab_cache[tab["sheet"]] = df
    return df

def require_columns(df, cols, tab_label):
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise SystemExit(f"ЭКСПОРТ ОСТАНОВЛЕН: во вкладке «{tab_label}» нет колонок: {missing}")

def cell(row, col):
    """Значение ячейки без nan-мусора."""
    v = str(row.get(col, '')).strip()
    return '' if v.lower() == 'nan' else v


# Тот же unrolled-паттерн, что в extract_refs, но с внешними скобками маркера
CITATION_MARKER_RE = re.compile(
    r"\([CcСс]itation:\s*[^()]*(?:\((?:[^()]*(?:\([^()]*\)[^()]*)*)\)[^()]*)*\)", flags=re.IGNORECASE
)


def fix_citations(text_loc, text_ru, ctx=""):
    """Восстанавливает маркеры (Citation: …) в переводе из русского оригинала.

    Имена источников — идентификаторы «Списка материалов» и переводу не подлежат;
    переводчики местами их переводили. Если количество маркеров совпадает,
    подменяем каждый маркер перевода соответствующим (по порядку) русским;
    если не совпадает — перевод не трогаем и предупреждаем.
    """
    if not text_loc or not text_ru:
        return text_loc
    ru_markers = CITATION_MARKER_RE.findall(text_ru)
    loc_markers = CITATION_MARKER_RE.findall(text_loc)
    if ru_markers == loc_markers:
        return text_loc
    if len(ru_markers) != len(loc_markers):
        print(f"[ЦИТАТЫ {ctx}] число маркеров не совпадает с русским текстом "
              f"({len(loc_markers)} против {len(ru_markers)}) — оставляю как есть")
        return text_loc
    it = iter(ru_markers)
    return CITATION_MARKER_RE.sub(lambda m: next(it), text_loc)


def lcell(row, base, lang):
    """Локализованная ячейка: «<base> (<lang>)» с фолбэком на русский.

    Терпит оба стиля заголовков переводов — «mapping description (en)» и
    «mapping description en» (в «Процедурах Нохчи» скобок нет). Русская колонка
    после переименования — «<base> (ru)», старый голый «<base>» тоже понимаем.
    Маркеры (Citation: …) в переводе принудительно восстанавливаются из русского.
    """
    ru_text = cell(row, f"{base} (ru)") or cell(row, base)
    if lang != "ru":
        for col in (f"{base} ({lang})", f"{base} {lang}"):
            v = cell(row, col)
            if v:
                return fix_citations(v, ru_text, ctx=f"{base} ({lang})")
    return ru_text

def split_contributors(value):
    """Строка контрибьюторов -> список имён.

    Разделитель — ТОЧКА С ЗАПЯТОЙ (как в отображении на сайте): внутри одного
    имени запятая законна — «Имя Фамилия, организация» или пояснение вклада.
    """
    return [c.strip() for c in value.split(';') if c.strip()]


def sheet_date(row, col, fallback):
    """Дата из колонки таблицы («21 April 2026») -> STIX ISO; пустая ячейка -> fallback."""
    v = cell(row, col)
    if not v:
        return fallback
    try:
        return pd.to_datetime(v).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    except (ValueError, TypeError):
        export_errors.append(f"не удалось разобрать дату «{v}» в колонке «{col}»")
        return fallback

def get_id(stix_type, name):
    # ключ - идентификатор сущности (TA0001, T0023.001, C1193, G0011, S0010), clean_name его съел бы;
    # для служебных объектов и связей - очищенное имя, как раньше
    key = str(name).strip()
    if not re.fullmatch(r"(TA|T|G|S|C)\d{4}(\.\d{3})?", key, re.I):
        key = clean_name(name)
    cache_key = f"{stix_type}_{key.lower()}"
    if cache_key not in id_cache:
        # Генерируем ЧЕСТНЫЙ uuid4, как просит issue 188; --stable-ids - uuid5 от ключа
        u = uuid.uuid5(uuid.NAMESPACE_URL, "decolonial.ist/" + cache_key) if STABLE_IDS else uuid.uuid4()
        id_cache[cache_key] = f"{stix_type}--{u}"
    return id_cache[cache_key]

# --- Регистрация кастомных типов (Домен на верхнем уровне) ---
@CustomObject('x-mitre-tactic', [
    ('name', StringProperty(required=True)),
    ('x_mitre_shortname', StringProperty(required=True)),
    ('x_mitre_domains', ListProperty(StringProperty(), required=True)),
    ('x_mitre_version', StringProperty(default=lambda: "1.0")),
    ('x_mitre_attack_spec_version', StringProperty(default=lambda: "3.3.0")),
    ('x_mitre_modified_by_ref', ReferenceProperty(valid_types='identity'))
])
class MitreTactic: pass

@CustomObject('x-mitre-matrix', [
    ('name', StringProperty(required=True)),
    ('tactic_refs', ListProperty(ReferenceProperty(valid_types='x-mitre-tactic'))),
    ('x_mitre_domains', ListProperty(StringProperty(), required=True)),
    ('x_mitre_version', StringProperty(default=lambda: "1.0")),
    ('x_mitre_attack_spec_version', StringProperty(default=lambda: "3.3.0")),
    ('x_mitre_modified_by_ref', ReferenceProperty(valid_types='identity'))
])
class MitreMatrix: pass

@CustomObject('x-mitre-collection', [
    ('name', StringProperty(required=True)),
    ('x_mitre_contents', ListProperty(DictionaryProperty())),
    ('x_mitre_version', StringProperty(default=lambda: "1.0")),
    ('x_mitre_attack_spec_version', StringProperty(default=lambda: "3.3.0")),
    ('x_mitre_modified_by_ref', ReferenceProperty(valid_types='identity'))
])
class MitreCollection: pass

# Сноски, которые реально стоят в текстах сайта (заполняет extract_refs): отчёт о сносках
# без карточки считает только их, а не все строки «Списка материалов» (архивариус, 26.10.2026)
USED_REFS = set()

def extract_refs(text, bib_dict, debug_ctx="", verbose=True):
    refs = []
    if not isinstance(text, str): return refs

    # [CcСс] ловит и латиницу и кириллицу. Паттерн «размотан» (unrolled loop),
    # чтобы не взрываться катастрофическим бэктрекингом; поддерживает скобки
    # внутри названия цитаты глубиной до двух уровней, например «(2 (23))»
    found = re.findall(r"\([CcСс]itation:\s*([^()]*(?:\((?:[^()]*(?:\([^()]*\)[^()]*)*)\)[^()]*)*)\)", text, flags=re.IGNORECASE)

    # Отладка: проверяем, видит ли скрипт вообще слово citation
    if verbose and "citation" in text.lower() and not found:
        print(f"[DEBUG {debug_ctx}] В тексте есть слово citation, но регулярка не сработала: {text}")
        
    for f in found:
        f_clean = f.strip()
        if f_clean in bib_dict:
            USED_REFS.add(f_clean)
            ref_obj = {k: v for k, v in bib_dict[f_clean].items() if v is not None}
            refs.append(ref_obj)
        else:
            print(f"[ОШИБКА МАППИНГА в {debug_ctx}] Цитаты '{f_clean}' НЕТ во вкладке 'Список материалов'!")
    return refs

ARCHIVE_COL = "ссылка на документ в архиве decolonial.ist"
# Витрина архива. В листе адрес карточки один, без языка (https://archive.decolonial.ist/137);
# языковые версии карточек — по схеме основного сайта: /uk/137, /en/137 (архивариус, 04.09.2026).
ARCHIVE_SITE_HOST = "archive.decolonial.ist"


def localize_card_url(url, lang):
    """Адрес карточки архива под язык бандла: /137 -> /uk/137 (ru — как есть).

    Трогаем только витрину archive.decolonial.ist; github-адреса и всё прочее
    возвращаем без изменений. Уже локализованный адрес (/uk/137) не задваиваем.
    """
    if not url or lang == "ru":
        return url
    p = urlsplit(url)
    if p.netloc.lower() != ARCHIVE_SITE_HOST:
        return url
    path = p.path or "/"
    first = path.strip("/").split("/", 1)[0]
    if first in LANGS:
        return url
    return urlunsplit((p.scheme, p.netloc, f"/{lang}{path if path.startswith('/') else '/' + path}", p.query, p.fragment))
# «выходные данные» и «архивный шифр» в строку сноски не идут (куратор 03.11.2026): они на карточке архива
BASIS_COL = "основание, разрешающее публикацию"   # «общественное достояние: издано в 1869 году»

# Разделитель блоков описания сноски: короткое тире с пробелами (правило проекта для UI).
# Знаки, после которых своя точка не ставится: «Столыпин П. А.», «Кто виноват?»
BIB_SENTENCE_END = ('.', '!', '?', '…')


def _bib_cell(row, col):
    """Ячейка листа материалов без nan-мусора."""
    v = str(row.get(col, '') or '').strip()
    return '' if v.lower() == 'nan' else v


def _bib_dot(s):
    """Блок описания как законченная часть: одна точка на конце, не две."""
    return s if s.endswith(BIB_SENTENCE_END) else f"{s}."


def _bib_basis(s):
    """Формула основания отдельным предложением: с заглавной буквы и с точкой.

    Первое слово с точкой внутри - это адрес («kremlin.ru: CC BY 4.0»), а не начало
    фразы: такие идентификаторы не трогаем.
    """
    if s[:1].islower() and '.' not in s.split(' ', 1)[0]:
        s = s[0].upper() + s[1:]
    return _bib_dot(s)


def build_bibliography(df_sources, verbose=True):
    """«Список материалов» → словарь сносок {«Название Год»: external_reference}.

    Описание сноски — МНОГОСТРОЧНОЕ, строки разделены \\n и остаются plain text:
    ровно этот же текст уходит в телеграм-зеркало, где никакой разметки нет.

        Ибрагимова З. Х. Мир чеченцев. XIX век. 2007.
        Карточка в архиве: https://github.com/decolonial-ist/archive/...

    Только эти две строки (куратор, 04.09.2026): первоисточник и основание
    публикации остаются в карточке архива, на сайт не выводятся.

    Куда ведёт сноска. Если у материала заполнена колонка «архив decolonial.ist» —
    у нас лежит его копия на github.com/decolonial-ist/archive, и сноска ведёт ТУДА:
    первоисточники в сети пропадают и переезжают, а наш файл лежит с контрольной суммой
    в картотеке. Первоисточник при этом не теряется — он идёт отдельной строкой описания.

    Безопасность: DEFAULT-DENY (модель куратора, вечер 01.09.2026; реестры —
    WORK/framework/WHITELIST_DRAFT.md и HOSTILE_DOMAINS.md). Политика живёт
    в hostile_domains.is_clickable, механика — на сайте. Адрес из белого списка
    пишется целиком со схемой, и макрос сайта делает из него ссылку; ВСЁ остальное —
    незнакомые домены, украинские адреса, российские площадки — пишется дефангнутым
    и без схемы: такой текст не матчится ни макросом, ни автолинковкой телеграма
    и гитхаба, и остаётся просто видимым адресом. У сноски на некликабельный адрес,
    которой не подпёрли копией в архиве, поля url нет вовсе: маркер [1] в тексте
    рендерится плоским, без ссылки.

    Колонки в архиве может не быть вовсе (старый снапшот, выгрузка --xlsx до заливки
    колонок) — тогда всё работает по-старому, сноска ведёт на первоисточник.
    """
    bibliography = {}
    n_archived = n_no_url = 0
    for _, r in df_sources.iterrows():
        name = str(r.get('Название', '')).strip()
        year = str(r.get('Год Публикации', '')).strip()
        author = str(r.get('Автор', '')).strip()
        u = safe_url(r.get('url', ''))
        s_name = f"{name} {year}".strip()
        url = u if u.lower() != 'nan' and u != '' else None
        # Видимая на сайте сноска: «Автор. Название. Год.» - и вся строка ссылка на
        # карточку архива, где лежит полная библиография (выходные данные, шифр,
        # первоисточник). Хвост «– Выходные данные. – Шифр.» из ТЗ архивариуса 09.2026
        # снят куратором 03.11.2026: реестр архива его не несёт, а карточка - несёт.
        # Пустые части выпадают: у документа автора может не быть вовсе.
        head = []
        if author and author.lower() != 'nan':
            # «Столыпин П. А.» уже кончается точкой инициала - второй не ставим
            head.append(_bib_dot(author))
        if name:
            head.append(_bib_dot(name))
        if year:
            head.append(_bib_dot(year))
        lines = [' '.join(head)] if head else ['']
        archive_u = safe_url(r.get(ARCHIVE_COL, ''))
        # Решение куратора 04.09.2026 (вечер): сноска на сайте — ОДНА строка
        # библиографии, и она целиком ссылка на карточку архива (url). Ни адреса
        # текстом, ни первоисточника, ни основания публикации: всё это живёт
        # в карточке, «только тем, кому оно надо». Прятать за текст можно только
        # НАШ адрес — правило «адреса видимы» (01.09) было про чужие домены.
        # У материала без карточки ссылки нет вовсе (после переезда архива
        # карточка, хотя бы заглушка, будет у каждого материала).
        if archive_u:
            n_archived += 1
            url = archive_u
        else:
            url = None
            n_no_url += 1
        bibliography[s_name] = {
            "source_name": s_name,
            "description": "\n".join(l for l in lines if l),
            "url": url,
        }
    if verbose:
        print(f"[архив] материалов в листе: {len(bibliography)}, из них с карточкой в архиве: {n_archived}")
    return bibliography


def build(lang, now):
    """Собирает бандл одного языка. get_id/id_cache общие на все вызовы,
    все ID считаются от русских имён — три бандла идентичны по ID и датам."""
    verbose = lang == "ru"  # отладочные принты цитат не утраиваем
    lang_prefix = "" if lang == "ru" else f"/{lang}"

    df_sources = load_tab(TABS["sources"])

    objects = []
    processed_rel_ids = set() 
    bibliography = build_bibliography(df_sources, verbose=verbose)
    for ref in bibliography.values():
        ref["url"] = localize_card_url(ref.get("url"), lang)

    objects = []
    #print(bibliography.keys())

    admin = Identity(
        id=get_id("identity", "Colonial Admin"),
        name="Colonial Admin",
        identity_class="organization",
        created=now, modified=now,
        custom_properties={"x_mitre_attack_spec_version": "3.3.0"}
    )
    objects.append(admin)

    # --- 1. ТАКТИКИ И ТЕХНИКИ (ИЗ НОВОЙ ВКЛАДКИ) ---
    df_tech = load_tab(TABS["techniques"])
    
    tactic_refs = []
    tech_data_map = {} 
    tech_name_to_id = {}
    
    # 1. Собираем уникальные тактики из колонки tactics
    unique_tactics = set()
    for raw_tactics in df_tech['tactics'].dropna():
        for t in str(raw_tactics).split(','):
            t_clean = t.strip()
            if t_clean and t_clean.lower() != 'nan':
                unique_tactics.add(t_clean)

    # Канон тактик — лист «Тактики | Tactics» (имена/описания на трёх языках,
    # честные created/last modified, autostamp штампует правки). Хардкод ниже —
    # фолбэк на время, пока листа нет / офлайн-режим со старым xlsx.
    df_tac = load_tactics_sheet()
    if df_tac is not None:
        tactic_shortnames = {}
        sheet_rows = sorted(df_tac.iterrows(), key=lambda ir: int(str(ir[1].get('order', '999')).strip() or 999))
        sheet_names = {str(r.get('name (ru)', '')).strip().lower() for _, r in sheet_rows}
        # техники могут ссылаться на старое имя переименованной тактики
        missing = {t for t in unique_tactics
                   if OLD_TACTIC_ALIASES.get(t.lower().strip(), t.lower().strip()) not in sheet_names}
        if missing:
            raise SystemExit(f"ЭКСПОРТ ОСТАНОВЛЕН: тактики техник не найдены в листе «Тактики | Tactics»: {sorted(missing)}")
        for _, r in sheet_rows:
            name_ru = str(r.get('name (ru)', '')).strip()
            t_clean_lower = name_ru.lower()
            t_short = str(r.get('shortname', '')).strip()
            t_ext_id = str(r.get('ID', '')).strip()
            t_stix_id = get_id("x-mitre-tactic", t_ext_id or name_ru)
            tactic_shortnames[t_clean_lower] = t_short
            for alias, canon in OLD_TACTIC_ALIASES.items():
                if canon == t_clean_lower:
                    tactic_shortnames[alias] = t_short
            objects.append({
                "type": "x-mitre-tactic",
                "id": t_stix_id,
                "name": lcell(r, 'name', lang) or name_ru,
                "description": lcell(r, 'description', lang) or f"Colonial Tactic: {name_ru}",
                "x_mitre_shortname": t_short,
                "x_mitre_domains": ["russia-colonialism"],
                "external_references": [{"source_name": "mitre-attack", "external_id": t_ext_id, "url": f"{SITE_BASE_URL}{lang_prefix}/tactics/{t_ext_id}"}],
                "created_by_ref": admin.id,
                "created": sheet_date(r, 'created', now), "modified": sheet_date(r, 'last modified', now),
                "x_mitre_modified_by_ref": admin.id,
                "spec_version": "2.1", "x_mitre_version": "1.0", "x_mitre_attack_spec_version": "3.3.0"
            })
            tactic_refs.append(t_stix_id)

    if df_tac is None:
        slug_map = {
            "легитимизация доминирования": "legitimization",
            "подготовка к захвату": "preparation",
            "захват управления": "seizure",
            # slug оставлен старый (neutralization) — сохраняет непрерывность
            # shortname'ов, kill_chain_phases и TA-нумерации после переименования
            "ослабление защиты": "neutralization",
            "нейтрализация защиты": "neutralization",  # старое имя тактики — алиас
            "закрепление": "persistence",
            "извлечение выгоды": "extraction"
        }

        tactic_shortnames = {}

        # Жесткий порядок тактик
        correct_order = [
            "легитимизация доминирования",
            "подготовка к захвату",
            "захват управления",
            "ослабление защиты",
            "нейтрализация защиты",  # старое имя той же тактики — сортируется в тот же слот
            "закрепление",
            "извлечение выгоды"
        ]

        def get_tactic_order(t):
            t_lower = t.lower().strip()
            return correct_order.index(t_lower) if t_lower in correct_order else 999

        # Сортируем тактики по нашему списку, а не по алфавиту
        ordered_tactics_list = sorted(list(unique_tactics), key=get_tactic_order)

        # Создаем объекты тактик (ID — от русского имени, name — локализованное)
        for idx, tac_name in enumerate(ordered_tactics_list):
            t_clean_lower = tac_name.lower().strip()
            t_short = slug_map.get(t_clean_lower, f"tactic-{idx+1:02d}")

            tactic_shortnames[t_clean_lower] = t_short
            t_ext_id = f"TA{idx+1:04d}"
            t_stix_id = get_id("x-mitre-tactic", t_ext_id)

            tac_name_loc = loc_tactic(tac_name, lang)
            objects.append({
                "type": "x-mitre-tactic",
                "id": t_stix_id,
                "name": tac_name_loc,
                "description": f"Colonial Tactic: {tac_name_loc}",
                "x_mitre_shortname": t_short,
                "x_mitre_domains": ["russia-colonialism"],
                "external_references": [{"source_name": "mitre-attack", "external_id": t_ext_id, "url": f"{SITE_BASE_URL}{lang_prefix}/tactics/{t_ext_id}"}],
                "created_by_ref": admin.id, "created": now, "modified": now,
                "x_mitre_modified_by_ref": admin.id,
                "spec_version": "2.1", "x_mitre_version": "1.0", "x_mitre_attack_spec_version": "3.3.0"
            })
            tactic_refs.append(t_stix_id)

    # 2. Создаем каркас техник в tech_data_map
    # ID и матчинг процедур — по русскому имени; name/description — локализованные
    for _, r in df_tech.iterrows():
        t_ext_id = str(r.get('ID', '')).strip()
        if not t_ext_id or t_ext_id.lower() == 'nan': continue

        t_name_ru = clean_name(lcell(r, 'name', 'ru'))
        t_name = clean_name(lcell(r, 'name', lang))
        desc = lcell(r, 'description', lang)

        tid = get_id("attack-pattern", t_ext_id)
        tech_name_to_id[t_name_ru.lower()] = tid

        is_sub = str(r.get('is sub-technique', '')).strip().upper() == 'TRUE'

        # Ссылки и цитаты
        t_url = f"{SITE_BASE_URL}{lang_prefix}/techniques/{t_ext_id.replace('.', '/')}"
        ext_refs = [{"source_name": "mitre-attack", "external_id": t_ext_id, "url": t_url}]
        ext_refs.extend(extract_refs(desc, bibliography, debug_ctx=f"Техника {t_ext_id} [{lang}]", verbose=verbose))
        
        # Народы техники наполняются из процедурных вкладок народов (см. ниже);
        # колонка platforms во вкладке техник больше не используется
        platforms = []
        
        # Тактики
        tactics_raw = str(r.get('tactics', '')).split(',')
        phases = []
        for tac in tactics_raw:
            t_clean = tac.strip()
            if t_clean and t_clean.lower() != 'nan':
                # Берем точный шортнейм из словаря, чтобы не было рассинхрона
                t_short = tactic_shortnames.get(t_clean.lower(), "unknown-tactic")
                phases.append({"kill_chain_name": "russia-colonialism", "phase_name": t_short})
                
        tech_data_map[tid] = {
            "id": tid, 
            "name": t_name,
            "description": desc,
            "kill_chain_phases": phases, 
            "external_references": ext_refs,
            "x_mitre_platforms": platforms,
            "x_mitre_domains": ["russia-colonialism"],
            "created_by_ref": admin.id,
            "created": sheet_date(r, 'created', now), "modified": sheet_date(r, 'last modified', now),
            "type": "attack-pattern",
            "x_mitre_version": sheet_version(r),
            "x_mitre_attack_spec_version": "3.3.0",
            "x_mitre_is_subtechnique": is_sub,
            "custom_properties": {
                "x_mitre_version": sheet_version(r),
                "x_mitre_modified_by_ref": admin.id,
                "x_mitre_attack_spec_version": "3.3.0",
                "x_mitre_is_subtechnique": is_sub
            },
            "allow_custom": True
        }
        # Контрибьюторы техники — колонка contributors, переводимая наравне с
        # остальным текстом: «contributors (en)» / «contributors (uk)», фолбэк на ru.
        # Разделитель имён — точка с запятой (в именах бывают запятые: «Имя, организация»).
        t_contribs = lcell(r, 'contributors', lang)
        if t_contribs:
            tech_data_map[tid]["custom_properties"]["x_mitre_contributors"] = split_contributors(t_contribs)

    # 3. Линкуем субтехники к родителям (Relationship subtechnique-of)
    for t_obj in tech_data_map.values():
        if t_obj["x_mitre_is_subtechnique"]:
            t_ext_id = next((ref["external_id"] for ref in t_obj["external_references"] if ref["source_name"] == "mitre-attack"), "")
            if "." in t_ext_id:
                parent_ext_id = t_ext_id.split(".")[0]
                parent_tid = next((k for k, v in tech_data_map.items() if any(r.get("external_id") == parent_ext_id for r in v.get("external_references", []))), None)
                
                if parent_tid:
                    objects.append({
                        "type": "relationship",
                        "id": get_id("relationship", f"subtech_{t_obj['id']}_{parent_tid}"),
                        "relationship_type": "subtechnique-of",
                        "source_ref": t_obj['id'],
                        "target_ref": parent_tid,
                        "created_by_ref": admin.id, "created": now, "modified": now,
                        "spec_version": "2.1", "x_mitre_version": "1.0", "x_mitre_attack_spec_version": "3.3.0"
                    })

    # ---- 2. ПРОЦЕДУРЫ ---
    # Загружаем вкладки процедур всех народов; народ определяется вкладкой.
    # Ошибки (строка без техники, неизвестная техника) валят экспорт в конце build().
    peoples_procedures = []  # [(имя народа, df, ярлык вкладки)]
    for people in PEOPLES:
        label = people["procedures"]["sheet"]
        df_pp = load_tab(people["procedures"])
        require_columns(df_pp, ["source name (ru)", "source group name (ru)", "source tool name (ru)",
                                "target technique name (ru)", "mapping description (ru)"], label)
        if len(df_pp) == 0:
            raise SystemExit(f"ЭКСПОРТ ОСТАНОВЛЕН: во вкладке «{label}» 0 опубликованных строк — "
                             f"проверь gid вкладки и флаги to be published")
        peoples_procedures.append((people["name"], df_pp, label))

    # Колонки с содержимым: если все пусты — это строка-разделитель для людей, пропускаем молча
    PROC_CONTENT_COLS = ['source name (ru)', 'source group name (ru)', 'source tool name (ru)',
                         'target technique name (ru)', 'mapping description (ru)']

    for people_name, df_pp, label in peoples_procedures:
        for i, r in df_pp.iterrows():
            if not any(cell(r, c) for c in PROC_CONTENT_COLS):
                continue
            t_name = clean_name(cell(r, 'target technique name (ru)')).lower()
            if not t_name:
                export_errors.append(f"«{label}», строка {i + 2}: заполненная строка без target technique name")
                continue
            t_id = tech_name_to_id.get(t_name)
            if not t_id:
                export_errors.append(f"«{label}»: техника «{t_name}» не найдена во вкладке техник")
                continue
            plats = tech_data_map[t_id].setdefault("x_mitre_platforms", [])
            if people_name not in plats:
                plats.append(people_name)

    for t_obj in tech_data_map.values():
        if t_obj.get("x_mitre_is_subtechnique"):
            ext_refs = t_obj.get("external_references", [])
            ext_id = next((ref.get("external_id") for ref in ext_refs if ref.get("source_name") == "mitre-attack"), "")
            
            if "." in ext_id:
                parent_ext_id = ext_id.split(".")[0] 
                parent_obj = next((p for p in tech_data_map.values() if any(r.get("external_id") == parent_ext_id for r in p.get("external_references", []))), None)
                
                if parent_obj:
                    if "x_mitre_platforms" not in parent_obj:
                        parent_obj["x_mitre_platforms"] = []
                    
                    for plat in t_obj.get("x_mitre_platforms", []):
                        if plat not in parent_obj["x_mitre_platforms"]:
                            parent_obj["x_mitre_platforms"].append(plat)

    for t_content in tech_data_map.values():
        # народы копились русскими каноническими именами — локализуем при выпуске
        t_content["x_mitre_platforms"] = [loc_people(p, lang) for p in t_content.get("x_mitre_platforms", [])]
        objects.append(AttackPattern(**t_content))

    objects.append({
        "type": "x-mitre-matrix",
        "id": get_id("x-mitre-matrix", "Russian colonialism Matrix"),
        "name": "Russian Colonialism",
        "description": "Russian colonialism Matrix",
        "tactic_refs": tactic_refs,
        "x_mitre_domains": ["russia-colonialism"],
        "external_references": [{"source_name": "mitre-attack", "external_id": "russia-colonialism", "url": f"{SITE_BASE_URL}{lang_prefix}/matrices/russia"}], # ОБЯЗАТЕЛЬНОЕ ПОЛЕ ДЛЯ БД
        "created_by_ref": admin.id, 
        "created": now, 
        "modified": now,
        "x_mitre_modified_by_ref": admin.id, 
        "spec_version": "2.1",
        "x_mitre_version": "1.0",
        "x_mitre_attack_spec_version": "3.3.0"
    })

    # Народы инструментов, кампаний и акторов — из процедурных вкладок народов
    tool_platforms = {}
    campaign_platforms = {}
    group_platforms = {}
    for people_name, df_pp, label in peoples_procedures:
        for _, r in df_pp.iterrows():
            s_name = cell(r, 'source tool name (ru)').lower()
            c_name = cell(r, 'source name (ru)').lower()
            g_name = cell(r, 'source group name (ru)').lower()
            if s_name:
                tool_platforms.setdefault(s_name, set()).add(people_name)
            if c_name:
                campaign_platforms.setdefault(c_name, set()).add(people_name)
            if g_name:
                group_platforms.setdefault(g_name, set()).add(people_name)

    # --- 2. СУЩНОСТИ ---
    entity_map = {"campaign": {}, "intrusion-set": {}, "tool": {}}
    # Иерархия кампаний (эпизоды): колонка «sub-campaign of» вкладок кампаний
    # (как «sub-technique of» у подтехник), значение — CNNNN родителя.
    # Ровно два уровня, родитель того же народа.
    campaign_registry = {}      # ext_id (CNNNN) -> {oid, people, parent, name_ru}
    campaign_name_to_ext = {}   # русское имя lower -> ext_id (для правила размещения техник)
    campaign_rows_seen = []     # (ext_id, name_ru, desc_ru, вкладка) — целостность между вкладками
    for key, stype, cls in [("groups", "intrusion-set", IntrusionSet),
                            ("campaigns", "campaign", Campaign),
                            ("tools", "tool", Tool)]:
        if key == "campaigns":
            # Кампании собираются из вкладок всех народов; народ вкладки
            # запоминается в служебной колонке _people
            frames = []
            for people in PEOPLES:
                c_label = people["campaigns"]["sheet"]
                df_c = load_tab(people["campaigns"])
                require_columns(df_c, ["name (ru)", "ID", "description (ru)", "first seen", "last seen"], c_label)
                if len(df_c) == 0:
                    raise SystemExit(f"ЭКСПОРТ ОСТАНОВЛЕН: во вкладке «{c_label}» 0 опубликованных строк — "
                                     f"проверь gid вкладки и флаги to be published")
                df_c = df_c.copy()
                df_c["_people"] = people["name"]
                frames.append(df_c)
            df = pd.concat(frames, ignore_index=True)
        else:
            df = load_tab(TABS[key])
        for _, r in df.iterrows():
            # ID и матчинг процедур — по русскому имени; name — локализованное
            name_ru = lcell(r, 'name', 'ru')
            if not name_ru: continue
            name = lcell(r, 'name', lang)
            # 1. ЧИНИМ ССЫЛКИ И ID (Если нет ID в таблице - генерим свой, иначе сайт проигнорит объект)
            ext_id = str(r.get('ID', '')).strip()
            if not ext_id or ext_id == 'nan':
                ext_prefix = "S" if stype == "tool" else "G" if stype == "intrusion-set" else "C"
                ext_id = f"{ext_prefix}{abs(hash(name_ru)) % 10000:04d}"
            oid = get_id(stype, ext_id)
            entity_map[stype][name_ru.lower()] = oid

            # Правильные пути для разных сущностей
            url_path = "software" if stype == "tool" else "groups" if stype == "intrusion-set" else "campaigns"


            ext_refs = [{"source_name": "mitre-attack", "external_id": ext_id, "url": f"{SITE_BASE_URL}{lang_prefix}/{url_path}/{ext_id}"}]

            entity_desc = lcell(r, 'description', lang) or 'No desc'

            # --- Добавляем отладку ---
            found_refs = extract_refs(entity_desc, bibliography, debug_ctx=f"{name_ru} [{lang}]", verbose=verbose)
            if verbose:
                print(f"[{stype.upper()}] {name_ru}: найдено цитат - {len(found_refs)}")

            ext_refs.extend(found_refs)
            
            item_props = {"x_mitre_version": sheet_version(r), "x_mitre_modified_by_ref": admin.id, "x_mitre_attack_spec_version": "3.3.0"}

            # Контрибьюторы из колонки contributors (имена через точку с запятой),
            # переводимой наравне с остальным текстом: «contributors (en/uk)», фолбэк на ru;
            # пусто = сделано проектом, сайт покажет дефолт decolonial.ist project
            contribs = lcell(r, 'contributors', lang)
            if contribs:
                item_props["x_mitre_contributors"] = split_contributors(contribs)
            
            extra_kwargs = {
                "x_mitre_domains": ["russia-colonialism"]
            }

            if stype == "tool":
                extra_kwargs["x_mitre_platforms"] = sorted(loc_people(p, lang) for p in tool_platforms.get(name_ru.lower(), set()))

            elif stype == "campaign":
                # Народ кампании — из её вкладки; процедуры могут добавить свои
                plats = set(campaign_platforms.get(name_ru.lower(), set()))
                own_people = str(r.get('_people', '')).strip()
                if own_people:
                    plats.add(own_people)
                extra_kwargs["x_mitre_platforms"] = sorted(loc_people(p, lang) for p in plats)
                fmt_d = lambda v: pd.to_datetime(v).strftime("%Y-%m-%dT%H:%M:%S.000Z") if pd.notna(v) else now
                extra_kwargs.update({"first_seen": fmt_d(r.get('first seen')), "last_seen": fmt_d(r.get('last seen')), "objective": entity_desc[:500]})

                # Эпизод: одна колонка «sub-campaign of» (CNNNN родителя) — как
                # «sub-technique of» у подтехник, только у кампаний ID плоские, поэтому
                # родитель берётся из колонки, а не из ID. Флаг x_dcl_is_subcampaign
                # выставляется по её наличию. Линковка и валидация — после цикла.
                # Колонка не обязательна: её отсутствие = иерархии во вкладке нет.
                parent_ext = cell(r, 'sub-campaign of').upper()
                raw_d = lambda v: pd.to_datetime(v) if pd.notna(v) and str(v).strip() else None
                campaign_registry[ext_id] = {"oid": oid, "people": own_people, "parent": parent_ext, "name_ru": name_ru,
                                             "first": raw_d(r.get('first seen')), "last": raw_d(r.get('last seen'))}
                campaign_name_to_ext[name_ru.lower()] = ext_id
                campaign_rows_seen.append((ext_id, name_ru, lcell(r, 'description', 'ru'), own_people))
                if parent_ext:
                    item_props["x_dcl_is_subcampaign"] = True
                    item_props["x_dcl_parent_campaign"] = parent_ext

            elif stype == "intrusion-set":
                # Добавляем народы Акторам
                extra_kwargs["x_mitre_platforms"] = sorted(loc_people(p, lang) for p in group_platforms.get(name_ru.lower(), set()))

            objects.append(cls(
                id=oid, name=name, description=entity_desc,
                external_references=ext_refs, custom_properties=item_props,
                **extra_kwargs, created_by_ref=admin.id,
                created=sheet_date(r, 'created', now), modified=sheet_date(r, 'last modified', now),
                allow_custom=True
            ))

    # 2б. Целостность идентичности кампаний между вкладками (мультидомен, 17.08):
    # один CNNNN в нескольких вкладках допустим ТОЛЬКО как точная копия (имя и
    # описание дословно совпадают); тот же CNNNN с разными текстами — ошибка данных.
    # Одно русское имя у РАЗНЫХ CNNNN — тоже ошибка: STIX id считается от имени,
    # такие кампании молча склеились бы в один объект.
    by_ext = {}
    by_name = {}
    for c_ext, c_name_ru, c_desc_ru, c_sheet in campaign_rows_seen:
        by_ext.setdefault(c_ext, []).append((c_name_ru, c_desc_ru, c_sheet))
        by_name.setdefault(c_name_ru.lower(), {})[c_ext] = c_sheet
    for c_ext, rows in by_ext.items():
        if len(rows) > 1:
            sheets = ", ".join(s for _, _, s in rows)
            if len({(n, d) for n, d, _ in rows}) > 1:
                export_errors.append(f"Кампания {c_ext} заведена в нескольких вкладках ({sheets}) с РАЗНЫМИ именем/описанием — копии разошлись, сверить и выровнять")
            elif lang == "ru":
                print(f"[КОПИИ] кампания {c_ext} продублирована точной копией во вкладках: {sheets} — "
                      f"тексты совпадают, но объект уедет в бандл дважды; для живой работы репликами нужен настоящий мердж")
    for c_name_l, exts in by_name.items():
        if len(exts) > 1:
            listing = ", ".join(f"{e} ({s})" for e, s in sorted(exts.items()))
            export_errors.append(f"Имя кампании «{c_name_l}» носят разные ID: {listing} — STIX id считается от имени, объекты склеятся; переименовать одну из них")

    # 2а. Линкуем эпизоды к родительским кампаниям (Relationship subcampaign-of —
    # кастомный тип по образцу subtechnique-of; STIX 2.1 это допускает).
    # Родитель — полноценная кампания со своими процедурами (длящиеся явления живут
    # на нём). Ограничена только ГЛУБИНА: у кампании с детьми не может быть своего
    # родителя — трёхэтажных цепочек «война → вторжение → бой» не строим, как и у
    # субтехник (T1234.001.001 не бывает); если тянет на третий этаж — верхушка
    # выбрана не на той высоте.
    for c_ext, rec in campaign_registry.items():
        p_ext = rec["parent"]
        if not p_ext:
            continue
        if p_ext == c_ext:
            export_errors.append(f"Кампания {c_ext} указывает «sub-campaign of» на саму себя")
            continue
        parent = campaign_registry.get(p_ext)
        if not parent:
            export_errors.append(f"Кампания {c_ext}: «sub-campaign of» = {p_ext} не найдена во вкладках кампаний")
            continue
        if parent["people"] != rec["people"]:
            export_errors.append(f"Кампания {c_ext} ({rec['people']}): родитель {p_ext} принадлежит другому народу ({parent['people']})")
            continue
        if parent["parent"]:
            export_errors.append(f"Кампания {c_ext}: родитель {p_ext} сам является эпизодом {parent['parent']} — больше двух уровней нельзя")
            continue
        # Окно родителя обязано покрывать окно эпизода (куратор 05.09): всё, что стоит
        # на родителе, действует весь его период, значит эпизод не может вылезать за
        # его даты. Пустой last seen = идёт до сих пор: у родителя это открытый верх,
        # у эпизода при закрытом родителе — ошибка.
        d = lambda v: v.strftime("%Y-%m-%d") if v is not None else "…"
        if rec["first"] is not None and parent["first"] is not None and rec["first"] < parent["first"]:
            export_errors.append(f"Кампания {c_ext}: начало {d(rec['first'])} раньше начала родителя {p_ext} ({d(parent['first'])})")
        if parent["last"] is not None:
            if rec["last"] is None:
                export_errors.append(f"Кампания {c_ext}: идёт до сих пор (last seen пуст), а родитель {p_ext} закончился {d(parent['last'])}")
            elif rec["last"] > parent["last"]:
                export_errors.append(f"Кампания {c_ext}: конец {d(rec['last'])} позже конца родителя {p_ext} ({d(parent['last'])})")
        objects.append({
            "type": "relationship",
            "id": get_id("relationship", f"subcampaign_{rec['oid']}_{parent['oid']}"),
            "relationship_type": "subcampaign-of",
            "source_ref": rec["oid"],
            "target_ref": parent["oid"],
            "created_by_ref": admin.id, "created": now, "modified": now,
            "spec_version": "2.1", "x_mitre_version": "1.0", "x_mitre_attack_spec_version": "3.3.0"
        })

    # --- 3. СВЯЗИ (RELATIONSHIPS) ---
    def add_rel(src, target, rel_type, desc="", desc_ru="", people=None, contributors=None):
        safe_desc = str(desc).strip() if pd.notna(desc) and str(desc).strip() != '' else ""
        rel_refs = extract_refs(safe_desc, bibliography, debug_ctx=f"Связь {src}->{target} [{lang}]", verbose=verbose)

        import hashlib
        # хэш — ОТ РУССКОГО описания: id связи должен совпадать во всех трёх бандлах
        safe_desc_ru = str(desc_ru).strip() if pd.notna(desc_ru) and str(desc_ru).strip() != '' else ""
        desc_hash = hashlib.md5(safe_desc_ru.encode('utf-8')).hexdigest()[:8]
        rid = get_id("relationship", f"{rel_type}_{src}_{target}_{desc_hash}")

        if rid not in processed_rel_ids:
            props = {"x_mitre_version": "1.0", "x_mitre_modified_by_ref": admin.id, "x_mitre_attack_spec_version": "3.3.0"}
            # народ процедурной вкладки, породившей связь: сайт использует его,
            # чтобы точно фильтровать примеры процедур по народам
            if people:
                props["x_mitre_platforms"] = [loc_people(people, lang)]
            # контрибьюторы процедуры (колонка contributors листа процедур) - на связи
            # кампании с техникой; сайт показывает их на странице процедуры
            if contributors:
                props["x_mitre_contributors"] = contributors
            objects.append(Relationship(
                id=rid, relationship_type=rel_type, source_ref=src, target_ref=target,
                description=safe_desc,
                external_references=rel_refs if rel_refs else None,
                custom_properties=props,
                created_by_ref=admin.id, created=now, modified=now, allow_custom=True
            ))
            processed_rel_ids.add(rid)

    proc_pairs = {}      # (вкладка, кампания lower, техника lower) -> [строки] — внутрилистовые дубли

    for people_name, df_pp, label in peoples_procedures:
      for i, r in df_pp.iterrows():

        # Извлекаем имена из колонок вкладки процедур (матчинг — по русским именам)
        c_name = cell(r, 'source name (ru)').lower()
        g_name = cell(r, 'source group name (ru)').lower()
        s_name = cell(r, 'source tool name (ru)').lower()
        t_name = clean_name(cell(r, 'target technique name (ru)')).lower()

        # Достаем описание маппинга: локализованное — в объект,
        # русское — в хэш для стабильного id связи
        mapping_description = lcell(r, 'mapping description', lang)
        mapping_description_ru = cell(r, 'mapping description (ru)')
        # контрибьюторы процедуры: «contributors (ru/en/uk)», фолбэк на ru; колонки
        # может не быть вовсе - тогда процедура проекта, как раньше
        proc_contribs = split_contributors(lcell(r, 'contributors', lang))

        c_id = entity_map["campaign"].get(c_name)
        g_id = entity_map["intrusion-set"].get(g_name)
        s_id = entity_map["tool"].get(s_name)
        t_id = tech_name_to_id.get(t_name)

        # Непустое имя, которого нет среди сущностей, — ошибка данных: раньше
        # такие строки молча выпадали из экспорта
        if c_name and not c_id:
            export_errors.append(f"«{label}»: кампания «{c_name}» не найдена во вкладке кампаний")
        if g_name and not g_id:
            export_errors.append(f"«{label}»: актор «{g_name}» не найден во вкладке акторов")
        if s_name and not s_id:
            export_errors.append(f"«{label}»: инструмент «{s_name}» не найден во вкладке инструментов")

        # 1. СВЯЗЬ: Группа -> Софт (Чтобы софт был в профиле группы)
        if g_id and s_id: 
            add_rel(g_id, s_id, "uses", mapping_description, mapping_description_ru, people=people_name)

        # 2. СВЯЗЬ: Софт -> Техника (Чтобы техники были в профиле софта)
        if s_id and t_id:
            add_rel(s_id, t_id, "uses", mapping_description, mapping_description_ru, people=people_name)

        # 3. Остальные связи из процедур
        if c_id and t_id:
            add_rel(c_id, t_id, "uses", mapping_description, mapping_description_ru, people=people_name,
                    contributors=proc_contribs)
            # внутрилистовые дубли пары кампания+техника (правило 1×1×1 народ);
            # та же пара в листах РАЗНЫХ народов — законный мультидомен, не считается
            proc_pairs.setdefault((label, c_name, t_name), []).append(i + 2)
        
        if c_id and g_id: 
            add_rel(c_id, g_id, "attributed-to", mapping_description, mapping_description_ru, people=people_name)
            
        if g_id and t_id: 
            add_rel(g_id, t_id, "uses", mapping_description, mapping_description_ru, people=people_name)
            
        if c_id and s_id:
            add_rel(c_id, s_id, "uses", mapping_description, mapping_description_ru, people=people_name)

    # Иерархия кампаний (решение куратора 05.09.2026): никаких проверок техник
    # между родителем и эпизодами. На родителе живёт то, что верно для всего его
    # периода; на эпизодах — события эпизодов, и одна техника законно повторяется
    # на нескольких эпизодах одной войны (три вторжения = три «интервенции»).
    # Связь subcampaign-of — только навигационная, как subtechnique-of.
    if lang == "ru":  # предупреждения одни на прогон, не троить по языкам
        # Мягкий чекер (го куратора 17.08): дубль пары кампания+техника ВНУТРИ одного
        # листа — нарушение правила «1 кампания × 1 техника × 1 народ», но экспорт
        # не валим (известные дубли куратор правит в своём темпе)
        for (dup_label, dup_c, dup_t), dup_rows in sorted(proc_pairs.items()):
            if len(dup_rows) > 1:
                dup_ext = campaign_name_to_ext.get(dup_c, "")
                print(f"[ДУБЛИ] «{dup_label}»: кампания «{dup_c}»{f' ({dup_ext})' if dup_ext else ''} + "
                      f"техника «{dup_t}» в {len(dup_rows)} строках (строки {', '.join(map(str, dup_rows))}) — "
                      f"по правилу 1×1×1 слить в одну ячейку")

    # --- ЖЁСТКАЯ ВАЛИДАЦИЯ: при ошибках данных файл не пишем ---
    if export_errors:
        print("\nЭКСПОРТ ОСТАНОВЛЕН — исправь данные в таблице:" if not KEEP_GOING
              else "\nОШИБКИ ДАННЫХ (--keep-going: бандл всё равно записан, для сравнения):")
        for e in sorted(set(export_errors)):
            print("  -", e)
        if not KEEP_GOING:
            raise SystemExit(1)

    # --- 4. КОЛЛЕКЦИЯ ---
    # Сериализуем объекты заранее: Workbench сверяет объекты по связке
    # ID + точная дата модификации, поэтому в манифест кладём фактический
    # modified каждого объекта (даты записей теперь идут из таблицы)
    serialized_objects = []
    for o in objects:
        serialized_objects.append(o if isinstance(o, dict) else json.loads(o.serialize()))

    unique_contents = {}
    for o in serialized_objects:
        unique_contents[o["id"]] = o.get("modified", now)

    # Создаем объект коллекции
    collection = {
        "type": "x-mitre-collection",
        "id": get_id("x-mitre-collection", "Russian colonialism"),
        "spec_version": "2.1",
        "name": "Russian colonialism",
        "x_mitre_version": "18.1",
        "x_mitre_attack_spec_version": "3.3.0",    # ДОБАВИТЬ
        "x_mitre_domains": ["russia-colonialism"],
        "x_mitre_contents": [{"object_ref": k, "object_modified": v} for k, v in unique_contents.items()],
        "created": now, 
        "modified": now 
    }
    final_objects = [collection] + serialized_objects

    bundle_output = {
        "type": "bundle",
        "id": f"bundle--{uuid.uuid5(uuid.NAMESPACE_URL, 'decolonial.ist/bundle/' + lang + '/' + now) if STABLE_IDS else uuid.uuid4()}",
        "objects": final_objects
    }

    if verbose:
        no_card = sorted(n for n in USED_REFS if not bibliography[n].get("url"))
        print(f"[архив] сносок в текстах сайта: {len(USED_REFS)}, из них без карточки (маркер без ссылки): {len(no_card)}")
        for n in no_card:
            print(f"[архив]   без карточки: {n}")
    USED_REFS.clear()

    out_path = output_path_for(lang)
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(bundle_output, f, indent=4, ensure_ascii=False)
    print(f"Готово [{lang}]. Уникальных объектов: {len(final_objects)}. Файл: {out_path}")


def build_all():
    """Три бандла за один прогон: общий now и общий id_cache — объекты
    всех языков идентичны по ID и датам."""
    now = FIXED_NOW or datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.000Z")
    for lang in LANGS:
        export_errors.clear()
        build(lang, now)


if __name__ == "__main__":
    import sys
    args = sys.argv[1:]
    if "--xlsx" in args:
        XLSX_PATH = args[args.index("--xlsx") + 1]
    if "--key" in args:
        KEY_PATH = args[args.index("--key") + 1]
    if "--no-key" in args:      # форс публичного CSV (отладка)
        KEY_PATH = None
    if "--output" in args:
        OUTPUT_PATH = args[args.index("--output") + 1]
    if "--kb" in args:
        KB_DIR = os.path.expanduser(args[args.index("--kb") + 1])
    if "--sheet" in args:       # старый путь: Google-таблица (только для сравнений, закрыта с 03.11.2026)
        KB_DIR = None
    if "--random-ids" in args:
        STABLE_IDS = False
    if "--now" in args:
        FIXED_NOW = args[args.index("--now") + 1]
    if "--keep-going" in args:
        KEEP_GOING = True
    build_all()