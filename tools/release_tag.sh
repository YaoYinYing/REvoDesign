#! bash
echo 'Dumping version from `REvoDesign/__version__.py` ...'
old_version=$(git diff REvoDesign/__version__.py | grep '^\-__version__=' | awk '{str=$2;gsub("'\''","",str);print str}')
new_version=$(git diff REvoDesign/__version__.py | grep '^+__version__=' | awk '{str=$2;gsub("'\''","",str);print str}')
new_date=$(date +'%Y-%m-%d')

echo "New Version: ${new_version}, Old Version: ${old_version}, tagged date: ${new_date}"

echo 'Checking version ...'
# exit if any of the variables are missing.
if [[ ! $new_version || ! $old_version || ! $new_date  ]];then 
    echo "Error: $new_version , $old_version, $new_date"
    exit 1;
fi
if [[ $new_version == $old_version ]];then 
    echo Same version number: $new_version == $old_version;
    exit 1;
fi
echo 'Done.'

echo set new tag to changelog
sed -i 's/## \[Unreleased\]/## [Unreleased]\n\n## \['"$new_version"'\] - '"$new_date"'/' ./CHANGELOG.md

echo set new tag to pyproject
sed -i 's/^version = \"'"$old_version"'\"/version = \"'"$new_version"'\"/' ./pyproject.toml

echo  collect version files and creating new commit...
git add ./CHANGELOG.md ./pyproject.toml REvoDesign/__version__.py
# version commit
git commit -m 'Dump version: '"$old_version"' -> '"$new_version"''
echo pushing new version
git push 

echo set git tag ..
git tag v$new_version
git push origin --tags
