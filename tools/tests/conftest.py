import sys
from pathlib import Path

# Núcleos puros de los addons (sin Odoo): se importan directamente porque el __init__ de cada addon necesita Odoo.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'step_mobile_portal' / 'lib'))
