"""Tolerant parsers for the three source formats.

The sample files are intentionally messy: the CSV has every row wrapped in
quotes (so a naive reader sees ONE column), the JSON has each line wrapped in
quotes with doubled quotes, and all files carry a UTF-8 BOM. Parsers repair
these before parsing and raise ParseError on anything unrecoverable.
"""
import csv
import io
import json
import xml.etree.ElementTree as ET


class ParseError(ValueError):
    pass


def _decode(raw: bytes | str) -> str:
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8-sig", errors="replace")
    return raw.lstrip("\ufeff")


def parse_csv(raw) -> list[dict]:
    text = _decode(raw)
    lines = [l.strip() for l in text.splitlines() if l.strip()]
    fixed = []
    for l in lines:
        # Repair rows wrapped in one pair of quotes: "a,b,c" -> a,b,c
        if l.startswith('"') and l.endswith('"') and l.count('"') == 2:
            l = l[1:-1]
        fixed.append(l)
    reader = csv.DictReader(io.StringIO("\n".join(fixed)))
    if not reader.fieldnames:
        raise ParseError("CSV has no header row")
    rows = []
    for r in reader:
        rows.append({(k or "").strip(): (v or "").strip() for k, v in r.items()})
    return rows


def _repair_json(text: str) -> str:
    """Undo CSV-style quoting: every line wrapped in "..." with "" escapes."""
    lines = []
    for l in text.splitlines():
        s = l.strip()
        if s.startswith('"') and (s.endswith('"') or s.endswith('",')):
            tail = "," if s.endswith('",') else ""
            s = s[1: -2 if tail else -1].replace('""', '"') + tail
            lines.append(s)
        else:
            lines.append(l)
    return "\n".join(lines)


def parse_json(raw):
    text = _decode(raw)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    try:
        return json.loads(_repair_json(text))
    except json.JSONDecodeError as e:
        raise ParseError(f"Invalid JSON: {e}") from e


def parse_xml(raw) -> list[dict]:
    text = _decode(raw).strip()
    try:
        root = ET.fromstring(text)
    except ET.ParseError as e:
        raise ParseError(f"Invalid XML: {e}") from e
    out = []
    for node in root:
        out.append({c.tag: (c.text or "").strip() for c in node})
    return out
