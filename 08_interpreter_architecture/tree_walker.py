#!/usr/bin/env python3
"""
tree_walker.py - 树遍历解释器（Tree-Walking Interpreter）

一个完整的树遍历解释器实现，支持：
  - 变量声明和赋值
  - 算术运算（+, -, *, /, %, **）
  - 比较运算（==, !=, <, >, <=, >=）
  - 逻辑运算（and, or, not）
  - if/elif/else 条件语句
  - while 循环
  - for 循环
  - 函数定义和调用
  - 闭包（闭包捕获外部变量）
  - 内置函数（print, len, typeof, range, str, int, input）
  - 错误处理
  - REPL 交互模式

语言语法示例：
  let x = 10
  fn add(a, b) { return a + b }
  if x > 5 { print("big") } else { print("small") }
  for i = 0, 10 { print(i) }
  while x > 0 { x = x - 1 }

运行方式：
  python tree_walker.py              # 进入REPL模式
  python tree_walker.py script.txt   # 执行脚本文件

作者：compiler_learn 教学项目
"""

from __future__ import annotations

import sys
import math
from enum import Enum, auto
from dataclasses import dataclass, field
from typing import Any, Optional


# =============================================================================
# 第一部分：词法分析器（Lexer / Tokenizer）
# =============================================================================

class TokenType(Enum):
    """Token 类型枚举"""
    # 字面量
    NUMBER = auto()
    STRING = auto()
    TRUE = auto()
    FALSE = auto()
    NIL = auto()

    # 标识符和关键字
    IDENT = auto()
    LET = auto()
    FN = auto()
    IF = auto()
    ELIF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    IN = auto()
    RETURN = auto()
    BREAK = auto()
    CONTINUE = auto()
    AND = auto()
    OR = auto()
    NOT = auto()

    # 运算符
    PLUS = auto()       # +
    MINUS = auto()      # -
    STAR = auto()       # *
    SLASH = auto()      # /
    PERCENT = auto()    # %
    POWER = auto()      # **
    ASSIGN = auto()     # =
    EQ = auto()         # ==
    NEQ = auto()        # !=
    LT = auto()         # <
    GT = auto()         # >
    LTE = auto()        # <=
    GTE = auto()        # >=

    # 分隔符
    LPAREN = auto()     # (
    RPAREN = auto()     # )
    LBRACE = auto()     # {
    RBRACE = auto()     # }
    LBRACKET = auto()   # [
    RBRACKET = auto()   # ]
    COMMA = auto()      # ,
    COLON = auto()      # :
    SEMICOLON = auto()  # ;
    DOT = auto()        # .

    # 特殊
    EOF = auto()
    NEWLINE = auto()


# 关键字映射表
KEYWORDS: dict[str, TokenType] = {
    "let": TokenType.LET,
    "fn": TokenType.FN,
    "if": TokenType.IF,
    "elif": TokenType.ELIF,
    "else": TokenType.ELSE,
    "while": TokenType.WHILE,
    "for": TokenType.FOR,
    "in": TokenType.IN,
    "return": TokenType.RETURN,
    "break": TokenType.BREAK,
    "continue": TokenType.CONTINUE,
    "and": TokenType.AND,
    "or": TokenType.OR,
    "not": TokenType.NOT,
    "true": TokenType.TRUE,
    "false": TokenType.FALSE,
    "nil": TokenType.NIL,
}


@dataclass
class Token:
    """Token 数据结构"""
    type: TokenType
    value: Any
    line: int
    column: int

    def __repr__(self) -> str:
        return f"Token({self.type}, {self.value!r}, line={self.line})"


class LexError(Exception):
    """词法分析错误"""
    def __init__(self, message: str, line: int, column: int):
        super().__init__(f"LexError at line {line}, column {column}: {message}")
        self.line = line
        self.column = column


