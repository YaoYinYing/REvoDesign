
# stop at which stage, default is compile only
stage=$stage || stage='compile'

black_path=$(which black)
pyuic5_path=$(which pyuic5)
lupdate_path=$(which lupdate)
lrelease_path=$(which lrelease)

echo "Using pyuic5 at: $pyuic5_path"
echo "Using lupdate at: $lupdate_path"
echo "Using lrelease at: $lrelease_path"

# recompile ui to py
echo "Compiling UI to Py code..."
pyuic5 src/REvoDesign/UI/REvoDesign.ui -o src/REvoDesign/UI/Ui_REvoDesign.py
echo Compiled UI to Py code at src/REvoDesign/UI/Ui_REvoDesign.py
# format ui code
echo Formatted UI code ...
$black_path src/REvoDesign/UI/Ui_REvoDesign.py
echo Done formatting UI code.

if [ "$stage" == 'compile' ]; then echo Done with "$stage";exit 0; fi

# update translation files
for i in $(ls src/REvoDesign/UI/language/*.ts); do
    echo "Updating $i"
    lupdate  src/REvoDesign/UI/REvoDesign.ui -ts "$i"
done
echo "Translation files updated."
if [ "$stage" == 'translate' ]; then echo Done with "$stage";exit 0; fi


# release translation file to binarys
echo Releasing translation files to binarys...
cd src/REvoDesign/UI/ || exit;lrelease liguist.pro;cd ../../..
echo Done.