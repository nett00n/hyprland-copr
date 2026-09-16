#!/usr/bin/env python3
"""Sort string lists and dict keys in packages.yaml.

Sorts build_requires, requires, and files lists alphabetically within each
package, deduplicating entries as it goes. Also sorts dict keys alphabetically
within all mappings, including the top-level packages dict (package names are
sorted alphabetically). Lists of dicts (sources, bundled_deps) are left
untouched.

Sorting and dedup of list items (_item_sort_key) are case-insensitive and
ignore a leading "- " and surrounding quote characters, so "Foo", "foo", and
'"foo"' are treated as the same item and only the first-encountered spelling
is kept.

Comment lines within a sorted list block are floated to the top of the block.

--dry-run prints what would change but skips the write path's YAML re-parse
validation (process_content's output is not re-validated in dry-run mode).

Usage:
    python3 scripts/sort-yaml-lists.py           # sort in-place
    python3 scripts/sort-yaml-lists.py --dry-run  # preview only
"""

import argparse
import re
import sys
from collections import Counter

import yaml

from lib.paths import PACKAGES_YAML, ROOT

SORTABLE_KEYS: frozenset[str] = frozenset({"build_requires", "requires", "files"})
PRESERVE_DICT_ORDER: frozenset[str] = frozenset()


def _item_sort_key(line: str) -> str:
    return line.strip().removeprefix("- ").strip("\"'").lower()


def _sort_block(lines: list[str]) -> list[str]:
    """Sort and deduplicate list items; comment lines float to the top."""
    comments = [ln for ln in lines if ln.strip().startswith("#")]
    items = [ln for ln in lines if not ln.strip().startswith("#")]
    items.sort(key=_item_sort_key)
    seen: set[str] = set()
    deduped: list[str] = []
    for ln in items:
        key = _item_sort_key(ln)
        if key not in seen:
            seen.add(key)
            deduped.append(ln)
    return comments + deduped


def _dict_entry_name(entry: list[str]) -> str:
    """Return the lowercased key name from the first line of a dict entry."""
    m = re.match(r"^\s*([\w][\w-]*)\s*:", entry[0])
    return m.group(1).lower() if m else ""


def _split_dict_entries(block: list[str], key_indent: int) -> list[list[str]]:
    """Split a dict block into per-key entry groups at key_indent."""
    entries: list[list[str]] = []
    current: list[str] = []
    for line in block:
        raw = line.rstrip("\n")
        if not raw:
            if current:
                current.append(line)
            continue
        indent = len(raw) - len(raw.lstrip())
        stripped = raw.lstrip()
        if indent == key_indent and re.match(r"[\w][\w-]*\s*:", stripped):
            if current:
                entries.append(current)
            current = [line]
        else:
            current.append(line)
    if current:
        entries.append(current)
    return entries


def _block_is_dict(block: list[str], expected_indent: int) -> bool:
    """Return True if the first content line at expected_indent is a dict key."""
    for line in block:
        raw = line.rstrip("\n")
        if not raw or raw.strip().startswith("#"):
            continue
        indent = len(raw) - len(raw.lstrip())
        if indent == expected_indent:
            stripped = raw.lstrip()
            if stripped.startswith("- "):
                return False
            return bool(re.match(r"[\w][\w-]*\s*:", stripped))
    return False


def _process_dict_body(
    block: list[str],
    key_indent: int,
    sorted_keys_out: list[str],
) -> list[str]:
    """Sort dict keys in block at key_indent; recurse into nested structures."""
    entries = _split_dict_entries(block, key_indent)
    processed: list[list[str]] = []

    for entry in entries:
        key_name = _dict_entry_name(entry)
        first_line = entry[0]
        children = entry[1:]

        if not children:
            processed.append(entry)
            continue

        child_indent = key_indent + 2

        if key_name in SORTABLE_KEYS:
            sorted_children = _sort_block(children)
            if sorted_children != children:
                sorted_keys_out.append(key_name)
            processed.append([first_line, *sorted_children])
        elif (
            _block_is_dict(children, child_indent)
            and key_name not in PRESERVE_DICT_ORDER
        ):
            sorted_children = _process_dict_body(
                children, child_indent, sorted_keys_out
            )
            processed.append([first_line, *sorted_children])
        else:
            processed.append(entry)

    sorted_entries = sorted(processed, key=_dict_entry_name)
    if sorted_entries != processed:
        sorted_keys_out.append("dict")

    return [line for entry in sorted_entries for line in entry]


