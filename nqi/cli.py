import os
import sys

from .logic import get_binary_path


NQ_TOOLS = {"nq", "nqtail", "nqterm"}


def ensure_default_nqdir() -> None:
    """Use a persistent per-user queue dir unless caller provided NQDIR."""
    if "NQDIR" in os.environ:
        return
    nq_dir = os.path.expanduser("~/.local/share/nq")
    os.makedirs(nq_dir, exist_ok=True)
    os.environ["NQDIR"] = nq_dir


def exec_nq_tool(tool_name: str, args: list[str]) -> int:
    """Exec the requested nq utility, preferring bundled binaries."""
    tool_path = get_binary_path(tool_name)
    
    # Add the bundled binary directory to the PATH so that the tools
    # can find each other (e.g., nqterm calling nq/nqtail).
    if os.path.sep in tool_path:
        bin_dir = os.path.dirname(tool_path)
        current_path = os.environ.get("PATH", "")
        if bin_dir not in current_path.split(os.pathsep):
            os.environ["PATH"] = f"{bin_dir}{os.pathsep}{current_path}"
            
    argv = [tool_name, *args]
    try:
        if os.path.sep in tool_path:
            os.execv(tool_path, argv)
        os.execvp(tool_path, argv)
    except OSError as exc:
        print(f"Failed to execute {tool_name}: {exc}", file=sys.stderr)
        return 127
    return 0


def main() -> int:
    ensure_default_nqdir()

    program = os.path.basename(sys.argv[0])
    if program.endswith(".py"):
        program = program[:-3]
    args = sys.argv[1:]

    # If the program name matches an nq tool exactly, behave as that tool.
    # This allows symlinking nq -> nqi, nqtail -> nqi, etc.
    if program in NQ_TOOLS:
        return exec_nq_tool(program, args)

    # Explicit subcommand style: `nqi nq ...`
    if args and args[0] in NQ_TOOLS:
        return exec_nq_tool(args[0], args[1:])

    # Help handling
    if args and (args[0] == "--help" or args[0] == "-h"):
        print("Usage: nqi [nq-command...]")
        print("       nqi -f [nqtail-command...]")
        print("       nqi -t [nqterm-command...]")
        print("       nqi (no arguments) for the TUI")
        print("\nSubcommands:")
        print("  nq, nqtail, nqterm  Direct access to nq utilities")
        return 0

    # Default nqi behavior:
    # nqi -f => nqtail
    if args and args[0] == "-f":
        return exec_nq_tool("nqtail", args[1:])
    # nqi -t => nqterm
    if args and args[0] == "-t":
        return exec_nq_tool("nqterm", args[1:])

    # nqi <cmd...> behaves like nq <cmd...>
    if args:
        return exec_nq_tool("nq", args)

    # No arguments => UI
    from .app import main as app_main
    app_main()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())