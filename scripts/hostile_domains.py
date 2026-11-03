"""Политика кликабельности адресов: DEFAULT-DENY.

Модель утверждена куратором вечером 01.09.2026, реестры —
`~/tmp/WORK/framework/WHITELIST_DRAFT.md` (белый список) и
`~/tmp/WORK/framework/HOSTILE_DOMAINS.md` (чёрный).

Смысл: читатель не должен уметь попасть одним кликом НИКУДА, кроме нашего архива,
украинских сайтов и горстки международных институций и библиотек. Всё остальное —
просто незнакомые домены — остаётся видимым текстом с разорванной последней точкой
(«sevkrimrus.narod[.]ru/ZAKON/1654.htm»): автолинковка телеграма и гитхаба такой
текст не подхватывает, а человек, которому адрес действительно нужен, копирует его
руками и чинит точку сам. Цена ошибки несимметрична: лишний дефанг стоит читателю
одной правки точки, лишний клик из рф стоит ему записи в логе провайдера.

Порядок решения (см. is_clickable):
  1. ЧЁРНЫЙ список — вторая линия обороны, проверяется ПЕРВЫМ: домен оттуда не может
     стать кликабельным, даже если однажды по недосмотру попадёт в белый.
  2. БЕЛЫЙ список — точное совпадение или поддомен по точечной границе, либо
     белая зона целиком (WHITELIST_ZONES: украинские .ua и .укр — решение куратора
     04.09.2026, отменившее правило «.ua светит читателя из рф»).
  3. Всё прочее — дефанг.

Чёрный список: ярусы A и B — зоны (HOSTILE_ZONES, сравнение по последнему лейблу
имени, и в юникоде, и в punycode); ярус C — домены (HOSTILE_DOMAINS) и бренды
целиком на любой зоне (HOSTILE_BRANDS).
"""

import re
from urllib.parse import urlsplit

# --- Ярус A: зоны рф, Беларуси и российских регистратур -----------------------
ZONES_TIER_A = [
    "ru", "su", "рф", "москва", "moscow", "дети", "tatar", "рус",
    "онлайн", "сайт", "by", "бел",
]

# --- Ярус B: зоны досягаемости ФСБ --------------------------------------------
# Армения (am, հայ) исключена решением куратора 01.09.2026.
# Молдова (md) не включена; Приднестровье закрыто точечными доменами яруса C.
ZONES_TIER_B = [
    "kz", "қаз", "kg", "tj", "ge", "გე", "rs", "срб", "ir", "kp",
]


def _punycode(label):
    """xn--форма кириллической/грузинской зоны; для латиницы вернёт её же."""
    try:
        return label.encode("idna").decode("ascii")
    except (UnicodeError, UnicodeDecodeError):
        return label


# Зоны сравниваем и в юникоде, и в punycode: в ссылках встречаются обе записи.
HOSTILE_ZONES = frozenset(
    [z.lower() for z in ZONES_TIER_A + ZONES_TIER_B]
    + [_punycode(z.lower()) for z in ZONES_TIER_A + ZONES_TIER_B]
)

# --- Ярус C: домены на международных зонах ------------------------------------
# Основание помечено в комментарии; в код оно не едет — реестр ведётся в
# HOSTILE_DOMAINS.md, здесь только исполнение.
HOSTILE_DOMAINS = frozenset([
    # госСМИ по санкционным спискам ЕС [eu-sanctions]
    "rt.com", "ruptly.tv", "rtd.xyz", "rtde.tech", "esrt.online", "esrt.press",
    "sputnikglobe.com", "sputniknews.com",
    "rossiyasegodnya.com", "tass.com",
    "news-front.info", "southfront.org", "strategic-culture.org",
    "journal-neo.org", "orientalreview.org", "katehon.com", "eadaily.com",
    # экосистемы госкапитала [state-capital]
    "vk.com", "ok.ru", "mail.ru", "dzen.ru",
    "yandex.com", "yandex.ru", "ya.ru", "auto.ru", "kinopoisk.ru",
    "rutube.ru",
    "sber.ru", "sberbank.ru", "sberbank.com",
    # [ua-sanctions]
    "kaspersky.com", "kaspersky.ru", "drweb.com", "drweb.ru",
    # [pace]
    "patriarchia.ru",
    # органы самопровозглашённой администрации Приднестровья
    "gospmr.org", "vspmr.org",
    # группа 3 заявки вебера, утверждена 01.09.2026 вместе с белым списком:
    # российские площадки на международных зонах, хостинг и логи де-факто рф
    "historyrussia.org",          # + docs.historyrussia.org [state-capital]
    "apsnyteka.org",              # библиотека оккупированной Абхазии
    "scepsis.net",
    "na5ballov.pro", "royallib.com", "loveread.ec", "rulit.me",
    "rev-lib.com", "vostlit.info", "istmat.org",   # [ru-infrastructure]
])

