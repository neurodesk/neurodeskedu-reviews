"""Bootstrap review UUIDs for all NeurodeskEDU notebooks/pages.

One-time (or incremental) script that:
  1. Parses _toc.yml to find every content page.
  2. Checks which ones already have nd_review_id.
  3. Generates a UUID for those that don't.
  4. Injects the UUID into the file (.ipynb metadata or .md front-matter).
  5. (Optional) Creates a GitHub issue in the reviews repo for each page.

Usage:
  # Dry run — just list what would happen:
  python tools/bootstrap_reviews.py --books-dir ../neurodeskedu/books --dry-run

  # Write UUIDs into files (no GitHub issues):
  python tools/bootstrap_reviews.py --books-dir ../neurodeskedu/books

  # Write UUIDs AND create GitHub issues:
  python tools/bootstrap_reviews.py --books-dir ../neurodeskedu/books \\
      --create-issues --reviews-repo neurodesk/neurodeskedu-reviews
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import uuid
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import yaml  # PyYAML
except ImportError:
    yaml = None  # type: ignore


# ---------------------------------------------------------------------------
# TOC parsing
# ---------------------------------------------------------------------------

def _parse_toc_files(toc_path: Path) -> List[str]:
    """Return all 'file:' entries from _toc.yml (relative, no extension)."""
    if yaml is None:
        # Fallback: regex extraction if PyYAML isn't installed.
        text = toc_path.read_text(encoding="utf-8")
        return re.findall(r"^\s*-?\s*file:\s*(.+)$", text, re.MULTILINE)
    with toc_path.open("r", encoding="utf-8") as f:
        toc = yaml.safe_load(f)
    files: List[str] = []
    _walk_toc(toc, files)
    return files


def _walk_toc(node: Any, acc: List[str]) -> None:
    if isinstance(node, dict):
        if "file" in node:
            acc.append(str(node["file"]))
        for v in node.values():
            _walk_toc(v, acc)
    elif isinstance(node, list):
        for item in node:
            _walk_toc(item, acc)


# ---------------------------------------------------------------------------
# File-type detection & UUID read/write
# ---------------------------------------------------------------------------

def _resolve_file(books_dir: Path, rel: str) -> Tuple[Optional[Path], str]:
    """Given a TOC entry (no extension), resolve to the actual file.
    Returns (path, filetype) where filetype is 'ipynb', 'md', or 'unknown'.
    """
    for ext, ftype in [(".ipynb", "ipynb"), (".md", "md")]:
        p = books_dir / (rel + ext)
        if p.is_file():
            return p, ftype
    return None, "unknown"


def _read_review_id_ipynb(path: Path) -> Optional[str]:
    with path.open("r", encoding="utf-8") as f:
        nb = json.load(f)
    return nb.get("metadata", {}).get("nd_review_id") or None


def _write_review_id_ipynb(path: Path, review_id: str) -> None:
    with path.open("r", encoding="utf-8") as f:
        nb = json.load(f)
    nb.setdefault("metadata", {})["nd_review_id"] = review_id
    with path.open("w", encoding="utf-8") as f:
        json.dump(nb, f, indent=1, ensure_ascii=False)
        f.write("\n")


def _read_review_id_md(path: Path) -> Optional[str]:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^---\s*\n(.*?)\n---", text, re.DOTALL)
    if not m:
        return None
    fm = m.group(1)
    rid = re.search(r"^nd_review_id:\s*[\"']?([^\s\"']+)", fm, re.MULTILINE)
    return rid.group(1) if rid else None


def _write_review_id_md(path: Path, review_id: str) -> None:
    text = path.read_text(encoding="utf-8")
    m = re.match(r"^(---\s*\n)(.*?)(\n---)", text, re.DOTALL)
    if m:
        front = m.group(2)
        # Insert nd_review_id after the first line of front-matter
        lines = front.split("\n")
        # Add after the first key-value line
        insert_idx = 1  # after title usually
        for i, line in enumerate(lines):
            if line.strip() and ":" in line and not line.strip().startswith("#"):
                insert_idx = i + 1
                break
        lines.insert(insert_idx, f'nd_review_id: "{review_id}"')
        new_fm = "\n".join(lines)
        text = m.group(1) + new_fm + m.group(3) + text[m.end():]
    else:
        # No front-matter — add one
        text = f'---\nnd_review_id: "{review_id}"\n---\n{text}'
    path.write_text(text, encoding="utf-8")


# ---------------------------------------------------------------------------
# GitHub issue creation
# ---------------------------------------------------------------------------

def _create_github_issue(
    reviews_repo: str,
    token: str,
    title: str,
    body: str,
    labels: List[str],
) -> Dict[str, Any]:
    url = f"https://api.github.com/repos/{reviews_repo}/issues"
    payload = json.dumps({
        "title": title,
        "body": body,
        "labels": labels,
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, method="POST")
    req.add_header("Accept", "application/vnd.github+json")
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/json")
    req.add_header("User-Agent", "neurodeskedu-bootstrap")
    with urllib.request.urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def _make_issue_body(review_id: str, source_path: str) -> str:
    return (
        f"<!-- nd-review\n"
        f"review_id: {review_id}\n"
        f"source_path: {source_path}\n"
        f"-->\n\n"
        f"**Source:** `{source_path}`\n\n"
        f"---\n"
        f"_This issue was auto-generated by the bootstrap script._\n"
    )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main(argv: List[str]) -> int:
    parser = argparse.ArgumentParser(description="Bootstrap review UUIDs for NeurodeskEDU pages.")
    parser.add_argument("--books-dir", required=True,
                        help="Path to the neurodeskedu books/ directory.")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print what would happen without writing anything.")
    parser.add_argument("--create-issues", action="store_true",
                        help="Also create GitHub issues in the reviews repo.")
    parser.add_argument("--reviews-repo",
                        default=os.environ.get("ND_REVIEWS_REPO", "neurodesk/neurodeskedu-reviews"),
                        help="GitHub repo for review issues.")
    parser.add_argument("--skip-intro", action="store_true", default=True,
                        help="Skip intro.md pages (default: True).")
    parser.add_argument("--skip-contribute", action="store_true", default=True,
                        help="Skip contribute/ pages (default: True).")
    args = parser.parse_args(argv)

    books_dir = Path(args.books_dir)
    toc_path = books_dir / "_toc.yml"
    if not toc_path.is_file():
        print(f"ERROR: _toc.yml not found at {toc_path}", file=sys.stderr)
        return 1

    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if args.create_issues and not token:
        print("ERROR: --create-issues requires GITHUB_TOKEN env var.", file=sys.stderr)
        return 1

    toc_files = _parse_toc_files(toc_path)
    print(f"Found {len(toc_files)} entries in _toc.yml")

    results = {"skipped": 0, "already_has_id": 0, "would_create": 0, "created": 0, "errors": 0}

    for rel in toc_files:
        # Filters
        basename = rel.rsplit("/", 1)[-1] if "/" in rel else rel
        if args.skip_intro and basename == "intro":
            results["skipped"] += 1
            continue
        if args.skip_contribute and rel.startswith("contribute/"):
            results["skipped"] += 1
            continue

        path, ftype = _resolve_file(books_dir, rel)
        if path is None:
            print(f"  WARN: file not found for TOC entry '{rel}'")
            results["errors"] += 1
            continue

        # Check existing review_id
        existing_id = None
        if ftype == "ipynb":
            existing_id = _read_review_id_ipynb(path)
        elif ftype == "md":
            existing_id = _read_review_id_md(path)

        source_path = str(path.relative_to(books_dir)).replace("\\", "/")

        if existing_id:
            print(f"  SKIP {source_path} (already has review_id: {existing_id})")
            results["already_has_id"] += 1
            continue

        new_id = str(uuid.uuid4())

        if args.dry_run:
            print(f"  WOULD assign {source_path} → {new_id}")
            results["would_create"] += 1
            continue

        # Write UUID to file
        try:
            if ftype == "ipynb":
                _write_review_id_ipynb(path, new_id)
            elif ftype == "md":
                _write_review_id_md(path, new_id)
            print(f"  SET  {source_path} → {new_id}")
            results["created"] += 1
        except Exception as e:
            print(f"  ERROR writing {source_path}: {e}", file=sys.stderr)
            results["errors"] += 1
            continue

        # Create GitHub issue
        if args.create_issues and token:
            try:
                title = f"Review: {source_path}"
                body = _make_issue_body(new_id, source_path)
                issue = _create_github_issue(
                    args.reviews_repo, token, title, body, labels=["review:queued"]
                )
                print(f"        → Issue #{issue['number']}: {issue['html_url']}")
            except Exception as e:
                print(f"        → ERROR creating issue: {e}", file=sys.stderr)
                results["errors"] += 1

    print(f"\nDone: {results}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
