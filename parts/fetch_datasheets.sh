#!/usr/bin/env bash
# Fetch datasheet PDFs listed in parts/sources.json into parts/datasheets/ (gitignored).
set -uo pipefail
cd "$(dirname "$0")/.."
UA="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
mkdir -p parts/datasheets
python3 - <<'PY' > /tmp/_ds_list.txt
import json
for p in json.load(open("parts/sources.json"))["parts"]:
    if p["url"]: print(p["id"], p["url"])
PY
while read -r id url; do
  out="parts/datasheets/${id}.pdf"
  code=$(curl -sS -L -A "$UA" --max-time 45 -w '%{http_code}' -o "$out" "$url" 2>/dev/null || echo "ERR")
  if [ -f "$out" ]; then
    sz=$(stat -f%z "$out" 2>/dev/null || echo 0)
    kind=$(file -b --mime-type "$out")
  else sz=0; kind="none"; fi
  if [ "$kind" = "application/pdf" ] && [ "$sz" -gt 20000 ]; then
    printf 'OK    %-14s %6s KB  %s\n' "$id" "$((sz/1024))" "$code"
  else
    printf 'FAIL  %-14s %6s KB  http=%s type=%s\n' "$id" "$((sz/1024))" "$code" "$kind"
    rm -f "$out"
  fi
done < /tmp/_ds_list.txt
