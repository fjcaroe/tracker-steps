/** @odoo-module **/
import { Component, onWillStart, useState } from '@odoo/owl';
import { registry } from '@web/core/registry';
import { useService } from '@web/core/utils/hooks';

export class ControlPanel extends Component {
    static template = 'step_export_control.Panel';
    static props = ['*'];
    setup() {
        this.orm = useService('orm'); this.action = useService('action');
        this.mode = this.props.action.tag.endsWith('vessels') ? 'vessels' : 'documents';
        this.state = useState({ loading: true, error: '', data: null, query: '', season: '', date: '', position: 'theoretical', status: '' });
        onWillStart(() => this.load());
    }
    async load() {
        this.state.loading = true; this.state.error = '';
        try {
            this.state.data = await this.orm.call('step.export.export', 'control_dashboard', [], {
                mode: this.mode, season_id: this.state.season || false, query: this.state.query,
                consultation_date: this.state.date || false,
            });
            this.state.date ||= this.state.data.date;
        } catch (error) { this.state.error = error.message || 'No se pudo consultar el panel.'; }
        finally { this.state.loading = false; }
    }
    get rows() {
        return (this.state.data?.rows || []).filter(r => !this.state.status || (this.mode === 'vessels'
            ? r.voyage_status === this.state.status : r.documents.some(d => d.color === this.state.status && !d.sent)));
    }
    get metrics() {
        const rows = this.state.data?.rows || [];
        return this.mode === 'documents' ? [
            { label: 'Embarques', value: rows.length },
            { label: 'Documentos enviados', value: rows.flatMap(r => r.documents).filter(d => d.sent).length },
            { label: 'Pendientes vencidos', value: rows.flatMap(r => r.documents).filter(d => !d.sent && d.color === 'late').length },
        ] : [
            { label: 'En trÃ¡nsito', value: rows.filter(r => r.voyage_status === 'transit').length },
            { label: 'PrÃ³ximos a arribar', value: rows.filter(r => r.near_arrival).length },
            { label: 'Arribados', value: rows.filter(r => r.voyage_status === 'arrived').length },
        ];
    }
    onMarkerKey(event, id) { if (event.key === 'Enter') this.open(id); }
    open(id) { return this.action.doAction({ type: 'ir.actions.act_window', res_model: 'step.export.export', res_id: id, views: [[false, 'form']], target: 'current' }); }
    configure(xmlid) { return this.action.doAction('step_export_control.' + xmlid); }
    date(value) { return value ? value.split('-').reverse().join('-') : 'â€”'; }
    shortDate(value) { return value ? value.slice(5).split('-').reverse().join('-') : ''; }
    status(row) { return { transit: 'En trÃ¡nsito', arrived: 'Arribado', scheduled: 'Por zarpar', unknown: 'Revisar fechas' }[row.voyage_status]; }
    title(doc) { return `${doc.sent ? 'Enviado: ' + this.date(doc.date) : 'Pendiente'} Â· MÃ¡ximo: ${this.date(doc.deadline)}${doc.duplicates ? ' Â· Revisar registros duplicados' : ''}`; }
    point(p) { return { x: (p[1] + 180) * 1000 / 360, y: (90 - p[0]) * 500 / 180 }; }
    paths(points) {
        // Split at the antimeridian so a route never draws across the entire map.
        let paths = [], current = [];
        for (const p of points) {
            const xy = this.point(p);
            if (current.length && Math.abs(xy.x - current[current.length - 1].x) > 500) {
                paths.push(current); current = [];
            }
            current.push(xy);
        }
        if (current.length) paths.push(current);
        return paths.map(path => path.map(p => `${p.x},${p.y}`).join(' '));
    }
    get markers() {
        return this.rows.filter(r => r.voyage_status === 'transit').map(r => ({ ...r,
            position: this.state.position === 'ais' ? r.ais_position : r.theoretical_position,
        })).filter(r => r.position).map(r => ({ ...r, ...this.point(r.position) }));
    }
}
registry.category('actions').add('step_export_control.documents', ControlPanel);
registry.category('actions').add('step_export_control.vessels', ControlPanel);
