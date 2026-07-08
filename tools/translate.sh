
# stop at which stage, default is compile only
stage=$stage || stage='compile'

pylupdate5_path=$(which pylupdate5)
lrelease_path=$(which lrelease)

echo "Using pylupdate5 at: $pylupdate5_path"
echo "Using lrelease at: $lrelease_path"

# update translation files
# Scans REvoDesign.ui for widget strings, and application/ for QCoreApplication.translate()
# calls (menu.py, language_settings.py, etc.)
for i in $(ls src/REvoDesign/UI/language/*.ts); do
    echo "Updating $i"
    $pylupdate5_path \
        src/REvoDesign/UI/REvoDesign.ui \
        src/REvoDesign/application/menu.py \
        src/REvoDesign/application/i18n/language_settings.py \
        -ts "$i"
done
echo "Translation files updated."
if [ "$stage" == 'translate' ]; then echo Done with "$stage";exit 0; fi


# release translation file to binarys
echo Releasing translation files to binarys...
cd src/REvoDesign/UI/ || exit;lrelease liguist.pro;cd ../../..
echo Done.