import os

from shutil import rmtree
from pymol import cmd
import argparse


class PyMOLSessionMerger:
    def __init__(self, session_paths, save_path):
        self.session_paths = session_paths
        self.save_path = save_path
        self.mode = 1
        self.delete = False
        self.quiet = False

    def add_session_path(self, session_path):
        self.session_paths.append(session_path)

    def merge_sessions(self):
        cmd.reinitialize()
        for session_path in self.session_paths:
            print(f"Loading session: {session_path}")
            cmd.load(
                session_path, partial=self.mode, quiet=self.quiet
            )

            if self.delete:
                rmtree(os.path.dirname(session_path))

        print(f"Saving merged session: {self.save_path}")
        cmd.save(self.save_path, quiet=self.quiet)
        print('Done.')

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Merge PyMOL sessions.')
    parser.add_argument('session_paths', nargs='+', help='Paths to PyMOL sessions to be merged.')
    parser.add_argument('--save_path', required=True, help='Path to save the merged session.')
    parser.add_argument('--mode', type=int, default=1, help='Loading mode (default: 1).')
    parser.add_argument('--delete', action='store_true', help='Delete session files after loading.')
    parser.add_argument('--quiet', action='store_true', help='Run in quiet mode.')

    args = parser.parse_args()

    merger = PyMOLSessionMerger(args.session_paths, args.save_path)
    merger.mode = args.mode
    merger.delete = args.delete
    merger.quiet = args.quiet

    merger.merge_sessions()