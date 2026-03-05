import os
import tempfile
import unittest
from types import SimpleNamespace
from unittest.mock import Mock, patch

from nqy.app import NQY
from nqy.logic import JobStatus


class AppActionTests(unittest.TestCase):
    def test_action_restart_job_reenqueues_command(self):
        app = NQY()
        app.nq_dir = "/tmp/nq"
        app.selected_job = ",abc.123"
        app.refresh_jobs = Mock()

        with patch("nqy.app.get_job_command", return_value=["echo", "ok"]), \
             patch("nqy.app.run_nq_cmd") as mocked_run:
            app.action_restart_job()

        mocked_run.assert_called_once_with(["echo", "ok"])
        app.refresh_jobs.assert_called_once()

    def test_action_copy_log_notifies_on_read_error(self):
        app = NQY()
        app.selected_job = ",abc.123"
        app.nq_dir = "/tmp/nq"
        app.notify = Mock()

        with patch("builtins.open", side_effect=OSError("boom")):
            app.action_copy_log()

        app.notify.assert_called_once_with("Failed to read log file.", severity="error")

    def test_action_delete_job_skips_finished_jobs(self):
        app = NQY()
        app.selected_job = ",abc.123"
        app.nq_dir = "/tmp/nq"
        app._require_confirmation = Mock()

        with patch("nqy.app.get_job_status", return_value=JobStatus.FINISHED):
            app.action_delete_job()

        app._require_confirmation.assert_not_called()

    def test_action_delete_job_calls_kill_on_confirmed_active_job(self):
        app = NQY()
        app.selected_job = ",abc.123"
        app.nq_dir = "/tmp/nq"
        app._target_index = None
        app.refresh_jobs = Mock()
        app.query_one = Mock(return_value=SimpleNamespace(index=4))

        captured = {}

        def capture_confirmation(_name, _message, callback):
            captured["callback"] = callback

        app._require_confirmation = capture_confirmation

        with patch("nqy.app.get_job_status", return_value=JobStatus.QUEUED), \
             patch("nqy.app.kill_job", return_value=True) as mocked_kill:
            app.action_delete_job()
            self.assertIn("callback", captured)
            captured["callback"]()

        mocked_kill.assert_called_once_with(",abc.123", "/tmp/nq")
        self.assertEqual(app._target_index, 4)
        app.refresh_jobs.assert_called_once()


if __name__ == "__main__":
    unittest.main()
