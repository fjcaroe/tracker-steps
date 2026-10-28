"""Conservative structural checks of actual payroll configuration; never evaluate code."""
import ast
import hashlib
from collections import Counter
from odoo import _
from odoo.exceptions import UserError

ESSENTIAL=('BASIC','GROSS','NET')


def category_chain(category):
    result=set();seen=set()
    while category:
        if category.id in seen:raise UserError(_('Salary category hierarchy contains a cycle.'))
        seen.add(category.id);result.add(category.code);category=category.parent_id
    return result


def references(code):
    """Accept a single arithmetic assignment, not arbitrary Python or business policy."""
    try:
        tree=ast.parse(code or '')
        if len(tree.body)!=1 or not isinstance(tree.body[0],ast.Assign):return None
        statement=tree.body[0]
        if len(statement.targets)!=1 or not isinstance(statement.targets[0],ast.Name) or statement.targets[0].id!='result':return None
        def terms(node,sign=1):
            if isinstance(node,ast.BinOp) and isinstance(node.op,(ast.Add,ast.Sub)):
                return terms(node.left,sign)+terms(node.right,sign if isinstance(node.op,ast.Add) else -sign)
            if isinstance(node,ast.Constant) and node.value==0:return []
            if isinstance(node,ast.Attribute) and isinstance(node.value,ast.Name):
                if node.value.id=='categories':return [('category',node.attr,sign)]
                if node.value.id=='payslip' and node.attr=='paid_amount':return [('paid_amount','',sign)]
            if isinstance(node,ast.Subscript) and isinstance(node.slice,ast.Constant):
                if isinstance(node.value,ast.Name) and node.value.id=='categories':return [('category',node.slice.value,sign)]
                inner=node.value
                if node.slice.value=='total' and isinstance(inner,ast.Subscript) and isinstance(inner.value,ast.Name) and inner.value.id=='result_rules' and isinstance(inner.slice,ast.Constant):
                    return [('rule',inner.slice.value,sign)]
            if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute) and isinstance(node.func.value,ast.Name) and node.func.value.id=='categories' and node.func.attr=='get':
                if not node.keywords and len(node.args) in (1,2) and isinstance(node.args[0],ast.Constant) and (len(node.args)==1 or isinstance(node.args[1],ast.Constant) and node.args[1].value==0):
                    return [('category',node.args[0].value,sign)]
            raise ValueError('Unverified expression')
        values=Counter()
        for kind,name,sign in terms(statement.value):values[(kind,name)]+=sign
        return {key:value for key,value in values.items() if value}
    except (SyntaxError,ValueError,TypeError):return None


def configuration_report(structure):
    structure.ensure_one();structure.check_access('read')
    rules=structure.with_context(active_test=False).rule_ids.filtered('active')
    rules.check_access('read')
    errors=[];chosen={}
    # A duplicate code is a shared evaluation key, even with distinct categories
    # or conditions. Never certify a configuration by silently choosing a row.
    duplicate_codes={code:group.sorted(lambda rule:(rule.sequence,rule.id)).ids
                     for code,group in rules.grouped('code').items() if len(group)>1}
    errors.extend('RULE_CODE_AMBIGUOUS:'+code for code in sorted(duplicate_codes) if code not in ESSENTIAL)
    for code in ESSENTIAL:
        found=rules.filtered(lambda rule:rule.code==code)
        if len(found)!=1:errors.append(code+('_MISSING' if not found else '_AMBIGUOUS'))
        else:chosen[code]=found
    if len(chosen)==3:
        basic,gross,net=(chosen[code] for code in ESSENTIAL)
        if not basic.sequence<gross.sequence<net.sequence:errors.append('ESSENTIAL_SEQUENCE')
        if basic.amount_select!='code' or references(basic.amount_python_compute)!={('paid_amount',''):1}:
            errors.append('BASIC_UNVERIFIED_AMOUNT')
        reachable=category_chain(basic.category_id);dependent={'BASIC'}
        for rule in rules.sorted(lambda rule:(rule.sequence,rule.id)):
            if rule.id==basic.id or rule.sequence<=basic.sequence:continue
            if rule.sequence>=gross.sequence:break
            refs=references(rule.amount_python_compute) if rule.amount_select=='code' and rule.condition_select=='none' else None
            if refs and any(coefficient>0 and (kind=='category' and name in reachable or kind=='rule' and name in dependent) for (kind,name),coefficient in refs.items()):
                reachable.update(category_chain(rule.category_id));dependent.add(rule.code)
        refs=references(gross.amount_python_compute) if gross.amount_select=='code' else None
        if refs is None:errors.append('GROSS_UNVERIFIED_AMOUNT')
        elif not any(coefficient>0 and (kind=='category' and name in reachable or kind=='rule' and name in dependent) for (kind,name),coefficient in refs.items()):
            errors.append('GROSS_DISCONNECTED_FROM_BASIC')
        refs=references(net.amount_python_compute) if net.amount_select=='code' else None
        if refs is None:errors.append('NET_UNVERIFIED_AMOUNT')
        elif not any(coefficient>0 and (kind=='category' and name in category_chain(gross.category_id) or kind=='rule' and name=='GROSS') for (kind,name),coefficient in refs.items()):
            errors.append('NET_DISCONNECTED_FROM_GROSS')
    return {'structure_id':structure.id,'rule_count':len(rules),'essential_ids':{code:rule.id for code,rule in chosen.items()},
            'duplicate_code_ids':duplicate_codes,
            'essential_candidate_ids':{code:rules.filtered(lambda rule:rule.code==code).sorted(lambda rule:(rule.sequence,rule.id)).ids for code in ESSENTIAL},
            'errors':errors,'structural_checks_passed':not errors,'financial_certified':False,
            'rule_body_sha256':{str(rule.id):hashlib.sha256((rule.amount_python_compute or '').encode()).hexdigest() for rule in rules}}


def validate_configuration(structure):
    result=configuration_report(structure)
    if result['errors']:
        raise UserError(_('Payroll configuration cannot be certified: %s',', '.join(result['errors'])))
    return result
