
'''
File Dialog
'''
from functools import partial
import os
from typing import Any, Literal, Optional


from pymol.Qt.utils import getSaveFileNameWithExt

from .ui_driver import ConfigBus
from ..tools.utils import extract_archive
from ..logger import root_logger

from ..common import FileExtentions
from ..basic import SingletonAbstract,FileExtensionCollection

from ..tools.customized_widgets import decide, getOpenFileNameWithExt

IO_MODE = Literal["r", "w"]

logging=root_logger.getChild(__name__)

class FileDialog(SingletonAbstract):
    def __init__(self, window:Optional[Any], pwd: Optional[str]):
        # Check if the instance has already been initialized
        if not hasattr(self, "initialized"):
            self.window=window
            self.PWD=pwd if pwd is not None else os.getcwd()
            self.register_file_dialof_buttons()
            # Mark the instance as initialized to prevent reinitialization
            self.initialize()
            self.initialized = True

    
    
    # class public function that can be shared with each tab
    # callback for the "Browse" button
    def browse_filename(
        self, mode: IO_MODE = "r", exts: tuple[FileExtensionCollection,...] = (FileExtentions.Any,)
    ) -> Optional[str]:
        """Open Finder/Explorer to browse from a filename

        Args:
            mode (IO_MODE, optional): mode to open this file. Defaults to 'r'.
            exts (tuple, optional): file extention group.
                Defaults to [FileExtentions.Any].

        Returns:
            str, optional: selected filename or None if canceled. 
        """

        ext=FileExtensionCollection.squeeze(exts)

        filter_strings = ext.filter_string

        if mode == "w":
            browse_title = "Save As..."
            filename = getSaveFileNameWithExt(
                self.window, browse_title, filter=filter_strings
            )
        else:
            browse_title = "Open ..."
            filename = getOpenFileNameWithExt(
                self.window, browse_title, filter=filter_strings
            )

            filename_bn = os.path.basename(filename)
            filename_ext=filename_bn.split(".")[-1]

            # Check if the selected file is a compressed archive
            is_compressed = filename_ext in FileExtentions.Compressed
            if is_compressed:
                # Ask whether to overide
                confirmed = decide(
                    title="Extract Archive",
                    description=f"The selected file '{filename_bn}'"
                    " is a compressed archive. Do you want to extract it?",
                )

                if confirmed:
                    # Extract the archive and browse the extracted file
                    flatten_compressed_files(filename, self.PWD)
                    return self.browse_filename(mode, exts=exts)
                else:
                    # Keep the previously selected filename and return it
                    return filename

        if filename:
            return filename
        
    
    # A universal and versatile function for input file path browsing.
    def open_file(self, cfg_item: str, exts: tuple[FileExtensionCollection,...] = (FileExtentions.Any,)) -> Optional[str]:
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
                (FileExtentions.Mutable,
                    FileExtentions.Any,
                    FileExtentions.Compressed,),
            )
            if input_mut_txt_fn:
                ConfigBus().set_widget_value(cfg_mutant_table, input_mut_txt_fn)
                return
            
            logging.warning(
                f"Could not open file for reading: {input_mut_txt_fn}"
            )
            return
                

        output_mut_txt_fn = self.browse_filename(
            mode=mode,
            exts=(
                FileExtentions.Mutable,
                FileExtentions.Any,
            ),
        )
        if output_mut_txt_fn and os.path.exists(
            os.path.dirname(output_mut_txt_fn)
        ):
            logging.info(f"Output file is set as {output_mut_txt_fn}")
            ConfigBus().set_widget_value(cfg_mutant_table, output_mut_txt_fn)
            return
        
        logging.warning(f"Invalid output path: {output_mut_txt_fn}.")

            
    def register_file_dialof_buttons(self):
        bus=ConfigBus()
        bus.button("open_customized_indices").clicked.connect(
            partial(
                self.open_file,
                "ui.mutate.input.residue_ids",
                (FileExtentions.TXT, FileExtentions.Any),
            )
        )

        bus.button("open_input_csv").clicked.connect(
            partial(
                self.open_file,
                "ui.mutate.input.profile",
                (FileExtentions.PSSM,
                    FileExtentions.Any,
                    FileExtentions.Compressed,)
            )
        )

        bus.button("open_input_csv_2").clicked.connect(
            partial(
                self.open_file,
                "ui.visualize.input.profile",
                (FileExtentions.PSSM,
                    FileExtentions.Any,
                    FileExtentions.Compressed,),
            )
        )
        bus.button("open_gremlin_mtx").clicked.connect(
            partial(
                self.open_file,
                "ui.interact.input.gremlin_pkl",
                (
                    FileExtentions.PickledObject,
                    FileExtentions.Any,
                ),
            )
        )
        bus.button("open_mut_table_2").clicked.connect(
            partial(
                self.open_mutant_table, "ui.cluster.input.from_mutant_txt", "r"
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
            partial(
                self.open_mutant_table, "ui.evaluate.input.to_mutant_txt", "w"
            )
        )


def flatten_compressed_files(compressed_file: str, target_dir: Optional[str] = None) -> str:
    """
    Flattens and extracts the contents of a compressed file.

    Parameters:
    - compressed_file (str): The path to the compressed file to be extracted.
    - target_dir (Optional[str]): The directory where the extracted files will be placed. 
      If not provided, the current working directory is used.

    Returns:
    - str: The path to the directory where the files have been extracted.
    """

    # Set the target directory to the current working directory if not specified
    if target_dir is None:
        target_dir = os.getcwd()

    # Create a path for the extracted files
    flatten_path = os.path.join(
        target_dir,
        "expanded_compressed_files",
        os.path.basename(compressed_file),
    )

    # Create the directory if it does not exist
    os.makedirs(flatten_path, exist_ok=True)

    # Extract the archive to the specified directory
    extract_archive(archive_file=compressed_file, extract_to=flatten_path)

    # Return the path to the extracted directory
    return flatten_path

