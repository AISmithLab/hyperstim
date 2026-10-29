#!/usr/bin/env bash
# The daily commit of the collected dataset (plan 013), run by the server's timer as the data
# bot's user. Copies the collector's exported files into a clone of this repo, commits them
# as a `data:` commit and pushes to main. The site doesn't wait for this: the API reads the
# collector's files directly. This is the public record and a second copy.
#
#   scripts/commit-data.sh <clone> <collected-dir>
#
# <clone> is the bot's own clone (never a dev checkout); its origin must accept the bot's
# deploy key. Does nothing when nothing changed.
set -euo pipefail

[ $# = 2 ] || {
  echo "usage: $0 <clone> <collected-dir>" >&2
  exit 2
}
CLONE="$1" SOURCE="$2"
DEST="backend/data/collected"
git=(git -C "$CLONE" -c user.name="HyperStim data bot" -c user.email="hyperstim-data-bot@users.noreply.github.com")

"${git[@]}" fetch --quiet origin main
"${git[@]}" checkout --quiet -B main origin/main
mkdir -p "$CLONE/$DEST"
files=()
for f in "$SOURCE"/[0-9][0-9][0-9][0-9].tsv "$SOURCE"/{removed.tsv,excluded-channels.tsv,CHANGELOG.tsv,meta.json}; do
  [ -f "$f" ] && files+=("$f")
done
[ ${#files[@]} -gt 0 ] || exit 0
cp "${files[@]}" "$CLONE/$DEST/"
"${git[@]}" add -- "$DEST"
"${git[@]}" diff --cached --quiet && exit 0

# The message counts what's new since the last commit: rows in the year files and in
# removed.tsv (without their header lines), and the change in channels (the changelog's
# latest day, its columns found by name).
rows() { # <rev, ":0" for the staged files> <path>...
  local rev="$1" n=0 path
  shift
  for path in "$@"; do
    n=$((n + $("${git[@]}" show "$rev:$path" 2>/dev/null | tail -n +2 | wc -l)))
  done
  echo "$n"
}
mapfile -t years < <("${git[@]}" ls-files -- "$DEST/[0-9][0-9][0-9][0-9].tsv")
added=$(($(rows :0 "${years[@]}") - $(rows HEAD "${years[@]}")))
removed=$(($(rows :0 "$DEST/removed.tsv") - $(rows HEAD "$DEST/removed.tsv")))
channels() {
  "${git[@]}" show "$1:$DEST/CHANGELOG.tsv" 2>/dev/null |
    awk -F'\t' 'NR == 1 { for (i = 1; i <= NF; i++) col[$i] = i; next }
      $1 > day { day = $1; n = $col["channels"] } END { print n }'
}
before="$(channels HEAD || true)" after="$(channels :0 || true)"
new_channels=0
[[ $before =~ ^[0-9]+$ && $after =~ ^[0-9]+$ ]] && new_channels=$((after - before))
plural() { [ "$1" = 1 ] && echo "$1 $2" || echo "$1 ${2}s"; }
subject="data: Add $(plural "$added" video)"
[ "$new_channels" -gt 0 ] && subject+=" and $(plural "$new_channels" channel)"
[ "$removed" -gt 0 ] && subject+=", remove $removed"
subject+=" ($(date -u +%F))"
"${git[@]}" commit --quiet -m "$subject"

for attempt in 1 2 3; do
  if "${git[@]}" push --quiet origin main; then
    echo "$subject"
    exit 0
  fi
  # Someone pushed meanwhile: only the bot writes these files, so the rebase never conflicts.
  "${git[@]}" fetch --quiet origin main
  "${git[@]}" rebase --quiet origin/main
  sleep $((attempt * 10))
done
echo "commit-data: couldn't push" >&2
exit 1
