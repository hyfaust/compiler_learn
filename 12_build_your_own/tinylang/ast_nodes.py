"""
AST 节点定义

定义了 TinyLang 抽象语法树的所有节点类型。每个语法结构
（语句和表达式）都有对应的 AST 节点类。

设计原则：
- 使用 dataclass 简化节点定义
- 所有节点继承自 ASTNode 基类
- 语句 (Statement) 和表达式 (Expression) 分类管理
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Optional


# ============================================================
#  基类
# ============================================================

class ASTNode:
    """所有 AST 节点的基类"""
    pass


class Statement(ASTNode):
    """语句基类 —— 语句不产生值（或产生值但不被使用）"""
    pass


class Expression(ASTNode):
    """表达式基类 —— 表达式总是产生一个值"""
    pass


# ============================================================
#  字面量 (Literal) 表达式
# ============================================================

@dataclass
class IntegerLiteral(Expression):
    """整数字面量，例如 42"""
    value: int


@dataclass
class FloatLiteral(Expression):
    """浮点数字面量，例如 3.14"""
    value: float


@dataclass
class StringLiteral(Expression):
    """字符串字面量，例如 "hello" """
    value: str


@dataclass
class BooleanLiteral(Expression):
    """布尔字面量：true 或 false"""
    value: bool


@dataclass
class NoneLiteral(Expression):
    """空值字面量：none"""
    pass


@dataclass
class ArrayLiteral(Expression):
    """数组字面量，例如 [1, 2, 3]"""
    elements: list[Expression] = field(default_factory=list)


# ============================================================
#  变量与访问
# ============================================================

@dataclass
class Identifier(Expression):
    """标识符（变量名/函数名），例如 x, foo"""
    name: str


@dataclass
class IndexExpression(Expression):
    """索引访问表达式，例如 arr[0]"""
    array: Expression
    index: Expression


# ============================================================
#  运算符表达式
# ============================================================

@dataclass
class BinaryOp(Expression):
    """二元运算表达式，例如 a + b, x == y

    op 的可能值：
    算术: '+', '-', '*', '/', '%'
    比较: '==', '!=', '<', '>', '<=', '>='
    逻辑: 'and', 'or'
    """
    left: Expression
    op: str
    right: Expression


@dataclass
class UnaryOp(Expression):
    """一元运算表达式，例如 -x, not flag

    op 的可能值: '-', 'not'
    """
    op: str
    operand: Expression


@dataclass
class CallExpression(Expression):
    """函数调用表达式，例如 foo(1, 2)"""
    callee: Expression
    args: list[Expression] = field(default_factory=list)


# ============================================================
#  语句 (Statement) 节点
# ============================================================

@dataclass
class Program(ASTNode):
    """程序根节点，包含一组语句"""
    statements: list[Statement] = field(default_factory=list)


@dataclass
class LetStatement(Statement):
    """变量声明语句：let x = 5;"""
    name: str
    value: Expression


@dataclass
class AssignmentStatement(Statement):
    """赋值语句：x = 5; 或 arr[0] = 5;

    target 可以是 Identifier（变量赋值）或 IndexExpression（索引赋值）
    """
    target: Expression
    value: Expression


@dataclass
class ExpressionStatement(Statement):
    """表达式语句 —— 将表达式作为语句执行，丢弃结果值

    例如：foo(42);  调用函数但不使用返回值
    """
    expression: Expression


@dataclass
class IfStatement(Statement):
    """if/elif/else 条件语句

    结构示例：
        if cond1 { body1 }
        elif cond2 { body2 }
        else { body3 }
    """
    condition: Expression
    then_body: list[Statement] = field(default_factory=list)
    elif_clauses: list[tuple[Expression, list[Statement]]] = field(default_factory=list)
    else_body: Optional[list[Statement]] = None


@dataclass
class WhileStatement(Statement):
    """while 循环语句：while cond { body }"""
    condition: Expression
    body: list[Statement] = field(default_factory=list)


@dataclass
class ForStatement(Statement):
    """for-in 循环语句：for i in arr { body }"""
    var_name: str
    iterable: Expression
    body: list[Statement] = field(default_factory=list)


@dataclass
class FunctionDef(Statement):
    """函数定义语句：func name(params) { body } 或匿名函数 fn(params) { body }"""
    name: Optional[str] = None
    params: list[str] = field(default_factory=list)
    body: list[Statement] = field(default_factory=list)


@dataclass
class ReturnStatement(Statement):
    """return 语句：return expr; 或 return;"""
    value: Optional[Expression] = None


@dataclass
class BreakStatement(Statement):
    """break 语句 —— 跳出当前循环"""
    pass


@dataclass
class ContinueStatement(Statement):
    """continue 语句 —— 跳到当前循环的下一次迭代"""
    pass
