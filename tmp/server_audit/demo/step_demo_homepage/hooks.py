def post_init_hook(env):
    """Make the branded homepage the active primary view for each website."""
    homepage = env.ref("website.homepage", raise_if_not_found=False)
    if not homepage:
        return

    website = env["website"].sudo().search([], limit=1)
    if website:
        website.name = "Steps Agro Demo"

    competing = env["ir.ui.view"].sudo().search(
        [
            ("key", "=", "website.homepage"),
            ("id", "!=", homepage.id),
            "|",
            ("website_id", "=", False),
            ("website_id", "=", website.id if website else False),
        ]
    )
    competing.write(
        {
            "active": True,
            "name": homepage.name,
            "arch_db": homepage.arch_db,
        }
    )
