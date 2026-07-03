# Tools

Utility modules providing reusable functionality across REvoDesign.

## General Utilities (`REvoDesign.tools.utils`)

Orphaned but widely used utility functions for configuration resolution, color mapping, archiving, device detection, and function inspection.

### Key Functions

::: REvoDesign.tools.utils.run_command
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.run_worker_thread_in_pool
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.resolve_dotted_expression
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.resolve_dotted_function
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.resolve_lambda_expression
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.resolve_dotted_config_item
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.get_color
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.cmap_reverser
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.rescale_number
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.timing
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.require_not_none
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.require_installed
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.get_cited
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.inspect_method_types
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.minibatches
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.minibatches_generator
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.extract_archive
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.device_picker
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.pairwise_loop
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.count_and_sort_characters
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.generate_strong_password
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.random_deduplicate
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.convert_residue_ranges
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.utils.xvg2df
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

## Mutant Tools (`REvoDesign.tools.mutant_tools`)

Functions for parsing, manipulating, and extracting mutation data from strings, PyMOL objects, and files.

### Key Functions

::: REvoDesign.tools.mutant_tools.aa3_to_aa1
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.mutant_tools.extract_mutants_from_mutant_id
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.mutant_tools.extract_mutant_score_from_string
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.mutant_tools.extract_mutant_from_sequences
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.mutant_tools.extract_mutant_from_pymol_object
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.mutant_tools.shorter_range
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.mutant_tools.expand_range
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.mutant_tools.read_customized_indice
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.mutant_tools.existed_mutant_tree
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.mutant_tools.quick_mutagenesis
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.mutant_tools.save_mutant_choices
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.mutant_tools.write_input_mutant_table
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.mutant_tools.determine_profile_type
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.mutant_tools.get_mutant_table_columns
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.mutant_tools.pick_design_from_profile
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.mutant_tools.process_mutations
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

## PyMOL Utilities (`REvoDesign.tools.pymol_utils`)

Molecule-level utilities wrapping the PyMOL `cmd` API for session management, residue analysis, and structure manipulation.

### Key Functions

::: REvoDesign.tools.pymol_utils.is_empty_session
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.is_hidden_object
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.is_polymer_protein
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.find_small_molecules_in_protein
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.find_design_molecules
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.find_all_protein_chain_ids_in_protein
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.is_distal_residue_pair
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.renumber_chain_ids
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.get_molecule_sequence
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.get_atom_pair_cst
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.autogrid_flexible_residue
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.refresh_all_selections
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.is_a_REvoDesign_session
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.make_temperal_input_pdb
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.extract_smiles_from_chain
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.renumber_protein_chain
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.get_pymol_settings
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.list_palettes
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.exists
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.pymol_utils.load_safely
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

### Data Classes

::: REvoDesign.tools.pymol_utils.PyMOLSetting
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## Measurement Utilities (`REvoDesign.tools.measure_utils`)

Reads PyMOL measurement objects (distance, angle, dihedral) from the session and produces Gromacs index input strings. Handles PyMOL's internal `ObjectDist`/`DistSet` data structures.

### Classes

::: REvoDesign.tools.measure_utils.MeasureType
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.measure_utils.AtomDescriptor
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.measure_utils.MeasureInfo
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.measure_utils.DistSet
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.measure_utils.Measurement
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### Functions

::: REvoDesign.tools.measure_utils.build_scene_atom_list
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.measure_utils.build_unique_id_map
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.measure_utils.read_measurement
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

## Download Registry (`REvoDesign.tools.download_registry`)

Manages automatic downloading, verification, and caching of remote file resources using the Pooch library. Supports retry mechanisms, alternative URLs, and hash-based verification.

::: REvoDesign.tools.download_registry.FileDownloadRegistry
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.download_registry.DownloadedFile
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## Rosetta Utilities (`REvoDesign.tools.rosetta_utils`)

Environment detection and configuration helpers for integrating with the Rosetta molecular modeling suite.

### Key Functions

::: REvoDesign.tools.rosetta_utils.setup_minimal_rosetta_db
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.rosetta_utils.list_fastrelax_scripts
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.rosetta_utils.extra_res_to_opts
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.rosetta_utils.is_run_node_available
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.rosetta_utils.is_docker_available
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.rosetta_utils.is_wsl_available
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.rosetta_utils.is_rosetta_runnable
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.rosetta_utils.read_rosetta_config
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.rosetta_utils.read_rosetta_node_config
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.rosetta_utils.copy_rosetta_citation
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

## System Tools (`REvoDesign.tools.system_tools`)

System information collection and environment detection.

::: REvoDesign.tools.system_tools.check_mac_rosetta2
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.system_tools.SystemInfoReduced
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.system_tools.get_client_info
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

## CGO Utilities (`REvoDesign.tools.cgo_utils`)

Compiled Graphics Objects (CGO) helpers for programmatic PyMOL rendering. Provides a geometric primitive library — points, spheres, cylinders, cones, arrows, curves (Bezier, Catmull-Rom, B-Spline, Hermite, NURBS), tori, polyhedra, text boards — built on `pymol.cgo`.

### Key Classes

::: REvoDesign.tools.cgo_utils.Point
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.cgo_utils.Color
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.cgo_utils.GraphicObject
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.cgo_utils.Sphere
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.cgo_utils.Cylinder
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.cgo_utils.Cone
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.cgo_utils.Arrow
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.cgo_utils.TextBoard
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

Additional primitive classes: `LineVertex`, `Sausage`, `Doughnut`, `Triangle`, `TriangleSimple`, `Cube`, `Square`, `PolyLines`, `RoundedRectangle`, `Ellipse`, `Ellipsoid`, `Polygon`, `Polyhedron`.

Curve classes: `PseudoCurve`, `PseudoBezier`, `PseudoCatmullRom`, `PseudoBSpline`, `PseudoHermite`, `PseudoArc`, `PseudoNURBS`.

## Custom Widgets (`REvoDesign.tools.customized_widgets`)

Custom Qt widgets and dialogs used throughout the REvoDesign UI.

### Key Classes

::: REvoDesign.tools.customized_widgets.REvoDesignWidget
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.customized_widgets.ImageWidget
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.customized_widgets.QButtonMatrix
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.customized_widgets.QButtonMatrixGremlin
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.customized_widgets.QHoverCross
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.customized_widgets.ButtonCoords
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.customized_widgets.QButtonBrick
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.customized_widgets.MultiCheckableComboBox
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.customized_widgets.ValueDialog
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.customized_widgets.ParallelExecutor
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.customized_widgets.QtParallelExecutor
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.customized_widgets.AskedValue
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.customized_widgets.AskedValueCollection
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.customized_widgets.dialog_wrapper
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.customized_widgets.widget_signal_tape
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.customized_widgets.create_cmap_icon
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.tools.customized_widgets.pick_color
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

## Package Manager (`REvoDesign.tools.package_manager`)

Thread management, process tracking, and background task execution infrastructure. See `README.thread-management.md` for the full design document.

### Key Classes

::: REvoDesign.tools.package_manager.WorkerThread
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.package_manager.ThreadExecutionManager
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.package_manager.ThreadPoolRegistry
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.package_manager.RunningProcessRegistry
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.package_manager.ThreadDashboard
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.package_manager.AbortButtonOverlay
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

::: REvoDesign.tools.package_manager.REvoDesignPackageManager
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

## Session Merger (`REvoDesign.tools.SessionMerger`)

Command-line tool for merging multiple PyMOL session files into a single session.

::: REvoDesign.tools.SessionMerger
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3
