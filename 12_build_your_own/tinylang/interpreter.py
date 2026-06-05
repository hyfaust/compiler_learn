"""
树遍历解释器 (Tree-Walking Interpreter)

最直观的程序执行方式：直接遍历 AST 并对每个节点求值。
这是最容易理解和实现的执行模型，非常适合教学。

工作原理：
- 表达式 (Expression) 节点 => 求值，返回一个值
- 语句 (Statement) 节点   => 执行，产生副作用
- 使用 Environment 链管理变量作用域
- 函数定义时捕获当前环境（闭包）
- break/continue 通过 Python 异常实现非局部跳转

优点：实现简单，易于理解和调试
缺点：执行速度较慢（每步都要遍历树结构）
"""

from .ast_nodes import *
from .environment import Environment
from .builtins import BuiltinFunction, get_builtins
from .errors import RuntimeError_


# ============================================================
#  辅助函数
# ============================================================

def is_truthy(value) -> bool:
    """判断一个 TinyLang 值的"真值"

    真值规则（类似 Python）：
    - false       -> 假
    - none        -> 假
    - 0 (整数)    -> 假
    - 0.0 (浮点)  -> 假
    - "" (空字符串) -> 假
    - [] (空数组)  -> 假
    - 其他所有值   -> 真

    注意：在 TinyLang 中，bool 是 int 的子类型在 Python 中，
    所以需要先检查 bool 再检查 int。
    """
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


# ============================================================
#  用户定义函数
# ============================================================

class TinyLangFunction:
    """用户定义的函数（闭包）

    保存函数的定义信息和定义时的作用域环境。
    当函数被调用时，创建一个以闭包环境为父的新环境。

    Attributes:
        name:    函数名
        params:  参数名列表
        body:    函数体（语句列表）
        closure: 定义时的环境（闭包）
        arity:   参数个数
    """

    def __init__(self, node: FunctionDef, closure: Environment):
        self.name = node.name
        self.params = node.params
        self.body = node.body
        self.closure = closure
        self.arity = len(node.params)

    def __repr__(self):
        return f"<function {self.name}/{self.arity}>"


# ============================================================
#  异常类（用于控制流）
# ============================================================

class ReturnException(Exception):
    """return 语句抛出的异常，用于实现函数返回"""
    def __init__(self, value):
        self.value = value


class BreakException(Exception):
    """break 语句抛出的异常，用于跳出循环"""
    pass


class ContinueException(Exception):
    """continue 语句抛出的异常，用于跳到下一次迭代"""
    pass


# ============================================================
#  树遍历解释器
# ============================================================

