"""
TinyLang 树遍历解释器

一个自包含的树遍历解释器实现，包含：
- Environment 类（支持嵌套作用域）
- 内置函数（print, len, type, str, int, float, range, append）
- 函数调用和闭包支持
- break/continue 支持
- REPL 模式

用法：
    python tinylang_interpreter.py <file.tl>   # 执行文件
    python tinylang_interpreter.py             # 进入 REPL
"""

import importlib.util as _ilu
import os as _os
import sys as _sys

# 通过文件路径导入 tinylang.py（避免与 tinylang/ 包冲突）
# 如果 tinylang.py 已经通过主脚本注册到 sys.modules，则直接复用
_mod_key = "_tinylang_standalone_mod"
if _mod_key in _sys.modules:
    _mod = _sys.modules[_mod_key]
else:
    _tinylang_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "tinylang.py")
    _spec = _ilu.spec_from_file_location(_mod_key, _tinylang_path)
    _mod = _ilu.module_from_spec(_spec)
    _sys.modules[_mod_key] = _mod
    _spec.loader.exec_module(_mod)

Lexer = _mod.Lexer
Parser = _mod.Parser
Program = _mod.Program
IntegerLiteral = _mod.IntegerLiteral
FloatLiteral = _mod.FloatLiteral
StringLiteral = _mod.StringLiteral
BooleanLiteral = _mod.BooleanLiteral
NoneLiteral = _mod.NoneLiteral
Identifier = _mod.Identifier
BinaryOp = _mod.BinaryOp
UnaryOp = _mod.UnaryOp
CallExpression = _mod.CallExpression
ArrayLiteral = _mod.ArrayLiteral
IndexExpression = _mod.IndexExpression
VarDecl = _mod.VarDecl
Assignment = _mod.Assignment
ExprStatement = _mod.ExprStatement
IfStmt = _mod.IfStmt
WhileStmt = _mod.WhileStmt
ForStmt = _mod.ForStmt
FuncDef = _mod.FuncDef
ReturnStmt = _mod.ReturnStmt
BreakStmt = _mod.BreakStmt
ContinueStmt = _mod.ContinueStmt
TinyLangError = _mod.TinyLangError


# ============================================================
#  错误
# ============================================================

class RuntimeError_(TinyLangError):
    pass


# ============================================================
#  Environment（作用域链）
# ============================================================

class Environment:
    """嵌套作用域环境，支持词法作用域和闭包"""

    def __init__(self, parent=None):
        self.vars: dict = {}
        self.parent: Environment | None = parent

    def define(self, name: str, value):
        self.vars[name] = value

    def get(self, name: str):
        if name in self.vars:
            return self.vars[name]
        if self.parent is not None:
            return self.parent.get(name)
        raise RuntimeError_(f"未定义的变量: '{name}'")

    def set(self, name: str, value):
        if name in self.vars:
            self.vars[name] = value
            return
        if self.parent is not None:
            self.parent.set(name, value)
            return
        raise RuntimeError_(f"未定义的变量: '{name}'")


# ============================================================
#  辅助函数
# ============================================================

def is_truthy(value) -> bool:
    if value is None:
        return False
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    if isinstance(value, str):
        return len(value) > 0
    if isinstance(value, list):
        return len(value) > 0
    return True


def format_value(value) -> str:
    if value is True:
        return "true"
    if value is False:
        return "false"
    if value is None:
        return "none"
    if isinstance(value, list):
        return "[" + ", ".join(format_value(v) for v in value) + "]"
    return str(value)


# ============================================================
#  内置函数
# ============================================================

class BuiltinFunc:
    def __init__(self, name, func):
        self.name = name
        self.func = func
        self.arity = -1  # 可变参数

    def __repr__(self):
        return f"<builtin: {self.name}>"


