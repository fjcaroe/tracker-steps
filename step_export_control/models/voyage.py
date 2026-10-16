"""Voyage dates, explicit maritime routes and separately timestamped AIS positions."""
from datetime import datetime, timedelta, timezone
import math
import re
from odoo import api, fields, models, _
from odoo.exceptions import ValidationError


def route_position(points, fraction):
    """Interpolate by segment distance along an explicitly configured sea route."""
    def distance(a,b):
        lat1,lat2=map(math.radians,(a[0],b[0])); dlat=lat2-lat1
        dlon=math.radians((b[1]-a[1]+180)%360-180)
        return 2*math.asin(min(1,math.sqrt(math.sin(dlat/2)**2+math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2)))
    lengths=[distance(a,b) for a,b in zip(points,points[1:])]
    remaining=sum(lengths)*max(0,min(1,fraction))
    for a,b,length in zip(points,points[1:],lengths):
        if remaining <= length and length:
            ratio=remaining/length
            return [a[0]+(b[0]-a[0])*ratio,(a[1]+((b[1]-a[1]+180)%360-180)*ratio+180)%360-180]
        remaining-=length
    return list(points[-1])


class Port(models.Model):
    _inherit='l10n_cl.customs_port'
    control_coordinates_set=fields.Boolean(string='Coordenadas verificadas')
    control_latitude=fields.Float(string='Latitud',digits=(10,6))
    control_longitude=fields.Float(string='Longitud',digits=(10,6))

    @api.constrains('control_latitude','control_longitude')
    def _check_coordinates(self):
        if any(not(-90<=p.control_latitude<=90 and -180<=p.control_longitude<=180) for p in self):
            raise ValidationError(_('Las coordenadas del puerto están fuera de rango.'))


class Route(models.Model):
    _name='step.export.sea.route'
    _description='Ruta marítima teórica'
    name=fields.Char(required=True)
    company_id=fields.Many2one('res.company',required=True,default=lambda self:self.env.company)
    origin_port_id=fields.Many2one('l10n_cl.customs_port',required=True,ondelete='restrict',string='Puerto de salida')
    destination_port_id=fields.Many2one('l10n_cl.customs_port',required=True,ondelete='restrict',string='Puerto de arribo')
    waypoint_ids=fields.One2many('step.export.sea.waypoint','route_id',string='Puntos de navegación')

    def _points(self):
        self.ensure_one()
        if not(self.origin_port_id.control_coordinates_set and self.destination_port_id.control_coordinates_set):
            return []
        return [[self.origin_port_id.control_latitude,self.origin_port_id.control_longitude],
                *[[p.latitude,p.longitude] for p in self.waypoint_ids.sorted('sequence')],
                [self.destination_port_id.control_latitude,self.destination_port_id.control_longitude]]


class Waypoint(models.Model):
    _name='step.export.sea.waypoint'
    _description='Punto de una ruta marítima'
    _order='sequence,id'
    route_id=fields.Many2one('step.export.sea.route',required=True,ondelete='cascade')
    company_id=fields.Many2one(related='route_id.company_id',store=True)
    sequence=fields.Integer(default=10)
    name=fields.Char(string='Referencia')
    latitude=fields.Float(required=True,digits=(10,6))
    longitude=fields.Float(required=True,digits=(10,6))

    @api.constrains('latitude','longitude')
    def _check_coordinates(self):
        if any(not(-90<=p.latitude<=90 and -180<=p.longitude<=180) for p in self):
            raise ValidationError(_('Las coordenadas de la ruta están fuera de rango.'))


class Vessel(models.Model):
    _inherit='step.export.vessel'
    mmsi=fields.Char(string='MMSI',index=True,help='Identificador AIS de nueve dígitos. No se vincula por similitud del nombre.')
    ais_latitude=fields.Float(string='Latitud AIS',readonly=True,digits=(10,6),copy=False)
    ais_longitude=fields.Float(string='Longitud AIS',readonly=True,digits=(10,6),copy=False)
    ais_reported_at=fields.Datetime(string='Fecha de posición AIS',readonly=True,copy=False)
    ais_received_at=fields.Datetime(string='Última recepción AIS',readonly=True,copy=False)
    ais_speed=fields.Float(string='Velocidad AIS (nudos)',readonly=True,copy=False)
    ais_course=fields.Float(string='Rumbo AIS',readonly=True,copy=False)
    _sql_constraints=[('mmsi_company_unique','unique(company_id,mmsi)','El MMSI ya está registrado en esta empresa.')]

    @api.constrains('mmsi')
    def _check_mmsi(self):
        if any(v.mmsi and not re.fullmatch(r'[0-9]{9}',v.mmsi) for v in self):
            raise ValidationError(_('El MMSI debe contener exactamente nueve dígitos.'))

    def write(self, values):
        if 'mmsi' in values and any((v.mmsi or False)!=(values['mmsi'] or False) for v in self):
            # A reassigned radio identity must never display the former ship's fix.
            values={**values,**{name:False for name in ('ais_latitude','ais_longitude','ais_reported_at',
                'ais_received_at','ais_speed','ais_course')}}
        return super().write(values)

    @api.model
    def _ingest_ais_event(self, event):
        """Private collector entry point: no public RPC or name-based matching."""
        meta=event.get('MetaData') or {}
        message=(event.get('Message') or {}).get(event.get('MessageType'),{})
        if event.get('MessageType') not in ('PositionReport','StandardClassBPositionReport','ExtendedClassBPositionReport') or message.get('Valid') is False:
            return 0
        mmsi=str(meta.get('MMSI') or message.get('UserID') or '')
        if not re.fullmatch(r'[0-9]{9}',mmsi):
            return 0
        latitude=message.get('Latitude',meta.get('latitude',meta.get('Latitude')))
        longitude=message.get('Longitude',meta.get('longitude',meta.get('Longitude')))
        if not isinstance(latitude,(float,int)) or not isinstance(longitude,(float,int)) or not(-90<=latitude<=90 and -180<=longitude<=180):
            return 0
        timestamp=meta.get('time_utc')
        if not timestamp:
            return 0  # reception time alone is not proof of the position age
        try:
            normalized=str(timestamp).replace(' UTC','').replace('Z','+00:00')
            # AISStream uses Go timestamps with nanoseconds and a +0000 suffix;
            # Odoo runs Python 3.10, whose ISO parser needs microseconds/+00:00.
            normalized=re.sub(r'(\.\d{6})\d+',r'\1',normalized)
            normalized=re.sub(r'\s([+-]\d{2})(\d{2})$',r'\1:\2',normalized)
            reported=datetime.fromisoformat(normalized)
            if reported.tzinfo:
                reported=reported.astimezone(timezone.utc).replace(tzinfo=None)
        except (ValueError,TypeError):
            return 0
        now=fields.Datetime.now()
        if reported>now+timedelta(minutes=5):
            return 0
        records=self.search([('mmsi','=',mmsi)])
        for vessel in records:
            if vessel.ais_reported_at and reported<=vessel.ais_reported_at:
                continue
            vessel.write({'ais_latitude':latitude,'ais_longitude':longitude,'ais_reported_at':reported,
                'ais_received_at':now,'ais_speed':message.get('Sog',0),'ais_course':message.get('Cog',0)})
        return len(records)


