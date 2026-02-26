import os
import subprocess
import fcntl
import re
from textual.app import App, ComposeResult
from textual.widgets import Header, Footer, ListView, ListItem, Label, Log, Input
from textual.containers import Horizontal, Vertical
from textual.binding import Binding
from textual.reactive import reactive

def sanitize_ansi(text: str) -> str:
    # Remove terminal control sequences that would mess up the layout
    # specifically Clear Screen and Cursor Movement used by bigjob.sh/watch
    text = re.sub(r'\x1b\[[0-9;]*[HfJKm]', '', text)
    text = re.sub(r'\x1b\[[0-9;]*[A-G]', '', text)
    # Also handle form feeds which are often used as clear screen
    text = text.replace('\f', '\n--- Clear ---\n')
    return text

class JobListItem(ListItem):
    def __init__(self, job_id: str, status: str):
        super().__init__()
        self.job_id = job_id
        self.status = status # "Queued", "Running", "Finished"

    def compose(self) -> ComposeResult:
        if self.status == "Running":
            icon = "▶"
        elif self.status == "Finished":
            icon = "✔"
        elif self.status == "Queued":
            icon = "~"
        else:
            icon = "?"
        
        yield Label(f"{icon} {self.job_id}", classes=self.status.lower())

class NQX(App):
    CSS = """
    Screen {
        background: $surface;
    }

    #main_container {
        height: 1fr;
    }

    #job_list_container {
        width: 35%;
        border-right: tall $primary;
    }

    #log_container {
        width: 65%;
        padding: 0;
    }

    #command_input {
        dock: bottom;
        margin: 1;
    }

    ListItem {
        padding: 0 1;
    }

    ListItem.--highlight {
        background: $primary;
        color: $text;
    }

    Label.queued {
        color: yellow;
    }

    Label.running {
        color: green;
        text-style: bold;
    }

    Label.finished {
        color: gray;
    }

    Log {
        background: $surface;
        color: $text;
        border: solid $primary;
    }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("d", "delete_job", "Kill Job"),
        Binding("c", "clear_logs", "Clear Logs"),
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
                # max_lines keeps the memory usage low and avoids overflow issues
                yield Log(id="log_view", auto_scroll=True, max_lines=1000)
        yield Input(placeholder="Enter command to schedule (e.g., ./bigjob.sh -m 5)", id="command_input")
        yield Footer()

    def on_mount(self) -> None:
        self.nq_path = os.path.abspath("./nq/nq")
        self.last_read_pos = {} 
        self.refresh_jobs()
        self.set_interval(1.0, self.refresh_jobs)
        self.set_interval(0.5, self.update_log_tail) # Faster updates for tailing

    def get_job_status(self, path: str) -> str:
        try:
            with open(path, "r") as f:
                try:
                    fcntl.flock(f, fcntl.LOCK_SH | fcntl.LOCK_NB)
                    fcntl.flock(f, fcntl.LOCK_UN)
                    return "Finished"
                except (BlockingIOError, IOError):
                    if os.access(path, os.X_OK):
                        return "Running"
                    return "Queued"
        except Exception:
            return "Unknown"

    def refresh_jobs(self) -> None:
        nq_dir = os.environ.get("NQDIR", ".")
        try:
            files = [f for f in os.listdir(nq_dir) if f.startswith(",")]
            files.sort()
            job_list = self.query_one("#job_list", ListView)
            current_selection = None
            if job_list.index is not None and job_list.index < len(job_list.children):
                current_selection = job_list.children[job_list.index].job_id

            job_list.clear()
            for job_id in files:
                status = self.get_job_status(os.path.join(nq_dir, job_id))
                item = JobListItem(job_id, status)
                job_list.append(item)
            
            if current_selection:
                for i, item in enumerate(job_list.children):
                    if item.job_id == current_selection:
                        job_list.index = i
                        break
        except Exception:
            pass

    def on_list_view_highlighted(self, event: ListView.Highlighted) -> None:
        if event.item:
            if self.selected_job != event.item.job_id:
                self.selected_job = event.item.job_id
                self.query_one("#log_view", Log).clear()
                self.last_read_pos[self.selected_job] = 0
                self.update_log_tail()

    def update_log_tail(self) -> None:
        if not self.selected_job:
            return
        
        nq_dir = os.environ.get("NQDIR", ".")
        log_path = os.path.join(nq_dir, self.selected_job)
        log_view = self.query_one("#log_view", Log)
        
        try:
            size = os.path.getsize(log_path)
            pos = self.last_read_pos.get(self.selected_job, 0)
            
            if size < pos:
                pos = 0
                log_view.clear()

            if size > pos:
                with open(log_path, "rb") as f:
                    f.seek(pos)
                    # Limit the read size per tick to keep UI responsive
                    new_data = f.read(1024 * 20) 
                    self.last_read_pos[self.selected_job] = f.tell()
                    
                    text = new_data.decode("utf-8", errors="replace")
                    # Sanitize the text to remove layout-breaking control sequences
                    clean_text = sanitize_ansi(text)
                    if clean_text.strip():
                        log_view.write(clean_text)
        except Exception:
            pass

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        cmd = event.value.strip()
        if cmd:
            try:
                subprocess.Popen([self.nq_path] + cmd.split(), 
                                 cwd=os.getcwd(),
                                 stdout=subprocess.DEVNULL, 
                                 stderr=subprocess.DEVNULL)
                self.query_one("#command_input", Input).value = ""
                self.notify(f"Scheduled: {cmd}")
                self.refresh_jobs()
            except Exception as e:
                self.notify(f"Failed to schedule: {e}", severity="error")

    def action_delete_job(self) -> None:
        if not self.selected_job:
            return
        
        try:
            subprocess.run([self.nq_path, "-k", self.selected_job])
            self.notify(f"Terminated: {self.selected_job}")
            self.refresh_jobs()
        except Exception as e:
            self.notify(f"Error: {e}", severity="error")

    def action_clear_logs(self) -> None:
        nq_dir = os.environ.get("NQDIR", ".")
        count = 0
        for f in os.listdir(nq_dir):
            if f.startswith(","):
                path = os.path.join(nq_dir, f)
                if self.get_job_status(path) == "Finished":
                    os.remove(path)
                    count += 1
        self.notify(f"Cleaned {count} finished logs")
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
