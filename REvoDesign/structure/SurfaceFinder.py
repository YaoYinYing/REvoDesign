from __future__ import print_function
from pymol import cmd
import os
from REvoDesign.common.RunnerConfig import REvoDesignRunnerConfig
from REvoDesign.REvoDesign import logging as logger
from attrs import define, field

logging = logger.getChild(__name__)

'''
This is a slightly modified version of the code on: 
http://pymolwiki.org/index.php/FindSurfaceResidues
'''


@define(kw_only=True)
class SurfaceFinderConfig(REvoDesignRunnerConfig):
    exclude_residue_selection: str = field(converter=str, default='')
    cutoff: float = field(converter=float, default=15)
    do_show_surf_CA: bool = field(converter=bool, default=True)


def findSurfaceAtoms(selection="all", cutoff=2.5, quiet=1):
    """
    DESCRIPTION

        Finds those atoms on the surface of a protein
        that have at least 'cutoff' exposed A**2 surface area.

    USAGE

        findSurfaceAtoms [ selection, [ cutoff ]]

    SEE ALSO

        findSurfaceResidues
    """
    cutoff, quiet = float(cutoff), int(quiet)

    tmpObj = cmd.get_unused_name("_tmp")
    cmd.create(tmpObj, "(" + selection + ") and polymer", zoom=0)

    cmd.set("dot_solvent", 1, tmpObj)
    # get per-atom surface area and store it in b-factor
    cmd.get_area(selection=tmpObj, load_b=1)

    # threshold on what one considers an "exposed" atom (in A**2):
    cmd.remove(tmpObj + " and b < " + str(cutoff))

    selName = cmd.get_unused_name("exposed_atm_")
    cmd.select(selName, "(" + selection + ") in " + tmpObj)

    cmd.delete(tmpObj)

    if not quiet:
        print("Exposed atoms are selected in: " + selName)

    return selName


def findSurfaceResidues(
    selection="all", cutoff=2.5, doShow=0, quiet=1, return_selection=1
):
    """
    DESCRIPTION

        Finds those residues on the surface of a protein
        that have at least 'cutoff' exposed A**2 surface area.

    USAGE

        findSurfaceResidues [ selection, [ cutoff, [ doShow ]]]

    ARGUMENTS

        selection = string: object or selection in which to find exposed
        residues {default: all}

        cutoff = float: cutoff of what is exposed or not {default: 2.5 Ang**2}

    RETURNS

        (list: (chain, resv ) )
            A Python list of residue numbers corresponding
            to those residues w/more exposure than the cutoff.

    """
    cutoff, doShow, quiet = float(cutoff), int(doShow), int(quiet)

    selName = findSurfaceAtoms(selection, cutoff, quiet)

    exposed = set()
    cmd.iterate(selName, "exposed.add((chain,resv))", space=locals())

    selNameRes = cmd.get_unused_name("exposed_res_")
    cmd.select(selNameRes, "byres " + selName)

    if not quiet:
        print("Exposed residues are selected in: " + selNameRes)

    if doShow:
        cmd.show_as("spheres", "(" + selection + ") and polymer")
        cmd.color("white", selection)
        cmd.color("yellow", selNameRes)
        cmd.color("red", selName)

    if not return_selection:
        return sorted(exposed)
    else:
        return selNameRes


cmd.extend("findSurfaceAtoms", findSurfaceAtoms)
cmd.extend("findSurfaceResidues", findSurfaceResidues)


@define(kw_only=True)
class SurfaceFinder(SurfaceFinderConfig):
    def process_surface_residues(self):
        cmd.save(self.input_pse)
        logging.debug(
            f'exclude_residue_selection = {self.exclude_residue_selection}'
        )

        if (
            self.exclude_residue_selection
            or self.exclude_residue_selection != ''
        ):
            sel_exclude_residue_selection = (
                f'and (not {self.exclude_residue_selection})'
            )
            ray_selection_list = [
                self.exclude_residue_selection,
                self.molecule,
            ]
        else:
            sel_exclude_residue_selection = ''
            ray_selection_list = [self.molecule]

        if self.do_show_surf_CA:
            cmd.disable('all')
            cmd.enable(self.molecule)
            cmd.set('sphere_scale', 0.5)

        molecule_selection = f'{self.molecule} and c. {self.chain_id}'

        cmd.scene('initial_scene', 'store')

        os.makedirs(
            'surface_residue_records', exist_ok=True
        )  # Create a directory for residue records

        cmd.scene('initial_scene')
        surface_selection = findSurfaceResidues(
            selection=self.molecule, cutoff=self.cutoff, return_selection=1
        )

        ner_ca_selection = f'ner_ca_{self.cutoff}'
        er_ca_selection = f'er_ca_{self.cutoff}'

        cmd.create(
            ner_ca_selection,
            f'{molecule_selection} and (not {surface_selection}) and n. CA {sel_exclude_residue_selection}',
        )
        cmd.create(
            er_ca_selection,
            f'{molecule_selection} and {surface_selection} and n. CA {sel_exclude_residue_selection}',
        )

        if self.do_show_surf_CA:
            cmd.hide('everything', f'{ner_ca_selection} or {er_ca_selection}')
            cmd.show('spheres', ner_ca_selection)
            cmd.set('sphere_color', 'salmon', ner_ca_selection)
            cmd.show('spheres', er_ca_selection)
            cmd.set('sphere_color', 'aquamarine', er_ca_selection)

        for obj in ray_selection_list:
            cmd.zoom(obj)
            scene_id = f'{obj[:20]}_cutoff_{self.cutoff}'
            cmd.refresh()
            cmd.scene(
                scene_id, 'store', message=f'surface_cutoff: {self.cutoff}'
            )

        cmd.refresh()

        # Save residue IDs to a text file
        surface_residue_ids = list(
            set(
                [
                    int(atom.resi)
                    for atom in cmd.get_model(er_ca_selection).atom
                ]
            )
        )
        surface_residue_ids.sort()
        residue_filename = os.path.join(
            'surface_residue_records',
            f'{self.molecule}_residues_cutoff_{self.cutoff}.txt',
        )
        with open(residue_filename, 'w') as f:
            f.write(','.join(map(str, surface_residue_ids)))

        if self.do_show_surf_CA:
            cmd.hide('spheres', f'{ner_ca_selection} or {er_ca_selection}')

        cmd.save(self.output_pse)
