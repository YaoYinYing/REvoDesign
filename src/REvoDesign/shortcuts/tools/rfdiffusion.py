import sys
import os
import re
import shutil

import time, pickle
from omegaconf import OmegaConf,DictConfig
from hydra import errors as hydra_errors

import numpy as np
import random
import glob

from dataclasses import dataclass, field
import warnings
from RosettaPy.utils.task import RosettaCmdTask, execute


from REvoDesign.basic import ThirdPartyModuleAbstract, TorchModuleAbstract
from REvoDesign.tools.utils import get_cited, require_installed, timing
from REvoDesign.tools.dl_weights import ModelFetchSetting
from REvoDesign.bootstrap.set_config import is_package_installed, reload_config_file
from REvoDesign.bootstrap import REVODESIGN_CONFIG_FILE
from REvoDesign.tools.package_manager import run_command
from REvoDesign import ROOT_LOGGER,issues

logging = ROOT_LOGGER.getChild(__name__)

this_file_dir=os.path.dirname(os.path.abspath(__file__))


RFDIFFUSION_WEIGHTS_BASE_URL = 'https://github.com/YaoYinYing/RFdiffusion/releases/download/weights/'

# DGL Solver to solve installation of dgl(dgl==2.2.1)
# non-cuda: `pip install dgl==2.2.1 -f https://data.dgl.ai/wheels/repo.html`
# ge cuda-121: `pip install  dgl==2.2.1 -f https://data.dgl.ai/wheels/cu121/repo.html`
# ge cuda-118: `pip install  dgl -f https://data.dgl.ai/wheels/cu118/repo.html`

@dataclass
class DglSolver:
    installed: bool = is_package_installed('dgl')
    cuda_version: str = ''
    which_nvcc = shutil.which('nvcc')

    def fetch_cuda_version_before_install(self):
        
        if not self.which_nvcc:
            return
        nvcc_version= run_command(['nvcc', '--version']).stdout.split('\n')[3]
        nvcc_version_match = re.search(r'release (\d+\.\d+)', nvcc_version)
        if not nvcc_version_match:
            return
        cuda_version = nvcc_version_match.group(1)
        if cuda_version >= '12.1':
            self.cuda_version = 'cu121'
        elif cuda_version >= '11.8':
            self.cuda_version = 'cu118'
        else:
            self.cuda_version = ''
            warnings.warn(
                issues.PlatformNotSupportedWarning(
                    f"CUDA version {cuda_version} is not supported by DGL. Please install CUDA version >= 11.8 if you need to use DGL with CUDA support."
                ))
            
    def install(self):
        if self.cuda_version:
            index_link = f'https://data.dgl.ai/wheels/{self.cuda_version}/repo.html'
        else:
            index_link = 'https://data.dgl.ai/wheels/repo.html'
            
        run_command([sys.executable,'-m','pip', 'install', 'dgl==2.2.1', '-f', index_link])
        self.installed = is_package_installed('dgl')

# Pretrained weights for RFDiffusion
'''
0d9f82af03c73011c6fec060bac5b731 ActiveSite_ckpt.pt
4aa4a27ba280d23541e01860c106c7cc Base_ckpt.pt
5c58d7d5c329c1297fab0aa6cebad81b Base_epoch8_ckpt.pt
9c000b475b293b54bcf5fbd8109f5794 Complex_Fold_base_ckpt.pt
7a5d99f3c8bede52d9240f79a99bc30b Complex_base_ckpt.pt
5bb77fc129777d742045a444f43bf587 Complex_beta_ckpt.pt
1e9245a486262dff3cb3286f22a3014d InpaintSeq_Fold_ckpt.pt
a6f8652938bb45c332ffa683d8ad3509 InpaintSeq_ckpt.pt
6f4d00394d34f6a9072d70976f6c8777 RF_structure_prediction_weights.pt
'''

RfDiffusionActiveSiteWeights = ModelFetchSetting(
    name='RFDiffusion_ActiveSite_ckpt',
    version='weights',
    url=RFDIFFUSION_WEIGHTS_BASE_URL + 'ActiveSite_ckpt.pt',
    md5sum='0d9f82af03c73011c6fec060bac5b731'
)
RfDiffusionBaseWeights = ModelFetchSetting(
    name='RFDiffusion_Base_ckpt',
    version='weights',
    url=RFDIFFUSION_WEIGHTS_BASE_URL + 'Base_ckpt.pt',
    md5sum='4aa4a27ba280d23541e01860c106c7cc'
)
RfDiffusionBaseEpoch8Weights = ModelFetchSetting(
    name='RFDiffusion_Base_epoch8_ckpt',
    version='weights',
    url=RFDIFFUSION_WEIGHTS_BASE_URL + 'Base_epoch8_ckpt.pt',
    md5sum='5c58d7d5c329c1297fab0aa6cebad81b'
)
RfDiffusionComplexFoldBaseWeights = ModelFetchSetting(
    name='RFDiffusion_Complex_Fold_base_ckpt',
    version='weights',
    url=RFDIFFUSION_WEIGHTS_BASE_URL + 'Complex_Fold_base_ckpt.pt',
    md5sum='9c000b475b293b54bcf5fbd8109f5794'
)
RfDiffusionComplexBaseWeights = ModelFetchSetting(
    name='RFDiffusion_Complex_base_ckpt',
    version='weights',
    url=RFDIFFUSION_WEIGHTS_BASE_URL + 'Complex_base_ckpt.pt',
    md5sum='7a5d99f3c8bede52d9240f79a99bc30b'
)
RfDiffusionComplexBetaWeights = ModelFetchSetting(
    name='RFDiffusion_Complex_beta_ckpt',
    version='weights',
    url=RFDIFFUSION_WEIGHTS_BASE_URL + 'Complex_beta_ckpt.pt',
    md5sum='5bb77fc129777d742045a444f43bf587'
)
RfDiffusionInpaintSeqFoldWeights = ModelFetchSetting(
    name='RFDiffusion_InpaintSeq_Fold_ckpt',
    version='weights',
    url=RFDIFFUSION_WEIGHTS_BASE_URL + 'InpaintSeq_Fold_ckpt.pt',
    md5sum='1e9245a486262dff3cb3286f22a3014d'
)
RfDiffusionInpaintSeqWeights = ModelFetchSetting(
    name='RFDiffusion_InpaintSeq_ckpt',
    version='weights',
    url=RFDIFFUSION_WEIGHTS_BASE_URL + 'InpaintSeq_ckpt.pt',
    md5sum='a6f8652938bb45c332ffa683d8ad3509'
)
RfDiffusionRFStructurePredictionWeights = ModelFetchSetting(
    name='RFDiffusion_RF_structure_prediction_weights',
    version='weights',
    url=RFDIFFUSION_WEIGHTS_BASE_URL + 'RF_structure_prediction_weights.pt',
    md5sum='6f4d00394d34f6a9072d70976f6c8777'
)


