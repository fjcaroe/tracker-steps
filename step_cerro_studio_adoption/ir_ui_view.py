"""Keep the previous architecture of adopted Studio views when XML reloads identical data."""
from lxml import etree

from odoo import models

from .ownership import structure


class CerroView(models.Model):
    _inherit = 'ir.ui.view'

    def _load_records_write(self, values):
        owner = self.env.context.get('install_module', '')
        xmlid = self.env.context.get('install_xmlid', '')
        if (owner.startswith('step_cerro_') and xmlid and self.type in ('list', 'form')
                and values.keys() == {'name','model','priority','inherit_id','arch'}):
            name = xmlid.partition('.')[2] if xmlid.startswith(owner + '.') else xmlid
            data = self.env['ir.model.data']
            owned = self.env.ref(owner + '.' + name, raise_if_not_found=False)
            if (owned == self and data.search_count([('module','=','studio_customization'),('model','=','ir.ui.view'),
                                                     ('res_id','=',self.id)], limit=1)
                    and self.name == values['name'] and self.model == values['model']
                    and self.priority == int(values['priority']) and self.inherit_id.id == values['inherit_id']):
                parser = etree.XMLParser(resolve_entities=False)
                original = etree.fromstring(self.with_context(lang='en_US').arch_db.encode(), parser)
                proposed = etree.fromstring(values['arch'].encode(), parser)
                if (structure(original) == structure(proposed)
                        and not any((node.tail or '').strip() for tree in (original,proposed) for node in tree.iter())):
                    return
        return super()._load_records_write(values)