class Lexer:
    """
    词法分析器：将源代码字符串分解为 Token 流。

    工作原理：
    1. 逐字符扫描源代码
    2. 根据第一个字符判断 Token 类型
    3. 读取完整的 Token（可能跨多个字符）
    4. 返回 Token 序列
    """

    def __init__(self, source: str, filename: str = "<stdin>"):
        self.source = source
        self.filename = filename
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: list[Token] = []

    def error(self, message: str) -> LexError:
        return LexError(message, self.line, self.column)

    def peek(self) -> str:
        """查看当前字符，不移动位置"""
        if self.pos >= len(self.source):
            return '\0'
        return self.source[self.pos]

    def advance(self) -> str:
        """读取并返回当前字符，然后前进"""
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def match(self, expected: str) -> bool:
        """如果下一个字符匹配则消费它"""
        if self.pos + 1 < len(self.source) and self.source[self.pos + 1] == expected:
            self.advance()
            return True
        return False

    def skip_whitespace_and_comments(self):
        """跳过空白字符和注释"""
        while self.pos < len(self.source):
            ch = self.peek()
            if ch in (' ', '\t', '\r'):
                self.advance()
            elif ch == '#':
                # 单行注释：跳到行末
                while self.pos < len(self.source) and self.peek() != '\n':
                    self.advance()
            elif ch == '/' and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == '/':
                # 另一种单行注释
                while self.pos < len(self.source) and self.peek() != '\n':
                    self.advance()
            else:
                break

    def read_number(self) -> Token:
        """读取数字（整数或浮点数）"""
        start_col = self.column
        start = self.pos
        has_dot = False
        while self.pos < len(self.source):
            ch = self.peek()
            if ch.isdigit():
                self.advance()
            elif ch == '.' and not has_dot:
                # 检查是否是小数点（而不是 .. 运算符）
                if self.pos + 1 < len(self.source) and self.source[self.pos + 1].isdigit():
                    has_dot = True
                    self.advance()
                else:
                    break
            elif ch == '_':
                # 允许数字中的下划线分隔符，如 1_000_000
                self.advance()
            else:
                break
        text = self.source[start:self.pos].replace('_', '')
        if has_dot:
            return Token(TokenType.NUMBER, float(text), self.line, start_col)
        return Token(TokenType.NUMBER, int(text), self.line, start_col)

    def read_string(self) -> Token:
        """读取字符串字面量"""
        start_col = self.column
        quote = self.advance()  # 消费开头引号
        result = []
        while self.pos < len(self.source) and self.peek() != quote:
            if self.peek() == '\\':
                self.advance()
                if self.pos >= len(self.source):
                    raise self.error("Unterminated string escape")
                esc = self.advance()
                escape_map = {
                    'n': '\n', 't': '\t', 'r': '\r',
                    '\\': '\\', '\'': '\'', '"': '"', '0': '\0',
                }
                result.append(escape_map.get(esc, '\\' + esc))
            elif self.peek() == '\n':
                raise self.error("Unterminated string (newline in string)")
            else:
                result.append(self.advance())
        if self.pos >= len(self.source):
            raise self.error("Unterminated string")
        self.advance()  # 消费结尾引号
        return Token(TokenType.STRING, ''.join(result), self.line, start_col)

    def read_identifier(self) -> Token:
        """读取标识符或关键字"""
        start_col = self.column
        start = self.pos
        while self.pos < len(self.source) and (self.peek().isalnum() or self.peek() == '_'):
            self.advance()
        text = self.source[start:self.pos]
        token_type = KEYWORDS.get(text, TokenType.IDENT)
        # true/false 关键字转为布尔值
        if token_type == TokenType.TRUE:
            return Token(TokenType.TRUE, True, self.line, start_col)
        if token_type == TokenType.FALSE:
            return Token(TokenType.FALSE, False, self.line, start_col)
        if token_type == TokenType.NIL:
            return Token(TokenType.NIL, None, self.line, start_col)
        return Token(token_type, text, self.line, start_col)

    def tokenize(self) -> list[Token]:
        """将源代码转换为 Token 序列"""
        while self.pos < len(self.source):
            self.skip_whitespace_and_comments()

            if self.pos >= len(self.source):
                break

            ch = self.peek()
            start_col = self.column

            # 数字
            if ch.isdigit():
                self.tokens.append(self.read_number())
            # 字符串
            elif ch in ('"', "'"):
                self.tokens.append(self.read_string())
            # 标识符或关键字
            elif ch.isalpha() or ch == '_':
                self.tokens.append(self.read_identifier())
            # 运算符和分隔符
            elif ch == '+':
                self.advance()
                self.tokens.append(Token(TokenType.PLUS, '+', self.line, start_col))
            elif ch == '-':
                self.advance()
                self.tokens.append(Token(TokenType.MINUS, '-', self.line, start_col))
            elif ch == '*':
                self.advance()
                if self.peek() == '*':
                    self.advance()
                    self.tokens.append(Token(TokenType.POWER, '**', self.line, start_col))
                else:
                    self.tokens.append(Token(TokenType.STAR, '*', self.line, start_col))
            elif ch == '/':
                self.advance()
                self.tokens.append(Token(TokenType.SLASH, '/', self.line, start_col))
            elif ch == '%':
                self.advance()
                self.tokens.append(Token(TokenType.PERCENT, '%', self.line, start_col))
            elif ch == '=':
                self.advance()
                if self.peek() == '=':
                    self.advance()
                    self.tokens.append(Token(TokenType.EQ, '==', self.line, start_col))
                else:
                    self.tokens.append(Token(TokenType.ASSIGN, '=', self.line, start_col))
            elif ch == '!':
                self.advance()
                if self.peek() == '=':
                    self.advance()
                    self.tokens.append(Token(TokenType.NEQ, '!=', self.line, start_col))
                else:
                    raise self.error(f"Unexpected character '!'")
            elif ch == '<':
                self.advance()
                if self.peek() == '=':
                    self.advance()
                    self.tokens.append(Token(TokenType.LTE, '<=', self.line, start_col))
                else:
                    self.tokens.append(Token(TokenType.LT, '<', self.line, start_col))
            elif ch == '>':
                self.advance()
                if self.peek() == '=':
                    self.advance()
                    self.tokens.append(Token(TokenType.GTE, '>=', self.line, start_col))
                else:
                    self.tokens.append(Token(TokenType.GT, '>', self.line, start_col))
            elif ch == '(':
                self.advance()
                self.tokens.append(Token(TokenType.LPAREN, '(', self.line, start_col))
            elif ch == ')':
                self.advance()
                self.tokens.append(Token(TokenType.RPAREN, ')', self.line, start_col))
            elif ch == '{':
                self.advance()
                self.tokens.append(Token(TokenType.LBRACE, '{', self.line, start_col))
            elif ch == '}':
                self.advance()
                self.tokens.append(Token(TokenType.RBRACE, '}', self.line, start_col))
            elif ch == '[':
                self.advance()
                self.tokens.append(Token(TokenType.LBRACKET, '[', self.line, start_col))
            elif ch == ']':
                self.advance()
                self.tokens.append(Token(TokenType.RBRACKET, ']', self.line, start_col))
            elif ch == ',':
                self.advance()
                self.tokens.append(Token(TokenType.COMMA, ',', self.line, start_col))
            elif ch == ':':
                self.advance()
                self.tokens.append(Token(TokenType.COLON, ':', self.line, start_col))
            elif ch == ';':
                self.advance()
                self.tokens.append(Token(TokenType.SEMICOLON, ';', self.line, start_col))
            elif ch == '.':
                self.advance()
                self.tokens.append(Token(TokenType.DOT, '.', self.line, start_col))
            elif ch == '\n':
                self.advance()
                self.tokens.append(Token(TokenType.NEWLINE, '\\n', self.line, start_col))
            else:
                raise self.error(f"Unexpected character '{ch}'")

        self.tokens.append(Token(TokenType.EOF, None, self.line, self.column))
        return self.tokens


# =============================================================================
# 第二部分：抽象语法树（AST）
# =============================================================================

# --- 基础节点 ---

@dataclass
class ASTNode:
    """AST 节点基类"""
    line: int = 0


# --- 表达式节点 ---

@dataclass
class NumberLiteral(ASTNode):
    """数字字面量: 42, 3.14"""
    value: float | int = 0


@dataclass
class StringLiteral(ASTNode):
    """字符串字面量: "hello" """
    value: str = ""


@dataclass
class BoolLiteral(ASTNode):
    """布尔字面量: true, false"""
    value: bool = False


@dataclass
class NilLiteral(ASTNode):
    """nil 字面量"""
    pass


@dataclass
class ArrayLiteral(ASTNode):
    """数组字面量: [1, 2, 3]"""
    elements: list[ASTNode] = field(default_factory=list)


@dataclass
class Identifier(ASTNode):
    """标识符引用: x, foo"""
    name: str = ""


@dataclass
class BinaryOp(ASTNode):
    """二元运算: a + b, a == b"""
    op: str = ""
    left: ASTNode = field(default_factory=ASTNode)
    right: ASTNode = field(default_factory=ASTNode)


@dataclass
class UnaryOp(ASTNode):
    """一元运算: -x, not x"""
    op: str = ""
    operand: ASTNode = field(default_factory=ASTNode)


@dataclass
class Assignment(ASTNode):
    """赋值: x = value"""
    name: str = ""
    value: ASTNode = field(default_factory=ASTNode)


