import type {TrailGap} from './fleetTrail';
export type ReceiverObservation = {
 at:string; contact_at:string; fix_at:string|null; assignment_id:string;
 state:'gps'|'no_gps'|'contact_without_fix'|'no_contact'|'invalid_message'; pending:number;
};
export function gapEvidence(gap:TrailGap, observations:ReceiverObservation[]) {
 const start=Date.parse(gap.before.recorded_at),end=Date.parse(gap.after.recorded_at);
 const contacts=observations.filter(row=>row.assignment_id===gap.before.assignment_id &&
   Date.parse(row.contact_at)>start && Date.parse(row.contact_at)<end && row.state!=='no_contact');
 if(contacts.some(row=>row.state==='no_gps'))return 'Hubo comunicación. El equipo informó falta de posición GPS válida.';
 if(contacts.length)return 'Hubo comunicación del equipo durante este intervalo. La ruta intermedia sigue sin posiciones comprobadas.';
 if(gap.after.recovered)return 'La primera posición posterior llegó con atraso. No hay diagnóstico de comunicación suficiente para el intervalo.';
 return 'Comunicación durante el intervalo sin comprobar. No hay evidencia suficiente para atribuirlo a cobertura o señal GPS.';
}
