#!/usr/bin/env python3
"""Validate every parts/catalog/*.json against parts/schema/part.schema.json.

Also reports extraction coverage so we can see how much of the form is filled
and how much is still unverified. Run: python3 parts/validate.py
"""
import json, pathlib, sys

ROOT = pathlib.Path(__file__).resolve().parent
schema = json.loads((ROOT / "schema" / "part.schema.json").read_text())
files = sorted((ROOT / "catalog").glob("*.json"))

try:
    from jsonschema import Draft202012Validator
    validator = Draft202012Validator(schema)
except ImportError:
    validator = None
    print("! jsonschema not installed (pip install jsonschema) -- structural checks only\n")

def walk(node, hits):
    """Count leaf measurements/models by review_status."""
    if isinstance(node, dict):
        if "review_status" in node and ("value" in node or "expression" in node):
            hits[node["review_status"]] = hits.get(node["review_status"], 0) + 1
        for v in node.values():
            walk(v, hits)
    elif isinstance(node, list):
        for v in node:
            walk(v, hits)

fail = 0
print(f"{'part':<18} {'role':<16} {'verified':>8} {'extracted':>10} {'assumed':>8}  status")
print("-" * 78)
for f in files:
    part = json.loads(f.read_text())
    errs = sorted(validator.iter_errors(part), key=lambda e: e.path) if validator else []
    hits = {}
    walk(part, hits)
    status = "OK" if not errs else f"{len(errs)} SCHEMA ERROR(S)"
    if errs:
        fail += 1
    print(f"{part.get('id',f.stem):<18} {part.get('role',''):<16} "
          f"{hits.get('human_verified',0):>8} {hits.get('extracted',0):>10} "
          f"{hits.get('assumed',0):>8}  {status}")
    for e in errs[:3]:
        print(f"    -> {'/'.join(map(str, e.path)) or '(root)'}: {e.message[:90]}")

print("-" * 78)
print(f"{len(files)} part(s), {fail} with schema errors")
sys.exit(1 if fail else 0)
