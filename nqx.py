#!/usr/bin/env python3
import os
from nqx_tui.app import NQX


def main():
    # Default NQDIR to ~/.local/share/nq so jobs are stored in a persistent
    # user-owned directory instead of the current working directory.
    if "NQDIR" not in os.environ:
        nq_dir = os.path.expanduser("~/.local/share/nq")
        os.makedirs(nq_dir, exist_ok=True)
        os.environ["NQDIR"] = nq_dir
    app = NQX()
    app.run()


if __name__ == "__main__":
    main()
