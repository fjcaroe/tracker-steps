from odoo.exceptions import ValidationError
from lxml import etree


MODULE = 'step_cerro_product_account_views'
VIEWS = (
    ('expense_category_accounts', 'odoo_studio_product__4e8cc471-cfb4-4b1c-86a3-1974a90d73f8',
     'product.product', 'hr_expense.product_product_expense_categories_tree_view', 160,
     "//field[@name='description']", ('property_account_expense_id', 'categ_id')),
    ('product_template_accounts', 'odoo_studio_product__7a71a49a-898b-40ea-999d-36cc8dd289b3',
     'product.template', 'account.product_template_view_tree', 99,
     "//list[1]/field[@name='name']", ('categ_id', 'property_account_expense_id')),
)


def adopt_views(env):
    aliases = []
    for name, legacy, model, parent, priority, anchor, fields in VIEWS:
        original = env.ref('studio_customization.' + legacy, raise_if_not_found=False)
        owned = env.ref(MODULE + '.' + name, raise_if_not_found=False)
        if owned and owned != original:
            raise ValidationError('El identificador de la vista ya est\u00e1 ocupado.')
        if not original:
            continue
        if (original._name != 'ir.ui.view' or original.model != model or original.inherit_id != env.ref(parent)
                or original.type != 'list' or original.mode != 'extension' or not original.active
                or original.priority != priority or original.groups_id):
            raise ValidationError('La vista original del cat\u00e1logo de Cerro cambi\u00f3.')
        # Avoid replacing edits made after the source inventory.
        tree = etree.fromstring(original.with_context(lang='en_US').arch_db.encode())
        children = list(tree)
        if tree.tag != 'data' or len(children) != 1 or children[0].tag != 'xpath':
            raise ValidationError('La arquitectura de la vista original cambi\u00f3.')
        xpath = children[0]
        if (dict(xpath.attrib) != {'expr': anchor, 'position': 'after'} or
                [(node.tag, dict(node.attrib), len(node)) for node in xpath] !=
                [('field', {'name': field, 'optional': 'show'}, 0) for field in fields]):
            raise ValidationError('Las columnas de la vista original de Cerro cambi\u00f3.')
        aliases.append({'xml_id': MODULE + '.' + name, 'record': original, 'noupdate': False})
    if aliases:
        if len(aliases) != len(VIEWS):
            raise ValidationError('El conjunto de vistas originales de Cerro est\u00e1 incompleto.')
        env['ir.model.data']._update_xmlids(aliases)
