"""Fixed read-only query catalog. No SQL, domains or model names from the caller.

Business data never enters a provider prompt. ORM ACLs, record rules and field
permissions apply, even when the caller has multiple allowed companies.
"""
import datetime
import re
import unicodedata

from odoo import api, fields, models, _
from odoo.exceptions import AccessError, ValidationError


# key: label, model, date field, explicit safe output fields, fixed domain
CATALOG = {
    "asientos": ("Asientos", "account.move", "date", ("name", "date", "state", "ref"), (("move_type", "=", "entry"),)),
    "facturas": ("Facturas", "account.move", "invoice_date", ("name", "invoice_date", "state", "payment_state", "amount_total", "amount_residual", "currency_id"), (("move_type", "in", ["out_invoice", "out_refund", "in_invoice", "in_refund"]),)),
    "pagos": ("Pagos", "account.payment", "date", ("name", "date", "state", "payment_type", "amount", "currency_id"), ()),
    "ventas": ("Ventas", "sale.order", "date_order", ("name", "date_order", "state", "amount_total", "currency_id"), ()),
    "compras": ("Compras", "purchase.order", "date_order", ("name", "date_order", "state", "amount_total", "currency_id"), ()),
    "inventario": ("Transferencias de inventario", "stock.picking", "scheduled_date", ("name", "scheduled_date", "state", "origin"), ()),
    "fabricacion": ("Órdenes de fabricación", "mrp.production", "date_start", ("name", "date_start", "state", "product_qty"), ()),
    "tareas": ("Tareas de proyectos", "project.task", "create_date", ("name", "stage_id", "date_deadline"), ()),
    "colaciones": ("Registros de colaciones", "step.colacion.registration", "meal_date", ("name", "meal_date", "state", "company_currency_amount"), ()),
    "tesoreria": ("Flujos de tesorería", "step.cashflow", "start_date", ("name", "start_date", "end_date", "state"), ()),
    "proformas": ("Proformas de proveedores", "step.vendor.proforma", "date", ("name", "date", "date_due", "state", "amount_total", "currency_id"), ()),
}


def normalize(value):
    return ''.join(c for c in unicodedata.normalize('NFD', value.lower()) if unicodedata.category(c) != 'Mn')


