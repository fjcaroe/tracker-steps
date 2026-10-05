/** @odoo-module **/
import { Component, onWillStart, onPatched, useRef, useState } from "@odoo/owl";
import { registry } from "@web/core/registry";
import { useService } from "@web/core/utils/hooks";

export class StepsAssistant extends Component {
    static template = "step_support_assistant.Chat";
    static props = ["*"];

    setup() {
        this.orm = useService("orm");
        this.action = useService("action");
        this.transcript = useRef("transcript");
        this.composer = useRef("composer");
        this.state = useState({ loading: true, busy: false, ready: false, error: "", question: "", messages: [], articles: [], notice: "" });
        onWillStart(async () => {
            try {
                const data = await this.orm.call("step.support.assistant", "get_bootstrap", []);
                Object.assign(this.state, { ready: data.ready, articles: data.articles, notice: data.notice });
            } catch {
                this.state.error = "No fue posible cargar la ayuda. Reintenta o contacta a soporte.";
            } finally {
                this.state.loading = false;
            }
        });
        this.lastLength = 0;
        onPatched(() => {
            if (this.state.messages.length !== this.lastLength || this.state.busy) {
                this.transcript.el?.scrollTo({ top: this.transcript.el.scrollHeight, behavior: "smooth" });
                this.lastLength = this.state.messages.length;
            }
        });
    }

    async submit() {
        const question = this.state.question.trim();
        if (!question || question.length > 2000 || this.state.busy || this.state.loading) return;
        const previousQuestions = this.state.messages.filter(message => message.role === "user").slice(-4).map(message => message.text);
        this.state.messages.push({ id: this.state.messages.length, role: "user", text: question, sources: [] });
        this.state.question = "";
        this.state.busy = true;
        this.state.error = "";
        try {
            const result = await this.orm.call("step.support.assistant", "ask", [], { question, previous_questions: previousQuestions });
            this.state.messages.push({ id: this.state.messages.length, role: "assistant", text: result.answer, sources: result.sources });
        } catch (error) {
            this.state.error = error.data?.message || "No fue posible enviar la consulta. Reintenta o contacta a soporte.";
            this.state.question = question;
            this.state.messages.pop();
        } finally {
            this.state.busy = false;
            this.composer.el?.focus();
        }
    }

    onKeydown(event) {
        if (event.key === "Enter" && !event.shiftKey && !event.isComposing) {
            event.preventDefault();
            this.submit();
        }
    }

    newConversation() {
        if (this.state.busy) return;
        this.state.messages = [];
        this.state.question = "";
        this.state.error = "";
    }

    openArticle(id) {
        return this.action.doAction({ type: "ir.actions.act_window", res_model: id < 0 ? "knowledge.article" : "step.assistant.article", res_id: Math.abs(id),
            views: [[false, "form"]], target: "new" });
    }
}

class AssistantLauncher extends Component {
    static template = "step_support_assistant.Launcher";
    static props = ["*"];
    setup() { this.action = useService("action"); }
    open() { return this.action.doAction("step_support_assistant.action_assistant"); }
}

registry.category("actions").add("step_support_assistant.chat", StepsAssistant);
registry.category("systray").add("step_support_assistant.launcher", { Component: AssistantLauncher }, { sequence: 5 });
