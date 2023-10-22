import argparse, os
from shutil import rmtree
from pymol import cmd


def merge_sessions(session_paths, save_path=None, mode=1, delete=0, quiet=0):
    # this is important! we need to cleanup the session to prevent segmentation fault error!
    cmd.reinitialize()

    for session_path in session_paths:
        print(f"Loading session: {session_path}")
        cmd.load(session_path, partial=mode, quiet=quiet)
        # delete it after loading
        if delete:
            rmtree(os.path.dirname(session_path))

    if save_path:
        print(f"Saving merged session: {save_path}")
        cmd.save(save_path, quiet=quiet)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Merge multiple PyMOL sessions."
    )
    parser.add_argument(
        "sessions", nargs="+", help="List of PyMOL session paths to merge."
    )
    parser.add_argument(
        "-s",
        "--save",
        metavar="output_path",
        help="Path to save the merged session.",
    )

    args = parser.parse_args()
    merge_sessions(args.sessions, args.save, mode=2, quiet=0)
