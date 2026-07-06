# Installation

REvoDesign uses its own **Package Manager** — a graphical installer that runs
inside PyMOL. It is not distributed on PyPI.

## System Requirements

REvoDesign runs on all major operating systems:

| Component | Recommended |
|-----------|-------------|
| CPU | Intel Core i5 or above |
| Memory | 8 GB or above |
| Disk | 2 GB free minimum |
| Display | 1920×1080 or higher |
| Software | PyMOL 2.5+, Python 3.10+ (3.12 recommended) |

Supported operating systems:

- **Windows 10** or later
- **Ubuntu Linux 20.04** or later
- **macOS 12** or later

## Install PyMOL

REvoDesign requires PyMOL. We recommend installing the open-source build from
conda-forge:

```bash
# Install Miniconda first: https://www.anaconda.com/docs/getting-started/miniconda/install
conda create -y -n revodesign python=3.12
conda activate revodesign
conda install -y -c conda-forge pymol-open-source pyqt=5
pymol
```

If you already have a working PyMOL installation (2.5+), skip this step.

## Install REvoDesign Package Manager

1. Open PyMOL.
2. Navigate to **Plugin → Plugin Manager → Install New Plugin**.
3. Select **Install from PyMOLWiki or any URL**.
4. Paste the Package Manager URL:

    ```text
    https://gist.githubusercontent.com/YaoYinYing/c1e8bfe0fc0b9c60bf49ea04a550a044/raw/REvoDesign_PyMOL.py
    ```

5. Click **Fetch** and confirm.

<figure markdown="span">
![PyMOL Plugin Manager](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/plugin-manager-interface.png){ width="600" }
<figcaption>PyMOL Plugin Manager interface</figcaption>
</figure>

<figure markdown="span">
![Paste Package Manager URL](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/paste-package-manager-url.png){ width="600" }
<figcaption>Paste the REvoDesign Package Manager URL and click Fetch</figcaption>
</figure>

<figure markdown="span">
![Confirm install location](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/confirm-install-location.png){ width="600" }
<figcaption>Confirm plugin installation location</figcaption>
</figure>

6. The **REvoDesign Package Manager** appears in the Plugin menu.

## Install REvoDesign from the Package Manager

### Using a Local Archive (Recommended)

1. Download the latest release (`.zip` or `.tar.gz`) from the
   [GitHub Releases](https://github.com/YaoYinYing/REvoDesign/releases) page.
2. In PyMOL, open **Plugin → REvoDesign Package Manager**.
3. Set **Source** to `Local file`.
4. Click **`...`** and select the downloaded archive.
5. In the **Extra** section, choose components to install:
    - `None` — core only (recommended for first-time install)
    - `Customized` — select specific components from the list
    - `Everything` — all components except the test suite
6. Click **Install**.

<figure markdown="span">
![Package Manager menu entry](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/package-manager-menu.png){ width="600" }
<figcaption>Package Manager appears in the Plugin menu after installation</figcaption>
</figure>

<figure markdown="span">
![Package Manager interface](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/package-manager-interface.png){ width="500" }
<figcaption>Package Manager main interface</figcaption>
</figure>

<figure markdown="span">
![Package Manager — judging installer view](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/GUI-judging-installer@4x.png){ width="600" }
<figcaption>Package Manager judging installer — component selection and install progress</figcaption>
</figure>

!!! tip "First-time installation"
    Start with `None` for the Extra components. You can install additional
    components later by re-running the Package Manager with `Customized`.

### Using the Repository (Advanced)

Set **Source** to `Repository` to install directly from GitHub. You can specify
a branch, tag, or commit hash in the **Commit** field. Use **Tag** to select
from available release tags (click the dropdown after the tags load). Click
**Refresh GitHub Release tags** from the right-click menu if the tag list is
stale.

### Network Configuration

In the **Network** section you can configure:

- HTTP/HTTPS proxy settings
- PyPI mirror URL (useful for users in mainland China)

## Verify Installation

1. Restart PyMOL after installation completes.
2. Check that **REvoDesign** appears in the **Plugin** menu.
3. If installation fails, check the PyMOL command log for error details.
   Users in mainland China may need to adjust network settings and retry.

## Right-Click Menu

Right-click in the empty area of the Package Manager for additional options:

| Option | Description |
|--------|-------------|
| **Upgrade this manager** | Update the Package Manager UI and Python files. Shows a diff of changes before confirming. |
| **Reset REvoDesign's configuration** | Delete user config and restore defaults from the program directory. Use when bad config prevents startup. |
| **Collect diagnostic data** (reduced) | Minimal diagnostic info to clipboard. |
| **Collect diagnostic data** (full, non-sensitive) | Complete diagnostic info with sensitive data filtered out. |
| **Collect diagnostic data** (full, with sensitive) | Complete unfiltered diagnostic data. Only share with trusted parties. |
| **Refresh GitHub Release tags** | Refresh the Tag dropdown for repository installs. |

<figure markdown="span">
![Right-click menu](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/right-click-menu.png){ width="600" }
<figcaption>Right-click menu in the Package Manager</figcaption>
</figure>

<figure markdown="span">
![Diagnostic data collection](https://github-image-cache.yaoyy.moe/revodesign-user-guide-images/imags/diagnostic-data.png){ width="600" }
<figcaption>Diagnostic data collection options</figcaption>
</figure>

## Self-Upgrade

1. Right-click in the Package Manager empty area.
2. Select **Upgrade this manager**.
3. Review the diff of changes shown in the confirmation dialog.
4. Click **Yes** to apply the update.
5. Restart PyMOL for the updated manager to take effect.

## Reset Configuration

If REvoDesign fails to start due to a bad configuration:

1. Right-click in the Package Manager empty area.
2. Select **Reset REvoDesign's configuration**.
3. Confirm by clicking **Yes**.
4. The user config directory is replaced with fresh defaults.
5. Restart PyMOL.

## Advanced Install Options

| Option | Purpose |
|--------|---------|
| **Verbose** (slider) | Logging verbosity during install. Far right = minimal; center = normal; far left = full debug. Use far left for troubleshooting failed installs. |
| **Tag** | Select a release tag when Source is Repository. |
| **Commit** | Custom branch, tag, or commit hash for repository installs. |
| **Refresh** | Refresh the list of available optional components. |
| **Cache** | Override the default cache location. Not recommended unless disk space is constrained. |
