#!/bin/bash
# AlphaFold2 runner — official google-deepmind/alphafold (runner protocol v2).
set -e
task_context_src="${TASK_CONTEXT_SRC:-/app/revocompute/task_context.sh}"
[[ -f "$task_context_src" ]] && source "$task_context_src"

usage() { echo "Usage: $0 -i <task.json> -o <output_dir>"; exit 1; }
while getopts ":i:o:" opt; do case "${opt}" in i) input_file=$OPTARG ;; o) output_dir=$OPTARG ;; ?) usage ;; esac; done
[[ -z "${input_file:-}" || -z "${output_dir:-}" ]] && usage
input_file=$(readlink -f "$input_file"); output_dir=$(readlink -f "$output_dir")
[[ ! -f "$input_file" ]] && { echo "Task manifest not found: $input_file"; exit 1; }
mkdir -p "$output_dir"

MODEL_PRESET=$(_parse_param model_preset monomer)
MAX_TEMPLATE_DATE=$(_parse_param max_template_date 2021-11-01)
DB_PRESET=$(_parse_param db_preset full_dbs)
NUM_MULTIMER=$(_parse_param num_multimer_predictions_per_model 1)
MODELS_TO_RELAX=$(_parse_param models_to_relax best)
BENCHMARK=$(_parse_param benchmark false)
fasta_path=$(primary_input)

# A100 memory behaviour: let JAX overcommit via unified memory.
export TF_FORCE_UNIFIED_MEMORY=1
export XLA_PYTHON_CLIENT_MEM_FRACTION=4.0

DB=/mnt/alphafold/db
PARAMS_ROOT=/mnt/alphafold/params_root

af_args=(
  "--fasta_paths=${fasta_path}"
  "--output_dir=${output_dir}"
  "--data_dir=${PARAMS_ROOT}"
  "--max_template_date=${MAX_TEMPLATE_DATE}"
  "--db_preset=${DB_PRESET}"
  "--model_preset=${MODEL_PRESET}"
  "--models_to_relax=${MODELS_TO_RELAX}"
  "--use_gpu_relax=true"
  "--benchmark=${BENCHMARK}"
  "--bfd_database_path=${DB}/bfd/bfd_metaclust_clu_complete_id30_c90_final_seq.sorted_opt"
  "--mgnify_database_path=${DB}/mgnify/mgy_clusters.fa"
  "--template_mmcif_dir=${DB}/pdb_mmcif/mmcif_files"
  "--obsolete_pdbs_path=${DB}/pdb_mmcif/obsolete.dat"
  "--uniref90_database_path=${DB}/uniref90/uniref90.fasta"
)
if [[ "$MODEL_PRESET" == "multimer" ]]; then
  af_args+=(
    "--uniprot_database_path=${DB}/uniprot/uniprot.fasta"
    "--pdb_seqres_database_path=${DB}/pdb_seqres/pdb_seqres.txt"
    "--num_multimer_predictions_per_model=${NUM_MULTIMER}"
  )
else
  af_args+=(
    "--pdb70_database_path=${DB}/pdb70/pdb70"
    "--uniref30_database_path=${DB}/uniref30_uc30/UniRef30_2022_02/UniRef30_2022_02"
  )
fi

cd "${ALPHAFOLD_PATH:-/opt/alphafold}"
# AlphaFold logs its phases to stderr (absl logging); the shared translator
# rewrites the stable ones into the stdout stage protocol while passing the
# original lines through to the stderr log unchanged.
python3 run_alphafold.py "${af_args[@]}" 2> >(awk -f /app/revocompute/stage_translate.awk \
  -v PATTERNS=/app/revocompute/alphafold.stages >&1)

[[ -n "$(ls "${output_dir}"/*/ranked_0.pdb 2>/dev/null || true)" ]] || {
  echo "AlphaFold produced no ranked_0.pdb" >&2; exit 1; }
touch "${output_dir}/task_finished"
echo "AlphaFold complete."
