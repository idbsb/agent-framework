"""Local test harness: temporary DB, optionally synthetic evolution. No existing DB opens."""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from fixtures.p2_synthetic.synthetic_fixture import jd, evolution

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--synthetic-quality', action='store_true')
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix='runtime-', dir=ROOT/'tests/fixtures/p2_synthetic') as directory:
        os.environ['P1_CLOSURE_DB'] = str(Path(directory)/'synthetic_test.sqlite3')
        os.environ['P1_CLOSURE_WRITES'] = '1'
        from src.api.app import app
        from src.api.integration_service import get_system_data
        from src.integration.evolution_adapter import EvolutionAdapter
        if args.synthetic_quality:
            # Reuse the actual adapter and endpoint; only the source is synthetic/temporary.
            title = 'AI Agent开发工程师'  # Existing UI focus identifier, not an employer claim.
            payload = dict(meta={'config': {'min_jd_count': 3}}, jobs={title: evolution()})
            (Path(directory)/'key_job_evolution_v1.json').write_text(json.dumps(payload), encoding='utf-8')
            rows = [jd(i, standard_job_title=title, published_at=None) for i in range(1, 13)]
            system = get_system_data()
            system.evolution = EvolutionAdapter(Path(directory), records_provider=lambda: rows)
        import uvicorn
        print('SYNTHETIC/temporary database only:', directory, flush=True)
        uvicorn.run(app, host='127.0.0.1', port=8000)
