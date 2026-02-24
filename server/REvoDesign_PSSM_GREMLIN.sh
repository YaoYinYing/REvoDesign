#!/bin/bash
#SBATCH --job-name=run_GREMLIN_PSSM
#SBATCH --output=%x.o%j
#SBATCH --error=%x.e%j
# make it stop if error occurs.
# use traditional way for conda environment

############################################################
# >>> conda initialize >>>
# !! Contents within this block are managed by 'conda init' !!
if command -v conda >/dev/null 2>&1; then
  __conda_setup="$('conda' 'shell.bash' 'hook' 2>/dev/null)"
  eval "$__conda_setup"
  unset __conda_setup
  # <<< conda initialize <<<
  ############################################################

  # detect the conda env
  possible_conda_env_names=("GREMLIN" "tensorflow1.13")
  readarray -t existed_conda_env_names < <(conda info --envs | awk '{print $1}')

  for env_1 in "${possible_conda_env_names[@]}"; do
  for env_2 in "${existed_conda_env_names[@]}"; do
      if [[ "$env_1" == "$env_2" ]]; then
        echo "find ${env_1} env"
        conda activate "${env_1}"
        break
      fi
    done
  done
else
 echo "expected in docker image."
fi

# run dir
REVODESIGN_RUNSCRIPT_PATH=$(readlink -f "$(dirname "$0")")

evalue=1E-10
iter=4

# make it stop if error occurs.
set -e

usage() {
    echo ""
    echo "Usage: $0 <OPTIONS>"
    echo "Optional Parameters:"
    echo "      -i                  <fasta> input fasta file"
    echo "      -j                  <nproc> Number of threads used in this run. All processors will be used by default."
    echo "      -o                  <output_dir>   Output directory."
    echo "      -r                  <gremlin_iter> Iteration of GREMLIN, 100 by default"
    echo "      -U                  <uniref30_db> Path/prefix to Uniclust30 database, default for JAPS sever."
    echo "      -u                  <uniref90_db> Path/prefix to Uniref90, default for JAPS sever. "
    echo "      -B                  <blast_bin> Path/prefix to NCBI BLAST, default as $(dirname "$(command -v psiblast)")"
    echo "      -h                  print help message and exit."
    echo ""
    exit 1
}

while getopts ":i:o:j:r:U:u:B:h:" opt; do
    case "${opt}" in
    i) fasta=$OPTARG ;;
    j) nproc=$OPTARG ;;
    o) output_dir=$OPTARG ;;
    r) gremlin_iter=$OPTARG ;;
    U) uniref30_db=$OPTARG ;;
    u) uniref90_db=$OPTARG ;;
    B) blast_bin=$OPTARG ;;
    h) usage ;;
    ?) usage ;;

    esac
done

if [[ -z "${fasta:-}" ]]; then
  echo "Missing required option: -i <fasta>"
  usage
fi

if [[ "$blast_bin" == "" ]]; then
  blast_bin="$(dirname "$(command -v psiblast)")"
fi

echo "Checking blast version: $("${blast_bin}/psiblast" -version)"

SCRIPT_PATH='scripts'
echo "${REVODESIGN_RUNSCRIPT_PATH}/${SCRIPT_PATH}"

pth=$(pwd)
pth=$(readlink -f "$pth")
echo "We are now in $pth."

if [[ "$nproc" == "" ]]; then
    nproc=$(nproc)
fi

echo "Using $nproc processors."

# GREMLIN calc
export GREMLIN_CALC_CPU_NUM="$nproc"
export OMP_NUM_THREADS="$nproc"
export OPENBLAS_NUM_THREADS="$nproc"
export MKL_NUM_THREADS="$nproc"
export VECLIB_MAXIMUM_THREADS="$nproc"
export NUMEXPR_NUM_THREADS="$nproc"
export TF_NUM_INTRAOP_THREADS="$nproc"
export TF_NUM_INTEROP_THREADS="$nproc"
export OMP_DYNAMIC=FALSE
export MKL_DYNAMIC=FALSE


fasta_fp=$(readlink -f "$fasta")

if [[ "$gremlin_iter" == "" ]]; then
    gremlin_iter=100
fi

echo "Run GREMLIN w/ iteration: $gremlin_iter"

if [[ "$uniref30_db" == "" ]]; then
    uniref30_db=/mnt/db/uniref30_uc30/UniRef30_2022_02/UniRef30_2022_02
fi

if [[ "$uniref90_db" == "" ]]; then
    uniref90_db=/mnt/db/uniref90/uniref90
    
fi

uniref90_db_dir=$(dirname "$uniref90_db")

