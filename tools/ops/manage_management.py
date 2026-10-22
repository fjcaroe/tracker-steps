"""Test and promote the same agricultural management package without downgrades.

Private overlays avoid replacing addon roots shared with production. A passed
clone, unchanged source/config baseline, lease and backup are required to promote.
"""
import argparse
import ast
import configparser
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import socket
import subprocess
import tarfile
import urllib.request

HERE = Path(__file__).resolve().parent
MODULES = ('step_management_costs', 'step_management_costs_agriculture', 'step_management_costs_machinery',
           'step_management_costs_tracker', 'step_agriculture_catalogs', 'step_management_costs_producers')
BUSINESS = ('step_management_operational_budget', 'step_management_budget_line', 'step_management_budget_center',
            'step_management_estimation', 'step_management_estimation_line', 'step_management_historical_cost',
            'step_management_plan', 'step_management_production_order', 'step_management_crop_program')
SETTINGS = False
PRODUCERS = False
PACKING_INITIAL_MIGRATION = False
EXPORT_SALE_ADDITION = False
EXPORT_PORT_ADDITIONS = False
TICKET_REVISION = ''
SALE_FORMAT_INITIAL = False
CLIENT_REVISION_INITIAL = False
CONTRACT_REPORT_INITIAL = False
FRUIT_REPORTS_INITIAL = False
ESTIMATE_REVISION_INITIAL = False
DAILY_ESTIMATE_INITIAL = False
SHIPMENT_PROVISION_INITIAL = False
BUDGET_DESIGN_INITIAL = False
DOCUMENT_DESIGN_INITIAL = False
SHIPPING_DESIGN_INITIAL = False
SAG_PROTOTYPE_INITIAL = False
TRACEABILITY_INITIAL = False
PROMOTION_COLUMNS = {}
AGRICULTURE_SOURCE = None
AGRICULTURE_COLUMNS = None


def run(*command, **kwargs):
    return subprocess.run(command, check=True, **kwargs)


def query(database, sql):
    # stdin also supports the large preservation query without argv limits.
    return subprocess.run(['sudo', '-u', 'postgres', 'psql', '-v', 'ON_ERROR_STOP=1', '-d', database, '-At'],
                          input=sql, text=True, check=True, stdout=subprocess.PIPE).stdout.strip()


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def tree_hash(path):
    digestor = hashlib.sha256()
    for file in sorted(path.rglob('*')):
        if file.is_file() and file.suffix in {'.py', '.xml', '.csv', '.js', '.scss', '.css'} and '__pycache__' not in file.parts:
            digestor.update(str(file.relative_to(path)).encode())
            digestor.update(file.read_bytes().replace(b'\r\n', b'\n'))
    return digestor.hexdigest()


def agriculture_migrate(action, database, source):
    return run('/usr/bin/python3.10', str(source / 'migrate_schema.py'), action, database)


def agriculture_snapshot(database):
    command = ['/usr/bin/python3.10', str(AGRICULTURE_SOURCE / 'migrate_schema.py'), 'snapshot', database]
    if AGRICULTURE_COLUMNS.exists():
        command += ['--baseline', str(AGRICULTURE_COLUMNS)]
    result = run(*command, text=True, capture_output=True)
    proof = json.loads(result.stdout)
    if not AGRICULTURE_COLUMNS.exists():
        AGRICULTURE_COLUMNS.write_text(json.dumps(proof))
    return proof


