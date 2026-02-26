#!/usr/bin/env python3
"""Build script: compile Typst notes to HTML and generate the site in dist/."""

import json
import os
import re
import shutil
import subprocess
import time
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NOTES_DIR = ROOT / "notes"
SITE_DIR = ROOT / "site"
DIST_DIR = ROOT / "dist"


class TextExtractor(HTMLParser):
    """Extract plain text from HTML."""

    def __init__(self):
        super().__init__()
        self.parts = []
        self._skip = False

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)

    def get_text(self):
        return " ".join(self.parts)


def get_git_timestamp(folder_path: str) -> int | None:
    """Get unix timestamp of last commit touching the given path."""
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--pretty=format:%ct", "--", folder_path],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        ts = result.stdout.strip()
        if ts:
            return int(ts)
    except Exception:
        pass
    return None


def extract_preview(html: str, max_len: int = 200) -> str:
    """Extract first max_len characters of plain text from HTML."""
    extractor = TextExtractor()
    extractor.feed(html)
    text = extractor.get_text().strip()
    text = re.sub(r"\s+", " ", text)
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0] + "..."
    return text


def inject_into_html(html: str, title: str) -> str:
    """Inject stylesheet link and nav header into Typst HTML output."""
    nav = (
        '<nav class="note-nav"><a href="../../">&larr; Back to notes</a></nav>\n'
    )
    css_link = '<link rel="stylesheet" href="../../style.css">\n'

    # Inject CSS into <head>
    if "<head>" in html:
        html = html.replace("<head>", "<head>\n" + css_link, 1)
    elif "<html>" in html:
        html = html.replace("<html>", "<html>\n<head>\n" + css_link + "</head>", 1)

    # Inject nav after <body>
    if "<body>" in html:
        html = html.replace("<body>", "<body>\n" + nav, 1)

    return html


def build():
    # Clean dist
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir()

    # Read note registry
    registry = json.loads((NOTES_DIR / "notes.json").read_text())
    notes_data = []

    for entry in registry:
        title = entry["title"]
        folder = entry["folder"]
        labels = entry.get("labels", [])
        src_folder = NOTES_DIR / folder
        dst_folder = DIST_DIR / "notes" / folder

        if not src_folder.exists():
            print(f"WARNING: folder not found: {src_folder}, skipping")
            continue

        # Copy entire note folder to dist (preserves images, etc.)
        shutil.copytree(src_folder, dst_folder)

        # Compile Typst to HTML in-place
        typ_file = dst_folder / "main.typ"
        html_file = dst_folder / "index.html"

        result = subprocess.run(
            [
                "typst",
                "compile",
                "--format",
                "html",
                "--features",
                "html",
                str(typ_file),
                str(html_file),
            ],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        if result.returncode != 0:
            print(f"ERROR compiling {typ_file}:")
            print(result.stderr)
            continue

        # Read compiled HTML
        html = html_file.read_text()

        # Extract preview before injection
        preview = extract_preview(html)

        # Post-process: inject CSS + nav
        html = inject_into_html(html, title)
        html_file.write_text(html)

        # Clean up .typ source files from dist
        for typ in dst_folder.glob("*.typ"):
            typ.unlink()

        # Get timestamp
        timestamp = get_git_timestamp(f"notes/{folder}/")
        if timestamp is None:
            timestamp = int(time.time())

        notes_data.append(
            {
                "title": title,
                "folder": folder,
                "labels": labels,
                "timestamp": timestamp,
                "preview": preview,
            }
        )

    # Sort by timestamp descending
    notes_data.sort(key=lambda n: n["timestamp"], reverse=True)

    # Write notes-data.json
    (DIST_DIR / "notes-data.json").write_text(
        json.dumps(notes_data, indent=2) + "\n"
    )

    # Copy site files
    for name in ["index.html", "style.css", "script.js"]:
        shutil.copy2(SITE_DIR / name, DIST_DIR / name)

    print(f"Built {len(notes_data)} note(s) into {DIST_DIR}/")


if __name__ == "__main__":
    build()
