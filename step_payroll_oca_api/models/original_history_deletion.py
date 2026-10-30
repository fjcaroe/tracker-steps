"""Original deletion policies with explicit, ordinary-actor draft deletion.

The native run FK is CASCADE. PostgreSQL alone would skip the actual child
unlink methods. Authorize the complete physical descendants and invoke their
real ORM unlink chain before deleting a run; never reconstruct payroll values.
"""
from psycopg2 import sql

from odoo import _, fields, models
from odoo.exceptions import UserError
from odoo.addons.step_payroll_contracts.history import assert_mutable


def _access(records, names):
    records.check_access("read")
    records.check_access("unlink")
    records.check_field_access_rights("read", names)
    return records


def _lock(records, names):
    _access(records, names)
    if any(type(ident) is not int or ident <= 0 for ident in records.ids):
        raise UserError(_("Delete only saved original payroll drafts."))
    records.flush_recordset(names)
    if records:
        records.env.cr.execute(sql.SQL("SELECT id FROM {} WHERE id=ANY(%s) ORDER BY id FOR UPDATE").format(
            sql.Identifier(records._table)), (records.ids,))
        if {row[0] for row in records.env.cr.fetchall()} != set(records.ids):
            raise UserError(_("Original payroll records changed before deletion."))
        records.invalidate_recordset(names)
        _access(records, names)
    return records


def _children(parents, relation):
    """Read only full relation IDs after model/field ACL; no filtered O2M."""
    parents.check_access("read")
    parents.check_field_access_rights("read", [relation])
    field = parents._fields[relation]
    if field.type != "one2many" or field.related:
        raise UserError(_("Original payroll child relation requires review before deletion."))
    children = parents.env[field.comodel_name].with_context(active_test=False)
    inverse = children._fields[field.inverse_name]
    if inverse.type != "many2one" or inverse.comodel_name != parents._name or not inverse.store:
        raise UserError(_("Original payroll child ownership requires review before deletion."))
    _access(children, [inverse.name])
    children.flush_model([inverse.name])
    parents.env.cr.execute(sql.SQL("SELECT id FROM {} WHERE {}=ANY(%s) ORDER BY id").format(
        sql.Identifier(children._table), sql.Identifier(inverse.name)), (parents.ids,))
    return children.browse([row[0] for row in parents.env.cr.fetchall()]), inverse.name


def _company(records):
    company = records.env.company
    company.check_access("read")
    owners = records.company_id
    owners.check_access("read")
    if any(not record.company_id or record.company_id != company for record in records):
        raise UserError(_("Select the original payroll company before deleting its drafts."))


class Payslip(models.Model):
    _inherit = "hr.payslip"

    company_id = fields.Many2one(required=True, ondelete="restrict")
    payslip_run_id = fields.Many2one(ondelete="cascade")


class PayslipRun(models.Model):
    _inherit = "hr.payslip.run"

    def unlink(self):
        normal = self.sudo(False).with_context(active_test=False)
        if not normal:
            return super(PayslipRun, normal).unlink()
        # The savepoint also protects callers that catch a later provider
        # exception without rolling back their whole transaction.
        with normal.env.cr.savepoint():
            run_fields = ["state", "company_id", "credit_note", "slip_ids"]
            _lock(normal, run_fields)
            _company(normal)
            if any(run.state != "draft" or run.credit_note for run in normal):
                raise UserError(_("Delete only unapproved draft payroll batches; closed or refund batches require review."))
            slips, inverse = _children(normal, "slip_ids")
            slip_fields = ["state", "company_id", "paid", "credit_note", inverse]
            slip_fields += [name for name in ("step_history_locked", "move_id", "compute_date") if name in slips._fields]
            _lock(slips, slip_fields)
            _company(slips)
            assert_mutable(slips)
            if any(slip.state != "draft" or slip.credit_note
                    or ("move_id" in slip._fields and slip.move_id)
                    or ("compute_date" in slip._fields and slip.compute_date)
                    or slip.payslip_run_id not in normal for slip in slips):
                raise UserError(_("Delete only unapproved, unposted draft payslips; calculated or closed history is preserved."))
            descendants = []
            for relation in ("line_ids", "input_line_ids", "worked_days_line_ids"):
                children, owner = _children(slips, relation)
                _lock(children, [owner])
                if any(record[owner] not in slips for record in children):
                    raise UserError(_("Original payroll child ownership changed before deletion."))
                descendants.append(children)
            # Locks on the parent prevent concurrent FK attachments. Re-read
            # physical IDs as a final assertion; no cached relation subset can
            # silently become the scope of a SQL cascade.
            current, unused = _children(normal, "slip_ids")
            if set(current.ids) != set(slips.ids):
                raise UserError(_("Original batch membership changed before deletion."))
            for children in descendants:
                children.unlink()
            slips.unlink()
            remaining, unused = _children(normal, "slip_ids")
            if remaining:
                raise UserError(_("A payroll provider left unapproved batch children; deletion was rolled back."))
            return super(PayslipRun, normal).unlink()
