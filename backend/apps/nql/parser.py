"""
Lark-based parser for the SQL-like NQL surface (PROJECT_HANDBOOK.md §14 / master spec §12):

    SELECT name, email FROM lead
    WHERE status = "open" AND value >= 1000 AND assigned_to = @me
    ORDER BY value DESC
    LIMIT 50

It produces the same :class:`NQLQuery` AST the JSON loader does, so both surfaces
share one compiler. JOINs/aggregations are JSON-only in v1.
"""
from __future__ import annotations

from lark import Lark, Transformer
from lark.exceptions import LarkError

from .ast import Condition, FilterGroup, NQLQuery, SortClause
from .exceptions import NQLSyntaxError

_GRAMMAR = r"""
    start: select_clause? "FROM"i CNAME where_clause? orderby_clause? limit_clause?

    select_clause: "SELECT"i CNAME ("," CNAME)*
    where_clause: "WHERE"i or_expr

    or_expr: and_expr ("OR"i and_expr)*
    and_expr: atom ("AND"i atom)*
    atom: comparison
        | "(" or_expr ")"

    comparison: CNAME OP value                          -> binary
              | CNAME "NOT"i "IN"i "(" value_list ")"   -> not_in_op
              | CNAME "IN"i "(" value_list ")"          -> in_op
              | CNAME "CONTAINS"i value                 -> contains_op
              | CNAME "IS"i "NOT"i "NULL"i              -> is_not_null
              | CNAME "IS"i "NULL"i                     -> is_null

    OP: "=" | "!=" | ">=" | "<=" | ">" | "<"

    value: ESCAPED_STRING     -> str_val
         | SIGNED_NUMBER      -> num_val
         | BOOL               -> bool_val
         | "null"i            -> null_val
         | MAGIC              -> magic_val
    value_list: value ("," value)*

    orderby_clause: "ORDER"i "BY"i sort_item ("," sort_item)*
    sort_item: CNAME SORTDIR?

    BOOL.2: "true"i | "false"i
    SORTDIR: "ASC"i | "DESC"i
    MAGIC: /@[a-zA-Z_][a-zA-Z0-9_]*/

    limit_clause: "LIMIT"i INT ("OFFSET"i INT)?

    %import common.CNAME
    %import common.ESCAPED_STRING
    %import common.SIGNED_NUMBER
    %import common.INT
    %import common.WS
    %ignore WS
"""


class _Select(list):
    """Marker so SELECT lists aren't confused with ORDER BY lists."""


class _Limit(tuple):
    pass


class _ToAst(Transformer):
    # values
    def str_val(self, items):
        return items[0][1:-1]                      # strip quotes

    def num_val(self, items):
        text = str(items[0])
        return float(text) if "." in text else int(text)

    def bool_val(self, items):
        return str(items[0]).lower() == "true"

    def null_val(self, items):
        return None

    def magic_val(self, items):
        return str(items[0])                       # "@me" etc. — resolved at compile time

    def value(self, items):
        return items[0]

    def value_list(self, items):
        return list(items)

    # comparisons
    def binary(self, items):
        return Condition(field=str(items[0]), op=str(items[1]), value=items[2])

    def in_op(self, items):
        return Condition(field=str(items[0]), op="in", value=items[1])

    def not_in_op(self, items):
        return Condition(field=str(items[0]), op="not in", value=items[1])

    def contains_op(self, items):
        return Condition(field=str(items[0]), op="contains", value=items[1])

    def is_null(self, items):
        return Condition(field=str(items[0]), op="is null")

    def is_not_null(self, items):
        return Condition(field=str(items[0]), op="is not null")

    def atom(self, items):
        return items[0]

    def and_expr(self, items):
        return items[0] if len(items) == 1 else FilterGroup(op="and", conditions=list(items))

    def or_expr(self, items):
        return items[0] if len(items) == 1 else FilterGroup(op="or", conditions=list(items))

    def where_clause(self, items):
        return items[0]

    # select / order / limit
    def select_clause(self, items):
        return _Select(str(i) for i in items)

    def sort_item(self, items):
        direction = "desc" if len(items) > 1 and str(items[1]).lower() == "desc" else "asc"
        return SortClause(field=str(items[0]), direction=direction)

    def orderby_clause(self, items):
        return list(items)

    def limit_clause(self, items):
        nums = [int(i) for i in items]
        return _Limit((nums[0], nums[1] if len(nums) > 1 else 0))

    def start(self, items):
        select, entity, where, sort, limit, offset = [], None, None, [], None, 0
        for child in items:
            if isinstance(child, _Select):
                select = list(child)
            elif isinstance(child, _Limit):
                limit, offset = child[0], child[1]
            elif isinstance(child, Condition | FilterGroup):
                where = child
            elif isinstance(child, list):
                sort = child
            else:
                entity = str(child)
        return NQLQuery(entity=entity, select=select, filter=where,
                        sort=sort, limit=limit, offset=offset)


_PARSER = Lark(_GRAMMAR, parser="earley", start="start")
_TRANSFORMER = _ToAst()


def parse_nql_text(text: str) -> NQLQuery:
    """Parse SQL-like NQL text into an NQLQuery. Raises NQLSyntaxError on failure."""
    try:
        tree = _PARSER.parse(text)
        return _TRANSFORMER.transform(tree)
    except LarkError as exc:
        raise NQLSyntaxError(f"NQL syntax error: {exc}") from exc
