import os
import fcntl
import re
import shlex
import signal
import subprocess
import time
from enum import Enum


class JobStatus(Enum):
    RUNNING = "Running"
    QUEUED = "Queued"
    FINISHED = "Finished"
    UNKNOWN = "Unknown"

def sanitize_ansi(text: str) -> str:
    """Removes ANSI escape codes and formats logs."""
    text = re.sub(r'\x1b\[[0-9;]*[HfJKm]', '', text)
    text = re.sub(r'\x1b\[[0-9;]*[A-G]', '', text)
    text = text.replace('\f', '\n--- Clear ---\n')
    return text

def get_job_status(path: str) -> JobStatus:
    """Determines the current status of an nq job by checking file locks."""
    try:
        with open(path, "r") as f:
            try:
                # Try to get a shared lock without blocking
                fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
                fcntl.flock(f, fcntl.LOCK_UN)
                return JobStatus.FINISHED
            except (BlockingIOError, IOError):
                # If lock is held, check if the executable bit is set
                return JobStatus.RUNNING if os.access(path, os.X_OK) else JobStatus.QUEUED
    except (OSError, ValueError):
        return JobStatus.UNKNOWN

def get_job_pid(job_id: str) -> int | None:
    """Extracts the PID from an nq job filename (`,TIMESTAMP.PID`)."""
    dot = job_id.rfind(".")
    if dot == -1:
        return None
    try:
        return int(job_id[dot + 1:])
    except ValueError:
        return None

def kill_job(job_id: str) -> None:
    """Kills a running or queued nq job by sending SIGTERM to its PID."""
    pid = get_job_pid(job_id)
    if pid is None:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass  # process already exited

def get_binary_path(name="nq"):
    """Returns the absolute path to an nq utility binary.

    Search order:
    1. If name is 'nq', check NQ_BIN environment variable.
    2. Bundled binary in nqy/bin/{name} (compiled at install time by setup.py).
    3. Local development build at ./nq/{name}.
    4. System PATH.
    """
    if name == "nq":
        env_nq = os.environ.get("NQ_BIN")
        if env_nq and os.path.isfile(env_nq):
            return env_nq

    # Binary bundled inside the installed package (nqy/bin/...)
    bundled = os.path.join(os.path.dirname(__file__), "bin", name)
    if os.path.isfile(bundled):
        return bundled

    # Local development tree
    local_path = os.path.abspath(f"./nq/{name}")
    if os.path.isfile(local_path):
        return local_path

    # Fallback to system PATH
    return name

def get_nq_executable():
    return get_binary_path("nq")

def get_job_command(path: str) -> list[str] | None:
    """Reads the command from a job file's first line (exec ...)."""
    try:
        with open(path, "r") as f:
            line = f.readline().strip()
            if line.startswith("exec "):
                parts = shlex.split(line[5:])
                return parts[1:] if (parts[0] == "nq" or parts[0].endswith("/nq")) else parts
    except (OSError, ValueError):
        pass
    return None

def run_nq_cmd(args: list):
    """Executes an nq command in the background."""
    nq_path = get_nq_executable()
    subprocess.Popen(["nq"] + args, executable=nq_path,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

def swap_jobs(nq_dir: str, job1_id: str, job2_id: str, current_files: list):
    """Swaps two queued jobs by re-enqueuing affected tasks."""

    # Find indices in the current list
    idx1 = current_files.index(job1_id)
    idx2 = current_files.index(job2_id)
    
    start_idx = min(idx1, idx2)
    affected_ids = current_files[start_idx:]
    
    commands = []
    for jid in affected_ids:
        path = os.path.join(nq_dir, jid)
        if get_job_status(path) != JobStatus.QUEUED:
            continue # Skip non-queued jobs if state changed

        cmd = get_job_command(path)
        if cmd:
            commands.append(cmd)

        # Kill and remove old job
        kill_job(jid)
        try:
            os.remove(path)
        except OSError:
            pass
    
    # Perform swap in the command list
    l1, l2 = idx1 - start_idx, idx2 - start_idx
    if l1 < len(commands) and l2 < len(commands):
        commands[l1], commands[l2] = commands[l2], commands[l1]
    
    # Re-enqueue
    for cmd_args in commands:
        run_nq_cmd(cmd_args)
        time.sleep(0.02)
