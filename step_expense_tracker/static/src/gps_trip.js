/** @odoo-module **/
import { Component, xml, onMounted, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

class GpsTripExpense extends Component {
    static template = xml`<main class="p-4"><h2>Rendir un recorrido GPS</h2>
        <p role="status" t-esc="state.message"/>
        <a href="/tracker#history">Volver a Tracker</a></main>`;
    setup() {
        const action = useService("action");
        const orm = useService("orm");
        this.state = useState({ message: "Preparando el formulario de rendición…" });
        onMounted(async () => {
            try {
                const key = "steps.tracker.expenseTrip";
                const draft = JSON.parse(sessionStorage.getItem(key) || "null");
                if (!draft || Date.now() - draft.created > 15 * 60 * 1000) {
                    sessionStorage.removeItem(key);
                    this.state.message = "Selecciona el recorrido en Tracker para preparar una rendición.";
                    return;
                }
                const form = await orm.call("hr.expense", "action_prepare_tracker_trip", [draft], {
                    context: { allowed_company_ids: [draft.company] },
                });
                await action.doAction(form, { clearBreadcrumbs: true });
                sessionStorage.removeItem(key);
            } catch (error) {
                this.state.message = error.data?.message || "No se pudo abrir la rendición. Vuelve a Tracker e inténtalo de nuevo.";
            }
        });
    }
}
registry.category("actions").add("steps_expense_gps_trip", GpsTripExpense);