@dataclass
class IndexAccess(ASTNode):
    """数组下标访问: arr[i]"""
    array: ASTNode = field(default_factory=ASTNode)
    index: ASTNode = field(default_factory=ASTNode)


@dataclass
class IndexAssign(ASTNode):
    """数组下标赋值: arr[i] = value"""
    array: ASTNode = field(default_factory=ASTNode)
    index: ASTNode = field(default_factory=ASTNode)
    value: ASTNode = field(default_factory=ASTNode)


@dataclass
class FunctionCall(ASTNode):
    """函数调用: foo(1, 2)"""
    callee: ASTNode = field(default_factory=ASTNode)
    arguments: list[ASTNode] = field(default_factory=list)


# --- 语句节点 ---

@dataclass
class LetStatement(ASTNode):
    """变量声明: let x = expr"""
    name: str = ""
    value: ASTNode = field(default_factory=ASTNode)


@dataclass
class ExprStatement(ASTNode):
    """表达式语句: expr（结果被丢弃）"""
    expr: ASTNode = field(default_factory=ASTNode)


@dataclass
class ReturnStatement(ASTNode):
    """return 语句"""
    value: Optional[ASTNode] = None


@dataclass
class BreakStatement(ASTNode):
    """break 语句"""
    pass


@dataclass
class ContinueStatement(ASTNode):
    """continue 语句"""
    pass


@dataclass
class IfStatement(ASTNode):
    """if/elif/else 语句"""
    condition: ASTNode = field(default_factory=ASTNode)
    then_body: list[ASTNode] = field(default_factory=list)
    elif_branches: list[tuple[ASTNode, list[ASTNode]]] = field(default_factory=list)
    else_body: list[ASTNode] = field(default_factory=list)


@dataclass
class WhileStatement(ASTNode):
    """while 循环"""
    condition: ASTNode = field(default_factory=ASTNode)
    body: list[ASTNode] = field(default_factory=list)


@dataclass
class ForStatement(ASTNode):
    """for 循环: for i = start, end, step { body }"""
    var_name: str = ""
    start: ASTNode = field(default_factory=ASTNode)
    end: ASTNode = field(default_factory=ASTNode)
    step: Optional[ASTNode] = None
    body: list[ASTNode] = field(default_factory=list)


@dataclass
class FunctionDef(ASTNode):
    """函数定义: fn name(params) { body }"""
    name: str = ""
    params: list[str] = field(default_factory=list)
    body: list[ASTNode] = field(default_factory=list)


@dataclass
class Block(ASTNode):
    """代码块: { statements }"""
    statements: list[ASTNode] = field(default_factory=list)


# =============================================================================
# 第三部分：解析器（Parser）
# =============================================================================

class ParseError(Exception):
    """语法分析错误"""
    def __init__(self, message: str, token: Token):
        super().__init__(f"ParseError at line {token.line}: {message}")
        self.token = token