# --- Белый список: ЕДИНСТВЕННОЕ, что кликабельно ------------------------------
# Точное совпадение или поддомен по точечной границе. Семейство Викимедиа держим
# родительскими доменами: языковых поддоменов у него сотни (uk.wikipedia.org,
# commons.wikimedia.org, ru.wikisource.org), перечислять их поимённо бессмысленно.
# Группа 2 черновика 01.09 была НЕ включена («домен идентифицирует читателя
# из рф»). 04.09.2026 куратор это правило отменил: украинские сайты кликабельны —
# зоны .ua/.укр целиком (WHITELIST_ZONES) и украинские институции на международных
# зонах (ниже); остаток группы 2 (radiosvoboda/svoboda.org, kavkaz-uzel.eu,
# dzurdzuki.com) куратор добавил тем же вечером. Группа 2 закрыта целиком.
WHITELIST_DOMAINS = frozenset([
    # мы сами
    "decolonial.ist",             # + archive.decolonial.ist
    "github.com",
    "t.me",                       # наше телеграм-зеркало (куратор 02.09.2026)
    # Викимедиа
    "wikipedia.org", "wikisource.org", "wikimedia.org",
    # Internet Archive (+ web.archive.org)
    "archive.org",
    # правозащита
    "hrw.org",
    # ООН и агентства
    "ohchr.org",                  # + ukraine.ohchr.org
    "un.org",                     # + digitallibrary.un.org
    "undocs.org", "reliefweb.int",
    # межгосударственные органы и суды
    "europarl.europa.eu", "coe.int",   # coe.int покрывает hudoc.echr.coe.int
    "icc-cpi.int",
    # наш фреймворк
    "attack.mitre.org",
    # академические репозитории и библиотеки
    "researchgate.net", "gallica.bnf.fr",
    "oxfordenergy.org", "justiceinfo.net",
    # фреймворк DISARM: упомянут в тексте тактики TA0004 (добавлен куратором 01.09.2026)
    "disarm.foundation",
    # украинские институции на международных зонах (куратор 04.09.2026)
    "khpg.org",                   # Харьковская правозащитная группа (+ museum.khpg.org)
    "suspilne.media",             # Суспільне
    "stopfake.org",
    "lvivcenter.org",             # Центр міської історії (+ lia.lvivcenter.org)
    "pereiaslav.city",
    # остаток группы 2 — добавлен куратором 04.09.2026 («добавляй в белый список»)
    "radiosvoboda.org", "svoboda.org",   # РСЕ/РС
    "kavkaz-uzel.eu",                    # Кавказский узел
    "dzurdzuki.com",                     # вайнахский исторический проект
    # каталоги изданий — карточки книг под авторским правом вместо читалок (куратор 04.09.2026,
    # «добавляй»): архив ставит их в «Издание», розыскной лист /wanted/ ссылается на Google Books
    "books.google.com",
    "worldcat.org",
    "openlibrary.org",                   # Open Library, проект Internet Archive (куратор 05.09.2026)
])

# Белые ЗОНЫ: кликабельно всё на зоне целиком. Украина — решение куратора 04.09.2026.
# Сравнение по последнему лейблу, и в юникоде, и в punycode, как у чёрных зон.
# Чёрный список всё равно проверяется первым (ярус C может закрыть отдельный домен).
WHITELIST_ZONES = frozenset(
    [z.lower() for z in ("ua", "укр")] + [_punycode(z.lower()) for z in ("ua", "укр")]
)

