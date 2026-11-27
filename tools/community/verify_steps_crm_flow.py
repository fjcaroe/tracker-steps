"""Compare native and Community CRM receipts without writing customer data to the report."""
import argparse
import json
from pathlib import Path

from prepare_steps_crm_cohort import SOURCE_MANIFESTS


def verify(native, community, reads, providers):
    if not __debug__:
        raise ValueError('Run with normal assertion checks.')
    expected = ['MANAGEMENT_QA_STEPS_CRM_20261126U42C', 'COMMUNITY_STEPS_CRM_20261126U42C']
    assert [r['database'] for r in (native, community)] == expected
    assert [r['database'] for r in reads] == expected
    for record in (native, community, *reads):
        assert (record['uid'], record['menu'],record['server_action'],record['action'],record['view']) == (7,340,488,505,1484)
        assert record['form_fields'] == 71
        assert [record[name][0] for name in ('visible_leads','owned_leads','visible_contacts')] == [1640,9,1586]
    for field in ('visible_leads','owned_leads','visible_contacts','original_relationships'):
        assert all(row[field] == native[field] for row in (community, *reads))
    for trial in (native, community):
        assert (trial['phase'],trial['rows_preserved'],trial['original_counter_count']) == ('rolled_back',True,804)
    assert 0 < native['selected_stage'] != native['won_stage'] > 0
    assert (native['selected_stage'],native['won_stage']) == (community['selected_stage'],community['won_stage'])
    a, b = reads
    assert a['phase'] == b['phase'] == 'inspected' and a['full_form'] == b['full_form']
    full = a['full_form']
    assert (full['records'],full['fields'],len(full['field_digests'])) == (9,72,72)
    assert providers == {'active':157, 'official_manifest_digest': SOURCE_MANIFESTS}
    return {'providers':157, 'original_menu':native['menu'], 'read_opportunities':full['records'],
            'properties':full['fields'], 'historic_values_sha256':full['values'],
            'stage':native['selected_stage'], 'won_stage':native['won_stage'],
            'sequence_draws': {row['database']:row['test_advanced'] for row in (native,community)}}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    for argument in ('native','community','native-read','community-read','providers'):
        parser.add_argument('--'+argument, type=Path, required=True)
    args = parser.parse_args()
    def load(path):
        return json.loads(path.read_bytes())
    print(json.dumps(verify(load(args.native), load(args.community),
                            (load(args.native_read), load(args.community_read)), load(args.providers))))
