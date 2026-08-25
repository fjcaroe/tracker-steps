import logging


_logger = logging.getLogger(__name__)


def post_init_hook(env):
    """Hide the obsolete standalone Studio launcher without deleting its data.

    Finiquitos is being incorporated into the contractual lifecycle.  The
    legacy Studio root menu is therefore archived so it no longer appears as
    an independent application, while its models and records remain intact.
    """
    menu = env.ref(
        "studio_customization.finiquitos_76a3c0e4-8cce-4d9f-aa56-c3e0b98129aa",
        raise_if_not_found=False,
    )
    if not menu:
        menu = env["ir.ui.menu"].sudo().search(
            [("name", "=", "Finiquitos"), ("parent_id", "=", False)],
            limit=1,
        )
    if menu and menu.active:
        menu.sudo().write({"active": False})
        _logger.info("Archived legacy standalone Finiquitos launcher (menu %s).", menu.id)