def _collect_list_block(
    lines: list[str], i: int, min_indent: int
) -> tuple[list[str], int]:
    """Collect list block lines stopping at blank lines or dedent."""
    block: list[str] = []
    while i < len(lines):
        cur = lines[i]
        raw = cur.rstrip("\n")
        if not raw:
            break
        if len(raw) - len(raw.lstrip()) < min_indent:
            break
        block.append(cur)
        i += 1
    return block, i


def _collect_dict_block(
    lines: list[str], i: int, min_indent: int
) -> tuple[list[str], list[str], int]:
    """Collect dict block lines stopping only at non-blank dedented lines.

    Returns (body_lines, trailing_blank_lines, next_i).
    Blank lines inside block scalars are included in the body; trailing blank
    lines (between this block and the next sibling) are returned separately.
    """
    block: list[str] = []
    while i < len(lines):
        cur = lines[i]
        raw = cur.rstrip("\n")
        if raw and len(raw) - len(raw.lstrip()) < min_indent:
            break
        block.append(cur)
        i += 1
    # Separate trailing blank lines so they're emitted after the sorted body.
    trailing: list[str] = []
    while block and not block[-1].rstrip("\n"):
        trailing.insert(0, block.pop())
    return block, trailing, i


def process_content(content: str) -> tuple[str, list[str]]:
    """Return (new_content, sorted_key_names).

    Top-level package entries are collected and sorted by name the same way
    _process_dict_body sorts nested dict keys; any content before the first
    top-level key (e.g. a `---` document start marker) is preserved verbatim
    and excluded from sorting.
    """
    lines = content.splitlines(keepends=True)
    prefix: list[str] = []
    top_entries: list[tuple[str, list[str]]] = []
    sorted_keys: list[str] = []
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^( *)([\w][\w-]*):\s*\n$", line)
        if m:
            key = m.group(2)
            child_indent = len(m.group(1)) + 2
            entry_lines: list[str] = [line]
            i += 1

            if key in SORTABLE_KEYS:
                block, i = _collect_list_block(lines, i, child_indent)
                sorted_block = _sort_block(block)
                if sorted_block != block:
                    sorted_keys.append(key)
                entry_lines.extend(sorted_block)
            else:
                block, trailing, i = _collect_dict_block(lines, i, child_indent)
                if (
                    block
                    and _block_is_dict(block, child_indent)
                    and key not in PRESERVE_DICT_ORDER
                ):
                    sorted_block = _process_dict_body(block, child_indent, sorted_keys)
                    entry_lines.extend(sorted_block)
                else:
                    entry_lines.extend(block)
                entry_lines.extend(trailing)

            top_entries.append((key, entry_lines))
        elif top_entries:
            # A non-key line encountered after the first top-level entry
            # (e.g. a stray blank/comment line between packages) stays
            # attached to the entry just emitted, so it travels with that
            # entry if top-level order changes.
            top_entries[-1][1].append(line)
            i += 1
        else:
            prefix.append(line)
            i += 1

    sorted_top = sorted(top_entries, key=lambda entry: entry[0].lower())
    if [key for key, _ in sorted_top] != [key for key, _ in top_entries]:
        sorted_keys.append("dict")

    result = prefix + [ln for _, entry_lines in sorted_top for ln in entry_lines]
    return "".join(result), sorted_keys


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sort lists and dict keys in packages.yaml."
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="preview changes without writing",
    )
    args = parser.parse_args()

    if not PACKAGES_YAML.exists():
        sys.exit(f"error: {PACKAGES_YAML} not found")

    content = PACKAGES_YAML.read_text()
    new_content, sorted_keys = process_content(content)

    if not sorted_keys:
        print("Nothing to sort — all lists and dicts already sorted.")
        return

    prefix = "[dry-run] " if args.dry_run else ""
    counts = Counter(sorted_keys)
    print(f"{prefix}Sorted {len(sorted_keys)} block(s):")
    for key, count in sorted(counts.items()):
        print(f"  {key} (x{count})")

    if args.dry_run:
        return

    try:
        yaml.safe_load(new_content)
    except yaml.YAMLError as exc:
        sys.exit(f"error: result is not valid YAML: {exc}")

    PACKAGES_YAML.write_text(new_content)
    print(f"\nUpdated {PACKAGES_YAML.relative_to(ROOT)}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nUser Interrupted.", file=sys.stderr)
        sys.exit(130)
