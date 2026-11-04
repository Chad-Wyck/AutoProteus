"""Run the curated W&T synthetic CPU controls; never boot a VM or load a model."""
import importlib.util
import json
import os
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.chdir(ROOT)
os.environ.update(CUDA_VISIBLE_DEVICES='', HF_HUB_OFFLINE='1',
                  TRANSFORMERS_OFFLINE='1', HF_HUB_DISABLE_TELEMETRY='1',
                  PYTHONDONTWRITEBYTECODE='1')
sys.dont_write_bytecode = True
for package in ('numpy', 'safetensors', 'yaml'):
    if importlib.util.find_spec(package) is None:
        raise SystemExit('Install docs/weights-and-training/requirements-cpu.txt first: missing '+package)

manifest=json.loads((ROOT/'docs/weights-and-training/SOURCE-MANIFEST.json').read_text(encoding='utf-8'))
names=[Path(row['path']).name for row in manifest['files'] if row['path'].startswith('tests/')]
(ROOT/'.data/test-tensor-workspace').mkdir(parents=True,exist_ok=True)
loader=unittest.TestLoader()
suite=unittest.TestSuite()
for name in sorted(names):
    suite.addTests(loader.discover(str(ROOT/'tests'),pattern=name))
result=unittest.TextTestRunner(verbosity=1).run(suite)
print(json.dumps({'scope':'synthetic CPU controls; no live model/VM work',
                  'tests':result.testsRun,'failures':len(result.failures),
                  'errors':len(result.errors),'skipped':len(result.skipped)},indent=2))
raise SystemExit(0 if result.wasSuccessful() else 1)
