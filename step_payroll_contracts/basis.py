"""Recognize a narrow monthly worked-day polynomial without executing rule code."""
import ast
from fractions import Fraction


def monthly_worked_day_basis(source):
    if not isinstance(source,str) or len(source)>8192:return None
    aliases={}

    def zero(node):
        return isinstance(node,ast.Constant) and type(node.value) in (int,float) and node.value==0

    def combine(left,right,operator):
        if not isinstance(left,dict) or not isinstance(right,dict):raise ValueError()
        result={}
        if operator in ('add','sub'):
            result=dict(left)
            for term,value in right.items():result[term]=result.get(term,Fraction(0))+value*(1 if operator=='add' else -1)
        elif operator=='mul':
            for a,x in left.items():
                for b,y in right.items():
                    term=tuple(sorted(a+b));result[term]=result.get(term,Fraction(0))+x*y
        elif operator=='div':
            if set(right)!={()} or not right[()]:raise ValueError()
            result={term:value/right[()] for term,value in left.items()}
        if len(result)>64 or any(len(term)>2 for term in result):raise ValueError()
        return {term:value for term,value in result.items() if value}

    def expression(node):
        if isinstance(node,ast.Name):return aliases[node.id]
        if isinstance(node,ast.Constant) and type(node.value) in (int,float):
            value=Fraction(str(node.value));return {():value} if value else {}
        if isinstance(node,ast.Attribute):
            if isinstance(node.value,ast.Name) and node.value.id=='contract' and node.attr=='wage':
                return {('wage',):Fraction(1)}
            if node.attr=='number_of_days':
                record=expression(node.value)
                if isinstance(record,tuple) and record[0]=='record':return {('day:'+record[1],):Fraction(1)}
            raise ValueError()
        if isinstance(node,ast.Call) and isinstance(node.func,ast.Attribute):
            call=node.func
            if isinstance(call.value,ast.Name) and call.value.id=='worked_days' and call.attr=='get' and len(node.args)==1 and not node.keywords:
                code=node.args[0]
                if isinstance(code,ast.Constant) and isinstance(code.value,str) and code.value:
                    return ('record',code.value)
            raise ValueError()
        if isinstance(node,ast.BoolOp) and isinstance(node.op,ast.Or) and len(node.values)==2 and zero(node.values[1]):
            value=expression(node.values[0])
            if value=={('wage',):Fraction(1)}:return value
            raise ValueError()
        if isinstance(node,ast.IfExp) and zero(node.orelse):
            test=node.test
            if isinstance(test,ast.BoolOp) and isinstance(test.op,ast.And) and len(test.values)==2:
                record=expression(test.values[0]);days=expression(test.values[1]);body=expression(node.body)
                if isinstance(record,tuple) and record[0]=='record' and days==body=={('day:'+record[1],):Fraction(1)}:return body
            raise ValueError()
        if isinstance(node,ast.BinOp):
            operator={ast.Add:'add',ast.Sub:'sub',ast.Mult:'mul',ast.Div:'div'}.get(type(node.op))
            if operator:return combine(expression(node.left),expression(node.right),operator)
        raise ValueError()

    try:
        statements=ast.parse(source or '').body
        if not statements or len(statements)>32:return None
        for index,statement in enumerate(statements):
            if not isinstance(statement,ast.Assign) or len(statement.targets)!=1 or not isinstance(statement.targets[0],ast.Name):return None
            name=statement.targets[0].id
            if name in aliases or name.startswith('_') or name in ('contract','worked_days','payslip','categories','inputs','result_rules',
                    'rules','employee','env','result_qty','result_rate','result_name'):return None
            if (name=='result')!=(index==len(statements)-1):return None
            aliases[name]=expression(statement.value)
        polynomial=aliases['result']
        if not isinstance(polynomial,dict) or not polynomial:return None
        codes=[]
        for term,value in polynomial.items():
            if len(term)!=2 or term[1]!='wage' or not term[0].startswith('day:') or value!=Fraction(1,30):return None
            codes.append(term[0][4:])
        return {'kind':'contract_worked_days_monthly','divisor':30,'worked_day_codes':sorted(codes),'financial_certified':False}
    except (SyntaxError,ValueError,TypeError,KeyError,ZeroDivisionError,OverflowError,RecursionError):
        return None
