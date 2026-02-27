from textual.app import ComposeResult
from textual.widgets import ListItem, Label

class JobListItem(ListItem):
    """A list item representing an nq job with status badge."""
    def __init__(self, job_id: str, status: str):
        super().__init__()
        self.job_id = job_id
        self.status = status

    def compose(self) -> ComposeResult:
        yield Label(self.get_display_text(), id="job_label")

    def get_display_text(self) -> str:
        if self.status == "Running":
            badge = "[bold #2ecc71][RUN][/] "
        elif self.status == "Finished":
            badge = "[bold #64748b][FIN][/] "
        else:
            badge = "[bold #f1c40f][QUE][/] "
        return f"{badge} {self.job_id}"

    def update_status(self, new_status: str):
        if self.status != new_status:
            self.status = new_status
            label = self.query_one("#job_label", Label)
            label.update(self.get_display_text())
