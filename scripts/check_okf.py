#!/usr/bin/env python3
"""
Check an OKF (Open Knowledge Format) knowledge bundle for conformance.

OKF spec: https://github.com/GoogleCloudPlatform/knowledge-catalog/blob/main/okf/SPEC.md

Verifies:
  - every non-reserved .md file has a parseable YAML frontmatter block with a non-empty `type`
  - index.md files carry no frontmatter, except the bundle-root index.md (which declares `okf_version`)
  - log.md carries no frontmatter
  - markdown links to local .md files (bundle-relative "/..." or relative "./...") resolve to real files

Exits non-zero if any conformance error or broken local link is found.

Usage:
    scripts/check_okf.py [BUNDLE_DIR]   # default: docs
"""

import argparse
import collections
import os
import re
import sys

# Matches markdown links ending in .md, with an optional #anchor (external http(s)/mailto links are skipped below)
LINK_RE = re.compile(r"\]\((?P<target>[^)\s#]+\.md)(?:#[^)]*)?\)")
TYPE_RE = re.compile(r"^type:\s*(?P<type>\S.*)$", re.MULTILINE)


def frontmatter(text):
    """Return the YAML frontmatter block (without the --- fences), or None if absent."""
    if not text.startswith("---\n"):
        return None

    end = text.find("\n---", 4)
    if end == -1:
        return None

    return text[4:end]


def check_bundle(root):
    """Yield human-readable problem strings for the OKF bundle rooted at `root`."""
    md_files = []
    for dirpath, _, filenames in os.walk(root):
        for name in filenames:
            if name.endswith(".md"):
                md_files.append(os.path.join(dirpath, name))

    md_files.sort()
    present = {os.path.relpath(p, root).replace(os.sep, "/") for p in md_files}
    types = collections.Counter()
    problems = []

    for path in md_files:
        rel = os.path.relpath(path, root).replace(os.sep, "/")
        name = os.path.basename(path)
        with open(path, encoding="utf-8") as fh:
            text = fh.read()

        fm = frontmatter(text)
        if name == "index.md":
            if rel == "index.md":  # bundle root: the one index.md allowed to have frontmatter
                if not fm or "okf_version" not in fm:
                    problems.append(f"{rel}: bundle-root index.md must declare okf_version")
            elif fm is not None:
                problems.append(f"{rel}: non-root index.md must not have frontmatter")
        elif name == "log.md":
            if fm is not None:
                problems.append(f"{rel}: log.md must not have frontmatter")
        elif fm is None:
            problems.append(f"{rel}: missing frontmatter")
        else:
            m = TYPE_RE.search(fm)
            if m:
                types[m.group("type").strip()] += 1
            else:
                problems.append(f"{rel}: missing non-empty 'type' field")

        for m in LINK_RE.finditer(text):
            target = m.group("target")
            if target.startswith(("http://", "https://", "mailto:")):
                continue  # external link, not ours to resolve

            if target.startswith("/"):
                resolved = target.lstrip("/")
            else:
                resolved = os.path.normpath(os.path.join(os.path.dirname(rel), target)).replace(os.sep, "/")

            if resolved not in present:
                problems.append(f"{rel}: broken link -> {target}")

    return md_files, types, problems


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("bundle", nargs="?", default="docs", help="Path to the bundle root (default: docs)")
    args = parser.parse_args(argv)

    if not os.path.isdir(args.bundle):
        sys.exit(f"Not a directory: {args.bundle}")

    md_files, types, problems = check_bundle(args.bundle)

    print(f"Bundle: {args.bundle}")
    print(f"Markdown files: {len(md_files)}")
    if types:
        print("Concept types:")
        for concept_type, count in sorted(types.items()):
            print(f"  {count:2d}  {concept_type}")

    if problems:
        print(f"\n{len(problems)} problem(s):")
        for problem in problems:
            print(f"  ERROR {problem}")
        return 1

    print("\nOK: bundle is OKF-conformant, all local links resolve.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
