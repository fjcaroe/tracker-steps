/** @odoo-module **/

/**
 * Rotula las columnas de semana de las hojas del flujo con la semana
 * calendario real del horizonte.
 *
 * Las cubetas del modelo siguen siendo `w1`..`w5` —ventanas de siete días
 * desde el inicio del horizonte—, pero el encabezado que ve el usuario debe
 * decir W35, W36, … El rótulo depende del registro abierto, y el encabezado de
 * una lista se resuelve en el cliente, así que se reescribe aquí: se toma el
 * `start_date` del flujo, que es el registro padre del one2many, y se
 * reemplaza el rótulo de esas cinco columnas antes de renderizar.
 */

import { registry } from "@web/core/registry";
import { X2ManyField, x2ManyField } from "@web/views/fields/x2many/x2many_field";

/** Columnas afectadas, en orden de ventana. */
const WEEK_FIELDS = ["amount_w1", "amount_w2", "amount_w3", "amount_w4", "amount_w5"];

/** Milisegundos de un día, para desplazar el inicio de cada ventana. */
const DAY_MS = 24 * 60 * 60 * 1000;

/**
 * Semana ISO-8601 de una fecha. Igual que `date.isocalendar()[1]` en Python:
 * la semana empieza en lunes y la número 1 es la que contiene el 4 de enero.
 */
function isoWeek(date) {
    const target = new Date(Date.UTC(date.getFullYear(), date.getMonth(), date.getDate()));
    // Se lleva la fecha al jueves de su semana: el año ISO es el de ese jueves.
    const isoDay = (target.getUTCDay() + 6) % 7;
    target.setUTCDate(target.getUTCDate() - isoDay + 3);
    const firstThursday = new Date(Date.UTC(target.getUTCFullYear(), 0, 4));
    const firstIsoDay = (firstThursday.getUTCDay() + 6) % 7;
    firstThursday.setUTCDate(firstThursday.getUTCDate() - firstIsoDay + 3);
    return 1 + Math.round((target - firstThursday) / (7 * DAY_MS));
}

/** Convierte el valor de un campo Date de Odoo a un `Date` nativo. */
function toNativeDate(value) {
    if (!value) {
        return null;
    }
    if (value instanceof Date) {
        return value;
    }
    // Los campos de fecha llegan como objetos luxon.
    if (typeof value.toJSDate === "function") {
        return value.toJSDate();
    }
    const parsed = new Date(value);
    return isNaN(parsed.getTime()) ? null : parsed;
}

export class TreasuryWeekLinesField extends X2ManyField {
    /** Rótulo por campo, o `null` si el flujo todavía no tiene fecha de inicio. */
    get weekLabels() {
        const start = toNativeDate(this.props.record.data.start_date);
        if (!start) {
            return null;
        }
        const labels = {};
        WEEK_FIELDS.forEach((field, index) => {
            const day = new Date(start.getTime() + index * 7 * DAY_MS);
            labels[field] = `W${isoWeek(day)}`;
        });
        return labels;
    }

    get rendererProps() {
        const props = super.rendererProps;
        const labels = this.weekLabels;
        if (!labels || !props.archInfo || !props.archInfo.columns) {
            return props;
        }
        props.archInfo = {
            ...props.archInfo,
            columns: props.archInfo.columns.map((column) => {
                const label = labels[column.name];
                if (!label) {
                    return column;
                }
                // `attrs.sum` es el texto del total al pie; se mueve junto con
                // el encabezado para que ambos digan la misma semana.
                const attrs = column.attrs && column.attrs.sum
                    ? { ...column.attrs, sum: label }
                    : column.attrs;
                return { ...column, label, string: label, attrs };
            }),
        };
        return props;
    }
}

export const treasuryWeekLinesField = {
    ...x2ManyField,
    component: TreasuryWeekLinesField,
};

registry.category("fields").add("treasury_week_lines", treasuryWeekLinesField);
