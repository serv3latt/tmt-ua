#!/bin/sh
# Publishes the current app/ folder to the public repository behind GitHub
# Pages (decision 49). Only the contents of app/ are copied, into a separate
# clone in .publish/ (ignored by the research repo), so neither the research
# files nor the research repo's history ever reach the public repository.
#
# Run from the research repo root:  sh app/tools/publish.sh "commit message"

set -eu

REPO_URL=https://github.com/serv3latt/tmt-ua.git
ROOT=$(git rev-parse --show-toplevel)
WORK="$ROOT/.publish"
MESSAGE=${1:?"Usage: sh app/tools/publish.sh \"commit message\""}

if [ ! -d "$WORK/.git" ]; then
  git clone --quiet "$REPO_URL" "$WORK"
fi
cd "$WORK"
git pull --quiet --ff-only 2>/dev/null || true # a fresh empty repo has nothing to pull

rsync -a --delete --exclude .git --exclude __pycache__ --exclude .DS_Store "$ROOT/app/" "$WORK/"

git add -A
if git diff --cached --quiet; then
  echo "Nothing to publish: the public repository already matches app/."
  exit 0
fi
git commit --quiet -m "$MESSAGE"
git push --quiet -u origin HEAD:main
echo "Published $(git rev-parse --short HEAD) to $REPO_URL"
