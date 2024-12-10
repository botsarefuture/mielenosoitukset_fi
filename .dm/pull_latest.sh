#!/bin/bash

# Pull the latest changes from the specified branch of the remote repository
# Usage: ./pull_latest.sh branch

if [ -z "$1" ]; then
    echo "Error: No branch specified."
    echo "Usage: ./pull_latest.sh branch"
    exit 1
fi

branch=$1
origin_url="https://github.com/botsarefuture/mielenosoitukset_fi.git"

git fetch "$origin_url" "$branch"
git reset --hard FETCH_HEAD
git clean -fd