#!/usr/bin/env python3
"""Tiny KiCad control bridge for the widget demo.

This is deliberately file-based: the widget can turn language into a structured
action, call this script, and KiCad will see the board file change. A real
plugin can replace this once live in-app KiCad control is needed.
"""

from __future__ import annotations

import argparse
import json
import re
import uuid
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BOARD = ROOT / "kicad" / "ecg-patch" / "ecg-patch.kicad_pcb"


def _find_matching_close(text: str, start: int) -> int:
    depth = 0
    in_string = False
    escaped = False
    for i in range(start, len(text)):
        ch = text[i]
        if escaped:
            escaped = False
            continue
        if ch == "\\":
            escaped = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
            if depth == 0:
                return i
    raise ValueError("unbalanced KiCad s-expression")


def _footprints(text: str) -> list[tuple[str, int, int, str]]:
    out = []
    pos = 0
    while True:
        start = text.find("(footprint ", pos)
        if start == -1:
            break
        end = _find_matching_close(text, start) + 1
        block = text[start:end]
        ref = re.search(r'\(property\s+"Reference"\s+"([^"]+)"', block)
        if ref:
            out.append((ref.group(1), start, end, block))
        pos = end
    return out


def list_refs(board: Path) -> dict[str, object]:
    board = Path(board)
    text = board.read_text(encoding="utf-8")
    refs = []
    for ref, _, _, block in _footprints(text):
        at = re.search(r"\(at\s+([-0-9.]+)\s+([-0-9.]+)(?:\s+([-0-9.]+))?\)", block)
        refs.append(
            {
                "ref": ref,
                "position_mm": [float(at.group(1)), float(at.group(2))] if at else None,
                "rotation_deg": float(at.group(3) or 0) if at else 0,
            }
        )
    return {"board": str(board), "footprints": refs}


def move_ref(board: Path, ref: str, x: float, y: float, rotation: float | None) -> dict[str, object]:
    board = Path(board)
    text = board.read_text(encoding="utf-8")
    for found_ref, start, end, block in _footprints(text):
        if found_ref != ref:
            continue
        at = re.search(r"\(at\s+([-0-9.]+)\s+([-0-9.]+)(?:\s+([-0-9.]+))?\)", block)
        if not at:
            raise ValueError(f"{ref}: footprint has no top-level at")
        before = {
            "position_mm": [float(at.group(1)), float(at.group(2))],
            "rotation_deg": float(at.group(3) or 0),
        }
        rot = before["rotation_deg"] if rotation is None else rotation
        new_block = block[: at.start()] + f"(at {x:g} {y:g} {rot:g})" + block[at.end():]
        board.write_text(text[:start] + new_block + text[end:], encoding="utf-8")
        return {
            "board": str(board),
            "changed": True,
            "ref": ref,
            "before": before,
            "after": {"position_mm": [x, y], "rotation_deg": rot},
        }
    raise ValueError(f"unknown footprint ref: {ref}")


def annotate_ref(board: Path, ref: str, note: str = "Review this placement") -> dict[str, object]:
    board = Path(board)
    refs = {item["ref"]: item for item in list_refs(board)["footprints"]}
    if ref not in refs or refs[ref]["position_mm"] is None:
        raise ValueError(f"unknown footprint ref: {ref}")
    x, y = refs[ref]["position_mm"]
    clean_note = re.sub(r"\s+", " ", note).strip()[:64] or "Review this placement"
    marker = f"ASTRA: {ref} - {clean_note}"
    annotation = f'''
  (gr_circle (center {x:g} {y:g}) (end {x + 5:g} {y:g}) (stroke (width 0.35) (type solid) (color 255 170 0 1)) (fill none) (layer "F.SilkS") (uuid "{uuid.uuid4()}"))
  (gr_text "{marker}" (at {x:g} {y - 6:g} 0) (layer "F.SilkS") (uuid "{uuid.uuid4()}")
    (effects (font (size 1 1) (thickness 0.16)) (justify left bottom))
  )
'''
    text = board.read_text(encoding="utf-8")
    insert_at = text.rfind("\n)")
    if insert_at == -1:
        raise ValueError("could not find board close")
    board.write_text(text[:insert_at] + annotation + text[insert_at:], encoding="utf-8")
    return {
        "board": str(board),
        "changed": True,
        "ref": ref,
        "note": marker,
        "position_mm": [x, y],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="MissionPCB KiCad widget bridge")
    parser.add_argument("--board", type=Path, default=DEFAULT_BOARD)
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    move = sub.add_parser("move")
    move.add_argument("ref")
    move.add_argument("--x", type=float, required=True)
    move.add_argument("--y", type=float, required=True)
    move.add_argument("--rotation", type=float)
    annotate = sub.add_parser("annotate")
    annotate.add_argument("ref")
    annotate.add_argument("--note", default="Review this placement")
    args = parser.parse_args()

    if args.cmd == "list":
        print(json.dumps(list_refs(args.board), indent=2))
    elif args.cmd == "move":
        print(json.dumps(move_ref(args.board, args.ref, args.x, args.y, args.rotation), indent=2))
    elif args.cmd == "annotate":
        print(json.dumps(annotate_ref(args.board, args.ref, args.note), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
