"""The four native accounting predicates with two equivalent PostgreSQL deparses."""
CHECKS=('account_move_line_check_accountable_required_fields','account_move_line_check_amount_currency_balance_sign',
        'account_move_line_check_credit_debit','account_move_line_check_non_accountable_fields_null')
ELEM="ARRAY[('line_section'::character varying)::text, ('line_note'::character varying)::text]"
ARRAY="(ARRAY['line_section'::character varying, 'line_note'::character varying])::text[]"
