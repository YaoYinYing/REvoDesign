import os
from pymol import cmd
import argparse
from REvoDesign.tools.logger import python_logging as logger
logging=logger.getChild(__name__)

class PyMOLSessionMerger:
    """
    Class: PyMOLSessionMerger
    Usage:
    - Initialize: merger = PyMOLSessionMerger(session_paths, save_path)
    - Add Session Path: merger.add_session_path(session_path)
    - Merge Sessions: merger.merge_sessions()

    This class facilitates merging PyMOL sessions by loading multiple sessions and saving the merged session.

    Attributes:
    - session_paths (list): List of paths to PyMOL session files
    - save_path (str): Path to save the merged PyMOL session
    - mode (int): Partial or full loading mode (default is 1)
    - delete (bool): Whether to delete loaded sessions after merging (default is False)
    - quiet (bool): Whether to suppress informational messages during loading and saving (default is False)

    Methods:
    - add_session_path(session_path): Adds a session path to the list of session_paths.
    - merge_sessions(): Merges the PyMOL sessions by loading and saving according to provided attributes.
    """

    def __init__(self, session_paths, save_path):
        self.session_paths = session_paths
        self.save_path = save_path
        self.mode = 1
        self.delete = False
        self.quiet = False

    def add_session_path(self, session_path):
        """
        Method: add_session_path
        Usage: merger.add_session_path(session_path)

        Adds a session path to the list of session_paths.

        Args:
        - session_path (str): Path to a PyMOL session file

        Returns:
        - None
        """
        self.session_paths.append(session_path)

    def merge_sessions(self):
        """
        Method: merge_sessions
        Usage: merger.merge_sessions()

        Merges the PyMOL sessions by loading and saving according to the provided attributes.

        Returns:
        - None
        """
        cmd.reinitialize()
        for session_path in self.session_paths:
            logging.info(f"Loading session: {session_path}")
            cmd.load(session_path, partial=self.mode, quiet=self.quiet)

            if self.delete:
                os.remove(session_path)

        print(f"Saving merged session: {self.save_path}")
        cmd.save(self.save_path, quiet=self.quiet)
        print('Done.')


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Merge PyMOL sessions.')
    parser.add_argument(
        'session_paths',
        nargs='+',
        help='Paths to PyMOL sessions to be merged.',
    )
    parser.add_argument(
        '--save_path', required=True, help='Path to save the merged session.'
    )
    parser.add_argument(
        '--mode', type=int, default=1, help='Loading mode (default: 1).'
    )
    parser.add_argument(
        '--delete',
        action='store_true',
        help='Delete session files after loading.',
    )
    parser.add_argument(
        '--quiet', action='store_true', help='Run in quiet mode.'
    )

    args = parser.parse_args()

    merger = PyMOLSessionMerger(args.session_paths, args.save_path)
    merger.mode = args.mode
    merger.delete = args.delete
    merger.quiet = args.quiet

    merger.merge_sessions()
