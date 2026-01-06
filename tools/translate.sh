# recompile ui to py
pyuic5_path=$(which pyuic5)
lupdate_path=$(which lupdate)
lrelease_path=$(which lrelease)

echo "Using pyuic5 at: $pyuic5_path"
echo "Using lupdate at: $lupdate_path"
echo "Using lrelease at: $lrelease_path"

echo "Compiling UI to Py code..."
pyuic5 src/REvoDesign/UI/REvoDesign.ui -o src/REvoDesign/UI/Ui_REvoDesign.py
# update translation files
for i in $(ls src/REvoDesign/UI/language/*.ts); do
    echo "Updating $i"
    lupdate  src/REvoDesign/UI/REvoDesign.ui -ts $i
done
echo "Translation files updated."
# release translation file to binarys
echo Releasing translation files to binarys...
cd src/REvoDesign/UI/;lrelease liguist.pro;cd ../../..
echo "Done."