import unittest
from unittest.mock import patch

from nqi.cli import ensure_default_nqdir, exec_nq_tool, main


class CLITests(unittest.TestCase):
    def test_ensure_default_nqdir_sets_when_missing(self):
        with patch.dict("nqi.cli.os.environ", {}, clear=True), \
             patch("nqi.cli.os.makedirs") as mocked_makedirs:
            ensure_default_nqdir()
            self.assertIn("NQDIR", __import__("os").environ)
            mocked_makedirs.assert_called_once()

    def test_exec_nq_tool_uses_execvp_for_path_lookup(self):
        with patch("nqi.cli.get_binary_path", return_value="nq"), \
             patch("nqi.cli.os.execvp", side_effect=OSError("boom")) as mocked_execvp:
            code = exec_nq_tool("nq", ["echo", "hello"])
        mocked_execvp.assert_called_once_with("nq", ["nq", "echo", "hello"])
        self.assertEqual(code, 127)

    def test_main_dispatches_subcommand_style(self):
        with patch("nqi.cli.ensure_default_nqdir"), \
             patch("nqi.cli.exec_nq_tool", return_value=0) as mocked_exec, \
             patch("nqi.cli.sys.argv", ["nqi", "nqtail", "-f"]):
            code = main()
        mocked_exec.assert_called_once_with("nqtail", ["-f"])
        self.assertEqual(code, 0)

    def test_main_nqi_forwards_command_to_nq(self):
        with patch("nqi.cli.ensure_default_nqdir"), \
             patch("nqi.cli.exec_nq_tool", return_value=0) as mocked_exec, \
             patch("nqi.cli.sys.argv", ["nqi", "echo", "hello"]):
            code = main()
        mocked_exec.assert_called_once_with("nq", ["echo", "hello"])
        self.assertEqual(code, 0)

    def test_main_nqi_dash_f_calls_nqtail(self):
        with patch("nqi.cli.ensure_default_nqdir"), \
             patch("nqi.cli.exec_nq_tool", return_value=0) as mocked_exec, \
             patch("nqi.cli.sys.argv", ["nqi", "-f"]):
            code = main()
        mocked_exec.assert_called_once_with("nqtail", [])
        self.assertEqual(code, 0)

    def test_main_nqi_dash_t_calls_nqterm(self):
        with patch("nqi.cli.ensure_default_nqdir"), \
             patch("nqi.cli.exec_nq_tool", return_value=0) as mocked_exec, \
             patch("nqi.cli.sys.argv", ["nqi", "-t"]):
            code = main()
        mocked_exec.assert_called_once_with("nqterm", [])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