if compgen -G "${uniref90_db_dir}"/*.phr > /dev/null; then
  echo "Uniref90 is already formatted as BLAST+ readable."
else 
  if compgen -G "${uniref90_db_dir}"/*.fasta > /dev/null; then 
    echo "find ${uniref90_db}.fasta"
  else
    echo "${uniref90_db}.fasta not found, exit."
    exit 1
  fi
  echo "Making BLAST DB Uniref90 for the first time use... this will take a long time."
  pushd "${uniref90_db_dir}"
  makeblastdb -in uniref90.fasta -dbtype prot -parse_seqids -out uniref90
  popd
  echo "Uniref90 is now formatted."
fi

# into workingdir
cd "$pth"

RUN_GREMLIN() {
    local fasta
    fasta=$(readlink -f "$1")
    local fasta_fn
    fasta_fn=$(basename "$1")
    if [[ ! -f "$fasta" ]]; then
        echo "FASTA not exist: $fasta"
        exit 1
    fi

    local instance=${fasta_fn%.fasta}

    echo Running GREMLIN sequence searching ...

    local dst
    dst=$(readlink -f "$(pwd)")
    local dst_msa="${dst}/gremlin_msa"
    local dst_gremlin="${dst}/gremlin_res"

    mkdir -p "$dst_msa"
    mkdir -p "$dst_gremlin"
    
    pushd "$dst_msa"
    echo "REVODESIGN_STAGE:hhblits"
    if [[ ! -f "${instance}.a3m" ]]; then
        local -a cmd=(
            hhblits
            -i "$fasta"
            -oa3m "${instance}.a3m"
            -o "${instance}.hhr"
            -d "$uniref30_db"
            -n "$iter"
            -e "$evalue"
            -mact 0.35
            -maxfilt 100000000
            -neffmax 20
            -cpu "$nproc"
            -nodiff
            -realign_max 10000000
            -maxmem 64
        )
        echo "${cmd[*]}"
        "${cmd[@]}" 1>"${pipline_res_dir}"/log/"${instance}"_gremlin_hhblits.log 2>"${pipline_res_dir}"/log/"${instance}"_gremlin_hhblits.err
    fi

    echo "REVODESIGN_STAGE:hhfilter"
    local -a cmd=(hhfilter -i "${instance}.a3m" -id 90 -cov 75 -o "${instance}.i90c75.a3m")
    echo "${cmd[*]}"
    local expected_msa=${instance}.i90c75.a3m
    if [[ ! -f "$expected_msa" ]]; then
      "${cmd[@]}" 1>"${pipline_res_dir}"/log/"${instance}"_gremlin_hhfilter.log 2>"${pipline_res_dir}"/log/"${instance}"_gremlin_hhfilter.err
    fi

    # post-processing
    # remove lower case
    local -a cmd=(python "${REVODESIGN_RUNSCRIPT_PATH}/${SCRIPT_PATH}/fasta_lower_char_rm.py" "$expected_msa")
    echo "${cmd[*]}"
    "${cmd[@]}" 1>"${pipline_res_dir}"/log/"${instance}"_gremlin_remove_inserts.log 2>"${pipline_res_dir}"/log/"${instance}"_gremlin_remove_inserts.err
    # expected output is "$dst_msa/${expected_msa%.a3m}_aln.fas"
    popd
    echo Running GREMLIN ...

    echo "REVODESIGN_STAGE:gremlin"
    pushd "$dst_gremlin"
    if [[ ! -f "${dst_gremlin}/${instance}.i90c75_aln.GREMLIN.mrf.pkl" ]]; then

      local -a cmd=(
          python
          "${REVODESIGN_RUNSCRIPT_PATH}/${SCRIPT_PATH}/GREMLIN_TFv1.py"
          "${dst_msa}/${expected_msa%.a3m}_aln.fas"
          "$dst_gremlin"
          "$gremlin_iter"
      )
      echo "${cmd[*]}"
      "${cmd[@]}" 1>"${pipline_res_dir}"/log/"${instance}"_gremlin_tfv1.log 2>"${pipline_res_dir}"/log/"${instance}"_gremlin_tfv1.err
      
    else
      echo "Checkpoint file exists: ${dst_gremlin}/${instance}.i90c75_aln.GREMLIN.mrf.pkl skip GREMLIN_TFv1"
    fi

    popd
}

RUN_PSSM() {
    local fasta
    fasta=$(readlink -f "$1")
    local fasta_fn
    fasta_fn=$(basename "$1")
    if [[ ! -f "$fasta" ]]; then
        echo FASTA not exist: "$fasta"
        exit 1
    fi

    local instance=${fasta_fn%.fasta}

    echo Running BLAST sequence searching ...
    echo "REVODESIGN_STAGE:blast"
    echo Processing "$fasta" ...

    local dst
    dst=$(readlink -f "$(pwd)")
    local dst_msa="${dst}/pssm_msa"
    
    mkdir -p "$dst_msa"
    
    #cp $fasta $dst;
    pushd "$dst_msa"
    if [[ ! -f "${instance}_ascii_mtx_file" ]]; then
        local -a cmd=(
            "${blast_bin}/psiblast"
            -query "$fasta"
            -db "$uniref90_db"
            -out_pssm "${instance}.ckp"
            -evalue 0.01
            -out_ascii_pssm "${instance}_ascii_mtx_file"
            -out "${instance}_output_file"
            -num_iterations 3
            -num_threads "$nproc"
        )
        echo "${cmd[*]}"
        "${cmd[@]}" 1>"${pipline_res_dir}"/log/"${instance}"_pssm_psiblast.log 2>"${pipline_res_dir}"/log/"${instance}"_pssm_psiblast.err
    fi
    wait
    
    popd

}

if [[ -z "${output_dir:-}" ]]; then
  fasta_fn=$(basename "${fasta_fp}")
  instance=${fasta_fn%.fasta}
  pipline_res_dir=$(readlink -f "${instance}"_GREMLIN_PSSM_output)
else
  pipline_res_dir=$(readlink -f "$output_dir")
fi

mkdir -p "$pipline_res_dir"/log

pushd "$pipline_res_dir"

echo Processing "$fasta_fp" ...
RUN_GREMLIN "$fasta_fp"
popd
pushd "$pipline_res_dir"
RUN_PSSM "$fasta_fp"
popd

touch "${pipline_res_dir}/log/task_finished"
