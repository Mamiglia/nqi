#!/usr/bin/env bash
# install.sh – Install nqi (TUI) + nq/nqtail/nqterm (C utilities)
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/mamiglia/nqi/master/install.sh | bash
#   ./install.sh

set -euo pipefail

# ── helpers ────────────────────────────────────────────────────────────────────
info()  { printf '\033[1;34m==> \033[0m%s\n' "$*"; }
ok()    { printf '\033[1;32m ok \033[0m%s\n' "$*"; }
warn()  { printf '\033[1;33mwarn\033[0m %s\n' "$*" >&2; }
die()   { printf '\033[1;31merr \033[0m%s\n' "$*" >&2; exit 1; }

have_cmd() { command -v "$1" >/dev/null 2>&1; }

ask_yes_no() {
    local prompt="$1" answer
    printf '%s [y/N] ' "$prompt"
    if [ -t 0 ]; then
        read -r answer
    elif [ -e /dev/tty ]; then
        read -r answer </dev/tty
    else
        printf '(no tty, skipping)\n'
        return 1
    fi
    case "$answer" in
        [Yy]*) return 0 ;;
        *) return 1 ;;
    esac
}

detect_shell_rc() {
    case "${SHELL:-}" in
        */zsh)  echo "${HOME}/.zshrc" ;;
        */bash) echo "${HOME}/.bashrc" ;;
        *)      echo "${HOME}/.profile" ;;
    esac
}

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
NQI_REPO="https://github.com/mamiglia/nqi.git"
# Pin remote installs to a release tag by default for reproducibility.
NQI_REF="${NQI_REF:-v0.1.2}"

# Detect local checkout vs. being piped from curl.
if [[ -f "${SCRIPT_DIR}/pyproject.toml" || -f "${SCRIPT_DIR}/setup.py" ]]; then
    NQI_SRC="${SCRIPT_DIR}"
else
    NQI_SRC="git+${NQI_REPO}@${NQI_REF}"
fi

# ── pre-flight checks ────────────────────────────────────────────────────────
have_cmd python3 || die "python3 not found."
python3 -c "import sys; sys.exit(0 if sys.version_info >= (3,8) else 1)" \
    || die "Python 3.8 or newer is required."

if ! have_cmd make || { ! have_cmd gcc && ! have_cmd clang; }; then
    warn "gcc/clang and make are recommended to compile the bundled nq utilities."
    warn "If compilation fails during install, nqi will require a system-installed nq."
fi

# ── install nqi (setup.py compiles and bundles nq into the wheel) ─────────────
info "Installing nqi..."
if have_cmd pipx; then
    pipx install --force "${NQI_SRC}"
    ok "nqi installed via pipx"
else
    python3 -m pip install --user "${NQI_SRC}"
    ok "nqi installed via pip --user"
fi

if [[ "${NQI_SRC}" == git+* ]]; then
    ok "Installed from pinned ref: ${NQI_REF}"
fi

# ── migrate old install ──────────────────────────────────────────────────────
# Previous versions of install.sh created wrapper scripts; clean them up.
for bin in nq nqtail nqterm; do
    wrapper="${HOME}/.local/bin/${bin}"
    if [[ -f "${wrapper}" ]] && head -1 "${wrapper}" 2>/dev/null | grep -q '^#!/'; then
        rm -f "${wrapper}"
        ok "removed legacy wrapper ${wrapper}"
    fi
done
if [[ -d "${HOME}/.local/lib/nqi" ]]; then
    rm -rf "${HOME}/.local/lib/nqi"
    ok "removed legacy ${HOME}/.local/lib/nqi"
fi

# ── create default queue directory ────────────────────────────────────────────
NQ_DIR="${HOME}/.local/share/nq"
mkdir -p "${NQ_DIR}"
ok "Default job directory ready: ${NQ_DIR}"

# ── configure shell environment ──────────────────────────────────────────────
RC_FILE="$(detect_shell_rc)"
NQDIR_LINE='export NQDIR="${HOME}/.local/share/nq"'
PATH_LINE='export PATH="${HOME}/.local/bin:${PATH}"'

lines_to_add=()
labels=()

if ! grep -qF 'NQDIR' "${RC_FILE}" 2>/dev/null; then
    lines_to_add+=("${NQDIR_LINE}")
    labels+=("NQDIR (so nq and nqi share the same queue)")
fi

if [[ ":${PATH}:" != *":${HOME}/.local/bin:"* ]] && \
   ! grep -qF '.local/bin' "${RC_FILE}" 2>/dev/null; then
    lines_to_add+=("${PATH_LINE}")
    labels+=("PATH (so nqi and nq are available)")
fi

if [[ ${#lines_to_add[@]} -gt 0 ]]; then
    echo
    info "The following should be added to ${RC_FILE}:"
    for i in "${!lines_to_add[@]}"; do
        echo "  ${lines_to_add[$i]}    # ${labels[$i]}"
    done
    echo
    if ask_yes_no "  Append to ${RC_FILE}?"; then
        printf '\n# Added by nqi installer\n' >> "${RC_FILE}"
        for line in "${lines_to_add[@]}"; do
            echo "${line}" >> "${RC_FILE}"
        done
        ok "Updated ${RC_FILE}"
        warn "Run 'source ${RC_FILE}' or open a new terminal for changes to take effect."
    else
        warn "Skipped. Add them manually for nq and nqi to share the same queue."
    fi
fi

# ── fail-fast post-install check ──────────────────────────────────────────────
NQI_BIN="$(command -v nqi || true)"
if [[ -z "${NQI_BIN}" && -x "${HOME}/.local/bin/nqi" ]]; then
    NQI_BIN="${HOME}/.local/bin/nqi"
fi
[[ -n "${NQI_BIN}" ]] || die "nqi was installed but is not on PATH. Add ~/.local/bin to PATH and retry."

TMP_NQDIR="$(mktemp -d "${TMPDIR:-/tmp}/nqi-install-check.XXXXXX")"
trap 'rm -rf "${TMP_NQDIR}"' EXIT
if ! NQDIR="${TMP_NQDIR}" "${NQI_BIN}" true >/dev/null 2>&1; then
    die "Post-install check failed: unable to enqueue with nqi (no usable bundled/system nq)."
fi
if ! NQDIR="${TMP_NQDIR}" "${NQI_BIN}" -w >/dev/null 2>&1; then
    die "Post-install check failed: unable to wait for queued jobs via nqi -w."
fi
ok "Post-install check passed: nqi can execute nq jobs"

echo
echo "  nqi now wraps: nq, nqtail, nqterm"
echo "  Run:  nqi         - open the TUI"
echo "        nqi <cmd>   - enqueue a job (nq-compatible)"
echo "        nqi -f      - tail current job (nqtail-compatible)"
echo "        nqi -t      - open terminal helper (nqterm-compatible)"
