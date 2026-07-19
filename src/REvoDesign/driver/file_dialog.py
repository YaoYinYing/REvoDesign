# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only


"""
File Dialog
"""

import os
import shutil
import tarfile
import tempfile
import zipfile
from functools import partial
from typing import Any, Literal

from pymol.Qt.utils import getSaveFileNameWithExt

from ..basic import FileExtensionCollection, SingletonAbstract
from ..common import file_extensions
from ..logger import ROOT_LOGGER
from ..tools.customized_widgets import decide, getMultipleFiles, getOpenFileNameWithExt
from ..tools.utils import extract_archive
from .ui_driver import ConfigBus

IO_MODE = Literal["r", "w"]

logging = ROOT_LOGGER.getChild(__name__)

MAX_ARCHIVE_BROWSE_BYTES = 2 * 1024 * 1024 * 1024


class FileDialog(SingletonAbstract):
    """
    FileDialog class inherits from SingletonAbstract to implement a singleton pattern for file dialog functionality.
    This ensures that file dialog operations are centralized and shareable across different tabs.
    """

    def singleton_init(self, window: Any | None, pwd: str | None):
        """
        Initializes the singleton instance of FileDialog.

        Parameters:
        - window: Optional[Any] - The window object where the file dialog is displayed.
        - pwd: Optional[str] - The current working directory, if not provided, defaults to the system's
        current working directory.

        This method initializes the file dialog with the provided window and directory, registers file
        dialog buttons, and marks the instance as initialized.
        """
        self.window = window
        self.PWD = pwd or os.getcwd()
        self._archive_temp_dirs: set[str] = set()
        self.register_file_dialog_buttons()
        # Mark the instance as initialized to prevent reinitialization
        self.initialize()

    # class public function that can be shared with each tab
    # callback for the "Browse" button

    def browse_multiple_files(
        self, exts: tuple[FileExtensionCollection, ...] | None = (file_extensions.Any,)
    ) -> list[str]:
        return getMultipleFiles(self.window, exts)

    def browse_filename(
        self,
        mode: IO_MODE = "r",
        exts: tuple[FileExtensionCollection, ...] = (file_extensions.Any,),
        directory: str | None = None,
    ) -> str | None:
        """Open Finder/Explorer to browse from a filename

        Args:
            mode (IO_MODE, optional): mode to open this file. Defaults to 'r'.
            exts (tuple, optional): file extention group.
                Defaults to [FileExtentions.Any].

        Returns:
            str, optional: selected filename or None if canceled.
        """

        ext = FileExtensionCollection.squeeze(exts)

        filter_strings = ext.filter_string

        # refer a file path to write in
        if mode == "w":
            browse_title = "Save As..."
            filename = getSaveFileNameWithExt(self.window, browse_title, filter=filter_strings)
            return filename if filename else None

        # otherwise, open a file to read
        browse_title = "Open ..."
        filename = getOpenFileNameWithExt(
            self.window,
            browse_title,
            directory or "",
            filter=filter_strings,
        )

        # no file selected
        if not filename:
            return None

        # selected
        filename_bn = os.path.basename(filename)
        filename_ext = filename_bn.split(".")[-1]

        # Check if the selected file is a compressed archive
        # if not, return
        if filename_ext not in file_extensions.Compressed:
            return filename

        # if so, ask user whether to extract this compressed file
        confirmed = decide(
            title="Extract Archive",
            description=f"The selected file '{filename_bn}'" " is a compressed archive. Do you want to extract it?",
        )

        # if the answer is no
        if not confirmed:
            # Keep the previously selected filename and return it
            return filename

        # otherwise, extract the archive and browse the extracted file
        extracted_dir = flatten_compressed_files(filename)
        self._archive_temp_dirs.add(extracted_dir)
        return self.browse_filename(mode, exts=exts, directory=extracted_dir)

    # A universal and versatile function for input file path browsing.

    def open_file(
        self, cfg_item: str, exts: tuple[FileExtensionCollection, ...] = (file_extensions.Any,)
    ) -> str | None:
        """Open Any File

        Args:
            cfg_input (str): Configure item in ConfigBus
            exts (tuple, optional): File Extention(s).
                Defaults to (FileExtentions.Any,).

        Returns:
            str: filepath of opened file.
        """
        input_fn = self.browse_filename(mode="r", exts=exts)
        if input_fn:
            ConfigBus().set_widget_value(cfg_item, input_fn)
            return input_fn

    def open_mutant_table(self, cfg_mutant_table: str, mode: IO_MODE = "r"):
        """Open a mutant table file

        Args:
            cfg_mutant_table (str): Config item in ConfigBus
            mode (IO_MODE, optional): file operator mode. Defaults to 'r'.
        """
        if mode == "r":
            input_mut_txt_fn = self.open_file(
                cfg_mutant_table,
                (
                    file_extensions.Mutable,
                    file_extensions.Any,
                    file_extensions.Compressed,
                ),
            )
            if input_mut_txt_fn:
                ConfigBus().set_widget_value(cfg_mutant_table, input_mut_txt_fn)
                return

            logging.warning(f"Could not open file for reading: {input_mut_txt_fn}")
            return

        output_mut_txt_fn = self.browse_filename(
            mode=mode,
            exts=(
                file_extensions.Mutable,
                file_extensions.Any,
            ),
        )
        if output_mut_txt_fn and os.path.exists(os.path.dirname(output_mut_txt_fn)):
            logging.info(f"Output file is set as {output_mut_txt_fn}")
            ConfigBus().set_widget_value(cfg_mutant_table, output_mut_txt_fn)
            return

        logging.warning(f"Invalid output path: {output_mut_txt_fn}.")

    def register_file_dialog_buttons(self):
        bus = ConfigBus()
        bus.button("open_customized_indices").clicked.connect(
            partial(
                self.open_file,
                "ui.mutate.input.residue_ids",
                (file_extensions.TXT, file_extensions.Any),
            )
        )

        bus.button("open_input_csv").clicked.connect(
            partial(
                self.open_file,
                "ui.mutate.input.profile",
                (
                    file_extensions.PSSM,
                    file_extensions.Any,
                    file_extensions.Compressed,
                ),
            )
        )

        bus.button("open_input_csv_2").clicked.connect(
            partial(
                self.open_file,
                "ui.visualize.input.profile",
                (
                    file_extensions.PSSM,
                    file_extensions.Any,
                    file_extensions.Compressed,
                ),
            )
        )
        bus.button("open_gremlin_mtx").clicked.connect(
            partial(
                self.open_file,
                "ui.interact.input.gremlin_pkl",
                (
                    file_extensions.PickledObject,
                    file_extensions.Any,
                ),
            )
        )
        bus.button("open_mut_table_2").clicked.connect(
            partial(self.open_mutant_table, "ui.cluster.input.from_mutant_txt", "r")
        )
        bus.button("open_cluster_evo_pssm_profile").clicked.connect(
            partial(
                self.open_file,
                "ui.cluster.evo.inputs.pssm_profile",
                (
                    file_extensions.PSSM,
                    file_extensions.CSV,
                    file_extensions.Any,
                    file_extensions.Compressed,
                ),
            )
        )
        bus.button("open_cluster_evo_esm1v_table").clicked.connect(
            partial(
                self.open_file,
                "ui.cluster.evo.inputs.esm1v_table",
                (
                    file_extensions.CSV,
                    file_extensions.Any,
                    file_extensions.Compressed,
                ),
            )
        )
        bus.button("open_cluster_evo_structure_pdb").clicked.connect(
            partial(
                self.open_file,
                "ui.cluster.evo.inputs.structure_pdb",
                (
                    file_extensions.PDB,
                    file_extensions.Session,
                    file_extensions.Any,
                ),
            )
        )
        bus.button("open_mut_table_csv").clicked.connect(
            partial(
                self.open_mutant_table,
                "ui.visualize.input.from_mutant_txt",
                "r",
            )
        )
        bus.button("open_mut_table_csv_2").clicked.connect(
            partial(
                self.open_mutant_table,
                "ui.visualize.input.multi_design.to_mutant_txt",
                "w",
            )
        )
        bus.button("open_save_mutant_table").clicked.connect(
            partial(
                self.open_mutant_table,
                "ui.interact.input.to_mutant_txt",
                "w",
            )
        )
        bus.button("open_mut_table").clicked.connect(
            partial(self.open_mutant_table, "ui.evaluate.input.to_mutant_txt", "w")
        )

    def cleanup_archive_dirs(self) -> None:
        temp_dirs = getattr(self, "_archive_temp_dirs", set())
        for temp_dir in list(temp_dirs):
            shutil.rmtree(temp_dir, ignore_errors=True)
        temp_dirs.clear()

    def __del__(self):
        self.cleanup_archive_dirs()


