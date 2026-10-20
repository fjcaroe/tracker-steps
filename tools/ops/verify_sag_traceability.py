"""Run both approved functional flows in the same registry, rolling back fixtures."""
from pathlib import Path

for filename in ('verify_sag_lot.py', 'verify_traceability.py'):
    exec(compile((Path(PROBE_TOOLS) / filename).read_text(), filename, 'exec'))
