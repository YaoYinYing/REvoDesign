from itertools import *
import os
import re
import pathlib
import numpy as np
from multiprocessing import Pool
from concurrent.futures import ThreadPoolExecutor
from REvoDesign.tools.mutant_tools import (
    extract_mutants_from_mutant_id as extract_mutants,
)


class GenerateVariantsinFastafile:
    def __init__(self):
        self.data = {}
        self.fastaseq = ""
        self.newfasta = ""
        self.group = ""
        self.name = "-1"
        self.filename_id = ""

    def getdata(self, inputfile):
        fasta_seq = []
        with open(inputfile, 'r') as f:
            for line in f:
                if line[0] == '>':
                    continue
                else:
                    self.fastaseq = self.fastaseq + line.strip()

    def get_fastasequence_from_file(self, inputfile):
        fasta_seq = ""
        with open(inputfile, 'r') as f:
            for line in f:
                if line[0] == '>':
                    continue
                else:
                    fasta_seq += line.strip()
        return fasta_seq

    def insert_mutations(self, position, native, newmutation, newfasta):
        '''
        :param position:
        :param native:
        :param newmutation:
        :param newfasta:
        :return: fastafile with mutation inserted
        '''
        # print "Input to method: ", position, native, newmutation, newfasta
        for aa in range(len(self.fastaseq)):
            # print aa, position-1
            if aa == position - 1:
                # print self.fastaseq[0:position-1]
                # print newmutation
                # print self.fastaseq[position:]
                # print("WT,POS,AA: ",self.fastaseq[aa],aa,native,self.fastaseq[aa] == native)
                assert self.fastaseq[aa] == native
                newfasta = (
                    newfasta[0 : position - 1]
                    + newmutation
                    + newfasta[position:]
                )

        return newfasta

    def get_mutated_fasta_string(
        self, position, native, newmutation, fastasequence
    ):
        '''
        :param position:
        :param native:
        :param newmutation:
        :param newfasta:
        :return: fastafile with mutation inserted
        '''
        newfasta = fastasequence
        for aa in range(len(fastasequence)):
            if aa == position - 1:
                # print("Native,Pos,Design",native,position,fastasequence[aa],fastasequence[aa] == native)
                assert fastasequence[aa] == native
                newfasta = (
                    newfasta[0 : position - 1]
                    + newmutation
                    + newfasta[position:]
                )

        return newfasta

    def write2file(self, filename):
        filename = filename.replace("__", "_")
        # print filename
        # print self.name
        if self.name != "-1":
            filename = self.name + self.group + ".fasta"
            # print filename

        with open(filename + self.filename_id, 'w') as f:
            f.write(">" + filename.split('.')[0] + '\n')
            f.write(self.newfasta)

    def run_analysis(self, fastafile, mutation, native, position):
        '''
        :param fastafile: native fastafile - i think need to be a sequnce
        :param mutations: mutations string separated with comma
        :param native: native amino acids
        :param position: positions to mutate
        :return: fasta sequence with new mutations
        '''
        # self.fastaseq
        self.getdata(fastafile)

        mutations = mutation.split(",")
        positions = position.split(",")
        natives = native.split(",")

        for i, j, k in zip(positions, natives, mutations):
            # print "Debug from method 2: ", i,j,k
            self.fastaseq = self.insert_mutations(int(i), j, k, self.fastaseq)
        return self.fastaseq


