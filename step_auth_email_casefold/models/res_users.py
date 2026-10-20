"""Normalize email identifiers only; retain native password, MFA and cooldown checks."""
from odoo import api, models, _
from odoo.exceptions import ValidationError


def email_login(value):
    return isinstance(value, str) and '@' in value


class Users(models.Model):
    _inherit = 'res.users'

    def init(self):
        super().init()
        self.env.cr.execute("SELECT 1 FROM res_users WHERE strpos(login,'@')>0 GROUP BY lower(login) HAVING count(*)>1 LIMIT 1")
        if self.env.cr.fetchone():
            raise ValidationError(_('Existen correos de usuario que solo difieren en mayúsculas. Resuelva la duplicidad antes de instalar.'))
        self.env.cr.execute("CREATE UNIQUE INDEX IF NOT EXISTS step_auth_email_login_ci_unique ON res_users (lower(login)) WHERE strpos(login,'@')>0")

    @api.model
    def _get_login_domain(self, login):
        if not email_login(login):
            return super()._get_login_domain(login)
        # Equality is literal: percent and underscore in a mailbox are never wildcards.
        # The index guarantees one identity, including accounts archived for later reuse.
        self.env.cr.execute("SELECT id FROM res_users WHERE strpos(login,'@')>0 AND lower(login)=lower(%s)", [login])
        ids = [row[0] for row in self.env.cr.fetchall()]
        return [('id', '=', ids[0] if len(ids) == 1 else 0)]

    @classmethod
    def _login(cls, db, credential, user_agent_env):
        if email_login(credential.get('login')):
            credential = dict(credential, login=credential['login'].lower())
        return super()._login(db, credential, user_agent_env)

    @api.model
    def _check_email_login_available(self, login, exclude=()):
        if not email_login(login):
            return
        self.env.cr.execute("SELECT id FROM res_users WHERE strpos(login,'@')>0 AND lower(login)=lower(%s)", [login])
        if any(row[0] not in exclude for row in self.env.cr.fetchall()):
            raise ValidationError(_('Ya existe una cuenta con ese correo, independientemente de las mayúsculas.'))

    @api.model_create_multi
    def create(self, vals_list):
        values = []
        seen = set()
        for vals in vals_list:
            vals = dict(vals)
            login = vals.get('login')
            if email_login(login):
                login = vals['login'] = login.lower()
                self._check_email_login_available(login)
                if login in seen:
                    raise ValidationError(_('No cree varias cuentas con el mismo correo.'))
                seen.add(login)
            values.append(vals)
        return super().create(values)

    def write(self, vals):
        if email_login(vals.get('login')):
            vals = dict(vals, login=vals['login'].lower())
            if len(self)>1:
                raise ValidationError(_('Actualice el correo de una cuenta a la vez.'))
            self._check_email_login_available(vals['login'], self.ids)
        return super().write(vals)
