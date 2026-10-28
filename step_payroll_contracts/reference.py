"""Select preserved closed reference cases; never calculate or reconstruct a wage."""
from datetime import date
from decimal import Decimal


def select_closed_reference(cases, as_of=None):
    cutoff=(as_of or date.today()).replace(day=1).isoformat()
    candidates=[];positive=[]
    for case in cases:
        if case['state'] not in ('done','paid') or case['date_to']>=cutoff:
            continue
        assert case['date_from']<=case['date_to']
        totals=case['stored_totals']
        assert set(totals)=={'BASIC','GROSS','NET'}
        values=[Decimal(str(totals[code])) for code in ('BASIC','GROSS','NET')]
        if not all(value.is_finite() for value in values):
            raise ValueError('Non-finite stored reference total')
        candidates.append(case)
        if all(value>0 for value in values):positive.append(case)
    selected=max(positive or candidates,key=lambda case:(case['date_to'],case['id'])) if candidates else None
    return {'selected_case':selected,'positive_closed_previous_month_cases':len(positive),
            'selected_case_has_positive_essential_totals':bool(selected and selected in positive),
            'zero_cases_preserved':True}
