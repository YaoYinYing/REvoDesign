# Interface Overview

REvoDesign runs as a PyMOL plugin. Its main window is organized into functional
zones around a tabbed workflow.

<figure markdown="span">
![REvoDesign main interface zones](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/main-interface-zones.png){ width="500" }
<figcaption>REvoDesign main interface with functional zones labeled</figcaption>
</figure>

## Interface Zones

1. **Molecule and Chain Selector** — Appears after loading a structure.
   Select the target molecule and chain for analysis.

2. **CPU Core Limit** — Caps the number of CPU cores used for parallel
   computation. Maximum equals available system cores.

3. **Color Preset** — Select a matplotlib colormap for result coloring.
   The preview bar shows the low-to-high gradient (top-left to bottom-right).
   The adjacent checkbox inverts the color scale.

    <figure markdown="span">
    ![Color preset dropdown](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/color-preset-dropdown.png){ width="500" }
    <figcaption>Color preset dropdown with gradient preview icons</figcaption>
    </figure>

4. **Core Function Tabs** — The main workspace, organized by workflow stage:
   **Prepare**, **Mutate**, **Evaluate**, **Cluster**, **Visualize**,
   **Interact**, **Socket**, and **Config**.

5. **Progress Bar** — Shows task status:
    - Scrolls during background computation.
    - Shows design/calculation progress percentage.
    - Shows your position during rational screening (e.g., mutant index
      within the MutantTree, co-evolution pair index in the queue).

6. **Tooltip Area** — Hover over any control to see usage hints here.

## Drop-Down Menus

Auxiliary design tools are organized in the menu bar by function category.

<figure markdown="span">
![Drop-down menus](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/dropdown-menus.png){ width="600" }
<figcaption>Drop-down menus provide additional task functions</figcaption>
</figure>

<figure markdown="span">
![Menu functions overview](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/menu_functions@4x.png){ width="600" }
<figcaption>Complete menu function reference with categorized tool entries</figcaption>
</figure>

Many menu items open a parameter dialog for user input. For example,
**Tools → Relax w/ Ca Constraints** runs Rosetta sidechain relaxation with
Cα restraints.

<figure markdown="span">
![Task parameter dialog](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/task-parameter-dialog.png){ width="350" }
<figcaption>Task parameter window — fill in the fields and run</figcaption>
</figure>

<figure markdown="span">
![Dialog wrapper examples](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/dialog-wrapper@4x.png){ width="500" }
<figcaption>Dialog wrapper pattern — parameter dialogs for various task configurations</figcaption>
</figure>

!!! warning "Parameters are ephemeral"
    Task dialog inputs are stored in memory only — closing the window discards
    them. Click **Save** to persist the parameters as a JSON file for reuse.

Saved parameter files can be reloaded via **Load** or by drag-and-drop onto
the dialog window.

<figure markdown="span">
![Drag-and-drop parameter loading](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/drag-drop-params.png){ width="600" }
<figcaption>Save parameters to JSON; reload via Load button or drag-and-drop</figcaption>
</figure>

## Language Switching

REvoDesign supports internationalization (i18n) for the main window.
The language selector is in the top-right area.

<figure markdown="span">
![Language switcher](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/language-switcher.png){ width="600" }
<figcaption>Interface language switching</figcaption>
</figure>

<figure markdown="span">
![Chinese UI](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/chinese-ui.png){ width="600" }
<figcaption>REvoDesign main interface in Chinese</figcaption>
</figure>

!!! note
    Translation covers the main window only. Log messages, task dialogs, and
    tooltips remain in English.

## Configuration Management

All UI changes modify the in-memory configuration immediately but are **not**
persisted to disk automatically.

<figure markdown="span">
![Save/load experiments](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/save-load-experiments.png){ width="600" }
<figcaption>Configurations can be saved and loaded as experiment snapshots</figcaption>
</figure>

<figure markdown="span">
![Save configuration options](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/save-config-options.png){ width="600" }
<figcaption>Configuration save options in the Edit menu</figcaption>
</figure>

| Action | Shortcut | Description |
|--------|----------|-------------|
| **Save Configurations** | `Ctrl+S` | Write current config to disk. Loaded on next startup. |
| **Save Configuration As…** | `Ctrl+Alt+S` | Save to a different location. |
| **Save to Experiment** | `Ctrl+Shift+S` | Save config as a named experiment for reproducibility. |
| **Load Experiment** | `Ctrl+Shift+L` | Load a previously saved experiment. |
| **Edit Configuration** | — | Open config files in the Monaco editor (external browser). |
| **Reconfigure** | — | Reload config from disk and apply to UI. |
| **Initialize Configuration** | — | Delete user config and restore factory defaults. |

!!! danger "Broken config?"
    If REvoDesign won't start due to a bad configuration, use the Package
    Manager's right-click menu to **Reset REvoDesign's configuration**.
    This restores factory defaults.

## Socket — Multi-User Collaboration

The **Socket** tab enables real-time peer-to-peer collaboration between
multiple REvoDesign instances. Users can share views, mutant trees, and
design data over a WebSocket connection.

<figure markdown="span">
![Socket design workflow](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/socket_design_workflow@4x.png){ width="600" }
<figcaption>Figure: Socket-based collaborative design workflow between multiple REvoDesign instances</figcaption>
</figure>
