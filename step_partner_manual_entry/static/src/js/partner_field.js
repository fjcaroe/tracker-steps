/** @odoo-module **/
import "@partner_autocomplete/js/partner_autocomplete_many2one";
import { registry } from "@web/core/registry";
import { many2OneField } from "@web/views/fields/many2one/many2one_field";

// Keep native local search, quick create and create/edit. No paid suggestions.
registry.category("fields").add("res_partner_many2one", many2OneField, { force: true });
