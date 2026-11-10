/** @odoo-module **/

import { patch } from "@web/core/utils/patch";
import { StepActivitiesDashboard } from "@step_hr/js/activities_dashboard";

patch(StepActivitiesDashboard.prototype, {
    async loadDashboard(period = this.state.period || "day") {
        const request = (this.periodRequest || 0) + 1;
        this.periodRequest = request;
        this.state.period = period;
        this.state.loading = true;
        this.state.error = null;
        try {
            const data = await this.orm.call("hr.salary.custom", "get_activities_period_dashboard", [period]);
            if (request === this.periodRequest) {
                this.state.data = data;
            }
        } catch {
            if (request === this.periodRequest) {
                this.state.error = "No fue posible cargar el centro de Actividades.";
                this.notification.add(this.state.error, { type: "danger" });
            }
        } finally {
            if (request === this.periodRequest) {
                this.state.loading = false;
            }
        }
    },
});
