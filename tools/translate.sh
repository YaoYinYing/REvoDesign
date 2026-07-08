
# stop at which stage, default is compile only
stage=$stage || stage='compile'

pylupdate5_path=$(which pylupdate5)
lrelease_path=$(which lrelease)

echo "Using pylupdate5 at: $pylupdate5_path"
echo "Using lrelease at: $lrelease_path"

# update translation files from .ui widget strings
# Dynamic-menu and dialog strings in Python source are hand-maintained in the .ts files.
# pylupdate5 marks hand-maintained entries as "obsolete" because they are not found in
# the .ui file — strip the attribute so lrelease includes them in the compiled .qm.
for i in src/REvoDesign/UI/language/*.ts; do
    echo "Updating $i"
    $pylupdate5_path src/REvoDesign/UI/REvoDesign.ui src/REvoDesign/UI/value_dialog.ui src/REvoDesign/UI/launching.ui -ts "$i"
    # sed -i with backup extension is portable across BSD (macOS) and GNU/Linux.
    sed -i.bak 's/ type="obsolete"//g' "$i"
    rm -f "$i.bak"
    # pylupdate5 marks entries "unfinished" when .ui line numbers shift
    # even though the translation text is still valid.  Strip the flag so
    # lrelease includes them.
    sed -i.bak 's/ type="unfinished"//g' "$i"
    rm -f "$i.bak"
done
echo "Translation files updated."
if [ "$stage" == 'translate' ]; then echo Done with "$stage";exit 0; fi


# release translation file to binarys
echo Releasing translation files to binarys...
cd src/REvoDesign/UI/ || exit;lrelease liguist.pro;cd ../../..
echo Done.