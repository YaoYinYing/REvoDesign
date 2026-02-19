# Mock UniRef30/90 for Server Testing

## UniRef90 - PSI-BLAST

1. Make Database directory: `mkdir -p miniuc/uc90`
2. Make Database for NCBI-Blast:

```bash
makeblastdb -in tests/data/msa/2KL8_blast.fasta -dbtype prot -parse_seqids -out miniuc/uc90/uniref90
```

3. Validate Database:

```bash
mkdir -p testminiuc/uc90/; 
psiblast -query 2KL8.fasta -db miniuc/uc90/uniref90 -out_pssm testminiuc/uc90/2KL8.ckp -evalue 0.01 -out_ascii_pssm testminiuc/uc90/2KL8_ascii_mtx_file -out testminiuc/uc90/2KL8_output_file -num_iterations 3 -num_threads 2
```


## UniRef30 - HH-suite

1. Make Database directory:

```bash
mkdir -p miniuc/uc30
```

2. Make Database for HH-suite:

```bash
cd miniuc/uc30; 
# make ffindex 
ffindex_from_fasta -s miniuc30_a3m.ff{data,index} ../../tests/data/msa/2KL8.i90c75_aln.fa;
# translate
cstranslate -A $CONDA_PREFIX/data/cs219.lib -D $CONDA_PREFIX/data/context_data.crf -x 0.3 -c 4 -f -i miniuc30_a3m -o miniuc30_cs219 -I a3m -b;
cd ../..
```

3. Validate Database:

```bash
hhblits -i 2KL8.fasta -oa3m 2KL8.a3m -o 2KL8.hhr -d ../../uc30/miniuc30 -n 4 -e 1E-10 -mact 0.35 -maxfilt 100000000 -neffmax 20 -cpu  2 -nodiff -realign_max 10000000 -maxmem 1
```