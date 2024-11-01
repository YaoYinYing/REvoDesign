#! bash
set -e

if [[ $(uname -s) == 'Darwin' ]];then 
    SED=gsed;
    echo In Darwin, using gsed: GNU-sed
    if ! command -v gsed; then 
        echo GNU-sed is not found, fetching via homebrew...
        brew install gnu-sed;
    fi
else
    SED=sed;
fi

echo 'Dumping version from `src/REvoDesign/__init__.py` ...'
old_version=$(git diff src/REvoDesign/__init__.pyy | grep '^\-__version__ = ' | awk '{str=$3;gsub("'\''","",str);print str}')
new_version=$(git diff src/REvoDesign/__init__.py | grep '^+__version__ = ' | awk '{str=$3;gsub("'\''","",str);print str}')
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
$SED -i 's/## \[Unreleased\]/## [Unreleased]\n\n## \['"$new_version"'\] - '"$new_date"'/' ./CHANGELOG.md 
echo fetching changelog bwt two versions:
rm -f changelog_tag.md
echo 'Dump version: '"$old_version"' -> '"$new_version" > changelog_tag.md
echo >> changelog_tag.md
echo '## Change log:' >> changelog_tag.md
echo >> changelog_tag.md
$SED -n '/## \['"$new_version"'\]/,/## \['"$old_version"'\]/p' ./CHANGELOG.md |grep -v '^## \|^$' >> changelog_tag.md

cat changelog_tag.md

echo  collect version files and creating new commit...
git add ./CHANGELOG.md
# version commit
git commit -m 'Dump version: '"$old_version"' -> '"$new_version"''

echo pushing new version
echo set git tag ..
git tag -F changelog_tag.md v$new_version 

git push 
git push origin --tags
rm -f changelog_tag.md
