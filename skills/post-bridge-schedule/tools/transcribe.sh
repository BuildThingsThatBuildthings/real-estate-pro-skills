#!/bin/bash
# Transcribe every video in a folder so captions are grounded in what was said.
#   transcribe.sh <folder> [out-dir]
#
# -nostdin and </dev/null are mandatory: ffmpeg consumes stdin inside a read
# loop and silently truncates filenames without them.
set -e
DIR="${1:?usage: transcribe.sh <folder> [out-dir]}"
OUT="${2:-$DIR/transcripts}"
CFG_DIR="${RE_SKILLS_CONFIG_DIR:-$(cd "$(dirname "$0")/../../.." && pwd)/config}"
MODEL=$(python3 -c "import json,os;p=os.path.expanduser('$CFG_DIR/pipeline.json');print(os.path.expanduser(json.load(open(p))['tools']['whisper_model'])) if os.path.isfile(p) else print('')" 2>/dev/null)
BIN=$(python3 -c "import json,os;p=os.path.expanduser('$CFG_DIR/pipeline.json');print(json.load(open(p))['tools'].get('whisper_cli','whisper-cli')) if os.path.isfile(p) else print('whisper-cli')" 2>/dev/null)
[ -f "$MODEL" ] || { echo "whisper model not found: $MODEL (set tools.whisper_model in pipeline.json)"; exit 1; }
mkdir -p "$OUT"
for f in "$DIR"/*.mp4 "$DIR"/*.mov; do
  [ -e "$f" ] || continue
  slug=$(basename "${f%.*}")
  [ -s "$OUT/$slug.txt" ] && { echo "skip $slug"; continue; }
  ffmpeg -nostdin -v error -y -i "$f" -ar 16000 -ac 1 -c:a pcm_s16le "/tmp/w_$$.wav" </dev/null
  "$BIN" -m "$MODEL" -f "/tmp/w_$$.wav" -nt -np </dev/null 2>/dev/null \
    | tr '\n' ' ' | sed 's/  */ /g;s/^ //' > "$OUT/$slug.txt"
  rm -f "/tmp/w_$$.wav"
  echo "done $slug ($(wc -w < "$OUT/$slug.txt") words)"
done
