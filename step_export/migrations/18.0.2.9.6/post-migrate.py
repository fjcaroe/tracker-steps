"""Link unique customs port references; preserve IDs, amounts and historical text."""
from collections import defaultdict
from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    names, codes = defaultdict(list), defaultdict(list)
    for port in env['l10n_cl.customs_port'].search([]):
        names[port.name.strip().casefold()].append(port.id)
        codes[str(port.code)].append(port.id)
    for shipment in env['step.export.export'].search([]):
        for old, relation in [('origin_port', 'origin_port_id'), ('destination_port', 'destination_port_id')]:
            text = (shipment[old] or '').strip()
            if not text or shipment[relation]:
                continue
            matches = codes.get(str(int(text)), []) if text.isascii() and text.isdigit() else names.get(text.casefold(), [])
            if len(matches) == 1:
                cr.execute('UPDATE step_export_export SET %s=%%s WHERE id=%%s' % relation, [matches[0], shipment.id])
    env.invalidate_all()