def make_builtins(output_list=None):
    builtins = {}

    def _print(args):
        text = " ".join(format_value(a) for a in args)
        if output_list is not None:
            output_list.append(text)
        print(text)
        return None
    builtins["print"] = BuiltinFunc("print", _print)

    def _len(args):
        if len(args) != 1:
            raise RuntimeError_("len() 需要 1 个参数")
        v = args[0]
        if isinstance(v, (list, str)):
            return len(v)
        raise RuntimeError_(f"len() 不支持 {type(v).__name__}")
    builtins["len"] = BuiltinFunc("len", _len)

    def _type(args):
        if len(args) != 1:
            raise RuntimeError_("type() 需要 1 个参数")
        v = args[0]
        if isinstance(v, bool): return "boolean"
        if isinstance(v, int): return "integer"
        if isinstance(v, float): return "float"
        if isinstance(v, str): return "string"
        if isinstance(v, list): return "array"
        if v is None: return "none"
        if isinstance(v, BuiltinFunc): return "builtin_function"
        if isinstance(v, UserFunc): return "function"
        return "unknown"
    builtins["type"] = BuiltinFunc("type", _type)

    def _str(args):
        if len(args) != 1:
            raise RuntimeError_("str() 需要 1 个参数")
        return format_value(args[0])
    builtins["str"] = BuiltinFunc("str", _str)

    def _int(args):
        if len(args) != 1:
            raise RuntimeError_("int() 需要 1 个参数")
        v = args[0]
        if isinstance(v, bool): return 1 if v else 0
        if isinstance(v, (int, float)): return int(v)
        if isinstance(v, str):
            try: return int(v)
            except ValueError: return int(float(v))
        raise RuntimeError_(f"无法转换为整数: {type(v).__name__}")
    builtins["int"] = BuiltinFunc("int", _int)

    def _float(args):
        if len(args) != 1:
            raise RuntimeError_("float() 需要 1 个参数")
        v = args[0]
        if isinstance(v, bool): return 1.0 if v else 0.0
        if isinstance(v, (int, float)): return float(v)
        if isinstance(v, str): return float(v)
        raise RuntimeError_(f"无法转换为浮点数: {type(v).__name__}")
    builtins["float"] = BuiltinFunc("float", _float)

    def _range(args):
        if len(args) == 1: return list(range(int(args[0])))
        if len(args) == 2: return list(range(int(args[0]), int(args[1])))
        if len(args) == 3: return list(range(int(args[0]), int(args[1]), int(args[2])))
        raise RuntimeError_("range() 需要 1-3 个参数")
    builtins["range"] = BuiltinFunc("range", _range)

    def _append(args):
        if len(args) != 2:
            raise RuntimeError_("append() 需要 2 个参数")
        if not isinstance(args[0], list):
            raise RuntimeError_("append() 第一个参数必须是数组")
        args[0].append(args[1])
        return args[0]
    builtins["append"] = BuiltinFunc("append", _append)

    return builtins


# ============================================================
#  用户定义函数（闭包）
# ============================================================

class UserFunc:
    def __init__(self, node: FuncDef, closure: Environment):
        self.name = node.name
        self.params = node.params
        self.body = node.body
        self.closure = closure
        self.arity = len(node.params)

    def __repr__(self):
        return f"<function {self.name}/{self.arity}>"


# ============================================================
#  控制流异常
# ============================================================

class ReturnExc(Exception):
    def __init__(self, value):
        self.value = value

class BreakExc(Exception): pass
class ContinueExc(Exception): pass


# ============================================================
#  树遍历解释器
# ============================================================