def make_deterministic(seed=0):
    import torch

    torch.manual_seed(seed)
    np.random.seed(seed)
    random.seed(seed)


@require_installed
class RfDiffusion(ThirdPartyModuleAbstract, TorchModuleAbstract):
    name: str= 'RFDiffusion'
    installed: bool = is_package_installed('rfdiffusion') and is_package_installed('dgl')

    def __init__(self):
        try:
            config=reload_config_file("rfdiffusion/base")["rfdiffusion"]
        except hydra_errors.MissingConfigException as e:
            raise issues.ConfigureOutofDateError(
                'To run RFDiffusion, please reset/the configuration files '
                f'or copy the entire directory {os.path.join(this_file_dir, "../../config/rfdiffusion")}'
                f'to {os.path.join(os.path.dirname(REVODESIGN_CONFIG_FILE))} and restart REvoDesign.')


    # a copy from `https://github.com/RosettaCommons/RFdiffusion/blob/main/scripts/run_inference.py`
    @get_cited
    def main(self, conf: DictConfig) -> None:
        import torch
        from rfdiffusion.util import writepdb_multi, writepdb
        from rfdiffusion.inference import utils as iu

        if conf.inference.deterministic:
            make_deterministic()

        # Check for available GPU and print result of check
        if torch.cuda.is_available():
            self.device = torch.cuda.get_device_name(torch.cuda.current_device())
            logging.info(f"Found GPU with device_name {self.device}. Will run RFdiffusion on {self.device}")
        else:
            logging.warning("////////////////////////////////////////////////")
            logging.warning("///// NO GPU DETECTED! Falling back to CPU /////")
            logging.warning("////////////////////////////////////////////////")

        # Initialize sampler and target/contig.
        sampler = iu.sampler_selector(conf)

        # Loop over number of designs to sample.
        design_startnum = sampler.inf_conf.design_startnum
        if sampler.inf_conf.design_startnum == -1:
            existing = glob.glob(sampler.inf_conf.output_prefix + "*.pdb")
            indices = [-1]
            for e in existing:
                print(e)
                m = re.match(".*_(\d+)\.pdb$", e)
                print(m)
                if not m:
                    continue
                m = m.groups()[0]
                indices.append(int(m))
            design_startnum = max(indices) + 1

        for i_des in range(design_startnum, design_startnum + sampler.inf_conf.num_designs):
            if conf.inference.deterministic:
                make_deterministic(i_des)

            start_time = time.time()
            out_prefix = f"{sampler.inf_conf.output_prefix}_{i_des}"
            logging.info(f"Making design {out_prefix}")
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
            # Loop over number of reverse diffusion time steps.
            for t in range(int(sampler.t_step_input), sampler.inf_conf.final_step - 1, -1):
                px0, x_t, seq_t, plddt = sampler.sample_step(
                    t=t, x_t=x_t, seq_init=seq_t, final_step=sampler.inf_conf.final_step
                )
                px0_xyz_stack.append(px0)
                denoised_xyz_stack.append(x_t)
                seq_stack.append(seq_t)
                plddt_stack.append(plddt[0])  # remove singleton leading dimension

            # Flip order for better visualization in pymol
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

            # For logging -- don't flip
            plddt_stack = torch.stack(plddt_stack)

            # Save outputs
            os.makedirs(os.path.dirname(out_prefix), exist_ok=True)
            final_seq = seq_stack[-1]

            # Output glycines, except for motif region
            final_seq = torch.where(
                torch.argmax(seq_init, dim=-1) == 21, 7, torch.argmax(seq_init, dim=-1)
            )  # 7 is glycine

            bfacts = torch.ones_like(final_seq.squeeze())
            # make bfact=0 for diffused coordinates
            bfacts[torch.where(torch.argmax(seq_init, dim=-1) == 21, True, False)] = 0
            # pX0 last step
            out = f"{out_prefix}.pdb"

            # Now don't output sidechains
            writepdb(
                out,
                denoised_xyz_stack[0, :, :4],
                final_seq,
                sampler.binderlen,
                chain_idx=sampler.chain_idx,
                bfacts=bfacts,
            )

            # run metadata
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
                # trajectory pdbs
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

            logging.info(f"Finished design in {(time.time()-start_time)/60:.2f} minutes")

            with timing('cleaning up...'):
                self.cleanup()
            

    # converted using https://www.bruot.org/ris2bib/
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

