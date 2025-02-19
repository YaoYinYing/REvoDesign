#! /bin/bash

# make it stop when error occurs.
set -e

# use traditional way for conda environment
source $CONDA_PREFIX/etc/profile.d/conda.sh
conda activate esm


# CHECK SCRIPT DIR
if [[ ! -d $PROTEIN_DESIGN_KIT ]]; then
    echo '$PROTEIN_DESIGN_KIT' is not defined or unaccessible!
    exit 1
fi

export MODULE_PATH="$PROTEIN_DESIGN_KIT/4._Tools/scripts/module/"

# CHECK GIT COMMIT
source $MODULE_PATH/check_git_commit.sh

# ARGUMENTS INPUT
source $MODULE_PATH/slurm_processors_mpi.sh


# USAGE

# FETCH OPTIONS IF NOT SLURM
####################################################################################################################
if [[ $IN_SLURM == false ]]; then
    usage() {
      echo ""
        echo "Usage: $0<OPTIONS>"
        echo "Required Parameters:"
        echo "      -i       <sequence> "
        echo "Optional Parameters:"
        echo "      -m       <esm_model> "
        echo "      -n       <instance> "
        echo "      -N       <msa_samples> "
        echo "      -a       <alignment> "
        echo "      -s       <scoring_strategy> "
        echo "      -g       <use_gpu> "
        echo ""
        exit 1
    }
    while getopts ":i:m:N:n:a:s:g:j:" opt; do
        case "${opt}" in
            # required options
            i) sequence=$OPTARG ;;
            m) esm_model=$OPTARG ;;
            N) msa_samples=$OPTARG ;;
            n) instance=$OPTARG ;;
            a) alignment=$OPTARG ;;
            s) scoring_strategy=$OPTARG ;;
            g) use_gpu=$OPTARG ;;
            j) nproc=$OPTARG ;;
            # updatable options


            *) echo Unknown option!;usage ;;
        esac
    done
    MPI_COMPUTE_RESOURCE="--use-hwthread-cpus -np $nproc "
    pretrained_data_dir="/mnt/db/weights/esm/checkpoints/"
    # GREMLIN config
    database_seqs=/mnt/db/uniref30_uc30/UniRef30_2022_02/UniRef30_2022_02
    evalue=1E-10
    iter=4

    #esm_repo_dir="/repo/esm/"
else
    MPI_COMPUTE_RESOURCE="--hostfile $NODEFILE "
    pretrained_data_dir="/mnt/db/weights/esm/checkpoints/"
fi

# DEFINE SUBDIR
# if the structure of directory changes someday, we need to update the statements here.

dir="$PROTEIN_DESIGN_KIT/2._Working/1._MutationEffects/ESM-1v/"
path_to_script=$dir
echo script path: "${path_to_script}"

# PROCESSING UNDEFINED ARGUMENTS
echo Using $nproc processors.

# functions used
RUN_HHBLITS(){
    local instance=$1
    local sequence=$2
    echo Running hhblits to ${instance} ...
    mkdir -p MSA || echo NEVER MIND
    pushd MSA
    echo ">${instance}" > ${instance}.fasta
    echo "${sequence}" >> ${instance}.fasta
    if [[ ! -f "${instance}.a3m" ]];then
        # same configuration w/ GREMLIN
        local cmd="hhblits -i ${instance}.fasta -oa3m ${instance}.a3m -d ${database_seqs} -n ${iter} -e ${evalue} \
                -mact 0.35 -maxfilt 100000000 -neffmax 20 -cpu ${nproc} -nodiff -realign_max 10000000 -maxmem 64"
        echo "$cmd"
        eval "$cmd"

    fi
    if [[ ! -f "${instance}.i90c75.a3m" ]];then
        local cmd="hhfilter -i ${instance}.a3m -id 90 -cov 75 -o ${instance}.i90c75.a3m"
        echo "$cmd"
        eval "$cmd"
        local expected_msa=${instance}.i90c75.a3m
        echo "HHblits is done! expected msa: ${instance}.i90c75.a3m"
    else
        echo "Previous HHfilter result is found: ${instance}.i90c75.a3m"
    fi

    # post-processing
    # remove lower case
    echo "Now removing the insertions in sequences ..."
    if [[ ! -f "${instance}.i90c75_aln.fas" ]];then
        local cmd="python ${PROTEIN_DESIGN_KIT}/2._Working/0._IntergatedProtocol/GREMLIN_PSSM/scripts/fasta_lower_char_rm.py ./${instance}.i90c75.a3m"
        echo "$cmd"
        eval "$cmd"
    else
        echo "Previous MSA result is found! expected msa: ${instance}.i90c75_aln.fas"
    fi
    # expected output is "$dst_msa/${expected_msa%.a3m}_aln.fas"

    popd
}

if [[ "$scoring_strategy" == "" ]];then
    scoring_strategy="masked-marginals"
elif [[ "$scoring_strategy" != "wt-marginals" && "$scoring_strategy" != "pseudo-ppl" && "$scoring_strategy" !=  "masked-marginals" ]];then
    echo "Unknown scoring_strategy: ${scoring_strategy}"
    usage
else
    echo "Using scoring_strategy: ${scoring_strategy}"
fi

if [[ "$use_gpu" == "" || "$use_gpu" == "true" ]];then
    use_gpu=true
    use_gpu_flag=""
elif [[ "$use_gpu" == "false" ]];then
    use_gpu_flag=" --nogpu "
else
    use_gpu_flag=""
