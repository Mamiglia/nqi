import os
import tempfile
import unittest
from unittest.mock import patch

import fcntl

from nqy.logic import JobStatus, kill_job, swap_jobs


class LogicTests(unittest.TestCase):
    def test_kill_job_refuses_finished_job_in_nq_dir(self):
        with tempfile.TemporaryDirectory() as td:
            job_id = ",abc.12345"
            path = os.path.join(td, job_id)
            with open(path, "w", encoding="utf-8") as f:
                f.write("exec sleep 10\n")

            with patch("nqy.logic.os.kill") as mocked_kill:
                self.assertFalse(kill_job(job_id, td))
                mocked_kill.assert_not_called()

    def test_kill_job_allows_queued_job_in_nq_dir(self):
        with tempfile.TemporaryDirectory() as td:
            job_id = ",abc.23456"
            path = os.path.join(td, job_id)
            with open(path, "w", encoding="utf-8") as f:
                f.write("exec sleep 10\n")

            lock_file = open(path, "r", encoding="utf-8")
            try:
                fcntl.flock(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
                os.chmod(path, 0o644)  # not executable => QUEUED

                with patch("nqy.logic.os.kill") as mocked_kill:
                    self.assertTrue(kill_job(job_id, td))
                    mocked_kill.assert_called_once_with(23456, unittest.mock.ANY)
            finally:
                fcntl.flock(lock_file, fcntl.LOCK_UN)
                lock_file.close()

    def test_swap_jobs_reenqueues_in_swapped_order(self):
        current_files = [",003.300", ",002.200", ",001.100"]
        commands = {
            ",002.200": ["echo", "second"],
            ",001.100": ["echo", "first"],
        }
        reenqueued = []

        def fake_status(_path):
            return JobStatus.QUEUED

        def fake_get_cmd(path):
            return commands.get(os.path.basename(path))

        with patch("nqy.logic.get_job_status", side_effect=fake_status), \
             patch("nqy.logic.get_job_command", side_effect=fake_get_cmd), \
             patch("nqy.logic.kill_job", return_value=True), \
             patch("nqy.logic.os.remove"), \
             patch("nqy.logic.run_nq_cmd", side_effect=lambda args: reenqueued.append(args)), \
             patch("nqy.logic.time.sleep"):
            swap_jobs("/tmp/nq", ",002.200", ",001.100", current_files)

        self.assertEqual(reenqueued, [["echo", "first"], ["echo", "second"]])


if __name__ == "__main__":
    unittest.main()
