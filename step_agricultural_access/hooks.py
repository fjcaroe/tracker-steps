from odoo import Command


def post_init_hook(env):
    """Preserve the pre-installation menu visibility for current users."""
    agricultural_category = env.ref(
        "step_agricultural_access.module_category_agricultural_steps"
    )
    categories = env["ir.module.category"].search(
        [("id", "child_of", agricultural_category.id)]
    )
    groups = env["res.groups"].search([("category_id", "in", categories.ids)])
    internal_users = env["res.users"].with_context(active_test=False).search(
        [("share", "=", False)]
    )
    internal_users.write(
        {"groups_id": [Command.link(group_id) for group_id in groups.ids]}
    )
