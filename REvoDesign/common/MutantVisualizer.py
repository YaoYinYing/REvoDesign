import os
import re
import time
import shutil
import tempfile
import multiprocessing
import pandas as pd
from Bio.Data import IUPACData
from pymol import cmd, util
import matplotlib
matplotlib.use('Agg')
from phylogenetics.pymol_pssm_script import mutate
from tools.merge_sessions import merge_sessions
from absl import logging

class MutantVisualizer:
    def __init__(self, molecule, chain_id):
        self.molecule = molecule
        self.chain_id = chain_id
        self.mutfile = ''
        self.input_session = None
        self.save_session = None
        self.nproc = os.cpu_count()
        self.full = False
        self.cmap = "bwr_r"
        self.key_col = "best_leaf"
        self.score_col = "totalscore"
        self.group_name = 'default_group'


        self.min_score = 0.5
        self.max_score = 0.5

    def get_color(self, cmap, data, min_value, max_value):
        if min_value == max_value:
            return [0.5,0.5,0.5]
        num_color = cmap.N
        scaled_value = (data - min_value) / (max_value - min_value)
        color = cmap(int(num_color * scaled_value))[:3]
        return color

    
    def process_position(self,mutant, score,):
        temp_dir = tempfile.mkdtemp(prefix='pymol_pssm_')
        temp_session_path = os.path.join(temp_dir, f"position_{mutant}.pse")
        cmd.load(self.input_session)

        cmd.hide('surface')

        color = self.get_color(matplotlib.colormaps[self.cmap], score, self.min_score, self.max_score)
        logging.info(f" Visualizing {mutant} {score}: {color}")
        self.create_pymol_objects(mutant, color)
        cmd.hide('everything', 'hydrogens and polymer.protein')
        cmd.delete(self.molecule)
        cmd.save(temp_session_path)
        cmd.reinitialize()
        return temp_session_path

    def create_pymol_objects(self, mutant, color):
        new_obj_name = mutant
        cmd.create(f"{new_obj_name}", f'{self.molecule} and c. {self.chain_id}')

        mut_pos=[]

        for mut in mutant.split('_'):
            if mut[0].isdigit():
                position = int(mut[0:-1])
            else:
                position = int(mut[1:-1])
            new_residue=mut[-1]
            new_residue_3 = IUPACData.protein_letters_1to3[new_residue].upper()
            mut_pos.append(position)
            mutate(new_obj_name, self.chain_id, position, new_residue_3)
            cmd.hide('lines', f'{new_obj_name}')
            cmd.show("sticks", f" {new_obj_name} and resi {position} and (sidechain or n. CA)")

        if not self.full:
            cmd.remove(f" {new_obj_name} and not ( resi {'+'.join([str(i) for i in mut_pos])} and (sidechain or n. CA))")

        # set backbone color
        cmd.set_color(f'color_{new_obj_name}', color)
        cmd.color(f'color_{new_obj_name}', f'( {new_obj_name} and resi {"+".join([str(i) for i in mut_pos])} )')
        util.cnc(f'({new_obj_name} and resi {"+".join([str(i) for i in mut_pos])})', _self=cmd)

        if self.group_name:
            cmd.group(self.group_name, f'{new_obj_name}', )

    # provide a full function of PyMOL mutate that requires explicit mutagenesis description
    def create_mutagenesis_objects(self, mutant, color):
        # mutant: <chain_id><wt><pos><mut>_..._<score>
        new_obj_name = mutant
        cmd.create(f"{new_obj_name}", self.molecule)

        mut_pos=[]

        # TODO: suport '(\w)(\d+)(\w)' and '(\d+)(\w)' format, meaning that wt and chain can be set as default
        for mut in mutant.split('_')[:-1]:
            # a full match of mutagenesis description
            matched_mut=re.match(r'(\w)(\w)(\d+)(\w)',mut)
            chain_id=matched_mut.group(1)
            wt_res=matched_mut.group(2)
            position=int(matched_mut.group(3))
            new_residue=matched_mut.group(4)
            
            new_residue_3 = IUPACData.protein_letters_1to3[new_residue].upper()
            #mut_pos.append(position)

            mut_pos.append(f'(c. {chain_id} and i. {str(position)})')
            mutate(new_obj_name, chain_id, position, new_residue_3)
            cmd.hide('lines', f'{new_obj_name}')
            cmd.show("sticks", f' {new_obj_name} and c. {chain_id} and i. {position} and (sidechain or n. CA)')

        if not self.full:
            cmd.remove(f' {new_obj_name} and not ( ({" or ".join(mut_pos)}) and (sidechain or n. CA))')

        # set backbone color
        cmd.set_color(f'color_{new_obj_name}', color)
        cmd.color(f'color_{new_obj_name}', f'({new_obj_name} and ({" or ".join(mut_pos)}) )')
        util.cnc(f'{new_obj_name} and ({" or ".join(mut_pos)})', _self=cmd)

        if self.group_name:
            cmd.group(self.group_name, f'{new_obj_name}', )

    def run_with_progressbar(self,progress_bar):
        # Check the file format and read data accordingly
        if self.mutfile.lower().endswith('.csv'):
            # Read mutation data from CSV file using pandas
            mutation_data = pd.read_csv(self.mutfile)
        elif self.mutfile.lower().endswith('.txt'):
            # Read mutation data from TXT file using pandas and use 'key_col' as the column name
            mutation_data = pd.read_csv(self.mutfile, sep='\t', names=[self.key_col])
        else:
            raise ValueError("Invalid file format. Only CSV and TXT formats are supported.")

        # Check if the key_col exists in the dataframe
        if self.key_col not in mutation_data.columns:
            raise ValueError(f"Variant column '{self.key_col}' not found in the data.")

        # Check if the score_col exists in the dataframe, if not, add it with a default value of 1
        if self.score_col not in mutation_data.columns:
            logging.info(f"Warning: Score column '{self.score_col}' not found in the data. Setting score to 1.")
            mutation_data[self.score_col] = 1

        self.mutation_dict = {}
        score_list = []
        for _, row in mutation_data.iterrows():
            variant = row[self.key_col]
            score = row[self.score_col]
            self.mutation_dict[variant] = score
            score_list.append(score)

        # Determine the range for color bar
        min_score = min(score_list)
        max_score = max(score_list)

        self.min_score = min_score
        self.max_score = max_score

        self.run_mutagenesis_tasks(progress_bar=progress_bar)


    def run_mutagenesis_tasks(self,progress_bar):
        from tools.utils import refresh_window, ParallelExecutor

        # Create a multiprocessing pool
        self.mutagenesis_tasks=[(variant.replace('/', '_'),score) for variant, score in self.mutation_dict.items()]

        progress_bar.setRange(0, 0)

        parallel_executor = ParallelExecutor(self.process_position, self.mutagenesis_tasks, n_jobs=self.nproc)


        parallel_executor.start()
        
        while not parallel_executor.isFinished():
            #logging.info(f'Running ....')
            refresh_window()
            time.sleep(0.001)

        progress_bar.setRange(0, len(self.mutagenesis_tasks))
        progress_bar.setValue(len(self.mutagenesis_tasks))

        self.results=parallel_executor.handle_result()
        cmd.reinitialize()

        logging.info("Merging all sessions .... This may take a while ...")

        cmd.hide('surface')

        mutagenesis_sessions = [session_path for session_path in self.results if session_path]
        logging.debug(f'mutangesis_sessions: {mutagenesis_sessions}')

        merged_temp_session = f"{os.path.join(os.path.dirname(self.save_session), f'tmp_{os.path.basename(self.save_session)}')}"
        merge_sessions(session_paths=mutagenesis_sessions,
                       save_path=merged_temp_session,
                       mode=2,
                       delete=1)

        merge_sessions(session_paths=[self.input_session, merged_temp_session],
                       save_path=self.save_session,
                       mode=2)
        

        
    def handle_calculation_result(self, results):
        # Handle the results of the calculation as needed
        self.results = results  # Store the results for further processing
        logging.info("Calculation results:", self.results)