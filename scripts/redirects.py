#!/usr/bin/env python3
"""Реестр переносов адресов: `redirects.yml` в корне базы (куратор 07.11.2026, «го»).

Адрес страницы сайта - идентификатор файла: кампания `C0103` -> /campaigns/C0103/, процедура
`C0103.T0019` -> /procedures/C0103.T0019/. Файл ушёл из `campaigns/` (кампанию слили в другую,
технику разделили, текст сняли с сайта) - адрес умирает, а на него ведут посты Telegram, поисковики
и чужие ссылки. Реестр говорит сайту, куда вести читателя со старого адреса.

    python scripts/redirects.py --check [КОРЕНЬ]        # CI и локально: код 1, если адрес пропал молча
    python scripts/redirects.py --suggest [КОРЕНЬ]      # черновик строк для пропавших адресов (в stdout)
    python scripts/redirects.py --export ФАЙЛ [КОРЕНЬ]  # JSON для сайта (CI кладёт в релиз `stix`)

Правило: каждый идентификатор, который когда-либо лежал в `campaigns/` ветки main и которого там
больше нет, должен стоять в реестре как `from`. Иначе проверка красная и merge не проходит.
Пишет строку тот, кто переносит файл; `--suggest` подсказывает черновик по истории git.

Запись реестра:
    - from: C0103.T0019          # старый адрес
      to: [C1205.T0019]          # новые адреса; при разделении - несколько; при снятии с сайта - кампания или []
      reason: merged             # merged - слили в другую сущность; split - разделили; renamed - сменили номер;
                                 # unpublished - сняли с сайта (файл лежит в unpublished/)
      date: 2026-11-07           # когда перенесли

Цепочек нет: `to` всегда существующий файл в `campaigns/`, не другой `from`.
"""
import datetime
import json
import os
import re
import subprocess
import sys

import yaml

ID_RE = re.compile(r"^C\d{4}(\.T\d{4}(\.\d{3})?)?$")
REASONS = ("merged", "split", "renamed", "unpublished")
REGISTRY = "redirects.yml"


def find_root(start):
    p = os.path.abspath(start)
    while not os.path.isdir(os.path.join(p, "techniques")):
        parent = os.path.dirname(p)
        if parent == p:
            sys.exit(f"корень базы не найден от {start}")
        p = parent
    return p


def ids_in(folder):
    """Идентификаторы файлов <folder>/C*/C*.yml (кампании и процедуры)."""
    out = set()
    if not os.path.isdir(folder):
        return out
    for camp in os.listdir(folder):
        d = os.path.join(folder, camp)
        if not os.path.isdir(d):
            continue
        for f in os.listdir(d):
            if f.endswith(".yml"):
                out.add(f[:-4])
    return out


def ids_ever(root):
    """Идентификаторы, когда-либо добавленные в campaigns/ (история текущей ветки; в CI - fetch-depth: 0)."""
    try:
        out = subprocess.run(
            ["git", "-C", root, "log", "--format=", "--name-only", "--diff-filter=A", "--", "campaigns"],
            capture_output=True, text=True, check=True).stdout
    except (subprocess.CalledProcessError, FileNotFoundError) as e:
        sys.exit(f"git log не отработал: {e}")
    ids = set()
    for line in out.splitlines():
        m = re.match(r"^campaigns/[^/]+/([^/]+)\.yml$", line.strip())
        if m:
            ids.add(m.group(1))
    return ids


def load_registry(root):
    path = os.path.join(root, REGISTRY)
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data or []


