from dataclasses import dataclass
from typing import Any, Iterable, Union
from immutabledict import immutabledict
from omegaconf import DictConfig, OmegaConf
from pymol.Qt import QtWidgets

from REvoDesign.tools.customized_widgets import (
    create_cmap_icon,
    get_widget_value,
    set_widget_value,
)
from functools import partial
from REvoDesign.tools.logger import logging
from REvoDesign.tools.post_installed import reload_config_file
from REvoDesign.tools.utils import dirname_does_exist, filepath_does_exists


class ConfigBus:
    def __init__(self, ui: QtWidgets.QWidget):
        self.ui = ui
        self.cfg = reload_config_file()
        self.w2c = Widget2ConfigMapper(ui=self.ui)

    def initialize_widget_with_cfg_group(self):
        for i, (widget, group_cfgs) in enumerate(self.w2c.group_config_map):
            group_values = []

            if isinstance(group_cfgs, str) or callable(group_cfgs):
                group_cfgs = tuple([group_cfgs])

            for j, group_cfg in enumerate(group_cfgs):
                if callable(group_cfg):
                    values = group_cfg()
                else:
                    values = self.get_value(group_cfg)

                if not values:
                    continue

                if isinstance(values, list):
                    group_values.extend(values)
                elif isinstance(values, dict) and not group_values:
                    group_values = values.copy()
                elif isinstance(values, dict) and group_values:
                    if isinstance(group_values, list):
                        raise TypeError(
                            f'{group_cfg} returns a dict while group_values is a list'
                        )
                    else:
                        group_values.update(values)

            if not group_values:
                continue

            set_widget_value(widget, group_values)

            default_cfg_item = self.w2c._find_config_item(ui_element=widget)
            if default_cfg_item:
                self.restore_widget_value(default_cfg_item)

    def update_cfg_item_from_widget(self, widget: QtWidgets.QWidget):
        cfg_item = self.w2c.widget2config_dict.get(widget)
        value = get_widget_value(widget=widget)
        OmegaConf.update(self.cfg, cfg_item, value)

    def _widget_link(self, widget: QtWidgets.QWidget):
        return partial(self.update_cfg_item_from_widget, widget)

    def register_widget_changes_to_cfg(self):
        for widget in self.w2c.all_widgets:
            if isinstance(
                widget,
                (
                    QtWidgets.QDoubleSpinBox,
                    QtWidgets.QSpinBox,
                    QtWidgets.QProgressBar,
                ),
            ):
                widget.valueChanged.connect(self._widget_link(widget))
            elif isinstance(widget, QtWidgets.QComboBox):
                widget.currentTextChanged.connect(self._widget_link(widget))
            elif isinstance(widget, QtWidgets.QLineEdit):
                widget.textChanged.connect(self._widget_link(widget))
            elif isinstance(widget, QtWidgets.QCheckBox):
                widget.stateChanged.connect(self._widget_link(widget))

    def get_widget(self, cfg_item: str) -> QtWidgets.QWidget:
        assert (
            cfg_item in self.w2c.all_cfg_items
        ), f'Invalid cfg item: {cfg_item}'
        return self.w2c._find_widget(cfg_item)

    def get_widget_value(self, cfg_item: str):
        return get_widget_value(widget=self.get_widget(cfg_item))

    def set_widget_value(self, cfg_item: str, value):
        set_widget_value(widget=self.get_widget(cfg_item), value=value)

    def restore_widget_value(self, cfg_item: str):
        set_widget_value(
            widget=self.get_widget(cfg_item), value=self.get_value(cfg_item)
        )

    def get_cfg_item(self, widget: QtWidgets.QWidget) -> DictConfig:
        assert widget in self.w2c.all_widgets
        return self.w2c._find_config_item(widget)

    def get_value(self, cfg_item: str, typing=None) -> Union[Any, list[Any]]:
        value = OmegaConf.select(self.cfg, cfg_item)
        if value is None and typing == Union[str, None]:
            value = ''
        if value is None and typing == Union[int, float]:
            value = 0

        if typing == str:
            return str(value)
        elif typing == float:
            return float(value)
        elif typing == int:
            return int(value)

        if 'group' in cfg_item and value:
            value = list(value)
        return value

    def set_value(self, cfg_item: str, value):
        if value is not None:
            OmegaConf.update(self.cfg, cfg_item, value)

    def toggle_buttons(self, buttons: Iterable, set_enabled: bool = False):
        for button in buttons:
            self.button(button).setEnabled(set_enabled)

    def fp_lock(
        self,
        cfg_fps: Union[list, tuple, str],
        buttons_id_to_release: Union[list, tuple, Any],
    ):
        if isinstance(cfg_fps, str):
            cfg_fps = tuple([cfg_fps])

        if not isinstance(buttons_id_to_release, (list, tuple)):
            buttons_id_to_release = [buttons_id_to_release]

        self.toggle_buttons(buttons=buttons_id_to_release, set_enabled=False)

        for cfg_fp in cfg_fps:
            _fp = self.get_value(cfg_fp)
            logging.info(f'Checking file path: {_fp}')
            if not _fp or not dirname_does_exist(_fp):
                logging.warning(f'The dirname of `{_fp}` is not valid.')
                return
            else:
                if not filepath_does_exists(_fp):
                    logging.warning(f'The file `{_fp}` is not valid.')
                else:
                    logging.info(f'The file `{_fp}` is valid.')

        self.toggle_buttons(buttons=buttons_id_to_release, set_enabled=True)

    def button(self, id: str):
        assert id in self.w2c.run_buttons
        return self.w2c.run_buttons[id]


