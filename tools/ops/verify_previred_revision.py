"""Verify both corrections in the same native payroll registry and download."""
from pathlib import Path
from lxml import etree

assert hasattr(env['step.previred.extractor'], '_allow_open_ended_movements')
arch = etree.fromstring(env['hr.payslip'].get_view(view_type='form')['arch'].encode())
assert arch.xpath("//field[@name='previred_movement_ids']")
assert not env['hr.previred.movement']._fields['date_to'].required
exec((Path(PROBE_TOOLS) / 'verify_previred_contributions.py').read_text())
