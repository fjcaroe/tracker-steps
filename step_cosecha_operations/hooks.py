"""Retire only the obsolete embedded employee form, preserving other layouts."""
import logging
from lxml import etree

_logger = logging.getLogger(__name__)


def migrate_contractor_form(env):
    views = env['ir.ui.view'].with_context(active_test=False).search([
        ('model', '=', 'step.cosecha.registry'),
        ('inherit_id', '!=', False),
    ])
    for view in views:
        root = etree.fromstring(view.arch_db)
        changed = False
        for form in root.xpath(".//field[@name='employee_id_domain']/form"):
            # This copied employee form references fields removed from payroll.
            # Use the current employee view instead of retaining a stale snapshot.
            missing = [f.get('name') for f in form.xpath('.//field')
                       if f.get('name') in ('firstname', 'middle_name', 'last_name',
                                            'mothers_name', 'type_id', 'genero')
                       and f.get('name') not in env['hr.employee']._fields]
            if missing:
                parent = form.getparent()
                parent.remove(form)
                parent.set('widget', 'many2many_tags')
                parent.set('readonly', '1')
                changed = True
        if changed:
            view.write({'arch_db': etree.tostring(root, encoding='unicode')})
            _logger.info('T102 retired obsolete employee subform from view %s', view.id)
