import glob
import os
import pickle
import random
import re
import shutil
import sys
import time
import warnings
from dataclasses import dataclass
from typing import List, Optional
import numpy as np
from hydra import errors as hydra_errors
from omegaconf import DictConfig, OmegaConf
from REvoDesign import ROOT_LOGGER, issues
from REvoDesign.basic import ThirdPartyModuleAbstract, TorchModuleAbstract
from REvoDesign.bootstrap import REVODESIGN_CONFIG_FILE
from REvoDesign.bootstrap.set_config import (is_package_installed,
                                             reload_config_file)
from REvoDesign.tools.download_registry import FileDownloadRegistry
from REvoDesign.tools.package_manager import run_command
from REvoDesign.tools.rfdiffusion_tools import SubstratePotentialVisualizer
from REvoDesign.tools.utils import (device_picker, get_cited,
                                    require_installed, timing)
logging = ROOT_LOGGER.getChild(__name__)
this_file_dir = os.path.dirname(os.path.abspath(__file__))
RFDIFFUSION_WEIGHTS_BASE_URL = 'https://github.com/YaoYinYing/RFdiffusion/releases/download/weights/'
RFD_WEIGHTS_STR = '''
0d9f82af03c73011c6fec060bac5b731 ActiveSite_ckpt.pt
4aa4a27ba280d23541e01860c106c7cc Base_ckpt.pt
5c58d7d5c329c1297fab0aa6cebad81b Base_epoch8_ckpt.pt
9c000b475b293b54bcf5fbd8109f5794 Complex_Fold_base_ckpt.pt
7a5d99f3c8bede52d9240f79a99bc30b Complex_base_ckpt.pt
5bb77fc129777d742045a444f43bf587 Complex_beta_ckpt.pt
1e9245a486262dff3cb3286f22a3014d InpaintSeq_Fold_ckpt.pt
a6f8652938bb45c332ffa683d8ad3509 InpaintSeq_ckpt.pt
6f4d00394d34f6a9072d70976f6c8777 RF_structure_prediction_weights.pt
        Pick a model.
        Override Priority:
            1. If ckpt_override_path is set in config, use it.
            2. If model_name is set in input, use it.
            3. If model_name is set in config, use it.
            4. If model is not set, try to infer the model name from the config.
            5. Otherwise, use the default model (base).
        Parameters
        ----------
        model_name: str, optional
            The name of the model to use. If None, the model will be automatically picked based on the input.
        Ensure DGL is installed. If not, try to install it.
        Instantiate RFDiffusion app with config preset and overrides.
        Args:
            config_preset: str, optional
                The config preset to use. Defaults to 'base'.
            model_name: Optional[str], optional
                The model name to use. Defaults to None.
            overrides: Optional[List[str]], optional
                The overrides to use. Defaults to None.
        Run RFdifussion inference.
        '''
        import torch
        from rfdiffusion.inference import utils as iu
        from rfdiffusion.util import writepdb, writepdb_multi
        if self.config.inference.deterministic:
            make_deterministic()
        devices = device_picker()
        gpu_devices = [d for d in devices if d.startswith(("cuda", "mps"))]
        if any(d for d in gpu_devices):
            self.device = gpu_devices[0]
            logging.info(f"Found GPU with device_name {self.device}. Will run RFdiffusion on {self.device}")
        else:
            self.device = "cpu"
            logging.warning("////////////////////////////////////////////////")
            logging.warning("///// NO GPU DETECTED! Falling back to CPU /////")
            logging.warning("////////////////////////////////////////////////")
        sampler = iu.sampler_selector(self.config)
        design_startnum = sampler.inf_conf.design_startnum
        if sampler.inf_conf.design_startnum == -1:
            existing = glob.glob(sampler.inf_conf.output_prefix + "*.pdb")
            indices = [-1]
            for e in existing:
                print(e)
                m = re.match(r".*_(\d+)\.pdb$", e)
                print(m)
                if not m:
                    continue
                m = m.groups()[0]
                indices.append(int(m))
            design_startnum = max(indices) + 1
        for i_des in range(design_startnum, design_startnum + sampler.inf_conf.num_designs):
            if self.config.inference.deterministic:
                make_deterministic(i_des)
            out_prefix = f"{sampler.inf_conf.output_prefix}_{i_des}"
            with timing(f'making design {out_prefix} / {sampler.inf_conf.num_designs}', unit='min'):
                start_time = time.time()
                if sampler.inf_conf.cautious and os.path.exists(out_prefix + ".pdb"):
                    logging.info(
                        f"(cautious mode) Skipping this design because {out_prefix}.pdb already exists."
                    )
                    continue
                x_init, seq_init = sampler.sample_init()
                denoised_xyz_stack = []
                px0_xyz_stack = []
                seq_stack = []
                plddt_stack = []
                x_t = torch.clone(x_init)
                seq_t = torch.clone(seq_init)
                for t in range(int(sampler.t_step_input), sampler.inf_conf.final_step - 1, -1):
                    px0, x_t, seq_t, plddt = sampler.sample_step(
                        t=t, x_t=x_t, seq_init=seq_t, final_step=sampler.inf_conf.final_step
                    )
                    px0_xyz_stack.append(px0)
                    denoised_xyz_stack.append(x_t)
                    seq_stack.append(seq_t)
                    plddt_stack.append(plddt[0])  
                denoised_xyz_stack = torch.stack(denoised_xyz_stack)
                denoised_xyz_stack = torch.flip(
                    denoised_xyz_stack,
                    [
                        0,
                    ],
                )
                px0_xyz_stack = torch.stack(px0_xyz_stack)
                px0_xyz_stack = torch.flip(
                    px0_xyz_stack,
                    [
                        0,
                    ],
                )
                plddt_stack = torch.stack(plddt_stack)
                os.makedirs(os.path.dirname(out_prefix), exist_ok=True)
                final_seq = seq_stack[-1]
                final_seq = torch.where(
                    torch.argmax(seq_init, dim=-1) == 21, 7, torch.argmax(seq_init, dim=-1)
                )  
                bfacts = torch.ones_like(final_seq.squeeze())
                bfacts[torch.where(torch.argmax(seq_init, dim=-1) == 21, True, False)] = 0
                out = f"{out_prefix}.pdb"
                writepdb(
                    out,
                    denoised_xyz_stack[0, :, :4],
                    final_seq,
                    sampler.binderlen,
                    chain_idx=sampler.chain_idx,
                    bfacts=bfacts,
                )
                trb = dict(
                    config=OmegaConf.to_container(sampler._conf, resolve=True),
                    plddt=plddt_stack.cpu().numpy(),
                    device=self.device,
                    time=time.time() - start_time,
                )
                if hasattr(sampler, "contig_map"):
                    for key, value in sampler.contig_map.get_mappings().items():
                        trb[key] = value
                with open(f"{out_prefix}.trb", "wb") as f_out:
                    pickle.dump(trb, f_out)
                if sampler.inf_conf.write_trajectory:
                    traj_prefix = (
                        os.path.dirname(out_prefix) + "/traj/" + os.path.basename(out_prefix)
                    )
                    os.makedirs(os.path.dirname(traj_prefix), exist_ok=True)
                    out = f"{traj_prefix}_Xt-1_traj.pdb"
                    writepdb_multi(
                        out,
                        denoised_xyz_stack,
                        bfacts,
                        final_seq.squeeze(),
                        use_hydrogens=False,
                        backbone_only=False,
                        chain_ids=sampler.chain_idx,
                    )
                    out = f"{traj_prefix}_pX0_traj.pdb"
                    writepdb_multi(
                        out,
                        px0_xyz_stack,
                        bfacts,
                        final_seq.squeeze(),
                        use_hydrogens=False,
                        backbone_only=False,
                        chain_ids=sampler.chain_idx,
                    )
            with timing('cleaning up...'):
                self.cleanup()
    __bibtex__ = {
        'RFDiffusion': '''@Article{Watson2023,
author={Watson, Joseph L.
and Juergens, David
and Bennett, Nathaniel R.
and Trippe, Brian L.
and Yim, Jason
and Eisenach, Helen E.
and Ahern, Woody
and Borst, Andrew J.
and Ragotte, Robert J.
and Milles, Lukas F.
and Wicky, Basile I. M.
and Hanikel, Nikita
and Pellock, Samuel J.
and Courbet, Alexis
and Sheffler, William
and Wang, Jue
and Venkatesh, Preetham
and Sappington, Isaac
and Torres, Susana V{\'a}zquez
and Lauko, Anna
and De Bortoli, Valentin
and Mathieu, Emile
and Ovchinnikov, Sergey
and Barzilay, Regina
and Jaakkola, Tommi S.
and DiMaio, Frank
and Baek, Minkyung
and Baker, David},
title={De novo design of protein structure and function with RFdiffusion},
journal={Nature},
year={2023},
month={Aug},
day={01},
volume={620},
number={7976},
pages={1089-1100},
abstract={There has been considerable recent progress in designing new proteins using deep-learning methods1--9. Despite this progress, a general deep-learning framework for protein design that enables solution of a wide range of design challenges, including de novo binder design and design of higher-order symmetric architectures, has yet to be described. Diffusion models10,11 have had considerable success in image and language generative modelling but limited success when applied to protein modelling, probably due to the complexity of protein backbone geometry and sequence--structure relationships. Here we show that by fine-tuning the RoseTTAFold structure prediction network on protein structure denoising tasks, we obtain a generative model of protein backbones that achieves outstanding performance on unconditional and topology-constrained protein monomer design, protein binder design, symmetric oligomer design, enzyme active site scaffolding and symmetric motif scaffolding for therapeutic and metal-binding protein design. We demonstrate the power and generality of the method, called RoseTTAFold diffusion (RFdiffusion), by experimentally characterizing the structures and functions of hundreds of designed symmetric assemblies, metal-binding proteins and protein binders. The accuracy of RFdiffusion is confirmed by the cryogenic electron microscopy structure of a designed binder in complex with influenza haemagglutinin that is nearly identical to the design model. In a manner analogous to networks that produce images from user-specified inputs, RFdiffusion enables the design of diverse functional proteins from simple molecular specifications.},
issn={1476-4687},
doi={10.1038/s41586-023-06415-8},
url={https://doi.org/10.1038/s41586-023-06415-8}
}
''',
    }
def visualize_substrate_potentials(pdb_path,
                                   lig_key,
                                   blur: bool = False,
                                   weight: float = 1,
                                   r_0: float = 8,
                                   d_0: float = 2,
                                   s: float = 1,
                                   eps: float = 1e-6,
                                   rep_r_0: float = 5,
                                   rep_s: float = 2,
                                   rep_r_min: float = 1,):
    return SubstratePotentialVisualizer(
        pdb_path=pdb_path,
        lig_key=lig_key,
        blur=blur,
        weight=weight,
        r_0=r_0,
        d_0=d_0,
        s=s,
        eps=eps,
        rep_r_0=rep_r_0,
        rep_s=rep_s,
        rep_r_min=rep_r_min,
    )
def run_general_rfdiffusion_task(config_preset: str = 'base',
                                 model_name: Optional[str] = None,
                                 overrides: Optional[List[str]] = None):
    app = RfDiffusion(
        config_preset=config_preset,
        model_name=model_name,
        overrides=overrides,
    )
    app.main()