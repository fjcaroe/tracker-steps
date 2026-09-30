export type DeviceRegistration = {
 id:string;version:number;device_id:string;imei:string;brand:string;model:string;firmware:string|null;
 protocol:string|null;tracking_approved:boolean;asset_id:string|null;asset_name:string|null;
 signal_state:string;last_received_at:string|null;phone:string|null;operator:string|null;
 plan_type:'prepaid'|'postpaid'|'iot'|'unknown';apn:string|null;responsible:string|null;
 last_recharged_on:string|null;next_recharge_on:string|null;data_expires_on:string|null;line_review_on:string|null;reminder_days:number;notes:string|null;
};
export type SimReminder = {id:string;registration_id:string;title:string;device:string;asset_name:string|null;due_on:string;days_remaining:number;responsible:string|null};
export type Configuration = {items:DeviceRegistration[];reminders:SimReminder[];today:string};
export function calendarReminder(device: DeviceRegistration) {
 const escape = (s:string)=>s.replaceAll('\\','\\\\').replaceAll('\n','\\n').replaceAll(',','\\,').replaceAll(';','\\;');
 const events = [['next_recharge_on','Recargar SIM'],['data_expires_on','Renovar datos SIM'],['line_review_on','Revisar vigencia de línea']] as const;
 const text = ['BEGIN:VCALENDAR','VERSION:2.0','PRODID:-//Steps//Tracker//ES','CALSCALE:GREGORIAN', ...events.flatMap(([key,title]) => device[key] ? [
  'BEGIN:VEVENT', 'UID:'+device.id+'-'+key+'@steps-tracker','DTSTAMP:'+new Date().toISOString().replace(/[-:]/g,'').replace(/\.\d{3}/,''),
  'DTSTART;VALUE=DATE:'+device[key]!.replaceAll('-',''),
  'SUMMARY:'+escape(title+' · '+(device.asset_name || device.model)),
  'DESCRIPTION:Revisa la SIM en Steps Tracker. Fecha ingresada por tu administrador.',
  'BEGIN:VALARM','ACTION:DISPLAY','DESCRIPTION:Recordatorio de conectividad','TRIGGER:-P'+device.reminder_days+'D','END:VALARM','END:VEVENT'] : []),'END:VCALENDAR'].join('\r\n');
 const url=URL.createObjectURL(new Blob([text],{type:'text/calendar;charset=utf-8'}));
 const link=document.createElement('a');link.href=url;link.download='steps-recordatorios-sim.ics';link.click();setTimeout(()=>URL.revokeObjectURL(url),1000);
}