def check(root):
    errors = []
    reg = load_registry(root)
    if not isinstance(reg, list):
        return [f"{REGISTRY}: ожидается список записей"]
    current = ids_in(os.path.join(root, "campaigns"))
    unpublished = ids_in(os.path.join(root, "unpublished", "campaigns"))
    froms = {e.get("from") for e in reg if isinstance(e, dict)}
    seen = set()
    for i, e in enumerate(reg, 1):
        where = f"{REGISTRY} запись {i}"
        if not isinstance(e, dict):
            errors.append(f"{where}: не словарь")
            continue
        extra = set(e) - {"from", "to", "reason", "date"}
        if extra:
            errors.append(f"{where}: лишние поля {sorted(extra)}")
        src, dst, reason, date = e.get("from"), e.get("to"), e.get("reason"), e.get("date")
        if not isinstance(src, str) or not ID_RE.match(src):
            errors.append(f"{where}: from должен быть идентификатором кампании или процедуры, не {src!r}")
            continue
        where = f"{REGISTRY} {src}"
        if src in seen:
            errors.append(f"{where}: повтор from")
        seen.add(src)
        if src in current:
            errors.append(f"{where}: файл ещё лежит в campaigns/, переносить адрес нечего")
        if reason not in REASONS:
            errors.append(f"{where}: reason должен быть одним из {REASONS}, не {reason!r}")
        if not isinstance(date, (datetime.date, str)) or not re.match(r"^\d{4}-\d{2}-\d{2}$", str(date)):
            errors.append(f"{where}: date в виде ГГГГ-ММ-ДД, не {date!r}")
        if not isinstance(dst, list) or not all(isinstance(t, str) for t in dst):
            errors.append(f"{where}: to должен быть списком идентификаторов")
            continue
        for t in dst:
            if not ID_RE.match(t):
                errors.append(f"{where}: to {t!r} не идентификатор")
            elif t in froms:
                errors.append(f"{where}: to {t} сам перенесён - цепочки запрещены, веди сразу на конечный адрес")
            elif t not in current:
                errors.append(f"{where}: to {t} нет в campaigns/")
            if t == src:
                errors.append(f"{where}: to совпадает с from")
        if reason == "unpublished":
            if src not in unpublished:
                errors.append(f"{where}: reason unpublished, но файла нет в unpublished/campaigns/")
            if len(dst) > 1:
                errors.append(f"{where}: при снятии с сайта to - кампания или пустой список")
        elif reason == "split":
            if len(dst) < 2:
                errors.append(f"{where}: split - два и больше новых адресов")
        elif len(dst) != 1:
            errors.append(f"{where}: {reason} - ровно один новый адрес")
    gone = ids_ever(root) - current
    silent = sorted(gone - seen)
    for g in silent:
        hint = " (лежит в unpublished/)" if g in unpublished else ""
        errors.append(f"адрес {g} пропал из campaigns/ без записи в {REGISTRY}{hint}; черновик: --suggest")
    return errors


def suggest(root):
    reg = {e.get("from") for e in load_registry(root) if isinstance(e, dict)}
    current = ids_in(os.path.join(root, "campaigns"))
    unpublished = ids_in(os.path.join(root, "unpublished", "campaigns"))
    gone = sorted((ids_ever(root) - current) - reg)
    today = datetime.date.today().isoformat()
    if not gone:
        print("# пропавших адресов нет", file=sys.stderr)
        return 0
    for g in gone:
        if g in unpublished:
            camp = g.split(".")[0]
            to = [camp] if camp in current and camp != g else []
            print(f"- from: {g}\n  to: {json.dumps(to)}\n  reason: unpublished\n  date: {today}")
        else:
            print(f"- from: {g}\n  to: []  # TODO: новый адрес\n  reason: merged  # merged | split | renamed\n  date: {today}")
    return 0


def export(root, out):
    reg = load_registry(root)
    data = [{"from": e["from"], "to": list(e.get("to") or []), "reason": e["reason"], "date": str(e["date"])}
            for e in reg]
    os.makedirs(os.path.dirname(os.path.abspath(out)), exist_ok=True)
    with open(out, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=1)
        f.write("\n")
    print(f"{out}: записей {len(data)}")
    return 0


def main(argv):
    args = list(argv)
    mode = "--check"
    out = None
    if args and args[0] in ("--check", "--suggest", "--export"):
        mode = args.pop(0)
        if mode == "--export":
            if not args:
                sys.exit("--export ФАЙЛ")
            out = args.pop(0)
    root = find_root(args[0] if args else os.path.join(os.path.dirname(os.path.abspath(__file__)), ".."))
    if mode == "--suggest":
        return suggest(root)
    errors = check(root)
    if errors:
        print("\n".join(errors))
        print(f"ошибок: {len(errors)}")
        return 1
    n = len(load_registry(root))
    print(f"{REGISTRY}: записей {n}; пропавших адресов без записи нет")
    if mode == "--export":
        return export(root, out)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
