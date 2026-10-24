/** Column preferences for the Helpdesk portal list. */
(() => {
    const storageKey = "steps.helpdesk.ticket-columns.v1";
    const available = ["created", "assignee", "priority", "updated", "comment"];
    const defaults = ["created", "assignee"];

    function init() {
        const portal = document.querySelector(".steps-helpdesk-portal .steps-helpdesk-columns");
        if (!portal) return;
        const table = document.querySelector(".steps-helpdesk-portal .table");

        // Odoo's built-in search, sort and group controls generate their own
        // links. Carry the additional filters through those controls too.
        const customFilters = [...new URLSearchParams(window.location.search)]
            .filter(([name]) => name.startsWith("steps_"));
        portal.closest(".steps-helpdesk-portal")
            .querySelectorAll(".o_portal_search_panel a[href]")
            .forEach((link) => {
                const url = new URL(link.href, window.location.origin);
                if (url.pathname !== "/my/tickets") return;
                for (const [name, value] of customFilters) {
                    if (!url.searchParams.has(name)) url.searchParams.set(name, value);
                }
                link.href = url.toString();
            });
        portal.closest(".steps-helpdesk-portal")
            .querySelectorAll(".o_portal_search_panel form")
            .forEach((form) => {
                for (const [name, value] of customFilters) {
                    if (form.elements.namedItem(name)) continue;
                    const input = document.createElement("input");
                    input.type = "hidden";
                    input.name = name;
                    input.value = value;
                    form.appendChild(input);
                }
            });
        if (!table) return;

        let selected = defaults;
        try {
            const saved = JSON.parse(localStorage.getItem(storageKey));
            if (Array.isArray(saved)) selected = saved.filter((column) => available.includes(column));
        } catch (_) {
            selected = defaults;
        }

        function render() {
            for (const column of available) {
                const visible = selected.includes(column);
                table.querySelectorAll(`[data-steps-column="${column}"]`).forEach((cell) => {
                    cell.hidden = !visible;
                });
                const choice = portal.querySelector(`[data-steps-column-choice="${column}"]`);
                if (choice) choice.checked = visible;
            }
            table.querySelectorAll(".steps-helpdesk-group-row th").forEach((cell) => {
                cell.colSpan = 2 + selected.length;
            });
        }

        portal.querySelectorAll("[data-steps-column-choice]").forEach((choice) => {
            choice.addEventListener("change", () => {
                selected = available.filter((column) => {
                    const input = portal.querySelector(`[data-steps-column-choice="${column}"]`);
                    return input && input.checked;
                });
                try {
                    localStorage.setItem(storageKey, JSON.stringify(selected));
                } catch (_) {
                    // The choice still works for this page when storage is unavailable.
                }
                render();
            });
        });
        render();
    }

    if (document.readyState === "loading") {
        document.addEventListener("DOMContentLoaded", init, { once: true });
    } else {
        init();
    }
})();
