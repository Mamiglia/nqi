# nqi

**nqi** is interactive 
[nq](https://github.com/leahneukirchen/nq) UI (get it?): a minimal, daemon-free Unix job queue built on `flock(2)`.

Enqueue long-running commands with `nq` and manage them interactively: inspect
logs, reorder the queue, kill or re-enqueue jobs, and clean up finished runs —
all without leaving your terminal.

```
┌─────────────────────────────────────────────────────────┐
│ nqi                                              q:Quit  │
├──────────────────┬──────────────────────────────────────┤
│ ● make all       │ [Running] make all                    │
│ ○ ./benchmark    │                                       │
│ ✓ nq sleep 60    │ gcc -O2 -o main main.c               │
│                  │ Linking ...                           │
│                  │                                       │
├──────────────────┴──────────────────────────────────────┤
│ K:Kill  k/j:Swap  d:Re-enqueue  c:Clean  y:Copy  !:Cmd  │
└─────────────────────────────────────────────────────────┘
```

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
| `gcc` or `clang` + `make` | to build the bundled `nq` C utilities |
| `pipx` or `pip` | for the Python install |

> macOS and BSDs should work but are untested. `flock(2)` must be available.

## Installation

### One-line install

```bash
curl -fsSL https://raw.githubusercontent.com/mamiglia/nqi/master/install.sh | bash
```

This clones the repo, compiles `nq`, installs `nq`/`nqtail`/`nqterm` wrappers to
`~/.local/bin` (backed by upstream binaries in `~/.local/lib/nqi/bin`), and
installs the `nqi` TUI via `pipx` (falling back to `pip --user`).

The wrappers set `NQDIR=~/.local/share/nq` when `NQDIR` is unset, so plain
`nq ...` commands and `nqi` use the same default queue.

If `~/.local/bin` is not yet in your `PATH`, add this to your shell config
(`~/.bashrc`, `~/.zshrc`, etc.):

```bash
export PATH="${HOME}/.local/bin:${PATH}"
```

### pip / pipx

```bash
# isolated environment (recommended)
pipx install git+https://github.com/mamiglia/nqi.git

# or into user site-packages
pip install --user git+https://github.com/mamiglia/nqi.git
```

`setup.py` automatically initialises the `nq` git submodule (or downloads the
upstream tarball), compiles it, and bundles the binaries inside the wheel. If
compilation fails, `nqi` falls back to a system-installed `nq`.

If you use a separately installed `nq` binary and want the same default queue
as `nqi`, set this in your shell config:

```bash
export NQDIR="${HOME}/.local/share/nq"
```

### Manual

```bash
git clone --recurse-submodules https://github.com/mamiglia/nqi.git
cd nqi/nq && make && sudo make install   # installs nq to /usr/local/bin
cd ..
pip install --user .
```

## Usage

```bash
# Optional (recommended unless using the installer wrappers)
export NQDIR="${HOME}/.local/share/nq"

# Enqueue jobs
nq make all
nq ./run-benchmark --config fast
nq sleep 60

# Tail the currently-running job's output
nqtail

# Open the interactive TUI
nqi
```

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

### Custom nq binary

```bash
NQ_BIN=/opt/custom/nq nqi
```

`nqi` resolves the `nq` binary in this order:

1. `NQ_BIN` environment variable
2. Bundled binary at `nqi/bin/nq` (compiled at install time)
3. Local development build at `./nq/nq`
4. System `PATH`

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
└── install.sh       # one-shot shell installer
```

## License

- `nqi` TUI — [MIT](LICENSE)
- `nq` C utilities — Public Domain ([CC0](http://creativecommons.org/publicdomain/zero/1.0/))
