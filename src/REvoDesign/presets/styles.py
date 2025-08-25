from typing import Optional
from pymol import cmd
def visualize_hydrophobic_hydrophilic(
    pdb_id: Optional[str] = None,
    remove_hoh: bool = True,
    rezoom: bool = True,
    reorient: bool = True
):
    """
    Visualize the hydrophobic and hydrophilic regions of a protein structure in PyMOL.
    Args:
        pdb_id (Optional[str]): PDB ID of the protein structure to fetch and visualize.
                                If None, assumes a protein model is already loaded.
        remove_hoh (bool): Whether to remove water molecules (resn HOH). Default is True.
        rezoom (bool): Whether to zoom in on the protein after processing. Default is True.
        reorient (bool): Whether to orient the protein after processing. Default is True.
    """
    if pdb_id is not None:
        cmd.reinitialize()
        cmd.fetch(pdb_id)
    if remove_hoh:
        cmd.select("water", "resn HOH")
        cmd.remove("water")
    hydrophobic_residues = "ala+gly+val+ile+leu+phe+met"
    cmd.select("hydrophobic", f"resn {hydrophobic_residues}")
    cmd.show("sticks", "hydrophobic and (!name c+n+o)")
    cmd.color("yelloworange", "hydrophobic")
    cmd.select("hydrophilic", "!hydrophobic and (!name c+n+o)")
    cmd.show("sticks", "hydrophilic")
    cmd.color("lightblue", "hydrophilic")
    cmd.color("white", "bb.")
    cmd.color("oxygen", "elem o")
    cmd.color("nitrogen", "elem N")
    cmd.color("sulfur", "elem S")
    cmd.set("ray_trace_mode", 3)
    cmd.set("stick_radius", 0.4)
    cmd.set("cartoon_loop_radius", 0.4)
    cmd.set("cartoon_oval_width", 0.4)
    cmd.set("cartoon_rect_width", 0.4)
    cmd.set("fog", 0)
    cmd.bg_color("white")
    cmd.set("valence", 0)
    cmd.set("ray_shadow", 0)
    if rezoom:
        cmd.zoom()
    if reorient:
        cmd.orient()
def visualize_cartoon_settings(
    pdb_id: Optional[str] = None,
    remove_hoh: bool = True,
    rezoom: bool = True,
    reorient: bool = True
):
    """
    Visualize protein structure with enhanced cartoon settings and rendering options in PyMOL.
    Args:
        pdb_id (Optional[str]): PDB ID of the protein structure to fetch and visualize.
                                If None, assumes a protein model is already loaded.
        remove_hoh (bool): Whether to remove water molecules (resn HOH). Default is True.
        rezoom (bool): Whether to zoom in on the protein after processing. Default is True.
        reorient (bool): Whether to orient the protein after processing. Default is True.
    """
    if pdb_id is not None:
        cmd.reinitialize()
        cmd.fetch(pdb_id)
    if remove_hoh:
        cmd.select("water", "resn HOH")
        cmd.remove("water")
    cmd.set("cartoon_loop_radius", 0.2)
    cmd.set("cartoon_oval_width", 0.2)
    cmd.set("cartoon_rect_width", 0.2)
    cmd.set("specular", "off")
    cmd.set("ray_trace_mode", 1)
    cmd.set("ray_trace_disco_factor", 1.0)
    cmd.set("ray_trace_gain", 0.0)
    cmd.set("ambient", 0.66)
    cmd.set("ray_shadow", 0)
    cmd.select("alpha_carbons", "name ca")
    cmd.show("spheres", "alpha_carbons")
    cmd.set("sphere_scale", 0)
    cmd.set("cartoon_side_chain_helper", 1)
    cmd.bg_color("white")
    cmd.color("gray80")
    if rezoom:
        cmd.zoom()
    if reorient:
        cmd.orient()
def visualize_cartoon_loops(
    pdb_id: Optional[str] = None,
    remove_hoh: bool = True,
    rezoom: bool = True,
    reorient: bool = True
):
    """
    Visualize protein cartoon loops with enhanced settings and spectrum coloring in PyMOL.
    Args:
        pdb_id (Optional[str]): PDB ID of the protein structure to fetch and visualize.
                                If None, assumes a protein model is already loaded.
        remove_hoh (bool): Whether to remove water molecules (resn HOH). Default is True.
        rezoom (bool): Whether to zoom in on the protein after processing. Default is True.
        reorient (bool): Whether to orient the protein after processing. Default is True.
    """
    if pdb_id is not None:
        cmd.reinitialize()
        cmd.fetch(pdb_id)
    if remove_hoh:
        cmd.select("water", "resn HOH")
        cmd.remove("water")
    cmd.cartoon("loop")
    cmd.set("cartoon_loop_radius", 1.5)
    cmd.spectrum()
    cmd.set("fog", 0)
    cmd.bg_color("white")
    cmd.set("valence", 0)
    cmd.set("ray_shadow", 0)
    cmd.set("ray_trace_mode", 3)
    if rezoom:
        cmd.zoom()
    if reorient:
        cmd.orient()