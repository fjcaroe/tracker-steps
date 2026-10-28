"""Retire only the obsolete company Previred layout, keeping its original ID/arch."""
from lxml import etree

LEGACY = {'x_studio_caja_compensacin','x_studio_tiene_mutualidad',
          'x_studio_mutualidad','x_studio_factor_mutualidad','x_studio_isl'}
NATIVE = {'caja_compensacion','has_mutual','mutual','rate_base','rate_additional'}


def pre_init_hook(env):
    cr=env.cr
    cr.execute("SELECT name FROM ir_model_fields WHERE model='res.company'")
    fields={row[0] for row in cr.fetchall()}
    cr.execute("SELECT id,arch_db FROM ir_ui_view WHERE model='res.company' AND active AND name LIKE 'Odoo Studio:%'")
    for ident,translations in cr.fetchall():
        names=set()
        for arch in translations.values():
            tree=etree.fromstring(arch)
            names.update(node.get('name') for node in tree.xpath('.//field'))
        if not (names & LEGACY) or (names & LEGACY) <= fields:
            continue
        assert names <= LEGACY, 'Mixed obsolete company layout requires a dedicated migration'
        assert NATIVE <= fields, 'Native payroll company controls must exist before retiring the obsolete layout'
        # Do not recreate the removed Studio columns or infer contribution rates.
        # The existing Institutions page owns the current native parameters.
        cr.execute("SELECT module,name FROM ir_model_data WHERE model='ir.ui.view' AND res_id=%s AND module='studio_customization'",(ident,))
        for module,name in cr.fetchall():
            cr.execute("UPDATE ir_model_data SET module='step_company_form_restore',name=%s,noupdate=TRUE WHERE module=%s AND name=%s",
                       ('legacy_company_layout_'+str(ident)+'_'+name,module,name))
        cr.execute('UPDATE ir_ui_view SET active=FALSE WHERE id=%s',(ident,))
        print('COMPANY_OBSOLETE_LAYOUT_ARCHIVED id='+str(ident))
    env.invalidate_all()
