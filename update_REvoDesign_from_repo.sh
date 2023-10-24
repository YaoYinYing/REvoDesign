#! /bin/sh

git_repo_dir="$(dirname "$0")"

python_exe=$(which python)

$python_exe -m pip install $git_repo_dir --upgrade
