# recompile ui to py

pyuic5 src/REvoDesign/UI/REvoDesign.ui -o src/REvoDesign/UI/Ui_REvoDesign.py
# update translation files
for i in $(ls src/REvoDesign/UI/language/*.ts); do
    lupdate  src/REvoDesign/UI/REvoDesign.ui -ts $i
done

# release translation file to binarys
cd src/REvoDesign/UI/;lrelease liguist.pro;cd ../../..