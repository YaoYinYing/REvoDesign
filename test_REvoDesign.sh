#! /bin/sh

# kill all PyMOL session
#ps aux |grep '/Applications/PyMOL.app' |awk '{system("kill "$2)}'
git_repo_dir="$(dirname "$0")"
# copy the package
rm -r $HOME/.pymol/startup/REvoDesign
cp -r $git_repo_dir/REvoDesign $HOME/.pymol/startup

# launch a new session
pymol /Users/yyy/Documents/projects/hands/SXL/CHS/models/diffdock_conformer/CHS_CM4.diffdock.unrelaxed.pdb