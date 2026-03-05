"""
Custom setuptools build that compiles the nq C utilities and bundles them
inside the nqy wheel (at nqy/bin/).
"""

import os
import sys
import shutil
import subprocess
from pathlib import Path

from setuptools import setup
from setuptools.command.build_py import build_py as _build_py

NQ_BINARIES = ["nq", "nqtail", "nqterm"]
NQ_SRC = Path(__file__).parent / "nq"
BIN_DEST = Path(__file__).parent / "nqy" / "bin"
# Upstream nq repo – used as a fallback when the submodule isn't initialised
# and we're not inside a git working tree (e.g. a pip sdist install).
NQ_UPSTREAM = "https://github.com/leahneukirchen/nq/archive/refs/heads/master.tar.gz"


def _nq_source_populated() -> bool:
    """True when the nq/ submodule has been checked out (nq.c is present)."""
    return (NQ_SRC / "nq.c").exists()


def ensure_nq_submodule():
    """Make sure the nq/ submodule is populated before we try to build it.

    Strategy (in order):
    1. Already present  → nothing to do.
    2. Inside a git repo → ``git submodule update --init``.
    3. Not a git repo   → download the upstream tarball and extract it.
    """
    if _nq_source_populated():
        return

    repo_root = Path(__file__).parent
    git_dir = repo_root / ".git"

    if git_dir.exists():
        print("Initialising nq git submodule...")
        try:
            subprocess.check_call(
                ["git", "-C", str(repo_root), "submodule", "update", "--init", "--", "nq"]
            )
            if _nq_source_populated():
                return
        except (subprocess.CalledProcessError, FileNotFoundError) as exc:
            print(f"Warning: git submodule init failed ({exc}).", file=sys.stderr)

    # Fallback: download a tarball of the upstream nq source.
    import tarfile
    import urllib.request
    import tempfile

    print(f"Downloading nq source from {NQ_UPSTREAM} ...")
    try:
        with tempfile.TemporaryDirectory() as tmp:
            tarball = os.path.join(tmp, "nq.tar.gz")
            urllib.request.urlretrieve(NQ_UPSTREAM, tarball)
            with tarfile.open(tarball) as tf:
                tf.extractall(tmp)
            # The tarball extracts to nq-master/ — move its contents into nq/
            extracted = next(
                d for d in Path(tmp).iterdir()
                if d.is_dir() and d.name != "__MACOSX"
            )
            NQ_SRC.mkdir(exist_ok=True)
            for item in extracted.iterdir():
                dest = NQ_SRC / item.name
                if dest.exists():
                    continue
                shutil.copytree(str(item), str(dest)) if item.is_dir() else shutil.copy2(str(item), str(dest))
        if _nq_source_populated():
            print("nq source downloaded successfully.")
            return
    except Exception as exc:
        print(f"Warning: Could not download nq source ({exc}).", file=sys.stderr)

    print("Warning: nq source unavailable; nqy will fall back to a system-installed nq.",
          file=sys.stderr)


def compile_nq():
    """Ensure nq source is present, then compile it. Returns True on success."""
    ensure_nq_submodule()
    if not _nq_source_populated():
        print("Warning: nq/ source not found; skipping C build.", file=sys.stderr)
        return False
    print("Building nq C utilities...")
    try:
        subprocess.check_call(["make", "-C", str(NQ_SRC)])
        return True
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        print(f"Warning: Could not build nq utilities ({exc}).", file=sys.stderr)
        print("nqy will fall back to a system-installed nq if available.", file=sys.stderr)
        return False


def bundle_binaries():
    """Copy compiled nq binaries into nqy/bin/ so they travel with the wheel."""
    BIN_DEST.mkdir(exist_ok=True)
    for binary in NQ_BINARIES:
        src = NQ_SRC / binary
        if src.exists():
            dst = BIN_DEST / binary
            shutil.copy2(str(src), str(dst))
            dst.chmod(0o755)


class build_py(_build_py):
    """Compile nq and bundle the binaries into the package before assembling the wheel."""

    def run(self):
        if compile_nq():
            bundle_binaries()
        super().run()


setup(
    cmdclass={
        "build_py": build_py,
    },
)
