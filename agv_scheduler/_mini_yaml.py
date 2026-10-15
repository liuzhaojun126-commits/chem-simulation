# -*- coding: utf-8 -*-
"""极简 YAML 子集解析器（无第三方依赖）。

只解析本工程 config/*.yaml 用到的子集：
  - 注释（#）
  - 缩进嵌套 mapping / list
  - block list（- item / - {inline map} / - [inline list]）
  - inline map {k: v, ...} / inline list [a, b, ...]
  - 标量：int / float / bool / null / 字符串
优先使用 PyYAML（若已安装），否则回退到本解析器。
"""
from __future__ import annotations

from typing import Any


def _strip_comment(s: str) -> str:
    in_q = None
    for i, ch in enumerate(s):
        if ch in ("\"", "'"):
            if in_q == ch:
                in_q = None
            elif in_q is None:
                in_q = ch
        elif ch == "#" and in_q is None:
            return s[:i]
    return s


def _split_top(s: str, sep: str) -> list:
    """在顶层（不在 {} 或 [] 内）按 sep 切分。"""
    parts = []
    depth = 0
    cur = []
    for ch in s:
        if ch in "{[":
            depth += 1
            cur.append(ch)
        elif ch in "}]":
            depth -= 1
            cur.append(ch)
        elif ch == sep and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
    if cur:
        parts.append("".join(cur).strip())
    return parts


def _parse_scalar(s: str) -> Any:
    s = s.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in ("\"", "'"):
        return s[1:-1]
    low = s.lower()
    if low in ("true", "false"):
        return low == "true"
    if low in ("null", "none", "~"):
        return None
    try:
        return int(s)
    except ValueError:
        pass
    try:
        return float(s)
    except ValueError:
        pass
    return s


def _parse_inline(s: str) -> Any:
    s = s.strip()
    if not s:
        return None
    if s.startswith("{"):
        s = s[1:-1].strip()
        if not s:
            return {}
        d = {}
        for part in _split_top(s, ","):
            if ":" not in part:
                continue
            k, v = part.split(":", 1)
            d[k.strip()] = _parse_inline(v.strip())
        return d
    if s.startswith("["):
        s = s[1:-1].strip()
        if not s:
            return []
        return [_parse_inline(p) for p in _split_top(s, ",")]
    return _parse_scalar(s)


def _parse_block(lines: list, i: int):
    indent = lines[i][0]
    content = lines[i][1]
    if content.startswith("- "):
        return _parse_list(lines, i, indent)
    return _parse_map(lines, i, indent)


def _parse_map(lines: list, i: int, indent: int):
    result = {}
    while i < len(lines):
        il, content = lines[i]
        if il < indent:
            break
        if il > indent or content.startswith("- "):
            break
        if ":" not in content:
            i += 1
            continue
        key, rest = content.split(":", 1)
        key = key.strip().strip("\"'")
        rest = rest.strip()
        if rest == "":
            if i + 1 < len(lines) and lines[i + 1][0] > indent:
                value, i = _parse_block(lines, i + 1)
            else:
                value, i = None, i + 1
        else:
            value, i = _parse_inline(rest), i + 1
        result[key] = value
    return result, i


def _parse_list(lines: list, i: int, indent: int):
    result = []
    while i < len(lines):
        il, content = lines[i]
        if il < indent:
            break
        if il > indent or not content.startswith("- "):
            break
        rest = content[2:].strip()
        if rest in ("", "-"):
            if i + 1 < len(lines) and lines[i + 1][0] > indent:
                value, i = _parse_block(lines, i + 1)
            else:
                value, i = None, i + 1
        else:
            value, i = _parse_inline(rest), i + 1
        result.append(value)
    return result, i


def loads(text: str) -> Any:
    lines = []
    for raw in text.splitlines():
        s = _strip_comment(raw)
        if not s.strip():
            continue
        indent = len(s) - len(s.lstrip())
        lines.append((indent, s.strip()))
    if not lines:
        return {}
    result, _ = _parse_block(lines, 0)
    return result


def load(path: str) -> Any:
    try:
        import yaml as _pyyaml
        with open(path, "r", encoding="utf-8") as f:
            return _pyyaml.safe_load(f)
    except ImportError:
        with open(path, "r", encoding="utf-8") as f:
            return loads(f.read())
