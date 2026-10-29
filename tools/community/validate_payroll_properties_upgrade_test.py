"""Pure snapshot/audit comparisons; no ORM or payroll engine is represented."""
import copy
import unittest

import validate_payroll_properties_upgrade as probe


def fixtures():
    before = {table: [] for table in probe.RAW_TABLES}
    stamp = '2026-10-29T09:00:00'
    before['hr_payroll_structure'] = [dict(id=41, code='SYNTHETIC', write_uid=1, write_date=stamp)]
    before['hr_payroll_structure_type'] = [dict(id=42, write_uid=1, write_date=stamp)]
    before['hr_salary_rule'] = [dict(id=10, note='<p>Nota á</p>', analytic_account_id=7, company_id=9),
                                dict(id=11, note=None, analytic_account_id=None, company_id=9)]
    before['hr_payslip'] = [dict(id=20, paid=True, step_history_locked=True, state='done', write_date=stamp)]
    before['hr_payslip_line'] = [dict(id=21, note='<p>Original</p>', analytic_account_id=7, total=123.45, write_date=stamp)]
    before.update(model_ids=[dict(id=1, model='hr.salary.rule')],
        field_ids=[dict(id=2, model='hr.salary.rule', name='note')], business_sequences={'ir_sequence_007': [15, True]},
        relations={name: [] for name in probe.RELATIONS},
        xml_config_aliases=[dict(id=900+i, module='l10n_cl_simpledigital_payroll', name=name,
            model=probe.CONFIG_ALIASES[name][1], res_id=value, noupdate=False)
            for i,(name,value) in enumerate((('structure_chile',41),('structure_type_chile',42)))])
    before['property_columns'] = [dict(table=table, field=field, data_type=kind)
        for table,field,kind in (('hr_salary_rule','note','text'),('hr_salary_rule','analytic_account_id','integer'),
                                ('hr_payslip_line','note','text'),('hr_payslip_line','analytic_account_id','integer'))]
    after = copy.deepcopy(before)
    after['hr_salary_rule'][0].update(note={'en_US':'<p>Nota á</p>'}, analytic_account_id={'9':7})
    for table in ('hr_payroll_structure','hr_payroll_structure_type'):
        after[table][0]['write_date'] = '2026-10-29T10:05:00'
    for row in after['property_columns']:
        if row['table'] == 'hr_salary_rule':
            row['data_type'] = 'jsonb'
    database = 'COMMUNITY_PAYROLL_API_PROPERTIES_UPGRADE_SYNTHETIC'
    audit = dict(database=database, license='AGPL-3',
        approved_xml_sha256=probe.CONFIG_XML_SHA256, approved_derived_xml_sha256=probe.DERIVED_CONFIG_XML_SHA256,
        legacy_xml_sha256=probe.DERIVED_CONFIG_XML_SHA256,
        candidate_xml_sha256=probe.DERIVED_CONFIG_XML_SHA256, package_xml_sha256=probe.DERIVED_CONFIG_XML_SHA256,
        provider_source_file_count=52, provider_source_files_sha256=probe.PROVIDER_SOURCE_FILES_SHA256,
        legacy_builder_sha256=probe.PROVIDER_BUILDER_SHA256, candidate_builder_sha256=probe.PROVIDER_BUILDER_SHA256,
        legacy_provider_derivation_sha256=probe.PROVIDER_DERIVATION_SHA256,
        candidate_provider_derivation_sha256=probe.PROVIDER_DERIVATION_SHA256,
        source_pin_manifest_sha256='a'*64, package_files_sha256='b'*64, upgrade_log_sha256='c'*64,
        sql_clock_before_sha256='d'*64, sql_clock_after_sha256='e'*64,
        clock_source='PostgreSQL clock_timestamp AT TIME ZONE UTC',
        sql_utc_before='2026-10-29T10:00:00', sql_utc_after='2026-10-29T10:10:00',
        reload_log_lines=[database+' odoo.modules.loading: loading l10n_cl_simpledigital_payroll/'+probe.CONFIG_XML+' '],
        aliases_before=copy.deepcopy(before['xml_config_aliases']))
    return before, after, audit


