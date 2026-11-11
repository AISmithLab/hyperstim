"""Build the pair report page: report.html with results/<name>.json inlined.

    uv run python 001-variant-pairs/build_report.py seed-pair

Writes cache/report/<name>/index.html, plus a.mp4 and b.mp4 (the two downloads, for the
synced viewer), next to the frame sprites score_pair.py wrote there. Stills and videos come
from the downloads, so the built page stays out of git; publish it from that folder.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent


def main() -> None:
    name = sys.argv[1]
    data = json.loads((HERE / "results" / f"{name}.json").read_text())
    for v in data["videos"].values():  # the page shows descriptions' shared lines, not whole texts
        v.pop("description", None)
    page = (HERE / "report.html").read_text()
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    out = HERE.parent / "cache" / "report" / name / "index.html"
    out.write_text(page.replace("__DATA__", blob))
    # The viewer plays the downloads themselves (360p): a.mp4 and b.mp4 next to the page.
    for key in ("a", "b"):
        src = HERE.parent / "cache" / "video" / f"{data['pair'][key]}.mp4"
        shutil.copyfile(src, out.parent / f"{key}.mp4")
    print(out, f"{out.stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