class Parser:
    """
    递归下降解析器：将 Token 流解析为 AST。

    语法规则（优先级从低到高）：
      program     = statement*
      statement   = let_stmt | if_stmt | while_stmt | for_stmt
                  | fn_def | return_stmt | break_stmt | continue_stmt
                  | expr_stmt
      expr        = logic_or
      logic_or    = logic_and ("or" logic_and)*
      logic_and   = equality ("and" equality)*
      equality    = comparison (("==" | "!=") comparison)*
      comparison  = addition (("<" | ">" | "<=" | ">=") addition)*
      addition    = multiplication (("+" | "-") multiplication)*
      multiplication = power (("*" | "/" | "%") power)*
      power       = unary ("**" power)?         # 右结合
      unary       = ("-" | "not") unary | call
      call        = primary ("(" args? ")" | "[" expr "]")*
      primary     = NUMBER | STRING | "true" | "false" | "nil"
                  | IDENT | "(" expr ")" | array_literal
    """

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        """查看当前 Token"""
        if self.pos >= len(self.tokens):
            return self.tokens[-1]
        return self.tokens[self.pos]

    def advance(self) -> Token:
        """消费并返回当前 Token"""
        tok = self.tokens[self.pos]
        self.pos += 1
        return tok

    def expect(self, token_type: TokenType) -> Token:
        """期望下一个 Token 是指定类型，否则报错"""
        tok = self.peek()
        if tok.type != token_type:
            raise ParseError(
                f"Expected {token_type.name}, got {tok.type.name} ({tok.value!r})",
                tok
            )
        return self.advance()

    def match(self, *types: TokenType) -> Optional[Token]:
        """如果当前 Token 匹配指定类型之一，则消费它"""
        if self.peek().type in types:
            return self.advance()
        return None

    def skip_newlines(self):
        """跳过换行符"""
        while self.peek().type == TokenType.NEWLINE:
            self.advance()

    # --- 语句解析 ---

    def parse_program(self) -> list[ASTNode]:
        """解析整个程序"""
        statements = []
        self.skip_newlines()
        while self.peek().type != TokenType.EOF:
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
            self.skip_newlines()
        return statements

    def parse_statement(self) -> ASTNode:
        """解析一条语句"""
        tok = self.peek()

        if tok.type == TokenType.LET:
            return self.parse_let_statement()
        elif tok.type == TokenType.IF:
            return self.parse_if_statement()
        elif tok.type == TokenType.WHILE:
            return self.parse_while_statement()
        elif tok.type == TokenType.FOR:
            return self.parse_for_statement()
        elif tok.type == TokenType.FN:
            return self.parse_function_def()
        elif tok.type == TokenType.RETURN:
            return self.parse_return_statement()
        elif tok.type == TokenType.BREAK:
            self.advance()
            return BreakStatement(line=tok.line)
        elif tok.type == TokenType.CONTINUE:
            self.advance()
            return ContinueStatement(line=tok.line)
        else:
            return self.parse_expr_statement()

    def parse_let_statement(self) -> LetStatement:
        """解析 let 声明: let name = expr"""
        tok = self.expect(TokenType.LET)
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.ASSIGN)
        value = self.parse_expression()
        self.skip_newlines()
        return LetStatement(name=name, value=value, line=tok.line)

    def parse_if_statement(self) -> IfStatement:
        """解析 if 语句"""
        tok = self.expect(TokenType.IF)
        condition = self.parse_expression()
        self.skip_newlines()
        then_body = self.parse_block()

        elif_branches = []
        else_body = []

        self.skip_newlines()
        while self.match(TokenType.ELIF):
            elif_cond = self.parse_expression()
            self.skip_newlines()
            elif_body = self.parse_block()
            elif_branches.append((elif_cond, elif_body))
            self.skip_newlines()

        if self.match(TokenType.ELSE):
            self.skip_newlines()
            else_body = self.parse_block()

        return IfStatement(
            condition=condition,
            then_body=then_body,
            elif_branches=elif_branches,
            else_body=else_body,
            line=tok.line,
        )

    def parse_while_statement(self) -> WhileStatement:
        """解析 while 循环"""
        tok = self.expect(TokenType.WHILE)
        condition = self.parse_expression()
        self.skip_newlines()
        body = self.parse_block()
        return WhileStatement(condition=condition, body=body, line=tok.line)

    def parse_for_statement(self) -> ForStatement:
        """解析 for 循环: for i = start, end[, step] { body }"""
        tok = self.expect(TokenType.FOR)
        var_name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.ASSIGN)
        start = self.parse_expression()
        self.expect(TokenType.COMMA)
        end = self.parse_expression()

        step = None
        if self.match(TokenType.COMMA):
            step = self.parse_expression()

        self.skip_newlines()
        body = self.parse_block()
        return ForStatement(
            var_name=var_name, start=start, end=end,
            step=step, body=body, line=tok.line,
        )

    def parse_function_def(self) -> FunctionDef:
        """解析函数定义: fn name(params) { body }"""
        tok = self.expect(TokenType.FN)
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.LPAREN)
        params = []
        if self.peek().type != TokenType.RPAREN:
            params.append(self.expect(TokenType.IDENT).value)
            while self.match(TokenType.COMMA):
                params.append(self.expect(TokenType.IDENT).value)
        self.expect(TokenType.RPAREN)
        self.skip_newlines()
        body = self.parse_block()
        return FunctionDef(name=name, params=params, body=body, line=tok.line)

    def parse_return_statement(self) -> ReturnStatement:
        """解析 return 语句"""
        tok = self.expect(TokenType.RETURN)
        value = None
        # 如果后面不是换行或 }，则有返回值
        if self.peek().type not in (TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF):
            value = self.parse_expression()
        return ReturnStatement(value=value, line=tok.line)

    def parse_expr_statement(self) -> ExprStatement:
        """解析表达式语句"""
        expr = self.parse_expression()
        # 尝试解析赋值
        if isinstance(expr, Identifier) and self.match(TokenType.ASSIGN):
            value = self.parse_expression()
            expr = Assignment(name=expr.name, value=value, line=expr.line)
        # 尝试解析下标赋值: arr[i] = value
        elif isinstance(expr, IndexAccess) and self.match(TokenType.ASSIGN):
            value = self.parse_expression()
            expr = IndexAssign(array=expr.array, index=expr.index, value=value, line=expr.line)
        self.skip_newlines()
        return ExprStatement(expr=expr, line=expr.line)

    def parse_block(self) -> list[ASTNode]:
        """解析代码块: { statements }"""
        self.expect(TokenType.LBRACE)
        self.skip_newlines()
        statements = []
        while self.peek().type != TokenType.RBRACE:
            if self.peek().type == TokenType.EOF:
                raise ParseError("Unexpected end of file, expected '}'", self.peek())
            stmt = self.parse_statement()
            if stmt:
                statements.append(stmt)
            self.skip_newlines()
        self.expect(TokenType.RBRACE)
        return statements

    # --- 表达式解析（优先级递增的 Pratt 解析 / 运算符优先级解析）---

    def parse_expression(self) -> ASTNode:
        """入口：解析表达式"""
        return self.parse_logic_or()

    def parse_logic_or(self) -> ASTNode:
        """解析 or 逻辑运算"""
        left = self.parse_logic_and()
        while self.match(TokenType.OR):
            right = self.parse_logic_and()
            left = BinaryOp(op='or', left=left, right=right, line=left.line)
        return left

    def parse_logic_and(self) -> ASTNode:
        """解析 and 逻辑运算"""
        left = self.parse_equality()
        while self.match(TokenType.AND):
            right = self.parse_equality()
            left = BinaryOp(op='and', left=left, right=right, line=left.line)
        return left

    def parse_equality(self) -> ASTNode:
        """解析相等比较"""
        left = self.parse_comparison()
        while (tok := self.match(TokenType.EQ, TokenType.NEQ)):
            right = self.parse_comparison()
            left = BinaryOp(op=tok.value, left=left, right=right, line=left.line)
        return left

    def parse_comparison(self) -> ASTNode:
        """解析大小比较"""
        left = self.parse_addition()
        while (tok := self.match(TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE)):
            right = self.parse_addition()
            left = BinaryOp(op=tok.value, left=left, right=right, line=left.line)
        return left

    def parse_addition(self) -> ASTNode:
        """解析加减法"""
        left = self.parse_multiplication()
        while (tok := self.match(TokenType.PLUS, TokenType.MINUS)):
            right = self.parse_multiplication()
            left = BinaryOp(op=tok.value, left=left, right=right, line=left.line)
        return left

    def parse_multiplication(self) -> ASTNode:
        """解析乘除模"""
        left = self.parse_power()
        while (tok := self.match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT)):
            right = self.parse_power()
            left = BinaryOp(op=tok.value, left=left, right=right, line=left.line)
        return left

    def parse_power(self) -> ASTNode:
        """解析幂运算（右结合）"""
        left = self.parse_unary()
        if self.match(TokenType.POWER):
            right = self.parse_power()  # 右递归实现右结合
            left = BinaryOp(op='**', left=left, right=right, line=left.line)
        return left

    def parse_unary(self) -> ASTNode:
        """解析一元运算"""
        if (tok := self.match(TokenType.MINUS)):
            operand = self.parse_unary()
            return UnaryOp(op='-', operand=operand, line=tok.line)
        if (tok := self.match(TokenType.NOT)):
            operand = self.parse_unary()
            return UnaryOp(op='not', operand=operand, line=tok.line)
        return self.parse_call()

    def parse_call(self) -> ASTNode:
        """解析函数调用和下标访问"""
        expr = self.parse_primary()
        while True:
            if self.match(TokenType.LPAREN):
                # 函数调用
                args = []
                if self.peek().type != TokenType.RPAREN:
                    args.append(self.parse_expression())
                    while self.match(TokenType.COMMA):
                        args.append(self.parse_expression())
                self.expect(TokenType.RPAREN)
                expr = FunctionCall(callee=expr, arguments=args, line=expr.line)
            elif self.match(TokenType.LBRACKET):
                # 下标访问
                index = self.parse_expression()
                self.expect(TokenType.RBRACKET)
                expr = IndexAccess(array=expr, index=index, line=expr.line)
            else:
                break
        return expr

    def parse_primary(self) -> ASTNode:
        """解析基本表达式"""
        tok = self.peek()

        if tok.type == TokenType.NUMBER:
            self.advance()
            return NumberLiteral(value=tok.value, line=tok.line)

        if tok.type == TokenType.STRING:
            self.advance()
            return StringLiteral(value=tok.value, line=tok.line)

        if tok.type == TokenType.TRUE:
            self.advance()
            return BoolLiteral(value=True, line=tok.line)

        if tok.type == TokenType.FALSE:
            self.advance()
            return BoolLiteral(value=False, line=tok.line)

        if tok.type == TokenType.NIL:
            self.advance()
            return NilLiteral(line=tok.line)

        if tok.type == TokenType.IDENT:
            self.advance()
            return Identifier(name=tok.value, line=tok.line)

        if tok.type == TokenType.LPAREN:
            self.advance()
            expr = self.parse_expression()
            self.expect(TokenType.RPAREN)
            return expr

        if tok.type == TokenType.LBRACKET:
            return self.parse_array_literal()

        raise ParseError(f"Unexpected token: {tok.type.name} ({tok.value!r})", tok)

    def parse_array_literal(self) -> ArrayLiteral:
        """解析数组字面量: [1, 2, 3]"""
        tok = self.expect(TokenType.LBRACKET)
        elements = []
        if self.peek().type != TokenType.RBRACKET:
            elements.append(self.parse_expression())
            while self.match(TokenType.COMMA):
                if self.peek().type == TokenType.RBRACKET:
                    break
                elements.append(self.parse_expression())
        self.expect(TokenType.RBRACKET)
        return ArrayLiteral(elements=elements, line=tok.line)


