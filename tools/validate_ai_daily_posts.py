#!/usr/bin/env python3
"""Validate the two daily Hexo posts before they are committed."""

from __future__ import annotations

import re
import sys
from pathlib import Path


REQUIRED_FIELDS = ("title", "date", "categories", "tags", "cover", "coverWidth", "coverHeight")
PRIVATE_PATTERNS = (
    r"192\.168\.102\.148",
    r"\b(?:10|172\.(?:1[6-9]|2\d|3[0-1])|192\.168)\.\d+\.\d+",
    r"example\.com",
    r"file://",
)


def parse_front_matter(path: Path) -> tuple[dict[str, str], str]:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"{path}: missing front matter")
    _, raw, body = text.split("---", 2)
    fields = {}
    lines = raw.splitlines()
    current_key = None
    for line in lines:
        if ":" in line and not line.startswith((" ", "-")):
            key, value = line.split(":", 1)
            current_key = key.strip()
            fields[current_key] = value.strip()
        elif line.lstrip().startswith("-") and current_key in {"categories", "tags"}:
            fields[current_key] = f"{fields.get(current_key, '')} {line.lstrip()[1:].strip()}".strip()
    return fields, body.strip()


def main() -> int:
    if len(sys.argv) != 2 or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", sys.argv[1]):
        print("usage: validate_ai_daily_posts.py YYYY-MM-DD", file=sys.stderr)
        return 2
    root = Path(__file__).resolve().parents[1]
    day = sys.argv[1]
    errors = []
    for section, category in (("ai_diary", "ai_diary"), ("ai_tech", "ai_tech")):
        files = sorted((root / "source" / "_posts" / section).glob(f"{day}-*.md"))
        if len(files) != 1:
            errors.append(f"{section}: expected exactly one post for {day}, found {len(files)}")
            continue
        fields, body = parse_front_matter(files[0])
        missing = [field for field in REQUIRED_FIELDS if field not in fields]
        if missing:
            errors.append(f"{files[0]}: missing front matter {', '.join(missing)}")
        if category not in fields.get("categories", "").lower():
            errors.append(f"{files[0]}: category must contain {category}")
        if len(fields.get("title", "").strip()) > 120:
            errors.append(f"{files[0]}: title is too long")
        if len(body) < 1000:
            errors.append(f"{files[0]}: body is shorter than 1000 characters")
        for pattern in PRIVATE_PATTERNS:
            if re.search(pattern, files[0].read_text(encoding="utf-8"), re.IGNORECASE):
                errors.append(f"{files[0]}: contains forbidden pattern {pattern}")
    if errors:
        print("\n".join(f"ERROR: {error}" for error in errors))
        return 1
    print(f"PASS: validated AI Diary and AI Tech for {day}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
