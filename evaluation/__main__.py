"""Read input labels/predictions and print derived metrics; never updates inputs."""
import argparse
import json
from pathlib import Path
from .metrics import evaluate

parser = argparse.ArgumentParser()
parser.add_argument('--gold', type=Path, required=True)
parser.add_argument('--predictions', type=Path, required=True)
args = parser.parse_args()
result = evaluate(json.loads(args.gold.read_text(encoding='utf-8')), json.loads(args.predictions.read_text(encoding='utf-8')))
print(json.dumps(result, ensure_ascii=False, indent=2))