class Settings(models.Model):
    _name='step.export.control.settings'
    _description='Parámetros de paneles de exportación'
    company_id=fields.Many2one('res.company',required=True,default=lambda self:self.env.company)
    near_arrival_days=fields.Integer(string='Alerta de arribo en menos de (días)',default=7,required=True)
    ais_fresh_minutes=fields.Integer(string='Vigencia máxima de posición AIS (minutos)',default=120,required=True)
    _sql_constraints=[('company_unique','unique(company_id)','Ya existen parámetros para esta empresa.')]

    @api.constrains('near_arrival_days','ais_fresh_minutes')
    def _check_positive(self):
        if any(p.near_arrival_days<1 or p.ais_fresh_minutes<1 for p in self):
            raise ValidationError(_('Los plazos deben ser positivos.'))


class Shipment(models.Model):
    _inherit='step.export.export'
    transit_time=fields.Integer(string='Transit time (días)',compute='_compute_transit',inverse='_inverse_transit')
    sea_route_id=fields.Many2one('step.export.sea.route',string='Ruta marítima teórica',check_company=True)

    @api.depends('departure_date','arrival_date')
    def _compute_transit(self):
        for s in self:
            s.transit_time=(s.arrival_date-s.departure_date).days if s.arrival_date and s.departure_date else 0

    def _inverse_transit(self):
        for s in self:
            if not s.departure_date or s.transit_time<0:
                raise ValidationError(_('Indique zarpe y un tiempo de tránsito no negativo.'))
            s.arrival_date=s.departure_date+timedelta(days=s.transit_time)

    @api.constrains('sea_route_id','origin_port_id','destination_port_id','company_id')
    def _check_route(self):
        for s in self.filtered('sea_route_id'):
            if s.sea_route_id.company_id!=s.company_id or s.origin_port_id!=s.sea_route_id.origin_port_id or s.destination_port_id!=s.sea_route_id.destination_port_id:
                raise ValidationError(_('La ruta debe corresponder a la empresa y los puertos del embarque.'))

    def _voyage_control_values(self,today):
        self.ensure_one()
        s=self
        settings=self.env['step.export.control.settings'].search([('company_id','=',s.company_id.id)],limit=1)
        threshold=settings.near_arrival_days if settings else 7
        fresh_minutes=settings.ais_fresh_minutes if settings else 120
        valid=bool(s.departure_date and s.arrival_date and s.arrival_date>=s.departure_date)
        status='unknown' if not valid else 'scheduled' if today<s.departure_date else 'arrived' if today>=s.arrival_date else 'transit'
        days=max(0,(s.arrival_date-today).days) if valid and status=='transit' else 0
        arrived=max(0,(today-s.arrival_date).days) if valid and status=='arrived' else 0
        color='ontime' if status=='arrived' else 'near' if status=='transit' and days<threshold else 'today' if status=='transit' else 'unknown'
        points=s.sea_route_id._points() if s.sea_route_id else []
        position=route_position(points,(today-s.departure_date).days/max(1,s.transit_time)) if status=='transit' and points else False
        vessel=s.vessel_id
        age=(fields.Datetime.now()-vessel.ais_reported_at).total_seconds()/60 if vessel.ais_reported_at else None
        return {'transit_time':s.transit_time,'voyage_status':status,'days_to_arrival':days,'days_arrived':arrived,
            'voyage_color':color,'near_arrival':status=='transit' and days<threshold,'route':points,
            'theoretical_position':position,'ais_position':[vessel.ais_latitude,vessel.ais_longitude] if vessel.ais_reported_at else False,
            'ais_reported_at':str(vessel.ais_reported_at or ''),'ais_fresh':age is not None and 0<=age<=fresh_minutes,
            'mmsi':vessel.mmsi or ''}
