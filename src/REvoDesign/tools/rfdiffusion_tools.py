import biotite.structure as struc
import biotite.structure.io as bsio
import matplotlib
import matplotlib.pyplot as plt
import numpy as np

from REvoDesign.basic import ThirdPartyModuleAbstract
from REvoDesign.bootstrap.set_config import is_package_installed
from REvoDesign.tools.utils import require_installed

matplotlib.use('Agg')


@require_installed
class SubstratePotentialVisualizer(ThirdPartyModuleAbstract):
    '''
    This Class helps to reproduce the Extended Data Fig. 6E of the RFdiffusion paper.

    '''
    name: str = 'SubstratePotentialVisualizer'
    installed: bool = is_package_installed('rfdiffusion')

    def __init__(
            self,
            pdb_path,
            lig_key,
            blur: bool = False,
            weight: float = 1,
            r_0: float = 8,
            d_0: float = 2,
            s: float = 1,
            eps: float = 1e-6,
            rep_r_0: float = 5,
            rep_s: float = 2,
            rep_r_min: float = 1):
        """
        Initializes the SubstratePotentialVisualizer.

        This class computes and visualizes a ligand-centered external potential field based on distance-dependent
        attractive and repulsive interactions. The external potential field is modeled similarly to the implicit
        potentials used in protein-ligand interaction modeling, as implemented in the `substrate_contacts` class.

        Args:
            pdb_path (str):
                Path to the input PDB file containing the protein-ligand complex.
                The ligand must be properly defined with connectivity.

            lig_key (str):
                Residue name of the ligand (e.g., "ATP", "HEM"), used to extract ligand coordinates from the PDB file.

            blur (bool, default=False):
                If True, applies a Gaussian blur to the potential map. This can help smooth out the potential
                field and make it easier to visualize.

            weight (float, default=1):
                Scaling factor for the total potential energy. Higher values increase the influence of the external
                potential on the diffusion process.

            r_0 (float, default=8 Å):
                Defines the maximum range of attractive interactions. Beyond this distance, the attraction potential
                smoothly decays.

                - **Biological relevance**: This represents an approximate range where ligand-protein interactions
                  are significant in molecular docking.
                - **Mathematical definition**: Serves as a normalization factor in the distance-dependent
                  contact energy function.

            d_0 (float, default=2 Å):
                Defines the preferred contact distance for attractive interactions. At distances **d < d_0**,
                the attractive potential plateaus.

                - **Biological relevance**: Represents the optimal distance for stabilizing hydrogen bonds and
                  hydrophobic contacts.
                - **Mathematical role**: Appears in the `contact_energy(d, d_0, r_0)` function as the reference
                  contact distance.

            s (float, default=1):
                Scaling factor for the attractive contact potential. Larger values make attractive interactions
                stronger relative to repulsion.

                - **Biological relevance**: Controls the relative weight of hydrophobic and van der Waals interactions.
                - **Mathematical role**: Appears as a multiplicative factor in the attractive energy term.

            eps (float, default=1e-6):
                Small constant added to prevent division by zero in energy calculations.

                - **Mathematical role**: Regularization term in the denominator of the attraction function.

            rep_r_0 (float, default=5 Å):
                Defines the onset of repulsive interactions. If the distance between a ligand atom and a protein atom
                is **d < rep_r_0**, a repulsive force is applied.

                - **Biological relevance**: Prevents steric clashes by modeling atomic repulsion.
                - **Mathematical role**: Acts as the threshold in the `poly_repulse(d, rep_r_0, rep_s)` function.

            rep_s (float, default=2):
                Scaling factor for the repulsive potential. Larger values make steric repulsions stronger.

                - **Biological relevance**: Controls the penalty for steric clashes in ligand binding.
                - **Mathematical role**: Appears in the polynomial repulsion function.

            rep_r_min (float, default=1 Å):
                Defines the minimum repulsion distance. When **d < rep_r_min**, repulsion is maximized.

                - **Biological relevance**: Prevents unrealistic ligand placements inside protein cores.
                - **Mathematical role**: Defines a lower bound for steric clash penalties.

        Summary:
        ----------
        This model assumes that **ligand atoms influence the diffusion process** by introducing distance-dependent
        energetic constraints. The external potential is a sum of:
        - **Attractive potential**: Encourages residues to approach ligand atoms up to a certain threshold.
        - **Repulsive potential**: Prevents steric clashes when residues come too close.

        This potential framework is useful for **enzyme active site design, protein-ligand binding modeling, and
        small-molecule docking simulations**.
        """
        from rfdiffusion.potentials.potentials import substrate_contacts

        self.pdb_path = pdb_path
        self.lig_key = lig_key
        self.blur = blur
        self.weight = weight
        self.r_0 = r_0
        self.d_0 = d_0
        self.s = s
        self.eps = eps
        self.rep_r_0 = rep_r_0
        self.rep_s = rep_s
        self.rep_r_min = rep_r_min

        self.ligand_coords, self.ligand_bonds, self.ligand_elements = self.load_ligand()
        self.align_to_principal_axes()
        self.potential_calculator = substrate_contacts(
            weight=self.weight, r_0=self.r_0, d_0=self.d_0, s=self.s,
            eps=self.eps, rep_r_0=self.rep_r_0, rep_s=self.rep_s, rep_r_min=self.rep_r_min
        )

    def load_ligand(self):
        """Loads ligand atomic coordinates, connectivity, and element types."""
        structure = bsio.load_structure(self.pdb_path, model=1)
        ligand_atoms = structure[structure.res_name == self.lig_key]
        if len(ligand_atoms) == 0:
            raise ValueError(f"Ligand '{self.lig_key}' not found in PDB file: {self.pdb_path}")

        ligand_coords = ligand_atoms.coord.astype(float)
        ligand_elements = ligand_atoms.element
        bonds = struc.connect_via_residue_names(ligand_atoms)

        return ligand_coords, bonds, ligand_elements

    def align_to_principal_axes(self):
        """Uses PCA to rotate the ligand so that its principal axis aligns with the Z-axis."""
        from sklearn.decomposition import PCA

        pca = PCA(n_components=3)
        pca.fit(self.ligand_coords)
        rotation_matrix = pca.components_.T
        self.ligand_coords = np.dot(self.ligand_coords - np.mean(self.ligand_coords, axis=0), rotation_matrix)

    def compute_potential_field(self, grid_size=200, margin=10):
        """
        Computes the substrate potential field around the ligand.
        Uses a high-resolution grid and applies a strong Gaussian blur.
        """
        import torch
        from scipy.ndimage import gaussian_filter

        x_min, y_min, z_min = np.min(self.ligand_coords, axis=0) - margin
        x_max, y_max, z_max = np.max(self.ligand_coords, axis=0) + margin

        z_plane = np.median(self.ligand_coords[:, 2])
        xs = np.linspace(x_min, x_max, grid_size)
        ys = np.linspace(y_min, y_max, grid_size)
        X, Y = np.meshgrid(xs, ys)
        Z = np.full_like(X, z_plane)

        potential_field = np.zeros_like(X)
        for i in range(grid_size):
            for j in range(grid_size):
                point = np.array([X[i, j], Y[i, j], Z[i, j]])
                distances = np.linalg.norm(self.ligand_coords - point, axis=1)
                d_min = np.min(distances)

                dgram = torch.tensor([d_min]).float().unsqueeze(0)
                energy = sum(fn(dgram).sum().item() for fn in self.potential_calculator.energies)
                potential_field[i, j] = -self.weight * energy

        # Apply stronger Gaussian blur for smooth rendering
        if self.blur:
            potential_field = gaussian_filter(potential_field, sigma=5)
        return X, Y, potential_field

    def plot_potential_field(self, grid_size=200, margin=10, save_to: str = 'default.png'):
        """
        Plots the substrate potential field with overlaid ligand atoms and bonds.
        """
        X, Y, P = self.compute_potential_field(grid_size=grid_size, margin=margin)

        plt.figure(figsize=(8, 6))
        cp = plt.imshow(P, extent=[X.min(), X.max(), Y.min(), Y.max()], origin='lower', cmap="bwr_r", alpha=0.8)

        # Define atom colors
        color_map = {
            "C": "orange", "N": "cyan", "O": "white", "H": "white",
            "S": "yellow", "P": "orange", "F": "lime", "Cl": "lime",
            "Br": "lime", "I": "lime"
        }
        default_color = "orange"

        # Define atom sizes
        size_map = {"H": 30, "C": 100, "N": 80, "O": 80, "S": 80}
        default_size = 120

        # Overlay ligand atoms
        for idx, (coord, element) in enumerate(zip(self.ligand_coords, self.ligand_elements)):
            color = color_map.get(element, default_color)
            size = size_map.get(element, default_size)
            plt.scatter(coord[0], coord[1], c=color, s=size, edgecolors="black", linewidth=1.5, zorder=3)

        # Draw bonds
        for bond in self.ligand_bonds.as_array():
            atom1, atom2, bond_type = bond[:3]
            coord1 = self.ligand_coords[atom1]
            coord2 = self.ligand_coords[atom2]

            linewidth = 4 if bond_type == 2 else 2
            plt.plot([coord1[0], coord2[0]], [coord1[1], coord2[1]], color='black', linewidth=linewidth, zorder=2)

        # Remove axis labels
        plt.xticks([])
        plt.yticks([])

        # Adjust colorbar
        cbar = plt.colorbar(cp, orientation='horizontal', pad=0.1)
        cbar.set_label("Potential", fontsize=12)
        cbar.set_ticks([-9, -6, -3, 0, 3])

        # plt.show()
        plt.savefig(save_to, dpi=300, bbox_inches='tight')

# # Example usage:
# visualizer = SubstratePotentialVisualizer(
#     pdb_path="/Users/yyy/Documents/protein_design/RFdiffusion/examples/input_pdbs/5an7.pdb", lig_key="LLK"
# )
# visualizer.plot_potential_field(save_to='5an7_LLK.png')