def snapshot(database):
    if TICKET_REVISION == "agriculture-records":
        return agriculture_snapshot(database)
    existing = set(query(database, "SELECT tablename FROM pg_tables WHERE schemaname='public'").splitlines())
    current_columns = {}
    if TICKET_REVISION in ('sag-traceability', 'dispatch-improvements', 'export-dashboard', 'agro-analytics', 'harvest-planning', 'harvest-operations', 'agriculture-records'):
        current_columns = json.loads(query(database, "SELECT json_object_agg(table_name,cols) FROM (SELECT table_name,json_agg(column_name) cols FROM information_schema.columns WHERE table_schema='public' GROUP BY table_name) s"))
    statements = []
    for table in BUSINESS:
        assert re.fullmatch('[a-z_][a-z0-9_]*', table), 'Invalid preservation table'
        if table in existing:
            row = 'jsonb_strip_nulls(to_jsonb(t))' if PRODUCERS else 'to_jsonb(t)' if SETTINGS else "(to_jsonb(t)-ARRAY['center_id','cost_center_id','write_date'])"
            if TICKET_REVISION in ('sag-traceability', 'dispatch-improvements', 'export-dashboard', 'agro-analytics', 'harvest-planning', 'harvest-operations', 'agriculture-records'):
                added = sorted(set(current_columns[table]) - set(PROMOTION_COLUMNS[table]))
                if added: row = "(to_jsonb(t)-ARRAY[%s])" % ','.join("'%s'" % c for c in added)
            if TICKET_REVISION == 'traceability' and TRACEABILITY_INITIAL and table == 'step_export_export':
                row = "(to_jsonb(t)-'arrival_quality_id')"
            if TICKET_REVISION == 'sag-lot':
                additions = {
                    'step_packing_inspection': ['sag_species_id','sag_packing_id','sag_service_id','sag_fruit_type','sag_receiver_id','sag_instruction_id','sag_multi_ot','sag_scan','sag_dispatch_sheet_reference','sag_export_sequence','sag_dispatch_date','sag_repack_operation','sag_manual_dispatch','sag_product_condition'],
                    'res_partner':['step_sag_plant_number'], 'res_country':['step_sag_code'],
                    'res_city':['step_sag_province_name'], 'step_fundo':['step_sag_city_id'],
                    'stock_quant_package':['step_sag_folio'],
                }
                columns = additions.get(table, [])
                if columns: row = "(to_jsonb(t)-ARRAY[%s])" % ','.join("'%s'" % c for c in columns)
            if TICKET_REVISION == 'sag-prototype' and SAG_PROTOTYPE_INITIAL and table == 'step_packing_inspection':
                columns = ['sag_prototype', 'sag_phase', 'sag_country_id', 'sag_counterpart_id', 'sag_requirements', 'sag_request_reference', 'sag_scheduled_at', 'sag_sif_reference', 'sag_initial', 'sag_documents', 'sag_traceability', 'sag_presentation', 'sag_packaging', 'sag_sampling_basis', 'sag_sample_count', 'sag_sample_findings', 'sag_laboratory_reference', 'sag_laboratory_received', 'sag_treatment', 'sag_treatment_detail']
                row = "(to_jsonb(t)-ARRAY[%s])" % ','.join("'%s'" % c for c in columns)
            if TICKET_REVISION == 'dispatch-design':
                additions={'step_export_dispatch_order':['shipment_id','date','pallets_per_truck'],
                    'step_dispatch_guide':['dispatch_instruction_id','scan_code']}
                columns=additions.get(table,[])
                if columns:row="(to_jsonb(t)-ARRAY[%s])" % ','.join("'%s'" % c for c in columns)
            if TICKET_REVISION == 'export-control':
                # Only fields introduced by this addon are excluded; every
                # pre-existing value, document, master and relation is preserved.
                additions = {
                    'step_export_export':['sea_route_id'],
                    'step_export_shipping_document':['document_created_on','sent_on','received_on','manual_reference','sent_message_id'],
                    'step_export_vessel':['mmsi','ais_latitude','ais_longitude','ais_reported_at','ais_received_at','ais_speed','ais_course'],
                    'l10n_cl_customs_port':['control_coordinates_set','control_latitude','control_longitude'],
                }
                columns=additions.get(table,[])
                if columns:
                    row="(to_jsonb(t)-ARRAY[%s])" % ','.join("'%s'" % column for column in columns)
            if TICKET_REVISION == 'producer-change' and table in ('stock_quant_package','step_packing_process_type'):
                row = "jsonb_strip_nulls(to_jsonb(t)-'changes_commercial_producer')"
            if TICKET_REVISION == 'purchase-mode' and table in ('step_producer_purchase_contract','step_export_estimate'):
                row = "jsonb_strip_nulls(to_jsonb(t))"
            if TICKET_REVISION == 'contract-report' and CONTRACT_REPORT_INITIAL and table == 'step_producer_purchase_contract':
                row = "(to_jsonb(t)-'season_id')"
            if TICKET_REVISION == 'fruit-categories':
                relations = {'stock_picking': {'fruit_category_id':'step_packing_fruit_category','fruit_class_id':'step_packing_fruit_class'},
                    'step_packing_picking_tag_line': {'category_id':'step_packing_fruit_category'},
                    'step_producer_purchase_contract_product': {'category_id':'step_packing_fruit_category'}}
                for column, source in relations.get(table, {}).items():
                    old_fk = query(database, "SELECT 1 FROM pg_constraint c JOIN pg_class t ON t.oid=c.conrelid JOIN pg_class r ON r.oid=c.confrelid JOIN pg_attribute a ON a.attrelid=t.oid AND a.attnum=ANY(c.conkey) WHERE c.contype='f' AND t.relname='%s' AND r.relname='%s' AND a.attname='%s'" % (table,source,column))
                    if old_fk and source == 'step_packing_fruit_category':
                        mapped = "COALESCE((SELECT to_jsonb(cat.id) FROM step_management_fruit_category cat JOIN step_packing_fruit_category old ON old.id=cat.step_contract_category_id WHERE old.id=t.%s AND cat.company_id IS NOT DISTINCT FROM old.company_id),to_jsonb(t.%s),'null'::jsonb)" % (column,column)
                        row = "jsonb_set(%s,'{%s}',%s)" % (row,column,mapped)
            if TICKET_REVISION == 'estimate-revision':
                additions = {'stock_package_type':['fruit_package_group','pallets_per_aircraft'],
                             'step_export_estimate_line':['bin_qty','process_pallet_qty','export_box_qty','export_pallet_qty']}
                if table == 'stock_package_type' and not ESTIMATE_REVISION_INITIAL:
                    additions.pop('stock_package_type')
                if table in additions:
                    row = "(to_jsonb(t)-ARRAY[%s])" % ','.join("'%s'" % name for name in additions[table])
            if TICKET_REVISION == 'budget-design' and BUDGET_DESIGN_INITIAL:
                additions = {'step_management_budget_template':['season_id','budget_version_id','species_id','variety_id','base_plants','base_kg'],
                    'step_management_budget_template_line':['origin_id','activity_id','calculation_uom_id','yield_quantity','fruit_category_id','calculation_quantity','calculation_amount','calculation_unit_price','machinery_budget_id'],
                    'step_management_budget_group':['origin_id','phenology_id'],
                    'step_management_operational_budget':['season_id','budget_version_id'],
                    'step_management_budget_line':['origin_id','activity_id','calculation_uom_id','expected_kg'],
                    'step_management_budget_month':['period_date'], 'step_management_budget_import':['season_master_id','version_master_id','target_budget_type']}
                if table in additions:
                    row = "(to_jsonb(t)-ARRAY[%s])" % ','.join("'%s'" % name for name in additions[table])
            if TICKET_REVISION == 'document-design' and DOCUMENT_DESIGN_INITIAL:
                additions = {'res_partner':['step_packing_csp'], 'stock_quant_package':['step_export_gross_kg','step_export_thermos'],
                    'sale_order':['step_price_kg','step_box_pricing'], 'sale_order_line':['step_document_kg_per_box']}
                if table in additions:
                    row = "(to_jsonb(t)-ARRAY[%s])" % ','.join("'%s'" % name for name in additions[table])
            if TICKET_REVISION == 'shipping-design' and SHIPPING_DESIGN_INITIAL:
                additions = {'res_company':['export_folio_mode','export_folio_initial'], 'sale_order':['export_folio'],
                    'account_move':['export_folio_sale_order_id'], 'step_export_shipment_line':['quality_id'],
                    'step_export_export':['freight_payment','booking','folio_sale_order_id','temperature','ventilation',
                        'controlled_atmosphere','filters','thermograph_qty','port_transport_id','packing_partner_id',
                        'consolidation','staking','logistics_operator_id','loading_datetime','counterpart_id',
                        'container_reference','container_qty','gross_kg']}
                if table in additions:
                    row = "(to_jsonb(t)-ARRAY[%s])" % ','.join("'%s'" % name for name in additions[table])
            if TICKET_REVISION == 'shipment-provision' and SHIPMENT_PROVISION_INITIAL:
                additions = {'step_export_export':['provision_analytic_account_id'], 'account_move':['shipment_provision_id']}
                if table in additions:
                    row = "(to_jsonb(t)-ARRAY[%s])" % ','.join("'%s'" % name for name in additions[table])
            if TICKET_REVISION == 'daily-estimate' and DAILY_ESTIMATE_INITIAL:
                additions = {'step_export_estimate':['fruit_type'], 'step_export_estimate_line':['market_id']}
                if table in additions:
                    row = "(to_jsonb(t)-ARRAY[%s])" % ','.join("'%s'" % name for name in additions[table])
            if TICKET_REVISION == 'fruit-reports' and FRUIT_REPORTS_INITIAL and table == 'step_especie':
                row = "(to_jsonb(t)-ARRAY['sag_code','base_boxes_per_pallet'])"
            if TICKET_REVISION == 'sale-format':
                row = 'to_jsonb(t)'
                additions = {'sale_order_line': ['step_export_kg', 'step_export_boxes', 'step_export_charge'],
                             'res_company': ['step_export_sale_format', 'step_export_bank_id'], 'res_bank': ['step_aba_routing']}
                if SALE_FORMAT_INITIAL and table in additions:
                    row = "(to_jsonb(t)-ARRAY[%s])" % ','.join("'%s'" % name for name in additions[table])
            if TICKET_REVISION == 'client-revision':
                row = 'to_jsonb(t)'
                additions = {'res_partner': ['step_export_carrier','step_export_consignee','step_export_notify','step_export_forwarder','step_export_customs_agent'],
                    'step_export_sales_program': ['transport_type'],
                    'step_export_sales_program_line': ['week_end','company_id','species_id','season_id','transport_type','program_state'],
                    'sale_order': ['step_export_sale_mode_id']}
                if CLIENT_REVISION_INITIAL and table in additions:
                    row = "(to_jsonb(t)-ARRAY[%s])" % ','.join("'%s'" % name for name in additions[table])
            if MODULES == ('step_packing_operations',) and PACKING_INITIAL_MIGRATION:
                # Only the versioned migration's added fields are excluded;
                # preserve every pre-existing row, ID, quantity and value.
                additions = {
                    'step_packing_production': ['raw_product_id', 'instruction_id', 'sale_order_id'],
                    'stock_quant_package': ['step_packing_production_id', 'step_packaging_id', 'step_packing_line_id'],
                    'step_fruit_package_line': ['source_package_id'],
                    'step_export_stock_reservation': ['destination_country_id', 'sales_program_id', 'species_id', 'variety_id', 'producer_id', 'caliber_id', 'category_id', 'tag_kind'],
                    'step_packing_repack': ['date', 'process_type_id', 'packing_partner_id', 'packing_line_id'],
                }
                if table in additions:
                    row = "(to_jsonb(t)-ARRAY[%s])" % ','.join("'%s'" % name for name in additions[table])
            if MODULES == ('step_export',) and EXPORT_SALE_ADDITION and table == 'sale_order':
                row = "(to_jsonb(t)-'step_export_sale')"
            if MODULES == ('step_export',) and EXPORT_PORT_ADDITIONS and table == 'step_export_export':
                row = "(to_jsonb(t)-ARRAY['origin_port_id','destination_port_id'])"
            condition = " WHERE key <> 'web.base.url'" if (SETTINGS or PRODUCERS) and table == 'ir_config_parameter' else ''
            statements.append("SELECT '%s',json_build_object('count',count(*),'digest',md5(COALESCE(string_agg(%s::text,'|' ORDER BY %s::text),'')))::text FROM %s t%s" % (table, row, row, table, condition))
    # One SQL statement sees a consistent MVCC snapshot across every table.
    # It preserves the same row normalization and hashes as the former loop.
    return dict(line.split('|', 1) for line in query(database, ' UNION ALL '.join(statements)).splitlines()) if statements else {}


