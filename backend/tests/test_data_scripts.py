"""The repo's data scripts (plan 013): the daily commit (scripts/commit-data.sh) and the
dataset's size in the release notes (scripts/release-notes.sh), both read from the collector's
CHANGELOG.tsv."""

import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMMIT_DATA = ROOT / "scripts" / "commit-data.sh"
RELEASE_NOTES = ROOT / "scripts" / "release-notes.sh"

COLUMNS = ["date", "videos", "channels", "ch_1", "ch_2", "ch_3", "ch_4", "ch_5plus", "ch_ready",
           "added_v", "removed_v", "new_ch", "note"]  # fmt: skip
HEADER = "\t".join(COLUMNS) + "\n"


def line(day: str, videos: int, channels: int, added: int, removed: int, new: int) -> str:
    """A changelog row; the per-level counts are made up (nothing here reads them)."""
    return "\t".join(
        [day, str(videos), str(channels), "40", "20", "10", "5", "500", "", str(added),
         str(removed), str(new), ""]
    ) + "\n"  # fmt: skip


CHANGELOG = HEADER + (  # as the collector writes it: the newest day first
    line("2026-10-29", 16725, 588, 15, 0, 7)
    + line("2026-10-28", 16710, 581, 143, 0, 18)
    + line("2026-10-27", 16567, 563, 137, 0, 18)
    + line("2026-10-26", 16430, 545, 128, 73, 3)
)


def git(cwd: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(cwd), *args], check=True, capture_output=True, text=True
    ).stdout


@pytest.fixture
def clone(tmp_path: Path) -> Path:
    """The bot's clone of a repo whose main has one commit."""
    origin, seed, bot = tmp_path / "origin.git", tmp_path / "seed", tmp_path / "bot"
    subprocess.run(["git", "init", "--quiet", "--bare", "-b", "main", str(origin)], check=True)
    subprocess.run(["git", "clone", "--quiet", str(origin), str(seed)], check=True)
    (seed / "README.md").write_text("repo\n")
    git(seed, "add", "README.md")
    git(seed, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", "init")
    git(seed, "push", "--quiet", "origin", "HEAD:main")
    subprocess.run(["git", "clone", "--quiet", str(origin), str(bot)], check=True)
    return bot


def collected(tmp_path: Path) -> Path:
    source = tmp_path / "collected"
    source.mkdir()
    (source / "CHANGELOG.tsv").write_text(CHANGELOG)
    (source / "2026.tsv").write_text("video_id\nabc\n")
    return source


def test_the_commit_message_counts_new_channels(tmp_path: Path, clone: Path) -> None:
    subprocess.run([str(COMMIT_DATA), str(clone), str(collected(tmp_path))], check=True)
    source = tmp_path / "collected"
    (source / "CHANGELOG.tsv").write_text(
        CHANGELOG.replace("2026-10-29\t16725\t588", "2026-10-30\t16727\t591", 1)
    )
    (source / "2026.tsv").write_text("video_id\nabc\ndef\nghi\n")
    subprocess.run([str(COMMIT_DATA), str(clone), str(source)], check=True)
    assert git(clone, "log", "-1", "--format=%s").startswith("data: Add 2 videos and 3 channels")


def test_the_release_notes_read_the_dataset_size_from_the_latest_day(tmp_path: Path) -> None:
    repo = tmp_path / "repo"
    path = repo / "backend" / "data" / "collected" / "CHANGELOG.tsv"
    path.parent.mkdir(parents=True)
    subprocess.run(["git", "init", "--quiet", "-b", "main", str(repo)], check=True)
    for changelog, subject in ((CHANGELOG, "data: Before"), (CHANGELOG.replace(
        "2026-10-29\t16725\t588", "2026-10-30\t16989\t594"), "data: After")):  # fmt: skip
        path.write_text(changelog)
        git(repo, "add", "-A")
        git(repo, "-c", "user.name=t", "-c", "user.email=t@example.com", "commit", "-qm", subject)
    notes = subprocess.run(
        [str(RELEASE_NOTES), "HEAD~1..HEAD"], cwd=repo, check=True, capture_output=True, text=True
    ).stdout
    assert "Dataset: 16,725 → 16,989 videos, 588 → 594 channels." in notes
