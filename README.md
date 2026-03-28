# nqi

**nqi** is interactive 
[nq](https://github.com/leahneukirchen/nq) UI (get it?): a minimal, daemon-free Unix job queue built on `flock(2)`.

Enqueue long-running commands with `nq` and manage them interactively: inspect
logs, reorder the queue, kill or re-enqueue jobs, and clean up finished runs —
all without leaving your terminal.


## Features

- Live job list with status indicators (Running / Queued / Finished)
- Full log viewer with ANSI escape stripping
- Reorder queued jobs with vim-style `k` / `j`
- Kill running jobs (double-press to confirm)
- Re-enqueue any finished or running job with `d`
- Clean all finished job logs with `c` (double-press to confirm)
- Copy a job's full log content to the clipboard with `y`
- Ad-hoc command input with `!`
- Default queue stored in `~/.local/share/nq` — no config needed

## Prerequisites

| Requirement | Notes |
|---|---|
| Linux / macOS / any POSIX.1-2008 system | `flock(2)` required |
| Python ≥ 3.8 | for the TUI |
| `gcc` or `clang` + `make` | to compile `nq` C utilities at install time (falls back to system `nq`) |
| `pipx` or `pip` | for the Python install |

> macOS and BSDs should work but are untested. `flock(2)` must be available.

## Installation

### One-line install

```bash
curl -fsSL https://raw.githubusercontent.com/mamiglia/nqi/master/install.sh | bash
```

This installs the `nqi` Python package via `pipx` (falling back to `pip --user`).
The build automatically compiles and bundles the `nq` C utilities inside the
package.

By default, the installer pins remote installs to the `v0.1.0` git tag for
reproducibility. Override with an explicit ref if needed:

```bash
NQI_REF=v0.1.0 curl -fsSL https://raw.githubusercontent.com/mamiglia/nqi/master/install.sh | bash
```

The installer runs a post-install self-check (`nqi true` + `nqi -w` in a temp
`NQDIR`) and fails fast if no usable bundled/system `nq` binary is available.

### pip / pipx

```bash
# isolated environment (recommended)
pipx install git+https://github.com/mamiglia/nqi.git

# or into user site-packages
pip install --user git+https://github.com/mamiglia/nqi.git
```

`setup.py` automatically initialises the `nq` git submodule (or downloads the
upstream tarball), compiles it, and bundles binaries inside the wheel. If
compilation fails, `nqi` falls back to a system-installed `nq`.

### Manual

```bash
git clone --recurse-submodules https://github.com/mamiglia/nqi.git
cd nqi/nq && make && sudo make install   # installs nq to /usr/local/bin
cd ..
pip install --user .
```

## Usage

```bash
# Enqueue jobs
nqi make all
nqi ./run-benchmark --config fast
nqi sleep 60

# Tail the currently-running job's output
nqi -f

# Open the interactive TUI
nqi
```

`nqi` installs only the `nqi` command.
It forwards to bundled `nq` tools internally:

- `nqi <cmd...>` behaves like `nq <cmd...>`
- `nqi -f` behaves like `nqtail`
- `nqi -t` behaves like `nqterm`

It prefers bundled binaries built during installation and uses
`~/.local/share/nq` as default queue storage when `NQDIR` is not set.

### Keyboard shortcuts

| Key | Action |
|-----|--------|
| `k` / `j` | Move the selected queued job up / down in the queue |
| `K` | Kill the selected job (press twice within 3 s to confirm) |
| `d` | Re-enqueue (restart) the selected job |
| `c` | Clean all finished job log files (press twice to confirm) |
| `y` | Copy the selected job's full log content to clipboard |
| `!` | Open inline command input to enqueue an arbitrary command |
| `Esc` | Return focus to the job list |
| `q` | Quit |

### Multiple queues with NQDIR

By default all job log files live in `~/.local/share/nq`. Set `NQDIR` to use
a different directory:

```bash
NQDIR=/tmp/downloads nq wget https://example.com/big.iso
NQDIR=/tmp/downloads nqi

export NQDIR="$PWD/.nq"
nq make test
nqi
```

`nqi` resolves binaries (`nq`, `nqtail`, `nqterm`) in this order:

1. Bundled binary at `nqi/bin/<name>` (compiled at install time)
2. Local development build at `./nq/<name>`
3. System `PATH`

## Development

```bash
git clone --recurse-submodules https://github.com/mamiglia/nqi.git
cd nqi

# Build the C utilities
cd nq && make && cd ..

# Install in editable mode
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# Run the TUI
python nqi.py

# Run Python tests
python -m unittest discover -s tests -v

# Smoke-test installer/pip Docker paths
./tools/test-install.sh
```

### Project layout

```
nqi/
├── nq/              # git submodule → github.com/leahneukirchen/nq
├── nqi/
│   ├── app.py       # Textual App — layout, bindings, event handling
│   ├── logic.py     # job-file parsing, flock-based status detection
│   ├── widgets.py   # custom Textual widgets
│   ├── styles.css   # Textual CSS
│   └── bin/         # compiled nq binaries bundled at install time
├── setup.py         # custom build that compiles nq during pip install
├── pyproject.toml
└── install.sh       # thin wrapper: pip/pipx install
```

## License

- `nqi` TUI — [MIT](LICENSE)
- `nq` C utilities — Public Domain ([CC0](http://creativecommons.org/publicdomain/zero/1.0/))
