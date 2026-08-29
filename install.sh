#!/bin/bash
# Install every skill in this bundle into ~/.claude/skills
set -e
MODE="${1:---symlink}"
SRC="$(cd "$(dirname "$0")" && pwd)/skills"
DEST="$HOME/.claude/skills"
mkdir -p "$DEST"
for d in "$SRC"/*/; do
  name="$(basename "$d")"
  target="$DEST/$name"
  if [ -e "$target" ] || [ -L "$target" ]; then
    echo "exists, skipping: $name  (remove $target to reinstall)"
    continue
  fi
  if [ "$MODE" = "--copy" ]; then cp -R "$d" "$target"; echo "copied:    $name"
  else ln -s "${d%/}" "$target"; echo "symlinked: $name"; fi
done
echo "done. skills in $DEST"
