"""Full AST-whitelist expression sandbox for .sky filter/evaluate expressions.

Only a small set of expression node types are allowed (comparisons, boolean
logic, arithmetic, literals, and name lookups against an explicit `names`
dict). Every other node type -- Call, Attribute, Subscript, Lambda,
comprehensions, Import/ImportFrom, Starred, etc. -- is rejected with a
specific reason before it is ever evaluated. Rejecting Call and Attribute
outright (rather than trying to blacklist individual dangerous functions)
is what blocks the whole family of `os.system`/`open`/`__import__`/`eval`/
`exec`/`globals()`/`.__class__.__mro__` gadget escapes: none of them are
reachable without a Call or an Attribute node somewhere in the tree.
"""
import ast

_ALLOWED_COMPARE_OPS = (ast.Lt, ast.LtE, ast.Gt, ast.GtE, ast.Eq, ast.NotEq)
_ALLOWED_BIN_OPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.FloorDiv)
_ALLOWED_BOOL_OPS = (ast.And, ast.Or)


class UnsafeExpressionError(ValueError):
    pass


def _eval_node(node, names):
    if isinstance(node, ast.Expression):
        return _eval_node(node.body, names)
    if isinstance(node, ast.Constant):
        if isinstance(node.value, (int, float, str, bool)) or node.value is None:
            return node.value
        raise UnsafeExpressionError(f"disallowed constant type: {type(node.value)}")
    if isinstance(node, ast.Name):
        if node.id in names:
            return names[node.id]
        raise UnsafeExpressionError(f"unknown name '{node.id}'")
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, names)
        for op, comparator in zip(node.ops, node.comparators):
            if not isinstance(op, _ALLOWED_COMPARE_OPS):
                raise UnsafeExpressionError(f"disallowed comparison operator: {op}")
            right = _eval_node(comparator, names)
            result = {
                ast.Lt: left < right,
                ast.LtE: left <= right,
                ast.Gt: left > right,
                ast.GtE: left >= right,
                ast.Eq: left == right,
                ast.NotEq: left != right,
            }[type(op)]
            if not result:
                return False
            left = right
        return True
    if isinstance(node, ast.BinOp):
        if not isinstance(node.op, _ALLOWED_BIN_OPS):
            raise UnsafeExpressionError(f"disallowed binary operator: {node.op}")
        left = _eval_node(node.left, names)
        right = _eval_node(node.right, names)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        if isinstance(node.op, ast.Div):
            return left / right
        if isinstance(node.op, ast.Mod):
            return left % right
        if isinstance(node.op, ast.FloorDiv):
            return left // right
    if isinstance(node, ast.BoolOp):
        if not isinstance(node.op, _ALLOWED_BOOL_OPS):
            raise UnsafeExpressionError(f"disallowed bool operator: {node.op}")
        values = [_eval_node(v, names) for v in node.values]
        return all(values) if isinstance(node.op, ast.And) else any(values)
    if isinstance(node, ast.UnaryOp):
        if isinstance(node.op, ast.Not):
            return not _eval_node(node.operand, names)
        if isinstance(node.op, ast.USub):
            return -_eval_node(node.operand, names)
        raise UnsafeExpressionError(f"disallowed unary operator: {node.op}")

    # Everything below is a *known dangerous* node type -- called out
    # explicitly (rather than falling through to the generic catch-all)
    # so BLOCKED reports name the actual escape family being attempted.
    if isinstance(node, ast.Call):
        raise UnsafeExpressionError(
            "function calls are forbidden (blocks eval/exec/__import__/"
            "os.system/open/subprocess/globals/etc.)"
        )
    if isinstance(node, ast.Attribute):
        raise UnsafeExpressionError(
            f"attribute access is forbidden (blocks '.{node.attr}' "
            "dunder/mro gadget escapes)"
        )
    if isinstance(node, ast.Subscript):
        raise UnsafeExpressionError("subscript access is forbidden")
    if isinstance(node, ast.Lambda):
        raise UnsafeExpressionError(
            "lambda expressions are forbidden (blocks closure/decorator-style bypasses)"
        )
    if isinstance(node, (ast.ListComp, ast.SetComp, ast.DictComp, ast.GeneratorExp)):
        raise UnsafeExpressionError("comprehensions are forbidden")
    if isinstance(node, ast.Starred):
        raise UnsafeExpressionError("starred unpacking is forbidden")
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        raise UnsafeExpressionError("import statements are forbidden")

    raise UnsafeExpressionError(f"disallowed expression node: {type(node).__name__}")


def safe_eval(expr, names):
    """Evaluate `expr` against a whitelist of AST nodes; `names` maps
    identifiers (e.g. item field names) to values available in the expr."""
    try:
        tree = ast.parse(expr, mode="eval")
    except SyntaxError as e:
        raise UnsafeExpressionError(f"syntax error in expression: {e}") from e
    return _eval_node(tree, names)
