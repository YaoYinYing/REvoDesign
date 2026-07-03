# Structure

Protein structure analysis tools for surface residue identification and binding pocket detection. These are used by the Prepare tab to define the designable region on a protein target.

## SurfaceFinder

Identifies surface-exposed residues on a protein structure using solvent-accessible surface area (SASA) calculations. Wraps and extends the PyMOLwiki `findSurfaceResidues` algorithm. Used by the Prepare tab to determine which residues are accessible for mutagenesis design.

### Workflow

1. Loads the input PyMOL session
2. Calculates per-atom solvent-accessible surface area using PyMOL's `get_area` with `dot_solvent=1`
3. Filters atoms with exposed surface area above a configurable cutoff (default 15.0 A^2)
4. Creates PyMOL selections for exposed residues (`er_ca`) and non-exposed residues (`ner_ca`)
5. Stores visual scenes at different zoom levels
6. Saves residue ID lists to `surface_residue_records/` directory
7. Saves the prepared session to the configured output path

::: REvoDesign.structure.SurfaceFinder.SurfaceFinder
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3

### Standalone Functions

::: REvoDesign.structure.SurfaceFinder.findSurfaceAtoms
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

::: REvoDesign.structure.SurfaceFinder.findSurfaceResidues
    options:
      show_root_heading: true
      show_source: false
      heading_level: 4

## PocketSearcher

Detects and characterizes binding pockets around a ligand or cofactor in a protein structure. Creates PyMOL selections representing pocket residues at configurable radii around the ligand. Used by the Prepare tab to define the designable region around the active site.

### Workflow

1. Loads the input PyMOL session
2. Processes ligand and cofactor residue name strings
3. Creates three pocket selections:
   - **Hetatm pocket**: All heteroatoms within `ligand_radius` of the protein
   - **Substrate pocket**: Polymer protein residues within `ligand_radius` of the specified ligand
   - **Design shell**: The substrate pocket (optionally excluding cofactor pocket)
4. Optionally creates a **cofactor pocket** selection if a cofactor is specified
5. Saves residue ID lists to the `save_dir` directory for each selection
6. Saves the prepared session to the configured output path

::: REvoDesign.structure.PocketSearcher.PocketSearcher
    options:
      show_root_heading: true
      show_source: false
      heading_level: 3
