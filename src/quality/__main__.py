"""Read-only aggregate report on configured frozen JD data; stdout only, no data writes."""
import json
from src.data_loader import DataLoader
from .loader import load_quality_records
from .science import quality_report

value = quality_report(load_quality_records(DataLoader()))
# Do not copy raw records or business text into derived CLI reports.
value.pop('records', None)
value['time_quality'].pop('records', None)
print(json.dumps(value, ensure_ascii=False, indent=2))
