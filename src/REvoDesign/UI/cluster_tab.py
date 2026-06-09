# Copyright (c) 2026 The REvoDesign Developers.
# Distributed under the terms of the GNU General Public License v3.0.
# SPDX-License-Identifier: GPL-3.0-only

"""Cluster tab UI builder."""

from PyQt5 import QtCore, QtWidgets


def _make_browse_row(parent, line_edit_name: str, button_name: str):
    layout = QtWidgets.QHBoxLayout()
    line_edit = QtWidgets.QLineEdit(parent)
    line_edit.setObjectName(line_edit_name)
    layout.addWidget(line_edit)
    button = QtWidgets.QPushButton(parent)
    button.setObjectName(button_name)
    button.setMaximumWidth(32)
    layout.addWidget(button)
    return layout, line_edit, button


def setup_cluster_tab(ui, tab_cluster):
    ui.stackedWidget = QtWidgets.QStackedWidget(tab_cluster)
    ui.stackedWidget.setGeometry(QtCore.QRect(290, 0, 341, 181))
    ui.stackedWidget.setFrameShape(QtWidgets.QFrame.Box)
    ui.stackedWidget.setFrameShadow(QtWidgets.QFrame.Sunken)
    ui.stackedWidget.setLineWidth(1)
    ui.stackedWidget.setObjectName("stackedWidget")
    ui.page = QtWidgets.QWidget()
    ui.page.setObjectName("page")
    ui.stackedWidget.addWidget(ui.page)
    ui.page_2 = QtWidgets.QWidget()
    ui.page_2.setObjectName("page_2")
    ui.stackedWidget.addWidget(ui.page_2)

    ui.groupBox_cluster_general = QtWidgets.QGroupBox(tab_cluster)
    ui.groupBox_cluster_general.setGeometry(QtCore.QRect(10, 0, 271, 181))
    ui.groupBox_cluster_general.setObjectName("groupBox_cluster_general")
    ui.verticalLayoutWidget_cluster_general = QtWidgets.QWidget(ui.groupBox_cluster_general)
    ui.verticalLayoutWidget_cluster_general.setGeometry(QtCore.QRect(10, 30, 251, 141))
    ui.verticalLayoutWidget_cluster_general.setObjectName("verticalLayoutWidget_cluster_general")
    ui.verticalLayout_cluster_general = QtWidgets.QVBoxLayout(ui.verticalLayoutWidget_cluster_general)
    ui.verticalLayout_cluster_general.setContentsMargins(0, 0, 0, 0)
    ui.verticalLayout_cluster_general.setSpacing(4)
    ui.verticalLayout_cluster_general.setObjectName("verticalLayout_cluster_general")

    ui.horizontalLayout_39 = QtWidgets.QHBoxLayout()
    ui.horizontalLayout_39.setObjectName("horizontalLayout_39")
    ui.label_input_mut_table = QtWidgets.QLabel(ui.verticalLayoutWidget_cluster_general)
    ui.label_input_mut_table.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
    ui.label_input_mut_table.setObjectName("label_input_mut_table")
    ui.horizontalLayout_39.addWidget(ui.label_input_mut_table)
    ui.lineEdit_input_mut_table = QtWidgets.QLineEdit(ui.verticalLayoutWidget_cluster_general)
    ui.lineEdit_input_mut_table.setText("")
    ui.lineEdit_input_mut_table.setObjectName("lineEdit_input_mut_table")
    ui.horizontalLayout_39.addWidget(ui.lineEdit_input_mut_table)
    ui.pushButton_open_mut_table_2 = QtWidgets.QPushButton(ui.verticalLayoutWidget_cluster_general)
    ui.pushButton_open_mut_table_2.setObjectName("pushButton_open_mut_table_2")
    ui.pushButton_open_mut_table_2.setMaximumWidth(32)
    ui.horizontalLayout_39.addWidget(ui.pushButton_open_mut_table_2)
    ui.verticalLayout_cluster_general.addLayout(ui.horizontalLayout_39)

    ui.horizontalLayout_40 = QtWidgets.QHBoxLayout()
    ui.horizontalLayout_40.setObjectName("horizontalLayout_40")
    ui.spinBox_num_mut_minimun = QtWidgets.QSpinBox(ui.verticalLayoutWidget_cluster_general)
    ui.spinBox_num_mut_minimun.setMaximumWidth(48)
    ui.spinBox_num_mut_minimun.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignTrailing | QtCore.Qt.AlignVCenter)
    ui.spinBox_num_mut_minimun.setMinimum(1)
    ui.spinBox_num_mut_minimun.setMaximum(20)
    ui.spinBox_num_mut_minimun.setObjectName("spinBox_num_mut_minimun")
    ui.horizontalLayout_40.addWidget(ui.spinBox_num_mut_minimun)
    ui.label_28 = QtWidgets.QLabel(ui.verticalLayoutWidget_cluster_general)
    ui.label_28.setAlignment(QtCore.Qt.AlignCenter)
    ui.label_28.setObjectName("label_28")
    ui.horizontalLayout_40.addWidget(ui.label_28)
    ui.spinBox_num_mut_maximum = QtWidgets.QSpinBox(ui.verticalLayoutWidget_cluster_general)
    ui.spinBox_num_mut_maximum.setMaximumWidth(48)
    ui.spinBox_num_mut_maximum.setMinimum(1)
    ui.spinBox_num_mut_maximum.setMaximum(20)
    ui.spinBox_num_mut_maximum.setObjectName("spinBox_num_mut_maximum")
    ui.horizontalLayout_40.addWidget(ui.spinBox_num_mut_maximum)
    ui.verticalLayout_cluster_general.addLayout(ui.horizontalLayout_40)

    ui.gridLayout_cluster_general_numbers = QtWidgets.QGridLayout()
    ui.gridLayout_cluster_general_numbers.setObjectName("gridLayout_cluster_general_numbers")
    ui.label_41 = QtWidgets.QLabel(ui.verticalLayoutWidget_cluster_general)
    ui.label_41.setObjectName("label_41")
    ui.gridLayout_cluster_general_numbers.addWidget(ui.label_41, 0, 0, 1, 1)
    ui.spinBox_num_cluster = QtWidgets.QSpinBox(ui.verticalLayoutWidget_cluster_general)
    ui.spinBox_num_cluster.setMinimum(1)
    ui.spinBox_num_cluster.setMaximum(150)
    ui.spinBox_num_cluster.setProperty("value", 15)
    ui.spinBox_num_cluster.setObjectName("spinBox_num_cluster")
    ui.gridLayout_cluster_general_numbers.addWidget(ui.spinBox_num_cluster, 0, 1, 1, 1)
    ui.label_40 = QtWidgets.QLabel(ui.verticalLayoutWidget_cluster_general)
    ui.label_40.setObjectName("label_40")
    ui.gridLayout_cluster_general_numbers.addWidget(ui.label_40, 1, 0, 1, 1)
    ui.spinBox_cluster_batchsize = QtWidgets.QSpinBox(ui.verticalLayoutWidget_cluster_general)
    ui.spinBox_cluster_batchsize.setMinimum(1)
    ui.spinBox_cluster_batchsize.setMaximum(10000)
    ui.spinBox_cluster_batchsize.setSingleStep(25)
    ui.spinBox_cluster_batchsize.setProperty("value", 100)
    ui.spinBox_cluster_batchsize.setObjectName("spinBox_cluster_batchsize")
    ui.gridLayout_cluster_general_numbers.addWidget(ui.spinBox_cluster_batchsize, 1, 1, 1, 1)
    ui.label_cluster_random_seed = QtWidgets.QLabel(ui.verticalLayoutWidget_cluster_general)
    ui.label_cluster_random_seed.setObjectName("label_cluster_random_seed")
    ui.gridLayout_cluster_general_numbers.addWidget(ui.label_cluster_random_seed, 2, 0, 1, 1)
    ui.spinBox_cluster_random_seed = QtWidgets.QSpinBox(ui.verticalLayoutWidget_cluster_general)
    ui.spinBox_cluster_random_seed.setMinimum(0)
    ui.spinBox_cluster_random_seed.setMaximum(999999)
    ui.spinBox_cluster_random_seed.setProperty("value", 0)
    ui.spinBox_cluster_random_seed.setObjectName("spinBox_cluster_random_seed")
    ui.gridLayout_cluster_general_numbers.addWidget(ui.spinBox_cluster_random_seed, 2, 1, 1, 1)
    ui.verticalLayout_cluster_general.addLayout(ui.gridLayout_cluster_general_numbers)

    ui.horizontalLayout_cluster_method = QtWidgets.QHBoxLayout()
    ui.horizontalLayout_cluster_method.setObjectName("horizontalLayout_cluster_method")
    ui.label_cluster_method = QtWidgets.QLabel(ui.verticalLayoutWidget_cluster_general)
    ui.label_cluster_method.setObjectName("label_cluster_method")
    ui.horizontalLayout_cluster_method.addWidget(ui.label_cluster_method)
    ui.comboBox_cluster_method = QtWidgets.QComboBox(ui.verticalLayoutWidget_cluster_general)
    ui.comboBox_cluster_method.setObjectName("comboBox_cluster_method")
    ui.horizontalLayout_cluster_method.addWidget(ui.comboBox_cluster_method)
    ui.verticalLayout_cluster_general.addLayout(ui.horizontalLayout_cluster_method)

    ui.horizontalLayout_63 = QtWidgets.QHBoxLayout()
    ui.horizontalLayout_63.setObjectName("horizontalLayout_63")
    ui.checkBox_shuffle_clustering = QtWidgets.QCheckBox(ui.verticalLayoutWidget_cluster_general)
    ui.checkBox_shuffle_clustering.setChecked(True)
    ui.checkBox_shuffle_clustering.setObjectName("checkBox_shuffle_clustering")
    ui.horizontalLayout_63.addWidget(ui.checkBox_shuffle_clustering)
    ui.verticalLayout_cluster_general.addLayout(ui.horizontalLayout_63)

    ui.label_cluster_method_summary = QtWidgets.QLabel(ui.verticalLayoutWidget_cluster_general)
    ui.label_cluster_method_summary.setWordWrap(True)
    ui.label_cluster_method_summary.setObjectName("label_cluster_method_summary")
    ui.verticalLayout_cluster_general.addWidget(ui.label_cluster_method_summary)

    ui.horizontalLayout_22 = QtWidgets.QHBoxLayout()
    ui.horizontalLayout_22.setSpacing(0)
    ui.horizontalLayout_22.setObjectName("horizontalLayout_22")
    ui.pushButton_run_cluster = QtWidgets.QPushButton(ui.verticalLayoutWidget_cluster_general)
    ui.pushButton_run_cluster.setEnabled(False)
    ui.pushButton_run_cluster.setObjectName("pushButton_run_cluster")
    ui.horizontalLayout_22.addWidget(ui.pushButton_run_cluster)
    ui.verticalLayout_cluster_general.addLayout(ui.horizontalLayout_22)

    ui.groupBox_cluster_method_settings = QtWidgets.QGroupBox(tab_cluster)
    ui.groupBox_cluster_method_settings.setGeometry(QtCore.QRect(10, 190, 421, 201))
    ui.groupBox_cluster_method_settings.setObjectName("groupBox_cluster_method_settings")
    ui.verticalLayoutWidget_cluster_method = QtWidgets.QWidget(ui.groupBox_cluster_method_settings)
    ui.verticalLayoutWidget_cluster_method.setGeometry(QtCore.QRect(10, 30, 401, 161))
    ui.verticalLayoutWidget_cluster_method.setObjectName("verticalLayoutWidget_cluster_method")
    ui.verticalLayout_cluster_method = QtWidgets.QVBoxLayout(ui.verticalLayoutWidget_cluster_method)
    ui.verticalLayout_cluster_method.setContentsMargins(0, 0, 0, 0)
    ui.verticalLayout_cluster_method.setSpacing(4)
    ui.verticalLayout_cluster_method.setObjectName("verticalLayout_cluster_method")
    ui.stackedWidget_cluster_method_settings = QtWidgets.QStackedWidget(ui.verticalLayoutWidget_cluster_method)
    ui.stackedWidget_cluster_method_settings.setObjectName("stackedWidget_cluster_method_settings")
    ui.verticalLayout_cluster_method.addWidget(ui.stackedWidget_cluster_method_settings)

    ui.page_cluster_agglomerative = QtWidgets.QWidget()
    ui.page_cluster_agglomerative.setObjectName("page_cluster_agglomerative")
    ui.formLayout_cluster_agglomerative = QtWidgets.QFormLayout(ui.page_cluster_agglomerative)
    ui.formLayout_cluster_agglomerative.setObjectName("formLayout_cluster_agglomerative")
    ui.comboBox_cluster_matrix = QtWidgets.QComboBox(ui.page_cluster_agglomerative)
    ui.comboBox_cluster_matrix.setObjectName("comboBox_cluster_matrix")
    ui.label_cluster_agglomerative_matrix = QtWidgets.QLabel(ui.page_cluster_agglomerative)
    ui.label_cluster_agglomerative_matrix.setObjectName("label_cluster_agglomerative_matrix")
    ui.formLayout_cluster_agglomerative.addRow(ui.label_cluster_agglomerative_matrix, ui.comboBox_cluster_matrix)
    ui.label_cluster_agglomerative_linkage = QtWidgets.QLabel(ui.page_cluster_agglomerative)
    ui.label_cluster_agglomerative_linkage.setObjectName("label_cluster_agglomerative_linkage")
    ui.label_cluster_agglomerative_linkage_value = QtWidgets.QLabel(ui.page_cluster_agglomerative)
    ui.label_cluster_agglomerative_linkage_value.setObjectName("label_cluster_agglomerative_linkage_value")
    ui.formLayout_cluster_agglomerative.addRow(
        ui.label_cluster_agglomerative_linkage, ui.label_cluster_agglomerative_linkage_value
    )
    ui.label_cluster_agglomerative_metric = QtWidgets.QLabel(ui.page_cluster_agglomerative)
    ui.label_cluster_agglomerative_metric.setObjectName("label_cluster_agglomerative_metric")
    ui.label_cluster_agglomerative_metric_value = QtWidgets.QLabel(ui.page_cluster_agglomerative)
    ui.label_cluster_agglomerative_metric_value.setObjectName("label_cluster_agglomerative_metric_value")
    ui.formLayout_cluster_agglomerative.addRow(
        ui.label_cluster_agglomerative_metric, ui.label_cluster_agglomerative_metric_value
    )
    ui.label_cluster_agglomerative_representative = QtWidgets.QLabel(ui.page_cluster_agglomerative)
    ui.label_cluster_agglomerative_representative.setObjectName("label_cluster_agglomerative_representative")
    ui.label_cluster_agglomerative_representative_value = QtWidgets.QLabel(ui.page_cluster_agglomerative)
    ui.label_cluster_agglomerative_representative_value.setWordWrap(True)
    ui.label_cluster_agglomerative_representative_value.setObjectName(
        "label_cluster_agglomerative_representative_value"
    )
    ui.formLayout_cluster_agglomerative.addRow(
        ui.label_cluster_agglomerative_representative,
        ui.label_cluster_agglomerative_representative_value,
    )
    ui.stackedWidget_cluster_method_settings.addWidget(ui.page_cluster_agglomerative)

    ui.page_cluster_evo = QtWidgets.QWidget()
    ui.page_cluster_evo.setObjectName("page_cluster_evo")
    ui.gridLayout_cluster_evo = QtWidgets.QGridLayout(ui.page_cluster_evo)
    ui.gridLayout_cluster_evo.setObjectName("gridLayout_cluster_evo")
    ui.label_cluster_evo_help = QtWidgets.QLabel(ui.page_cluster_evo)
    ui.label_cluster_evo_help.setWordWrap(True)
    ui.label_cluster_evo_help.setObjectName("label_cluster_evo_help")
    ui.gridLayout_cluster_evo.addWidget(ui.label_cluster_evo_help, 0, 0, 1, 4)
    ui.label_cluster_evo_pssm = QtWidgets.QLabel(ui.page_cluster_evo)
    ui.label_cluster_evo_pssm.setObjectName("label_cluster_evo_pssm")
    ui.gridLayout_cluster_evo.addWidget(ui.label_cluster_evo_pssm, 1, 0, 1, 1)
    pssm_row, ui.lineEdit_cluster_evo_pssm_profile, ui.pushButton_open_cluster_evo_pssm_profile = _make_browse_row(
        ui.page_cluster_evo,
        "lineEdit_cluster_evo_pssm_profile",
        "pushButton_open_cluster_evo_pssm_profile",
    )
    ui.gridLayout_cluster_evo.addLayout(pssm_row, 1, 1, 1, 3)
    ui.label_cluster_evo_esm = QtWidgets.QLabel(ui.page_cluster_evo)
    ui.label_cluster_evo_esm.setObjectName("label_cluster_evo_esm")
    ui.gridLayout_cluster_evo.addWidget(ui.label_cluster_evo_esm, 2, 0, 1, 1)
    esm_row, ui.lineEdit_cluster_evo_esm1v_table, ui.pushButton_open_cluster_evo_esm1v_table = _make_browse_row(
        ui.page_cluster_evo,
        "lineEdit_cluster_evo_esm1v_table",
        "pushButton_open_cluster_evo_esm1v_table",
    )
    ui.gridLayout_cluster_evo.addLayout(esm_row, 2, 1, 1, 3)
    ui.label_cluster_evo_structure = QtWidgets.QLabel(ui.page_cluster_evo)
    ui.label_cluster_evo_structure.setObjectName("label_cluster_evo_structure")
    ui.gridLayout_cluster_evo.addWidget(ui.label_cluster_evo_structure, 3, 0, 1, 1)
    pdb_row, ui.lineEdit_cluster_evo_structure_pdb, ui.pushButton_open_cluster_evo_structure_pdb = _make_browse_row(
        ui.page_cluster_evo,
        "lineEdit_cluster_evo_structure_pdb",
        "pushButton_open_cluster_evo_structure_pdb",
    )
    ui.gridLayout_cluster_evo.addLayout(pdb_row, 3, 1, 1, 3)
    ui.label_cluster_evo_mutation_col = QtWidgets.QLabel(ui.page_cluster_evo)
    ui.label_cluster_evo_mutation_col.setObjectName("label_cluster_evo_mutation_col")
    ui.gridLayout_cluster_evo.addWidget(ui.label_cluster_evo_mutation_col, 4, 0, 1, 1)
    ui.lineEdit_cluster_evo_esm_mutation_col = QtWidgets.QLineEdit(ui.page_cluster_evo)
    ui.lineEdit_cluster_evo_esm_mutation_col.setObjectName("lineEdit_cluster_evo_esm_mutation_col")
    ui.gridLayout_cluster_evo.addWidget(ui.lineEdit_cluster_evo_esm_mutation_col, 4, 1, 1, 1)

    weight_specs = (
        ("seq", 5, 0, "label_cluster_evo_weight_seq", "doubleSpinBox_cluster_evo_weight_seq"),
        ("physchem", 5, 2, "label_cluster_evo_weight_physchem", "doubleSpinBox_cluster_evo_weight_physchem"),
        ("spatial", 6, 0, "label_cluster_evo_weight_spatial", "doubleSpinBox_cluster_evo_weight_spatial"),
        ("pssm", 6, 2, "label_cluster_evo_weight_pssm", "doubleSpinBox_cluster_evo_weight_pssm"),
        ("esm", 7, 0, "label_cluster_evo_weight_esm", "doubleSpinBox_cluster_evo_weight_esm"),
    )
    for weight_name, row, column, label_name, spinbox_name in weight_specs:
        label = QtWidgets.QLabel(ui.page_cluster_evo)
        label.setObjectName(label_name)
        setattr(ui, label_name, label)
        ui.gridLayout_cluster_evo.addWidget(label, row, column, 1, 1)
        spinbox = QtWidgets.QDoubleSpinBox(ui.page_cluster_evo)
        spinbox.setDecimals(3)
        spinbox.setMinimum(0.0)
        spinbox.setMaximum(1000.0)
        spinbox.setSingleStep(0.1)
        spinbox.setObjectName(spinbox_name)
        setattr(ui, spinbox_name, spinbox)
        ui.gridLayout_cluster_evo.addWidget(spinbox, row, column + 1, 1, 1)
        if weight_name == "seq":
            spinbox.setValue(1.0)
    ui.stackedWidget_cluster_method_settings.addWidget(ui.page_cluster_evo)

    ui.page_cluster_kmeans = QtWidgets.QWidget()
    ui.page_cluster_kmeans.setObjectName("page_cluster_kmeans")
    ui.verticalLayout_cluster_kmeans = QtWidgets.QVBoxLayout(ui.page_cluster_kmeans)
    ui.verticalLayout_cluster_kmeans.setObjectName("verticalLayout_cluster_kmeans")
    ui.label_cluster_kmeans_summary = QtWidgets.QLabel(ui.page_cluster_kmeans)
    ui.label_cluster_kmeans_summary.setWordWrap(True)
    ui.label_cluster_kmeans_summary.setObjectName("label_cluster_kmeans_summary")
    ui.verticalLayout_cluster_kmeans.addWidget(ui.label_cluster_kmeans_summary)
    ui.label_cluster_kmeans_representative = QtWidgets.QLabel(ui.page_cluster_kmeans)
    ui.label_cluster_kmeans_representative.setWordWrap(True)
    ui.label_cluster_kmeans_representative.setObjectName("label_cluster_kmeans_representative")
    ui.verticalLayout_cluster_kmeans.addWidget(ui.label_cluster_kmeans_representative)
    ui.verticalLayout_cluster_kmeans.addStretch(1)
    ui.stackedWidget_cluster_method_settings.addWidget(ui.page_cluster_kmeans)

    ui.page_cluster_legacy = QtWidgets.QWidget()
    ui.page_cluster_legacy.setObjectName("page_cluster_legacy")
    ui.verticalLayout_cluster_legacy = QtWidgets.QVBoxLayout(ui.page_cluster_legacy)
    ui.verticalLayout_cluster_legacy.setObjectName("verticalLayout_cluster_legacy")
    ui.label_cluster_legacy_warning = QtWidgets.QLabel(ui.page_cluster_legacy)
    ui.label_cluster_legacy_warning.setWordWrap(True)
    ui.label_cluster_legacy_warning.setStyleSheet("color: rgb(170, 70, 0); font-weight: bold;")
    ui.label_cluster_legacy_warning.setObjectName("label_cluster_legacy_warning")
    ui.verticalLayout_cluster_legacy.addWidget(ui.label_cluster_legacy_warning)
    ui.label_cluster_legacy_summary = QtWidgets.QLabel(ui.page_cluster_legacy)
    ui.label_cluster_legacy_summary.setWordWrap(True)
    ui.label_cluster_legacy_summary.setObjectName("label_cluster_legacy_summary")
    ui.verticalLayout_cluster_legacy.addWidget(ui.label_cluster_legacy_summary)
    ui.verticalLayout_cluster_legacy.addStretch(1)
    ui.stackedWidget_cluster_method_settings.addWidget(ui.page_cluster_legacy)

    ui.groupBox_cluster_post = QtWidgets.QGroupBox(tab_cluster)
    ui.groupBox_cluster_post.setGeometry(QtCore.QRect(440, 190, 191, 201))
    ui.groupBox_cluster_post.setObjectName("groupBox_cluster_post")
    ui.verticalLayoutWidget_cluster_post = QtWidgets.QWidget(ui.groupBox_cluster_post)
    ui.verticalLayoutWidget_cluster_post.setGeometry(QtCore.QRect(10, 30, 171, 161))
    ui.verticalLayoutWidget_cluster_post.setObjectName("verticalLayoutWidget_cluster_post")
    ui.verticalLayout_cluster_post = QtWidgets.QVBoxLayout(ui.verticalLayoutWidget_cluster_post)
    ui.verticalLayout_cluster_post.setContentsMargins(0, 0, 0, 0)
    ui.verticalLayout_cluster_post.setSpacing(4)
    ui.verticalLayout_cluster_post.setObjectName("verticalLayout_cluster_post")
    ui.checkBox_cluster_mutate_and_relax = QtWidgets.QCheckBox(ui.verticalLayoutWidget_cluster_post)
    ui.checkBox_cluster_mutate_and_relax.setChecked(False)
    ui.checkBox_cluster_mutate_and_relax.setObjectName("checkBox_cluster_mutate_and_relax")
    ui.verticalLayout_cluster_post.addWidget(ui.checkBox_cluster_mutate_and_relax)
    ui.checkBox_cluster_rosetta_override_representatives = QtWidgets.QCheckBox(ui.verticalLayoutWidget_cluster_post)
    ui.checkBox_cluster_rosetta_override_representatives.setChecked(False)
    ui.checkBox_cluster_rosetta_override_representatives.setObjectName(
        "checkBox_cluster_rosetta_override_representatives"
    )
    ui.verticalLayout_cluster_post.addWidget(ui.checkBox_cluster_rosetta_override_representatives)
    ui.label_cluster_rosetta_note = QtWidgets.QLabel(ui.verticalLayoutWidget_cluster_post)
    ui.label_cluster_rosetta_note.setWordWrap(True)
    ui.label_cluster_rosetta_note.setObjectName("label_cluster_rosetta_note")
    ui.verticalLayout_cluster_post.addWidget(ui.label_cluster_rosetta_note)


