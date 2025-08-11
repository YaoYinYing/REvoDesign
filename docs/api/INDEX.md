# REvoDesign API Reference

- REvoDesign
  - REvoDesignPlugin
  - ConfigBus
  - file_extensions
  - ROOT_LOGGER, setup_logging
  - experiment_config, reload_config_file, save_configuration, set_cache_dir, set_REvoDesign_config_file, REVODESIGN_CONFIG_FILE
  - all_shortcuts

- basic
  - SingletonAbstract
  - ThirdPartyModuleAbstract, TorchModuleAbstract
  - IterableLoop
  - MutateRunnerAbstract
  - ExternalDesignerAbstract
  - FileExtension, FileExtensionCollection
  - GroupRegistryItem
  - ParamChangeRegistryItem, ParamChangeRegister
  - MenuItem, MenuCollection
  - MenuActionServerMonitor, ServerControlAbstract

- driver
  - ConfigBus, StoresWidget

- structure
  - SurfaceFinder
  - PocketSearcher

- sidechain
  - SidechainSolver
  - MutateRunnerAbstract
  - PyMOL_mutate, DLPacker_worker, PIPPack_worker

- magician
  - ExternalDesignerAbstract
  - ColabDesigner_MPNN, ddg

- shortcuts
  - shortcut_pssm2csv, shortcut_real_sc, shortcut_color_by_plddt,
    shortcut_find_interface, shortcut_color_by_mutation,
    shortcut_dump_sidechains, visualize_conformer_sdf

- tools
  - utils: run_command, run_worker_thread_with_progress, timing, generate_strong_password, random_deduplicate,
    minibatches, minibatches_generator, extract_archive, get_color, cmap_reverser, rescale_number,
    count_and_sort_characters, device_picker, pairwise
  - customized_widgets: notify_box, decide, refresh_window, set_widget_value, ImageWidget,
    hold_trigger_button, getExistingDirectory, WorkerThread, ValueDialog, AskedValueCollection,
    AppendableValueDialog, ask_for_appendable_values

- common
  - file_extensions: Session, Mutable, PDB, PDB_STRICT, MOL, SDF, PSSM, CSV, MSA, A3M, TXT, Any, Compressed,
    PickledObject, YAML, JSON, RosettaParams, Pictures

- Qt
  - QtCore, QtGui, QtWidgets, QtSource

See per-module pages in this folder for signatures, descriptions, and examples.