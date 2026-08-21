from odoo import Command


AGRICULTURAL_GROUP_XMLIDS = (
    "step_agricultural_access.group_app_activities",
    "step_agricultural_access.group_app_tracker",
    "step_agricultural_access.group_app_machinery",
    "step_agricultural_access.group_app_harvest",
    "step_agricultural_access.group_app_bpa_irrigation",
    "step_agricultural_access.group_app_quality",
    "step_agricultural_access.group_app_labor_protection",
    "step_agricultural_access.group_app_management_costs",
    "step_agricultural_access.group_app_freight",
)


def post_init_hook(env):
    """Preserve the pre-installation menu visibility for current users."""
    groups = env["res.groups"].browse(
        [env.ref(xmlid).id for xmlid in AGRICULTURAL_GROUP_XMLIDS]
    )
    internal_users = env["res.users"].with_context(active_test=False).search(
        [("share", "=", False)]
    )
    internal_users.write(
        {"groups_id": [Command.link(group_id) for group_id in groups.ids]}
    )
