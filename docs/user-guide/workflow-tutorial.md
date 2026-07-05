# Workflow Tutorial

This tutorial walks through a complete enzyme redesign session using
**CYP450 (PDB ID: 1SUO)** as the case study. You will learn how to identify
design hotspots, generate virtual saturation mutagenesis libraries, rationally
evaluate mutants, cluster candidates, cross-screen with external tools, and
explore co-evolution constraints.

## Prerequisites

- REvoDesign installed and working in PyMOL
- Evolution data (PSSM + GREMLIN) pre-computed for your target sequence
  ([see below](#obtaining-evolution-data))

### Obtaining Evolution Data

REvoDesign requires PSSM and GREMLIN profiles computed from sequence databases.
Use the computation service:

1. Go to <https://revodesign.yaoyy.moe/PSSM_GREMLIN/create_task>
2. Upload a FASTA-format sequence file (one sequence per file).
   Sequences may contain unknown residues (`X`) but not stop codons (`*`).
3. Monitor progress at the [Dashboard](https://revodesign.yaoyy.moe/PSSM_GREMLIN/dashboard).
4. Hover over a task to reveal a cancel button (if queued/running) or
   a download button (if complete).
5. When complete, download and unzip the archive for use in the Prepare step.

<figure markdown="span">
![PSSM/GREMLIN server — task submission page](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/pssm-gremlin-server-v2a@4x.png){ width="600" }
<figcaption>PSSM/GREMLIN server task submission: upload a single FASTA file or paste a sequence</figcaption>
</figure>

<figure markdown="span">
![PSSM/GREMLIN server — task dashboard](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/pssm-gremlin-server-v2b@4x.png){ width="600" }
<figcaption>PSSM/GREMLIN server dashboard: monitor task status, cancel queued/running jobs, download completed results</figcaption>
</figure>

!!! example "Example FASTA"
    ```
    >1SUO_A
    XXXXXXXXXXXXXXXXXXXXXXXXXXXGKLPPGPSPLPVLGNLLQMDRKGLLRSFLRLREKYGDVFTVYLGSRPVVVLCGTDAIREALVDQAEAFSGRGKIAVVDPIFQGYGVIFANGERWRALRRFSLATMRDFGMGKRSVEERIQEEARCLVEELRKSKGALLDNTLLFHSITSNIICSIVFGKRFDYKDPVFLRLLDLFFQSFSLISSFSSQVFELFSGFLKYFPGTHRQIYRNLQEINTFIGQSVEKHRATLDPSNPRDFIDVYLLRMEKDKSDPSSEFHHQNLILTVLSLFFAGTETTSTTLRYGFLLMLKYPHVTERVQKEIEQVIGSHRPPALDDRAKMPYTDAVIHEIQRLGDLIPFGVPHTVTKDTQFRGYVIPKNTEVFPVLSSALHDPRYFETPNTFNPGHFLDANGALKRNEGFMPFSLGKRICLGEGIARTELFLFFTTILQNFSIASPVPPEDIDLTPRESGVGNVPPSYQIRFLARH
    ```

## Step 1: Prepare the Structure

### Load and Set Up in PyMOL

In PyMOL, fetch the target structure and prepare it for analysis:

```bash
fetch 1SUO
```

1SUO is a CYP450 enzyme with four components:

| Segment ID | Molecule | Description |
|-----------|----------|-------------|
| A | Protein | Enzyme |
| B | HEM | Cofactor |
| C | CPZ | Substrate |
| D | HOH | Crystallization water |

Apply basic styling and clean up:

```python
# Cartoon styling
set cartoon_cylindrical_helices, 1
set cartoon_color, gray70
set cartoon_transparency, 0.3

# Fix secondary structure assignment
dss

# Remove crystallization water
remove resn HOH

# White background
bg_color white
```

Save this session — it will serve as the starting point for all subsequent
analysis.

<figure markdown="span">
![Prepared structure model](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/prepared-structure.png){ width="600" }
<figcaption>Prepared 1SUO structure with cartoon styling</figcaption>
</figure>

### Import Session into REvoDesign

In REvoDesign, go to **File → Import PyMOL Session** (or press
`Ctrl+N` / `Cmd+N`). This registers the PyMOL session so REvoDesign can
identify molecules and selections.

<figure markdown="span">
![Import PyMOL Session](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/import-pymol-session.png){ width="600" }
<figcaption>Import the current PyMOL session into REvoDesign</figcaption>
</figure>

### Detect Binding Pocket Hotspots

In the **Prepare** tab, under the **Pocket** section:

1. Identify the substrate and cofactor molecules by their residue names
   (e.g., `CPZ` for the substrate, `HEM` for the cofactor).
2. Set the contact distance cutoff for each (default: 8 Å for substrate,
   7 Å for cofactor).
3. Specify a save path to enable the detection button.
4. Click **Detect**.

<figure markdown="span">
![Pocket detection setup](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/pocket-detection-setup.png){ width="600" }
<figcaption>Specify the substrate (CPZ) and cofactor (HEM) molecules</figcaption>
</figure>

<figure markdown="span">
![Pocket settings complete](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/pocket-settings-complete.png){ width="550" }
<figcaption>Set contact distances and save path, then click Detect</figcaption>
</figure>

You can also use PyMOL selection syntax for complex cases (e.g.,
`r. UNK or r. LIG` to treat two ligands as one).

!!! info "How pocket detection works"
    Residues within the cutoff distance of the substrate/cofactor are collected
    into selection groups. Overlapping regions (shared by cofactor and
    substrate) are assigned to the cofactor group and removed from the
    substrate group to avoid double-counting.

Results are saved to `pockets/` in the working directory as
`<molecule>_<pocket_selection>_residues.txt`. The following selections
are created:

| Selection | Content |
|-----------|---------|
| `design_shell_CPZ_8.0_01` | Substrate-binding residues (cofactor overlap removed) |
| `pkt_cof_HEM_7.0_01` | Cofactor-binding residues |
| `pkt_CPZ_8.0_01` | Substrate-binding residues (full) |
| `pkt_hetatm_8.0_01` | All heteroatom-contacting residues (union) |

<figure markdown="span">
![Pocket detection results](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/pocket-detection-results.png){ width="450" }
<figcaption>Pocket detection results loaded into PyMOL</figcaption>
</figure>

### Detect Surface-Exposed Hotspots

In the **Prepare** tab, under the **Surface Exposure** section:

1. Set the solvent-accessible surface area (SASA) threshold (default: 15 Å²).
   Residues with SASA ≥ threshold are considered surface-exposed.
2. Optionally exclude pocket residues: click **Refresh Selection** to load
   available PyMOL selections, then choose `pkt_hetatm_8.0_01` from the
   Exclusion dropdown.
3. Specify a save path and click **Find**.

<figure markdown="span">
![Surface exposure options](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/surface-exposure-options.png){ width="600" }
<figcaption>Surface exposure and PPI interface detection options</figcaption>
</figure>

<figure markdown="span">
![Surface detection parameters](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/surface-detection-params.png){ width="600" }
<figcaption>Set exclusion, SASA threshold, and save path</figcaption>
</figure>

Results are visualized as spheres: **blue** for exposed, **red** for buried,
and **no sphere** for excluded residues. Results are also saved to
`surface_residue_records/` in the working directory.

<figure markdown="span">
![Surface exposure results](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/surface-exposure-results.png){ width="600" }
<figcaption>Surface exposure detection results (blue = exposed, red = buried)</figcaption>
</figure>

!!! warning
    The surface-exposure visualization session is for inspection only. Do not
    use it as the basis for further design steps — use the pre-detection
    session instead.

### Protein-Protein Interface (Optional)

For multimeric proteins, use the PPI section to detect chain-chain contacts:

1. Set **Chain Dist** to the minimum contact distance between chains.
2. Click **Find** to identify interfacial residues.
3. Click **Refresh Selection** to load the result for exclusion.

## Step 2: Mutate — Virtual Saturation Mutagenesis

The **Mutate** tab generates a pool of virtual point mutations under
constraints derived from evolutionary conservation (PSSM).

### Strategy 1: Surface Entropy Reduction

Surface entropy reduction replaces exposed residues with shorter, less
solvent-interacting amino acids within conservation constraints.

1. Load the unzipped evolution data into **Profile** and set type to **PSSM**.
2. Set **Residue ID** to the surface exposure result selection.
3. Choose a session save path.
4. Set **Score cutoff** bounds. Example: PSSM score difference ≥ -2 and
   ≤ 20 relative to wild-type (-2 tolerates slightly less conserved
   substitutions; 20 is effectively unbounded, meaning absolute conservation).
5. In **Substitution**:
    - **Reject**: `PC` (reject proline and cysteine)
    - **Accept**: e.g., `E:DATY` (replace E with D/A/T/Y candidates)
6. Enter a **Design Case** name for output file naming.
7. Click **Run!**

<figure markdown="span">
![Surface entropy reduction settings](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/surface-entropy-settings.png){ width="550" }
<figcaption>Surface entropy reduction design settings</figcaption>
</figure>

### Strategy 2: Catalytic Pocket Design

Catalytic pocket design uses a more permissive substitution strategy to
increase diversity near the active site.

1. Set **Score cutoff** to a wider range (e.g., ≥ -5, ≤ 20).
2. Clear the **Accept** substitution preferences to allow all valid
   substitutions.
3. Keep **Reject** as `PC` to avoid disruptive proline/cysteine mutations.

<figure markdown="span">
![Catalytic pocket design settings](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/catalytic-pocket-settings.png){ width="550" }
<figcaption>Catalytic pocket design with relaxed conservation constraints</figcaption>
</figure>

### Understanding the Output

Design results appear in PyMOL grouped by residue position:

- Group name: `mt_<WT><position>_<PSSM_score>`
- Mutant name: `<chain><WT><position><mutant>_<mutant_score>`
- Only the mutated sidechain is shown
- Carbon atoms are colored by PSSM score (see color preset)
- Full PDB structures are saved under `mutant_pdbs/` in the working directory

<figure markdown="span">
![Surface entropy reduction results](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/surface-entropy-results.png){ width="550" }
<figcaption>Surface entropy reduction — each group is a position, each entry a point mutant</figcaption>
</figure>

<figure markdown="span">
![Catalytic pocket design results](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/catalytic-pocket-results.png){ width="600" }
<figcaption>Catalytic pocket design results</figcaption>
</figure>

## Step 3: Evaluate — Rational Screening

The **Evaluate** tab provides tools for visual, side-by-side comparison of
wild-type and mutant sidechains to make informed decisions.

### Initialize the MutantTree

REvoDesign organizes mutants into a **MutantTree** — branches are residue
positions, leaves are individual point mutants at that position.

1. Go to the **Evaluate** tab.
2. Set a save path for mutant records and checkpoint files.
3. Click **Initialize** to scan the PyMOL session for mutant trees.
   If successful, **Total** shows a non-zero count and decision buttons
   become enabled.

<figure markdown="span">
![Evaluate — save path and checkpoint](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/evaluate-save-checkpoint.png){ width="500" }
<figcaption>Set save path for decision records and checkpoint files</figcaption>
</figure>

<figure markdown="span">
![Evaluate — status display](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/evaluate-status.png){ width="550" }
<figcaption>Evaluation status: total mutants, accepted count, navigation and decision tools</figcaption>
</figure>

### Navigate and Decide

In evaluation mode, REvoDesign hides all other mutants, collapses unrelated
branches, and shows only the current branch and individual. The wild-type
sidechain is displayed as a wireframe for comparison, while the mutant
sidechain is shown in ball-and-stick with a mesh surface.

<figure markdown="span">
![Evaluation mode](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/evaluation-mode.png){ width="600" }
<figcaption>Evaluation mode — wild-type (wireframe) vs mutant (ball-and-stick + mesh)</figcaption>
</figure>

Decision actions:

| Button | Action | Description |
|--------|--------|-------------|
| **Previous** | Go to previous mutant | Tooltip: `Shift+Opt+[` |
| **Next** | Go to next mutant | Tooltip: `Shift+Opt+]` |
| **Accept** | Accept current mutant | Tooltip: `Shift+Opt+-` |
| **Reject** | Reject current mutant | Tooltip: `Shift+Opt++` |

<figure markdown="span">
![Selecting the best-scoring mutant](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/best-scoring-mutant.png){ width="600" }
<figcaption>Review and select the best-scoring mutant in a branch</figcaption>
</figure>

<figure markdown="span">
![Decision state updated](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/decision-updated.png){ width="600" }
<figcaption>After accepting, the decision state updates immediately</figcaption>
</figure>

### Fast Navigation

Use the dropdown menus to jump directly to a specific branch or mutant.

<figure markdown="span">
![Branch selection dropdown](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/branch-dropdown.png){ width="500" }
<figcaption>Jump to any branch via the dropdown</figcaption>
</figure>

<figure markdown="span">
![Mutant selection dropdown](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/mutant-dropdown.png){ width="500" }
<figcaption>Select a specific point mutant within a branch</figcaption>
</figure>

- **Find the Best Hit** — automatically jumps to the highest-scoring mutant
  in the current branch.

<figure markdown="span">
![Find the Best Hit](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/find-best-hit.png){ width="600" }
<figcaption>Click "Find the Best Hit" to jump to the branch's top scorer</figcaption>
</figure>

- **I'm Lucky!** — scans every branch and collects the highest-scoring mutant
  from each. This is a rapid way to identify promising leads across all
  positions.

<figure markdown="span">
![I'm Lucky — auto sweep](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/im-lucky.png){ width="600" }
<figcaption>"I'm Lucky!" automatically collects the best mutant from each branch</figcaption>
</figure>

### Decision Persistence

Decision results are saved in real time to a text file, with corresponding
checkpoint files for reloading.

<figure markdown="span">
![Decision record file](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/decision-records.png){ width="600" }
<figcaption>Real-time decision records saved to a text file</figcaption>
</figure>

<figure markdown="span">
![Checkpoint files](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/checkpoint-files.png){ width="500" }
<figcaption>Checkpoint files allow resuming evaluation sessions</figcaption>
</figure>

To reload a previous checkpoint:

1. Re-initialize the MutantTree (clears previous decisions).
2. Load the checkpoint file.
3. Previous decisions are restored.

<figure markdown="span">
![Checkpoint loaded](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/checkpoint-loaded.png){ width="450" }
<figcaption>Checkpoint loaded — previous decisions restored</figcaption>
</figure>

## Step 4: Cluster — Reduce Library Size

REvoDesign uses sequence-based clustering to group similar mutants and select
representatives from each cluster, reducing the library to a size manageable
for wet-lab validation.

1. Load the accepted mutant list from the Evaluate step.
2. Set the number of mutations per mutant (default: 1).
3. Set the number of clusters (must be less than total mutants).
4. Choose a scoring matrix (default: PAM30).
5. Optionally enable **Mutate Relax** to score representatives with Rosetta
   energy evaluation.
6. Click **Run**.

<figure markdown="span">
![Cluster settings](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/cluster-settings.png){ width="550" }
<figcaption>Sequence clustering parameters</figcaption>
</figure>

The results panel shows a pairwise sequence similarity matrix (darker = more
similar).

<figure markdown="span">
![Cluster results](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/cluster-results.png){ width="600" }
<figcaption>Clustering results — matrix shows pairwise sequence similarity</figcaption>
</figure>

!!! warning "Cluster count"
    Too few clusters can force unrelated sequences into the same group,
    masking diversity. Choose a cluster count that balances library size
    with sequence diversity preservation.

### With Rosetta Energy Evaluation

When **Mutate Relax** is enabled, REvoDesign builds each mutant structure with
Rosetta and evaluates its energy. The lowest-energy mutant in each cluster is
selected as the representative.

<figure markdown="span">
![Cluster with Rosetta scoring](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/cluster-rosetta-scoring.png){ width="550" }
<figcaption>Enabling Rosetta Mutate Relax in clustering</figcaption>
</figure>

<figure markdown="span">
![Scoring results in log](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/scoring-log.png){ width="550" }
<figcaption>Scoring summary in the log output</figcaption>
</figure>

Full scoring results are saved as both Excel and CSV files for downstream
analysis.

!!! important "Mutate Relax assumptions"
    Mutate Relax operates under three assumptions:

    1. The starting structure is already energy-minimized.
    2. Point mutations do not affect backbone coordinates.
    3. Point mutations do not affect distant sidechain packing.

    Under these assumptions, only the mutated site is repacked locally.
    A well-optimized starting structure is critical for reliable scores.

## Step 5: Visualize — Cross-Screening and Data Display

The **Visualize** tab has two main functions:

### Cross-Screening with External Scoring Tools

Combine REvoDesign's mutation list with scores from external tools (ddG
predictors, stability predictors, etc.) for multi-criteria filtering.

This example uses **Pythia-ddG**, a structure-based ΔΔG predictor available on
BioLib at <https://biolib.com/YaoYinYing/pythia-wubianlab/>.

<figure markdown="span">
![Pythia-ddG on BioLib](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/pythia-biolib.png){ width="600" }
<figcaption>Pythia-ddG hosted on BioLib</figcaption>
</figure>

1. Upload the PDB structure to Pythia-ddG and run (takes ~1 minute).
2. Download the CSV results.
3. In REvoDesign's **Visualize** tab:
    - Load the mutant list.
    - Set the save path.
    - Select the Pythia-ddG CSV as the profile.
    - Verify **Profile type** is set to `CSV`.
    - Check **Invert color preset** (lower ddG = more stable = better).
    - Check **Global scoring** to use full-table extremes for coloring.
    - Enter a **Group** name for MutantTree organization.

<figure markdown="span">
![Cross-screening setup](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/cross-screening-setup.png){ width="500" }
<figcaption>Cross-screening configuration with external profile data</figcaption>
</figure>

!!! tip "Sidechain solver for cross-screening"
    When building mutant structures for cross-screening, use a high-accuracy
    sidechain solver like DLPacker for reliable structural details during
    visual inspection.

    <figure markdown="span">
    ![Sidechain solver selection](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/sidechain-solver.png){ width="600" }
    <figcaption>Adjust the sidechain solver for cross-screening accuracy</figcaption>
    </figure>

#### Pruning the MutantTree

Unwanted mutants can be removed during cross-screening review:

<figure markdown="span">
![Cross-screening sidechain display](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/cross-screening-display.png){ width="550" }
<figcaption>Cross-screening mutant sidechain display</figcaption>
</figure>

1. Click a mutant in the PyMOL viewer to select it.
2. Click **Hide** on the right panel to mark it for removal.

<figure markdown="span">
![Hide unwanted mutant](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/hide-mutant.png){ width="500" }
<figcaption>Step 1: Click "Hide" on the unwanted mutant</figcaption>
</figure>

3. Click **Reduce Session** to delete hidden mutants.

<figure markdown="span">
![Reduce and save](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/reduce-save.png){ width="600" }
<figcaption>Step 2: Reduce Session to delete, then rename and Save Mutant</figcaption>
</figure>

4. Rename the mutant table and click **Save Mutant** to persist.

<figure markdown="span">
![After pruning](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/after-pruning.png){ width="600" }
<figcaption>Pruned mutant table — unwanted entries removed</figcaption>
</figure>

<figure markdown="span">
![PSSM visualization example](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/visualizer-pssm-example@4x.png){ width="600" }
<figcaption>PSSM-based coloring of mutation scores on the 3D structure</figcaption>
</figure>

### Displaying Experimental Data on Structure

Map your experimental assay results (e.g., enzyme activity, product titer)
onto the 3D structure for visual analysis:

1. Prepare a CSV or Excel table:

    | mutant | normalized | group |
    |--------|------------|-------|
    | WT_1 | 0 | control |
    | wt_2 | -0.1 | control |
    | WT | 0 | control |
    | AE93D | 0.1 | low |
    | AK191R | 0.2 | medium |
    | AQ204E | 0.3 | high |

2. In the **Visualize** tab:
    - Set **Mutants** to the CSV path.
    - Set **Save as** to the session save path.
    - Clear the **Profile** path.
    - Set **Profile type** to empty.
    - Map column names: **Group**, **Mut**, **Score** to the appropriate
      CSV column names.

<figure markdown="span">
![Experimental data display settings](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/experimental-data-settings.png){ width="450" }
<figcaption>Map CSV columns to Group, Mutant name, and Score</figcaption>
</figure>

<figure markdown="span">
![Experimental data on structure](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/experimental-data-structure.png){ width="450" }
<figcaption>Experimental data mapped onto the 3D structure</figcaption>
</figure>

!!! note "WT handling"
    Rows whose mutant name contains "WT" (case-insensitive) are treated as
    controls. Their group assignment is ignored and the WT score is set to
    the average of all control rows.

<figure markdown="span">
![GREMLIN visualization example](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/visualizer-gremlin-example@4x.png){ width="600" }
<figcaption>GREMLIN co-evolution analysis: contact map and residue pair visualization</figcaption>
</figure>

## Step 6: Interact — Co-Evolution Analysis

The **Interact** tab uses GREMLIN Markov Random Field (MRF) models to identify
co-evolved residue pairs, revealing functional coupling between positions that
can guide combinatorial mutation design.

### Load GREMLIN Data

1. In the **Interact** tab, set the path to the GREMLIN MRF archive
   (e.g., `gremlin_res/1SUO_A.i90c75_aln.GREMLIN.mrf.pkl`).
2. Set the mutant design save path.
3. Adjust filters: top N co-evolving pairs, maximum contact distance,
   homo-oligomer chain binding mode.
4. Optionally enable scoring tools for on-the-fly mutant evaluation.
5. Click **Initialize** to load the co-evolution contact map.

<figure markdown="span">
![Co-evolution analysis interface](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/coevolution-interface.png){ width="600" }
<figcaption>Co-evolution analysis interface with GREMLIN contact map</figcaption>
</figure>

### Global Co-Evolution Scan

1. Click **Scan** to analyze the top co-evolving pairs within the distance
   cutoff.
2. Results are displayed as backbone traces: blue cylinders represent pairs,
   a yellow cylinder highlights the current pair. Cylinder thickness indicates
   co-evolution signal strength.

<figure markdown="span">
![Global co-evolution scan](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/global-coevolution-scan.png){ width="600" }
<figcaption>Global co-evolution pair scan results</figcaption>
</figure>

3. Navigate pairs with **Previous** / **Next**.
4. For each pair, the MRF matrix shows the 20×20 amino acid combination space.
   Grid cell color represents the GREMLIN probability for that residue pair.
5. **Click any cell** to instantly generate the corresponding double mutant.
   The mutant flows through: build → sidechain modeling → scoring (if
   enabled) → grouping → display.

<figure markdown="span">
![Real-time co-evolution analysis](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/realtime-coevolution.png){ width="550" }
<figcaption>Interactive MRF matrix — hover for pair info, click to design a double mutant</figcaption>
</figure>

<figure markdown="span">
![Designing from co-evolution](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/coevolution-design-mutant.png){ width="550" }
<figcaption>Double mutant designed from co-evolution matrix click</figcaption>
</figure>

The **WT** cell marks the wild-type residue combination at the current pair.

### Local Co-Evolution Analysis

Local analysis focuses on co-evolution partners of a single residue of
interest:

1. In PyMOL, click on a residue to create a `sele` selection object.
   (Or use: `select sele, 1SUO and resi 298`)
2. Ensure the `sele` selection is **enabled** (shown/active in PyMOL).
3. Click **Scan** in the Interact tab.

<figure markdown="span">
![Local co-evolution setup](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/local-coevolution-setup.png){ width="600" }
<figcaption>Local co-evolution analysis — select a residue in PyMOL first</figcaption>
</figure>

<figure markdown="span">
![Local co-evolution results](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/local-coevolution-results.png){ width="600" }
<figcaption>Local co-evolution scan — only pairs involving the selected residue</figcaption>
</figure>

Mutants designed from GREMLIN analysis must be explicitly saved — either
click **Accept** in the Interact tab or switch to the **Evaluate** tab for
structured rational screening.
