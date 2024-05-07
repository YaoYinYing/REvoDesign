#! bash

# A helper script for creating and managing self-hosted GitHub CI runners (Ubuntu)

set -e


function download_runner_image(){
    image_url=$1
    if [[ -z "${image_url}" ]]; then
        echo "Please input the url of runner image from GitHub (See: https://github.com/actions/runner/releases/)"
        read image_url;
    fi

    check_runner_url $image_url

    runner_image_zipped=$(basename "${image_url}")

    if [[ ! -f "${runner_image_zipped}" ]];then
        wget $image_url
    fi

}

function check_runner_url() {
    local url="$1"
    if [[ -z "${url}" ]]; then
        echo "ERROR: Please provide a viable URL for downloading the runner image."
        exit -1
    elif [[ ! ($url = "https"* &&  $url = *".tar.gz") ]];then
	echo $url
        echo "ERROR: Please provide a viable URL for downloading the runner image: http://*.tar.gz"
        exit -1
    fi
}

function check_runner_number() {
    local number="$1"
    if [[ -z "${number}" ]]; then
        echo "ERROR: Please provide a viable number for creating the runner instances."
        exit -1
    elif [[ ! $number  -gt 0 ]];then
        echo "ERROR: The number for creating the runner instances must greater than zero."
        exit -1
    elif [[ $number -gt 5 ]];then
        echo "WARNNING: The number for creating the runner instances is too large (at most 5 is recommended)."
    fi
}

function check_runner_prefix(){
    local prefix="$1"
    if [[ -z "${prefix}" ]];then
        echo "ERROR: Please provide a viable prefix for creating the runner instances"
        exit 1
    elif [[ $url2 = *' '* ]];then
        echo "Runner prefix must not contain spaces!"
        exit 1
    fi
}

function check_runner_image_sha256(){
    local image_file="$1"
    image_image_sha="$2"
    if [[ -z "${image_image_sha}" ]];then
        echo 'SHA256?'
        read image_image_sha
    fi
    echo "$image_image_sha  $image_file"
    echo "$image_image_sha  $image_file" | shasum -a 256 -c --strict

}

function install_runner(){
    download_runner_image $1

    check_runner_image_sha256 $runner_image_zipped $2

    echo "Downloading is complete."
    echo 'How many parallel runner you wish to create?'
    read runner_number

    check_runner_number $runner_number

    echo 'What prefix you wish it to call ? [`japs_runner` for example]'
    read runner_prefix

    check_runner_prefix $runner_prefix

    for i in $(seq 1 $runner_number);do
        runner_dir="${runner_prefix}_${i}"
	echo "Creating $runner_dir ..."
        mkdir -p ${runner_dir}/actions-runner;
        cd ${runner_dir}/actions-runner;
        tar xzf ../../${runner_image_zipped};
        cd ../../;
    done
}

function check_runner_path(){
    local runner_path=$1
    if [[ ! -d $runner_path ]];then
        echo "ERROR: Failed to find runner path ${runner_path}"
        exit 1
    fi
}

function read_runner_prefix_from_env(){
    if [[ -z "${runner_prefix}" ]];then
        echo "Please specify a prefix for the runners:"
        read runner_prefix
        check_runner_prefix $runner_prefix
    fi
}

function check_env_file(){
    if [[ ! -f '.env' ]];then
        echo "ERROR: Cannot find .env file for proxies"
        exit 1
    fi
}


function ping_pong_setup(){
    local url=$1
    local dir=$2
    local labels=$3

    echo Token please:
    read token

    expect_scripts='spawn /bin/bash ./config.sh --url '$url'; 

 	expect "*runner register token*"; 
 	send -- "'$token'\r";

 	expect "Enter the name of the runner group*";
 	send -- "\r";

 	expect "Enter the name of runner:*"; 
 	send -- "'${dir/_/-}'\r";

 	expect "Enter any additional labels*"; 
 	send -- "'$labels'\r";
    
    expect "Enter name of work folder*";
    send -- "\r";
    '
    

    echo $expect_scripts
    sleep 0.3
    expect -c "$expect_scripts"

}

function help_msg(){
    exec='bash ci-runner.admin.sh'
    echo "
Setup paralell GitHub self-hosted runner in a snap finger.

Usage: ${exec} command [options]
  command:
    install [url] [sha256]    Install runner from image file.
    register                  Register runner one-after-another to GitHub.
    enable                    Enable runners as system service for a target user.
    disable                   Disable runners as system service for a target user.
    uninstall | remove        Remove runners one-after-another from GitHub.
    restart | reboot          Restart runners via system service.
    proxies | proxy           Setting proxies to runners by linking '.env' file. 
                              A service restart is required.
                              
    help | -h | --help        Show this help message and exit.
    
    "
    exit 0

}


if [[ "$1" == 'install' ]];then
    install_runner $2 $3
elif [[ "$1" == 'help' || "$1" == '-h' || "$1" == '--help' ]];then
        help_msg
else
    read_runner_prefix_from_env

    if [[ "$1" == 'register' ]];then
        echo Which GitHub Repo url you wish to be registered for?
        read github_url
        echo What kind of labels can these runner call?
        read labels


        for dir in ${runner_prefix}_*; do
            check_runner_path $dir
            cd $dir/actions-runner/;

            # register runner
            ping_pong_setup $github_url $dir $labels

            cd ../..;
        done
    elif [[ "$1" == 'enable' ]];then
        echo Which user you wish to enable for?
        read enable_user
        for dir in ${runner_prefix}_*; do
            check_runner_path $dir
            cd $dir/actions-runner/;

            # enable runner as service
            ./svc.sh install $enable_user

            cd ../..;
        done

    elif [[ "$1" == 'disable' ]];then
        for dir in ${runner_prefix}_*; do
            check_runner_path $dir
            cd $dir/actions-runner/;

            # disable runner from service
            ./svc.sh stop
            ./svc.sh uninstall;

            cd ../..;
        done
    elif [[ "$1" == 'uninstall' || "$1" == 'remove' ]];then
        for dir in ${runner_prefix}_*; do
            check_runner_path $dir
            cd $dir/actions-runner/;

            echo Token please: 
            read token

            # remove config from repository
            ./config.sh remove --token $token;

            cd ../..;
        done
    elif [[ "$1" == 'restart' || "$1" == 'reboot' ]];then
        for dir in ${runner_prefix}_*; do
            check_runner_path $dir
            cd $dir/actions-runner/;
            echo Restarting $dir ... this may take a while...

            # restart runner from service
            ./svc.sh stop && ./svc.sh start &

            cd ../..;
        done
        wait
    elif [[ "$1" == 'proxies' || "$1" == 'proxy' ]];then
        check_env_file

        for dir in ${runner_prefix}_*; do
            check_runner_path $dir

            # link env file for proxies
            rm $dir/actions-runner/.env;
            ln .env $dir/actions-runner/.env;

        done

    elif [[ "$1" == 'clean' || "$1" == 'prune' ]];then
        for dir in ${runner_prefix}_*; do
            check_runner_path $dir
            selected_dir=$dir/actions-runner/_work

            # link env file for proxies
            rm -rvf $selected_dir;
            mkdir -p $selected_dir
        done
    
    fi

fi

