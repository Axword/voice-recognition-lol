#!/usr/bin/env python3
"""Copy style check.

Fails the build when a long dash shows up in text the user can read. Two things
are rejected:

    * the em dash (U+2014) anywhere,
    * the en dash (U+2013) used as punctuation, meaning surrounded by spaces.

An en dash inside a numeric range such as 10-20 written with U+2013 is left
alone, because that is typography rather than a sentence connector.

Scanned: webui/src, webui/index.html, README.md, docs, and Python string
literals in server/ and controller/. Binary files and node_modules are skipped.
In Markdown, code spans and fenced blocks are exempt, since a dash there is a
character sample rather than prose.

Usage: python tools/check_copy.py [--root PATH]
"""

from __future__ import annotations

import argparse
import ast
import re
import sys
from pathlib import Path

EM_DASH = "—"
EN_DASH = "–"

EN_DASH_AS_PUNCTUATION = re.compile(r"(?:\s|&nbsp;)" + EN_DASH + r"(?:\s|&nbsp;)")

CODE_SPAN = re.compile(r"`[^`]*`")
FENCE = re.compile(r"^\s*(```|~~~)")

SKIP_DIRS = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv", "venv", ".ruff_cache"}

TEXT_SUFFIXES = {
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".html",
    ".css",
    ".scss",
    ".md",
    ".json",
    ".txt",
    ".yml",
    ".yaml",
    ".svg",
}

# Directories scanned as plain text, every eligible file inside them.
TEXT_TREES = ("webui/src", "docs")

# Individual plain text files.
TEXT_FILES = ("webui/index.html", "README.md")

# Python packages where only string literals are inspected.
PYTHON_TREES = ("server", "controller")


class Violation:
    __slots__ = ("kind", "line", "path", "text")

    def __init__(self, path: Path, line: int, text: str, kind: str) -> None:
        self.path = path
        self.line = line
        self.text = text
        self.kind = kind


def _offending(text: str) -> str | None:
    if EM_DASH in text:
        return "em dash"
    if EN_DASH_AS_PUNCTUATION.search(text):
        return "en dash used as punctuation"
    return None


def _is_binary(path: Path) -> bool:
    try:
        chunk = path.open("rb").read(4096)
    except OSError:
        return True
    return b"\x00" in chunk


def _read_lines(path: Path) -> list[str] | None:
    if _is_binary(path):
        return None
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError):
        return None


def _walk(root: Path):
    for path in sorted(root.rglob("*")):
        if any(part in SKIP_DIRS for part in path.parts):
            continue
        if path.is_file():
            yield path


def check_text_file(path: Path, root: Path) -> list[Violation]:
    lines = _read_lines(path)
    if lines is None:
        return []
    is_markdown = path.suffix.lower() in {".md", ".markdown"}
    found: list[Violation] = []
    in_fence = False
    for number, line in enumerate(lines, start=1):
        candidate = line
        if is_markdown:
            if FENCE.match(line):
                in_fence = not in_fence
                continue
            if in_fence:
                continue
            candidate = CODE_SPAN.sub("", line)
        kind = _offending(candidate)
        if kind:
            found.append(Violation(path.relative_to(root), number, line.strip(), kind))
    return found


def check_python_file(path: Path, root: Path) -> list[Violation]:
    source = _read_lines(path)
    if source is None:
        return []
    try:
        tree = ast.parse("\n".join(source), filename=str(path))
    except SyntaxError as exc:
        print(f"{path}: could not parse, {exc}", file=sys.stderr)
        return []

    found: list[Violation] = []
    seen: set[tuple[int, str]] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        kind = _offending(node.value)
        if not kind:
            continue
        line = node.lineno
        key = (line, kind)
        if key in seen:
            continue
        seen.add(key)
        text = source[line - 1].strip() if line - 1 < len(source) else node.value.strip()
        found.append(Violation(path.relative_to(root), line, text, kind))
    return found


def collect(root: Path) -> list[Violation]:
    found: list[Violation] = []

    for relative in TEXT_FILES:
        path = root / relative
        if path.is_file():
            found.extend(check_text_file(path, root))

    for relative in TEXT_TREES:
        tree_root = root / relative
        if not tree_root.is_dir():
            continue
        for path in _walk(tree_root):
            if path.suffix.lower() in TEXT_SUFFIXES:
                found.extend(check_text_file(path, root))

    for relative in PYTHON_TREES:
        tree_root = root / relative
        if not tree_root.is_dir():
            continue
        for path in _walk(tree_root):
            if path.suffix == ".py":
                found.extend(check_python_file(path, root))

    found.sort(key=lambda item: (str(item.path), item.line))
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Reject long dashes in user facing copy.")
    parser.add_argument("--root", default=Path(__file__).resolve().parent.parent, type=Path)
    args = parser.parse_args(argv)

    root: Path = args.root.resolve()
    violations = collect(root)

    if not violations:
        print("check_copy: no long dashes found in user facing text")
        return 0

    print(f"check_copy: {len(violations)} violation(s)\n", file=sys.stderr)
    for item in violations:
        print(f"{item.path}:{item.line}: {item.text}", file=sys.stderr)
        print(f"    {item.kind}", file=sys.stderr)
    print(
        "\nUse a comma, a colon or a plain hyphen instead. "
        "Scanned: webui/src, webui/index.html, README.md, docs, "
        "and Python string literals in server/ and controller/.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
