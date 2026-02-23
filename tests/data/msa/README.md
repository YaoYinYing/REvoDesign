# Mock UniRef30/90 for Server Testing

# Overview

This directory ships a tiny, reproducible version of the UniRef30/UniRef90
databases that the server tests rely on.  The data are intentionally small so
they can be checked into the repository, but the build steps mirror the exact
commands used in production.  Running through the recipe below lets you rebuild
the mock databases from the raw FASTA alignment assets that live in this folder.


## Directory layout

- `2KL8.fasta` – single-sequence FASTA used as the query for every validation
  command.
- `2KL8_blast.fasta` – subset of UniRef90 sequences for the PSI‑BLAST database.
- `2KL8.i90c75_aln.fas` – HHblits alignment that mimics UniRef30 coverage.
- `miniuc/` – will contain the rebuilt HH-suite (`uc30`) and PSI‑BLAST (`uc90`)
  databases.
- `testminiuc/` – scratch space used by the validation commands.


## Requirements

- Install `blast` and `hhsuite` inside the repo’s Conda environment
  (see the project root README for environment creation).
- Ensure `$CONDA_PREFIX` points at that environment so HH-suite can locate
  `cs219.lib` and `context_data.crf`.


## Rebuild workflow

All commands assume the repository root as the working directory.

### 1. Create directories

```bash
mkdir -p miniuc/uc90 miniuc/uc30 testminiuc/uc90 testminiuc/uc30
```

### 2. Build the UniRef90 mock (PSI‑BLAST)

```bash
makeblastdb \
  -in tests/data/msa/2KL8_blast.fasta \
  -dbtype prot \
  -parse_seqids \
  -out miniuc/uc90/uniref90
```

Validate the database by generating a checkpoint and ASCII PSSM:

```bash
psiblast \
  -query tests/data/msa/2KL8.fasta \
  -db miniuc/uc90/uniref90 \
  -out_pssm testminiuc/uc90/2KL8.ckp \
  -out_ascii_pssm testminiuc/uc90/2KL8_ascii.mtx \
  -out testminiuc/uc90/2KL8.out \
  -evalue 0.01 \
  -num_iterations 3 \
  -num_threads 2
```

The `.ckp`, `.mtx`, and `.out` files are small and provide a quick regression
signal when tests read from the mock database.

### 3. Build the UniRef30 mock (HH-suite)

```bash
pushd miniuc/uc30

# Convert alignment FASTA to HH-suite ffindex/ffdata pairs.
ffindex_from_fasta -s miniuc30_a3m.ff{data,index} ../../tests/data/msa/2KL8.i90c75_aln.fas

# Translate A3M into the HH-suite compressed format.
cstranslate \
  -A $CONDA_PREFIX/data/cs219.lib \
  -D $CONDA_PREFIX/data/context_data.crf \
  -x 0.3 \
  -c 4 \
  -f \
  -i miniuc30_a3m \
  -o miniuc30_cs219 \
  -I a3m \
  -b

popd
```

Validate by running a small HHblits search:

```bash
hhblits \
  -i tests/data/msa/2KL8.fasta \
  -oa3m testminiuc/uc30/2KL8.a3m \
  -o testminiuc/uc30/2KL8.hhr \
  -d miniuc/uc30/miniuc30 \
  -n 4 \
  -e 1e-10 \
  -mact 0.35 \
  -maxfilt 1e8 \
  -neffmax 20 \
  -cpu 2 \
  -nodiff \
  -realign_max 1e7 \
  -maxmem 1
```

The generated `.a3m` and `.hhr` files are what server tests use to emulate
remote HHblits behavior.


## Tips

- Delete and rebuild `miniuc/` whenever the upstream FASTA files change to keep
  indices consistent.
- If Conda installs HH-suite into a different prefix, update `$CONDA_PREFIX`
  before running `cstranslate`.
- These commands are intentionally lightweight, so they finish in a few seconds
  even on CI, making them safe to run as part of local regression testing.
