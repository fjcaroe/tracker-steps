"""Preserve historical line audit and nullable flags during initial field fill."""


def pre_init_hook(env):
    # A transaction-local backup, never another business table or master.
    # Filling the new stored packaging snapshot invokes an ORM write; Odoo
    # otherwise stamps every old line and fills unrelated nullable booleans.
    env.cr.execute('''CREATE TEMPORARY TABLE step_document_line_initial ON COMMIT DROP AS
        SELECT id,write_uid,write_date,is_service,is_downpayment FROM sale_order_line''')


def post_init_hook(env):
    env.flush_all()
    env.cr.execute('''UPDATE sale_order_line l SET write_uid=b.write_uid,write_date=b.write_date,
        is_service=b.is_service,is_downpayment=b.is_downpayment
        FROM step_document_line_initial b WHERE l.id=b.id''')
    env.invalidate_all(flush=False)
