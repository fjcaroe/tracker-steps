"""Exercise I9 on a private PostgreSQL copy, with all fixture changes rolled back."""
import uuid
from pathlib import Path
from fastapi import Response, HTTPException
from sqlalchemy import text
from sqlalchemy.orm import Session
from app.main import app
from app.db.session import engine, get_db
from app.core.security import get_current_user
from app.models.users import User, UserCostCenter
from app.models.cost_centers import CostCenter
from app.models.machines import Machine
from app.models.mobile import MobileRoute
from app.routers.passenger_services import ServiceIn, create_service, get_service, list_services


def snapshot(connection, original=None):
    quote=connection.dialect.identifier_preparer.quote
    tables=original or {name:[column for column, in connection.execute(text('SELECT column_name FROM information_schema.columns WHERE table_schema=\'public\' AND table_name=:name ORDER BY ordinal_position'),{'name':name})] for name, in connection.execute(text("SELECT tablename FROM pg_tables WHERE schemaname='public' ORDER BY tablename"))}
    values={}
    for table,columns in tables.items():
        sql='SELECT count(*), md5(COALESCE(string_agg(h,\'\' ORDER BY h),\'\')) FROM (SELECT md5(row_to_json(old)::text) h FROM (SELECT '+','.join(map(quote,columns))+' FROM '+quote(table)+') old) hashes'
        values[table]=tuple(connection.execute(text(sql)).one())
    return tables,values


def main():
    database=engine.url.database
    assert engine.dialect.name=='postgresql' and database.startswith('TRACKER_MOVIL_QA_'), 'Private copy required'
    with engine.connect() as connection:
        columns,before=snapshot(connection)
    migration=(Path(__file__).resolve().parents[1]/'migrations/20261031_passenger_services.up.sql').read_text()
    for _ in range(2):
        with engine.connect() as connection:
            connection.execution_options(isolation_level='AUTOCOMMIT').exec_driver_sql(migration)
    with engine.connect() as connection:
        assert snapshot(connection,columns)[1]==before,'Existing rows changed during additive migration'
    print('POSTGRES_PASSENGER_MIGRATION_OK idempotent=True existing_rows_preserved=True')
    with engine.connect() as connection:
        outer=connection.begin()
        factory=lambda: Session(bind=connection,join_transaction_mode='create_savepoint')
        try:
            with factory() as db:
                cc=CostCenter(name='Private I9 test');db.add(cc);db.flush()
                users=[User(username='private-i9-'+uuid.uuid4().hex,full_name='Private I9 user',password_hash='not-a-password',is_admin=(i==0),is_active=True) for i in range(3)]
                db.add_all(users);db.flush()
                ids=[u.id for u in users]
                db.add_all([UserCostCenter(user_id=uid,cost_center_id=cc.id) for uid in ids[1:]])
                machine=Machine(name='Private I9 vehicle',cost_center_id=cc.id,is_active=True,passenger_capacity=3)
                db.add(machine);db.flush()
                route=MobileRoute(name='Private I9 route',machine_id=machine.id,waypoints=[],created_by=ids[0],status='assigned')
                db.add(route);db.flush();route_id=route.id;db.commit()
            who={'id':ids[0]}
            def current_user():
                with factory() as db:
                    return db.get(User,who['id'])
            stops=[{'id':str(uuid.uuid4()),'name':label,'scheduled_at':at} for label,at in [('Origen','2026-11-02T08:00:00-03:00'),('Destino','2026-11-02T09:00:00-03:00')]]
            payload={'id':str(uuid.uuid4()),'name':'Private I9 service','route_id':str(route_id),'driver_user_id':ids[1],'stops':stops,
                     'passengers':[{'id':str(uuid.uuid4()),'name':'Private passenger '+str(i),'document':'TEST-'+str(i),'boarding_stop_id':stops[0]['id'],'alighting_stop_id':stops[1]['id'],'seat':i} for i in (1,2,3)]}
            parsed=ServiceIn.model_validate(payload)
            with factory() as db:
                result=create_service(parsed,Response(),db,current_user())
                assert len(result['passengers'])==3
                assert create_service(parsed,Response(),db,current_user())['id']==payload['id']
                who['id']=ids[1]
                assert get_service(parsed.id,Response(),db,current_user())['id']==payload['id']
                assert len(list_services(Response(),mine=True,limit=50,db=db,current=current_user())[0]['passengers'])==3
                who['id']=ids[2]
                assert list_services(Response(),mine=False,limit=50,db=db,current=current_user())==[]
                for function,expected in [(lambda:get_service(parsed.id,Response(),db,current_user()),404),
                                          (lambda:create_service(parsed,Response(),db,current_user()),403)]:
                    try:
                        function()
                    except HTTPException as exc:
                        assert exc.status_code==expected
                    else:
                        raise AssertionError('Driver isolation failed')
            print('POSTGRES_PASSENGER_SERVICE_FLOW_OK three_passengers=True driver_isolation=True')
        finally:
            outer.rollback()
    with engine.connect() as connection:
        assert not connection.execute(text("SELECT count(*) FROM users WHERE username LIKE 'private-i9-%'")).scalar()
        assert snapshot(connection,columns)[1]==before,'Fixtures changed historic rows'
    print('POSTGRES_PASSENGER_FIXTURES_ROLLED_BACK')


if __name__=='__main__':main()