# =============================================================================
# 第四部分：运行时环境（Environment）
# =============================================================================

class ReturnSignal(Exception):
    """return 信号：用于从函数中返回值"""
    def __init__(self, value: Any):
        self.value = value


class BreakSignal(Exception):
    """break 信号：用于跳出循环"""
    pass


class ContinueSignal(Exception):
    """continue 信号：用于跳到循环的下一次迭代"""
    pass


class RuntimeError_(Exception):
    """运行时错误"""
    def __init__(self, message: str, line: int = 0):
        super().__init__(f"RuntimeError at line {line}: {message}")
        self.line = line


class Environment:
    """
    变量环境：管理变量的作用域链。

    环境形成一个链表结构：
    每个环境都有一个指向父环境的引用。
    变量查找从当前环境开始，沿链向上查找，直到找到变量或到达全局环境。
    """

    def __init__(self, parent: Optional[Environment] = None):
        self.vars: dict[str, Any] = {}
        self.parent = parent

    def get(self, name: str) -> Any:
        """获取变量值（沿作用域链查找）"""
        if name in self.vars:
            return self.vars[name]
        if self.parent:
            return self.parent.get(name)
        raise RuntimeError_(f"Undefined variable '{name}'")

    def set(self, name: str, value: Any):
        """设置变量值（如果变量在某层环境中已存在，则更新该层）"""
        if name in self.vars:
            self.vars[name] = value
            return
        if self.parent:
            try:
                self.parent.set(name, value)
                return
            except RuntimeError_:
                pass
        raise RuntimeError_(f"Undefined variable '{name}'")

    def define(self, name: str, value: Any):
        """在当前环境中定义新变量"""
        self.vars[name] = value


# =============================================================================
# 第五部分：可调用对象（Callable）
# =============================================================================

class Callable:
    """可调用对象的基类"""
    pass


class Function(Callable):
    """
    用户自定义函数（同时也是闭包）。

    closure_env 是函数定义时的环境，用于捕获自由变量。
    即使定义函数的代码块已执行完毕，闭包仍然通过 closure_env 引用那些变量。
    """

    def __init__(self, name: str, params: list[str], body: list[ASTNode],
                 closure_env: Environment):
        self.name = name
        self.params = params
        self.body = body
        self.closure_env = closure_env

    def __repr__(self) -> str:
        return f"<fn {self.name}/{len(self.params)}>"


class BuiltinFunction(Callable):
    """内置函数"""

    def __init__(self, name: str, func: Any):
        self.name = name
        self.func = func

    def __repr__(self) -> str:
        return f"<builtin {self.name}>"


# =============================================================================
# 第六部分：树遍历解释器（Tree-Walking Interpreter）
# =============================================================================

