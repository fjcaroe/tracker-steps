from odoo import Command
from odoo.tests import HttpCase, tagged


@tagged("post_install", "-at_install")
class TestNurseryOfflineHttp(HttpCase):
    def test_shell_and_authenticated_session(self):
        shell = self.url_open("/nursery-offline/")
        self.assertEqual(shell.status_code, 200)
        self.assertIn("Bitácora de vivero", shell.text)
        worker = self.url_open("/nursery-offline/sw.js")
        self.assertEqual(worker.status_code, 200)
        self.assertIn("steps-nursery-shell", worker.text)
        login = "qa-nursery-offline-http"
        user = self.env["res.users"].with_context(no_reset_password=True).create({
            "name": "QA Bitácora", "login": login, "password": login,
            "company_id": self.env.company.id, "company_ids": [Command.set(self.env.company.ids)],
            "groups_id": [Command.set(self.env.ref("step_nursery_operations.group_nursery_operator").ids)],
        })
        self.authenticate(login, login)
        session = self.url_open("/nursery-offline/session")
        self.assertEqual(session.status_code, 200)
        profile = session.json()
        self.assertEqual(profile["uid"], user.id)
        self.assertEqual(profile["companies"][0]["id"], self.env.company.id)
        self.assertIn("no-store", session.headers["Cache-Control"])
        foreign = self.url_open("/nursery-offline/orders/2147483647")
        self.assertEqual(foreign.status_code, 403)
        wrong_actor = self.url_open("/nursery-offline/sync", data={
            "csrf_token": profile["csrf"], "uid": user.id + 1, "company": self.env.company.id, "batch": "[]",
        })
        self.assertEqual(wrong_actor.status_code, 403)