class Widget2ConfigMapper:
    def __init__(self, ui):
        self.ui = ui

        self.group_config_map: list[tuple[Any, Union[str, tuple[str]]]] = [
            (self.ui.comboBox_cmap, CallableGroupValues.ColorMap),
            (
                self.ui.comboBox_cluster_matrix,
                CallableGroupValues.score_matrix,
            ),
            (
                self.ui.comboBox_sidechain_solver,
                'ui.config.sidechain_solver.group',
            ),
            (
                self.ui.comboBox_profile_type,
                ('profile.group', 'designer.group'),
            ),
            (
                self.ui.comboBox_profile_type_2,
                ('profile.group', 'designer.group'),
            ),
            (
                self.ui.comboBox_external_scorer,
                'designer.group',
            ),
        ]
        self.run_buttons: dict[str, Any] = {
            'submit_pssm_gremlin_job': self.ui.pushButton_submit_pssm_gremlin_job,
            'cancel_pssm_gremlin_job': self.ui.pushButton_cancel_pssm_gremlin_job,
            'download_pssm_gremlin_job': self.ui.pushButton_download_pssm_gremlin_job,
            'open_output_pse_pocket': self.ui.pushButton_open_output_pse_pocket,
            'open_output_pse_surface': self.ui.pushButton_open_output_pse_surface,
            'run_surface_refresh': self.ui.pushButton_run_surface_refresh,
            'dump_interfaces': self.ui.pushButton_dump_interfaces,
            'run_surface_detection': self.ui.pushButton_run_surface_detection,
            'run_pocket_detection': self.ui.pushButton_run_pocket_detection,
            'open_output_pse_mutate': self.ui.pushButton_open_output_pse_mutate,
            'open_customized_indices': self.ui.pushButton_open_customized_indices,
            'open_input_csv': self.ui.pushButton_open_input_csv,
            'run_PSSM_to_pse': self.ui.pushButton_run_PSSM_to_pse,
            'open_mut_table': self.ui.pushButton_open_mut_table,
            'reinitialize_mutant_choosing': self.ui.pushButton_reinitialize_mutant_choosing,
            'goto_best_hit_in_group': self.ui.pushButton_goto_best_hit_in_group,
            'load_mutant_choice_checkpoint': self.ui.pushButton_load_mutant_choice_checkpoint,
            'choose_lucky_mutant': self.ui.pushButton_choose_lucky_mutant,
            'previous_mutant': self.ui.pushButton_previous_mutant,
            'next_mutant': self.ui.pushButton_next_mutant,
            'reject_this_mutant': self.ui.pushButton_reject_this_mutant,
            'accept_this_mutant': self.ui.pushButton_accept_this_mutant,
            'open_mut_table_2': self.ui.pushButton_open_mut_table_2,
            'run_cluster': self.ui.pushButton_run_cluster,
            'save_this_mutant_table': self.ui.pushButton_save_this_mutant_table,
            'open_input_csv_2': self.ui.pushButton_open_input_csv_2,
            'open_mut_table_csv': self.ui.pushButton_open_mut_table_csv,
            'open_output_pse_visualize': self.ui.pushButton_open_output_pse_visualize,
            'run_visualizing': self.ui.pushButton_run_visualizing,
            'reduce_this_session': self.ui.pushButton_reduce_this_session,
            'open_mut_table_csv_2': self.ui.pushButton_open_mut_table_csv_2,
            'multi_design_initialize': self.ui.pushButton_multi_design_initialize,
            'multi_design_start_new_design': self.ui.pushButton_multi_design_start_new_design,
            'multi_design_left': self.ui.pushButton_multi_design_left,
            'multi_design_right': self.ui.pushButton_multi_design_right,
            'multi_design_end_this_design': self.ui.pushButton_multi_design_end_this_design,
            'multi_design_export_mutants_from_table': self.ui.pushButton_multi_design_export_mutants_from_table,
            'run_multi_design': self.ui.pushButton_run_multi_design,
            'open_gremlin_mtx': self.ui.pushButton_open_gremlin_mtx,
            'reinitialize_interact': self.ui.pushButton_reinitialize_interact,
            'run_interact_scan': self.ui.pushButton_run_interact_scan,
            'open_save_mutant_table': self.ui.pushButton_open_save_mutant_table,
            'interact_reject': self.ui.pushButton_interact_reject,
            'interact_accept': self.ui.pushButton_interact_accept,
            'ws_generate_randomized_key': self.ui.pushButton_ws_generate_randomized_key,
            'ws_connect_to_server': self.ui.pushButton_ws_connect_to_server,
            'ws_disconnect_from_server': self.ui.pushButton_ws_disconnect_from_server,
            'previous': self.ui.pushButton_previous,
            'next': self.ui.pushButton_next,
        }
        self.widget_config_map = [
            (self.ui.comboBox_cmap, 'ui.header_panel.cmap.default'),
            (
                self.ui.lineEdit_pssm_gremlin_url,
                'ui.client.pssm_gremlin_url',
            ),
            (
                self.ui.lineEdit_pssm_gremlin_user,
                'ui.client.pssm_gremlin_user',
            ),
            (
                self.ui.lineEdit_pssm_gremlin_passwd,
                'ui.client.pssm_gremlin_passwd',
            ),
            (
                self.ui.doubleSpinBox_cofactor_radius,
                'ui.prepare.cofactor_radius',
            ),
            (
                self.ui.doubleSpinBox_ligand_radius,
                'ui.prepare.ligand_radius',
            ),
            (
                self.ui.doubleSpinBox_interface_cutoff,
                'ui.prepare.chain_dist',
            ),
            (
                self.ui.doubleSpinBox_surface_cutoff,
                'ui.prepare.surface_probe_radius',
            ),
            (
                self.ui.checkBox_reverse_mutant_effect,
                'ui.mutate.reverse_score',
            ),
            (self.ui.lineEdit_score_maxima, 'ui.mutate.max_score'),
            (self.ui.lineEdit_score_minima, 'ui.mutate.min_score'),
            (self.ui.lineEdit_reject_substitution, 'ui.mutate.reject'),
            (self.ui.lineEdit_preffer_substitution, 'ui.mutate.accept'),
            (
                self.ui.spinBox_randomized_sampling,
                'ui.mutate.designer.randomized_sampling',
            ),
            (
                self.ui.checkBox_randomized_sampling,
                'ui.mutate.designer.enable_randomized_sampling',
            ),
            (
                self.ui.checkBox_deduplicate_designs,
                'ui.mutate.designer.deduplicate_designs',
            ),
            (
                self.ui.checkBox_designer_homooligomeric,
                'ui.mutate.designer.homooligomeric',
            ),
            (
                self.ui.spinBox_designer_batch,
                'ui.mutate.designer.batch',
            ),
            (
                self.ui.spinBox_designer_num_samples,
                'ui.mutate.designer.num_sample',
            ),
            (
                self.ui.doubleSpinBox_designer_temperature,
                'ui.mutate.designer.temperature',
            ),
            (
                self.ui.comboBox_cluster_matrix,
                'ui.cluster.score_matrix.default',
            ),
            (self.ui.checkBox_shuffle_clustering, 'ui.cluster.shuffle'),
            (self.ui.spinBox_num_mut_maximum, 'ui.cluster.mut_num_max'),
            (self.ui.spinBox_num_mut_minimun, 'ui.cluster.mut_num_min'),
            (self.ui.spinBox_num_cluster, 'ui.cluster.num_cluster'),
            (
                self.ui.spinBox_cluster_batchsize,
                'ui.cluster.batch_size',
            ),
            (
                self.ui.checkBox_reverse_mutant_effect_3,
                'ui.visualize.reverse_score',
            ),
            (
                self.ui.checkBox_global_score_policy,
                'ui.visualize.global_score_policy',
            ),
            (
                self.ui.checkBox_interact_ignore_wt,
                'ui.interact.interact_ignore_wt',
            ),
            (self.ui.spinBox_gremlin_topN, 'ui.interact.topN_pairs'),
            (
                self.ui.doubleSpinBox_max_interact_dist,
                'ui.interact.max_interact_dist',
            ),
            (
                self.ui.comboBox_external_scorer,
                'ui.interact.use_external_scorer',
            ),
            (
                self.ui.lineEdit_ws_server_url_to_connect,
                'ui.socket.server_url',
            ),
            (self.ui.checkBox_ws_server_mode, 'ui.socket.server_mode'),
            (self.ui.spinBox_ws_server_port, 'ui.socket.server_port'),
            (self.ui.checkBox_ws_server_use_key, 'ui.socket.use_key'),
            (
                self.ui.doubleSpinBox_ws_view_broadcast_interval,
                'ui.socket.broadcast.interval',
            ),
            (
                self.ui.checkBox_ws_broadcast_view,
                'ui.socket.broadcast.view',
            ),
            (
                self.ui.checkBox_ws_recieve_mutagenesis_broadcast,
                'ui.socket.receive.mutagenesis',
            ),
            (
                self.ui.checkBox_ws_recieve_view_broadcast,
                'ui.socket.receive.view',
            ),
            (
                self.ui.comboBox_sidechain_solver,
                'ui.config.sidechain_solver.default',
            ),
            (
                self.ui.doubleSpinBox_sidechain_solver_radius,
                'ui.config.sidechain_solver.repack_radius',
            ),
            (
                self.ui.comboBox_sidechain_solver_model,
                'ui.config.sidechain_solver.model',
            ),
            # inputs:
            ## header
            (
                self.ui.comboBox_design_molecule,
                'ui.header_panel.input.molecule',
            ),
            (self.ui.comboBox_chain_id, 'ui.header_panel.input.chain_id'),
            (self.ui.spinBox_nproc, 'ui.header_panel.nproc'),
            # prepare
            (
                self.ui.lineEdit_output_pse_pocket,
                'ui.prepare.input.pocket.to_pse',
            ),
            (self.ui.comboBox_ligand_sel, 'ui.prepare.input.pocket.substrate'),
            (
                self.ui.comboBox_cofactor_sel,
                'ui.prepare.input.pocket.cofactor',
            ),
            (
                self.ui.lineEdit_output_pse_surface,
                'ui.prepare.input.surface.to_pse',
            ),
            (
                self.ui.comboBox_surface_exclusion,
                'ui.prepare.input.surface.exclusion',
            ),
            # mutate
            (self.ui.lineEdit_output_pse_mutate, 'ui.mutate.input.to_pse'),
            (self.ui.lineEdit_input_csv, 'ui.mutate.input.profile'),
            (self.ui.comboBox_profile_type, 'ui.mutate.input.profile_type'),
            (self.ui.lineEdit_design_case, 'ui.mutate.input.design_case'),
            (
                self.ui.lineEdit_input_customized_indices,
                'ui.mutate.input.residue_ids',
            ),
            # evaluate
            (
                self.ui.lineEdit_output_mut_table,
                'ui.evaluate.input.to_mutant_txt',
            ),
            (
                self.ui.checkBox_rock_pymol,
                'ui.evaluate.rock',
            ),
            (
                self.ui.checkBox_show_wt,
                'ui.evaluate.show_wt',
            ),
            (
                self.ui.checkBox_reverse_mutant_effect_2,
                'ui.evaluate.reverse_score',
            ),
            # cluster
            (
                self.ui.lineEdit_input_mut_table,
                'ui.cluster.input.from_mutant_txt',
            ),
            # visualize
            (
                self.ui.lineEdit_output_pse_visualize,
                'ui.visualize.input.to_pse',
            ),
            (
                self.ui.lineEdit_input_mut_table_csv,
                'ui.visualize.input.from_mutant_txt',
            ),
            (self.ui.lineEdit_input_csv_2, 'ui.visualize.input.profile'),
            (
                self.ui.comboBox_profile_type_2,
                'ui.visualize.input.profile_type',
            ),
            (self.ui.lineEdit_group_name, 'ui.visualize.input.group_name'),
            (self.ui.comboBox_best_leaf, 'ui.visualize.input.best_leaf'),
            (self.ui.comboBox_totalscore, 'ui.visualize.input.totalscore'),
            (
                self.ui.lineEdit_multi_design_mutant_table,
                'ui.visualize.input.multi_design.to_mutant_txt',
            ),
            # interact
            (
                self.ui.lineEdit_input_gremlin_mtx,
                'ui.interact.input.gremlin_pkl',
            ),
            (
                self.ui.lineEdit_output_mutant_table,
                'ui.interact.input.to_mutant_txt',
            ),
            # socket
            (self.ui.lineEdit_ws_server_key, 'ui.socket.input.key'),
            (
                self.ui.lineEdit_ws_server_url_to_connect,
                'ui.socket.input.hostname',
            ),
            # # foot
            # (self.ui.lineEdit_ws_server_key, 'ui.footer_panel.progressbar'),
        ]

    @property
    def all_widgets(self) -> tuple[QtWidgets.QWidget]:
        return [w2c_pair[0] for w2c_pair in self.widget_config_map]

    @property
    def all_cfg_items(self) -> tuple[str]:
        return [w2c_pair[1] for w2c_pair in self.widget_config_map]

    @property
    def widget2config_dict(self) -> immutabledict:
        return immutabledict({i: j for (i, j) in self.widget_config_map})

    @property
    def config2widget_dict(self) -> immutabledict:
        return immutabledict({j: i for (i, j) in self.widget_config_map})

    def _find_config_item(self, ui_element):
        config_item = self.widget2config_dict.get(ui_element)
        # print(f'{ui_element} -> {config_item}')
        return config_item

    def _find_widget(self, config_item: str):
        ui_element = self.config2widget_dict.get(config_item)
        # print(f'{config_item} -> {ui_element}')
        return ui_element


@dataclass
class Widget2Widget:
    sidechain_solver2model = {
        'PIPPack': [
            'ui.config.sidechain_solver.pippack.model_names.group',
            'ui.config.sidechain_solver.pippack.model_names.default',
        ],
        'DLPacker': [''],
        'Dunbrack Rotamer Library': [''],
    }


class CallableGroupValues:
    @staticmethod
    def score_matrix() -> list:
        from Bio.Align import substitution_matrices
        import os

        score_matrix = [
            mtx
            for mtx in os.listdir(
                os.path.join(substitution_matrices.__path__[0], 'data')
            )
        ]
        return score_matrix

    @staticmethod
    def ColorMap() -> dict:
        # color map
        import matplotlib
        from pymol.Qt import QtGui

        cmap_group = {
            _cmap: QtGui.QIcon(create_cmap_icon(cmap=_cmap))
            for _cmap in matplotlib.colormaps()
        }
        return cmap_group
