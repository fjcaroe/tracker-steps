"""Preserve IDs when legacy XML resets an already identical action-view graph.

Only the short-lived upgrade process installs this adapter. Different graphs
follow normal Odoo handling and must pass the destination identity checks.
"""
def identical_reset(commands, existing):
    if not isinstance(commands, (tuple, list)) or not commands or commands[0][0] != 5:
        return False
    target = []
    for command in commands[1:]:
        if len(command) != 3 or command[0] != 0 or not isinstance(command[2], dict):
            return False
        values = command[2]
        if set(values) - {'view_mode', 'view_id', 'sequence'}:
            return False
        target.append((values.get('view_mode'), values.get('view_id', False), values.get('sequence', 0)))
    return bool(existing) and target == existing


def install():
    import logging
    from odoo.addons.base.models.ir_actions import IrActionsActWindow
    original = IrActionsActWindow.write
    if getattr(original, '_steps_preserve_identical_views', False):
        return
    logger = logging.getLogger(__name__)

    def write(actions, values):
        commands = values.get('view_ids')
        if not commands:
            return original(actions, values)
        result = True
        for action in actions:
            existing = [(row.view_mode, row.view_id.id or False, row.sequence) for row in action.view_ids]
            specific = values
            if identical_reset(commands, existing):
                specific = {k: v for k, v in values.items() if k != 'view_ids'}
                logger.info('Preserving identical action-view IDs for action %s', action.id)
            result = original(action, specific) and result
        return result

    write._steps_preserve_identical_views = True
    IrActionsActWindow.write = write


def install_menu_order():
    """The extraction changes ownership, not customers' existing menu order."""
    from odoo.addons.base.models.ir_ui_menu import IrUiMenu
    original = IrUiMenu.write
    if getattr(original, '_steps_preserve_menu_order', False):
        return
    captured = {}

    def write(menus, values):
        database = menus.env.cr.dbname
        if database not in captured:
            menus.env.cr.execute('SELECT id FROM ir_ui_menu')
            captured[database] = {row[0] for row in menus.env.cr.fetchall()}
        if 'sequence' not in values:
            return original(menus, values)
        result = True
        for menu in menus:
            specific = {k: v for k,v in values.items() if k != 'sequence'} if menu.id in captured[database] else values
            result = original(menu, specific) and result
        return result

    write._steps_preserve_menu_order = True
    IrUiMenu.write = write