fi


echo "Use GPU: ${use_gpu}"
echo "Use GPU flag: ${use_gpu_flag}"



if [[ "$sequence" == "" ]]; then
    echo WT sequence: ${sequence}
    echo required input missing!
    usage
fi

if [[ "$sequence" == "" ]]; then
    instance="undefined"
fi

if [[ "$nproc" == "" ]]; then
    nproc=$(nproc)
fi


if [[ "$esm_model" == "" ]];then
    esm_model="all"
fi

if [[ "$msa_samples" == "" ]];then
    msa_samples=400
fi

if [[ "$esm_model" == "esm-1v" ]];then
    model_name="esm-1v"
    model_names="esm-1v_1 esm-1v_2 esm-1v_3 esm-1v_4 esm-1v_5 "
    model_path="${pretrained_data_dir}/esm1v_t33_650M_UR90S_1.pt ${pretrained_data_dir}/esm1v_t33_650M_UR90S_2.pt ${pretrained_data_dir}/esm1v_t33_650M_UR90S_3.pt ${pretrained_data_dir}/esm1v_t33_650M_UR90S_4.pt ${pretrained_data_dir}/esm1v_t33_650M_UR90S_5.pt "
elif [[ "$esm_model" == "msa-1b" ]];then
    model_name="msa-1b"
    model_names="msa-1b "
    model_path="${pretrained_data_dir}/esm_msa1b_t12_100M_UR50S.pt "

elif [[ "$esm_model" == "esm-2" || "$esm_model" =~ "esm2" ]];then
    model_name="esm-2"
    model_names="esm-2 "
    model_path="${pretrained_data_dir}/esm2_t36_3B_UR50D.pt "

elif [[ "$esm_model" == 'all' ]]; then
    model_name='all'
    model_names="esm-1v_1 esm-1v_2 esm-1v_3 esm-1v_4 esm-1v_5 msa-1b esm-2 "
    model_path="${pretrained_data_dir}/esm1v_t33_650M_UR90S_1.pt ${pretrained_data_dir}/esm1v_t33_650M_UR90S_2.pt ${pretrained_data_dir}/esm1v_t33_650M_UR90S_3.pt ${pretrained_data_dir}/esm1v_t33_650M_UR90S_4.pt ${pretrained_data_dir}/esm1v_t33_650M_UR90S_5.pt ${pretrained_data_dir}/esm_msa1b_t12_100M_UR50S.pt ${pretrained_data_dir}/esm2_t36_3B_UR50D.pt "

else
    usage
fi

if [[ "$esm_model" == "msa-1b" || "$esm_model" == "all" ]];then
    if [[ "$scoring_strategy" != 'masked-marginals' ]];then
        echo "Fix scoring strategy to masked-marginals for msa-1b."
        scoring_strategy='masked-marginals'
    fi
    if [[ ! -f $alignment ]];then
        echo "MSA not found or unaccessible: $alignment"
        if [[ "$(which hhblits)" != "" ]];then
            RUN_HHBLITS ${instance} ${sequence}
            # expected msa: ./MSA/${instance}.i90c75.a3m
            alignment="./MSA/${instance}.i90c75_aln.fas"
            msa_flag=" --msa-path ${alignment} --msa-samples ${msa_samples} "
        else
            usage
        fi
    else
        echo "MSA: ${alignment}"
        msa_flag=" --msa-path ${alignment} --msa-samples ${msa_samples} "
    fi
fi


# generate Deep Mutation Scan joblist.
# expected job list: ./dms_job_list/${instance}_DMS_${model_name}.csv
if [[ ! -f ./dms_job_list/${instance}_DMS_${model_name}.csv ]];then
cmd="python $PROTEIN_DESIGN_KIT/2._Working/1._MutationEffects/ESM-1v/generate_dms.py \
    --sequence ${sequence} \
    --dms_output_csv ./dms_job_list/${instance}_DMS_${model_name}.csv"
    echo "$cmd"
    eval "$cmd"

else
    echo "Previous job list for ${instance} is found: ./dms_job_list/${instance}_DMS_${model_name}.csv"
fi

# run DMS:
if [[ ! -f ./dms_job_list/${instance}_DMS_${model_name}_labeled.csv ]];then
cmd="python $PROTEIN_DESIGN_KIT/2._Working/1._MutationEffects/ESM-1v/predict.py \
    --sequence ${sequence} ${msa_flag}\
    --model-location \
        ${model_path} \
    --dms-input ./dms_job_list/${instance}_DMS_${model_name}.csv \
    --mutation-col  mutations \
    --dms-output ./dms_job_list/${instance}_DMS_${model_name}_labeled.csv  \
    --scoring-strategy ${scoring_strategy}  \
    --offset-idx 1 ${use_gpu_flag} "
    echo "$cmd"
    eval "$cmd"
else
    echo "Previous labeled DMS data for ${instance} is found: ./dms_job_list/${instance}_DMS_${model_name}_labeled.csv"
fi

# plot it!
echo "Now plot the results ... "
cmd="python $PROTEIN_DESIGN_KIT/2._Working/1._MutationEffects/ESM-1v/ESM-1v_DMS_plot.py \
    --sequence ${sequence} \
    --instance ${instance} \
    --model_names ${model_names} \
    --models ${model_path} \
    --esm_dms_csv ./dms_job_list/${instance}_DMS_${model_name}_labeled.csv \
    --save_dir save_dms_${instance}_${model_name}"
echo "$cmd"
eval "$cmd"