class Interpreter:
    """
    树遍历解释器：递归遍历 AST 执行程序。

    工作原理：
    1. 从 AST 根节点开始
    2. 对每种节点类型，调用对应的 visit 方法
    3. visit 方法递归地对子节点求值
    4. 根据节点类型执行相应的操作
    """

    def __init__(self):
        self.global_env = Environment()
        self._register_builtins()

    def _register_builtins(self):
        """注册内置函数"""
        builtins = {
            "print": BuiltinFunction("print", self._builtin_print),
            "println": BuiltinFunction("println", self._builtin_println),
            "len": BuiltinFunction("len", self._builtin_len),
            "str": BuiltinFunction("str", self._builtin_str),
            "int": BuiltinFunction("int", self._builtin_int),
            "float": BuiltinFunction("float", self._builtin_float),
            "typeof": BuiltinFunction("typeof", self._builtin_typeof),
            "range": BuiltinFunction("range", self._builtin_range),
            "input": BuiltinFunction("input", self._builtin_input),
            "abs": BuiltinFunction("abs", self._builtin_abs),
            "min": BuiltinFunction("min", self._builtin_min),
            "max": BuiltinFunction("max", self._builtin_max),
            "push": BuiltinFunction("push", self._builtin_push),
            "assert": BuiltinFunction("assert", self._builtin_assert),
        }
        for name, func in builtins.items():
            self.global_env.define(name, func)

    # --- 内置函数实现 ---

    @staticmethod
    def _builtin_print(args: list) -> None:
        """print 函数：输出值（不换行）"""
        parts = []
        for arg in args:
            if arg is None:
                parts.append("nil")
            elif isinstance(arg, bool):
                parts.append("true" if arg else "false")
            elif isinstance(arg, float) and arg == int(arg):
                parts.append(str(int(arg)))
            elif isinstance(arg, list):
                parts.append("[" + ", ".join(str(a) for a in arg) + "]")
            else:
                parts.append(str(arg))
        print(" ".join(parts), end="")

    @staticmethod
    def _builtin_println(args: list) -> None:
        """println 函数：输出值并换行"""
        Interpreter._builtin_print(args)
        print()

    @staticmethod
    def _builtin_len(args: list) -> int:
        """len 函数：返回数组或字符串的长度"""
        if len(args) != 1:
            raise RuntimeError_("len() takes exactly 1 argument")
        arg = args[0]
        if isinstance(arg, (list, str)):
            return len(arg)
        raise RuntimeError_("len() argument must be a string or array")

    @staticmethod
    def _builtin_str(args: list) -> str:
        """str 函数：将值转换为字符串"""
        if len(args) != 1:
            raise RuntimeError_("str() takes exactly 1 argument")
        arg = args[0]
        if arg is None:
            return "nil"
        if isinstance(arg, bool):
            return "true" if arg else "false"
        if isinstance(arg, float) and arg == int(arg):
            return str(int(arg))
        return str(arg)

    @staticmethod
    def _builtin_int(args: list) -> int:
        """int 函数：将值转换为整数"""
        if len(args) != 1:
            raise RuntimeError_("int() takes exactly 1 argument")
        return int(args[0])

    @staticmethod
    def _builtin_float(args: list) -> float:
        """float 函数：将值转换为浮点数"""
        if len(args) != 1:
            raise RuntimeError_("float() takes exactly 1 argument")
        return float(args[0])

    @staticmethod
    def _builtin_typeof(args: list) -> str:
        """typeof 函数：返回值的类型名称"""
        if len(args) != 1:
            raise RuntimeError_("typeof() takes exactly 1 argument")
        arg = args[0]
        if arg is None:
            return "nil"
        if isinstance(arg, bool):
            return "boolean"
        if isinstance(arg, int):
            return "integer"
        if isinstance(arg, float):
            return "number"
        if isinstance(arg, str):
            return "string"
        if isinstance(arg, list):
            return "array"
        if isinstance(arg, Function):
            return "function"
        if isinstance(arg, BuiltinFunction):
            return "builtin"
        return "unknown"

    @staticmethod
    def _builtin_range(args: list) -> list:
        """range 函数：生成整数序列"""
        if len(args) == 1:
            return list(range(int(args[0])))
        elif len(args) == 2:
            return list(range(int(args[0]), int(args[1])))
        elif len(args) == 3:
            return list(range(int(args[0]), int(args[1]), int(args[2])))
        raise RuntimeError_("range() takes 1 to 3 arguments")

    @staticmethod
    def _builtin_input(args: list) -> str:
        """input 函数：读取用户输入"""
        if len(args) > 0:
            print(str(args[0]), end="")
        return input()

    @staticmethod
    def _builtin_abs(args: list):
        """abs 函数：取绝对值"""
        if len(args) != 1:
            raise RuntimeError_("abs() takes exactly 1 argument")
        return abs(args[0])

    @staticmethod
    def _builtin_min(args: list):
        """min 函数：取最小值"""
        if len(args) == 1 and isinstance(args[0], list):
            return min(args[0])
        return min(args)

    @staticmethod
    def _builtin_max(args: list):
        """max 函数：取最大值"""
        if len(args) == 1 and isinstance(args[0], list):
            return max(args[0])
        return max(args)

    @staticmethod
    def _builtin_push(args: list) -> None:
        """push 函数：向数组末尾添加元素"""
        if len(args) != 2:
            raise RuntimeError_("push() takes exactly 2 arguments (array, value)")
        if not isinstance(args[0], list):
            raise RuntimeError_("push() first argument must be an array")
        args[0].append(args[1])

    @staticmethod
    def _builtin_assert(args: list) -> None:
        """assert 函数：断言"""
        if len(args) < 1:
            raise RuntimeError_("assert() takes at least 1 argument")
        if not args[0]:
            msg = str(args[1]) if len(args) > 1 else "Assertion failed"
            raise RuntimeError_(f"AssertionError: {msg}")

    # --- 主入口 ---

    def run(self, source: str, filename: str = "<stdin>"):
        """执行源代码"""
        # 词法分析
        lexer = Lexer(source, filename)
        tokens = lexer.tokenize()

        # 语法分析
        parser = Parser(tokens)
        ast = parser.parse_program()

        # 执行
        result = None
        for stmt in ast:
            result = self.execute(stmt)
        return result

    # --- 节点执行（核心的 visit 方法）---

    def execute(self, node: ASTNode) -> Any:
        """根据节点类型分派到对应的执行方法"""
        method_name = f"exec_{type(node).__name__}"
        method = getattr(self, method_name, None)
        if method is None:
            raise RuntimeError_(f"Unknown node type: {type(node).__name__}", getattr(node, 'line', 0))
        return method(node)

    def exec_NumberLiteral(self, node: NumberLiteral) -> float | int:
        """数字字面量：直接返回值"""
        return node.value

    def exec_StringLiteral(self, node: StringLiteral) -> str:
        """字符串字面量：直接返回值"""
        return node.value

    def exec_BoolLiteral(self, node: BoolLiteral) -> bool:
        """布尔字面量：直接返回值"""
        return node.value

    def exec_NilLiteral(self, node: NilLiteral) -> None:
        """nil 字面量：返回 None"""
        return None

    def exec_ArrayLiteral(self, node: ArrayLiteral) -> list:
        """数组字面量：对每个元素求值"""
        return [self.execute(elem) for elem in node.elements]

    def exec_Identifier(self, node: Identifier) -> Any:
        """标识符：从环境中查找变量值"""
        return self.global_env.get(node.name)

    def exec_BinaryOp(self, node: BinaryOp) -> Any:
        """
        二元运算：先求值左右操作数，再执行运算。

        短路求值：and 和 or 运算符在确定结果后不求值右侧。
        """
        # 短路求值
        if node.op == 'and':
            left = self.execute(node.left)
            if not self._is_truthy(left):
                return left
            return self.execute(node.right)

        if node.op == 'or':
            left = self.execute(node.left)
            if self._is_truthy(left):
                return left
            return self.execute(node.right)

        left = self.execute(node.left)
        right = self.execute(node.right)

        op = node.op
        if op == '+':
            return left + right
        elif op == '-':
            return left - right
        elif op == '*':
            return left * right
        elif op == '/':
            if right == 0:
                raise RuntimeError_("Division by zero", node.line)
            return left / right
        elif op == '%':
            if right == 0:
                raise RuntimeError_("Modulo by zero", node.line)
            return left % right
        elif op == '**':
            return left ** right
        elif op == '==':
            return left == right
        elif op == '!=':
            return left != right
        elif op == '<':
            return left < right
        elif op == '>':
            return left > right
        elif op == '<=':
            return left <= right
        elif op == '>=':
            return left >= right
        else:
            raise RuntimeError_(f"Unknown operator: {op}", node.line)

    def exec_UnaryOp(self, node: UnaryOp) -> Any:
        """一元运算"""
        operand = self.execute(node.operand)
        if node.op == '-':
            return -operand
        elif node.op == 'not':
            return not self._is_truthy(operand)
        raise RuntimeError_(f"Unknown unary operator: {node.op}", node.line)

    def exec_Assignment(self, node: Assignment) -> Any:
        """赋值：更新环境中的变量"""
        value = self.execute(node.value)
        self.global_env.set(node.name, value)
        return value

    def exec_IndexAccess(self, node: IndexAccess) -> Any:
        """数组下标访问"""
        array = self.execute(node.array)
        index = self.execute(node.index)
        if not isinstance(array, list) and not isinstance(array, str):
            raise RuntimeError_("Cannot index non-array/non-string", node.line)
        if not isinstance(index, int):
            raise RuntimeError_("Index must be an integer", node.line)
        # 支持负数索引
        if index < 0:
            index += len(array)
        if index < 0 or index >= len(array):
            raise RuntimeError_(f"Index out of bounds: {index}", node.line)
        return array[index]

    def exec_IndexAssign(self, node: IndexAssign) -> Any:
        """数组下标赋值: arr[i] = value"""
        array = self.execute(node.array)
        index = self.execute(node.index)
        value = self.execute(node.value)
        if not isinstance(array, list):
            raise RuntimeError_("Cannot index-assign to non-array", node.line)
        if not isinstance(index, int):
            raise RuntimeError_("Index must be an integer", node.line)
        if index < 0:
            index += len(array)
        if index < 0 or index >= len(array):
            raise RuntimeError_(f"Index out of bounds: {index}", node.line)
        array[index] = value
        return value

    def exec_FunctionCall(self, node: FunctionCall) -> Any:
        """函数调用"""
        callee = self.execute(node.callee)
        args = [self.execute(arg) for arg in node.arguments]

        if isinstance(callee, BuiltinFunction):
            return callee.func(args)

        if isinstance(callee, Function):
            return self._call_function(callee, args)

        raise RuntimeError_("Not a callable", node.line)

    def _call_function(self, func: Function, args: list) -> Any:
        """
        调用用户自定义函数。

        关键点：创建新的环境，其父环境是函数的闭包环境（而非当前环境）。
        这样即使函数在不同的地方被调用，它仍然能访问到定义时的变量。
        """
        if len(args) != len(func.params):
            raise RuntimeError_(
                f"Function '{func.name}' expects {len(func.params)} arguments, got {len(args)}"
            )

        # 创建函数执行环境，父环境是闭包环境
        func_env = Environment(parent=func.closure_env)
        for param, arg in zip(func.params, args):
            func_env.define(param, arg)

        # 临时保存全局环境，用函数环境替换
        old_env = self.global_env
        self.global_env = func_env

        result = None
        try:
            for stmt in func.body:
                result = self.execute(stmt)
        except ReturnSignal as ret:
            result = ret.value
        finally:
            self.global_env = old_env

        return result

    def exec_LetStatement(self, node: LetStatement) -> None:
        """变量声明"""
        value = self.execute(node.value)
        self.global_env.define(node.name, value)

    def exec_ExprStatement(self, node: ExprStatement) -> Any:
        """表达式语句"""
        return self.execute(node.expr)

    def exec_ReturnStatement(self, node: ReturnStatement) -> None:
        """return 语句：抛出 ReturnSignal"""
        value = self.execute(node.value) if node.value else None
        raise ReturnSignal(value)

    def exec_BreakStatement(self, node: BreakStatement) -> None:
        """break 语句：抛出 BreakSignal"""
        raise BreakSignal()

    def exec_ContinueStatement(self, node: ContinueStatement) -> None:
        """continue 语句：抛出 ContinueSignal"""
        raise ContinueSignal()

    def exec_IfStatement(self, node: IfStatement) -> Any:
        """
        if/elif/else 语句：
        依次检查条件，执行第一个为真的分支。
        """
        if self._is_truthy(self.execute(node.condition)):
            return self.exec_block(node.then_body)

        for cond, body in node.elif_branches:
            if self._is_truthy(self.execute(cond)):
                return self.exec_block(body)

        if node.else_body:
            return self.exec_block(node.else_body)

    def exec_WhileStatement(self, node: WhileStatement) -> None:
        """while 循环"""
        while self._is_truthy(self.execute(node.condition)):
            try:
                self.exec_block(node.body)
            except BreakSignal:
                break
            except ContinueSignal:
                continue

    def exec_ForStatement(self, node: ForStatement) -> None:
        """for 循环: for i = start, end[, step] { body }"""
        start = self.execute(node.start)
        end = self.execute(node.end)
        step = self.execute(node.step) if node.step else 1

        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)):
            raise RuntimeError_("For loop range must be numbers", node.line)
        if not isinstance(step, (int, float)):
            raise RuntimeError_("For loop step must be a number", node.line)

        i = int(start)
        end_val = int(end)
        step_val = int(step)

        if step_val == 0:
            raise RuntimeError_("For loop step cannot be zero", node.line)

        while (step_val > 0 and i < end_val) or (step_val < 0 and i > end_val):
            self.global_env.define(node.var_name, i)
            try:
                self.exec_block(node.body)
            except BreakSignal:
                break
            except ContinueSignal:
                pass
            i += step_val

    def exec_FunctionDef(self, node: FunctionDef) -> None:
        """
        函数定义：创建函数对象并注册到当前环境。

        注意：函数对象保存了定义时的环境（closure_env），
        这就是闭包能够捕获外部变量的关键。
        """
        func = Function(
            name=node.name,
            params=node.params,
            body=node.body,
            closure_env=self.global_env,  # 捕获当前环境作为闭包环境
        )
        self.global_env.define(node.name, func)

    def exec_block(self, statements: list[ASTNode]) -> Any:
        """执行一组语句"""
        result = None
        for stmt in statements:
            result = self.execute(stmt)
        return result

    def exec_Block(self, node: Block) -> Any:
        """执行 Block 节点"""
        return self.exec_block(node.statements)

    # --- 辅助方法 ---

    @staticmethod
    def _is_truthy(value: Any) -> bool:
        """
        判断值的"真值性"。

        以下值为 falsy：
        - nil (None)
        - false (False)
        - 0
        - "" (空字符串)

        其他值均为 truthy。
        """
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        return True


