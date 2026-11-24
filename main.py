#!/usr/bin/env python3
"""The One-Line Exit.

Writes a single one-line resignation letter, exactly one line long, to
/output/entry.txt (or $MAKEFUN_OUTPUT_DIR).

The line is a fixed constant: a deterministic entry, byte-identical on
every run. Python 3 standard library only, no network, no randomness.
"""

import glob
import os
import sys
import tempfile

# The entry: one sentence, one line, 104 characters, no trailing newline.
ENTRY = (
    "I hereby resign as a ventriloquist: my dummy has been promoted twice, "
    "and I have not been promoted once."
)

OUTPUT_NAME = "entry.txt"


def _reject_control_chars(text: str) -> None:
    """Reject C0/C1 control characters (the gate wants plain UTF-8 text)."""
    for ch in text:
        code = ord(ch)
        if code < 0x20 or 0x7F <= code <= 0x9F:
            raise ValueError(f"control character U+{code:04X} in entry")


def _validate(text: str) -> None:
    """Enforce the competition gate: 1-140 chars, not whitespace-only."""
    _reject_control_chars(text)
    if not (1 <= len(text) <= 140):
        raise ValueError(f"entry length {len(text)} outside 1..140")
    if not text.strip():
        raise ValueError("entry is whitespace-only")
    if "\n" in text or "\r" in text:
        raise ValueError("entry must be a single line")
    if text.endswith("\n") or text.endswith("\r"):
        raise ValueError("entry must not end with a newline")


def _output_dir() -> str:
    """$MAKEFUN_OUTPUT_DIR, falling back to /output when unset or empty."""
    out = os.environ.get("MAKEFUN_OUTPUT_DIR") or "/output"
    return out


def _fsync_dir(path: str) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _write_all(fd: int, data: bytes) -> None:
    """Write every byte; os.write may return a short count, so loop."""
    view = memoryview(data)
    while view:
        n = os.write(fd, view)
        if n == 0:
            raise OSError("short write: wrote 0 bytes")
        view = view[n:]


def _clean_stale_tmps(out_dir: str) -> None:
    """Remove temp files left behind by a killed earlier run."""
    for stale in glob.glob(os.path.join(out_dir, ".entry-*.tmp")):
        try:
            os.unlink(stale)
        except OSError:
            pass


def _write_atomic(target: str, data: bytes) -> None:
    """Write data to target via a mkstemp temp file, then rename over it.

    The temp file is created with mkstemp (unique name, O_EXCL), written
    with a _write_all loop, fsync'd, chmod'd 0644, then atomically
    renamed onto the target. The finally clause unlinks the temp file
    whenever it still exists, so a failed or killed run never leaves a
    stale temp behind to poison the next run.
    """
    out_dir = os.path.dirname(target) or "."
    tmp_fd = None
    tmp_path = None
    try:
        tmp_fd, tmp_path = tempfile.mkstemp(
            dir=out_dir, prefix=".entry-", suffix=".tmp"
        )
        _write_all(tmp_fd, data)
        os.fsync(tmp_fd)
        os.close(tmp_fd)
        tmp_fd = None
        os.chmod(tmp_path, 0o644)
        os.replace(tmp_path, target)
        tmp_path = None
    finally:
        if tmp_fd is not None:
            try:
                os.close(tmp_fd)
            except OSError:
                pass
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def _write_entry(target: str, data: bytes) -> None:
    """Write once; on failure, clear stale temps and retry exactly once."""
    try:
        _write_atomic(target, data)
    except OSError:
        _clean_stale_tmps(os.path.dirname(target) or ".")
        _write_atomic(target, data)


def main() -> int:
    _validate(ENTRY)
    data = ENTRY.encode("utf-8")

    out_dir = _output_dir()
    # Never delete the output directory itself: the grader mounts it.
    os.makedirs(out_dir, exist_ok=True)

    target = os.path.join(out_dir, OUTPUT_NAME)
    _write_entry(target, data)
    _fsync_dir(out_dir)

    # Read-back verification: the file must match the constant exactly.
    with open(target, "rb") as fh:
        written = fh.read()
    if written != data:
        raise ValueError("read-back mismatch: entry.txt != ENTRY")
    os.chmod(target, 0o644)
    return 0


if __name__ == "__main__":
    sys.exit(main())
