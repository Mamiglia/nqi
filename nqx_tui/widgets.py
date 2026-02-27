from textual.app import ComposeResult
from textual.widgets import ListItem, Static

class JobListItem(ListItem):
    """A list item representing an nq job with status badge."""
    def __init__(self, job_id: str, status: str):
        super().__init__()
        self.job_id = job_id
        self.status = status

    def compose(self) -> ComposeResult:
        yield Static(self.get_display_text(), id="job_label")

    def get_display_text(self) -> str:
        if self.status == "Running":
            badge = "[bold #00ff00][[RUN]][/] "  # Bright Green
        elif self.status == "Finished":
            badge = "[bold #666666][[FIN]][/] "  # Muted Gray
        else:
            badge = "[bold #ffff00][[QUE]][/] "  # Yellow
        return f"{badge} {self.job_id}"

    def update_status(self, new_status: str):
        if self.status != new_status:
            self.status = new_status
            label = self.query_one("#job_label", Static)
            label.update(self.get_display_text())
