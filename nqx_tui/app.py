import os
import shlex
import subprocess
from pathlib import Path
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, Log, Input, Label, Static
from textual.containers import Horizontal, Vertical, Container
from textual.binding import Binding
from textual.reactive import reactive

from .logic import sanitize_ansi, get_job_status, get_nq_executable, run_nq_cmd, swap_jobs
from .widgets import JobListItem

class NQX(App):
    """The main nqx application interface."""
    TITLE = "nqx"
    CSS_PATH = "styles.css"

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "delete_job", "Kill"),
        Binding("K", "move_up", "Swap Up"),
        Binding("J", "move_down", "Swap Down"),
        Binding("s", "restart_job", "Restart"),
        Binding("c", "clear_logs", "Clean"),
        # Binding("r", "refresh", "Refresh"),
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
                p.can_focus = False
                yield ListView(id="job_list")
            with Vertical(id="log_container", classes="pane") as p:
                p.border_title = "LOG OUTPUT"
                p.can_focus = False
                yield Log(id="log_view", auto_scroll=True, max_lines=1000)
        with Container(id="command_pane") as p:
            p.can_focus = False
            with Horizontal(id="input_layout"):
                yield Label(" λ ", id="input_prompt")
                yield Input(placeholder="Enter command (hit ! to focus)...", id="command_input")
        yield Footer()

    def on_mount(self) -> None:
        self.nq_dir = os.path.abspath(os.environ.get("NQDIR", "."))
        self.nq_path = get_nq_executable()
        self.last_read_pos = {} 
        self._target_index = None
        self.refresh_jobs()
        self.set_interval(1.0, self.refresh_jobs)
        self.set_interval(0.5, self.update_log_tail)
        
        job_list = self.query_one("#job_list", ListView)
        job_list.highlight_on_focus = False
        job_list.index = 0
        job_list.focus()
        
        log_view = self.query_one("#log_view")
        log_view.can_focus = False
        log_view.styles.overflow_x = "hidden"

    def on_key(self, event) -> None:
        if event.key in ("tab", "shift+tab"):
            event.stop()
            event.prevent_default()

    def refresh_jobs(self) -> None:
        try:
            files = sorted([f for f in os.listdir(self.nq_dir) if f.startswith(",")])
            job_list = self.query_one("#job_list", ListView)
            
            # Record current state
            current_id = self.selected_job
            current_widgets = list(job_list.children)
            current_ids = [getattr(w, "job_id", None) for w in current_widgets]

            if current_ids != files:
                was_focused = job_list.has_focus
                # Clear and rebuild
                job_list.clear()
                for f in files:
                    status = get_job_status(os.path.join(self.nq_dir, f))
                    job_list.append(JobListItem(f, status))
                
                # Reset index to force Highlighted event even if it's the same index
                job_list.index = None
                
                if self._target_index is not None and files:
                    job_list.index = max(0, min(self._target_index, len(files) - 1))
                    self._target_index = None
                elif current_id:
                    for i, item in enumerate(job_list.children):
                        if item.job_id == current_id:
                            job_list.index = i
                            break
                    else:
                        if files: job_list.index = 0
                elif files:
                    job_list.index = 0
                
                if was_focused:
                    job_list.focus()
            else:
                for widget in current_widgets:
                    status = get_job_status(os.path.join(self.nq_dir, widget.job_id))
                    widget.update_status(status)

            self.query_one("#job_list_container").border_subtitle = f"{len(files)} total"
        except Exception:
            pass

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item:
            if self.selected_job != event.item.job_id:
                self.selected_job = event.item.job_id
                self.query_one("#log_view").clear()
                self.last_read_pos[self.selected_job] = 0
                self.update_log_tail()
                self.query_one("#log_container").border_subtitle = self.selected_job
        else:
            self.selected_job = None
            self.query_one("#log_view").clear()
            self.query_one("#log_container").border_subtitle = ""

    def update_log_tail(self) -> None:
        if not self.selected_job: return
        log_path = os.path.join(self.nq_dir, self.selected_job)
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
        except Exception:
            pass

    def action_focus_input(self) -> None:
        self.query_one("#command_input").focus()

    def action_focus_list(self) -> None:
        self.query_one("#job_list").focus()

    def action_none(self) -> None:
        """Disabled key handler."""
        pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        if cmd:
            run_nq_cmd(shlex.split(cmd))
            self.query_one("#command_input").value = ""
            self.action_focus_list()
            self.refresh_jobs()

    def action_move_down(self) -> None:
        job_list = self.query_one("#job_list")
        idx = job_list.index
        if idx is not None and idx < len(job_list.children) - 1:
            j1 = job_list.children[idx]
            j2 = job_list.children[idx + 1]
            if j1.status == "Queued" and j2.status == "Queued":
                current_files = [w.job_id for w in job_list.children]
                self._target_index = idx + 1
                swap_jobs(self.nq_dir, j1.job_id, j2.job_id, current_files)
                self.refresh_jobs()
            else:
                self.notify("Can only swap queued jobs", severity="warning")

    def action_move_up(self) -> None:
        job_list = self.query_one("#job_list")
        idx = job_list.index
        if idx is not None and idx > 0:
            j1 = job_list.children[idx - 1]
            j2 = job_list.children[idx]
            if j1.status == "Queued" and j2.status == "Queued":
                current_files = [w.job_id for w in job_list.children]
                self._target_index = idx - 1
                swap_jobs(self.nq_dir, j1.job_id, j2.job_id, current_files)
                self.refresh_jobs()
            else:
                self.notify("Can only swap queued jobs", severity="warning")

    def action_restart_job(self) -> None:
        if self.selected_job:
            job_list = self.query_one("#job_list")
            idx = job_list.index
            path = os.path.join(self.nq_dir, self.selected_job)
            with open(path, "r") as f:
                line = f.readline().strip()
                if line.startswith("exec "):
                    parts = shlex.split(line[5:])
                    cmd_args = parts[1:] if (parts[0] == "nq" or parts[0].endswith("/nq")) else parts
                    subprocess.run([self.nq_path, "-k", self.selected_job])
                    try: os.remove(path)
                    except: pass
                    self._target_index = idx
                    run_nq_cmd(cmd_args)
            self.refresh_jobs()

    def action_delete_job(self) -> None:
        if self.selected_job:
            job_list = self.query_one("#job_list")
            self._target_index = job_list.index
            subprocess.run([self.nq_path, "-k", self.selected_job])
            self.refresh_jobs()

    def action_clear_logs(self) -> None:
        for f in os.listdir(self.nq_dir):
            if f.startswith(",") and get_job_status(os.path.join(self.nq_dir, f)) == "Finished":
                try: os.remove(os.path.join(self.nq_dir, f))
                except: pass
        self.refresh_jobs()

    def action_refresh(self) -> None:
        self.refresh_jobs()
        if self.selected_job:
            self.query_one("#log_view").clear()
            self.last_read_pos[self.selected_job] = 0
            self.update_log_tail()
