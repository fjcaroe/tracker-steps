/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class StepsTrackerDashboard extends Component {
    static template = "step_tracker_odoo.StepsTrackerDashboard";

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.notification = useService("notification");
        this.state = useState({
            loading: true,
            days: 30,
            data: null,
        });
        onWillStart(() => this.loadDashboard());
    }

    async loadDashboard(days = this.state.days) {
        this.state.loading = true;
        this.state.days = Number(days);
        try {
            this.state.data = await this.orm.call(
                "step.tracker.work_order",
                "get_dashboard_data",
                [],
                { days: this.state.days }
            );
        } catch (error) {
            this.notification.add(
                "No fue posible cargar el tablero de Steps Tracker.",
                { type: "danger" }
            );
            throw error;
        } finally {
            this.state.loading = false;
        }
    }

    openAction(xmlId, domain = []) {
        return this.action.doAction(xmlId, { additionalContext: { tracker_dashboard_domain: domain } });
    }

    openSession(sessionId) {
        return this.action.doAction({
            type: "ir.actions.act_window",
            res_model: "step.tracker.session",
            res_id: sessionId,
            views: [[false, "form"]],
            target: "current",
        });
    }

    openWebTracker() {
        return this.action.doAction("step_tracker_odoo.action_step_tracker_open_web");
    }

    formatNumber(value, digits = 0) {
        return new Intl.NumberFormat("es-CL", {
            minimumFractionDigits: digits,
            maximumFractionDigits: digits,
        }).format(value || 0);
    }

    formatDate(value) {
        if (!value) {
            return "Sin fecha";
        }
        return new Intl.DateTimeFormat("es-CL", {
            day: "2-digit",
            month: "short",
            hour: "2-digit",
            minute: "2-digit",
        }).format(new Date(`${value.replace(" ", "T")}Z`));
    }
}

registry.category("actions").add("step_tracker_odoo.tracker_dashboard", StepsTrackerDashboard);
