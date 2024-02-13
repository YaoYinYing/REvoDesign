from dataclasses import dataclass
from immutabledict import immutabledict


class Widget2ConfigMapper:
    def __init__(self, ui):
        self.ui = ui
        self.widget_config_map = [
            (self.ui.comboBox_cmap, 'ui.header_panel.cmap'),
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
            (self.ui.comboBox_profile_type, 'ui.profile.default'),
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
                'ui.cluster.score_matrix',
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
            (self.ui.comboBox_profile_type_2, 'ui.profile.default'),
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
            (   self.ui.comboBox_sidechain_solver_model,
                'ui.config.sidechain_solver.model')
        ]



        self.widget2config_dict = self._widget2config()
        self.config2widget_dict = self._config2widget()

    def _widget2config(self) -> immutabledict:
        return immutabledict({i: j for (i, j) in self.widget_config_map})

    def _config2widget(self) -> immutabledict:
        return immutabledict({j: i for (i, j) in self.widget_config_map})

    def _find_config_item(self, ui_element):
        config_item = self.widget2config_dict[ui_element]
        print(f'{ui_element} -> {config_item}')
        return config_item

    def _find_widget_item(self, config_item: str):
        ui_element = self.config2widget_dict[config_item]
        print(f'{config_item} -> {ui_element}')
        return ui_element
@dataclass
class Widget2Widget:
    sidechain_solver2model={

        'PIPPack':[
        'ui.config.sidechain_solver.pippack.model_names.group',
        'ui.config.sidechain_solver.pippack.model_names.default'
        ],
        'DLPacker': [''],
        'Dunbrack Rotamer Library': ['']

    }