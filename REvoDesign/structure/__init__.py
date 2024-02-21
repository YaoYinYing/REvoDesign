from REvoDesign.tools.pymol_utils import fetch_exclusion_expressions, find_all_protein_chain_ids_in_protein, find_small_molecules_in_protein
from pymol import cmd
from attrs import define, field


@define(kw_only=True)
class StuctureRunner:
    design_molecule: str=field(converter=str)
    design_chain_id: str=field(converter=str)

    def reload_determine_tab_setup(
        self,
    ):
        # Setup pocket determination arguments
        small_molecules = find_small_molecules_in_protein(self.design_molecule)
        if small_molecules:
            self.bus.set_widget_value(
                'ui.prepare.input.pocket.substrate', small_molecules
            )
            self.bus.set_widget_value(
                'ui.prepare.input.pocket.cofactor', small_molecules
            )

    def update_surface_exclusion(self):
        exclusion_list = fetch_exclusion_expressions()

        self.bus.set_widget_value(
            'ui.prepare.input.surface.exclusion', exclusion_list
        )
        if exclusion_list:
            self.bus.get_widget(
                'ui.prepare.input.surface.exclusion'
            ).setCurrentIndex(0)

    def run_chain_interface_detection(self):
        molecule = self.bus.get_value('ui.header_panel.input.molecule')
        radius = self.bus.get_value('ui.prepare.chain_dist', float)
        chain_ids = find_all_protein_chain_ids_in_protein(molecule)
        if not chain_ids or len(chain_ids) <= 1:
            return

        for chain_id in chain_ids:
            cmd.select(
                f'if_{chain_id}',
                f'({molecule} and c. {chain_id} ) and byres ({molecule} and polymer.protein and (not c. {chain_id})) around {radius} and polymer.protein',
            )

    def run_surface_detection(self):
        input_file = self.temperal_session
        output_file = self.bus.get_value('ui.prepare.input.surface.to_pse')

        exclusion = self.bus.get_value('ui.prepare.input.surface.exclusion')
        cutoff = self.bus.get_value('ui.prepare.surface_probe_radius', float)
        do_show_surf_CA = True

        from REvoDesign.structure.SurfaceFinder import SurfaceFinder

        surfacefinder = SurfaceFinder(
            input_file=input_file,
            output_file=output_file,
            molecule=self.design_molecule,
            chain_id=self.design_chain_id,
        )

        surfacefinder.cutoff = cutoff
        surfacefinder.exclude_residue_selection = exclusion
        surfacefinder.do_show_surf_CA = do_show_surf_CA

        surfacefinder.process_surface_residues()

    def run_pocket_detection(self):
        input_file = self.temperal_session
        output_file = self.bus.get_value('ui.prepare.input.pocket.to_pse')
        ligand = self.bus.get_value('ui.prepare.input.pocket.substrate')
        cofactor = self.bus.get_value('ui.prepare.input.pocket.cofactor')
        ligand_radius = self.bus.get_value('ui.prepare.ligand_radius', float)
        cofactor_radius = self.bus.get_value(
            'ui.prepare.cofactor_radius', float
        )

        from REvoDesign.structure.PocketSearcher import PocketSearcher

        pocketsearcher = PocketSearcher(
            input_file=input_file,
            output_file=output_file,
            molecule=self.design_molecule,
            ligand=ligand,
        )

        pocketsearcher.chain_id = self.design_chain_id

        pocketsearcher.ligand_radius = ligand_radius
        pocketsearcher.cofactor = cofactor
        pocketsearcher.cofactor_radius = cofactor_radius

        pocketsearcher.save_dir = f'{self.PWD}/pockets/'
        pocketsearcher.search_pockets()