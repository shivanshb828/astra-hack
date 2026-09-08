"""Convert cached KiCad STEP candidates sequentially; no board integration."""
from pathlib import Path
import hashlib
import json
import subprocess
import time

ROOT = Path(__file__).resolve().parent
CLI = Path('/Applications/KiCad/KiCad.app/Contents/MacOS/kicad-cli')
OUT = ROOT / 'converted_models'


def main():
    OUT.mkdir(exist_ok=True)
    inventory = json.loads((ROOT / 'model_candidates.json').read_text())
    models = {}
    for part in inventory['parts']:
        for candidate in part['candidates']:
            for model in candidate['models']:
                if model['cached_path']:
                    models[model['cached_path']] = model
    results = []
    for i, (rel, model) in enumerate(sorted(models.items()), 1):
        source = ROOT / rel
        assert hashlib.sha256(source.read_bytes()).hexdigest() == model['sha256']
        stem = source.stem
        board = OUT / (stem + '.kicad_pcb')
        glb = OUT / (stem + '.glb')
        old_manifest = OUT / 'conversion_manifest.json'
        previous = json.loads(old_manifest.read_text())['models'] if old_manifest.exists() else []
        cached = next((r for r in previous if r['source_sha256'] == model['sha256']), None)
        if cached and glb.exists() and hashlib.sha256(glb.read_bytes()).hexdigest() == cached['raw_glb_sha256']:
            cached['source_metadata'] = model
            results.append(cached)
            print(f'{i}/{len(models)} {stem}: reused verified conversion', flush=True)
            continue
        board.write_text(f'''(kicad_pcb (version 20240108) (generator "pcbnew")
(general (thickness 1.6)) (paper "A4")
(layers (0 "F.Cu" signal) (31 "B.Cu" signal) (37 "F.SilkS" user "f.silkscreen") (44 "Edge.Cuts" user))
(setup (pad_to_mask_clearance 0))
(footprint "Candidate" (layer "F.Cu") (at 10 10) (attr smd)
 (property "Reference" "U1" (at 0 -5) (layer "F.SilkS"))
 (model "{source.as_posix()}" (offset (xyz 0 0 0)) (scale (xyz 1 1 1)) (rotate (xyz 0 0 0))))
(gr_rect (start 0 0) (end 30 30) (stroke (width 0.05) (type default)) (fill none) (layer "Edge.Cuts")))
''')
        command = [str(CLI), 'pcb', 'export', 'glb', '--no-board-body', '--force', '-o', str(glb), str(board)]
        start = time.monotonic()
        run = subprocess.run(command, capture_output=True, text=True, check=True)
        (OUT / (stem + '.log')).write_text(run.stdout + run.stderr)
        assert glb.read_bytes()[:4] == b'glTF'
        results.append({'package_model': stem, 'source_step': rel,
                        'source_metadata': model,
                        'source_sha256': model['sha256'], 'raw_glb': str(glb.relative_to(ROOT)),
                        'raw_glb_sha256': hashlib.sha256(glb.read_bytes()).hexdigest(),
                        'bytes': glb.stat().st_size, 'conversion_seconds': round(time.monotonic() - start, 4)})
        print(f'{i}/{len(models)} {stem}: {glb.stat().st_size} bytes', flush=True)
    record = {'status': 'STEP_TO_GLB_PASS', 'kicad_version': subprocess.check_output([str(CLI), '--version'], text=True).strip(),
              'count': len(results), 'note': 'Raw GLBs retain KiCad placement offset; library builder converts metres to millimetres, recentres XY and sets bottom Z=0.',
              'models': results}
    (OUT / 'conversion_manifest.json').write_text(json.dumps(record, indent=2) + '\n')


if __name__ == '__main__':
    main()