class Interpreter:
    """树遍历解释器

    通过递归遍历 AST 来执行程序。每个 AST 节点类型
    都有对应的处理方法。

    使用方法：
        from tinylang.lexer import Lexer
        from tinylang.parser import Parser
        from tinylang.interpreter import Interpreter

        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()

        interp = Interpreter()
        interp.run(ast)
    """

    def __init__(self, output_list: list = None):
        """初始化解释器

        Args:
            output_list: 可选的输出捕获列表，用于测试。
                         print 函数的输出会追加到此列表中。
        """
        self.output = output_list if output_list is not None else []
        self.global_env = Environment()
        self._setup_builtins()

    def _setup_builtins(self):
        """将内置函数注册到全局环境"""
        builtins = get_builtins(self.output)
        for name, func in builtins.items():
            self.global_env.define(name, func)

    # ============================================================
    #  程序入口
    # ============================================================

    def run(self, program: Program):
        """执行整个程序"""
        for stmt in program.statements:
            self._execute(stmt, self.global_env)

    # ============================================================
    #  语句执行
    # ============================================================

    def _execute(self, node: Statement, env: Environment):
        """执行一条语句，返回 None 或语句的求值结果"""

        # let 声明：在当前环境定义新变量
        if isinstance(node, LetStatement):
            value = self._evaluate(node.value, env)
            env.define(node.name, value)
            return None

        # 赋值：修改已有变量
        if isinstance(node, AssignmentStatement):
            value = self._evaluate(node.value, env)
            if isinstance(node.target, Identifier):
                env.set(node.target.name, value)
            elif isinstance(node.target, IndexExpression):
                arr = self._evaluate(node.target.array, env)
                idx = self._evaluate(node.target.index, env)
                if not isinstance(arr, list):
                    raise RuntimeError_("只能对数组进行索引赋值")
                arr[int(idx)] = value
            return None

        # 表达式语句：求值并丢弃结果
        if isinstance(node, ExpressionStatement):
            return self._evaluate(node.expression, env)

        # if/elif/else
        if isinstance(node, IfStatement):
            if is_truthy(self._evaluate(node.condition, env)):
                return self._execute_block(node.then_body, Environment(env))
            for elif_cond, elif_body in node.elif_clauses:
                if is_truthy(self._evaluate(elif_cond, env)):
                    return self._execute_block(elif_body, Environment(env))
            if node.else_body is not None:
                return self._execute_block(node.else_body, Environment(env))
            return None

        # while 循环
        if isinstance(node, WhileStatement):
            result = None
            while is_truthy(self._evaluate(node.condition, env)):
                try:
                    result = self._execute_block(node.body, Environment(env))
                except BreakException:
                    break
                except ContinueException:
                    continue
            return result

        # for-in 循环
        if isinstance(node, ForStatement):
            iterable = self._evaluate(node.iterable, env)
            if not isinstance(iterable, (list, str)):
                raise RuntimeError_("只能遍历数组或字符串")
            result = None
            for item in iterable:
                loop_env = Environment(env)
                loop_env.define(node.var_name, item)
                try:
                    result = self._execute_block(node.body, loop_env)
                except BreakException:
                    break
                except ContinueException:
                    continue
            return result

        # 函数定义：创建闭包并存入当前环境
        if isinstance(node, FunctionDef):
            func = TinyLangFunction(node, env)
            if node.name is not None:
                env.define(node.name, func)
            return func

        # return 语句
        if isinstance(node, ReturnStatement):
            value = None
            if node.value is not None:
                value = self._evaluate(node.value, env)
            raise ReturnException(value)

        # break / continue
        if isinstance(node, BreakStatement):
            raise BreakException()
        if isinstance(node, ContinueStatement):
            raise ContinueException()

        raise RuntimeError_(f"未知的语句类型: {type(node).__name__}")

    def _execute_block(self, statements: list, env: Environment):
        """在给定环境中执行一组语句"""
        result = None
        for stmt in statements:
            result = self._execute(stmt, env)
        return result

    # ============================================================
    #  表达式求值
    # ============================================================

    def _evaluate(self, node: Expression, env: Environment):
        """对表达式求值，返回结果值"""

        # ---- 字面量 ----
        if isinstance(node, IntegerLiteral):
            return node.value
        if isinstance(node, FloatLiteral):
            return node.value
        if isinstance(node, StringLiteral):
            return node.value
        if isinstance(node, BooleanLiteral):
            return node.value
        if isinstance(node, NoneLiteral):
            return None

        # ---- 标识符（变量引用） ----
        if isinstance(node, Identifier):
            return env.get(node.name)

        # ---- 数组字面量 ----
        if isinstance(node, ArrayLiteral):
            return [self._evaluate(elem, env) for elem in node.elements]

        # ---- 数组索引 ----
        if isinstance(node, IndexExpression):
            arr = self._evaluate(node.array, env)
            idx = self._evaluate(node.index, env)
            if not isinstance(arr, (list, str)):
                raise RuntimeError_(f"无法对 {type(arr).__name__} 类型进行索引访问")
            index = int(idx)
            if index < 0 or index >= len(arr):
                raise RuntimeError_(f"索引越界: {index} (长度为 {len(arr)})")
            return arr[index]

        # ---- 二元运算 ----
        if isinstance(node, BinaryOp):
            return self._eval_binary(node, env)

        # ---- 一元运算 ----
        if isinstance(node, UnaryOp):
            return self._eval_unary(node, env)

        # ---- 函数调用 ----
        if isinstance(node, CallExpression):
            return self._eval_call(node, env)

        # ---- 匿名函数 ----
        if isinstance(node, FunctionDef):
            return TinyLangFunction(node, env)

        raise RuntimeError_(f"未知的表达式类型: {type(node).__name__}")

    def _eval_binary(self, node: BinaryOp, env: Environment):
        """对二元运算表达式求值

        特殊处理 and/or 运算符：使用短路求值。
        - a and b: 如果 a 为假，直接返回 a；否则返回 b
        - a or b:  如果 a 为真，直接返回 a；否则返回 b
        """
        # 短路求值 and
        if node.op == "and":
            left = self._evaluate(node.left, env)
            if not is_truthy(left):
                return left
            return self._evaluate(node.right, env)

        # 短路求值 or
        if node.op == "or":
            left = self._evaluate(node.left, env)
            if is_truthy(left):
                return left
            return self._evaluate(node.right, env)

        # 普通运算：先求值两个操作数
        left = self._evaluate(node.left, env)
        right = self._evaluate(node.right, env)
        op = node.op

        # 算术运算
        if op == "+":
            # 字符串拼接：任一操作数为字符串时，将两者都转为字符串
            if isinstance(left, str) or isinstance(right, str):
                return str(left) + str(right)
            return left + right
        if op == "-":
            if not isinstance(left, (int, float)) or not isinstance(right, (int, float)):
                raise RuntimeError_(f"运算符 '-' 不支持 {type(left).__name__} 和 {type(right).__name__}")
            return left - right
        if op == "*":
            return left * right
        if op == "/":
            if right == 0:
                raise RuntimeError_("除以零")
            # 整数除法（两个操作数都是整数时）
            if isinstance(left, int) and isinstance(right, int):
                return left // right
            return left / right
        if op == "%":
            if right == 0:
                raise RuntimeError_("对零取模")
            return left % right

        # 比较运算
        if op == "==":
            return left == right
        if op == "!=":
            return left != right
        if op == "<":
            return left < right
        if op == ">":
            return left > right
        if op == "<=":
            return left <= right
        if op == ">=":
            return left >= right

        raise RuntimeError_(f"未知的二元运算符: {op}")

    def _eval_unary(self, node: UnaryOp, env: Environment):
        """对一元运算表达式求值"""
        operand = self._evaluate(node.operand, env)
        if node.op == "-":
            if not isinstance(operand, (int, float)):
                raise RuntimeError_(f"无法对 {type(operand).__name__} 取负")
            return -operand
        if node.op == "not":
            return not is_truthy(operand)
        raise RuntimeError_(f"未知的一元运算符: {node.op}")

    def _eval_call(self, node: CallExpression, env: Environment):
        """对函数调用表达式求值

        处理三种可调用对象：
        1. 内置函数 (BuiltinFunction) —— 直接调用 Python 函数
        2. 用户定义函数 (TinyLangFunction) —— 创建新环境并执行函数体
        """
        callee = self._evaluate(node.callee, env)
        args = [self._evaluate(arg, env) for arg in node.args]

        # 内置函数
        if isinstance(callee, BuiltinFunction):
            return callee.func(args)

        # 用户定义函数
        if isinstance(callee, TinyLangFunction):
            if len(args) != callee.arity:
                raise RuntimeError_(
                    f"函数 '{callee.name}' 需要 {callee.arity} 个参数，"
                    f"但传入了 {len(args)} 个"
                )
            # 创建函数执行环境，父环境是函数的闭包环境
            func_env = Environment(callee.closure)
            for i, param in enumerate(callee.params):
                func_env.define(param, args[i])
            try:
                self._execute_block(callee.body, func_env)
            except ReturnException as e:
                return e.value
            return None  # 没有显式 return 时返回 None

        raise RuntimeError_(f"不可调用的类型: {type(callee).__name__}")
