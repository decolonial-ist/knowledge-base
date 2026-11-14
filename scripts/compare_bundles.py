#!/usr/bin/env python3
"""Сравнение двух STIX-бандлов экспортёра: из таблицы и из файлов базы знаний.

    python3 scripts/compare_bundles.py sheet.json kb.json

Оба бандла собраны с --stable-ids и одним --now, поэтому различаться могут только данные.
Объекты сопоставляются по id (порядок в бандле не важен), поля сравниваются поштучно;
у текстов показывается первое расхождение. Код возврата 0 = бандлы совпадают.
"""
import json
import re
import sys


def norm(v):
    """Пробелы в текстах не считаются: файл не хранит хвостовые пробелы строк."""
    if isinstance(v, str):
        # хвостовые пробелы и повторные пустые строки не считаются: файл хранит абзацы одной пустой строкой
        return re.sub(r"\n{2,}", "\n", re.sub(r"[ \t]+\n", "\n", re.sub(r"[ \t]+", " ", v))).strip()
    if isinstance(v, list):
        items = [norm(x) for x in v]
        # манифест коллекции: порядок объектов зависит от порядка чтения, сравниваем как множество
        if items and all(isinstance(x, dict) and "object_ref" in x for x in items):
            return sorted(items, key=lambda d: d["object_ref"])
        return items
    if isinstance(v, dict):
        return {k: norm(x) for k, x in v.items()}
    return v


def first_diff(a, b):
    i = 0
    while i < min(len(a), len(b)) and a[i] == b[i]:
        i += 1
    return f"…{a[max(0, i - 40):i + 60]!r}  <->  …{b[max(0, i - 40):i + 60]!r}"


def main(p1, p2):
    o1 = {o["id"]: o for o in json.load(open(p1, encoding="utf-8"))["objects"]}
    o2 = {o["id"]: o for o in json.load(open(p2, encoding="utf-8"))["objects"]}
    only1, only2 = sorted(set(o1) - set(o2)), sorted(set(o2) - set(o1))
    # id связи - хэш русского описания: нормализованный текст даёт другой id. Связи без пары по id
    # сопоставляются по (тип связи, источник, цель, нормализованное описание): одна пара источник-цель
    # может нести несколько связей с разными текстами (по строке процедуры на каждую)
    key = lambda o: (o["type"], o.get("relationship_type"), o.get("source_ref"), o.get("target_ref"),
                     norm(o.get("description", "")))
    idx2 = {}
    for j in only2:
        if o2[j]["type"] == "relationship":
            idx2.setdefault(key(o2[j]), []).append(j)
    rematched = {}
    for i in list(only1):
        if o1[i]["type"] != "relationship":
            continue
        lst = idx2.get(key(o1[i]))
        if lst:
            j = lst.pop()
            rematched[i] = j
            only1.remove(i); only2.remove(j)
    for i, j in rematched.items():
        o2[i] = o2.pop(j)   # дальше сравнение по общему ключу
    print(f"связей сопоставлено по источнику, цели и тексту (другой id из-за пробелов): {len(rematched)}")
    label = lambda o: f"{o.get('type')} {(o.get('external_references') or [{}])[0].get('external_id', '')} «{str(o.get('name', ''))[:50]}»"
    print(f"объектов: {len(o1)} / {len(o2)}; только в первом: {len(only1)}, только во втором: {len(only2)}")
    for i in only1[:30]:
        print("  - только в первом:", label(o1[i]), i)
    for i in only2[:30]:
        print("  - только во втором:", label(o2[i]), i)
    ndiff = 0
    field_counts = {}
    for i in sorted(set(o1) & set(o2)):
        a, b = o1[i], o2[i]
        for k in sorted(set(a) | set(b)):
            if k == "id" and i in rematched:
                continue
            if norm(a.get(k)) != norm(b.get(k)):
                ndiff += 1
                field_counts[k] = field_counts.get(k, 0) + 1
                if field_counts[k] <= 5:
                    va, vb = json.dumps(a.get(k), ensure_ascii=False), json.dumps(b.get(k), ensure_ascii=False)
                    print(f"  ~ {label(a)} [{k}]: {first_diff(va, vb)}")
    print("расхождений в полях:", ndiff, dict(sorted(field_counts.items())))
    return 0 if not (only1 or only2 or ndiff) else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1], sys.argv[2]))
