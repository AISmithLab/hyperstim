#!/usr/bin/env bash
# The version bump and release notes for a range of commits (plan 010), used by release.sh.
#
#   scripts/release-notes.sh <from>..<to>
#
# Run in the repo. Prints the bump (major, minor or patch; none when there are only `data:`
# commits) on the first line, then the notes in Markdown: the commit subjects grouped by their
# Conventional Commits type (CLAUDE.md). The daily `data:` commits (plan 013) aren't listed:
# one line says how the dataset grew instead.
set -euo pipefail

[ $# = 1 ] || {
  echo "usage: $0 <from>..<to>" >&2
  exit 2
}

breaking=() features=() fixes=() other=()
data=0
while IFS= read -r hash; do
  subject="$(git log -1 --format=%s "$hash")"
  # A subject that doesn't follow the rule goes under Other, as it is.
  type="" bang="" text="$subject"
  if [[ $subject =~ ^([a-z]+)(\([^\)]*\))?(!)?:\ *(.+)$ ]]; then
    type="${BASH_REMATCH[1]}" bang="${BASH_REMATCH[3]}" text="${BASH_REMATCH[4]}"
  fi
  why="$(git log -1 --format=%b "$hash" | sed -n 's/^BREAKING[ -]CHANGE: *//p' | head -n 1)"
  if [ "$type" = data ]; then
    data=$((data + 1))
  elif [ -n "$bang" ] || [ -n "$why" ]; then
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
elif [ $((${#fixes[@]} + ${#other[@]})) -gt 0 ]; then
  echo patch
else
  echo none
fi

# The dataset's size at a commit: the last line of the collector's changelog (videos, channels),
# else the reference set's count (videos only).
size() {
  local line
  line="$(git show "$1:backend/data/collected/CHANGELOG.tsv" 2>/dev/null | tail -n 1)" || true
  if [[ $line =~ ^[0-9]{4}- ]]; then
    awk -F'\t' '{ print $5 "\t" $6 }' <<<"$line"
  else
    git show "$1:backend/data/videos.meta.json" 2>/dev/null |
      sed -n 's/.*"videoCount": *\([0-9]*\).*/\1/p' | head -n 1
  fi
}
grouped() { LC_ALL=en_US.UTF-8 printf "%'d" "$1" 2>/dev/null || printf '%d' "$1"; }
if [ "$data" -gt 0 ]; then
  IFS=$'\t' read -r v0 c0 <<<"$(size "${1%%..*}")" || true
  IFS=$'\t' read -r v1 c1 <<<"$(size "${1#*..}")" || true
  if [ -n "${v0:-}" ] && [ -n "${v1:-}" ]; then
    line="$(grouped "$v0") → $(grouped "$v1") videos"
    [ -n "${c0:-}" ] && [ -n "${c1:-}" ] && line+=", $(grouped "$c0") → $(grouped "$c1") channels"
    printf '\nDataset: %s.\n' "$line"
  fi
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
[ $((${#breaking[@]} + ${#features[@]} + ${#fixes[@]} + ${#other[@]} + data)) -gt 0 ] || printf '\nNo changes.\n'
