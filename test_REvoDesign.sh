#! /bin/sh

# kill all PyMOL session
#ps aux |grep '/Applications/PyMOL.app' |awk '{system("kill "$2)}'

# copy the package
rm -r $HOME/.pymol/startup/REvoDesign
cp -r /Users/yyy/Documents/protein_design/REvoDesign/REvoDesign $HOME/.pymol/startup

# launch a new session
pymol $PROTEIN_DESIGN_KIT/2._Working/0._IntergatedProtocol/REvoDesign/tests/test_data/Test_Session.pze