import matplotlib
import numpy as np
from REvoDesign.basic import ThirdPartyModuleAbstract
from REvoDesign.bootstrap.set_config import is_package_installed
from REvoDesign.tools.utils import require_installed
matplotlib.use('Qt5Agg')
@require_installed
class SubstratePotentialVisualizer(ThirdPartyModuleAbstract):
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
        import biotite.structure as struc
        import biotite.structure.io as bsio
        structure = bsio.load_structure(self.pdb_path, model=1)
        ligand_atoms = structure[structure.res_name == self.lig_key]
        if len(ligand_atoms) == 0:
            raise ValueError(f"Ligand '{self.lig_key}' not found in PDB file: {self.pdb_path}")
        ligand_coords = ligand_atoms.coord.astype(float)
        ligand_elements = ligand_atoms.element
        bonds = struc.connect_via_residue_names(ligand_atoms)
        return ligand_coords, bonds, ligand_elements
    def align_to_principal_axes(self):
        from sklearn.decomposition import PCA
        pca = PCA(n_components=3)
        pca.fit(self.ligand_coords)
        rotation_matrix = pca.components_.T
        self.ligand_coords = np.dot(self.ligand_coords - np.mean(self.ligand_coords, axis=0), rotation_matrix)
    def compute_potential_field(self, grid_size=200, margin=10):
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
        if self.blur:
            potential_field = gaussian_filter(potential_field, sigma=5)
        return X, Y, potential_field
    def plot_potential_field(self, grid_size=200, margin=10, save_to: str = 'default.png'):
        import matplotlib.pyplot as plt
        X, Y, P = self.compute_potential_field(grid_size=grid_size, margin=margin)
        plt.figure(figsize=(8, 6))
        cp = plt.imshow(P, extent=[X.min(), X.max(), Y.min(), Y.max()], origin='lower', cmap="bwr_r", alpha=0.8)
        color_map = {
            "C": "orange", "N": "cyan", "O": "white", "H": "white",
            "S": "yellow", "P": "orange", "F": "lime", "Cl": "lime",
            "Br": "lime", "I": "lime"
        }
        default_color = "black"
        size_map = {"H": 20, "C": 60, "N": 50, "O": 50, "S": 50}
        default_size = 90
        for idx, (coord, element) in enumerate(zip(self.ligand_coords, self.ligand_elements)):
            color = color_map.get(element, default_color)
            size = size_map.get(element, default_size)
            plt.scatter(coord[0], coord[1], c=color, s=size, edgecolors="black", linewidth=1.5, zorder=3)
        for bond in self.ligand_bonds.as_array():
            atom1, atom2, bond_type = bond[:3]
            coord1 = self.ligand_coords[atom1]
            coord2 = self.ligand_coords[atom2]
            plt.plot([coord1[0], coord2[0]], [coord1[1], coord2[1]], color='black', linewidth=bond_type * 2, zorder=2)
        plt.xticks([])
        plt.yticks([])
        cbar = plt.colorbar(cp, orientation='horizontal', pad=0.1)
        cbar.set_label("Potential", fontsize=12)
        cbar.set_ticks([-9, -6, -3, 0, 3])
        plt.savefig(save_to, dpi=300, bbox_inches='tight')
# visualizer.plot_potential_field(save_to='HEM.png')