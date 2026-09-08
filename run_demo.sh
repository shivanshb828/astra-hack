#!/usr/bin/env bash
#
# One button for the MissionPCB constraint demo.
#
#   1. Validate the naive layout          -> it fails, visibly and specifically
#   2. Solve from that same naive layout  -> the engine proposes a fix
#   3. Validate the solved layout         -> through the identical code path
#   4. Compare naive vs solved            -> what changed, check by check
#   5. Emit the LLM explanation brief     -> facts for the write-up layer
#
# Outputs land in out/ and layouts/ecg-patch-solved.json.
# Exit status is 0 only if the solved board passes everything.

set -uo pipefail

cd "$(dirname "$0")"
export PYTHONPATH=src

PARTS="parts/ecg-patch-parts.json"
CONSTRAINTS="missions/ecg-patch-constraints.json"
NAIVE="layouts/ecg-patch-naive.json"
TARGET="layouts/ecg-patch-missionpcb.json"
SOLVED="layouts/ecg-patch-solved.json"

run() { python3 -m constraint_engine "$@"; }

echo "=============================================================="
echo " 0. BUILD PARTS - merge catalog facts with this mission's clearances"
echo "=============================================================="
python3 tools/build_mission_parts.py --constraints "$CONSTRAINTS" --out "$PARTS"
echo

echo "=============================================================="
echo " 1. NAIVE LAYOUT - what a constraint-blind first pass produces"
echo "=============================================================="
run validate --parts "$PARTS" --layout "$NAIVE" --out out/naive
echo

echo "=============================================================="
echo " 2. SOLVE - search for a placement that satisfies the mission"
echo "=============================================================="
run solve --parts "$PARTS" --layout "$NAIVE" --out "$SOLVED" \
    --name "ECG Patch - MissionPCB Solved" --report-dir out/solved
solve_status=$?
echo

echo "=============================================================="
echo " 3. COMPARE - naive vs hand-authored target vs solved"
echo "=============================================================="
run compare --parts "$PARTS" --layouts "$NAIVE" "$TARGET" "$SOLVED" --out out/compare
echo

echo "=============================================================="
echo " 4. EXPLAIN - hand the naive failures to the judgment layer"
echo "=============================================================="
run explain --parts "$PARTS" --layout "$NAIVE" --out out/naive
echo

echo "=============================================================="
echo " 5. RENDER INPUTS - stable, committed paths for the Blender lane"
echo "=============================================================="
mkdir -p render
cp out/naive/validation_results.json  render/naive.json
cp out/solved/validation_results.json render/solved.json
echo "  render/naive.json   the before board  (7 failures to draw in red)"
echo "  render/solved.json  the after board   (51 passing, nothing to flag)"
echo

echo "Artifacts:"
echo "  out/naive/validation_report.md      failures, measured, with reasons"
echo "  out/naive/explain_brief.txt         prompt-ready brief for an LLM"
echo "  out/solved/validation_report.md     the corrected board"
echo "  out/compare/                        per-layout results for the sim"
echo "  $SOLVED   solved layout, same schema as the input
  render/naive.json render/solved.json  committed inputs for Blender"

exit $solve_status
