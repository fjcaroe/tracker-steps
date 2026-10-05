from odoo import Command
from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, tagged


@tagged("post_install", "-at_install")
class KnowledgeSourceTests(TransactionCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.user = cls.env["res.users"].with_context(no_reset_password=True).create({
            "name": "Knowledge assistant reader", "login": "knowledge_assistant_reader",
            "company_id": cls.env.company.id, "company_ids": [Command.set([cls.env.company.id])],
            "groups_id": [Command.set([cls.env.ref("base.group_user").id])],
        })
        Knowledge = cls.env["knowledge.article"]
        owner = [Command.create({"partner_id": cls.env.user.partner_id.id, "permission": "write"})]
        cls.public_article = Knowledge.create({"name": "Approved help", "internal_permission": "read", "body": "<p>Guía compartida de nuestro Odoo para usuarios internos.</p>", "article_member_ids": owner})
        cls.private_article = Knowledge.create({"name": "Private help", "internal_permission": "none", "body": "<p>Contenido privado que no debe aparecer.</p>", "article_member_ids": owner})
        cls.Approval = cls.env["step.assistant.knowledge.approval"]
        cls.Approval.create([{"article_id": cls.public_article.id, "published": True}, {"article_id": cls.private_article.id, "published": True}])

    def sources(self):
        return self.env["step.assistant.article"].with_user(self.user)._available_sources()

    def test_private_knowledge_never_reaches_sources(self):
        ids = [item["id"] for item in self.sources()]
        self.assertIn(-self.public_article.id, ids)
        self.assertNotIn(-self.private_article.id, ids)

    def test_revoked_knowledge_permissions_take_effect_immediately(self):
        self.public_article.internal_permission = "none"
        self.assertNotIn(-self.public_article.id, [item["id"] for item in self.sources()])

    def test_unapproved_article_not_retrieved(self):
        self.Approval.search([("article_id", "=", self.public_article.id)]).published = False
        self.assertNotIn(-self.public_article.id, [item["id"] for item in self.sources()])

    def test_reader_cannot_manage_approvals(self):
        with self.assertRaises(AccessError):
            self.Approval.with_user(self.user).search([])

    def test_markup_is_stripped(self):
        source = next(item for item in self.sources() if item["id"] == -self.public_article.id)
        self.assertNotIn("<p>", source["content"])
        self.assertIn("Guía compartida", source["content"])