class Interpreter:
    """树遍历解释器，直接对 AST 求值"""

    def __init__(self, output_list=None):
        self.output = output_list if output_list is not None else []
        self.env = Environment()
        for name, func in make_builtins(self.output).items():
            self.env.define(name, func)

    def run(self, program: Program):
        for stmt in program.statements:
            self._exec(stmt, self.env)

    # ---- 语句执行 ----

    def _exec(self, node, env: Environment):
        if isinstance(node, VarDecl):
            env.define(node.name, self._eval(node.value, env))
            return
        if isinstance(node, Assignment):
            val = self._eval(node.value, env)
            if isinstance(node.target, Identifier):
                env.set(node.target.name, val)
            elif isinstance(node.target, IndexExpression):
                arr = self._eval(node.target.array, env)
                idx = self._eval(node.target.index, env)
                if not isinstance(arr, list):
                    raise RuntimeError_("只能对数组索引赋值")
                arr[int(idx)] = val
            return
        if isinstance(node, ExprStatement):
            self._eval(node.expression, env)
            return
        if isinstance(node, IfStmt):
            if is_truthy(self._eval(node.condition, env)):
                return self._exec_block(node.then_body, Environment(env))
            for ec, eb in node.elif_clauses:
                if is_truthy(self._eval(ec, env)):
                    return self._exec_block(eb, Environment(env))
            if node.else_body is not None:
                return self._exec_block(node.else_body, Environment(env))
            return
        if isinstance(node, WhileStmt):
            while is_truthy(self._eval(node.condition, env)):
                try:
                    self._exec_block(node.body, Environment(env))
                except BreakExc:
                    break
                except ContinueExc:
                    continue
            return
        if isinstance(node, ForStmt):
            iterable = self._eval(node.iterable, env)
            if not isinstance(iterable, (list, str)):
                raise RuntimeError_("只能遍历数组或字符串")
            for item in iterable:
                loop_env = Environment(env)
                loop_env.define(node.var_name, item)
                try:
                    self._exec_block(node.body, loop_env)
                except BreakExc:
                    break
                except ContinueExc:
                    continue
            return
        if isinstance(node, FuncDef):
            env.define(node.name, UserFunc(node, env))
            return
        if isinstance(node, ReturnStmt):
            val = self._eval(node.value, env) if node.value is not None else None
            raise ReturnExc(val)
        if isinstance(node, BreakStmt):
            raise BreakExc()
        if isinstance(node, ContinueStmt):
            raise ContinueExc()
        raise RuntimeError_(f"未知语句: {type(node).__name__}")

    def _exec_block(self, stmts, env: Environment):
        for s in stmts:
            self._exec(s, env)

    # ---- 表达式求值 ----

    def _eval(self, node, env: Environment):
        if isinstance(node, IntegerLiteral): return node.value
        if isinstance(node, FloatLiteral): return node.value
        if isinstance(node, StringLiteral): return node.value
        if isinstance(node, BooleanLiteral): return node.value
        if isinstance(node, NoneLiteral): return None
        if isinstance(node, Identifier): return env.get(node.name)
        if isinstance(node, ArrayLiteral):
            return [self._eval(e, env) for e in node.elements]
        if isinstance(node, IndexExpression):
            arr = self._eval(node.array, env)
            idx = self._eval(node.index, env)
            if not isinstance(arr, (list, str)):
                raise RuntimeError_(f"无法索引 {type(arr).__name__}")
            i = int(idx)
            if i < 0 or i >= len(arr):
                raise RuntimeError_(f"索引越界: {i}")
            return arr[i]
        if isinstance(node, BinaryOp): return self._eval_binary(node, env)
        if isinstance(node, UnaryOp): return self._eval_unary(node, env)
        if isinstance(node, CallExpression): return self._eval_call(node, env)
        if isinstance(node, FuncDef): return UserFunc(node, env)
        raise RuntimeError_(f"未知表达式: {type(node).__name__}")

    def _eval_binary(self, node: BinaryOp, env: Environment):
        if node.op == "and":
            left = self._eval(node.left, env)
            return left if not is_truthy(left) else self._eval(node.right, env)
        if node.op == "or":
            left = self._eval(node.left, env)
            return left if is_truthy(left) else self._eval(node.right, env)

        left = self._eval(node.left, env)
        right = self._eval(node.right, env)
        op = node.op

        if op == "+":
            if isinstance(left, str) or isinstance(right, str):
                return str(left) + str(right)
            return left + right
        if op == "-": return left - right
        if op == "*": return left * right
        if op == "/":
            if right == 0: raise RuntimeError_("除以零")
            return left // right if isinstance(left, int) and isinstance(right, int) else left / right
        if op == "%":
            if right == 0: raise RuntimeError_("对零取模")
            return left % right
        if op == "==": return left == right
        if op == "!=": return left != right
        if op == "<": return left < right
        if op == ">": return left > right
        if op == "<=": return left <= right
        if op == ">=": return left >= right
        raise RuntimeError_(f"未知运算符: {op}")

    def _eval_unary(self, node: UnaryOp, env: Environment):
        val = self._eval(node.operand, env)
        if node.op == "-": return -val
        if node.op == "not": return not is_truthy(val)
        raise RuntimeError_(f"未知一元运算符: {node.op}")

    def _eval_call(self, node: CallExpression, env: Environment):
        callee = self._eval(node.callee, env)
        args = [self._eval(a, env) for a in node.args]

        if isinstance(callee, BuiltinFunc):
            return callee.func(args)

        if isinstance(callee, UserFunc):
            if len(args) != callee.arity:
                raise RuntimeError_(
                    f"函数 '{callee.name}' 需要 {callee.arity} 个参数，传入了 {len(args)} 个")
            func_env = Environment(callee.closure)
            for i, p in enumerate(callee.params):
                func_env.define(p, args[i])
            try:
                self._exec_block(callee.body, func_env)
            except ReturnExc as e:
                return e.value
            return None

        raise RuntimeError_(f"不可调用: {type(callee).__name__}")


# ============================================================
#  REPL
# ============================================================

def repl():
    print("TinyLang 解释器 REPL")
    print("输入 'exit' 或 'quit' 退出。")
    interp = Interpreter()
    while True:
        try:
            lines = []
            depth = 0
            prompt = ">>> "
            while True:
                try:
                    line = input(prompt)
                except EOFError:
                    print()
                    return
                lines.append(line)
                depth += line.count("{") - line.count("}")
                if depth <= 0:
                    break
                prompt = "... "
            src = "\n".join(lines).strip()
            if not src:
                continue
            if src in ("exit", "quit"):
                print("再见！")
                break
            if not src.endswith("}") and not src.endswith(";"):
                src += ";"
            ast = Parser(Lexer(src).tokenize()).parse()
            interp.run(ast)
        except TinyLangError as e:
            print(f"错误: {e}")
        except Exception as e:
            print(f"内部错误: {e}")


# ============================================================
#  主函数
# ============================================================

def main():
    import sys
    args = sys.argv[1:]
    file_args = [a for a in args if not a.startswith("--")]

    if not file_args:
        repl()
        return

    with open(file_args[0], "r", encoding="utf-8") as f:
        source = f.read()

    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interp = Interpreter()
    interp.run(ast)


if __name__ == "__main__":
    main()
