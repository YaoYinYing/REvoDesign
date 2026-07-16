# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Runtime controller for the clustering tab."""

from __future__ import annotations

from REvoDesign.logger import ROOT_LOGGER
from REvoDesign.Qt import QtCore, QtWidgets
from REvoDesign.tools.customized_widgets import decide

logging = ROOT_LOGGER.getChild(__name__)

FALLBACK_CLUSTER_METHODS: tuple[str, ...] = (
    "AgglomerativeCluster",
    "EvoCluster",
    "KMeansCluster",
    "LegacyCluster",
)


class ClusterTabController:
    """Configure runtime behavior of the clustering tab after setupUi()."""

    def __init__(self, ui, bus=None):
        self.ui = ui
        self.bus = bus
        self._installed = False
        self._methods_cache: list[str] | None = None

    def install(self) -> None:
        """Install tooltips, method-specific panel switching, and safe defaults."""
        self._populate_method_selector()
        self._install_tooltips()
        if not self._installed:
            self.ui.comboBox_cluster_method.currentTextChanged.connect(self._on_method_changed)
            self.ui.checkBox_cluster_mutate_and_relax.stateChanged.connect(self._sync_rosetta_override_state)
            self._installed = True
        self.sync_from_state()

    def sync_from_state(self) -> None:
        """Apply current configuration-backed widget state to the cluster tab."""
        self._populate_method_selector()
        method_name = self._configured_method_name()
        if self.ui.comboBox_cluster_method.currentText() != method_name:
            self._set_combo_text(self.ui.comboBox_cluster_method, method_name)
        self._set_method_page(method_name)
        self._sync_rosetta_override_state()
        self._update_method_selector_tip(method_name)

    def confirm_cluster_run(self) -> bool:
        """Require explicit confirmation for the deprecated legacy workflow."""
        if self.ui.comboBox_cluster_method.currentText() != "LegacyCluster":
            return True
        return decide(
            "LegacyCluster confirmation",
            (
                "LegacyCluster is compatibility-only and uses Ward linkage on the score matrix. "
                "Continue only if you need historical behavior."
            ),
        )

    def _available_methods(self) -> list[str]:
        if self._methods_cache is not None:
            return self._methods_cache
        try:
            from REvoDesign.clusters.cluster_sequence import IMPLEMENTED_CLUSTER_METHOD

            available = set(IMPLEMENTED_CLUSTER_METHOD)
        except Exception:
            available = set(FALLBACK_CLUSTER_METHODS)

        ordered = [name for name in FALLBACK_CLUSTER_METHODS if name in available]
        ordered.extend(sorted(name for name in available if name not in FALLBACK_CLUSTER_METHODS))
        self._methods_cache = ordered or list(FALLBACK_CLUSTER_METHODS)
        return self._methods_cache

    def _configured_method_name(self) -> str:
        if self.bus is not None:
            try:
                return str(self.bus.get_value("ui.cluster.method.use", default_value="AgglomerativeCluster"))
            except Exception as exc:
                logging.debug("Could not read configured cluster method; using current UI value: %s", exc)
        current = self.ui.comboBox_cluster_method.currentText()
        return current or "AgglomerativeCluster"

    def _populate_method_selector(self) -> None:
        methods = self._available_methods()
        combo = self.ui.comboBox_cluster_method
        existing = [combo.itemText(index) for index in range(combo.count())]
        if existing == methods:
            return

        current = self._configured_method_name()
        combo.blockSignals(True)
        combo.clear()
        combo.addItems(methods)
        combo.blockSignals(False)
        self._set_combo_text(combo, current)

    @staticmethod
    def _set_combo_text(combo: QtWidgets.QComboBox, text: str) -> None:
        match_exactly = getattr(QtCore.Qt, "MatchExactly", None)
        if match_exactly is None:
            match_exactly = QtCore.Qt.MatchFlag.MatchExactly
        index = combo.findText(text, match_exactly)
        combo.setCurrentIndex(index if index >= 0 else 0)

    def _page_map(self) -> dict[str, QtWidgets.QWidget]:
        return {
            "AgglomerativeCluster": self.ui.page_cluster_agglomerative,
            "EvoCluster": self.ui.page_cluster_evo,
            "KMeansCluster": self.ui.page_cluster_kmeans,
            "LegacyCluster": self.ui.page_cluster_legacy,
        }

    def _set_method_page(self, method_name: str) -> None:
        page = self._page_map().get(method_name, self.ui.page_cluster_agglomerative)
        self.ui.stackedWidget_cluster_method_settings.setCurrentWidget(page)

    def _on_method_changed(self, method_name: str) -> None:
        self._set_method_page(method_name)
        self._update_method_selector_tip(method_name)

    def _update_method_selector_tip(self, method_name: str) -> None:
        base_tip = "Select the clustering backend to use for this run."
        if method_name == "LegacyCluster":
            base_tip += " LegacyCluster is deprecated compatibility mode."
        self.ui.comboBox_cluster_method.setToolTip(base_tip)
        self.ui.comboBox_cluster_method.setStatusTip(base_tip)

    def _sync_rosetta_override_state(self, *_args) -> None:
        enabled = self.ui.checkBox_cluster_mutate_and_relax.isChecked()
        override_widget = self.ui.checkBox_cluster_rosetta_override_representatives
        override_widget.setEnabled(enabled)
        if not enabled and override_widget.isChecked():
            override_widget.setChecked(False)

    def _install_tooltips(self) -> None:
        tooltip_map: dict[QtWidgets.QWidget, str] = {
            self.ui.comboBox_cluster_method: "Select the clustering backend to use for this run.",
            self.ui.spinBox_cluster_random_seed: "Seed used when variant shuffling is enabled.",
            self.ui.page_cluster_agglomerative: (
                "AgglomerativeCluster uses the sequence distance matrix with average linkage and a precomputed metric."
            ),
            self.ui.label_cluster_agglomerative_representative_value: (
                "Representatives are selected as the nearest centroid among clustered variants. This is not a medoid policy."
            ),
            self.ui.page_cluster_evo: (
                "Optional Evo inputs with positive weights are used when available; missing optional inputs are skipped and remaining weights are renormalized."
            ),
            self.ui.lineEdit_cluster_evo_pssm_profile: (
                "Optional PSSM input for EvoCluster. If the corresponding weight is positive, the file path must exist."
            ),
            self.ui.lineEdit_cluster_evo_esm1v_table: (
                "Optional ESM-1v input for EvoCluster. If the corresponding weight is positive, the file path must exist."
            ),
            self.ui.lineEdit_cluster_evo_structure_pdb: (
                "Optional structure input for EvoCluster spatial distance. A temporary input PDB may be generated when needed."
            ),
            self.ui.lineEdit_cluster_evo_esm_mutation_col: "Column name used to read ESM mutation identifiers.",
            self.ui.page_cluster_kmeans: (
                "KMeansCluster operates on score-profile feature vectors instead of a precomputed distance matrix."
            ),
            self.ui.label_cluster_kmeans_representative_value: (
                "Representatives are selected by nearest centroid in score-profile feature space."
            ),
            self.ui.page_cluster_legacy: (
                "LegacyCluster is a deprecated compatibility mode that uses Ward linkage on the score matrix."
            ),
            self.ui.label_cluster_legacy_warning: (
                "Use this only to reproduce historical behavior. Prefer AgglomerativeCluster or EvoCluster for new analyses."
            ),
            self.ui.checkBox_cluster_mutate_and_relax: (
                "Run Rosetta Mutate/Relax scoring after clustering without rewriting representative FASTA files by default."
            ),
            self.ui.checkBox_cluster_rosetta_override_representatives: (
                "Rosetta scoring normally exports score tables only. Representative FASTA files are rewritten only when this explicit override option is enabled."
            ),
        }

        for widget, text in tooltip_map.items():
            widget.setToolTip(text)
            widget.setStatusTip(text)
            widget.setWhatsThis(text)
