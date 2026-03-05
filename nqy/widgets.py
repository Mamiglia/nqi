from textual.app import ComposeResult
from textual.widgets import ListItem, Static

from .logic import JobStatus

_STATUS_BADGES = {
    JobStatus.RUNNING:  "[bold #00ff00][[RUN]][/] ",
    JobStatus.FINISHED: "[bold #666666][[FIN]][/] ",
    JobStatus.QUEUED:   "[bold #ffff00][[QUE]][/] ",
    JobStatus.UNKNOWN:  "[bold #ff0000][[???]][/] ",
}

_BADGE_WIDTH = 7  # rendered width of badge, e.g. "[RUN] "

class JobListItem(ListItem):
    """A list item representing an nq job with status badge and marquee scroll."""
    def __init__(self, job_id: str, status: JobStatus, display_name: str):
        super().__init__()
        self.job_id = job_id
        self.status = status
        self.display_name = display_name
        self._scroll_offset = 0
        self._scroll_timer = None
        self._pause_ticks = 0

    def compose(self) -> ComposeResult:
        yield Static(self._render_text(), id="job_label")

    def _render_text(self, offset: int = 0) -> str:
        badge = _STATUS_BADGES.get(self.status, _STATUS_BADGES[JobStatus.UNKNOWN])
        name = self.display_name
        if offset > 0:
            padded = name + "   " + name
            name = padded[offset:]
        return f"{badge} {name}"

    def watch_highlighted(self, value: bool) -> None:
        super().watch_highlighted(value)
        if value:
            self._scroll_offset = 0
            self._pause_ticks = 4
            self._scroll_timer = self.set_interval(0.35, self._scroll_tick)
        else:
            if self._scroll_timer:
                self._scroll_timer.stop()
                self._scroll_timer = None
            self._scroll_offset = 0
            try:
                self.query_one("#job_label", Static).update(self._render_text())
            except Exception:
                pass

    def _scroll_tick(self) -> None:
        try:
            label = self.query_one("#job_label", Static)
        except Exception:
            return
        available = label.size.width - _BADGE_WIDTH - 1
        if len(self.display_name) <= max(available, 0):
            return
        if self._pause_ticks > 0:
            self._pause_ticks -= 1
            return
        self._scroll_offset = (self._scroll_offset + 1) % (len(self.display_name) + 3)
        label.update(self._render_text(self._scroll_offset))

    def update_status(self, new_status: JobStatus):
        if self.status != new_status:
            self.status = new_status
            offset = self._scroll_offset if self.highlighted else 0
            self.query_one("#job_label", Static).update(self._render_text(offset))