class PayrollPropertiesAuditCase(unittest.TestCase):
    def test_exact_two_loader_dates_are_reported_without_raw_exact_claim(self):
        proof = probe.verify_rows(*fixtures())
        self.assertEqual(proof['expected_write_date_changes'], 2)
        self.assertFalse(proof['all_original_raw_fields_exact'])
        self.assertEqual({(row['table'],row['id']) for row in proof['expected_write_date_change_records']},
                         {('hr_payroll_structure',41),('hr_payroll_structure_type',42)})
        self.assertEqual(proof['raw_rows_compared']-proof['raw_rows_preserved'],2)
        self.assertTrue(proof['historical_line_text_and_scalar_preserved'])

    def test_omitted_audit_retains_original_strict_timestamp_comparison(self):
        before,after,_ = fixtures()
        with self.assertRaises(AssertionError): probe.verify_rows(before,after)

    def test_source_pin_changes_or_missing_real_reload_are_rejected(self):
        for key in ('approved_xml_sha256','approved_derived_xml_sha256','legacy_xml_sha256','candidate_xml_sha256','package_xml_sha256'):
            before,after,audit = fixtures();audit[key]='d'*64
            with self.assertRaises(AssertionError): probe.verify_rows(before,after,audit)
        before,after,audit = fixtures();audit['reload_log_lines']=[]
        with self.assertRaises(AssertionError): probe.verify_rows(before,after,audit)

    def test_original_and_derived_pins_require_both_approved_52_file_provenances(self):
        for key in ('provider_source_files_sha256', 'legacy_builder_sha256', 'candidate_builder_sha256',
                    'legacy_provider_derivation_sha256', 'candidate_provider_derivation_sha256'):
            before,after,audit=fixtures();audit[key]='d'*64
            with self.assertRaises(AssertionError): probe.verify_rows(before,after,audit)
        before,after,audit=fixtures();audit['provider_source_file_count']=50
        with self.assertRaises(AssertionError): probe.verify_rows(before,after,audit)
        before,after,audit = fixtures();audit['reload_log_lines']=['another_database '+audit['reload_log_lines'][0].split(' ',1)[1]]
        with self.assertRaises(AssertionError): probe.verify_rows(before,after,audit)

    def test_alias_pk_model_res_id_and_false_noupdate_are_immutable(self):
        for key,value in (('id',999),('model','hr.salary.rule'),('res_id',999),('noupdate',True)):
            before,after,audit = fixtures();after['xml_config_aliases'][0][key]=value
            with self.assertRaises(AssertionError): probe.verify_rows(before,after,audit)

    def test_outside_or_reversed_sql_window_is_rejected(self):
        before,after,audit = fixtures();after['hr_payroll_structure'][0]['write_date']='2026-10-29T11:00:00'
        with self.assertRaises(AssertionError): probe.verify_rows(before,after,audit)
        before,after,audit = fixtures();audit['sql_utc_before']='2026-10-29T10:11:00'
        with self.assertRaises(AssertionError): probe.verify_rows(before,after,audit)

    def test_write_uid_and_every_other_configuration_value_remain_exact(self):
        for key,value in (('write_uid',2),('code','CHANGED')):
            before,after,audit=fixtures();after['hr_payroll_structure'][0][key]=value
            with self.assertRaises(AssertionError): probe.verify_rows(before,after,audit)

    def test_no_other_master_payroll_line_or_account_timestamp_is_exempted(self):
        for table in ('hr_payslip','hr_payslip_line','account_move','hr_contract','account_analytic_account','hr_work_entry'):
            before,after,audit=fixtures()
            before[table].append(dict(id=9000,write_date='2026-10-29T09:00:00'))
            after[table].append(dict(id=9000,write_date='2026-10-29T10:05:00'))
            with self.assertRaises(AssertionError): probe.verify_rows(before,after,audit)

    def test_paid_datetime_and_paid_or_history_flags_have_no_exception(self):
        for field,value in (('paid',False),('step_history_locked',False),('state','draft')):
            before,after,audit=fixtures();after['hr_payslip'][0][field]=value
            with self.assertRaises(AssertionError): probe.verify_rows(before,after,audit)
        before,after,audit=fixtures()
        before['hr_payslip'][0]['paid_datetime']='2026-10-29T09:00:00'
        after['hr_payslip'][0]['paid_datetime']='2026-10-29T10:05:00'
        with self.assertRaises(AssertionError): probe.verify_rows(before,after,audit)

    def test_line_note_analytic_and_amounts_are_not_projected_from_master(self):
        for field,value in (('note',{'en_US':'<p>Original</p>'}),('analytic_account_id',{'9':7}),('total',999)):
            before,after,audit=fixtures();after['hr_payslip_line'][0][field]=value
            with self.assertRaises(AssertionError): probe.verify_rows(before,after,audit)

    def test_only_one_expected_date_does_not_satisfy_two_record_witness(self):
        before,after,audit=fixtures();after['hr_payroll_structure'][0]['write_date']=before['hr_payroll_structure'][0]['write_date']
        with self.assertRaises(AssertionError): probe.verify_rows(before,after,audit)

    def test_null_properties_and_original_business_numbers_cannot_be_filled(self):
        before,after,audit=fixtures();after['hr_salary_rule'][1]['note']={'en_US':''}
        with self.assertRaises(AssertionError): probe.verify_rows(before,after,audit)
        before,after,audit=fixtures();after['business_sequences']['ir_sequence_007'][0]=16
        with self.assertRaises(AssertionError): probe.verify_rows(before,after,audit)


class PostgreSQLClockTest(unittest.TestCase):
    def test_fractional_json_precision_is_exact_on_python_310(self):
        from datetime import timedelta
        for fraction in ('1', '12', '123', '1234', '39977', '123456'):
            for zone in ('', 'Z', '+00:00'):
                value = probe.utc_datetime('2026-10-29T10:53:59.' + fraction + zone)
                self.assertEqual(value.microsecond, int(fraction.ljust(6, '0')))
                self.assertEqual(value.utcoffset(), timedelta(0))
        self.assertEqual(probe.utc_datetime('2026-10-29 10:53:59').microsecond, 0)
        for invalid in ('2026-10-29', '2026-10-29T10:53:59.1234567', '2026-10-29T10:53:59.invalid'):
            with self.assertRaises((ValueError, AssertionError)):
                probe.utc_datetime(invalid)


if __name__ == '__main__':
    unittest.main(verbosity=2)
