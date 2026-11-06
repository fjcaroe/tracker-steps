"""Classify only privately reviewed native rules; preserve their calculations."""


def configure(env, plan, apply=False):
    seen = set()
    results = []
    for item in plan:
        rule_id = item['id']
        assert isinstance(rule_id, int) and rule_id > 0 and rule_id not in seen
        seen.add(rule_id)
        rule = env['hr.salary.rule'].sudo().browse(rule_id).exists()
        assert rule and rule.code == item['code'] and rule.name == item['name'], \
            'Reviewed retroactive rule identity changed'
        if apply:
            # A versioned classification migration changes only the new flag,
            # retaining the original rule, audit columns, code and calculations.
            env.cr.execute('UPDATE hr_salary_rule '
                           'SET step_previred_family_retroactive=true WHERE id=%s',
                           (rule_id,))
            rule.invalidate_recordset(['step_previred_family_retroactive'])
        assert rule.step_previred_family_retroactive
        results.append({'rule_id': rule_id, 'classified': True})
    return results
