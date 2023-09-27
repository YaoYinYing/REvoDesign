import argparse
import os
from pymol import cmd

def read_enzyme_pockets(input_file, output_file, molecule, ligand, cofactor, save_dir,ligand_radius=6,cofactor_radius=7):
    """
    Read an existing structure file, analyze enzyme pockets, and save results.

    Parameters:
        input_file (str): Path to the input structure file (pdb/pse/pze).
        output_file (str): Path to the output session file (pze).
        obj (str): Object molecule ID.
        ligand (str): Ligand molecule ID.
        cofactor (str or None): Cofactor molecule ID or None.
        save_dir (str): Save directory path for pocket residue record.

    Example usage:
        python enzyme_pocket_analysis.py -i input.pdb -o output.pze --obj obj_id -lig ligand_id -cof cofactor_id -s save_dir
    """
    cmd.load(input_file)

    cmd.select('pkt_res', f'( {molecule} ) and byres hetatm around {ligand_radius}')
    cmd.select('pkt_res_lig', f'( {molecule} ) and (byres resn {ligand} around {cofactor_radius}) and polymer.protein')
    cmd.select('design_shell', f'( {molecule} ) and polymer.protein and (pkt_res_lig)')

    selections = ["pkt_res", "pkt_res_lig", "design_shell"]

    if cofactor is not None:
        cmd.select('pkt_res_cof', f'( {molecule} ) and (byres resn {cofactor} around 3) and polymer.protein')
        cmd.select('design_shell', f'design_shell and not (pkt_res_cof)')
        selections.append("pkt_res_cof")

    for i in selections:
        atoms = cmd.get_model(i)
        resi = list(set([int(atom.resi) for atom in atoms.atom]))
        resi.sort()

        # Save pocket residue records
        pocket_filename = os.path.join(save_dir, f"{i}_residues.txt")
        os.makedirs(os.path.dirname(pocket_filename), exist_ok=True)
        with open(pocket_filename, 'w') as f:
            f.write(','.join(map(str, resi)))

    # Save the session
    cmd.save(output_file)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Read existing structure file, analyze enzyme pockets, and save results.")
    parser.add_argument("-i", "--input", required=True, help="Path to the input structure file (pdb/pse/pze).")
    parser.add_argument("-o", "--output", required=True, help="Path to the output session file (pze).")
    parser.add_argument("--obj", required=True, help="Object molecule ID.")
    parser.add_argument("-lig", "--ligand", required=True, help="Ligand molecule ID.")
    parser.add_argument("-cof", "--cofactor", default=None, help="Cofactor molecule ID.")
    parser.add_argument("-s", "--save_dir", required=True, help="Save directory path for pocket residue record.")
    args = parser.parse_args()

    read_enzyme_pockets(args.input, args.output, args.obj, args.ligand, args.cofactor, args.save_dir)