# Бренды, которые реестр закрывает ЦЕЛИКОМ, на любой зоне: под ними сотни
# страновых доменов, перечислять их поимённо бессмысленно. Матчится лейбл,
# стоящий прямо перед зоной: «sputniknews» в sputniknews.by, «yandex»
# в mail.yandex.com.
HOSTILE_BRANDS = re.compile(
    r"^(?:yandex|sputnik\w*|sber\w*|kaspersky|drweb)$",
    flags=re.IGNORECASE,
)


def _host_of(url):
    """Имя хоста из адреса: без схемы, логина-пароля, порта и регистра.

    Адрес без схемы («narod.ru/page») urlsplit кладёт целиком в path, поэтому
    хост в таком случае вырезаем сами.
    """
    s = str(url or "").strip()
    if not s:
        return ""
    p = urlsplit(s)
    host = p.netloc or p.path.split("/", 1)[0]
    if "@" in host:                       # user:pass@host
        host = host.rsplit("@", 1)[1]
    host = host.split(":", 1)[0]          # порт
    return host.strip().strip(".").lower()


def _matches(host, domains):
    """Хост — это один из доменов набора или его поддомен (по точечной границе)."""
    return any(host == d or host.endswith("." + d) for d in domains)


def is_hostile(url):
    """Адрес в чёрном списке: враждебная зона, домен реестра или бренд?

    Вторая линия обороны. При default-deny сам по себе решения не принимает —
    кликабельность считает is_clickable, — но домен отсюда не может стать
    кликабельным ни при каких правках белого списка.
    """
    host = _host_of(url)
    if not host:
        return False
    labels = host.split(".")
    if len(labels) < 2:
        return False
    # ярусы A и B: зона — последний лейбл
    if labels[-1] in HOSTILE_ZONES:
        return True
    # ярус C: точное совпадение или поддомен по точечной границе
    if _matches(host, HOSTILE_DOMAINS):
        return True
    # ярус C, бренды целиком: лейбл прямо перед зоной
    return bool(HOSTILE_BRANDS.match(labels[-2]))


def is_clickable(url):
    """Единственная функция политики: можно ли из этого адреса делать ссылку.

    Default-deny. Чёрный список проверяется первым и перебивает белый; всё, чего
    нет в белом списке и не на белой зоне — незнакомые домены, площадки группы 2
    без решения куратора — некликабельно и уходит в дефанг.
    """
    host = _host_of(url)
    if not host or "." not in host:
        return False
    if is_hostile(url):
        return False
    if host.split(".")[-1] in WHITELIST_ZONES:
        return True
    return _matches(host, WHITELIST_DOMAINS)


def defang(url):
    """Адрес видимым текстом, но некликабельным: без схемы, последняя точка
    домена разорвана.

        https://sevkrimrus.narod.ru/ZAKON/1654.htm
        → sevkrimrus.narod[.]ru/ZAKON/1654.htm

    Путь не трогаем: точки в нём (…/doc.1654.html) остаются как есть, иначе
    адрес станет неверным при ручном восстановлении. «www» тоже оставляем —
    это часть адреса, который человек будет копировать.
    """
    s = str(url or "").strip()
    if not s:
        return ""
    # схема прочь
    s = re.split(r"^[a-zA-Z][a-zA-Z0-9+.\-]*://", s, maxsplit=1)[-1]
    # хост отдельно от всего остального (путь, запрос, якорь)
    m = re.match(r"^([^/?#]*)(.*)$", s, flags=re.DOTALL)
    hostpart, rest = m.group(1), m.group(2)
    # порт и логин остаются при хосте, точку рвём в самом имени
    userinfo, sep, name = hostpart.rpartition("@")
    name, colon, port = name.partition(":")
    if "." in name:
        head, _, zone = name.rpartition(".")
        name = f"{head}[.]{zone}"
    return f"{userinfo}{sep}{name}{colon}{port}{rest}"


def visible(url):
    """Как адрес показывается читателю: кликабельный — целиком со схемой (по ней
    сайт и телеграм его и линкуют), все прочие — дефангнутыми и без схемы."""
    return str(url or "").strip() if is_clickable(url) else defang(url)
