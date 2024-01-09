#! bash
old_version=$(git diff REvoDesign/__version__.py | grep '^\-__version__=' | awk '{str=$2;gsub("'\''","",str);print str}')
new_version=$(git diff REvoDesign/__version__.py | grep '^+__version__=' | awk '{str=$2;gsub("'\''","",str);print str}')
new_date=$(date +'%Y-%m-%d')

# exit if any of the variables are missing.
if [[ ! $new_version || ! $old_version || ! $new_date  ]];then 
    echo "Error: $new_version , $old_version, $$new_date"
    exit 1;
fi
if [[ $new_version == $old_version ]];then 
    echo same version number: $new_version == $old_version;
    exit 1;
fi

# set new tag to changelog
sed -i 's/## \[Unreleased\]/## [Unreleased]\n\n## \['"$new_version"'\] - '"$new_date"'/' ./CHANGELOG.md

# set new tag to changelog
sed -i 's/^version = \"'"$old_version"'\"/version = \"'"$new_version"'\"/' ./pyproject.toml

# collect version files
git add ./CHANGELOG.md ./pyproject.toml REvoDesign/__version__.py
# version commit
git commit -m 'Dump version: '"$old_version"' -> '"$new_version"''
# push
git push 

# set git tag
git tag v$new_version
git push origin --tags
