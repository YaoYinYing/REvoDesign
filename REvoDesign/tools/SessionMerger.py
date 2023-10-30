import os

from shutil import rmtree
from pymol import cmd


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
        # pymol.cmd.do(f'save {self.save_path}')
        cmd.refresh()
        cmd.save(self.save_path, quiet=self.quiet)
        print('Done.')
