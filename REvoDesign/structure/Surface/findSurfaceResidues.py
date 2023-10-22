'''
This is a slightly modified version of the code on: 
http://pymolwiki.org/index.php/FindSurfaceResidues
'''

from __future__ import print_function
from pymol import cmd
from Bio.Data import IUPACData
import os
from absl import logging


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


def determine_surface_residue(
    input_file,
    output_file,
    molecule,
    chain_id='A',
    exclude_residue_selection='',
    cutoff=15,
    do_show_surf_CA=True,
):
    # cmd.reinitialize()
    # cmd.load(input_file)
    cmd.save(input_file)

    logging.debug(f'exclude_residue_selection = {exclude_residue_selection}')

    if exclude_residue_selection or exclude_residue_selection != '':
        _sel_exclude_residue_selection = (
            f'and (not {exclude_residue_selection})'
        )
        ray_selection_list = [exclude_residue_selection, molecule]
    else:
        _sel_exclude_residue_selection = ''
        ray_selection_list = [molecule]

    if do_show_surf_CA:
        cmd.disable('all')
        cmd.enable(molecule)
        cmd.set('sphere_scale', 0.5)

    molecule = f'{molecule} and c. {chain_id}'

    cmd.scene('test_initial', 'store')

    os.makedirs(
        'surface_residue_records', exist_ok=True
    )  # Create a directory for residue records

    cmd.scene('test_initial')
    surface_selection = findSurfaceResidues(
        selection=molecule, cutoff=cutoff, return_selection=1
    )

    logging.debug(
        f'{molecule} and (not {surface_selection} ) and n. CA {_sel_exclude_residue_selection}'
    )

    cmd.create(
        f'ner_ca_{cutoff}',
        f'{molecule} and (not {surface_selection} ) and n. CA {_sel_exclude_residue_selection}',
    )
    cmd.create(
        f'er_ca_{cutoff}',
        f'{molecule} and {surface_selection} and n. CA {_sel_exclude_residue_selection}',
    )

    if do_show_surf_CA:
        cmd.hide('everything', f'ner_ca_{cutoff} or er_ca_{cutoff}')

        cmd.show('spheres', f'ner_ca_{cutoff}')
        cmd.set('sphere_color', 'salmon', f'ner_ca_{cutoff}')

        cmd.show('spheres', f'er_ca_{cutoff}')
        cmd.set('sphere_color', 'aquamarine', f'er_ca_{cutoff}')

    for _obj in ray_selection_list:
        cmd.zoom(_obj)
        scene_id = f'{_obj[:20]}_cutoff_{cutoff}'
        cmd.refresh()
        cmd.scene(scene_id, 'store', message=f'surface_cutoff: {cutoff}')

    cmd.refresh()

    # Save residue IDs to a text file
    surface_residue_ids = list(
        set([int(atom.resi) for atom in cmd.get_model(f'er_ca_{cutoff}').atom])
    )
    surface_residue_ids.sort()
    residue_filename = os.path.join(
        'surface_residue_records', f'residues_cutoff_{cutoff}.txt'
    )
    with open(residue_filename, 'w') as f:
        f.write(','.join(map(str, surface_residue_ids)))

    if do_show_surf_CA:
        cmd.hide('spheres', f'ner_ca_{cutoff} or er_ca_{cutoff}')

    cmd.save(output_file)
