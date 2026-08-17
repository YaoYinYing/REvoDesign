#!/usr/bin/env python3
"""Resolve task-type citations: fetch BibTeX for every declared citation_dois.

Each task type declares an ordered map ``citation_dois: {1: <doi>, 2: <doi>}``
(position -> DOI; projects with multiple papers list them all). This tool
fetches the BibTeX for every DOI via DOI content negotiation
(https://doi.org/<doi> with Accept: application/x-bibtex, Crossref-backed)
and writes the checked-in ``citation_bibtex: |`` block into
server/config/task_types.yaml — BibTeX is never hand-guessed, and DOIs are
validated against Crossref before entering the registry.

Usage:
  python3 server/tools/resolve_citations.py                 # resolve all declared DOIs
  python3 server/tools/resolve_citations.py --check         # verify no resolution is missing
  python3 server/tools/resolve_citations.py --search TITLE  # Crossref search for review
"""

from __future__ import annotations

import json
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REGISTRY = Path(__file__).resolve().parents[1] / "config" / "task_types.yaml"
DOI_RE = re.compile(r"10\.\d{4,9}/[^\s\"]+")
ENTRY_RE = re.compile(r"\{num: (\d+), doi: \"([^\"]+)\", title: \"([^\"]+)\"\}")
# One citation_dois list plus an optional following citation_bibtex block,
# inside one task-type entry.
BLOCK_RE = re.compile(
    r"(?m)^(    citation_dois:\n(?:      - \{num: \d+, doi: \"[^\"]+\", title: \"[^\"]+\"\}\n)+)"
    r"(    citation_bibtex: \|\n(?:      .*\n)*)?"
)


def fetch_bibtex(doi: str) -> str:
    request = urllib.request.Request(
        f"https://doi.org/{urllib.parse.quote(doi, safe='')}",
        headers={"Accept": "application/x-bibtex"},
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        if not response.headers.get_content_type().startswith("application/x-bibtex"):
            raise RuntimeError(f"doi.org did not return BibTeX for {doi}")
        return response.read().decode("utf-8").strip()


def _normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().lower()


def _bibtex_title(bibtex: str) -> str:
    match = re.search(r"title=\{([^}]*)\}", bibtex)
    return _normalize(match.group(1)) if match else ""


def search_doi(title: str) -> list[tuple[str, str]]:
    """Crossref bibliographic search — return (DOI, title) hits for review.

    Exact-title acceptance only: the caller confirms the hit before a DOI
    ever enters the registry (EndnoteTweak's DOI-first discipline).
    """
    url = "https://api.crossref.org/works?" + urllib.parse.urlencode(
        {"query.bibliographic": title, "rows": "5"}
    )
    with urllib.request.urlopen(url, timeout=30) as response:
        payload = json.loads(response.read().decode("utf-8"))
    hits = []
    for item in payload.get("message", {}).get("items", []):
        item_title = (item.get("title") or [""])[0].strip().lower()
        hits.append((item.get("DOI", ""), item_title))
    return hits


def resolve_block(block: str, existing: str | None) -> str | None:
    entries = ENTRY_RE.findall(block)
    if not entries:
        return None
    resolved = []
    for num, doi, title in entries:
        bibtex = fetch_bibtex(doi)
        if not bibtex:
            raise RuntimeError(f"empty BibTeX for {doi}")
        fetched_title = _bibtex_title(bibtex)
        if fetched_title and _normalize(title) not in fetched_title:
            # Human check: the fetched record disagrees with the declared
            # title — do not write it into the registry.
            raise RuntimeError(
                f"title mismatch for {doi}: declared {title!r} vs fetched {fetched_title!r}"
            )
        resolved.append(bibtex)
    merged = "\n\n".join(resolved)
    if existing and merged in existing:
        return None
    indented = "".join("      " + line + "\n" for line in merged.splitlines())
    return block + "    citation_bibtex: |\n" + indented


def main() -> int:
    if "--search" in sys.argv:
        title = sys.argv[sys.argv.index("--search") + 1]
        for doi, hit_title in search_doi(title):
            print(f"{doi}\t{hit_title}")
        return 0
    text = REGISTRY.read_text(encoding="utf-8")
    failures = 0
    changed = 0
    for block, existing in BLOCK_RE.findall(text):
        try:
            replacement = resolve_block(block, existing)
        except (RuntimeError, OSError, urllib.error.URLError) as exc:
            print(f"FAIL {block.splitlines()[0].strip()}: {exc}", file=sys.stderr)
            failures += 1
            continue
        if replacement is None:
            continue
        text = text.replace(block + (existing or ""), replacement, 1)
        changed += 1
        print(f"resolved {len(DOI_RE.findall(block))} DOI(s) for {block.splitlines()[0].strip()}")
    if failures:
        return 1
    if "--check" in sys.argv:
        if changed:
            print("resolutions are stale — rerun without --check", file=sys.stderr)
            return 1
        return 0
    if changed:
        REGISTRY.write_text(text, encoding="utf-8")
    print("registry updated" if changed else "nothing to resolve")
    return 0


if __name__ == "__main__":
    sys.exit(main())
