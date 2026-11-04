#!/usr/bin/env python3
"""Read-only conflict discovery. Exit 0: none found, 1: found, 2: incomplete scan."""
import argparse
import json
import os
from pathlib import Path
import re
import sys

CONFLICTS = {"grillme": "grill-me", "specfirst": "spec-first"}
SKIP = {".git", "node_modules", ".venv", "__pycache__", "uninstalled"}


def normalize(value):
    return re.sub(r"[^a-z0-9]", "", value.casefold())


def declared_name(path):
    # Read only frontmatter, never execute or load instructions from other skills.
    with path.open(encoding="utf-8-sig") as stream:
        if stream.readline().strip() != "---":
            return None
        for line in stream:
            if line.strip() in {"---", "..."}:
                break
            match = re.match(r"^name:\s*(.*?)\s*$", line)
            if match:
                value = match.group(1)
                if value.startswith(('"', "'")):
                    quote = value[0]
                    end = value.rfind(quote)
                    return value[1:end] if end > 0 else None
                return value.split(" #", 1)[0].strip()
    return None


def default_roots(project):
    home = Path.home()
    codex = Path(os.environ.get("CODEX_HOME", home / ".codex"))
    yield codex / "skills"
    yield codex / "plugins" / "cache"
    yield home / ".agents" / "skills"
    yield home / ".claude" / "skills"
    yield home / ".claude" / "plugins" / "cache"
    for parent in (project, *project.parents):
        for directory in (".agents", ".codex", ".claude"):
            yield parent / directory / "skills"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, default=Path.cwd())
    parser.add_argument("--root", action="append", type=Path, default=[],
                        help="Additional skill directory; repeat as needed.")
    parser.add_argument("--available-skill", action="append", default=[],
                        help="Name from the session skill catalog, including cloud-only skills.")
    args = parser.parse_args()
    matches, errors, scanned = [], [], []
    seen_files, seen_roots = set(), set()

    def record(name, source):
        canonical = CONFLICTS.get(normalize(name))
        if canonical:
            matches.append({"skill": canonical, "name": name, "source": source})

    for name in args.available_skill:
        # Catalog names may be qualified as plugin-name:skill-name.
        record(name.rsplit(":", 1)[-1], "session-catalog:" + name)

    roots = [(root, False) for root in default_roots(args.project.resolve())]
    roots += [(root, True) for root in args.root]
    for root, explicit in roots:
        root = root.expanduser().resolve()
        if root in seen_roots:
            continue
        seen_roots.add(root)
        try:
            exists = root.stat()
        except FileNotFoundError:
            if explicit:
                errors.append({"path": str(root), "error": "Explicit root does not exist"})
            continue
        except OSError as exc:
            errors.append({"path": str(root), "error": str(exc)})
            continue
        if not root.is_dir():
            errors.append({"path": str(root), "error": "Not a directory"})
            continue
        scanned.append(str(root))

        def walk_error(exc):
            errors.append({"path": str(exc.filename), "error": str(exc)})

        for directory, dirs, files in os.walk(root, followlinks=False, onerror=walk_error):
            dirs[:] = sorted(name for name in dirs if name not in SKIP)
            if "SKILL.md" not in files:
                continue
            path = Path(directory) / "SKILL.md"
            resolved = path.resolve()
            if resolved in seen_files:
                continue
            seen_files.add(resolved)
            try:
                name = declared_name(path)
                # Detect folder aliases too, including folders without valid frontmatter.
                record(name or path.parent.name, str(path))
                if name and normalize(name) != normalize(path.parent.name):
                    record(path.parent.name, str(path))
            except (OSError, UnicodeError) as exc:
                errors.append({"path": str(path), "error": str(exc)})

    matches = [dict(items) for items in sorted({tuple(sorted(m.items())) for m in matches})]
    excluded = sorted({match["skill"] for match in matches})
    result = {
        "scan_complete": not errors,
        "conflicts": matches,
        "workflow_exclusions": excluded,
        "warning": (
            "Conflicting skills found: " + ", ".join(excluded)
            + ". The coordinating agent must disable their use for this workflow "
              "and notify the user before continuing. Global installation is unchanged."
        ) if excluded else None,
        "scanned_roots": scanned,
        "errors": errors,
        "scope": "Local skill directories and explicitly supplied session catalog names only; "
                 "nested directory symlinks are not traversed. Pass their targets with --root. "
                 "This script detects conflicts; agents enforce workflow exclusions.",
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 2 if errors else (1 if excluded else 0)


if __name__ == "__main__":
    sys.exit(main())
