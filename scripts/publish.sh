#!/usr/bin/env bash
# Run locally after signing into GitHub CLI. Never paste tokens into chat.
# Creates a new private repository. No force pushes, deletes, or changes to existing apps.
set -euo pipefail
cd "$(dirname "$0")/.."
command -v gh >/dev/null || { echo 'Install GitHub CLI first.'; exit 1; }
gh auth status >/dev/null
OWNER="$(gh api user --jq .login)"
REPO="$OWNER/foodlabel-scanner"
if gh repo view "$REPO" >/dev/null 2>&1; then
  echo "$REPO already exists. Aborting; this script will not modify an existing repository."
  exit 1
fi
if [ -d .git ]; then
  echo 'This directory already contains a Git repository. Review it and publish manually.'
  exit 1
fi
git init -b main
git add .
git commit -m 'Build FoodLens Dutch-to-English food label scanner MVP'
gh repo create "$REPO" --private --source=. --remote=origin --push --description 'Dutch-to-English food label translation and conservative dietary checks'
git branch stage
git push origin stage
echo "Created private repository: https://github.com/$REPO"
