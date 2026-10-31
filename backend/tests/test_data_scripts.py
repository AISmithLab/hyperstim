"""The repo's data scripts (plan 013): the daily commit (scripts/commit-data.sh), which also
draws the README's growth chart, and the dataset's size in the release notes
(scripts/release-notes.sh), both read from the collector's CHANGELOG.tsv."""

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
COMMIT_DATA = ROOT / "scripts" / "commit-data.sh"
RELEASE_NOTES = ROOT / "scripts" / "release-notes.sh"

COLUMNS = ["date", "videos", "channels", "ch_1", "ch_2", "ch_3", "ch_4", "ch_5plus", "ch_ready",
           "ch_out", "added_v", "removed_v", "new_ch", "note"]  # fmt: skip
HEADER = "\t".join(COLUMNS) + "\n"


def line(day: str, videos: int, channels: int, added: int, removed: int, new: int) -> str:
    """A changelog row; the per-level counts are made up (nothing here reads them)."""
    return "\t".join(
        [day, str(videos), str(channels), "40", "20", "10", "5", "500", "", "", str(added),
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


def test_the_daily_commit_carries_the_chart(tmp_path: Path, clone: Path) -> None:
    subprocess.run([str(COMMIT_DATA), str(clone), str(collected(tmp_path))], check=True)
    files = git(clone, "show", "--name-only", "--format=", "HEAD").split()
    assert "backend/data/collected/growth.svg" in files
    assert "backend/data/collected/growth-dark.svg" in files
    assert "16,725 videos" in git(clone, "show", "HEAD:backend/data/collected/growth.svg")


def test_the_data_goes_in_when_the_chart_fails(tmp_path: Path, clone: Path) -> None:
    # A release without the chart's Python: the script copied alone.
    lone = tmp_path / "release" / "scripts" / "commit-data.sh"
    lone.parent.mkdir(parents=True)
    shutil.copy2(COMMIT_DATA, lone)
    result = subprocess.run(
        [str(lone), str(clone), str(collected(tmp_path))], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert "couldn't draw the growth chart" in result.stderr
    files = git(clone, "show", "--name-only", "--format=", "HEAD").split()
    assert "backend/data/collected/CHANGELOG.tsv" in files
    assert "backend/data/collected/growth.svg" not in files


def commit(clone: Path, source: Path) -> str:
    """Runs the daily commit; returns the newest commit's subject."""
    subprocess.run([str(COMMIT_DATA), str(clone), str(source)], check=True)
    return git(clone, "log", "-1", "--format=%s").strip()


def test_the_commit_message_is_the_new_days_rows(tmp_path: Path, clone: Path) -> None:
    source = collected(tmp_path)
    assert commit(clone, source) == (
        "data: Add 423 videos and 46 channels, remove 73 (2026-10-26 to 2026-10-29)"
    )
    (source / "CHANGELOG.tsv").write_text(
        HEADER + line("2026-10-30", 16727, 591, 2, 0, 3) + CHANGELOG.removeprefix(HEADER)
    )
    (source / "2026.tsv").write_text("video_id\nabc\ndef\nghi\nnext-day\n")
    assert commit(clone, source) == "data: Add 2 videos and 3 channels (2026-10-30)"


def test_nothing_is_committed_without_a_new_day(tmp_path: Path, clone: Path) -> None:
    source = collected(tmp_path)
    commit(clone, source)
    head = git(clone, "rev-parse", "HEAD")
    # The same days, with the files changed (videos added after midnight): no commit.
    (source / "2026.tsv").write_text("video_id\nabc\ndef\n")
    commit(clone, source)
    assert git(clone, "rev-parse", "HEAD") == head


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
