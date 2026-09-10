/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class StepsPayrollDashboard extends Component {
    static template = "step_hr_remuneration_book.PayrollDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.state = useState({ loading: true, error: null, data: null });
        onWillStart(() => this.load());
    }

    // Sin período, el servidor abre en el mes anterior: el mes en curso todavía
    // no tiene liquidaciones cargadas.
    async load(period = null) {
        this.state.loading = true;
        this.state.error = null;
        try {
            this.state.data = await this.orm.call(
                "hr.payslip",
                "get_steps_payroll_dashboard",
                [],
                { period }
            );
        } catch {
            this.state.error = "No fue posible cargar el resumen de Nómina.";
        } finally {
            this.state.loading = false;
        }
    }

    onPeriodChange(ev) {
        return this.load(ev.target.value);
    }

    openAction(xmlId) {
        return this.action.doAction(xmlId);
    }

    openPayslips(state = null) {
        const domain = state ? [["state", "=", state]] : [];
        return this.action.doAction({
            type: "ir.actions.act_window",
            name: "Recibos de nómina",
            res_model: "hr.payslip",
            views: [[false, "list"], [false, "form"]],
            domain,
            target: "current",
        });
    }

    openBatch(id) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "hr.payslip.run",
            res_id: id,
            views: [[false, "form"]],
            target: "current",
        });
    }

    formatAmount(value) {
        return new Intl.NumberFormat("es-CL", { maximumFractionDigits: 0 }).format(value || 0);
    }

    formatPercent(value, digits = 1) {
        return `${new Intl.NumberFormat("es-CL", {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
        }).format(value || 0)} %`;
    }
}

registry.category("actions").add(
    "step_hr_remuneration_book.payroll_dashboard",
    StepsPayrollDashboard
);
