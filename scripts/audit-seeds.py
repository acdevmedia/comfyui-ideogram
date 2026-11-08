"""Check every packaged version/workflow for unresolved or fixed upstream seed defaults."""
from pathlib import Path
import copy
import json
from workflow_seeds import apply_seed_defaults

root = Path(__file__).resolve().parents[1]
workflows = drivers = 0
for path in sorted(root.glob('versions/*/workflows/*.json')):
    data = json.loads(path.read_text())
    before = copy.deepcopy(data)
    count, unresolved = apply_seed_defaults(data)
    assert not unresolved, (path.name, 'unresolved seed drivers', unresolved)
    assert data == before, (path.name, 'seed defaults were not packaged')
    assert count, (path.name, 'no seed driver found')
    workflows += 1
    drivers += count
print(f'PASS: {workflows} workflows, {drivers} resolved seed drivers; packaged defaults are randomize.')
