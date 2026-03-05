import os
import shlex
import time
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, RichLog, Input, Label, Static
from textual.containers import Horizontal, Vertical, Container
from textual.binding import Binding
from textual.reactive import reactive
from rich.text import Text

from .logic import JobStatus, sanitize_ansi, get_job_command, get_job_status, kill_job, run_nq_cmd, swap_jobs
from .widgets import JobListItem

class NQY(App):
    """The main nqy application interface."""
    TITLE = "nqy"
    CSS_PATH = "styles.css"
    ENABLE_COMMAND_PALETTE = False

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("K", "delete_job", "Kill"),
        Binding("k", "move_up", "Swap Up"),
        Binding("j", "move_down", "Swap Down"),
        Binding("d", "restart_job", "Re-enqueue"),
        Binding("c", "clear_logs", "Clean"),
        Binding("y", "copy_log", "Copy Log"),
        Binding("!", "focus_input", "Command"),
        Binding("escape", "focus_list", "Back", show=False),
    ]

    selected_job = reactive(None)

    CONFIRM_TIMEOUT = 3.0  # seconds to confirm destructive actions

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._confirm_action = None  # name of action awaiting confirmation
        self._confirm_time = 0.0     # timestamp of first press

    def _require_confirmation(self, action_name: str, message: str, callback) -> None:
        """First press shows a warning; second press within timeout executes."""
        now = time.monotonic()
        if (
            self._confirm_action == action_name
            and now - self._confirm_time < self.CONFIRM_TIMEOUT
        ):
            self._confirm_action = None
            self._confirm_time = 0.0
            callback()
        else:
            self._confirm_action = action_name
            self._confirm_time = now
            self.notify(message, severity="warning", timeout=self.CONFIRM_TIMEOUT)

    def compose(self) -> ComposeResult:
        with Horizontal(id="main_container"):
            with Vertical(id="job_list_container", classes="pane") as p:
                p.border_title = "JOBS"
                p.can_focus = False
                yield ListView(id="job_list")
            with Vertical(id="right_panel"):
                with Vertical(id="log_container", classes="pane") as p:
                    p.border_title = "LOG OUTPUT"
                    p.can_focus = False
                    yield Static("", id="log_header")
                    yield RichLog(id="log_view", wrap=True, auto_scroll=True, max_lines=1000)
                with Container(id="command_pane") as p:
                    p.can_focus = False
                    with Horizontal(id="input_layout"):
                        yield Label(" λ ", id="input_prompt")
                        yield Input(placeholder="Enter command (hit ! to focus)...", id="command_input")
        yield Footer()

    def on_mount(self) -> None:
        default_nq_dir = os.path.expanduser("~/.local/share/nq")
        self.nq_dir = os.path.abspath(os.environ.get("NQDIR", default_nq_dir))
        os.makedirs(self.nq_dir, exist_ok=True)
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

    def on_key(self, event) -> None:
        """Suppress tab focus cycling."""
        if event.key in ("tab", "shift+tab"):
            event.prevent_default()

    def refresh_jobs(self) -> None:
        try:
            files = sorted([f for f in os.listdir(self.nq_dir) if f.startswith(",")], reverse=True)
            job_list = self.query_one("#job_list", ListView)
            
            current_widgets = list(job_list.children)
            current_ids = [getattr(w, "job_id", None) for w in current_widgets]

            if current_ids != files:
                was_focused = job_list.has_focus

                # Build new items before touching the DOM
                new_items = []
                for f in files:
                    path = os.path.join(self.nq_dir, f)
                    status = get_job_status(path)
                    cmd = get_job_command(path)
                    name = " ".join(cmd) if cmd else f
                    new_items.append(JobListItem(f, status, name))

                # Determine the desired index before clearing
                if self._target_index is not None and files:
                    target = max(0, min(self._target_index, len(files) - 1))
                    self._target_index = None
                elif self.selected_job:
                    target = next(
                        (i for i, f in enumerate(files) if f == self.selected_job),
                        0 if files else None,
                    )
                else:
                    target = 0 if files else None

                # Swap content in one batch — clear and mount together
                job_list.clear()
                job_list.mount_all(new_items)

                def _restore(idx=target, focus=was_focused):
                    job_list.index = idx
                    if focus:
                        job_list.focus()
                self.call_after_refresh(_restore)
            else:
                for widget in current_widgets:
                    status = get_job_status(os.path.join(self.nq_dir, widget.job_id))
                    widget.update_status(status)

            self.query_one("#job_list_container").border_subtitle = f"{len(files)} total"
        except OSError as e:
            self.notify(f"Failed to refresh jobs: {e}", severity="error")

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item:
            if self.selected_job != event.item.job_id:
                self.selected_job = event.item.job_id
                self.query_one("#log_view").clear()
                self.last_read_pos[self.selected_job] = 0
                # Show the command as a fixed header
                self.query_one("#log_header", Static).update(
                    f"$ {event.item.display_name}"
                )
                self.update_log_tail()
                self.query_one("#log_container").border_subtitle = self.selected_job
        else:
            self.selected_job = None
            self.query_one("#log_view").clear()
            self.query_one("#log_header", Static).update("")
            self.query_one("#log_container").border_subtitle = ""

    def update_log_tail(self) -> None:
        if not self.selected_job: return
        log_path = os.path.join(self.nq_dir, self.selected_job)
        log_view = self.query_one("#log_view", RichLog)
        try:
            status = get_job_status(log_path)
            size = os.path.getsize(log_path)
            pos = self.last_read_pos.get(self.selected_job, 0)
            if size < pos: pos = 0; log_view.clear()
            if pos == 0:
                # Skip the first line (exec command) — it's shown in the header
                with open(log_path, "rb") as f:
                    first_line = f.readline()
                    pos = f.tell()
            if size > pos:
                with open(log_path, "rb") as f:
                    f.seek(pos)
                    new_data = f.read(1024 * 20)
                    self.last_read_pos[self.selected_job] = f.tell()
                    clean_text = sanitize_ansi(new_data.decode("utf-8", errors="replace"))
                    if clean_text: log_view.write(clean_text)
            elif status == JobStatus.QUEUED and pos <= size:
                # No output yet — show a waiting message
                log_view.clear()
                log_view.write(Text("Waiting in queue...", style="dim italic"))
                self.last_read_pos[self.selected_job] = pos
        except OSError as e:
            self.notify(f"Error reading log: {e}", severity="error")

    def action_focus_input(self) -> None:
        self.query_one("#command_input").focus()

    def action_focus_list(self) -> None:
        self.query_one("#job_list").focus()

    def action_copy_log(self) -> None:
        """Copy the full log of the selected job to the clipboard."""
        if not self.selected_job:
            return
        log_path = os.path.join(self.nq_dir, self.selected_job)
        try:
            with open(log_path, "r", errors="replace") as f:
                f.readline()  # skip exec header
                content = f.read()
            content = sanitize_ansi(content).strip()
            if content:
                self.copy_to_clipboard(content)
                self.notify("Log copied to clipboard.")
            else:
                self.notify("No log content to copy.", severity="warning")
        except Exception:
            self.notify("Failed to read log file.", severity="error")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        if cmd:
            run_nq_cmd(shlex.split(cmd))
            self.query_one("#command_input").value = ""
            self.action_focus_list()
            self.refresh_jobs()

    def _swap(self, direction: int) -> None:
        """Swap the selected job with its neighbor. direction: +1 (down) or -1 (up)."""
        job_list = self.query_one("#job_list")
        idx = job_list.index
        neighbor = idx + direction if idx is not None else None
        if neighbor is None or neighbor < 0 or neighbor >= len(job_list.children):
            return
        j1, j2 = job_list.children[min(idx, neighbor)], job_list.children[max(idx, neighbor)]
        if j1.status != JobStatus.QUEUED or j2.status != JobStatus.QUEUED:
            self.notify("Can only swap queued jobs", severity="warning")
            return
        self._target_index = neighbor
        swap_jobs(self.nq_dir, j1.job_id, j2.job_id, list(reversed([w.job_id for w in job_list.children])))
        self.refresh_jobs()

    def action_move_down(self) -> None:
        self._swap(+1)

    def action_move_up(self) -> None:
        self._swap(-1)

    def action_restart_job(self) -> None:
        if self.selected_job:
            path = os.path.join(self.nq_dir, self.selected_job)
            cmd_args = get_job_command(path)
            if cmd_args:
                run_nq_cmd(cmd_args)
            self.refresh_jobs()

    def action_delete_job(self) -> None:
        if self.selected_job:
            job_id = self.selected_job
            status = get_job_status(os.path.join(self.nq_dir, job_id))
            if status not in (JobStatus.RUNNING, JobStatus.QUEUED):
                # self.notify("Can only kill queued or running jobs", severity="warning")
                return

            def _do_kill():
                job_list = self.query_one("#job_list")
                self._target_index = job_list.index
                if not kill_job(job_id, self.nq_dir):
                    # self.notify("Job is no longer killable", severity="warning")
                    pass
                self.refresh_jobs()
            self._require_confirmation(
                "kill",
                "Press K again to kill the selected job.",
                _do_kill,
            )

    def action_clear_logs(self) -> None:
        def _do_clean():
            removed = 0
            for f in os.listdir(self.nq_dir):
                if f.startswith(",") and get_job_status(os.path.join(self.nq_dir, f)) == JobStatus.FINISHED:
                    try:
                        os.remove(os.path.join(self.nq_dir, f))
                        removed += 1
                    except OSError:
                        pass
            self.notify(f"Removed {removed} finished job(s).")
            self.refresh_jobs()
        self._require_confirmation(
            "clean",
            "Press c again to remove all finished jobs.",
            _do_clean,
        )

def main():
    # Default NQDIR to ~/.local/share/nq so jobs are stored in a persistent
    # user-owned directory instead of the current working directory.
    if "NQDIR" not in os.environ:
        nq_dir = os.path.expanduser("~/.local/share/nq")
        os.makedirs(nq_dir, exist_ok=True)
        os.environ["NQDIR"] = nq_dir
    app = NQY()
    app.run()

if __name__ == "__main__":
    main()
