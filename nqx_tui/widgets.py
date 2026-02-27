from textual.app import ComposeResult
from textual.widgets import ListItem, Static

from .logic import JobStatus

_STATUS_BADGES = {
    JobStatus.RUNNING:  "[bold #00ff00][[RUN]][/] ",
    JobStatus.FINISHED: "[bold #666666][[FIN]][/] ",
    JobStatus.QUEUED:   "[bold #ffff00][[QUE]][/] ",
    JobStatus.UNKNOWN:  "[bold #ff0000][[???]][/] ",
}

class JobListItem(ListItem):
    """A list item representing an nq job with status badge."""
    def __init__(self, job_id: str, status: JobStatus, display_name: str):
        super().__init__()
        self.job_id = job_id
        self.status = status
        self.display_name = display_name

    def compose(self) -> ComposeResult:
        yield Static(self._display_text(), id="job_label")

    def _display_text(self) -> str:
        badge = _STATUS_BADGES.get(self.status, _STATUS_BADGES[JobStatus.UNKNOWN])
        return f"{badge} {self.display_name}"

    def update_status(self, new_status: JobStatus):
        if self.status != new_status:
            self.status = new_status
            self.query_one("#job_label", Static).update(self._display_text())
