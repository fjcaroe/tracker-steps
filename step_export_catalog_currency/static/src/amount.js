/** @odoo-module **/
import { registry } from "@web/core/registry";
import { formatFloat } from "@web/views/fields/formatters";
import { monetaryField } from "@web/views/fields/monetary/monetary_field";

// Keep the native currency binding and the native mixed-currency sum guard.
// Column/form labels identify the unit; cells and list/group totals omit symbols.
registry.category("fields").add("step_export_amount", {
    ...monetaryField,
    extractProps: (args) => ({ ...monetaryField.extractProps(args), hideSymbol: true }),
});
registry.category("formatters").add("step_export_amount", (value, options = {}) =>
    formatFloat(value, { ...options, digits: options.digits || [16, 2] })
);