# =============================================================================
# 第七部分：REPL 和脚本执行
# =============================================================================

def repl():
    """交互式 REPL（Read-Eval-Print Loop）"""
    print("=" * 60)
    print("  Tree-Walking Interpreter REPL")
    print("  输入代码执行，输入 quit 退出")
    print("  输入 :help 查看帮助")
    print("=" * 60)

    interpreter = Interpreter()

    while True:
        try:
            source = input("\n>>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not source:
            continue

        if source.lower() in ("quit", "exit", ":quit", ":exit"):
            print("Goodbye!")
            break

        if source == ":help":
            print("""
支持的语法：
  let x = 10                     # 变量声明
  x = 20                         # 变量赋值
  print(x + 1)                   # 表达式和内置函数
  if x > 5 { ... } else { ... } # 条件语句
  while x > 0 { x = x - 1 }    # while 循环
  for i = 0, 10 { print(i) }    # for 循环
  fn add(a, b) { return a + b } # 函数定义
  add(3, 4)                      # 函数调用
  [1, 2, 3]                      # 数组字面量
  arr[0]                         # 数组下标访问

内置函数：print, println, len, str, int, float, typeof, range,
          input, abs, min, max, push, assert
""")
            continue

        # 如果是单行表达式且没有 let/if/while/for/fn，包装为表达式语句
        # 这样可以支持在 REPL 中直接输入 2 + 3 并看到结果
        try:
            result = interpreter.run(source)
            # 只有当结果不为 None 时才显示
            if result is not None:
                if isinstance(result, bool):
                    print("true" if result else "false")
                elif isinstance(result, float) and result == int(result):
                    print(int(result))
                elif isinstance(result, list):
                    print("[" + ", ".join(str(x) for x in result) + "]")
                else:
                    print(result)
        except LexError as e:
            print(f"  Error: {e}")
        except ParseError as e:
            print(f"  Error: {e}")
        except RuntimeError_ as e:
            print(f"  Error: {e}")
        except Exception as e:
            print(f"  Unexpected error: {e}")


def run_file(filepath: str):
    """执行脚本文件"""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            source = f.read()
    except FileNotFoundError:
        print(f"Error: File not found: {filepath}")
        sys.exit(1)
    except Exception as e:
        print(f"Error reading file: {e}")
        sys.exit(1)

    interpreter = Interpreter()
    try:
        interpreter.run(source, filepath)
    except LexError as e:
        print(f"  Error: {e}")
        sys.exit(1)
    except ParseError as e:
        print(f"  Error: {e}")
        sys.exit(1)
    except RuntimeError_ as e:
        print(f"  Error: {e}")
        sys.exit(1)


# =============================================================================
# 第八部分：示例脚本（内置）
# =============================================================================

EXAMPLE_SCRIPT = """
# ==============================================
# Tree-Walking Interpreter 示例脚本
# ==============================================

# --- 1. 基本运算和变量 ---
println("=== 基本运算 ===")
let a = 10
let b = 3
println("a = ", a, ", b = ", b)
println("a + b = ", a + b)
println("a - b = ", a - b)
println("a * b = ", a * b)
println("a / b = ", a / b)
println("a % b = ", a % b)
println("a ** b = ", a ** b)

# --- 2. 条件语句 ---
println()
println("=== 条件语句 ===")
let x = 42
if x > 100 {
    println(x, " is very large")
} elif x > 10 {
    println(x, " is medium")
} else {
    println(x, " is small")
}

# --- 3. while 循环 ---
println()
println("=== while 循环 ===")
let count = 0
let sum = 0
while count < 10 {
    sum = sum + count
    count = count + 1
}
println("sum(0..9) = ", sum)

# --- 4. for 循环 ---
println()
println("=== for 循环 ===")
let factorial = 1
for i = 1, 11 {
    factorial = factorial * i
}
println("10! = ", factorial)

# --- 5. 函数 ---
println()
println("=== 函数 ===")
fn fibonacci(n) {
    if n <= 1 {
        return n
    }
    return fibonacci(n - 1) + fibonacci(n - 2)
}

print("fibonacci(0..10): ")
for i = 0, 11 {
    print(fibonacci(i), " ")
}
println()

# --- 6. 闭包 ---
println()
println("=== 闭包 ===")
fn make_counter(start) {
    let count = start
    fn increment() {
        count = count + 1
        return count
    }
    return increment
}

let counter = make_counter(0)
println("counter(): ", counter())
println("counter(): ", counter())
println("counter(): ", counter())

# 另一个计数器实例（独立的状态）
let counter2 = make_counter(100)
println("counter2(): ", counter2())
println("counter2(): ", counter2())

# --- 7. 高阶函数 ---
println()
println("=== 高阶函数 ===")
fn apply(f, x) {
    return f(x)
}

fn double(n) {
    return n * 2
}

fn square(n) {
    return n * n
}

println("apply(double, 5) = ", apply(double, 5))
println("apply(square, 5) = ", apply(square, 5))

# --- 8. 数组 ---
println()
println("=== 数组 ===")
let arr = [10, 20, 30, 40, 50]
println("arr = ", arr)
println("arr[0] = ", arr[0])
println("arr[2] = ", arr[2])
println("len(arr) = ", len(arr))

arr[2] = 99
println("arr[2] = 99 → arr = ", arr)

# --- 9. 递归：快速排序 ---
println()
println("=== 快速排序 ===")
fn quicksort(arr) {
    if len(arr) <= 1 {
        return arr
    }
    let pivot = arr[0]
    let less = []
    let greater = []
    for i = 1, len(arr) {
        if arr[i] < pivot {
            push(less, arr[i])
        } else {
            push(greater, arr[i])
        }
    }
    let result = quicksort(less)
    push(result, pivot)
    let right = quicksort(greater)
    for i = 0, len(right) {
        push(result, right[i])
    }
    return result
}

let data = [38, 27, 43, 3, 9, 82, 10]
println("before: ", data)
println("after:  ", quicksort(data))

# --- 10. 字符串操作 ---
println()
println("=== 字符串 ===")
let greeting = "Hello, World!"
println("greeting = ", greeting)
println("len(greeting) = ", len(greeting))
println("greeting[0] = ", greeting[0])
println("greeting[7..] indexing: ", greeting[7])

println()
println("All examples completed!")
"""


# =============================================================================
# 主程序入口
# =============================================================================

def main():
    """主程序入口"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "--example":
            # 运行内置示例脚本
            print("Running built-in example script...\n")
            interpreter = Interpreter()
            try:
                interpreter.run(EXAMPLE_SCRIPT, "<example>")
            except (LexError, ParseError, RuntimeError_) as e:
                print(f"\nError: {e}")
                sys.exit(1)
        else:
            # 执行指定的脚本文件
            run_file(sys.argv[1])
    else:
        # 进入 REPL 模式
        repl()


if __name__ == "__main__":
    main()
