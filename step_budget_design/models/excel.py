"""Bounded arithmetic reader for the supplied Excel layout; no eval/macros/links."""
import ast
import operator
import re
from odoo.exceptions import ValidationError

REF=re.compile(r"(?:(?:'([^']+)'|([A-Za-z_][A-Za-z_0-9 ]*))!)?(\$?[A-Z]{1,3}\$?\d{1,5})")
OPS={ast.Add:operator.add,ast.Sub:operator.sub,ast.Mult:operator.mul,ast.Div:operator.truediv}


class ExcelValues:
    def __init__(self,book):
        self.book=book;self.visiting=set();self.cache={}

    def value(self,sheet,coordinate):
        key=(sheet,coordinate.replace('$',''))
        if key in self.cache:return self.cache[key]
        if key in self.visiting or len(self.visiting)>100:raise ValidationError('Excel: referencia circular o demasiado profunda.')
        self.visiting.add(key)
        try:
            value=self.book[sheet][key[1]].value
            if isinstance(value,str) and value.startswith('='):
                raw=value[1:]
                direct=REF.fullmatch(raw.lstrip('+'))
                if direct:value=self.value(direct[1] or direct[2] or sheet,direct[3])
                else:
                    def ref(match):
                        result=self.value(match[1] or match[2] or sheet,match[3])
                        if result is None:result=0
                        if not isinstance(result,(int,float)):raise ValidationError('Excel: fórmula numérica con texto.')
                        return repr(result)
                    # SUM is intentionally unnecessary for importing input cells.
                    # Recompute totals in Odoo instead of trusting spreadsheet totals.
                    node=ast.parse(REF.sub(ref,raw),mode='eval').body
                    value=self._number(node)
            self.cache[key]=value
            return value
        except (ValueError,TypeError,KeyError,SyntaxError,ZeroDivisionError,OverflowError) as exc:
            raise ValidationError('Excel: fórmula no admitida en %s!%s. Use valores o aritmética simple.'%key) from exc
        finally:self.visiting.remove(key)

    def _number(self,node):
        if isinstance(node,ast.Constant) and isinstance(node.value,(int,float)):return node.value
        if isinstance(node,ast.BinOp) and type(node.op) in OPS:return OPS[type(node.op)](self._number(node.left),self._number(node.right))
        if isinstance(node,ast.UnaryOp) and isinstance(node.op,(ast.UAdd,ast.USub)):return self._number(node.operand)*(1 if isinstance(node.op,ast.UAdd) else -1)
        raise ValidationError('Excel: solo se admiten referencias y operaciones +, -, * y /.')
