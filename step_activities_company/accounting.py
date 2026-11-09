from odoo import _, models
from odoo.exceptions import UserError
from odoo.osv import expression


ACCOUNTING_SCOPE = object()
SCOPE_KEY = '_step_tarja_accounting_scope'


def scoped_domain(env, domain, index):
    scope = env.context.get(SCOPE_KEY)
    if isinstance(scope, tuple) and scope and scope[0] is ACCOUNTING_SCOPE:
        return expression.AND([domain, [('id', 'in', scope[index])]])
    return domain


class StepSeason(models.Model):
    _inherit = 'step.temporada'

    def _search(self, domain, *args, **kwargs):
        return super()._search(scoped_domain(self.env, domain, 1), *args, **kwargs)


class StepCostProvision(models.Model):
    _inherit = 'step.haber.costeo'

    def _search(self, domain, *args, **kwargs):
        return super()._search(scoped_domain(self.env, domain, 2), *args, **kwargs)


class StepTarja(models.Model):
    _inherit = 'step.tarja'

    def _step_compatible_master(self, record, extra_domain):
        if not record:
            return False
        domain = expression.AND([
            [('id', '=', record.id)], record._check_company_domain(self.company_id), extra_domain,
        ])
        return bool(self.env[record._name].search_count(domain, limit=1))

    def _step_daily_accounting_scope(self):
        self.ensure_one()
        issues = []
        company = self.company_id
        company_scope = company | company.parent_ids
        own = self.tarja_type == 'propio'
        journal = company.propio_journal_id if own else company.step_journal_id
        journal_label = _('Diario Transitorio para Contabilización Propia') if own else _('Diario Contratista')
        if not self._step_compatible_master(journal, [('active', '=', True)]):
            issues.append(_(
                'En Ajustes → Labores y Tareas, configure un %(field)s activo para esta empresa.',
                field=journal_label,
            ))
        if self.invoice_id:
            issues.append(_('El registro ya tiene un asiento asociado. Revíselo antes de volver a contabilizar.'))
        lines = self.tarja_line if own else self.tarja_cost_line
        if not lines:
            issues.append(_('Agregue al menos una línea de labores al registro.'))

        season = self.env['step.temporada']
        if self.date:
            seasons = season.search([
                ('company_id', 'in', company_scope.ids),
                ('start_date', '<=', self.date), ('end_date', '>=', self.date),
            ])
            season = seasons.filtered(lambda item: item.company_id == company) or seasons
            if len(season) != 1:
                issues.append(_(
                    'En Maestros → Temporadas, configure una sola temporada que cubra el %(date)s para esta empresa.',
                    date=self.date.strftime('%d/%m/%Y'),
                ))
            elif not self._step_compatible_master(season.cost_id, [('active', '=', True)]):
                issues.append(_(
                    'Asigne una cuenta analítica activa y compatible a la temporada %(season)s.',
                    season=season.display_name,
                ))
        else:
            issues.append(_('Indique la fecha del registro para determinar la temporada.'))

        provisions = self.env['step.haber.costeo']
        if own:
            configured = provisions.search([('company_id', 'in', company_scope.ids), ('active', '=', True)])
            concepts = dict(provisions._fields['type']._description_selection(self.env))
            for code, label in concepts.items():
                candidates = configured.filtered(lambda rule: rule.type == code)
                chosen = candidates.filtered(lambda rule: rule.company_id == company) or candidates
                if len(chosen) != 1:
                    issues.append(_(
                        'En Maestros → Haberes de costeo, configure un solo registro activo para %(concept)s.',
                        concept=label,
                    ))
                    continue
                provisions |= chosen
                for field, field_label in (('debe_account_id', _('Cuenta Debe')), ('haber_account_id', _('Cuenta Haber'))):
                    if not self._step_compatible_master(chosen[field], [('deprecated', '=', False)]):
                        issues.append(_(
                            'Configure %(field)s en el haber de costeo %(concept)s con una cuenta contable vigente de la empresa.',
                            field=field_label, concept=label,
                        ))
        elif journal and self._step_compatible_master(journal, [('active', '=', True)]):
            for account, label in ((journal.default_account_id, _('Cuenta por defecto')),
                                   (journal.account_control_ids[:1], _('Cuentas permitidas'))):
                if not self._step_compatible_master(account, [('deprecated', '=', False)]):
                    issues.append(_(
                        'Configure %(field)s con una cuenta contable vigente en el Diario Contratista.',
                        field=label,
                    ))

        for number, line in enumerate(lines, 1):
            if not self._step_compatible_master(line.cost_id, [('active', '=', True)]):
                issues.append(_('Seleccione un Centro de costos activo de la empresa en la línea %(line)s.', line=number))
            if not self._step_compatible_master(line.labor_id.actividad_id, [('active', '=', True)]):
                issues.append(_(
                    'En Maestros → Labores, revise la cuenta analítica Actividad de %(labor)s (línea %(line)s).',
                    labor=line.labor_id.display_name or _('la labor sin seleccionar'), line=number,
                ))
        if issues:
            raise UserError(_(
                'No se puede contabilizar %(task)s en %(company)s.\n\n%(issues)s',
                task=self.display_name, company=company.display_name,
                issues='\n'.join('• ' + issue for issue in issues),
            ))
        return ACCOUNTING_SCOPE, tuple(season.ids), tuple(provisions.ids)

    def action_conta(self):
        self.check_access('write')
        tasks = self.sorted('id')
        with self.env.cr.savepoint():
            # Serialize clicks before reading the existing journal entry.
            tasks.flush_recordset(['invoice_id'])
            self.env.cr.execute('SELECT id FROM step_tarja WHERE id = ANY(%s) ORDER BY id FOR UPDATE', [tasks.ids])
            tasks.invalidate_recordset(['invoice_id'])
            scopes = [(task, task._step_daily_accounting_scope()) for task in tasks]
            for task, scope in scopes:
                super(StepTarja, task.with_context(**{SCOPE_KEY: scope})).action_conta()
