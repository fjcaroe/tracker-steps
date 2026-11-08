/** @odoo-module **/

import { Component, onWillStart, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";
import { stages } from "./workspace";

class Greenhouse extends Component {
    static template = "step_ecoplantas_greenhouse.Dashboard";
    static props = ["*"];

    setup() {
        this.workspace = useService("steps_greenhouse_workspace");
        this.state = useState(this.workspace.state);
        onWillStart(() => this.workspace.refresh());
    }

    get data() {
        return this.state.data;
    }

    get stages() {
        return stages;
    }

    openRecord(key) {
        return this.workspace.open(key);
    }

    openTasks() {
        return this.workspace.open("project");
    }

    openLots() {
        return this.workspace.open("lots");
    }
}

registry.category("actions").add("step_ecoplantas_greenhouse.dashboard", Greenhouse);
