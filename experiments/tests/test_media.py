import json
import subprocess
from pathlib import Path

import numpy as np
import pytest

import media


@pytest.fixture
def run(monkeypatch):
    """Replaces subprocess.run: records each command and returns the queued stdout."""
    calls, outputs = [], []

    def fake(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return subprocess.CompletedProcess(cmd, 0, stdout=outputs.pop(0))

    monkeypatch.setattr(media.subprocess, "run", fake)
    return calls, outputs


def test_probe(run):
    calls, outputs = run
    outputs.append(json.dumps({
        "streams": [{"codec_type": "audio"},
                    {"codec_type": "video", "r_frame_rate": "30000/1001", "width": 640, "height": 360}],
        "format": {"duration": "123.45"}}))
    assert media.probe(Path("v.mp4")) == {"fps": pytest.approx(29.97, abs=1e-3), "width": 640,
                                          "height": 360, "duration": 123.45}
    assert calls[0][0][0] == "ffprobe" and calls[0][0][-1] == "v.mp4" and calls[0][1]["check"]


def test_frames_rgb_drops_partial_frame(run):
    calls, outputs = run
    w, h = 4, 2
    outputs.append(bytes(range(3 * w * h * 3)) + b"\0\0")  # 3 frames and a partial one
    f = media.frames(Path("v.mp4"), (w, h), fps=2)
    assert f.shape == (3, h, w, 3) and f.dtype == np.uint8 and f[0, 0, 1, 0] == 3
    cmd = calls[0][0]
    assert cmd[cmd.index("-vf") + 1] == "fps=2,scale=4:2:flags=area"
    assert cmd[cmd.index("-pix_fmt") + 1] == "rgb24"


def test_frames_gray(run):
    calls, outputs = run
    outputs.append(bytes(2 * 4 * 2))
    f = media.frames(Path("v.mp4"), (4, 2), gray=True)
    assert f.shape == (2, 2, 4)
    cmd = calls[0][0]
    assert cmd[cmd.index("-vf") + 1] == "scale=4:2:flags=area" and cmd[cmd.index("-pix_fmt") + 1] == "gray"


def test_audio(run):
    calls, outputs = run
    outputs.append(np.array([0.5, -0.25], np.float32).tobytes())
    y = media.audio(Path("v.mp4"), sr=16000)
    assert y.tolist() == [0.5, -0.25] and y.flags.writeable
    cmd = calls[0][0]
    assert cmd[cmd.index("-ar") + 1] == "16000" and cmd[cmd.index("-ac") + 1] == "1"
