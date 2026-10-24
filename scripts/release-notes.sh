#!/usr/bin/env bash
# The version bump and release notes for a range of commits (plan 010), used by release.sh.
#
#   scripts/release-notes.sh <from>..<to>
#
# Run in the repo. Prints the bump (major, minor or patch) on the first line, then the notes
# in Markdown: the commit subjects grouped by their Conventional Commits type (CLAUDE.md).
set -euo pipefail

[ $# = 1 ] || {
  echo "usage: $0 <from>..<to>" >&2
  exit 2
}

breaking=() features=() fixes=() other=()
while IFS= read -r hash; do
  subject="$(git log -1 --format=%s "$hash")"
  # A subject that doesn't follow the rule goes under Other, as it is.
  type="" bang="" text="$subject"
  if [[ $subject =~ ^([a-z]+)(\([^\)]*\))?(!)?:\ *(.+)$ ]]; then
    type="${BASH_REMATCH[1]}" bang="${BASH_REMATCH[3]}" text="${BASH_REMATCH[4]}"
  fi
  why="$(git log -1 --format=%b "$hash" | sed -n 's/^BREAKING[ -]CHANGE: *//p' | head -n 1)"
  if [ -n "$bang" ] || [ -n "$why" ]; then
    breaking+=("$text${why:+: $why}")
  elif [ "$type" = feat ]; then
    features+=("$text")
  elif [ "$type" = fix ]; then
    fixes+=("$text")
  else
    other+=("$text")
  fi
done < <(git log --no-merges --reverse --format=%H "$1")

if [ ${#breaking[@]} -gt 0 ]; then
  echo major
elif [ ${#features[@]} -gt 0 ]; then
  echo minor
else
  echo patch
fi

section() {
  local title="$1"
  shift
  [ $# -gt 0 ] || return 0
  printf '\n## %s\n\n' "$title"
  printf -- '- %s\n' "$@"
}
section "Breaking changes" "${breaking[@]+"${breaking[@]}"}"
section "Features" "${features[@]+"${features[@]}"}"
section "Fixes" "${fixes[@]+"${fixes[@]}"}"
section "Other" "${other[@]+"${other[@]}"}"
[ $((${#breaking[@]} + ${#features[@]} + ${#fixes[@]} + ${#other[@]})) -gt 0 ] || printf '\nNo changes.\n'
