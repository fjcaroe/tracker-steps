"""Read-only capability counts from private captures; never print frames or IDs."""
import argparse
from collections import Counter
import json
import math
from pathlib import Path
import sqlite3

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('database', type=Path)
args = parser.parse_args()
counts = Counter()
with sqlite3.connect(args.database.resolve().as_uri() + '?mode=ro', uri=True) as db:
    for (frame,) in db.execute('SELECT frame FROM capture'):
        fields = bytes(frame).decode('ascii', errors='replace').strip(';*\r\n').split(',')
        counts['captured_frames'] += 1
        if len(fields) < 15 or fields[4] != 'F' or fields[6] != 'A':
            counts['other_formats_require_specification'] += 1
            continue
        counts['gps103_f_positions'] += 1
        for name, index in (('course', 12), ('altitude', 13)):
            try:
                present = bool(fields[index]) and math.isfinite(float(fields[index]))
            except ValueError:
                present = False
            counts[name + ('_present' if present else '_absent')] += 1
        counts['acc_present'] += fields[14] in ('0', '1')
print(json.dumps({'counts': counts, 'battery_percent': 'not_decoded_in_validated_position_format',
                  'scope': 'captured_sample_only_not_a_hardware_capability_guarantee'}))