def extract(release, target):
    with tarfile.open(release) as archive:
        proof = json.loads(archive.extractfile('release.json').read())
        assert re.fullmatch('[0-9a-f]{40}', proof['commit'])
        assert set(proof['versions']) == set(MODULES)
        found = set()
        for member in archive.getmembers():
            path = Path(member.name)
            assert member.isfile() and not path.is_absolute() and '..' not in path.parts
            assert member.name == 'release.json' or path.parts[0] in MODULES
            assert member.name not in found
            found.add(member.name)
            if member.name != 'release.json':
                assert hashlib.sha256(archive.extractfile(member).read()).hexdigest() == proof['files'][member.name]
        assert found == set(proof['files']) | {'release.json'}
        archive.extractall(target)
    return proof


def errors(text, allowed_missing=('steps_api',)):
    found = []
    marker = 'Some modules are not loaded, some dependencies or manifest may be missing: '
    for line in text.splitlines():
        if ' ERROR ' not in line and ' CRITICAL ' not in line:
            continue
        if marker in line:
            missing = ast.literal_eval(line.split(marker, 1)[1].strip())
            if set(missing) <= set(allowed_missing):
                continue
        found.append(line)
    return found


def normalize_approved_account(base, options, database, args, commit):
    header = ('APPROVED_USER_ID=' + repr(args.normalize_user_id) + '\nEXPECTED_USER_LOGIN=' + repr(args.expected_user_login)
        + '\nEXPECTED_DATABASE=' + repr(database) + '\nNORMALIZE_COMMIT=' + repr(commit) + '\n')
    result = run(*(base[:4] + [base[4], 'shell'] + options + ['-d', database, '--log-level=error']),
        input=header + (HERE/'normalize_email_account.py').read_text(), text=True, capture_output=True)
    expected = 'EMAIL_ACCOUNT_NORMALIZED_OK ' if commit else 'EMAIL_ACCOUNT_NORMALIZATION_TESTED_OK '
    assert expected in result.stdout
    print('\n'.join(line for line in result.stdout.splitlines() if line.startswith(expected)), flush=True)