def flatten_compressed_files(
    compressed_file: str,
    target_dir: str | None = None,
    max_archive_bytes: int = MAX_ARCHIVE_BROWSE_BYTES,
) -> str:
    """
    Flattens and extracts the contents of a compressed file.

    Parameters:
    - compressed_file (str): The path to the compressed file to be extracted.
    - target_dir (Optional[str]): Parent directory for the temporary extraction directory.
      If not provided, the system temporary directory is used.

    Returns:
    - str: The path to the directory where the files have been extracted.
    """

    archive_size = os.path.getsize(compressed_file)
    if archive_size > max_archive_bytes:
        raise ValueError(
            f"Archive is too large to browse safely: {archive_size} bytes " f"(limit: {max_archive_bytes} bytes)"
        )
    payload_size = _compressed_archive_payload_size(compressed_file)
    if payload_size > max_archive_bytes:
        raise ValueError(
            f"Archive expands too large to browse safely: {payload_size} bytes " f"(limit: {max_archive_bytes} bytes)"
        )

    # Create a path for the extracted files
    temp_parent = target_dir or tempfile.gettempdir()
    flatten_path = tempfile.mkdtemp(
        prefix=f"revodesign-{os.path.basename(compressed_file)}-",
        dir=temp_parent,
    )

    # Extract the archive to the specified directory
    try:
        extract_archive(archive_file=compressed_file, extract_to=flatten_path)
    except Exception:
        shutil.rmtree(flatten_path, ignore_errors=True)
        raise

    # Return the path to the extracted directory
    return flatten_path


def _compressed_archive_payload_size(compressed_file: str) -> int:
    if compressed_file.endswith(".zip"):
        with zipfile.ZipFile(compressed_file, "r") as zip_ref:
            return sum(info.file_size for info in zip_ref.infolist() if not info.is_dir())

    tar_suffixes = (".tar", ".tar.gz", ".tgz", ".tar.bz2", ".tbz", ".tar.xz")
    if compressed_file.endswith(tar_suffixes):
        with tarfile.open(compressed_file, "r:*") as tar_ref:
            return sum(member.size for member in tar_ref.getmembers() if member.isfile())

    return os.path.getsize(compressed_file)
