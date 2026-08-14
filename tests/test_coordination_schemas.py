"""Validate the coordination markdown files conform to their schemas.

Run this script before any commit that touches `coordination/`. A
malformed entry blocks the commit, not a future session.

Schemas validated:
- DECISIONS.md: every ADR-NNN heading has Status, Date, Context,
  Decision, Consequences fields.
- INVARIANTS.md: every INV-NNN heading has Scope, Contract, Verified-by
  fields.
- GLOSSARY.md: every term heading has Symbol, Definition, Reference
  fields.
- OPEN_QUESTIONS.md: every Q-NNN heading has Status, Track, Blocks and
  Context fields.
- TODO.md: file exists and is non-empty.
- JOURNAL.md: file exists and is non-empty.

The validator returns exit code 0 on success and 1 on any violation; it
prints the offending file and heading.

This script is dependency-free (standard library only).
"""

from __future__ import annotations

import pathlib
import re

COORDINATION = pathlib.Path(__file__).resolve().parent.parent / "coordination"


def _split_into_entries(text: str, heading_pattern: re.Pattern[str]) -> list[tuple[str, str]]:
    """Split markdown into (heading, body) tuples on every level-2 heading
    that matches `heading_pattern`."""
    lines = text.splitlines()
    entries: list[tuple[str, str]] = []
    current_heading: str | None = None
    current_body: list[str] = []

    for line in lines:
        if heading_pattern.match(line):
            if current_heading is not None:
                entries.append((current_heading, "\n".join(current_body)))
            current_heading = line
            current_body = []
        elif current_heading is not None:
            current_body.append(line)

    if current_heading is not None:
        entries.append((current_heading, "\n".join(current_body)))

    return entries


def _has_field(body: str, field: str) -> bool:
    """Check whether the body contains a markdown field like `- Field: ...`."""
    pattern = re.compile(rf"^\s*[-*]\s*{re.escape(field)}\s*:", re.MULTILINE)
    return pattern.search(body) is not None


def validate_decisions(path: pathlib.Path) -> list[str]:
    if not path.exists():
        return [f"missing file: {path}"]
    text = path.read_text(encoding="utf-8")
    entries = _split_into_entries(text, re.compile(r"^##\s+ADR-\d+\s*[—-]"))
    required = ["Status", "Date", "Context", "Decision", "Consequences"]
    errors: list[str] = []
    for heading, body in entries:
        for field in required:
            if not _has_field(body, field):
                errors.append(f"{path.name}: {heading.strip()} missing field '{field}'")
    return errors


def validate_invariants(path: pathlib.Path) -> list[str]:
    if not path.exists():
        return [f"missing file: {path}"]
    text = path.read_text(encoding="utf-8")
    entries = _split_into_entries(text, re.compile(r"^##\s+INV-\d+\s*[—-]"))
    required = ["Scope", "Contract", "Verified-by"]
    errors: list[str] = []
    for heading, body in entries:
        for field in required:
            if not _has_field(body, field):
                errors.append(f"{path.name}: {heading.strip()} missing field '{field}'")
    return errors


def validate_glossary(path: pathlib.Path) -> list[str]:
    if not path.exists():
        return [f"missing file: {path}"]
    text = path.read_text(encoding="utf-8")
    # Glossary entries are level-2 headings whose text is the term itself.
    # Skip headings starting with placeholder markers like "Example".
    entries = _split_into_entries(text, re.compile(r"^##\s+(?!Example)\S"))
    required = ["Symbol", "Definition", "Used in"]
    errors: list[str] = []
    for heading, body in entries:
        # Skip entries explicitly labelled as templates / placeholders.
        if "placeholder" in heading.lower() or "<term placeholder>" in heading.lower():
            continue
        for field in required:
            if not _has_field(body, field):
                errors.append(f"{path.name}: {heading.strip()} missing field '{field}'")
    return errors


def validate_open_questions(path: pathlib.Path) -> list[str]:
    if not path.exists():
        return [f"missing file: {path}"]
    text = path.read_text(encoding="utf-8")
    entries = _split_into_entries(text, re.compile(r"^##\s+Q-\d+\s*[—-]"))
    required = ["Status", "Track", "Blocks", "Context"]
    errors: list[str] = []
    for heading, body in entries:
        for field in required:
            if not _has_field(body, field):
                errors.append(f"{path.name}: {heading.strip()} missing field '{field}'")
    return errors


def validate_exists_and_nonempty(path: pathlib.Path) -> list[str]:
    if not path.exists():
        return [f"missing file: {path}"]
    if not path.read_text(encoding="utf-8").strip():
        return [f"empty file: {path}"]
    return []


def main() -> int:
    errors: list[str] = []
    errors.extend(validate_decisions(COORDINATION / "DECISIONS.md"))
    errors.extend(validate_invariants(COORDINATION / "INVARIANTS.md"))
    errors.extend(validate_glossary(COORDINATION / "GLOSSARY.md"))
    errors.extend(validate_open_questions(COORDINATION / "OPEN_QUESTIONS.md"))
    errors.extend(validate_exists_and_nonempty(COORDINATION / "TODO.md"))
    errors.extend(validate_exists_and_nonempty(COORDINATION / "JOURNAL.md"))

    if errors:
        print("Coordination schema validation FAILED:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print("Coordination schema validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
