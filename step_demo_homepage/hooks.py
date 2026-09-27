def post_init_hook(env):
    """Make the branded homepage the active primary view for each website."""
    homepage = env.ref("website.homepage", raise_if_not_found=False)
    if not homepage:
        return

    website = env["website"].sudo().search([], limit=1)
    if website:
        website.name = "Steps Agro"

    page_values = {
        "active": True,
        "name": homepage.name,
        "arch_db": homepage.arch_db,
        "website_meta_title": homepage.website_meta_title,
        "website_meta_description": homepage.website_meta_description,
        "website_meta_keywords": homepage.website_meta_keywords,
    }

    competing = env["ir.ui.view"].sudo().search(
        [
            ("key", "=", "website.homepage"),
            ("id", "!=", homepage.id),
            "|",
            ("website_id", "=", False),
            ("website_id", "=", website.id if website else False),
        ]
    )
    competing.write(page_values)

    # Odoo caches sitemap.xml as attachments for several hours. Clear only
    # those generated files so new public pages are visible immediately.
    env["ir.attachment"].sudo().search(
        [("type", "=", "binary"), ("url", "=like", "/sitemap-%.xml")]
    ).unlink()
