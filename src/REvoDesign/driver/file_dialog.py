import os
from functools import partial
from typing import Any, List, Literal, Optional
from pymol.Qt.utils import getSaveFileNameWithExt
from ..basic import FileExtensionCollection, SingletonAbstract
from ..common import file_extensions
from ..logger import ROOT_LOGGER
from ..tools.customized_widgets import (decide, getMultipleFiles,
                                        getOpenFileNameWithExt)
from ..tools.utils import extract_archive
from .ui_driver import ConfigBus
IO_MODE = Literal["r", "w"]
logging = ROOT_LOGGER.getChild(__name__)
class FileDialog(SingletonAbstract):
    def singleton_init(self, window: Optional[Any], pwd: Optional[str]):
        self.window = window
        self.PWD = pwd or os.getcwd()
        self.register_file_dialog_buttons()
        self.initialize()
    def browse_multiple_files(self, exts: Optional[tuple[FileExtensionCollection, ...]] = (file_extensions.Any,)
                              ) -> List[str]:
        return getMultipleFiles(self.window, exts)
    def browse_filename(
        self, mode: IO_MODE = "r", exts: tuple[FileExtensionCollection, ...] = (file_extensions.Any,)
    ) -> Optional[str]:
        ext = FileExtensionCollection.squeeze(exts)
        filter_strings = ext.filter_string
        if mode == "w":
            browse_title = "Save As..."
            filename = getSaveFileNameWithExt(
                self.window, browse_title, filter=filter_strings
            )
            return filename if filename else None
        browse_title = "Open ..."
        filename = getOpenFileNameWithExt(
            self.window, browse_title, filter=filter_strings
        )
        if not filename:
            return None
        filename_bn = os.path.basename(filename)
        filename_ext = filename_bn.split(".")[-1]
        if filename_ext not in file_extensions.Compressed:
            return filename
        confirmed = decide(
            title="Extract Archive",
            description=f"The selected file '{filename_bn}'"
            " is a compressed archive. Do you want to extract it?",
        )
        if not confirmed:
            return filename
        flatten_compressed_files(filename, self.PWD)
        return self.browse_filename(mode, exts=exts)
    def open_file(self, cfg_item: str, exts: tuple[FileExtensionCollection, ...] = (
            file_extensions.Any,)) -> Optional[str]:
        input_fn = self.browse_filename(mode="r", exts=exts)
        if input_fn:
            ConfigBus().set_widget_value(cfg_item, input_fn)
            return input_fn
    def open_mutant_table(self, cfg_mutant_table: str, mode: IO_MODE = "r"):
        if mode == "r":
            input_mut_txt_fn = self.open_file(
                cfg_mutant_table,
                (file_extensions.Mutable,
                    file_extensions.Any,
                    file_extensions.Compressed,),
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
                file_extensions.Mutable,
                file_extensions.Any,
            ),
        )
        if output_mut_txt_fn and os.path.exists(
            os.path.dirname(output_mut_txt_fn)
        ):
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
                (file_extensions.PSSM,
                    file_extensions.Any,
                    file_extensions.Compressed,)
            )
        )
        bus.button("open_input_csv_2").clicked.connect(
            partial(
                self.open_file,
                "ui.visualize.input.profile",
                (file_extensions.PSSM,
                    file_extensions.Any,
                    file_extensions.Compressed,),
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
    if target_dir is None:
        target_dir = os.getcwd()
    flatten_path = os.path.join(
        target_dir,
        "expanded_compressed_files",
        os.path.basename(compressed_file),
    )
    os.makedirs(flatten_path, exist_ok=True)
    extract_archive(archive_file=compressed_file, extract_to=flatten_path)
    return flatten_path