"""Build the pair report page: report.html with results/<name>.json inlined.

    uv run python 001-variant-pairs/build_report.py seed-pair [--data PATH] [--out DIR]

Writes cache/report/<name>/index.html, plus a.mp4 and b.mp4 (the two downloads, for the
synced viewer), next to the frame sprites score_pair.py wrote there. Stills and videos come
from the downloads, so the built page stays out of git; publish it from that folder.
`--data` and `--out` build from another results file into another folder (e.g. to check the
page on test data); a download that isn't in the cache is then left out.

The same page shell serves the search site (build_search_site.py): there `write_pair` puts
the pair's data in data.json and its stills next to it, and the page reads its videos from the
site's videos.json.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

HERE = Path(__file__).resolve().parent
# A page served on its own (not wrapped at publish time) needs its own document head.
DOC_HEAD = ('<!doctype html>\n<html lang="en">\n<meta charset="utf-8">\n'
            '<meta name="viewport" content="width=device-width, initial-scale=1">\n')


def public_data(path: Path) -> dict:
    """A results file as the page shows it: descriptions left out (only shared lines are shown)."""
    data = json.loads(path.read_text())
    for v in data["videos"].values():
        v.pop("description", None)
    return data


def shell(data: dict | None = None, *, src: str = "", videos: str = "", name: str = "") -> str:
    """The report page: data inline, or (data None) fetched from `src`, with the video URLs read
    from `videos` (a JSON map {name: {"a": url, "b": url}}) under `name`."""
    page = (HERE / "report.html").read_text()
    blob = "null" if data is None else json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    page = (page.replace("__SRC__", src).replace("__VIDEOS__", videos).replace("__NAME__", name)
            .replace("__DATA__", blob.replace("</", "<\\/")))
    return DOC_HEAD + page if data is None else page


def pack(images: list, out: Path, quality: int) -> tuple[list[tuple[int, int]], tuple[int, int]]:
    """Stack RGB/BGR images top to bottom, left-aligned, into one JPEG; returns each one's (x, y)
    and the sheet's (W, H)."""
    import cv2
    import numpy as np

    W, H = max(im.shape[1] for im in images), sum(im.shape[0] for im in images)
    sheet = np.full((H, W, 3), 255, np.uint8)
    pos, y = [], 0
    for im in images:
        sheet[y:y + im.shape[0], :im.shape[1]] = im
        pos.append((0, y))
        y += im.shape[0]
    cv2.imwrite(str(out), sheet, [cv2.IMWRITE_JPEG_QUALITY, quality, cv2.IMWRITE_JPEG_OPTIMIZE, 1])
    return pos, (W, H)


# Site mode: the sprites go into two sheets, so a pair folder holds at most four files.
STILLS = ("mask", "edges", "sb-a", "sb-b")   # stills.jpg: the change map, outlines and storyboards
FRAMES = ("a", "b")                          # frames.jpg: A and B stills, only for pairs without video


def write_pair(name: str, data: dict, out_dir: Path, *, site: bool = False, quality: int = 65,
               scale: float = 1.0, stills_from: Path | None = None, frames: bool = True) -> list[str]:
    """One pair's page into out_dir; returns the files written. Standalone: index.html with the data
    inline. Site: index.html (shell), data.json (thumbnails inlined), stills.jpg and, with
    `frames`, frames.jpg, from the sprites in `stills_from`, recompressed at `quality` and scaled by
    `scale`; each sprite's place in its sheet goes into data.json."""
    out_dir.mkdir(parents=True, exist_ok=True)
    if not site:
        (out_dir / "index.html").write_text(shell(data))
        return ["index.html"]
    import base64

    import cv2

    src = stills_from or out_dir
    data = json.loads(json.dumps(data))
    sprites = data.get("sprites", {})
    data["thumbs"] = {}
    for k in ("a", "b"):
        p = src / f"thumb-{k}.jpg"
        if p.exists():
            ok, buf = cv2.imencode(".jpg", cv2.imread(str(p)), [cv2.IMWRITE_JPEG_QUALITY, 80])
            data["thumbs"][k] = "data:image/jpeg;base64," + base64.b64encode(buf.tobytes()).decode()
    files = ["index.html", "data.json"]
    for sheet, keys in (("stills.jpg", STILLS), ("frames.jpg", FRAMES if frames else ())):
        keys = [k for k in keys if k in sprites and (src / sprites[k]["file"]).exists()]
        if not keys:
            (out_dir / sheet).unlink(missing_ok=True)
            continue
        ims = []
        for k in keys:
            im = cv2.imread(str(src / sprites[k]["file"]))
            if scale != 1:
                im = cv2.resize(im, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
            ims.append(im)
        pos, (W, H) = pack(ims, out_dir / sheet, quality)
        for k, im, (x, y) in zip(keys, ims, pos, strict=True):
            sp = sprites[k]
            sp.update(sheet=sheet, x=x, y=y, W=W, H=H, iw=im.shape[1], ih=im.shape[0],
                      w=im.shape[1] / sp["cols"], h=im.shape[0] / sp["rows"])
        files.append(sheet)
    for k in list(sprites):  # sprites not packed (e.g. A and B with a video) aren't in the site
        if "sheet" not in sprites[k]:
            del sprites[k]
    (out_dir / "index.html").write_text(shell(None, src="data.json", videos="../../videos.json", name=name))
    (out_dir / "data.json").write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    for f in out_dir.iterdir():  # files of an earlier layout (videos copied in by the site builder stay)
        if f.name not in files and f.suffix != ".mp4":
            f.unlink()
    return files


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("name")
    ap.add_argument("--data", type=Path, help="results JSON (default: results/<name>.json)")
    ap.add_argument("--out", type=Path, help="output folder (default: cache/report/<name>)")
    args = ap.parse_args()
    data = public_data(args.data or HERE / "results" / f"{args.name}.json")
    out_dir = args.out or HERE.parent / "cache" / "report" / args.name
    write_pair(args.name, data, out_dir)
    out = out_dir / "index.html"
    # The viewer plays the downloads themselves (360p): a.mp4 and b.mp4 next to the page.
    for key in ("a", "b"):
        src = HERE.parent / "cache" / "video" / f"{data['pair'][key]}.mp4"
        if src.exists() or not args.out:
            shutil.copyfile(src, out_dir / f"{key}.mp4")
    print(out, f"{out.stat().st_size / 1e3:.0f} kB")


if __name__ == "__main__":
    main()
