"""Release check: download into a separate empty cache and build pinned images."""
import argparse
import json
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from controller.appliance import Appliance, digest
from controller.config import DEFAULTS
from controller.isolation import Artifacts, IsolatedAgent
from controller.storage import Store, atomic_json, now


def main(args):
    output = (ROOT / args.output).resolve()
    if not output.is_relative_to((ROOT / '.data').resolve()):
        raise ValueError('Keep release-check output inside the project .data directory')
    output.mkdir(parents=True, exist_ok=False)  # Never erase or reuse the app cache.
    appliance = Appliance(ROOT)
    appliance.directory, appliance.cache = output / 'isolation', output / 'downloads'
    report = {'started': now(), 'status': 'running', 'empty_cache': True, 'boot_requested': args.boot,
              'lock_sha256': digest(ROOT / 'controller/runtime-lock.json')}
    atomic_json(output / 'report.json', report)
    try:
        appliance.install()
        record = json.loads(appliance.record_path.read_text(encoding='utf-8'))
        assert all(digest(appliance.directory / name) == expected for name, expected in record['files'].items())
        lock = json.loads((ROOT / 'controller/runtime-lock.json').read_text(encoding='utf-8'))
        report['downloads'] = {item['name']: digest(appliance.cache / item['name']) for item in lock['sources']
                               if not appliance.linux or not item['name'].endswith('.exe')}
        report['build_passed'] = True
        if args.boot:
            appliance.verify()
            store = Store(output / 'sessions')
            settings = SimpleNamespace(values={**DEFAULTS, 'configured': True, 'provider': 'demo'}, key=lambda: '')
            class Client:
                calls = 0
                def complete(self, *args):
                    self.calls += 1
                    value = ({'action': {'tool': 'write_file', 'arguments': {'path': 'cold-start.txt', 'content': 'verified\n'}}}
                             if self.calls == 1 else {'status': 'completed'})
                    return {'content': json.dumps(value)}
            agent = IsolatedAgent(ROOT, store, settings, lambda _: Client())
            agent.appliance = appliance
            session = store.create('Verify the empty-cache installation.', 'demo', 'release fixture')
            try:
                agent.start(session)
                worker = agent.workers[session['id']][1]
                worker.join(timeout=120)
                if worker.is_alive():
                    agent.stop(session['id']); worker.join(timeout=10)
                report['boot_passed'] = (not worker.is_alive() and session['status'] == 'completed' and
                                        Artifacts(store, session).read('cold-start.txt') == b'verified\n')
                if not report['boot_passed']:
                    raise RuntimeError('The freshly installed VM did not complete its fixture task')
            finally:
                agent.close()
        report.update(status='completed', passed=True, finished=now())
    except BaseException as error:
        report.update(status='failed', passed=False, error=type(error).__name__ + ': ' + str(error))
        raise
    finally:
        atomic_json(output / 'report.json', report)
    print(json.dumps({'passed': report['passed'], 'build_passed': True, 'boot_passed': report.get('boot_passed')}))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--boot', action='store_true', help='Also run an isolated VM; requires KVM or WHPX')
    main(parser.parse_args())
