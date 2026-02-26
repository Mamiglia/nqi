import os
import subprocess
import fcntl
import re
import time
import shlex
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, Log, Input
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from textual.reactive import reactive

def sanitize_ansi(text: str) -> str:
    text = re.sub(r'\x1b\[[0-9;]*[HfJKm]', '', text)
    text = re.sub(r'\x1b\[[0-9;]*[A-G]', '', text)
    text = text.replace('\f', '\n--- Clear ---\n')
    return text

class JobListItem(ListItem):
    def __init__(self, job_id: str, status: str):
        super().__init__()
        self.job_id = job_id
        self.status = status

    def compose(self) -> ComposeResult:
        icon = "~"
        if self.status == "Running": icon = "▶"
        elif self.status == "Finished": icon = "✔"
        yield Label(f"{icon} {self.job_id}", classes=self.status.lower())

class NQX(App):
    CSS = """
    Screen { background: $surface; }
    #main_container { height: 1fr; }
    #job_list_container { width: 35%; border-right: tall $primary; }
    #log_container { width: 65%; padding: 0; }
    #command_input { dock: bottom; margin: 1; }
    ListItem { padding: 0 1; }
    ListItem.--highlight { background: $primary; color: $text; }
    Label.queued { color: yellow; }
    Label.running { color: green; text-style: bold; }
    Label.finished { color: gray; }
    Log { background: $surface; color: $text; border: solid $primary; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "delete_job", "Kill/Del"),
        Binding("K", "move_up", "Swap Up"),
        Binding("J", "move_down", "Swap Down"),
        Binding("s", "restart_job", "Restart"),
        Binding("c", "clear_logs", "Clean"),
        Binding("r", "refresh", "Refresh"),
    ]

    selected_job = reactive(None)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main_container"):
            with Vertical(id="job_list_container"):
                yield Label(" Jobs Queue", variant="header")
                yield ListView(id="job_list")
            with Vertical(id="log_container"):
                yield Label(" Log Output", variant="header")
                yield Log(id="log_view", auto_scroll=True, max_lines=1000)
        yield Input(placeholder="Enter command...", id="command_input")
        yield Footer()

    def on_mount(self) -> None:
        self.nq_path = os.path.abspath("./nq/nq")
        self.last_read_pos = {} 
        self.refresh_jobs()
        self.set_interval(1.0, self.refresh_jobs)
        self.set_interval(0.5, self.update_log_tail)

    def get_job_status(self, path: str) -> str:
        try:
            with open(path, "r") as f:
                try:
                    fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
                    fcntl.flock(f, fcntl.LOCK_UN)
                    return "Finished"
                except (BlockingIOError, IOError):
                    return "Running" if os.access(path, os.X_OK) else "Queued"
        except: return "Unknown"

    def refresh_jobs(self) -> None:
        nq_dir = os.environ.get("NQDIR", ".")
        try:
            files = sorted([f for f in os.listdir(nq_dir) if f.startswith(",")])
            job_list = self.query_one("#job_list", ListView)
            current_selection = None
            if job_list.index is not None and job_list.index < len(job_list.children):
                current_selection = job_list.children[job_list.index].job_id

            job_list.clear()
            for job_id in files:
                status = self.get_job_status(os.path.join(nq_dir, job_id))
                job_list.append(JobListItem(job_id, status))
            
            if current_selection:
                for i, item in enumerate(job_list.children):
                    if item.job_id == current_selection:
                        job_list.index = i
                        break
        except: pass

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item and self.selected_job != event.item.job_id:
            self.selected_job = event.item.job_id
            self.query_one("#log_view", Log).clear()
            self.last_read_pos[self.selected_job] = 0
            self.update_log_tail()

    def update_log_tail(self) -> None:
        if not self.selected_job: return
        log_path = os.path.join(os.environ.get("NQDIR", "."), self.selected_job)
        log_view = self.query_one("#log_view", Log)
        try:
            size = os.path.getsize(log_path)
            pos = self.last_read_pos.get(self.selected_job, 0)
            if size < pos: pos = 0; log_view.clear()
            if size > pos:
                with open(log_path, "rb") as f:
                    f.seek(pos)
                    new_data = f.read(1024 * 20)
                    self.last_read_pos[self.selected_job] = f.tell()
                    clean_text = sanitize_ansi(new_data.decode("utf-8", errors="replace"))
                    if clean_text.strip(): log_view.write(clean_text)
        except: pass

    def run_nq_cmd(self, args: list):
        # Use executable to keep argv[0] as "nq" while using the correct path
        subprocess.Popen(["nq"] + args, executable=self.nq_path,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _swap(self, idx1, idx2):
        nq_dir = os.environ.get("NQDIR", ".")
        job_list = self.query_one("#job_list", ListView)
        
        j1 = job_list.children[idx1]
        j2 = job_list.children[idx2]
        if j1.status != "Queued" or j2.status != "Queued":
            self.notify("Can only swap queued jobs", severity="warning")
            return

        start_idx = min(idx1, idx2)
        affected_items = job_list.children[start_idx:]
        
        commands = []
        for item in affected_items:
            path = os.path.join(nq_dir, item.job_id)
            with open(path, "r") as f:
                line = f.readline().strip()
                if line.startswith("exec "):
                    # Extract the original command parts, skipping 'exec' and the 'nq' binary
                    parts = shlex.split(line[5:])
                    if parts and (parts[0] == "nq" or parts[0].endswith("/nq")):
                        commands.append(parts[1:])
                    else:
                        commands.append(parts)
            subprocess.run([self.nq_path, "-k", item.job_id])
            try: os.remove(path)
            except: pass
        
        local_idx1 = idx1 - start_idx
        local_idx2 = idx2 - start_idx
        commands[local_idx1], commands[local_idx2] = commands[local_idx2], commands[local_idx1]

        for cmd_args in commands:
            self.run_nq_cmd(cmd_args)
            time.sleep(0.02) 
        
        self.notify(f"Swapped jobs")
        self.refresh_jobs()

    def action_move_down(self) -> None:
        job_list = self.query_one("#job_list", ListView)
        idx = job_list.index
        if idx is not None and idx < len(job_list.children) - 1:
            self._swap(idx, idx + 1)

    def action_move_up(self) -> None:
        job_list = self.query_one("#job_list", ListView)
        idx = job_list.index
        if idx is not None and idx > 0:
            self._swap(idx, idx - 1)

    def action_restart_job(self) -> None:
        if self.selected_job:
            path = os.path.join(os.environ.get("NQDIR", "."), self.selected_job)
            with open(path, "r") as f:
                line = f.readline().strip()
                if line.startswith("exec "):
                    parts = shlex.split(line[5:])
                    cmd_args = parts[1:] if (parts[0] == "nq" or parts[0].endswith("/nq")) else parts
                    subprocess.run([self.nq_path, "-k", self.selected_job])
                    try: os.remove(path)
                    except: pass
                    self.run_nq_cmd(cmd_args)
            self.notify("Restarted job")
            self.refresh_jobs()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        if cmd:
            self.run_nq_cmd(shlex.split(cmd))
            self.query_one("#command_input", Input).value = ""
            self.refresh_jobs()

    def action_delete_job(self) -> None:
        if self.selected_job:
            subprocess.run([self.nq_path, "-k", self.selected_job])
            self.refresh_jobs()

    def action_clear_logs(self) -> None:
        nq_dir = os.environ.get("NQDIR", ".")
        for f in os.listdir(nq_dir):
            if f.startswith(",") and self.get_job_status(os.path.join(nq_dir, f)) == "Finished":
                os.remove(os.path.join(nq_dir, f))
        self.selected_job = None
        self.query_one("#log_view", Log).clear()
        self.refresh_jobs()

    def action_refresh(self) -> None:
        self.refresh_jobs()
        if self.selected_job:
            self.query_one("#log_view", Log).clear()
            self.last_read_pos[self.selected_job] = 0
            self.update_log_tail()

if __name__ == "__main__":
    app = NQX()
    app.run()
