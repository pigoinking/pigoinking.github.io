#!/usr/bin/env python3
"""Build script: compile Typst notes to SVG and generate the site in dist/."""

import json
import re
import shutil
import subprocess
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
NOTES_DIR = ROOT / "notes"
SITE_DIR = ROOT / "site"
DIST_DIR = ROOT / "dist"


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


def extract_preview(typ_path: Path, max_len: int = 200) -> str:
    """Extract first max_len characters of plain text from a .typ file."""
    text = typ_path.read_text()
    text = re.sub(r"^=+\s+.*$", "", text, flags=re.MULTILINE)
    text = re.sub(r"#\w+[^)\n]*\)?", "", text)
    text = re.sub(r"\$[^$]*\$", "", text)
    text = re.sub(r"[*_`]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_len:
        text = text[:max_len].rsplit(" ", 1)[0] + "..."
    return text


def build():
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir()

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

        shutil.copytree(src_folder, dst_folder)

        typ_file = dst_folder / "main.typ"
        preview = extract_preview(typ_file)

        # Create a wrapper that sets page to wide, auto-height, minimal margins
        wrapper_file = dst_folder / "_build.typ"
        wrapper_file.write_text(
            '#set page(width: 700pt, height: auto, margin: (x: 30pt, y: 20pt))\n'
            '#include "main.typ"\n'
        )

        # Compile Typst to SVG (one per page: page-{n}.svg)
        svg_pattern = dst_folder / "page-{n}.svg"
        result = subprocess.run(
            ["typst", "compile", "--format", "svg", str(wrapper_file), str(svg_pattern)],
            capture_output=True,
            text=True,
            cwd=ROOT,
        )
        if result.returncode != 0:
            print(f"ERROR compiling {typ_file}:")
            print(result.stderr)
            continue

        # Collect SVG pages in order
        svg_files = sorted(dst_folder.glob("page-*.svg"),
                           key=lambda p: int(p.stem.split("-")[1]))

        # Inline SVGs into the HTML page
        svg_blocks = []
        for svg_file in svg_files:
            svg_content = svg_file.read_text()
            # Make SVG scale to container width
            # Remove fixed width/height attrs so CSS controls sizing
            svg_content = re.sub(r'\s+width="[^"]*"', '', svg_content, count=1)
            svg_content = re.sub(r'\s+height="[^"]*"', '', svg_content, count=1)
            svg_blocks.append(svg_content)
            svg_file.unlink()

        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{title}</title>
  <style>
    body {{ margin: 0; padding: 0; background: #fdfdfd; }}
    .note-nav {{
      font-family: system-ui, -apple-system, sans-serif;
      font-size: 0.9rem;
      padding: 0.75rem 0 0.5rem;
      /* 30pt margin / 700pt page width */
      margin-left: 4.3%;
    }}
    .note-nav a {{
      color: #2563eb;
      text-decoration: none;
    }}
    .note-nav a:hover {{
      text-decoration: underline;
    }}
    svg {{ display: block; width: 100%; height: auto; }}
  </style>
</head>
<body>
  <nav class="note-nav"><a href="../../">&lt; Back to notes</a></nav>
{"".join(svg_blocks)}
</body>
</html>
"""
        (dst_folder / "index.html").write_text(html)

        # Clean up .typ and build files from dist
        for f in dst_folder.glob("*.typ"):
            f.unlink()

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

    notes_data.sort(key=lambda n: n["timestamp"], reverse=True)

    (DIST_DIR / "notes-data.json").write_text(
        json.dumps(notes_data, indent=2) + "\n"
    )

    for name in ["index.html", "style.css", "script.js"]:
        shutil.copy2(SITE_DIR / name, DIST_DIR / name)

    print(f"Built {len(notes_data)} note(s) into {DIST_DIR}/")


if __name__ == "__main__":
    build()
