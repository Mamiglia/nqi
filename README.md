# nqy

**nqy** is a [Textual](https://textual.textualize.io/) terminal UI for
[nq](https://github.com/leahneukirchen/nq) — a minimal, daemon-free Unix job queue built on `flock(2)`.

Enqueue long-running commands with `nq` and manage them interactively: inspect
logs, reorder the queue, kill or re-enqueue jobs, and clean up finished runs —
all without leaving your terminal.

```
┌─────────────────────────────────────────────────────────┐
│ nqy                                              q:Quit  │
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
- Kill running jobs (with a confirmation two-key press)
- Re-enqueue any finished job with `d`
- Clean all finished job logs with `c`
- Copy a job's log path to the clipboard with `y`
- Ad-hoc command input with `!`
- Default queue stored in `~/.local/share/nq` — no config needed

## Prerequisites

| Requirement | Notes |
|---|---|
| Linux / macOS / any POSIX.1-2008 system | `flock(2)` required |
| Python ≥ 3.8 | for the TUI |
| `gcc` or `clang` + `make` | only needed when building from source |
| `pipx` or `pip` | for the Python install |

> macOS and BSDs should work but are untested. `flock(2)` must be available.

## Installation

### Recommended — one-line installer

Clone the repository and run the installer script.
It installs `nqy` via `pipx` (falling back to `pip --user`). The installation process automatically fetches and compiles [nq](https://github.com/leahneukirchen/nq), and installs the binaries (`nq`, `nqtail`, `nqterm`) to `~/.local/bin`.

```bash
git clone https://github.com/youruser/nqy.git
cd nqy
./install.sh
```

If `~/.local/bin` is not already in your `PATH`, the installer will tell you.
Add this line to your shell config (`~/.bashrc`, `~/.zshrc`, etc.) and restart
your shell:

```bash
export PATH="${HOME}/.local/bin:${PATH}"
```

### pip / pipx (also compiles nq automatically)

```bash
# isolated env — recommended
pipx install git+https://github.com/youruser/nqy.git

# or into your user site-packages
pip install --user git+https://github.com/youruser/nqy.git
```

`setup.py` will automatically initialise the `nq` git submodule (or download
the nq source tarball if not in a git working tree). When `make` and a C
compiler are available it compiles `nq` and bundles the binaries inside the
wheel. If compilation fails, `nqy` falls back to a system-installed `nq`.

### Manual (system-wide install of nq + user install of nqy)

```bash
git clone --recurse-submodules https://github.com/youruser/nqy.git
cd nqy/nq
make
sudo make install        # installs nq to /usr/local/bin
cd ..
pip install --user .     # installs nqy TUI
```

## Usage

```bash
# Enqueue jobs
nq make all
nq ./run-benchmark --config fast
nq sleep 60

# Tail the currently-running job's output
nqtail

# Open the interactive TUI (reads the same NQDIR as nq)
nqy
```

### TUI keyboard shortcuts

| Key | Action |
|-----|--------|
| `k` / `j` | Move the selected queued job up / down in the queue |
| `K` | Kill the selected job (press twice to confirm) |
| `d` | Duplicate the selected job |
| `c` | Clear all finished job log files in NQDIR |
| `y` | Copy the selected job's log path to clipboard |
| `!` | Open inline command input to enqueue an arbitrary command |
| `Esc` | Return focus to the job list |
| `q` | Quit |

### NQDIR — using multiple queues

By default all job log files live in `~/.local/share/nq`.  Set `NQDIR` to use
a different directory (useful for per-project or per-purpose queues):

```bash
# download queue
NQDIR=/tmp/downloads nq wget https://example.com/big.iso
NQDIR=/tmp/downloads nqy

# per-project queue stored inside the project
export NQDIR="$PWD/.nq"
nq make test
nqy
```

### Pointing nqy at a custom nq binary

```bash
NQ_BIN=/opt/custom/nq nqy
```

## Development

```bash
git clone --recurse-submodules https://github.com/youruser/nqy.git
cd nqy

# Build the C utilities (nq is a git submodule — already fetched above)
cd nq && make && cd ..

# Create and activate a virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the package in editable mode
pip install -e .

# Run the TUI directly
python nqy.py
```

### Project layout

```
nqy/
├── nq/                  # git submodule → github.com/leahneukirchen/nq
├── nqy/
│   ├── app.py           # Textual App — layout, bindings, event handling
│   ├── logic.py         # job-file parsing, flock-based status detection
│   ├── widgets.py       # custom Textual widgets (JobListItem, …)
│   ├── styles.css       # Textual CSS
│   └── bin/             # compiled nq binaries bundled at install time
├── nqy.py               # entry-point shim (sets NQDIR default, runs App)
├── setup.py             # custom build that compiles nq during pip install
├── pyproject.toml
└── install.sh           # one-shot shell installer
```

### nq binary lookup order

`nqy` finds the `nq` binary using the following fallback chain:

1. `NQ_BIN` environment variable
2. Bundled binary at `nqy/bin/nq` (compiled at install time)
3. Local development build at `./nq/nq`
4. System `PATH`

## Testing the install pipeline

Use the provided smoke-test to verify the full installation workflow in a
pristine Docker container before releasing:

```bash
./test-install.sh           # runs both install.sh and pip-install paths
./test-install.sh installer # test only the install.sh path
./test-install.sh pip       # test only the pip/setup.py path
```

See [test-install.sh](test-install.sh) and [Dockerfile.test](Dockerfile.test)
for details.

## License

- `nqy` TUI — [MIT](LICENSE)
- `nq` C utilities — Public Domain ([CC0](http://creativecommons.org/publicdomain/zero/1.0/))