def retranslate_cluster_tab(ui, _translate):
    ui.tab_cluster.setStatusTip(_translate("REvoDesignPyMOL_UI", "Cluster mutagenesis space."))
    ui.groupBox_cluster_general.setTitle(_translate("REvoDesignPyMOL_UI", "General clustering inputs"))
    ui.label_input_mut_table.setText(_translate("REvoDesignPyMOL_UI", "Mutants:"))
    ui.lineEdit_input_mut_table.setStatusTip(
        _translate("REvoDesignPyMOL_UI", "Input mutant table [*.mut.txt] path")
    )
    ui.pushButton_open_mut_table_2.setText(_translate("REvoDesignPyMOL_UI", "..."))
    ui.spinBox_num_mut_minimun.setStatusTip(
        _translate("REvoDesignPyMOL_UI", "Minimum number of mutations for each variant.")
    )
    ui.label_28.setText(
        _translate(
            "REvoDesignPyMOL_UI",
            "<html><head/><body><p><span style=\" font-size:18pt;\">≤ Num </span>"
            "<span style=\" font-size:18pt; vertical-align:sub;\">MUT</span>"
            "<span style=\" font-size:18pt;\"> ≤</span></p></body></html>",
        )
    )
    ui.spinBox_num_mut_maximum.setStatusTip(
        _translate("REvoDesignPyMOL_UI", "Maximum number of mutations for each variant.")
    )
    ui.label_41.setText(_translate("REvoDesignPyMOL_UI", "Clusters:"))
    ui.spinBox_num_cluster.setStatusTip(_translate("REvoDesignPyMOL_UI", "Number of clusters to generate."))
    ui.label_40.setText(_translate("REvoDesignPyMOL_UI", "Batch size:"))
    ui.spinBox_cluster_batchsize.setStatusTip(
        _translate("REvoDesignPyMOL_UI", "Alignment workload per clustering minibatch.")
    )
    ui.label_cluster_random_seed.setText(_translate("REvoDesignPyMOL_UI", "Random seed:"))
    ui.spinBox_cluster_random_seed.setStatusTip(
        _translate("REvoDesignPyMOL_UI", "Seed used when variant shuffling is enabled.")
    )
    ui.label_cluster_method.setText(_translate("REvoDesignPyMOL_UI", "Method:"))
    ui.comboBox_cluster_method.setStatusTip(
        _translate("REvoDesignPyMOL_UI", "Select the clustering backend to use for this run.")
    )
    ui.checkBox_shuffle_clustering.setStatusTip(_translate("REvoDesignPyMOL_UI", "Shuffle variants before clustering."))
    ui.checkBox_shuffle_clustering.setText(_translate("REvoDesignPyMOL_UI", "Shuffle variants"))
    ui.label_cluster_method_summary.setText(
        _translate(
            "REvoDesignPyMOL_UI",
            "AgglomerativeCluster is the default. LegacyCluster is available only for compatibility checks.",
        )
    )
    ui.pushButton_run_cluster.setText(_translate("REvoDesignPyMOL_UI", "Run !"))

    ui.groupBox_cluster_method_settings.setTitle(_translate("REvoDesignPyMOL_UI", "Method-specific settings"))
    ui.label_cluster_agglomerative_matrix.setText(_translate("REvoDesignPyMOL_UI", "Substitution matrix"))
    ui.comboBox_cluster_matrix.setStatusTip(_translate("REvoDesignPyMOL_UI", "Sequence alignment matrix"))
    ui.label_cluster_agglomerative_linkage.setText(_translate("REvoDesignPyMOL_UI", "Linkage"))
    ui.label_cluster_agglomerative_linkage_value.setText(_translate("REvoDesignPyMOL_UI", "average"))
    ui.label_cluster_agglomerative_metric.setText(_translate("REvoDesignPyMOL_UI", "Metric"))
    ui.label_cluster_agglomerative_metric_value.setText(_translate("REvoDesignPyMOL_UI", "precomputed"))
    ui.label_cluster_agglomerative_representative.setText(_translate("REvoDesignPyMOL_UI", "Representatives"))
    ui.label_cluster_agglomerative_representative_value.setText(
        _translate("REvoDesignPyMOL_UI", "Nearest centroid among clustered variants. This is not a medoid selection.")
    )

    ui.label_cluster_evo_help.setText(
        _translate(
            "REvoDesignPyMOL_UI",
            "Missing optional Evo inputs are skipped. The backend renormalizes the remaining positive-weight components and records the active set in cluster_method_report.json.",
        )
    )
    ui.label_cluster_evo_pssm.setText(_translate("REvoDesignPyMOL_UI", "PSSM profile"))
    ui.pushButton_open_cluster_evo_pssm_profile.setText(_translate("REvoDesignPyMOL_UI", "..."))
    ui.label_cluster_evo_esm.setText(_translate("REvoDesignPyMOL_UI", "ESM-1v table"))
    ui.pushButton_open_cluster_evo_esm1v_table.setText(_translate("REvoDesignPyMOL_UI", "..."))
    ui.label_cluster_evo_structure.setText(_translate("REvoDesignPyMOL_UI", "Structure PDB"))
    ui.pushButton_open_cluster_evo_structure_pdb.setText(_translate("REvoDesignPyMOL_UI", "..."))
    ui.label_cluster_evo_mutation_col.setText(_translate("REvoDesignPyMOL_UI", "ESM mutation column"))
    ui.label_cluster_evo_weight_seq.setText(_translate("REvoDesignPyMOL_UI", "Sequence weight"))
    ui.label_cluster_evo_weight_physchem.setText(_translate("REvoDesignPyMOL_UI", "Physchem weight"))
    ui.label_cluster_evo_weight_spatial.setText(_translate("REvoDesignPyMOL_UI", "Spatial weight"))
    ui.label_cluster_evo_weight_pssm.setText(_translate("REvoDesignPyMOL_UI", "PSSM weight"))
    ui.label_cluster_evo_weight_esm.setText(_translate("REvoDesignPyMOL_UI", "ESM weight"))

    ui.label_cluster_kmeans_summary.setText(
        _translate(
            "REvoDesignPyMOL_UI",
            "KMeansCluster operates on score-profile feature vectors instead of a precomputed distance matrix. Keep it available for comparison, not as the default recommendation.",
        )
    )
    ui.label_cluster_kmeans_representative.setText(
        _translate("REvoDesignPyMOL_UI", "Representatives are selected by nearest centroid in score-profile space.")
    )

    ui.label_cluster_legacy_warning.setText(
        _translate(
            "REvoDesignPyMOL_UI",
            "LegacyCluster is compatibility-only. It uses Ward linkage on the score matrix and should not be used for new analyses.",
        )
    )
    ui.label_cluster_legacy_summary.setText(
        _translate(
            "REvoDesignPyMOL_UI",
            "Use this only to reproduce historical behavior. Prefer AgglomerativeCluster or EvoCluster for new runs.",
        )
    )

    ui.groupBox_cluster_post.setTitle(_translate("REvoDesignPyMOL_UI", "Post-clustering Rosetta scoring"))
    ui.checkBox_cluster_mutate_and_relax.setStatusTip(
        _translate("REvoDesignPyMOL_UI", "Run Mutate'n'Relax scoring after clustering.")
    )
    ui.checkBox_cluster_mutate_and_relax.setText(
        _translate("REvoDesignPyMOL_UI", "Run Rosetta Mutate/Relax scoring after clustering")
    )
    ui.checkBox_cluster_rosetta_override_representatives.setText(
        _translate("REvoDesignPyMOL_UI", "Use Rosetta results to override cluster representatives")
    )
    ui.label_cluster_rosetta_note.setText(
        _translate(
            "REvoDesignPyMOL_UI",
            "Representative override is opt-in and disabled by default. Without it, Rosetta writes scoring outputs without rewriting representative FASTA files.",
        )
    )