def main():
    global PROMOTION_COLUMNS, TRACEABILITY_INITIAL, SAG_PROTOTYPE_INITIAL, DOCUMENT_DESIGN_INITIAL, SHIPPING_DESIGN_INITIAL, BUDGET_DESIGN_INITIAL, SHIPMENT_PROVISION_INITIAL, DAILY_ESTIMATE_INITIAL, ESTIMATE_REVISION_INITIAL, FRUIT_REPORTS_INITIAL, CONTRACT_REPORT_INITIAL, MODULES, BUSINESS, SETTINGS, PRODUCERS, PACKING_INITIAL_MIGRATION, EXPORT_SALE_ADDITION, EXPORT_PORT_ADDITIONS, TICKET_REVISION, SALE_FORMAT_INITIAL, CLIENT_REVISION_INITIAL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('qa', 'compatibility', 'certify', 'deploy', 'verify'))
    parser.add_argument('environment', choices=('development', 'cerro', 'steps', 'sys'))
    parser.add_argument('release', type=Path)
    parser.add_argument('run_id')
    parser.add_argument('--kind', choices=('management', 'export', 'homepage', 'settings', 'producers', 'fruit-reception', 'packing', 'payroll-fixes', 'previred-fix', 'tarja', 'sale-format', 'client-revision', 'estimate-report', 'contract-report', 'fruit-reports', 'estimate-revision', 'fruit-categories', 'daily-estimate', 'shipment-provision', 'budget-design', 'shipping-design', 'document-design', 'purchase-mode', 'producer-change', 'balance-analytic', 'export-control', 'email-login', 'dispatch-improvements', 'export-dashboard', 'agro-analytics', 'harvest-planning', 'harvest-operations', 'agriculture-records', 'dispatch-design', 'sag-prototype', 'sag-lot', 'traceability', 'sag-traceability'), default='management')
    parser.add_argument('--normalize-user-id', type=int)
    parser.add_argument('--expected-user-login')
    parser.add_argument('--approval-dir', type=Path)
    parser.add_argument('--development-proof', type=Path)
    args = parser.parse_args()
    if args.normalize_user_id is not None or args.expected_user_login is not None:
        assert args.normalize_user_id and args.expected_user_login and '@' in args.expected_user_login
        assert args.kind == 'email-login' and args.environment == 'cerro' and args.action in ('deploy','compatibility')

    SETTINGS = args.kind in ('settings', 'fruit-reception', 'packing')
    PRODUCERS = args.kind == 'producers'
    if PRODUCERS:
        assert args.environment == 'development', 'Producer revisions are QA-only'
        MODULES = ('step_producers', 'step_producer_fruit_flow', 'step_export', 'step_producers_integrations')
        BUSINESS = tuple(query('LAB_TAREAS', "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'step_%' OR tablename LIKE 'account_%' OR tablename LIKE 'stock_%' OR tablename LIKE 'product_%' OR tablename IN ('res_company','res_partner','res_partner_bank','mrp_bom','mrp_bom_line','ir_config_parameter')) ORDER BY tablename").splitlines())
    if SETTINGS:
        assert args.environment == 'development', 'Settings repair is QA-only'
        MODULES = ('step_packing_operations',) if args.kind == 'packing' else ('step_inventory_packing',) if args.kind == 'fruit-reception' else ('step_account_treasury_batch', 'step_dispatch_guide')
        BUSINESS = tuple(query('LAB_TAREAS', "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'step_%' OR tablename LIKE 'account_%' OR tablename LIKE 'stock_%' OR tablename LIKE 'product_%' OR tablename IN ('res_company','res_partner','res_partner_bank','fleet_vehicle','ir_config_parameter')) ORDER BY tablename").splitlines())
    assert args.environment != 'steps' or args.kind == 'homepage'
    if args.kind == 'homepage':
        MODULES = ('step_demo_homepage',)
        BUSINESS = ('account_move', 'account_move_line')
    if args.kind == 'export':
        MODULES = ('step_export',)
        BUSINESS = tuple(query('LAB_TAREAS', "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'step_%' OR tablename LIKE 'account_%' OR tablename LIKE 'stock_%' OR tablename LIKE 'product_%' OR tablename IN ('res_company','res_partner','sale_order','sale_order_line')) ORDER BY tablename").splitlines())
    if args.kind == 'sale-format':
        TICKET_REVISION = args.kind
        assert args.environment in ('development', 'cerro')
        MODULES = ('step_sale_export_report',)
        registry = json.loads((HERE / 'environments.json').read_text())
        target_db = registry['environments'][args.environment]['database']
        SALE_FORMAT_INITIAL = not query(target_db, "SELECT 1 FROM ir_module_module WHERE name='step_sale_export_report' AND state='installed'")
        assert query(target_db, "SELECT count(*) FROM ir_module_module WHERE name IN ('step_export','sale_stock') AND state='installed'") == '2'
        BUSINESS = tuple(query(target_db, "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'step_%' OR tablename LIKE 'account_%' OR tablename LIKE 'stock_%' OR tablename LIKE 'product_%' OR tablename LIKE 'sale_%' OR tablename LIKE 'hr_%' OR tablename IN ('res_company','res_partner','res_partner_bank','res_bank','l10n_cl_customs_port')) ORDER BY tablename").splitlines())
    if args.kind == 'client-revision':
        TICKET_REVISION = args.kind
        assert args.environment in ('development', 'cerro')
        MODULES = ('step_sale_export_report', 'step_export_client_revision')
        registry = json.loads((HERE / 'environments.json').read_text())
        target_db = registry['environments'][args.environment]['database']
        CLIENT_REVISION_INITIAL = not query(target_db, "SELECT 1 FROM ir_module_module WHERE name='step_export_client_revision' AND state='installed'")
        required = ('step_export', 'step_packing_operations', 'step_inventory_fruit_tag', 'step_sale_export_report', 'web_gantt')
        assert int(query(target_db, "SELECT count(*) FROM ir_module_module WHERE state='installed' AND name IN (%s)" % ','.join("'%s'" % n for n in required))) == len(required)
        BUSINESS = tuple(query(target_db, "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'step_%' OR tablename LIKE 'account_%' OR tablename LIKE 'stock_%' OR tablename LIKE 'product_%' OR tablename LIKE 'sale_%' OR tablename LIKE 'hr_%' OR tablename IN ('res_company','res_partner','res_partner_bank','res_bank','l10n_cl_customs_port')) ORDER BY tablename").splitlines())
    if args.kind in ('estimate-report','contract-report', 'fruit-reports', 'estimate-revision', 'fruit-categories', 'daily-estimate', 'shipment-provision', 'budget-design', 'shipping-design', 'document-design', 'purchase-mode', 'producer-change', 'balance-analytic', 'export-control', 'email-login', 'dispatch-improvements', 'export-dashboard', 'agro-analytics', 'harvest-planning', 'harvest-operations', 'agriculture-records', 'dispatch-design', 'sag-prototype', 'sag-lot', 'traceability', 'sag-traceability'):
        TICKET_REVISION = args.kind
        if args.kind in ('sag-prototype', 'sag-lot', 'traceability'):
            assert args.environment == 'development', 'T92 solo autoriza Desarrollo'
        SETTINGS = True
        assert args.environment in ('development', 'cerro')
        MODULES = ({'sag-traceability':('step_inventory_packing','step_packing_operations','step_packing_dispatch','step_packing_sag','step_export_traceability'),'traceability':('step_export_traceability',),'sag-lot':('step_packing_operations','step_packing_dispatch','step_packing_sag'),'sag-prototype':('step_packing_sag',),'email-login':('step_auth_email_casefold',),'dispatch-improvements':('step_packing_dispatch_improvements',),'agriculture-records':('step_agriculture_records','step_bpa_irrigation','step_bpa_inventory','step_qa','step_agro_traceability','step_budget_design','step_cosecha','step_cosecha_operations'),'harvest-operations':('step_cosecha_operations',),'harvest-planning':('step_cosecha_planning',),'agro-analytics':('step_agro_analytics',),'export-dashboard':('step_export_dashboard',),'dispatch-design':('step_packing_dispatch',),'export-control':('step_export_control',),'balance-analytic':('step_account_balance_analytic',),'producer-change':('step_packing_producer_change',),'purchase-mode':('step_producer_purchase_mode',),'estimate-report':('step_producer_estimate_report',),'contract-report':('step_producer_contract_report',),'fruit-reports':('step_producer_fruit_reports',),'estimate-revision':('step_producer_estimate_revision',),'fruit-categories':('step_fruit_category_unification',),'daily-estimate':('step_producer_daily_estimate',),'shipment-provision':('step_export_shipment_provision',),'budget-design':('step_budget_design',),'shipping-design':('step_export_shipping_design',),'document-design':('step_export_document_revision',)})[args.kind]
        registry = json.loads((HERE / 'environments.json').read_text())
        target_db = registry['environments'][args.environment]['database']
        SAG_PROTOTYPE_INITIAL = args.kind == 'sag-prototype' and not query(target_db, "SELECT 1 FROM ir_module_module WHERE name='step_packing_sag' AND state='installed'")
        TRACEABILITY_INITIAL = args.kind == 'traceability' and not query(target_db, "SELECT 1 FROM ir_module_module WHERE name='step_export_traceability' AND state='installed'")
        assert query(target_db, "SELECT count(*) FROM ir_module_module WHERE name IN ('step_producers','web_gantt','step_agriculture_catalogs') AND state='installed'") == '3'
        DOCUMENT_DESIGN_INITIAL = args.kind == 'document-design' and not query(target_db, "SELECT 1 FROM ir_module_module WHERE name='step_export_document_revision' AND state='installed'")
        SHIPPING_DESIGN_INITIAL = args.kind == 'shipping-design' and not query(target_db, "SELECT 1 FROM ir_module_module WHERE name='step_export_shipping_design' AND state='installed'")
        BUDGET_DESIGN_INITIAL = args.kind == 'budget-design' and not query(target_db, "SELECT 1 FROM ir_module_module WHERE name='step_budget_design' AND state='installed'")
        if args.kind == 'budget-design':
            assert args.environment == 'development', 'T77 is authorized only for Development'
        SHIPMENT_PROVISION_INITIAL = args.kind == 'shipment-provision' and not query(target_db, "SELECT 1 FROM ir_module_module WHERE name='step_export_shipment_provision' AND state='installed'")
        DAILY_ESTIMATE_INITIAL = args.kind == 'daily-estimate' and not query(target_db, "SELECT 1 FROM ir_module_module WHERE name='step_producer_daily_estimate' AND state='installed'")
        CONTRACT_REPORT_INITIAL = args.kind == 'contract-report' and not query(target_db, "SELECT 1 FROM ir_module_module WHERE name='step_producer_contract_report' AND state='installed'")
        ESTIMATE_REVISION_INITIAL = args.kind == 'estimate-revision' and not query(target_db, "SELECT 1 FROM ir_module_module WHERE name='step_producer_estimate_revision' AND state='installed'")
        if args.kind == 'estimate-revision':
            assert query(target_db, "SELECT count(*) FROM ir_module_module WHERE name IN ('step_producer_fruit_reports','step_producer_estimate_report') AND state='installed'") == '2'
        FRUIT_REPORTS_INITIAL = args.kind == 'fruit-reports' and not query(target_db, "SELECT 1 FROM ir_module_module WHERE name='step_producer_fruit_reports' AND state='installed'")
        if args.kind == 'fruit-reports':
            assert query(target_db, "SELECT count(*) FROM ir_module_module WHERE name IN ('step_producer_fruit_flow','step_export_client_revision') AND state='installed'") == '2'
        BUSINESS = tuple(query(target_db, "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'step_%' OR tablename LIKE 'account_%' OR tablename LIKE 'stock_%' OR tablename LIKE 'product_%' OR tablename LIKE 'sale_%' OR tablename LIKE 'hr_%' OR tablename IN ('res_company','res_partner','res_partner_bank','res_bank','l10n_cl_customs_port')) ORDER BY tablename").splitlines())
        if args.kind in ('sag-lot', 'sag-traceability'):
            BUSINESS = tuple(sorted(set(BUSINESS) | {'res_country', 'res_city'}))
    if args.kind in ('payroll-fixes', 'previred-fix', 'tarja'):
        TICKET_REVISION = args.kind
        assert args.environment in (('development', 'sys') if args.kind in ('payroll-fixes', 'previred-fix') else ('development',)), 'Ticket destination outside approved scope'
        SETTINGS = True
        MODULES = ('step_hr_previred', 'step_hr_previred_simpledigital', 'step_hr_contract_lifecycle_simpledigital') if args.kind == 'payroll-fixes' else ('step_inventory_packing', 'step_packing_operations')
        if args.kind == 'previred-fix':
            MODULES = ('step_hr_previred',)
        registry = json.loads((HERE / 'environments.json').read_text())
        target_db = registry['environments'][args.environment]['database']
        BUSINESS = tuple(query(target_db, "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'step_%' OR tablename LIKE 'hr_%' OR tablename LIKE 'account_%' OR tablename LIKE 'stock_%' OR tablename LIKE 'product_%' OR tablename LIKE 'sale_%' OR tablename LIKE 'purchase_%' OR tablename IN ('res_company','res_partner','res_partner_bank','ir_config_parameter')) ORDER BY tablename").splitlines())
    assert args.environment != 'sys' or args.kind in ('payroll-fixes', 'previred-fix')
    assert os.geteuid() == 0 and re.fullmatch('[a-z0-9_]{1,24}', args.run_id)
    registry = json.loads((HERE / 'environments.json').read_text())
    assert args.action != 'qa' or args.environment == registry['policy']['qa'], 'Only Desarrollo is QA'
    assert args.action != 'compatibility' or args.environment in registry['policy']['production']
    target = registry['environments'][args.environment]
    database, service = target['database'], target['service']
    allowed_missing = ['steps_api']
    conf = Path(target['config'])
    cfg = configparser.ConfigParser(interpolation=None)
    cfg.read(conf)
    opts = cfg['options']
    assert opts.get('db_name') == database
    if args.kind == 'homepage' and args.environment == 'steps':
        legacy = query(database, "SELECT latest_version FROM ir_module_module WHERE name='steps_transport' AND state='installed'")
        paths = [Path(item.strip()) for item in opts['addons_path'].split(',')]
        if legacy == '18.0.1.5' and not any((item / 'steps_transport' / '__manifest__.py').exists() for item in paths):
            # Audited pre-existing missing addon in Steps, unrelated to website.
            # The target clone must retain the exact same legacy registration.
            allowed_missing.append('steps_transport')
    user = subprocess.check_output(['systemctl', 'show', '--value', '--property=User', service], text=True).strip()
    identity = pwd.getpwnam(user)
    stage = Path('/opt/steps-validation') / ('management_' + args.environment + '_' + args.run_id)
    stage.mkdir(parents=True, exist_ok=True, mode=0o750)
    os.chown(stage, identity.pw_uid, identity.pw_gid)
    staged = stage / 'addons'
    staged.mkdir(exist_ok=True)
    proof = extract(args.release, staged)
    if args.kind == 'agriculture-records':
        assert args.environment == 'development', 'T103 is not a production authorization'
        global AGRICULTURE_SOURCE, AGRICULTURE_COLUMNS
        AGRICULTURE_SOURCE = staged / 'step_agriculture_records'
        AGRICULTURE_COLUMNS = stage / 'agriculture-columns.json'
        declarations = ast.parse((AGRICULTURE_SOURCE / 'schema.py').read_text())
        policy = next(ast.literal_eval(node.value) for node in declarations.body
                      if isinstance(node, ast.Assign) and any(isinstance(target, ast.Name) and
                      target.id == 'TAG_STATE_POLICY' for target in node.targets))
        assert args.action != 'deploy' or policy is not None, 'Resolve the human tag-state decision before publishing T103'
    for path in [staged, *staged.rglob('*')]:
        os.chown(path, identity.pw_uid, identity.pw_gid)
    release_sha = digest(args.release)
    if args.kind == 'sag-traceability':
        from approved_sag_traceability import verify_content, verify_authorization
        verify_content(proof)
        if args.environment == 'cerro':
            verify_authorization(args.approval_dir,args.development_proof,proof,release_sha)
        assert args.environment in ('development','cerro')
        PROMOTION_COLUMNS = json.loads(query(database, "SELECT json_object_agg(table_name,cols) FROM (SELECT table_name,json_agg(column_name) cols FROM information_schema.columns WHERE table_schema='public' GROUP BY table_name) s"))
    if args.kind == 'email-login':
        BUSINESS = tuple(sorted(set(BUSINESS) | set(query(database, "SELECT tablename FROM pg_tables WHERE schemaname='public' AND (tablename LIKE 'res_users%' OR tablename IN ('res_groups_users_rel','res_company_users_rel'))").splitlines())))
    if args.kind in ('dispatch-improvements', 'export-dashboard', 'agro-analytics', 'harvest-planning', 'harvest-operations', 'agriculture-records'):
        PROMOTION_COLUMNS = json.loads(query(database, "SELECT json_object_agg(table_name,cols) FROM (SELECT table_name,json_agg(column_name) cols FROM information_schema.columns WHERE table_schema='public' GROUP BY table_name) s"))
        if args.kind == 'harvest-operations':
            assert query(database, "SELECT count(*) FROM ir_module_module WHERE name IN ('step_cosecha_planning','step_packing') AND state='installed'") == '2'
        if args.kind == 'harvest-planning':
            assert query(database, "SELECT count(*) FROM ir_module_module WHERE name IN ('step_cosecha','step_management_costs','step_export') AND state='installed'") == '3', 'Harvest planning parents must already be installed'
        if args.kind == 'agro-analytics':
            assert query(database, "SELECT count(*) FROM ir_module_module WHERE name IN ('step_export_dashboard','step_packing_operations','step_inventory_packing','step_export_shipping_design') AND state='installed'") == '4', 'Analytics parents must already be installed'
        if args.kind == 'dispatch-improvements':
            assert query(database, "SELECT count(*) FROM ir_module_module WHERE name IN ('step_packing_dispatch','step_export_client_revision') AND state='installed'") == '2'
    installed = json.loads(query(database, "SELECT COALESCE(json_object_agg(name,latest_version),'{}'::json) FROM ir_module_module WHERE state='installed' AND name IN (%s)" % ','.join("'%s'" % name for name in MODULES)))
    if args.kind == 'packing':
        PACKING_INITIAL_MIGRATION = tuple(map(int, installed['step_packing_operations'].split('.'))) < (18, 0, 2, 8, 0)
    if args.kind == 'export':
        old_export = tuple(map(int, installed['step_export'].split('.')))
        EXPORT_SALE_ADDITION = old_export < (18, 0, 2, 9, 5)
        EXPORT_PORT_ADDITIONS = old_export < (18, 0, 2, 9, 6)
    if PRODUCERS:
        assert set(installed) >= set(MODULES) - {'step_producers_integrations'}, 'Revise only installed agricultural apps'
        assert query(database, "SELECT count(*) FROM ir_module_module WHERE name IN ('step_account_treasury','step_packing_operations') AND state='installed'") == '2', 'Bridge dependencies must already be installed'
    if SETTINGS and args.kind not in ('estimate-report','contract-report', 'fruit-reports', 'estimate-revision', 'fruit-categories', 'daily-estimate', 'shipment-provision', 'budget-design', 'shipping-design', 'document-design', 'purchase-mode', 'producer-change', 'balance-analytic', 'export-control', 'email-login', 'dispatch-improvements', 'export-dashboard', 'agro-analytics', 'harvest-planning', 'harvest-operations', 'agriculture-records', 'dispatch-design', 'sag-prototype', 'sag-lot', 'traceability', 'sag-traceability'):
        assert set(installed) == set(MODULES), 'Repair only existing modules'
    if SETTINGS or PRODUCERS or TICKET_REVISION in ('sale-format', 'client-revision', 'estimate-report', 'contract-report', 'fruit-reports', 'estimate-revision', 'fruit-categories', 'daily-estimate', 'shipment-provision', 'budget-design', 'shipping-design', 'document-design', 'purchase-mode', 'producer-change', 'balance-analytic', 'export-control', 'email-login', 'dispatch-improvements', 'export-dashboard', 'agro-analytics', 'harvest-planning', 'harvest-operations', 'agriculture-records', 'dispatch-design', 'sag-prototype', 'sag-lot', 'traceability', 'sag-traceability'):
        assert not query(database, "SELECT name FROM ir_module_module WHERE state IN ('to upgrade','to install','to remove')"), 'Pending upgrades'
    for name, old in installed.items():
        assert tuple(map(int, proof['versions'][name].split('.'))) >= tuple(map(int, old.split('.'))), 'Downgrade refused: ' + name
    update = [name for name in MODULES if name in installed]
    install = ['step_agriculture_catalogs'] if args.kind == 'management' else ['step_producers_integrations'] if PRODUCERS and 'step_producers_integrations' not in installed else []
    if args.kind in ('estimate-report','contract-report', 'fruit-reports', 'estimate-revision', 'fruit-categories', 'daily-estimate', 'shipment-provision', 'budget-design', 'shipping-design', 'document-design', 'purchase-mode', 'producer-change', 'balance-analytic', 'export-control', 'email-login', 'dispatch-improvements', 'export-dashboard', 'agro-analytics', 'harvest-planning', 'harvest-operations', 'agriculture-records', 'dispatch-design', 'sag-prototype', 'sag-lot', 'traceability', 'sag-traceability'):
        install = [name for name in MODULES if name not in installed]
    if args.kind == 'sale-format' and SALE_FORMAT_INITIAL:
        install = ['step_sale_export_report']
    if args.kind == 'client-revision' and CLIENT_REVISION_INITIAL:
        install = ['step_export_client_revision']
    if args.kind == 'management' and query(database, "SELECT 1 FROM ir_module_module WHERE name='step_producers' AND state='installed'"):
        install.append('step_management_costs_producers')
    addon_paths = opts['addons_path'].split(',')
    baseline = {'config_sha256': digest(conf), 'modules': {}}
    for name in installed:
        source = next(Path(path.strip()) / name for path in addon_paths if (Path(path.strip()) / name / '__manifest__.py').exists())
        baseline['modules'][name] = {'source': str(source), 'sha256': tree_hash(source), 'version': installed[name]}
    if SETTINGS or PRODUCERS or TICKET_REVISION in ('sale-format', 'client-revision', 'estimate-report', 'contract-report', 'fruit-reports', 'estimate-revision', 'fruit-categories', 'daily-estimate', 'shipment-provision', 'budget-design', 'shipping-design', 'document-design', 'purchase-mode', 'producer-change', 'balance-analytic', 'export-control', 'email-login', 'dispatch-improvements', 'export-dashboard', 'agro-analytics', 'harvest-planning', 'harvest-operations', 'agriculture-records', 'dispatch-design', 'sag-prototype', 'sag-lot', 'traceability', 'sag-traceability'):
        condition = "" if TICKET_REVISION in ('sale-format', 'client-revision', 'estimate-report', 'contract-report', 'fruit-reports', 'estimate-revision', 'fruit-categories', 'daily-estimate', 'shipment-provision', 'budget-design', 'shipping-design', 'document-design', 'purchase-mode', 'producer-change', 'balance-analytic', 'export-control', 'email-login', 'dispatch-improvements', 'export-dashboard', 'agro-analytics', 'harvest-planning', 'harvest-operations', 'agriculture-records', 'dispatch-design', 'sag-prototype', 'sag-lot', 'traceability', 'sag-traceability') else " AND name LIKE 'step%'"
        shared = json.loads(query(database, "SELECT json_object_agg(name,latest_version) FROM ir_module_module WHERE state='installed'" + condition))
        baseline['shared_modules'] = {}
        for name, version in shared.items():
            source = next((Path(path.strip()) / name for path in addon_paths if (Path(path.strip()) / name / '__manifest__.py').exists()), None)
            baseline['shared_modules'][name] = {'version': version, 'sha256': tree_hash(source) if source else None}
        if TICKET_REVISION in ('payroll-fixes', 'previred-fix'):
            for name in ('hr_payroll', 'l10n_cl_simpledigital_payroll'):
                version = query(database, "SELECT latest_version FROM ir_module_module WHERE name='%s' AND state='installed'" % name)
                source = next(Path(path.strip()) / name for path in addon_paths if (Path(path.strip()) / name / '__manifest__.py').exists())
                assert version, 'Payroll provider must already be installed'
                baseline['shared_modules'][name] = {'version': version, 'sha256': tree_hash(source)}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    base = ['sudo', '-u', user, '/usr/bin/python3.10', '/opt/odoo18/odoo-bin']
    if args.kind == 'sag-traceability' and args.environment == 'cerro':
        base[-1] = str(HERE / 'run_sag_cerro_upgrade.py')
    options = ['-c', str(conf), '--no-http', '--http-interface=127.0.0.1', '--http-port=0', '--gevent-port=0', '--workers=0', '--max-cron-threads=0', '--without-demo=all']
    qa_db = 'MANAGEMENT_QA_' + args.environment.upper() + '_' + args.run_id
    if args.action == 'certify':
        if args.kind == 'homepage' and 'steps_transport' in allowed_missing:
            assert query(qa_db, "SELECT latest_version FROM ir_module_module WHERE name='steps_transport' AND state='installed'") == '18.0.1.5'
        # Retry read-only post-test checks without repeating an unchanged suite.
        assert json.loads((stage / 'baseline.json').read_text()) == baseline
        logs=sorted(stage.glob('qa-*.log'))
        assert len(logs)==1
        text=logs[0].read_text(errors='replace')
        successful = 'Modules loaded.' in text if args.kind == 'homepage' else re.search(r"0 failed, 0 error\(s\) of [1-9][0-9]* tests when loading database '"+re.escape(qa_db)+"'",text)
        assert successful and not errors(text, allowed_missing)
        assert snapshot(qa_db)==json.loads((stage/'business_before.json').read_text())
        verify(base,options,qa_db,staged,opts,proof,stage,{*installed,*install})
        (stage/'qa_passed.json').write_text(json.dumps({'commit':proof['commit'],'release_sha256':release_sha,'database':qa_db,'log':str(logs[0])}))
        print('MANAGEMENT_CERTIFY_OK '+args.environment,flush=True)
        return
    if args.action in ('qa', 'compatibility'):
        if SETTINGS or PRODUCERS or TICKET_REVISION in ('sale-format', 'client-revision', 'estimate-report', 'contract-report', 'fruit-reports', 'estimate-revision', 'fruit-categories', 'daily-estimate', 'shipment-provision', 'budget-design', 'shipping-design', 'document-design', 'purchase-mode', 'producer-change', 'balance-analytic', 'export-control', 'email-login', 'dispatch-improvements', 'export-dashboard', 'agro-analytics', 'harvest-planning', 'harvest-operations', 'agriculture-records', 'dispatch-design', 'sag-prototype', 'sag-lot', 'traceability', 'sag-traceability'):
            settings_lease = open('/run/lock/steps-environments.lock', 'a')
            fcntl.flock(settings_lease, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for command in Path('/proc').glob('[0-9]*/cmdline'):
                try:
                    argv = command.read_bytes().decode(errors='replace').split('\x00')
                except OSError:
                    continue
                for index, arg in enumerate(argv):
                    if Path(arg).name == 'odoo-bin':
                        assert not any(option in ('-u', '-i', '--update', '--init') or option.startswith(('--update=', '--init=')) for option in argv[index + 1:]), 'Concurrent Odoo upgrade'
        if args.kind == 'homepage':
            from verify_home_heading_http import capture_before
            capture_before(target['url'], stage)
        # Catch import/API compatibility errors before restoring a whole clone.
        import_probe = "import sys,importlib.util\nsys.path.insert(0,'/opt/odoo18')\nspec=importlib.util.spec_from_file_location('odoo.addons.step_agriculture_catalogs.models.catalogs',%r)\nmodule=importlib.util.module_from_spec(spec)\nspec.loader.exec_module(module)\nprint('CATALOG_IMPORT_OK')\n" % str(staged / 'step_agriculture_catalogs/models/catalogs.py')
        if args.kind == 'management':
            run('/usr/bin/python3.10', '-c', import_probe)
        assert not query('postgres', "SELECT 1 FROM pg_database WHERE datname='%s'" % qa_db), 'Use a fresh run_id'
        (stage / 'baseline.json').write_text(json.dumps(baseline, indent=2))
        with (stage / 'source.dump').open('wb') as stream:
            run('sudo', '-u', 'postgres', 'pg_dump', '-Fc', database, stdout=stream)
        run('sudo', '-u', 'postgres', 'createdb', '-O', opts['db_user'], qa_db)
        query(qa_db, 'CREATE EXTENSION IF NOT EXISTS pg_trgm; CREATE EXTENSION IF NOT EXISTS unaccent;')
        with (stage / 'source.dump').open('rb') as stream:
            run('sudo', '-u', 'postgres', 'pg_restore', '--no-owner', '--no-acl', '--no-comments', '--role', opts['db_user'], '-d', qa_db, stdin=stream)
        # Compare the exact immutable dump restored for this run. The live QA
        # service can legitimately receive edits while pg_dump is running.
        before = snapshot(qa_db)
        (stage / 'business_before.json').write_text(json.dumps(before, indent=2))
        query(qa_db, 'UPDATE ir_cron SET active=false; UPDATE ir_mail_server SET active=false;')
        data = stage / 'data'
        source_store = Path(opts['data_dir']) / 'filestore' / database
        if source_store.exists():
            destination = data / 'filestore' / qa_db
            destination.mkdir(parents=True, exist_ok=True)
            run('rsync', '-a', str(source_store) + '/', str(destination) + '/')
        for path in [data, *data.rglob('*')] if data.exists() else []:
            os.chown(path, identity.pw_uid, identity.pw_gid)
        log = stage / ('qa-' + stamp + '.log')
        # HTTP tests must use a real private port and must never select the
        # source service's database through its inherited dbfilter.
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            private_port = listener.getsockname()[1]
        qa_options = [option for option in options if not option.startswith('--http-port=')]
        qa_options += ['--http-port=' + str(private_port), '--db-filter=^' + qa_db + '$']
        query(qa_db, "UPDATE ir_config_parameter SET value='http://127.0.0.1:%s' WHERE key='web.base.url'" % private_port)
        print('MANAGEMENT_QA_BEGIN ' + json.dumps({'database': qa_db, 'log': str(log), 'commit': proof['commit']}), flush=True)
        tags = ','.join('/' + name for name in [*update, *install])
        init_options = ['-i', ','.join(install)] if install else []
        update_options = ['-u', ','.join(update)] if update else []
        if args.kind == 'agriculture-records':
            agriculture_migrate('prepare', qa_db, AGRICULTURE_SOURCE)
        result = subprocess.run(base + qa_options + ['-d', qa_db, '--addons-path=' + str(staged) + ',' + opts['addons_path'], '--data-dir=' + str(data)] + init_options + update_options + ['--test-enable', '--test-tags', tags, '--stop-after-init', '--logfile=' + str(log)])
        text = log.read_text(errors='replace')
        print('\n'.join(line for line in text.splitlines() if 'tests.result' in line or ' ERROR ' in line or ' FAIL' in line)[-7000:], flush=True)
        results = re.findall(r'0 failed, 0 error\(s\) of ([1-9][0-9]*) tests when loading database ' + re.escape("'" + qa_db + "'"), text)
        assert result.returncode == 0 and (results or (args.kind == 'homepage' and 'Modules loaded.' in text)) and not errors(text, allowed_missing), 'QA failed: ' + str(log)
        if args.kind == 'agriculture-records':
            agriculture_migrate('finalize', qa_db, AGRICULTURE_SOURCE)
        assert snapshot(qa_db) == before, 'Business amounts/rows changed during migration'
        verify(base, options, qa_db, staged, opts, proof, stage, {*installed, *install})
        if args.kind == 'email-login':
            from verify_email_http import verify_http
            verify_http(base, options, qa_db, staged, opts, stage)
            assert snapshot(qa_db) == before, 'HTTP fixture cleanup changed original business/account records'
            if args.normalize_user_id:
                clone_options = options + ['--addons-path=' + str(staged) + ',' + opts['addons_path'], '--data-dir=' + str(data)]
                normalize_approved_account(base, clone_options, qa_db, args, False)
                assert snapshot(qa_db) == before, 'Normalization dry run changed the clone'
        (stage / 'qa_passed.json').write_text(json.dumps({'commit': proof['commit'], 'release_sha256': release_sha, 'database': qa_db, 'log': str(log)}))
        print('MANAGEMENT_QA_OK ' + args.environment, flush=True)
        return
    passed = json.loads((stage / 'qa_passed.json').read_text())
    assert passed['commit'] == proof['commit'] and passed['release_sha256'] == release_sha
    release_root = Path('/opt/steps-managed/releases') / args.environment / proof['commit']
    if args.action == 'deploy':
        if args.environment != registry['policy']['qa']:
            if args.kind == 'sag-traceability':
                # Every byte already reviewed in the two original Development
                # releases; the combined package also passed Development tests.
                verify_authorization(args.approval_dir,args.development_proof,proof,release_sha)
            else:
                qa_root = Path('/opt/steps-managed/releases/development') / proof['commit']
                assert (qa_root / 'release.json').exists(), 'First deliver this package to Desarrollo for review'
                assert json.loads((qa_root / 'release.json').read_text()) == proof
        assert json.loads((stage / 'baseline.json').read_text()) == baseline, 'Concurrent source/config change; repeat QA from current baseline'
        with open('/run/lock/steps-environments.lock', 'a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            for command in Path('/proc').glob('[0-9]*/cmdline'):
                try:
                    argv = command.read_bytes().decode(errors='replace').split('\x00')
                except OSError:
                    continue
                for index, arg in enumerate(argv):
                    if Path(arg).name in ('odoo-bin','run_sag_cerro_upgrade.py'):
                        assert not any(option in ('-u', '-i', '--update', '--init') or option.startswith(('--update=', '--init=')) for option in argv[index + 1:]), 'Concurrent upgrade PID ' + command.parent.name
            assert not release_root.exists(), 'Release already exists'
            release_root.mkdir(parents=True)
            extract(args.release, release_root)
            for path in [release_root, *release_root.rglob('*')]:
                os.chown(path, identity.pw_uid, identity.pw_gid)
            backup = Path('/opt/steps_backups') / ('management_' + args.environment + '_' + stamp)
            backup.mkdir(mode=0o700)
            shutil.copy2(conf, backup / 'odoo.conf')
            run('systemctl', 'stop', service)
            try:
                with (backup / 'database.dump').open('wb') as stream:
                    run('sudo', '-u', 'postgres', 'pg_dump', '-Fc', database, stdout=stream)
                if TICKET_REVISION in ('sale-format', 'client-revision', 'estimate-report', 'contract-report', 'fruit-reports', 'estimate-revision', 'fruit-categories', 'daily-estimate', 'shipment-provision', 'budget-design', 'shipping-design', 'document-design', 'purchase-mode', 'producer-change', 'balance-analytic', 'export-control', 'email-login', 'dispatch-improvements', 'export-dashboard', 'agro-analytics', 'harvest-planning', 'harvest-operations', 'agriculture-records', 'dispatch-design', 'sag-prototype', 'sag-lot', 'traceability', 'sag-traceability'):
                    store = Path(opts['data_dir']) / 'filestore' / database
                    if store.exists():
                        run('rsync', '-a', str(store) + '/', str(backup / 'filestore') + '/')
                before = snapshot(database)
                (backup / 'business_before.json').write_text(json.dumps(before, indent=2))
                if args.kind == 'agriculture-records':
                    agriculture_migrate('prepare', database, release_root / 'step_agriculture_records')
                new_paths = str(release_root) + ',' + opts['addons_path']
                changed, count = re.subn(r'(?m)^\s*addons_path\s*=.*$', 'addons_path = ' + new_paths, conf.read_text())
                assert count == 1
                conf.write_text(changed)
                log = stage / ('deploy-' + stamp + '.log')
                init_options = ['-i', ','.join(install)] if install else []
                update_options = ['-u', ','.join(update)] if update else []
                result = subprocess.run(base + options + ['-d', database] + init_options + update_options + ['--stop-after-init', '--logfile=' + str(log)])
                text = log.read_text(errors='replace')
                assert result.returncode == 0 and 'Modules loaded.' in text and not errors(text, allowed_missing), str(log)
                if args.kind == 'agriculture-records':
                    agriculture_migrate('finalize', database, release_root / 'step_agriculture_records')
                assert snapshot(database) == before, 'Business migration check failed'
                if TICKET_REVISION == 'sale-format':
                    # Explicit per-company configuration; never copy banking values.
                    selection = "env.ref('base.main_company')" if args.environment == 'development' else "env['res.company'].search([('vat','=','76943293-0')])"
                    script = "company=" + selection + "\nassert len(company)==1\ncompany.step_export_sale_format=True\nenv.cr.commit()\nprint('SALE_FORMAT_COMPANY_CONFIGURED_OK')\n"
                    result = run(*(base[:4] + [base[4], 'shell'] + options + ['-d', database, '--log-level=error']), input=script, text=True, capture_output=True)
                    assert 'SALE_FORMAT_COMPANY_CONFIGURED_OK' in result.stdout
                # T52 explicitly asks that current Cerro catalog entries be shared.
                if args.environment == 'cerro' and args.kind == 'management':
                    script = "from odoo import Command\nmodels=('step.temporada','step.especie','step.grupo.variedad','step.variedad')\nfor name in models:\n    records=env[name].search([])\n    records.with_context(_install_scope=__import__('odoo.addons.step_agriculture_catalogs.models.catalogs',fromlist=['_INSTALL_SCOPE'])._INSTALL_SCOPE).write({'company_ids':[Command.clear()]})\nfor name in models:\n    env[name].search([])._check_catalog_scope()\nenv.cr.commit()\nprint('CERRO_CATALOGS_SHARED_OK')\n"
                    result = run(*(base[:4] + [base[4], 'shell'] + options + ['-d', database, '--log-level=error']), input=script, text=True, capture_output=True)
                    assert 'CERRO_CATALOGS_SHARED_OK' in result.stdout
                if args.kind == 'email-login' and args.normalize_user_id:
                    normalize_approved_account(base, options, database, args, True)
                (backup / 'deployment.json').write_text(json.dumps({'commit': proof['commit'], 'sha256': release_sha, 'overlay': str(release_root), 'log': str(log)}))
            except Exception:
                # Keep the upgraded DB and recovery dump; never silently discard business data.
                print('MANAGEMENT_DEPLOY_FAILED backup=' + str(backup), flush=True)
                raise
            finally:
                run('systemctl', 'start', service)
            print('MANAGEMENT_DEPLOY_OK backup=' + str(backup), flush=True)
    verify(base, options, database, release_root, opts, proof, stage, {*installed, *install})
    run('systemctl', 'is-active', '--quiet', service)
    with urllib.request.urlopen(target['url'] + '/web/login?db=' + database, timeout=30) as response:
        assert response.status == 200 and b'password' in response.read()
    print('MANAGEMENT_VERIFY_OK ' + json.dumps({'environment': args.environment, 'commit': proof['commit'], 'url': target['url']}), flush=True)


def verify(base, options, database, source, opts, proof, stage, installed):
    export = MODULES == ('step_export',)
    homepage = MODULES == ('step_demo_homepage',)
    probe = (HERE / ('verify_sag_traceability.py' if TICKET_REVISION == 'sag-traceability' else 'verify_traceability.py' if TICKET_REVISION == 'traceability' else 'verify_sag_lot.py' if TICKET_REVISION == 'sag-lot' else 'verify_sag_prototype.py' if TICKET_REVISION == 'sag-prototype' else 'verify_email_login.py' if TICKET_REVISION == 'email-login' else 'verify_dispatch_improvements.py' if TICKET_REVISION == 'dispatch-improvements' else 'verify_agriculture_records.py' if TICKET_REVISION == 'agriculture-records' else 'verify_harvest_operations.py' if TICKET_REVISION == 'harvest-operations' else 'verify_harvest_planning.py' if TICKET_REVISION == 'harvest-planning' else 'verify_agro_analytics.py' if TICKET_REVISION == 'agro-analytics' else 'verify_export_dashboard.py' if TICKET_REVISION == 'export-dashboard' else 'verify_dispatch_design.py' if TICKET_REVISION == 'dispatch-design' else 'verify_export_control.py' if TICKET_REVISION == 'export-control' else 'verify_balance_analytic.py' if TICKET_REVISION == 'balance-analytic' else 'verify_producer_change.py' if TICKET_REVISION == 'producer-change' else 'verify_purchase_mode.py' if TICKET_REVISION == 'purchase-mode' else 'verify_document_design.py' if TICKET_REVISION == 'document-design' else 'verify_shipping_design.py' if TICKET_REVISION == 'shipping-design' else 'verify_budget_design.py' if TICKET_REVISION == 'budget-design' else 'verify_shipment_provision.py' if TICKET_REVISION == 'shipment-provision' else 'verify_daily_estimate.py' if TICKET_REVISION == 'daily-estimate' else 'verify_fruit_categories.py' if TICKET_REVISION == 'fruit-categories' else 'verify_estimate_revision.py' if TICKET_REVISION == 'estimate-revision' else 'verify_fruit_reports.py' if TICKET_REVISION == 'fruit-reports' else 'verify_contract_report.py' if TICKET_REVISION == 'contract-report' else 'verify_estimate_report.py' if TICKET_REVISION == 'estimate-report' else 'verify_client_revision.py' if TICKET_REVISION == 'client-revision' else 'verify_sale_format.py' if TICKET_REVISION == 'sale-format' else 'verify_ticket_revision.py' if TICKET_REVISION else 'verify_packing_revision.py' if MODULES == ('step_packing_operations',) else 'verify_fruit_reception.py' if MODULES == ('step_inventory_packing',) else 'verify_producer_revision.py' if PRODUCERS else 'verify_settings_navigation.py' if SETTINGS else 'verify_home_heading.py' if homepage else 'verify_export_navigation.py' if export else 'verify_management.py')).read_text()
    names = installed if SETTINGS or PRODUCERS or export or homepage or TICKET_REVISION in ('sale-format', 'client-revision', 'estimate-report', 'contract-report', 'fruit-reports', 'estimate-revision', 'fruit-categories', 'daily-estimate', 'shipment-provision', 'budget-design', 'shipping-design', 'document-design', 'purchase-mode', 'producer-change', 'balance-analytic', 'export-control', 'email-login', 'dispatch-improvements', 'export-dashboard', 'agro-analytics', 'harvest-planning', 'harvest-operations', 'agriculture-records', 'dispatch-design', 'sag-prototype', 'sag-lot', 'traceability', 'sag-traceability') else {*installed, 'step_agriculture_catalogs'}
    header = 'PROBE_TOOLS=' + repr(str(HERE)) + '\nimport sys\nsys.path.insert(0,' + repr(str(HERE)) + ')\nROOT=' + repr(str(source)) + '\nEXPECTED=' + repr({name: proof['versions'][name] for name in names}) + '\n'
    if TICKET_REVISION in ('sale-format', 'client-revision', 'estimate-report', 'contract-report', 'fruit-reports', 'estimate-revision', 'fruit-categories', 'daily-estimate', 'shipment-provision', 'budget-design', 'shipping-design', 'document-design', 'purchase-mode', 'producer-change', 'balance-analytic', 'export-control', 'email-login', 'dispatch-improvements', 'export-dashboard', 'agro-analytics', 'harvest-planning', 'harvest-operations', 'agriculture-records', 'dispatch-design', 'sag-prototype', 'sag-lot', 'traceability', 'sag-traceability'):
        header += 'OUTPUT=' + repr(str(stage)) + '\n'
    data_options = ['--data-dir=' + str(stage/'data')] if TICKET_REVISION in ('sale-format', 'client-revision', 'estimate-report', 'contract-report', 'fruit-reports', 'estimate-revision', 'fruit-categories', 'daily-estimate', 'shipment-provision', 'budget-design', 'shipping-design', 'document-design', 'purchase-mode', 'producer-change', 'balance-analytic', 'export-control', 'email-login', 'dispatch-improvements', 'export-dashboard', 'agro-analytics', 'harvest-planning', 'harvest-operations', 'agriculture-records', 'dispatch-design', 'sag-prototype', 'sag-lot', 'traceability', 'sag-traceability') and database.startswith('MANAGEMENT_QA_') else []
    from contextlib import nullcontext
    report_server = nullcontext()
    if TICKET_REVISION == 'dispatch-improvements' and database.startswith('MANAGEMENT_QA_'):
        from private_report_http import report_assets_http
        report_server = report_assets_http(base, options, database, source, opts, stage, query)
    with report_server:
        result = subprocess.run(base + ['shell'] + options + data_options + ['-d', database, '--db-filter=^' + database + '$', '--addons-path=' + str(source) + ',' + opts['addons_path'], '--log-level=error'], input=header + probe, text=True, capture_output=True)
    (stage / ('verify-' + database + '.log')).write_text(result.stdout + result.stderr)
    assert result.returncode==0 and 'MANAGEMENT_REGISTRY_OK' in result.stdout, result.stderr[-2500:]
    if TICKET_REVISION == 'sag-traceability':
        assert 'MANAGEMENT_CANONICAL_FRUIT_FKS_OK' in result.stdout
    print('\n'.join(line for line in result.stdout.splitlines() if line.startswith(('MANAGEMENT_REGISTRY_OK','MANAGEMENT_CANONICAL_FRUIT_FKS_OK'))), flush=True)
    if homepage:
        from verify_home_heading_http import verify_http
        verify_http(base, options, database, source, opts, stage)


if __name__ == '__main__':
    main()
