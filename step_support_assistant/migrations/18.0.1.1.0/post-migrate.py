from odoo import api, SUPERUSER_ID


def migrate(cr, version):
    env = api.Environment(cr, SUPERUSER_ID, {})
    replacements = {
        'help_assistant_scope': ('El asistente no modifica registros ni confirma saldos, estados o datos de documentos de negocio.',
            'El asistente no modifica registros. El botón Consultar datos reales muestra registros y saldos con tus permisos en la compañía actual; consulta la guía Consultar datos reales: alcance y filtros.'),
        'help_colaciones_duplicate': ('El asistente no comprueba registros concretos ni elimina duplicados.',
            'Puedes consultar registros visibles desde Consultar datos reales. El asistente no elimina duplicados.'),
    }
    for xmlid, (old, new) in replacements.items():
        article = env.ref('step_support_assistant.' + xmlid, raise_if_not_found=False)
        if article and old in article.content:
            article.content = article.content.replace(old, new)
