/** @odoo-module **/

import { registry } from "@web/core/registry";
import { session } from "@web/session";

registry.category("services").add("steps_greenhouse_theme", {
    dependencies: ["company"],
    start(env, { company }) {
        document.body.classList.toggle(
            "o_ecoplantas_company",
            company.currentCompany.id === session.steps_greenhouse_company
        );
    },
});
