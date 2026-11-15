#!/usr/bin/env python3
"""Проза файлов базы: одна фраза на строку.

    python scripts/resplit.py [--check] [файл.yml | папка ...]

Без аргументов проходит tactics, techniques, actors, tools, campaigns и unpublished рядом со scripts/.
Абзац блока `|` переразбивается делителем kbformat.split_sentences: текст и абзацы не меняются,
меняется только то, где кончаются строки. Абзац, разбивка которого не меняется, остаётся байт в байт.
Однострочное описание (description.<язык>) из нескольких фраз становится блоком `|-`, а блок,
от которого осталась одна строка, - строкой в том виде, в каком её пишет дампер базы.
Остальные строки файла не трогаются, в том числе пустые строки и строки из пробелов в конце файла.
Перед записью файл читается парсером YAML: если что-то кроме разбивки на строки изменилось бы, файл не пишется.

--check: только показать, какие файлы изменились бы; код выхода 1, если такие есть.
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import kbformat  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_DIRS = ("tactics", "techniques", "actors", "tools", "campaigns", "unpublished")

_BLOCK_RE = re.compile(r"^( *)([^\s#-][^:]*):[ ]+\|([+-]?)\d?[ ]*$")
_PLAIN_RE = re.compile(r"^( *)(en|uk|ru):[ ]+(?![|>])(\S.*)$")
_KEY_RE = re.compile(r"^( *)([^\s#-][^:]*):(?:[ ]|$)")


def _indent(line: str) -> int:
    return len(line) - len(line.lstrip(" "))


def _resplit_body(lines: list[str], ind: str) -> list[str]:
    """Строки тела блока (с отступом) -> те же строки с новой разбивкой абзацев."""
    out, para = [], []

    def flush():
        if not para:
            return
        old = [x.strip() for x in para]
        new = kbformat.split_sentences(" ".join(old))
        out.extend(para if new == old else [ind + x for x in new])
        para.clear()

    for line in lines:
        if line.strip():
            para.append(line)
        else:
            flush()
            out.append(line)
    flush()
    return out


def resplit_text(text: str) -> str:
    lines = text.split("\n")
    out, i, parents = [], 0, []
    while i < len(lines):
        line = lines[i]
        m_key = _KEY_RE.match(line)
        if m_key:
            ki = len(m_key.group(1))
            while parents and parents[-1][0] >= ki:
                parents.pop()
        m_block = _BLOCK_RE.match(line)
        if m_block:
            head = _indent(line)
            j = i + 1
            while j < len(lines) and (not lines[j].strip() or _indent(lines[j]) > head):
                j += 1
            last = j
            while last > i + 1 and not lines[last - 1].strip():
                last -= 1
            old_body = body = lines[i + 1:last]
            if body:
                ind = " " * min(_indent(x) for x in body if x.strip())
                body = _resplit_body(body, ind)
            if body != old_body and len(body) == 1 and m_block.group(3) == "-":
                # проза из одной строки (цитата из нескольких фраз склеилась): тот вид,
                # в каком её пишет дампер базы, - строка, а не блок
                one = kbformat.dump_yaml({m_block.group(2): body[0].strip()}).rstrip("\n")
                if "\n" not in one:
                    out.append(m_block.group(1) + one)
                    out.extend(lines[last:j])
                    i = j
                    continue
            out.append(line)
            out.extend(body)
            out.extend(lines[last:j])
            i = j
            continue
        m = _PLAIN_RE.match(line)
        if m and parents and parents[-1][1] == "description":
            value = kbformat.yaml.safe_load("x: " + m.group(3))["x"]
            if isinstance(value, str) and "\n" not in value:
                parts = kbformat.split_sentences(value)
                if len(parts) > 1:
                    ind = m.group(1)
                    out.append(f"{ind}{m.group(2)}: |-")
                    out.extend(f"{ind}  {x}" for x in parts)
                    i += 1
                    continue
        if m_key:
            parents.append((len(m_key.group(1)), m_key.group(2).strip()))
        out.append(line)
        i += 1
    return "\n".join(out)


def _same(a, b) -> bool:
    """Документы равны с точностью до разбивки прозы на строки."""
    if isinstance(a, dict) and isinstance(b, dict):
        return list(a) == list(b) and all(_same(a[k], b[k]) for k in a)
    if isinstance(a, list) and isinstance(b, list):
        return len(a) == len(b) and all(_same(x, y) for x, y in zip(a, b))
    if isinstance(a, str) and isinstance(b, str):
        return kbformat.prose_key(a) == kbformat.prose_key(b)
    return a == b


def files(args):
    targets = args or [os.path.join(ROOT, d) for d in DEFAULT_DIRS if os.path.isdir(os.path.join(ROOT, d))]
    for t in targets:
        if os.path.isdir(t):
            for d, _, fs in os.walk(t):
                yield from (os.path.join(d, f) for f in sorted(fs) if f.endswith(".yml"))
        elif t.endswith(".yml"):
            yield t


def main(argv):
    check = "--check" in argv
    args = [a for a in argv if a != "--check"]
    changed, refused = [], []
    for path in files(args):
        with open(path, encoding="utf-8") as f:
            text = f.read()
        new = resplit_text(text)
        if new == text:
            continue
        if not _same(kbformat.yaml.safe_load(text), kbformat.yaml.safe_load(new)):
            refused.append(path)
            continue
        changed.append(path)
        if not check:
            with open(path, "w", encoding="utf-8") as f:
                f.write(new)
    for p in changed:
        print(("изменился бы " if check else "переразбит ") + os.path.relpath(p))
    for p in refused:
        print("НЕ ТРОНУТ (изменилось бы не только разбиение): " + os.path.relpath(p))
    print(f"файлов {'к переразбивке' if check else 'переразбито'}: {len(changed)}, не тронуто: {len(refused)}")
    return 1 if (refused or (check and changed)) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