class BusinessAssistant(models.AbstractModel):
    _inherit = "step.support.assistant"

    def _business_model(self, name, output_fields=()):
        if name not in self.env.registry.models:
            raise AccessError(_("Esta aplicación no está disponible en el ambiente."))
        # Explicitly drop superuser mode, including for administrator sessions.
        model = self.env[name].sudo(False).with_context(allowed_company_ids=[self.env.company.id], active_test=True)
        if 'company_id' not in model._fields or any(field not in model._fields for field in output_fields) or not model.has_access('read'):
            raise AccessError(_("No tienes acceso de lectura a esta aplicación."))
        model.check_field_access_rights('read', list(output_fields) + ['company_id'])
        return model

    @api.model
    def get_business_catalog(self):
        self._check_user()
        available = []
        for key, (label, name, date_field, outputs, _) in CATALOG.items():
            try:
                model = self._business_model(name, outputs)
                if all(field in model._fields for field in outputs + (date_field,)):
                    available.append({'key': key, 'label': label})
            except AccessError:
                continue
        try:
            self._business_model('account.move.line', ('date', 'account_id', 'debit', 'credit', 'balance', 'parent_state'))
            available.insert(0, {'key': 'saldos', 'label': 'Saldo de una cuenta contable'})
        except AccessError:
            pass
        return available

    def _business_dates(self, start, end):
        for value in (start, end):
            if value and (not isinstance(value, str) or not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value)):
                raise ValidationError(_("Usa fechas con formato AAAA-MM-DD."))
        try:
            start, end = (fields.Date.to_date(value) if value else None for value in (start, end))
        except (ValueError, TypeError):
            raise ValidationError(_("La fecha no es válida."))
        if start and end and start > end:
            raise ValidationError(_("La fecha inicial debe ser anterior a la final."))
        return start, end

    def _business_envelope(self, answer, columns=(), rows=()):
        return {'status': 'answered', 'answer': answer, 'sources': [], 'columns': list(columns), 'records': list(rows)}

    @api.model
    def query_business(self, app, reference='', date_from='', date_to=''):
        self._check_user()
        if not isinstance(app, str) or app not in {*CATALOG, 'saldos'}:
            raise ValidationError(_("Selecciona una consulta disponible."))
        if not isinstance(reference, str) or len(reference) > 100:
            raise ValidationError(_("La referencia debe tener como máximo 100 caracteres."))
        reference = reference.strip()
        start, end = self._business_dates(date_from, date_to)
        if app == 'saldos':
            return self._account_balance(reference, start, end)
        label, name, date_field, output_fields, fixed_domain = CATALOG[app]
        model = self._business_model(name, output_fields + (date_field, 'name'))
        domain = [('company_id', '=', self.env.company.id)] + list(fixed_domain)
        if reference:
            # Literal substring, never a caller-authored domain/expression.
            domain.append(('name', 'ilike', reference.replace('%', '\\%').replace('_', '\\_')))
        if start:
            domain.append((date_field, '>=', fields.Datetime.to_datetime(start) if model._fields[date_field].type == 'datetime' else start))
        if end:
            if model._fields[date_field].type == 'datetime':
                domain.append((date_field, '<', fields.Datetime.to_datetime(end + datetime.timedelta(days=1))))
            else:
                domain.append((date_field, '<=', end))
        # Bounded rows; no unrestricted search_count, exports or implicit totals.
        records = model.search(domain, order=f'{date_field} desc, id desc', limit=21)
        labels = model.fields_get(list(output_fields), attributes=['string', 'selection'])
        columns = [labels[field]['string'] for field in output_fields]
        rows = []
        for values in records[:20].read(list(output_fields)):
            cells = []
            for field in output_fields:
                value = values[field]
                if isinstance(value, (tuple, list)):
                    # Check related model ACL/rules before exposing a display name.
                    related = model._fields[field].comodel_name
                    target = self.env[related].sudo(False).browse(value[0])
                    if not target.has_access('read'):
                        value = 'Restringido'
                    else:
                        value = target.display_name
                elif model._fields[field].type == 'selection':
                    value = dict(labels[field].get('selection', [])).get(value, value)
                elif value is False or value is None:
                    value = ''
                cells.append(str(value)[:240])
            rows.append({'id': values['id'], 'model': name, 'cells': cells})
        period = f"{start or 'sin inicio'} a {end or 'sin término'}"
        answer = f"{label} · compañía {self.env.company.display_name}. {period}. "
        answer += 'Hay más resultados; se muestran los 20 más recientes. Acota las fechas o la referencia.' if len(records) > 20 else f'{len(rows)} registros visibles con tus permisos.'
        if app == 'colaciones':
            answer += f' Los importes se expresan en {self.env.company.currency_id.name}.'
        answer += ' Consulta de solo lectura; abre un registro para revisar el detalle. No es un total del negocio.'
        return self._business_envelope(answer, columns, rows)

    def _account_balance(self, reference, start, end):
        if not reference:
            return self._business_envelope('Indica el código exacto de la cuenta contable. Ejemplo: saldo cuenta 110101 hasta 2026-09-30. Sin fecha inicial, el saldo es acumulado hasta la fecha final; con fecha inicial, muestra el movimiento neto del período.')
        lines = self._business_model('account.move.line', ('date', 'account_id', 'debit', 'credit', 'balance', 'parent_state'))
        accounts = self.env['account.account'].sudo(False).with_context(allowed_company_ids=[self.env.company.id])
        accounts.check_access('read')
        accounts.check_field_access_rights('read', ['code', 'name', 'company_ids'])
        account = accounts.search([('code', '=', reference), ('company_ids', 'in', [self.env.company.id])], limit=2)
        if len(account) != 1:
            return self._business_envelope('No encuentro una cuenta única y visible con ese código en tu compañía. Revisa el código exacto de la cuenta en Contabilidad.')
        end = end or fields.Date.context_today(lines)
        domain = [('company_id', '=', self.env.company.id), ('account_id', '=', account.id), ('parent_state', '=', 'posted'), ('date', '<=', end)]
        if start:
            domain.append(('date', '>=', start))
        groups = lines.read_group(domain, ['debit:sum', 'credit:sum', 'balance:sum'], [])
        totals = groups[0] if groups else {}
        currency = self.env.company.currency_id
        fmt = lambda value: f'{currency.round(value or 0):,.{currency.decimal_places}f} {currency.name}'
        kind = 'Movimiento neto del período' if start else 'Saldo acumulado'
        answer = (f'{kind} · {account.code} {account.name} · compañía {self.env.company.display_name}. '
                  f'Desde {start or "el inicio de los registros"} hasta {end}. Solo asientos publicados visibles con tus permisos. '
                  f'Debe: {fmt(totals.get("debit"))}. Haber: {fmt(totals.get("credit"))}. '
                  f'Saldo (Debe − Haber): {fmt(totals.get("balance"))}. '
                  'Los borradores quedan excluidos. Un permiso parcial puede mostrar solo una parte del libro contable.')
        return self._business_envelope(answer, ['Cuenta', 'Debe', 'Haber', 'Saldo'], [
            {'id': account.id, 'model': 'account.account', 'cells': [account.code, fmt(totals.get('debit')), fmt(totals.get('credit')), fmt(totals.get('balance'))]}])

    def _business_question(self, question):
        """Conservative local routing; unsupported filters require clarification."""
        text = normalize(question)
        if re.search(r'\b(como|procedimiento|configurar|que es)\b', text):
            return None
        app = next((key for key in ['saldos', *CATALOG] if re.search(r'\b' + (r'saldos?' if key == 'saldos' else key + '?') + r'\b', text)), None)
        if not app:
            return None
        if re.search(r'\b(crea|crear|borra|borrar|elimina|eliminar|modifica|modificar|publica|publicar|valida|validar|confirma|confirmar)\b', text):
            return self._business_envelope('Puedo consultar registros. Para modificar o validar una operación, abre la aplicación y utiliza sus controles habituales.')
        # Never silently ignore filters the local parser cannot enforce.
        stripped = re.sub(r'\d{4}-\d{2}-\d{2}', '', text)
        stripped = re.sub(r'\bcuenta\s+[\w.-]+', '', stripped)
        stripped = re.sub(r'\breferencia\s+[\w/.-]+', '', stripped)
        if re.search(r'\b(pendiente\w*|pagad\w*|vencid\w*|borrador\w*|publicad\w*|cliente|proveedor|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|hoy|ayer|mes|semana|ano)\b', stripped):
            return self._business_envelope('Para aplicar filtros precisos utiliza «Consultar datos» y las fechas AAAA-MM-DD. Esta versión filtra por referencia y fechas; los estados se muestran en los resultados. Para filtros por cliente, proveedor o estado, abre la aplicación.')
        dates = re.findall(r'\d{4}-\d{2}-\d{2}', question)
        if len(dates) > 2:
            return self._business_envelope('Usa una fecha final o un rango de dos fechas AAAA-MM-DD.')
        ref = re.search(r'\b' + ('cuenta' if app == 'saldos' else 'referencia') + r'\s+([\w/.-]+)', question, re.I)
        remaining = re.sub(r'\b(?:saldos?|cuenta|asientos?|facturas?|pagos?|ventas?|compras?|inventario|fabricacion|tareas?|colaciones?|tesoreria|proformas?|muestra|mostrar|ver|consulta|consultar|listar|lista|busca|buscar|ultimos|ultimas|reales|contables|generales|estado|estados|hasta|desde|entre|al|de|del|el|la|los|las|un|una|y|por|favor)\b', '', stripped)
        if re.sub(r'[\s¿?.,:;!¡-]', '', remaining):
            return self._business_envelope('Para consultar datos con filtros precisos, utiliza «Consultar datos reales»: selecciona la aplicación, referencia y fechas. También puedes escribir «últimos asientos» o «saldo cuenta 110101 hasta 2026-09-30».')
        start = dates[0] if len(dates) == 2 or (len(dates) == 1 and 'desde' in text) else ''
        end = dates[-1] if dates and not (len(dates) == 1 and 'desde' in text) else ''
        try:
            return self.query_business(app, ref.group(1) if ref else '', start, end)
        except AccessError:
            return self._business_envelope('Esta aplicación no está disponible con tus permisos en la compañía actual. Puedes solicitar una revisión de acceso a tu administrador.')
