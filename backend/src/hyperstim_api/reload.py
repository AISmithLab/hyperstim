"""The current dataset, reloaded in the background when the collector adds to it (plan 013).

Requests read `current` once and use that object throughout, so a reload in between never
mixes two versions in one answer. A reload builds the new dataset off to the side and then
swaps it in.
"""

import json
import logging
import threading
from pathlib import Path

from hyperstim_api.dataset import Dataset, collected_files, load_dataset

log = logging.getLogger(__name__)

Signature = tuple[tuple[str, int, int], ...]


class DatasetStore:
    def __init__(self, dataset_path: Path, collected_dir: Path | None, every_s: float) -> None:
        self._path = dataset_path
        self._dir = collected_dir
        self._every_s = every_s
        self._signature = self._files()
        self.current: Dataset = load_dataset(dataset_path, collected_dir)
        self.channels_checked_at: str | None = self._channels_checked_at()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def _files(self) -> Signature:
        if self._dir is None or not self._dir.is_dir():
            return ()
        out = []
        for path in [*collected_files(self._dir), self._dir / "meta.json"]:
            try:
                st = path.stat()
            except OSError:
                continue
            out.append((path.name, st.st_mtime_ns, st.st_size))
        return tuple(out)

    def _channels_checked_at(self) -> str | None:
        """When the collector last ran all of discovery's searches."""
        if self._dir is None:
            return None
        try:
            meta = json.loads((self._dir / "meta.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        value = meta.get("channelsCheckedAt")
        return value if isinstance(value, str) else None

    def reload_if_changed(self) -> bool:
        """Reload if the collector's files changed; True if it did."""
        signature = self._files()
        if signature == self._signature:
            return False
        try:
            dataset = load_dataset(self._path, self._dir)
        except (OSError, ValueError, KeyError) as exc:  # e.g. caught mid-write: next time
            log.error("Couldn't reload the dataset: %s", exc)
            return False
        self.current = dataset
        self.channels_checked_at = self._channels_checked_at()
        self._signature = signature
        return True

    def start(self) -> None:
        if self._dir is None:
            return
        self._thread = threading.Thread(target=self._loop, name="dataset-reload", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=10)

    def _loop(self) -> None:
        while not self._stop.wait(self._every_s):
            try:
                self.reload_if_changed()
            except Exception:
                log.exception("Dataset reload failed")
