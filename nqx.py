import os
import subprocess
import fcntl
import re
import time
import shlex
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, Log, Input, Static
from textual.containers import Horizontal, Vertical, Container
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
        yield Label(self.get_display_text(), id="status_label")

    def get_display_text(self) -> str:
        if self.status == "Running":
            badge = "[b][white on green] RUN [/][/]"
        elif self.status == "Finished":
            badge = "[b][white on #444444] FIN [/][/]"
        else:
            badge = "[b][black on yellow] QUE [/][/]"
        return f"{badge} [b]{self.job_id}[/]"

    def update_status(self, new_status: str):
        if self.status != new_status:
            self.status = new_status
            self.query_one("#status_label", Label).update(self.get_display_text())

class NQX(App):
    TITLE = "nqx"

    CSS = """
    Screen {
        background: #0f172a;
        color: #f8fafc;
    }

    #main_container {
        height: 1fr;
        padding: 1 1 0 1;
    }

    .pane {
        background: #1e293b;
        border: tall #334155;
        height: 100%;
    }

    .pane:focus-within {
        border: tall $primary;
    }

    #job_list_container { width: 35%; }
    #log_container { width: 65%; }

    #command_pane {
        height: 3;
        margin: 1;
        border: tall #334155;
        background: #1e293b;
    }

    #command_pane:focus-within {
        border: tall $primary;
    }

    ListView {
        background: transparent;
        height: 100%;
    }

    ListItem {
        padding: 0 1;
        background: transparent;
    }

    /* Highlight style - prominent and persistent */
    ListItem.--highlight {
        background: #2563eb;
        color: white;
        text-style: bold;
    }

    Log {
        background: transparent;
        color: #cbd5e1;
        overflow-x: hidden;
    }

    Input {
        background: transparent;
        border: none;
        color: white;
    }

    Input:focus { border: none; }

    #input_layout {
        layout: horizontal;
        height: 100%;
        align: left middle;
    }

    #input_prompt {
        color: $primary;
        text-style: bold;
        padding: 0 1;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "delete_job", "Kill"),
        Binding("K", "move_up", "Swap Up"),
        Binding("J", "move_down", "Swap Down"),
        Binding("s", "restart_job", "Restart"),
        Binding("c", "clear_logs", "Clean"),
        Binding("r", "refresh", "Refresh"),
        Binding("!", "focus_input", "Command"),
        Binding("escape", "focus_list", "Back", show=False),
        Binding("tab", "none", "None", show=False),
    ]

    selected_job = reactive(None)

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal(id="main_container"):
            with Vertical(id="job_list_container", classes="pane") as p:
                p.border_title = "JOBS"
                yield ListView(id="job_list")
            with Vertical(id="log_container", classes="pane") as p:
                p.border_title = "LOG OUTPUT"
                yield Log(id="log_view", auto_scroll=True, max_lines=1000)
        with Container(id="command_pane"):
            with Horizontal(id="input_layout"):
                yield Label(" λ ", id="input_prompt")
                yield Input(placeholder="Enter command...", id="command_input")
        yield Footer()

    def on_mount(self) -> None:
        self.nq_path = os.path.abspath("./nq/nq")
        self.last_read_pos = {} 
        self.refresh_jobs()
        self.set_interval(1.0, self.refresh_jobs)
        self.set_interval(0.5, self.update_log_tail)
        
        job_list = self.query_one("#job_list", ListView)
        if job_list.children:
            job_list.index = 0
        job_list.focus()

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
        nq_dir = os.path.abspath(os.environ.get("NQDIR", "."))
        try:
            files = sorted([f for f in os.listdir(nq_dir) if f.startswith(",")])
            job_list = self.query_one("#job_list", ListView)
            
            # Record current state
            current_id = self.selected_job
            current_widgets = list(job_list.children)
            current_ids = [getattr(w, "job_id", None) for w in current_widgets]

            if current_ids != files:
                # Full rebuild only if file set changed
                job_list.clear()
                for f in files:
                    status = self.get_job_status(os.path.join(nq_dir, f))
                    job_list.append(JobListItem(f, status))
                
                # Restore selection index by matching the job_id
                if current_id:
                    for i, item in enumerate(job_list.children):
                        if item.job_id == current_id:
                            job_list.index = i
                            break
                elif files and job_list.index is None:
                    job_list.index = 0
            else:
                # Surgical update of statuses only
                for widget in current_widgets:
                    status = self.get_job_status(os.path.join(nq_dir, widget.job_id))
                    widget.update_status(status)

            self.query_one("#job_list_container").border_subtitle = f"{len(files)} total"
        except: pass

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item and self.selected_job != event.item.job_id:
            self.selected_job = event.item.job_id
            self.query_one("#log_view").clear()
            self.last_read_pos[self.selected_job] = 0
            self.update_log_tail()
            self.query_one("#log_container").border_subtitle = self.selected_job

    def update_log_tail(self) -> None:
        if not self.selected_job: return
        log_path = os.path.join(os.path.abspath(os.environ.get("NQDIR", ".")), self.selected_job)
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
                    if clean_text: log_view.write(clean_text)
        except: pass

    def action_focus_input(self) -> None:
        self.query_one("#command_input").focus()

    def action_focus_list(self) -> None:
        self.query_one("#job_list").focus()

    def action_none(self) -> None:
        pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        if cmd:
            subprocess.Popen(["nq"] + shlex.split(cmd), executable=self.nq_path,
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.query_one("#command_input").value = ""
            self.action_focus_list()
            self.refresh_jobs()

    def run_nq_cmd(self, args: list):
        subprocess.Popen(["nq"] + args, executable=self.nq_path,
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

    def _swap(self, idx1, idx2):
        nq_dir = os.path.abspath(os.environ.get("NQDIR", "."))
        job_list = self.query_one("#job_list", ListView)
        if idx1 >= len(job_list.children) or idx2 >= len(job_list.children): return

        j1, j2 = job_list.children[idx1], job_list.children[idx2]
        if j1.status != "Queued" or j2.status != "Queued":
            self.notify("Can only swap queued jobs", severity="warning")
            return

        start_idx = min(idx1, idx2)
        affected_items = list(job_list.children[start_idx:])
        commands = []
        for item in affected_items:
            path = os.path.join(nq_dir, item.job_id)
            with open(path, "r") as f:
                line = f.readline().strip()
                if line.startswith("exec "):
                    parts = shlex.split(line[5:])
                    commands.append(parts[1:] if (parts[0] == "nq" or parts[0].endswith("/nq")) else parts)
            subprocess.run([self.nq_path, "-k", item.job_id])
            try: os.remove(path)
            except: pass
        
        l1, l2 = idx1 - start_idx, idx2 - start_idx
        commands[l1], commands[l2] = commands[l2], commands[l1]
        for cmd_args in commands:
            self.run_nq_cmd(cmd_args)
            time.sleep(0.02)
        self.refresh_jobs()

    def action_move_down(self) -> None:
        idx = self.query_one("#job_list").index
        if idx is not None: self._swap(idx, idx + 1)

    def action_move_up(self) -> None:
        idx = self.query_one("#job_list").index
        if idx is not None and idx > 0: self._swap(idx, idx - 1)

    def action_restart_job(self) -> None:
        if self.selected_job:
            nq_dir = os.path.abspath(os.environ.get("NQDIR", "."))
            path = os.path.join(nq_dir, self.selected_job)
            with open(path, "r") as f:
                line = f.readline().strip()
                if line.startswith("exec "):
                    parts = shlex.split(line[5:])
                    cmd_args = parts[1:] if (parts[0] == "nq" or parts[0].endswith("/nq")) else parts
                    subprocess.run([self.nq_path, "-k", self.selected_job])
                    try: os.remove(path)
                    except: pass
                    self.run_nq_cmd(cmd_args)
            self.refresh_jobs()

    def action_delete_job(self) -> None:
        if self.selected_job:
            subprocess.run([self.nq_path, "-k", self.selected_job])
            self.refresh_jobs()

    def action_clear_logs(self) -> None:
        nq_dir = os.path.abspath(os.environ.get("NQDIR", "."))
        for f in os.listdir(nq_dir):
            if f.startswith(",") and self.get_job_status(os.path.join(nq_dir, f)) == "Finished":
                os.remove(os.path.join(nq_dir, f))
        self.refresh_jobs()

    def action_refresh(self) -> None:
        self.refresh_jobs()
        if self.selected_job:
            self.query_one("#log_view").clear()
            self.last_read_pos[self.selected_job] = 0
            self.update_log_tail()

if __name__ == "__main__":
    NQX().run()
