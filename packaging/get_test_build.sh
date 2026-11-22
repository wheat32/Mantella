#!/usr/bin/env bash
# Builds the mod archive of the current branch on GitHub Actions (Mantella.exe has to be built on Windows)
# and downloads it to dist/, ready to be installed with Mod Organizer 2 ("Install a new mod from an archive").
#
# Requires the GitHub CLI (gh) to be logged in. The branch must be pushed: the build uses what is on GitHub.
set -euo pipefail

cd "$(git rev-parse --show-toplevel)"
branch="$(git rev-parse --abbrev-ref HEAD)"

if [[ -n "$(git status --porcelain)" ]]; then
    echo "Note: you have uncommitted changes. They will not be part of the build."
fi
if [[ "$(git rev-parse HEAD)" != "$(git rev-parse "origin/${branch}" 2>/dev/null || true)" ]]; then
    echo "Error: '${branch}' has commits that are not on GitHub yet. Push the branch first." >&2
    exit 1
fi

echo "Starting a build of '${branch}'..."
gh workflow run ci.yml --ref "${branch}"
sleep 5 # give GitHub a moment to register the run
run_id="$(gh run list --workflow ci.yml --branch "${branch}" --event workflow_dispatch --limit 1 --json databaseId --jq '.[0].databaseId')"

gh run watch "${run_id}" --exit-status
mkdir -p dist
gh run download "${run_id}" --name mod-archive-ci --dir dist
echo
echo "Downloaded:"
ls -1 dist/*.zip