class Combinations:
    def __init__(self):
        # contain mutations
        self.list_of_mutations = []
        self.path = './'
        self.sequence_variants = {}

        # number of combinations
        self.debug = 0
        self.chain_id = 'A'

        self.init_name = ""
        self.modulus = 21000
        self.fastasequence = ""
        self.processors = 8
        self.gvf = GenerateVariantsinFastafile()
        self.dummy_count = False

        # input mut.txt
        self.inputfile = ''
        # the number of desired combination
        self.combi = 1
        # target fasta file
        self.fastafile = ''

    def combinations(self, iterable, r):
        # combinations('ABCD', 2) --> AB AC AD BC BD CD
        # combinations(range(4), 3) --> 012 013 023 123
        pool = tuple(iterable)
        n = len(pool)
        if r > n:
            return
        indices = list(range(r))
        yield tuple(pool[i] for i in indices)
        while True:
            for i in reversed(list(range(r))):
                if indices[i] != i + n - r:
                    break
            else:
                return
            indices[i] += 1
            for j in list(range(i + 1, r)):
                indices[j] = indices[j - 1] + 1
            yield tuple(pool[i] for i in indices)

    def setdata(self, datafile):
        '''
        Make sure that there are no redundant mutations in the input
        '''
        with open(datafile) as f:
            for line in f:
                _line = line.strip()
                mut_obj = extract_mutants(
                    _line, sequences={self.chain_id: self.fastasequence}
                )
                mut_id = ''.join(
                    [
                        f'{_mut["wt_res"]}{_mut["position"]}{_mut["mut_res"]}'
                        for _mut in mut_obj.get_mutant_info()
                    ]
                )

                self.list_of_mutations.append(mut_id)
        self.list_of_mutations = list(set(self.list_of_mutations))

    def getUniquePositions(self, list_w_mutations):
        unique = True
        for i in list_w_mutations:
            mut_obj_i = extract_mutants(
                i.strip(), sequences={self.chain_id: self.fastasequence}
            )
            position = mut_obj_i.get_mutant_info()[0]['position']
            for j in list_w_mutations:
                if i != j:
                    mut_obj_j = extract_mutants(
                        j.strip(),
                        sequences={self.chain_id: self.fastasequence},
                    )
                    position2 = mut_obj_j.get_mutant_info()[0]['position']
                    if position == position2:
                        print(f"skip {i} - {j} : {position} == {position2}")
                        return False
                    else:
                        continue

        return unique

    def generate_fasta_in_parallel(self, mutationalstr, groupnr):
        name = self.init_name
        newfastasequence = self.fastasequence
        for tmpposition in mutationalstr:
            tmpstr = tmpposition.strip()
            tmp_native = tmpstr[0]
            tmp_pos = int(tmpstr[1:-1])
            tmp_mutant = tmpstr[-1]
            newfastasequence = self.gvf.get_mutated_fasta_string(
                tmp_pos, tmp_native, tmp_mutant, newfastasequence
            )
            name += tmpposition + "_"
        if self.dummy_count:
            name += "_" + str(groupnr)

        return name[0:-1], newfastasequence

    def get_generator_of_combinations(self):
        b = self.combinations(self.list_of_mutations, self.combi)
        return b

    def setup(self, inputfile, combinations, fastafile):
        """
        :param inputfile:
        :param combinations:
        :return:
        """
        self.combi = int(combinations)
        self.setdata(inputfile)
        b = self.combinations(self.list_of_mutations, self.combi)

        mutations = []
        # self.fastasequence = self.gvf.get_fastasequence_from_file( fastafile)
        # insert method here to evaluate the WT AA with the given fasta
        self.evalute_fasta_file()

        for j in b:
            eval = self.getUniquePositions(list(j))
            if self.debug == 1:
                print(j)
            if eval == True:
                mutations.append(j)

        # rewrite to parallel
        dummy = list(range(len(mutations)))
        # print("length of designs:: ",dummy)

        with ThreadPoolExecutor(self.processors) as p:
            name_seq = p.map(self.generate_fasta_in_parallel, mutations, dummy)
        # expected design combination file
        fastafile_stem = pathlib.Path(fastafile).resolve().stem
        inputfile_stem = pathlib.Path(inputfile).resolve().stem
        self.expected_output_fasta = (
            pathlib.Path(self.path)
            .resolve()
            .joinpath(
                f"{fastafile_stem}_{inputfile_stem}_designs_{str(self.combi)}.fasta"
            )
        )
        with open(self.expected_output_fasta, 'w') as f:
            for i in name_seq:
                f.write(">" + i[0] + "\n")
                f.write(i[1] + "\n")

    def evalute_fasta_file(self):
        for eval_wt in self.list_of_mutations:
            # count from 0 in python
            pos = int(eval_wt[1:-1]) - 1
            aa = eval_wt[0]
            assert aa == self.fastasequence[pos], (
                "WT =  "
                + self.fastasequence[pos]
                + str(pos + 1)
                + " input AA: "
                + aa
                + " mut file contains: "
                + eval_wt
            )

    def run_combinations(self):
        assert (
            os.path.exists(self.inputfile)
            and os.path.exists(self.fastafile)
            and self.combi >= 1
        )

        self.setup(self.inputfile, self.combi, self.fastafile)
