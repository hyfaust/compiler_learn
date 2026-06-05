#!/usr/bin/env python3
"""
bytecode_vm.py - 字节码虚拟机（Bytecode Virtual Machine）

一个完整的字节码编译器 + 栈式虚拟机实现，包括：

  第一部分：字节码定义（操作码枚举和指令格式）
  第二部分：词法分析器和语法分析器（复用 tree_walker.py 的设计）
  第三部分：字节码编译器（AST → 字节码）
  第四部分：栈式虚拟机执行引擎
  第五部分：完整的示例和主程序

功能：
  - 算术运算（+, -, *, /, %）
  - 比较运算（==, !=, <, >, <=, >=）
  - 逻辑运算（and, or, not）
  - 条件跳转（JUMP_IF_FALSE, JUMP_IF_TRUE）
  - 无条件跳转（JUMP）
  - 循环（for, while）
  - 函数调用和返回（CALL, RETURN）
  - 局部变量（LOAD_LOCAL, STORE_LOCAL）
  - 全局变量（LOAD_GLOBAL, STORE_GLOBAL）
  - 数组操作（BUILD_ARRAY, INDEX_GET, INDEX_SET）
  - 详细的执行跟踪输出

运行方式：
  python bytecode_vm.py              # 运行内置示例
  python bytecode_vm.py --no-trace   # 运行示例，不显示跟踪

作者：compiler_learn 教学项目
"""

from __future__ import annotations

import sys
from enum import IntEnum, auto
from dataclasses import dataclass, field
from typing import Any, Optional


# =============================================================================
# 第一部分：字节码定义
# =============================================================================

class Opcode(IntEnum):
    """
    字节码操作码定义。

    每个操作码对应虚拟机的一种基本操作。
    操作码后面可以跟随0个或1个操作数（operand）。
    """
    # ── 栈操作 ──
    NOP = 0             # 空操作
    POP = 1             # 弹出并丢弃栈顶
    DUP = 2             # 复制栈顶

    # ── 常量加载 ──
    LOAD_CONST = 10     # 加载常量到栈顶    LOAD_CONST const_index

    # ── 变量操作 ──
    LOAD_LOCAL = 20     # 加载局部变量      LOAD_LOCAL local_index
    STORE_LOCAL = 21    # 存储到局部变量     STORE_LOCAL local_index
    LOAD_GLOBAL = 22    # 加载全局变量      LOAD_GLOBAL name_index
    STORE_GLOBAL = 23   # 存储到全局变量     STORE_GLOBAL name_index

    # ── 算术运算（全部基于栈，无操作数）──
    ADD = 30            # 加法: b = pop(), a = pop(), push(a + b)
    SUB = 31            # 减法: b = pop(), a = pop(), push(a - b)
    MUL = 32            # 乘法
    DIV = 33            # 除法
    MOD = 34            # 取模
    NEG = 35            # 取负: push(-pop())

    # ── 比较运算 ──
    EQ = 40             # 等于
    NEQ = 41            # 不等于
    LT = 42             # 小于
    GT = 43             # 大于
    LTE = 44            # 小于等于
    GTE = 45            # 大于等于

    # ── 逻辑运算 ──
    NOT = 50            # 逻辑非

    # ── 跳转 ──
    JUMP = 60           # 无条件跳转        JUMP target_address
    JUMP_IF_FALSE = 61  # 栈顶为假则跳转     JUMP_IF_FALSE target_address
    JUMP_IF_TRUE = 62   # 栈顶为真则跳转     JUMP_IF_TRUE target_address
    JUMP_BACK = 63      # 无条件回跳        JUMP_BACK target_address

    # ── 函数 ──
    CALL = 70           # 调用函数          CALL num_args
    RETURN = 71         # 返回              RETURN (返回栈顶值)
    MAKE_FUNCTION = 72  # 创建函数对象       MAKE_FUNCTION name_index, param_count, code_index

    # ── 数组 ──
    BUILD_ARRAY = 80    # 创建数组          BUILD_ARRAY element_count
    INDEX_GET = 81      # 数组下标读取
    INDEX_SET = 82      # 数组下标写入

    # ── 特殊 ──
    PRINT = 90          # 打印栈顶值（调试用）
    HALT = 99           # 停止执行


# 操作码名称映射（用于反汇编显示）
OPCODE_NAMES = {v: v.name for v in Opcode}


def disassemble_instruction(code: list[int], offset: int, constants: list,
                            names: list) -> tuple[str, int]:
    """
    反汇编一条指令，返回 (描述字符串, 下一条指令偏移量)。
    """
    op = code[offset]
    name = OPCODE_NAMES.get(op, f"UNKNOWN({op})")

    # 无操作数指令
    no_operand_ops = {
        Opcode.NOP, Opcode.POP, Opcode.DUP,
        Opcode.ADD, Opcode.SUB, Opcode.MUL, Opcode.DIV, Opcode.MOD, Opcode.NEG,
        Opcode.EQ, Opcode.NEQ, Opcode.LT, Opcode.GT, Opcode.LTE, Opcode.GTE,
        Opcode.NOT, Opcode.INDEX_GET, Opcode.INDEX_SET, Opcode.PRINT, Opcode.HALT,
        Opcode.RETURN,
    }

    if op in no_operand_ops:
        return name, offset + 1

    # 单操作数指令
    single_operand_ops = {
        Opcode.LOAD_CONST: "constants",
        Opcode.LOAD_LOCAL: "locals",
        Opcode.STORE_LOCAL: "locals",
        Opcode.LOAD_GLOBAL: "names",
        Opcode.STORE_GLOBAL: "names",
        Opcode.JUMP: None,
        Opcode.JUMP_IF_FALSE: None,
        Opcode.JUMP_IF_TRUE: None,
        Opcode.JUMP_BACK: None,
        Opcode.CALL: None,
        Opcode.BUILD_ARRAY: None,
    }

    if op in single_operand_ops:
        arg = code[offset + 1]
        if op == Opcode.LOAD_CONST:
            val = constants[arg] if arg < len(constants) else "?"
            return f"{name} {arg} ({val!r})", offset + 2
        elif op in (Opcode.LOAD_GLOBAL, Opcode.STORE_GLOBAL):
            n = names[arg] if arg < len(names) else "?"
            return f"{name} {arg} ({n})", offset + 2
        elif op in (Opcode.JUMP, Opcode.JUMP_IF_FALSE, Opcode.JUMP_IF_TRUE, Opcode.JUMP_BACK):
            return f"{name} -> {arg}", offset + 2
        else:
            return f"{name} {arg}", offset + 2

    # MAKE_FUNCTION 有3个操作数
    if op == Opcode.MAKE_FUNCTION:
        name_idx = code[offset + 1]
        param_count = code[offset + 2]
        code_idx = code[offset + 3]
        n = names[name_idx] if name_idx < len(names) else "?"
        return f"MAKE_FUNCTION {n}({param_count} params) code={code_idx}", offset + 4

    return name, offset + 1


def disassemble(code_obj: CodeObject) -> str:
    """反汇编整个代码对象，返回可读的字符串。"""
    lines = [f"=== Disassembly: {code_obj.name} ==="]
    lines.append(f"  Constants: {code_obj.constants}")
    lines.append(f"  Names:     {code_obj.names}")
    lines.append(f"  Locals:    {code_obj.local_names}")
    lines.append(f"  Num params:{code_obj.num_params}")
    lines.append("")

    offset = 0
    while offset < len(code_obj.code):
        line, next_offset = disassemble_instruction(
            code_obj.code, offset, code_obj.constants, code_obj.names
        )
        lines.append(f"  {offset:4d}  {line}")
        offset = next_offset

    # 反汇编嵌套的函数代码
    for i, const in enumerate(code_obj.constants):
        if isinstance(const, CodeObject):
            lines.append("")
            lines.append(disassemble(const))

    return "\n".join(lines)


@dataclass
class CodeObject:
    """
    代码对象：包含编译后的字节码以及所有元数据。

    这是字节码编译器的输出，也是虚拟机的输入。
    类似于 CPython 的 PyCodeObject。
    """
    name: str = "<module>"              # 代码对象名称
    code: list[int] = field(default_factory=list)       # 字节码指令序列
    constants: list[Any] = field(default_factory=list)   # 常量池
    names: list[str] = field(default_factory=list)       # 名称池（全局变量名、函数名等）
    local_names: list[str] = field(default_factory=list) # 局部变量名
    num_params: int = 0                 # 参数数量

    def add_constant(self, value: Any) -> int:
        """添加常量到常量池，返回索引"""
        for i, c in enumerate(self.constants):
            if c == value and type(c) == type(value):
                return i
        self.constants.append(value)
        return len(self.constants) - 1

    def add_name(self, name: str) -> int:
        """添加名称到名称池，返回索引"""
        for i, n in enumerate(self.names):
            if n == name:
                return i
        self.names.append(name)
        return len(self.names) - 1

    def add_local(self, name: str) -> int:
        """添加局部变量名，返回索引"""
        for i, n in enumerate(self.local_names):
            if n == name:
                return i
        self.local_names.append(name)
        return len(self.local_names) - 1

    def emit(self, *args: int):
        """发射一条指令"""
        for arg in args:
            self.code.append(arg)

    def emit_jump(self, op: Opcode) -> int:
        """发射跳转指令，返回跳转目标的占位位置（稍后回填）"""
        self.emit(op)
        pos = len(self.code)
        self.emit(0)  # 占位符
        return pos

    def patch_jump(self, jump_pos: int):
        """回填跳转目标地址"""
        target = len(self.code)
        self.code[jump_pos] = target

    def current_pos(self) -> int:
        """返回当前代码位置"""
        return len(self.code)


# =============================================================================
# 第二部分：词法分析器和语法分析器（复用 tree_walker.py 的设计）
# =============================================================================

# 导入 tree_walker 模块中的 Token、Lexer、Parser 和 AST 节点
# 这里为了自包含，重新实现一个简化版本

from enum import Enum as _Enum


class TokenType(_Enum):
    """Token 类型"""
    NUMBER = auto()
    STRING = auto()
    TRUE = auto()
    FALSE = auto()
    NIL = auto()
    IDENT = auto()
    LET = auto()
    FN = auto()
    IF = auto()
    ELIF = auto()
    ELSE = auto()
    WHILE = auto()
    FOR = auto()
    RETURN = auto()
    BREAK = auto()
    CONTINUE = auto()
    AND = auto()
    OR = auto()
    NOT = auto()
    PLUS = auto()
    MINUS = auto()
    STAR = auto()
    SLASH = auto()
    PERCENT = auto()
    ASSIGN = auto()
    EQ = auto()
    NEQ = auto()
    LT = auto()
    GT = auto()
    LTE = auto()
    GTE = auto()
    LPAREN = auto()
    RPAREN = auto()
    LBRACE = auto()
    RBRACE = auto()
    LBRACKET = auto()
    RBRACKET = auto()
    COMMA = auto()
    EOF = auto()
    NEWLINE = auto()


_KEYWORDS = {
    "let": TokenType.LET, "fn": TokenType.FN, "if": TokenType.IF,
    "elif": TokenType.ELIF, "else": TokenType.ELSE, "while": TokenType.WHILE,
    "for": TokenType.FOR, "return": TokenType.RETURN, "break": TokenType.BREAK,
    "continue": TokenType.CONTINUE, "and": TokenType.AND, "or": TokenType.OR,
    "not": TokenType.NOT, "true": TokenType.TRUE, "false": TokenType.FALSE,
    "nil": TokenType.NIL,
}


@dataclass
class Token:
    type: TokenType
    value: Any
    line: int


# --- AST 节点 ---

@dataclass
class ASTNode:
    line: int = 0

@dataclass
class NumberLit(ASTNode):
    value: float | int = 0

@dataclass
class StringLit(ASTNode):
    value: str = ""

@dataclass
class BoolLit(ASTNode):
    value: bool = False

@dataclass
class NilLit(ASTNode):
    pass

@dataclass
class ArrayLit(ASTNode):
    elements: list[ASTNode] = field(default_factory=list)

@dataclass
class Ident(ASTNode):
    name: str = ""

@dataclass
class BinOp(ASTNode):
    op: str = ""
    left: ASTNode = field(default_factory=ASTNode)
    right: ASTNode = field(default_factory=ASTNode)

@dataclass
class UnaryOp(ASTNode):
    op: str = ""
    operand: ASTNode = field(default_factory=ASTNode)

@dataclass
class Assign(ASTNode):
    name: str = ""
    value: ASTNode = field(default_factory=ASTNode)

@dataclass
class IndexGet(ASTNode):
    array: ASTNode = field(default_factory=ASTNode)
    index: ASTNode = field(default_factory=ASTNode)

@dataclass
class IndexSet(ASTNode):
    array: ASTNode = field(default_factory=ASTNode)
    index: ASTNode = field(default_factory=ASTNode)
    value: ASTNode = field(default_factory=ASTNode)

@dataclass
class CallExpr(ASTNode):
    callee: ASTNode = field(default_factory=ASTNode)
    args: list[ASTNode] = field(default_factory=list)

@dataclass
class LetStmt(ASTNode):
    name: str = ""
    value: ASTNode = field(default_factory=ASTNode)

@dataclass
class ExprStmt(ASTNode):
    expr: ASTNode = field(default_factory=ASTNode)

@dataclass
class ReturnStmt(ASTNode):
    value: Optional[ASTNode] = None

@dataclass
class BreakStmt(ASTNode):
    pass

@dataclass
class ContinueStmt(ASTNode):
    pass

@dataclass
class IfStmt(ASTNode):
    condition: ASTNode = field(default_factory=ASTNode)
    then_body: list[ASTNode] = field(default_factory=list)
    elif_branches: list[tuple[ASTNode, list[ASTNode]]] = field(default_factory=list)
    else_body: list[ASTNode] = field(default_factory=list)

@dataclass
class WhileStmt(ASTNode):
    condition: ASTNode = field(default_factory=ASTNode)
    body: list[ASTNode] = field(default_factory=list)

@dataclass
class ForStmt(ASTNode):
    var_name: str = ""
    start: ASTNode = field(default_factory=ASTNode)
    end: ASTNode = field(default_factory=ASTNode)
    step: Optional[ASTNode] = None
    body: list[ASTNode] = field(default_factory=list)

@dataclass
class FuncDef(ASTNode):
    name: str = ""
    params: list[str] = field(default_factory=list)
    body: list[ASTNode] = field(default_factory=list)


# --- 简化词法分析器 ---

class SimpleLexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.tokens: list[Token] = []

    def peek(self) -> str:
        return self.source[self.pos] if self.pos < len(self.source) else '\0'

    def advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
        return ch

    def match(self, ch: str) -> bool:
        if self.pos + 1 < len(self.source) and self.source[self.pos + 1] == ch:
            self.advance()
            return True
        return False

    def skip_ws(self):
        while self.pos < len(self.source):
            c = self.peek()
            if c in ' \t\r':
                self.advance()
            elif c == '#':
                while self.pos < len(self.source) and self.peek() != '\n':
                    self.advance()
            elif c == '/' and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == '/':
                while self.pos < len(self.source) and self.peek() != '\n':
                    self.advance()
            else:
                break

    def tokenize(self) -> list[Token]:
        while self.pos < len(self.source):
            self.skip_ws()
            if self.pos >= len(self.source):
                break
            c = self.peek()
            ln = self.line

            if c.isdigit():
                start = self.pos
                has_dot = False
                while self.pos < len(self.source) and (self.peek().isdigit() or self.peek() == '_'):
                    self.advance()
                if self.pos < len(self.source) and self.peek() == '.' and self.pos + 1 < len(self.source) and self.source[self.pos + 1].isdigit():
                    has_dot = True
                    self.advance()
                    while self.pos < len(self.source) and self.peek().isdigit():
                        self.advance()
                text = self.source[start:self.pos].replace('_', '')
                self.tokens.append(Token(TokenType.NUMBER, float(text) if has_dot else int(text), ln))
            elif c in '"\'':
                quote = self.advance()
                buf = []
                while self.pos < len(self.source) and self.peek() != quote:
                    if self.peek() == '\\':
                        self.advance()
                        if self.pos < len(self.source):
                            esc = self.advance()
                            buf.append({'n': '\n', 't': '\t', '\\': '\\', '"': '"', "'": "'"}.get(esc, esc))
                    else:
                        buf.append(self.advance())
                if self.pos < len(self.source):
                    self.advance()
                self.tokens.append(Token(TokenType.STRING, ''.join(buf), ln))
            elif c.isalpha() or c == '_':
                start = self.pos
                while self.pos < len(self.source) and (self.peek().isalnum() or self.peek() == '_'):
                    self.advance()
                text = self.source[start:self.pos]
                tt = _KEYWORDS.get(text, TokenType.IDENT)
                if tt == TokenType.TRUE:
                    self.tokens.append(Token(TokenType.TRUE, True, ln))
                elif tt == TokenType.FALSE:
                    self.tokens.append(Token(TokenType.FALSE, False, ln))
                elif tt == TokenType.NIL:
                    self.tokens.append(Token(TokenType.NIL, None, ln))
                else:
                    self.tokens.append(Token(tt, text, ln))
            elif c == '+':
                self.advance(); self.tokens.append(Token(TokenType.PLUS, '+', ln))
            elif c == '-':
                self.advance(); self.tokens.append(Token(TokenType.MINUS, '-', ln))
            elif c == '*':
                self.advance(); self.tokens.append(Token(TokenType.STAR, '*', ln))
            elif c == '/':
                self.advance(); self.tokens.append(Token(TokenType.SLASH, '/', ln))
            elif c == '%':
                self.advance(); self.tokens.append(Token(TokenType.PERCENT, '%', ln))
            elif c == '=':
                self.advance()
                if self.peek() == '=':
                    self.advance(); self.tokens.append(Token(TokenType.EQ, '==', ln))
                else:
                    self.tokens.append(Token(TokenType.ASSIGN, '=', ln))
            elif c == '!':
                self.advance()
                if self.peek() == '=':
                    self.advance(); self.tokens.append(Token(TokenType.NEQ, '!=', ln))
                else:
                    raise SyntaxError(f"Line {ln}: unexpected '!'")
            elif c == '<':
                self.advance()
                if self.peek() == '=':
                    self.advance(); self.tokens.append(Token(TokenType.LTE, '<=', ln))
                else:
                    self.tokens.append(Token(TokenType.LT, '<', ln))
            elif c == '>':
                self.advance()
                if self.peek() == '=':
                    self.advance(); self.tokens.append(Token(TokenType.GTE, '>=', ln))
                else:
                    self.tokens.append(Token(TokenType.GT, '>', ln))
            elif c == '(':
                self.advance(); self.tokens.append(Token(TokenType.LPAREN, '(', ln))
            elif c == ')':
                self.advance(); self.tokens.append(Token(TokenType.RPAREN, ')', ln))
            elif c == '{':
                self.advance(); self.tokens.append(Token(TokenType.LBRACE, '{', ln))
            elif c == '}':
                self.advance(); self.tokens.append(Token(TokenType.RBRACE, '}', ln))
            elif c == '[':
                self.advance(); self.tokens.append(Token(TokenType.LBRACKET, '[', ln))
            elif c == ']':
                self.advance(); self.tokens.append(Token(TokenType.RBRACKET, ']', ln))
            elif c == ',':
                self.advance(); self.tokens.append(Token(TokenType.COMMA, ',', ln))
            elif c == '\n':
                self.advance(); self.tokens.append(Token(TokenType.NEWLINE, '\\n', ln))
            elif c == ';':
                self.advance()
            else:
                raise SyntaxError(f"Line {ln}: unexpected '{c}'")

        self.tokens.append(Token(TokenType.EOF, None, self.line))
        return self.tokens


# --- 简化语法分析器 ---

class SimpleParser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    def peek(self) -> Token:
        return self.tokens[min(self.pos, len(self.tokens) - 1)]

    def advance(self) -> Token:
        t = self.tokens[self.pos]; self.pos += 1; return t

    def expect(self, tt: TokenType) -> Token:
        t = self.peek()
        if t.type != tt:
            raise SyntaxError(f"Expected {tt.name}, got {t.type.name}")
        return self.advance()

    def match(self, *types: TokenType) -> Optional[Token]:
        if self.peek().type in types:
            return self.advance()
        return None

    def skip_nl(self):
        while self.peek().type == TokenType.NEWLINE:
            self.advance()

    def parse(self) -> list[ASTNode]:
        stmts = []
        self.skip_nl()
        while self.peek().type != TokenType.EOF:
            stmts.append(self.parse_stmt())
            self.skip_nl()
        return stmts

    def parse_stmt(self) -> ASTNode:
        t = self.peek()
        if t.type == TokenType.LET: return self.parse_let()
        if t.type == TokenType.IF: return self.parse_if()
        if t.type == TokenType.WHILE: return self.parse_while()
        if t.type == TokenType.FOR: return self.parse_for()
        if t.type == TokenType.FN: return self.parse_fn()
        if t.type == TokenType.RETURN:
            tok = self.advance()
            val = None
            if self.peek().type not in (TokenType.NEWLINE, TokenType.RBRACE, TokenType.EOF):
                val = self.parse_expr()
            return ReturnStmt(value=val, line=tok.line)
        if t.type == TokenType.BREAK:
            tok = self.advance(); return BreakStmt(line=tok.line)
        if t.type == TokenType.CONTINUE:
            tok = self.advance(); return ContinueStmt(line=tok.line)
        return self.parse_expr_stmt()

    def parse_let(self) -> LetStmt:
        tok = self.expect(TokenType.LET)
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.ASSIGN)
        val = self.parse_expr()
        self.skip_nl()
        return LetStmt(name=name, value=val, line=tok.line)

    def parse_if(self) -> IfStmt:
        tok = self.expect(TokenType.IF)
        cond = self.parse_expr()
        self.skip_nl()
        then_body = self.parse_block()
        elif_b = []
        else_b = []
        self.skip_nl()
        while self.match(TokenType.ELIF):
            ec = self.parse_expr(); self.skip_nl(); eb = self.parse_block()
            elif_b.append((ec, eb)); self.skip_nl()
        if self.match(TokenType.ELSE):
            self.skip_nl(); else_b = self.parse_block()
        return IfStmt(condition=cond, then_body=then_body,
                      elif_branches=elif_b, else_body=else_b, line=tok.line)

    def parse_while(self) -> WhileStmt:
        tok = self.expect(TokenType.WHILE)
        cond = self.parse_expr()
        self.skip_nl()
        body = self.parse_block()
        return WhileStmt(condition=cond, body=body, line=tok.line)

    def parse_for(self) -> ForStmt:
        tok = self.expect(TokenType.FOR)
        var = self.expect(TokenType.IDENT).value
        self.expect(TokenType.ASSIGN)
        start = self.parse_expr()
        self.expect(TokenType.COMMA)
        end = self.parse_expr()
        step = None
        if self.match(TokenType.COMMA):
            step = self.parse_expr()
        self.skip_nl()
        body = self.parse_block()
        return ForStmt(var_name=var, start=start, end=end, step=step, body=body, line=tok.line)

    def parse_fn(self) -> FuncDef:
        tok = self.expect(TokenType.FN)
        name = self.expect(TokenType.IDENT).value
        self.expect(TokenType.LPAREN)
        params = []
        if self.peek().type != TokenType.RPAREN:
            params.append(self.expect(TokenType.IDENT).value)
            while self.match(TokenType.COMMA):
                params.append(self.expect(TokenType.IDENT).value)
        self.expect(TokenType.RPAREN)
        self.skip_nl()
        body = self.parse_block()
        return FuncDef(name=name, params=params, body=body, line=tok.line)

    def parse_expr_stmt(self) -> ExprStmt:
        expr = self.parse_expr()
        if isinstance(expr, Ident) and self.match(TokenType.ASSIGN):
            val = self.parse_expr()
            expr = Assign(name=expr.name, value=val, line=expr.line)
        elif isinstance(expr, IndexGet) and self.match(TokenType.ASSIGN):
            val = self.parse_expr()
            expr = IndexSet(array=expr.array, index=expr.index, value=val, line=expr.line)
        self.skip_nl()
        return ExprStmt(expr=expr, line=expr.line)

    def parse_block(self) -> list[ASTNode]:
        self.expect(TokenType.LBRACE)
        self.skip_nl()
        stmts = []
        while self.peek().type != TokenType.RBRACE:
            stmts.append(self.parse_stmt())
            self.skip_nl()
        self.expect(TokenType.RBRACE)
        return stmts

    def parse_expr(self) -> ASTNode: return self.parse_or()
    def parse_or(self) -> ASTNode:
        left = self.parse_and()
        while self.match(TokenType.OR):
            right = self.parse_and()
            left = BinOp(op='or', left=left, right=right, line=left.line)
        return left
    def parse_and(self) -> ASTNode:
        left = self.parse_eq()
        while self.match(TokenType.AND):
            right = self.parse_eq()
            left = BinOp(op='and', left=left, right=right, line=left.line)
        return left
    def parse_eq(self) -> ASTNode:
        left = self.parse_cmp()
        while (t := self.match(TokenType.EQ, TokenType.NEQ)):
            right = self.parse_cmp()
            left = BinOp(op=t.value, left=left, right=right, line=left.line)
        return left
    def parse_cmp(self) -> ASTNode:
        left = self.parse_add()
        while (t := self.match(TokenType.LT, TokenType.GT, TokenType.LTE, TokenType.GTE)):
            right = self.parse_add()
            left = BinOp(op=t.value, left=left, right=right, line=left.line)
        return left
    def parse_add(self) -> ASTNode:
        left = self.parse_mul()
        while (t := self.match(TokenType.PLUS, TokenType.MINUS)):
            right = self.parse_mul()
            left = BinOp(op=t.value, left=left, right=right, line=left.line)
        return left
    def parse_mul(self) -> ASTNode:
        left = self.parse_unary()
        while (t := self.match(TokenType.STAR, TokenType.SLASH, TokenType.PERCENT)):
            right = self.parse_unary()
            left = BinOp(op=t.value, left=left, right=right, line=left.line)
        return left
    def parse_unary(self) -> ASTNode:
        if (t := self.match(TokenType.MINUS)):
            return UnaryOp(op='-', operand=self.parse_unary(), line=t.line)
        if (t := self.match(TokenType.NOT)):
            return UnaryOp(op='not', operand=self.parse_unary(), line=t.line)
        return self.parse_call()
    def parse_call(self) -> ASTNode:
        expr = self.parse_primary()
        while True:
            if self.match(TokenType.LPAREN):
                args = []
                if self.peek().type != TokenType.RPAREN:
                    args.append(self.parse_expr())
                    while self.match(TokenType.COMMA):
                        args.append(self.parse_expr())
                self.expect(TokenType.RPAREN)
                expr = CallExpr(callee=expr, args=args, line=expr.line)
            elif self.match(TokenType.LBRACKET):
                idx = self.parse_expr()
                self.expect(TokenType.RBRACKET)
                expr = IndexGet(array=expr, index=idx, line=expr.line)
            else:
                break
        return expr
    def parse_primary(self) -> ASTNode:
        t = self.peek()
        if t.type == TokenType.NUMBER:
            self.advance(); return NumberLit(value=t.value, line=t.line)
        if t.type == TokenType.STRING:
            self.advance(); return StringLit(value=t.value, line=t.line)
        if t.type == TokenType.TRUE:
            self.advance(); return BoolLit(value=True, line=t.line)
        if t.type == TokenType.FALSE:
            self.advance(); return BoolLit(value=False, line=t.line)
        if t.type == TokenType.NIL:
            self.advance(); return NilLit(line=t.line)
        if t.type == TokenType.IDENT:
            self.advance(); return Ident(name=t.value, line=t.line)
        if t.type == TokenType.LPAREN:
            self.advance(); expr = self.parse_expr(); self.expect(TokenType.RPAREN); return expr
        if t.type == TokenType.LBRACKET:
            return self.parse_array()
        raise SyntaxError(f"Unexpected token: {t.type.name}")
    def parse_array(self) -> ArrayLit:
        tok = self.expect(TokenType.LBRACKET)
        elems = []
        if self.peek().type != TokenType.RBRACKET:
            elems.append(self.parse_expr())
            while self.match(TokenType.COMMA):
                if self.peek().type == TokenType.RBRACKET: break
                elems.append(self.parse_expr())
        self.expect(TokenType.RBRACKET)
        return ArrayLit(elements=elems, line=tok.line)


# =============================================================================
# 第三部分：字节码编译器（AST → 字节码）
# =============================================================================

class CompileError(Exception):
    def __init__(self, message: str, line: int = 0):
        super().__init__(f"CompileError at line {line}: {message}")
        self.line = line


class Compiler:
    """
    字节码编译器：将 AST 编译为字节码。

    编译过程是深度优先遍历 AST，对每种节点类型生成对应的字节码。
    """

    def __init__(self):
        self.code_objects: list[CodeObject] = []
        self.current: Optional[CodeObject] = None
        self.loop_stack: list[tuple[int, list[int]]] = []  # (loop_start, break_patches)

    def compile(self, ast: list[ASTNode]) -> CodeObject:
        """编译整个程序，返回主代码对象"""
        self.current = CodeObject(name="<module>")
        self.code_objects.append(self.current)
        self._compile_stmts(ast)
        self.current.emit(Opcode.HALT)
        return self.current

    def _compile_stmts(self, stmts: list[ASTNode]):
        for stmt in stmts:
            self._compile_stmt(stmt)

    def _compile_stmt(self, node: ASTNode):
        """编译一条语句"""
        if isinstance(node, LetStmt):
            self._compile_let(node)
        elif isinstance(node, ExprStmt):
            # Assign 和 IndexSet 不产生栈值，直接编译为语句
            if isinstance(node.expr, Assign):
                self._compile_assign(node.expr)
            elif isinstance(node.expr, IndexSet):
                self._compile_index_set(node.expr)
            else:
                self._compile_expr(node.expr)
                self.current.emit(Opcode.POP)  # 丢弃表达式的值
        elif isinstance(node, ReturnStmt):
            self._compile_return(node)
        elif isinstance(node, IfStmt):
            self._compile_if(node)
        elif isinstance(node, WhileStmt):
            self._compile_while(node)
        elif isinstance(node, ForStmt):
            self._compile_for(node)
        elif isinstance(node, FuncDef):
            self._compile_funcdef(node)
        elif isinstance(node, BreakStmt):
            self._compile_break(node)
        elif isinstance(node, ContinueStmt):
            self._compile_continue(node)
        elif isinstance(node, Assign):
            self._compile_assign(node)
        elif isinstance(node, IndexSet):
            self._compile_index_set(node)
        else:
            raise CompileError(f"Unknown statement type: {type(node).__name__}", getattr(node, 'line', 0))

    def _compile_expr(self, node: ASTNode):
        """编译一个表达式（将结果压入栈顶）"""
        if isinstance(node, NumberLit):
            idx = self.current.add_constant(node.value)
            self.current.emit(Opcode.LOAD_CONST, idx)
        elif isinstance(node, StringLit):
            idx = self.current.add_constant(node.value)
            self.current.emit(Opcode.LOAD_CONST, idx)
        elif isinstance(node, BoolLit):
            idx = self.current.add_constant(node.value)
            self.current.emit(Opcode.LOAD_CONST, idx)
        elif isinstance(node, NilLit):
            idx = self.current.add_constant(None)
            self.current.emit(Opcode.LOAD_CONST, idx)
        elif isinstance(node, ArrayLit):
            for elem in node.elements:
                self._compile_expr(elem)
            self.current.emit(Opcode.BUILD_ARRAY, len(node.elements))
        elif isinstance(node, Ident):
            self._compile_load_var(node.name, node.line)
        elif isinstance(node, BinOp):
            self._compile_binop(node)
        elif isinstance(node, UnaryOp):
            self._compile_unaryop(node)
        elif isinstance(node, CallExpr):
            self._compile_call(node)
        elif isinstance(node, IndexGet):
            self._compile_index_get(node)
        elif isinstance(node, IndexSet):
            self._compile_index_set(node)
        elif isinstance(node, Assign):
            self._compile_assign_expr(node)
        else:
            raise CompileError(f"Unknown expression type: {type(node).__name__}", getattr(node, 'line', 0))

    def _compile_load_var(self, name: str, line: int):
        """加载变量：先查局部变量，再查全局变量"""
        if name in self.current.local_names:
            idx = self.current.local_names.index(name)
            self.current.emit(Opcode.LOAD_LOCAL, idx)
        else:
            idx = self.current.add_name(name)
            self.current.emit(Opcode.LOAD_GLOBAL, idx)

    def _compile_store_var(self, name: str, line: int):
        """存储变量：先查局部变量，再查全局变量"""
        if name in self.current.local_names:
            idx = self.current.local_names.index(name)
            self.current.emit(Opcode.STORE_LOCAL, idx)
        else:
            idx = self.current.add_name(name)
            self.current.emit(Opcode.STORE_GLOBAL, idx)

    def _is_module_level(self) -> bool:
        """判断当前是否在模块级别编译（非函数内部）"""
        return self.current.num_params == 0 and self.current.name == "<module>"

    def _compile_let(self, node: LetStmt):
        """编译 let 声明"""
        self._compile_expr(node.value)
        if self._is_module_level():
            # 模块级别：使用全局变量
            idx = self.current.add_name(node.name)
            self.current.emit(Opcode.STORE_GLOBAL, idx)
        else:
            # 函数内部：使用局部变量
            if node.name not in self.current.local_names:
                self.current.add_local(node.name)
            idx = self.current.local_names.index(node.name)
            self.current.emit(Opcode.STORE_LOCAL, idx)

    def _compile_assign(self, node: Assign):
        """编译赋值语句"""
        self._compile_expr(node.value)
        self._compile_store_var(node.name, node.line)

    def _compile_assign_expr(self, node: Assign):
        """编译赋值表达式（结果也留在栈上）"""
        self._compile_expr(node.value)
        self.current.emit(Opcode.DUP)
        self._compile_store_var(node.name, node.line)

    def _compile_binop(self, node: BinOp):
        """编译二元运算"""
        # 短路求值
        if node.op == 'and':
            self._compile_expr(node.left)
            self.current.emit(Opcode.DUP)
            end_jump = self.current.emit_jump(Opcode.JUMP_IF_FALSE)
            self.current.emit(Opcode.POP)
            self._compile_expr(node.right)
            self.current.patch_jump(end_jump)
            return
        if node.op == 'or':
            self._compile_expr(node.left)
            self.current.emit(Opcode.DUP)
            end_jump = self.current.emit_jump(Opcode.JUMP_IF_TRUE)
            self.current.emit(Opcode.POP)
            self._compile_expr(node.right)
            self.current.patch_jump(end_jump)
            return

        self._compile_expr(node.left)
        self._compile_expr(node.right)

        op_map = {
            '+': Opcode.ADD, '-': Opcode.SUB, '*': Opcode.MUL,
            '/': Opcode.DIV, '%': Opcode.MOD,
            '==': Opcode.EQ, '!=': Opcode.NEQ,
            '<': Opcode.LT, '>': Opcode.GT,
            '<=': Opcode.LTE, '>=': Opcode.GTE,
        }
        if node.op in op_map:
            self.current.emit(op_map[node.op])
        else:
            raise CompileError(f"Unknown operator: {node.op}", node.line)

    def _compile_unaryop(self, node: UnaryOp):
        """编译一元运算"""
        self._compile_expr(node.operand)
        if node.op == '-':
            self.current.emit(Opcode.NEG)
        elif node.op == 'not':
            self.current.emit(Opcode.NOT)
        else:
            raise CompileError(f"Unknown unary operator: {node.op}", node.line)

    def _compile_call(self, node: CallExpr):
        """编译函数调用（callee 先入栈，然后参数入栈）"""
        self._compile_expr(node.callee)
        for arg in node.args:
            self._compile_expr(arg)
        self.current.emit(Opcode.CALL, len(node.args))

    def _compile_if(self, node: IfStmt):
        """
        编译 if 语句。

        字节码结构：
          条件表达式
          JUMP_IF_FALSE -> elif/else
          then_body
          JUMP -> end
          elif/else_body
          end:
        """
        self._compile_expr(node.condition)
        else_jump = self.current.emit_jump(Opcode.JUMP_IF_FALSE)
        self._compile_stmts(node.then_body)

        end_jumps = []
        end_jumps.append(self.current.emit_jump(Opcode.JUMP))

        self.current.patch_jump(else_jump)

        for cond, body in node.elif_branches:
            self._compile_expr(cond)
            elif_jump = self.current.emit_jump(Opcode.JUMP_IF_FALSE)
            self._compile_stmts(body)
            end_jumps.append(self.current.emit_jump(Opcode.JUMP))
            self.current.patch_jump(elif_jump)

        if node.else_body:
            self._compile_stmts(node.else_body)

        for jmp in end_jumps:
            self.current.patch_jump(jmp)

    def _compile_while(self, node: WhileStmt):
        """
        编译 while 循环。

        字节码结构：
          loop_start:
            条件表达式
            JUMP_IF_FALSE -> loop_end
            body
            JUMP_BACK -> loop_start
          loop_end:
        """
        loop_start = self.current.current_pos()
        self.loop_stack.append((loop_start, []))

        self._compile_expr(node.condition)
        exit_jump = self.current.emit_jump(Opcode.JUMP_IF_FALSE)

        self._compile_stmts(node.body)
        self.current.emit(Opcode.JUMP_BACK, loop_start)

        self.current.patch_jump(exit_jump)

        # 回填所有 break 跳转
        _, break_patches = self.loop_stack.pop()
        for bp in break_patches:
            self.current.code[bp] = self.current.current_pos()

    def _compile_for(self, node: ForStmt):
        """
        编译 for 循环: for i = start, end, step { body }

        字节码结构：
          LOAD start; STORE i
          loop_start:
            LOAD i; LOAD end; LT (或 GT)
            JUMP_IF_FALSE -> loop_end
            body
            LOAD i; LOAD step; ADD; STORE i
            JUMP_BACK -> loop_start
          loop_end:
        """
        # 初始化循环变量
        self._compile_expr(node.start)
        if self._is_module_level():
            # 模块级：循环变量存在全局
            if node.var_name not in [self.current.names[i] for i in range(len(self.current.names))]:
                self.current.add_name(node.var_name)
            name_idx = self.current.names.index(node.var_name) if node.var_name in self.current.names else self.current.add_name(node.var_name)
            self.current.emit(Opcode.STORE_GLOBAL, name_idx)
            use_global = True
        else:
            if node.var_name not in self.current.local_names:
                self.current.add_local(node.var_name)
            var_idx = self.current.local_names.index(node.var_name)
            self.current.emit(Opcode.STORE_LOCAL, var_idx)
            use_global = False

        loop_start = self.current.current_pos()
        self.loop_stack.append((loop_start, []))

        # 条件检查: i < end (step > 0) 或 i > end (step < 0)
        if use_global:
            self.current.emit(Opcode.LOAD_GLOBAL, name_idx)
        else:
            self.current.emit(Opcode.LOAD_LOCAL, var_idx)
        self._compile_expr(node.end)

        # 默认 step = 1，所以用 <
        # 如果 step 是负数常量，用 >
        use_gt = False
        if node.step and isinstance(node.step, NumberLit) and node.step.value < 0:
            use_gt = True

        self.current.emit(Opcode.LT if not use_gt else Opcode.GT)
        exit_jump = self.current.emit_jump(Opcode.JUMP_IF_FALSE)

        # 循环体
        self._compile_stmts(node.body)

        # i = i + step
        if use_global:
            self.current.emit(Opcode.LOAD_GLOBAL, name_idx)
        else:
            self.current.emit(Opcode.LOAD_LOCAL, var_idx)
        if node.step:
            self._compile_expr(node.step)
        else:
            idx = self.current.add_constant(1)
            self.current.emit(Opcode.LOAD_CONST, idx)
        self.current.emit(Opcode.ADD)
        if use_global:
            self.current.emit(Opcode.STORE_GLOBAL, name_idx)
        else:
            self.current.emit(Opcode.STORE_LOCAL, var_idx)

        # 跳回循环开始
        self.current.emit(Opcode.JUMP_BACK, loop_start)

        self.current.patch_jump(exit_jump)

        # 回填 break
        _, break_patches = self.loop_stack.pop()
        for bp in break_patches:
            self.current.code[bp] = self.current.current_pos()

    def _compile_return(self, node: ReturnStmt):
        """编译 return 语句"""
        if node.value:
            self._compile_expr(node.value)
        else:
            idx = self.current.add_constant(None)
            self.current.emit(Opcode.LOAD_CONST, idx)
        self.current.emit(Opcode.RETURN)

    def _compile_break(self, node: BreakStmt):
        """编译 break 语句"""
        if not self.loop_stack:
            raise CompileError("break outside of loop", node.line)
        pos = self.current.emit_jump(Opcode.JUMP)
        self.loop_stack[-1][1].append(pos)

    def _compile_continue(self, node: ContinueStmt):
        """编译 continue 语句"""
        if not self.loop_stack:
            raise CompileError("continue outside of loop", node.line)
        loop_start = self.loop_stack[-1][0]
        self.current.emit(Opcode.JUMP_BACK, loop_start)

    def _compile_funcdef(self, node: FuncDef):
        """
        编译函数定义。

        1. 创建新的代码对象
        2. 将参数注册为局部变量
        3. 编译函数体
        4. 在父代码对象中发射 MAKE_FUNCTION 指令
        """
        # 保存当前代码对象
        parent = self.current

        # 创建新代码对象
        func_code = CodeObject(name=node.name, num_params=len(node.params))
        self.code_objects.append(func_code)
        self.current = func_code

        # 注册参数为局部变量
        for param in node.params:
            func_code.add_local(param)

        # 编译函数体
        self._compile_stmts(node.body)

        # 如果函数没有显式 return，添加隐式 return nil
        func_code.emit(Opcode.LOAD_CONST, func_code.add_constant(None))
        func_code.emit(Opcode.RETURN)

        # 恢复父代码对象
        self.current = parent

        # 在父代码对象中添加函数代码对象到常量池
        code_idx = self.current.add_constant(func_code)
        name_idx = self.current.add_name(node.name)
        self.current.emit(Opcode.MAKE_FUNCTION, name_idx, len(node.params), code_idx)
        # 存储函数：模块级别用全局变量，函数内部用局部变量
        if self._is_module_level():
            self.current.emit(Opcode.STORE_GLOBAL, name_idx)
        else:
            if node.name not in self.current.local_names:
                self.current.add_local(node.name)
            idx = self.current.local_names.index(node.name)
            self.current.emit(Opcode.STORE_LOCAL, idx)

    def _compile_index_get(self, node: IndexGet):
        """编译数组下标读取"""
        self._compile_expr(node.array)
        self._compile_expr(node.index)
        self.current.emit(Opcode.INDEX_GET)

    def _compile_index_set(self, node: IndexSet):
        """编译数组下标写入"""
        self._compile_expr(node.array)
        self._compile_expr(node.index)
        self._compile_expr(node.value)
        self.current.emit(Opcode.INDEX_SET)


# =============================================================================
# 第四部分：栈式虚拟机执行引擎
# =============================================================================

@dataclass
class Closure:
    """函数闭包对象"""
    code: CodeObject
    name: str

    def __repr__(self):
        return f"<closure {self.name}>"


class VMError(Exception):
    def __init__(self, message: str):
        super().__init__(message)


class VM:
    """
    栈式虚拟机：执行字节码。

    工作原理：
    1. 维护一个操作数栈（operand stack）
    2. 维护一个调用栈（call stack）用于函数调用
    3. 逐条读取并执行字节码指令
    4. 指令通过压栈/弹栈操作来传递数据

    状态变量：
    - stack: 操作数栈
    - sp: 栈指针（指向栈顶的下一个位置）
    - call_stack: 调用栈（保存函数调用时的状态）
    - globals: 全局变量字典
    - code: 当前正在执行的代码对象
    - pc: 程序计数器（Program Counter）
    - bp: 基址指针（Base Pointer）—— 当前栈帧在操作数栈中的起始位置
    """

    def __init__(self, trace: bool = True):
        self.trace = trace          # 是否显示执行跟踪
        self.stack: list[Any] = []  # 操作数栈
        self.call_stack: list[dict] = []  # 调用栈
        self.globals: dict[str, Any] = {}  # 全局变量
        self.code: Optional[CodeObject] = None
        self.pc: int = 0            # 程序计数器
        self.bp: int = 0            # 基址指针
        self.step_count: int = 0    # 执行步数

    def run(self, code_obj: CodeObject):
        """运行代码对象"""
        self.code = code_obj
        self.pc = 0
        self.bp = 0
        self.stack.clear()
        self.call_stack.clear()
        self.globals.clear()
        self.step_count = 0

        if self.trace:
            print("\n" + "=" * 70)
            print("  BYTECODE VM EXECUTION TRACE")
            print("=" * 70)
            print(disassemble(code_obj))
            print("\n--- Execution ---\n")

        self._execute()

    def push(self, value: Any):
        """压入栈顶"""
        self.stack.append(value)

    def pop(self) -> Any:
        """弹出栈顶"""
        if not self.stack:
            raise VMError("Stack underflow")
        return self.stack.pop()

    def peek(self) -> Any:
        """查看栈顶"""
        if not self.stack:
            raise VMError("Stack underflow")
        return self.stack[-1]

    def _trace_op(self, name: str, detail: str = ""):
        """打印执行跟踪"""
        if self.trace:
            stack_str = [str(v) if not isinstance(v, (list, Closure)) else repr(v) for v in self.stack]
            self.step_count += 1
            print(f"  [{self.step_count:4d}] pc={self.pc:4d}  {name:20s} {detail:30s}  stack=[{', '.join(stack_str)}]")

    def _execute(self):
        """主执行循环"""
        while True:
            if self.pc >= len(self.code.code):
                break

            opcode = self.code.code[self.pc]

            if opcode == Opcode.NOP:
                self._trace_op("NOP")
                self.pc += 1

            elif opcode == Opcode.POP:
                val = self.pop()
                self._trace_op("POP", f"popped={self._fmt(val)}")
                self.pc += 1

            elif opcode == Opcode.DUP:
                self.push(self.peek())
                self._trace_op("DUP")
                self.pc += 1

            elif opcode == Opcode.LOAD_CONST:
                idx = self.code.code[self.pc + 1]
                val = self.code.constants[idx]
                self.push(val)
                self._trace_op("LOAD_CONST", f"[{idx}]={self._fmt(val)}")
                self.pc += 2

            elif opcode == Opcode.LOAD_LOCAL:
                idx = self.code.code[self.pc + 1]
                val = self.stack[self.bp + idx]
                self.push(val)
                name = self.code.local_names[idx] if idx < len(self.code.local_names) else "?"
                self._trace_op("LOAD_LOCAL", f"slot={idx}({name}) val={self._fmt(val)}")
                self.pc += 2

            elif opcode == Opcode.STORE_LOCAL:
                idx = self.code.code[self.pc + 1]
                val = self.pop()
                # 确保栈足够大
                while len(self.stack) <= self.bp + idx:
                    self.stack.append(None)
                self.stack[self.bp + idx] = val
                name = self.code.local_names[idx] if idx < len(self.code.local_names) else "?"
                self._trace_op("STORE_LOCAL", f"slot={idx}({name}) val={self._fmt(val)}")
                self.pc += 2

            elif opcode == Opcode.LOAD_GLOBAL:
                idx = self.code.code[self.pc + 1]
                name = self.code.names[idx]
                if name not in self.globals:
                    raise VMError(f"Undefined global variable: '{name}'")
                val = self.globals[name]
                self.push(val)
                self._trace_op("LOAD_GLOBAL", f"'{name}'={self._fmt(val)}")
                self.pc += 2

            elif opcode == Opcode.STORE_GLOBAL:
                idx = self.code.code[self.pc + 1]
                name = self.code.names[idx]
                val = self.pop()
                self.globals[name] = val
                self._trace_op("STORE_GLOBAL", f"'{name}'={self._fmt(val)}")
                self.pc += 2

            elif opcode == Opcode.ADD:
                b, a = self.pop(), self.pop()
                self.push(a + b)
                self._trace_op("ADD", f"{self._fmt(a)} + {self._fmt(b)} = {self._fmt(a+b)}")
                self.pc += 1

            elif opcode == Opcode.SUB:
                b, a = self.pop(), self.pop()
                self.push(a - b)
                self._trace_op("SUB", f"{self._fmt(a)} - {self._fmt(b)} = {self._fmt(a-b)}")
                self.pc += 1

            elif opcode == Opcode.MUL:
                b, a = self.pop(), self.pop()
                self.push(a * b)
                self._trace_op("MUL", f"{self._fmt(a)} * {self._fmt(b)} = {self._fmt(a*b)}")
                self.pc += 1

            elif opcode == Opcode.DIV:
                b, a = self.pop(), self.pop()
                if b == 0:
                    raise VMError("Division by zero")
                self.push(a / b)
                self._trace_op("DIV", f"{self._fmt(a)} / {self._fmt(b)}")
                self.pc += 1

            elif opcode == Opcode.MOD:
                b, a = self.pop(), self.pop()
                if b == 0:
                    raise VMError("Modulo by zero")
                self.push(a % b)
                self._trace_op("MOD", f"{self._fmt(a)} % {self._fmt(b)}")
                self.pc += 1

            elif opcode == Opcode.NEG:
                a = self.pop()
                self.push(-a)
                self._trace_op("NEG", f"-{self._fmt(a)}")
                self.pc += 1

            elif opcode == Opcode.EQ:
                b, a = self.pop(), self.pop()
                self.push(a == b)
                self._trace_op("EQ", f"{self._fmt(a)} == {self._fmt(b)} → {a == b}")
                self.pc += 1

            elif opcode == Opcode.NEQ:
                b, a = self.pop(), self.pop()
                self.push(a != b)
                self._trace_op("NEQ", f"{self._fmt(a)} != {self._fmt(b)} → {a != b}")
                self.pc += 1

            elif opcode == Opcode.LT:
                b, a = self.pop(), self.pop()
                self.push(a < b)
                self._trace_op("LT", f"{self._fmt(a)} < {self._fmt(b)} → {a < b}")
                self.pc += 1

            elif opcode == Opcode.GT:
                b, a = self.pop(), self.pop()
                self.push(a > b)
                self._trace_op("GT", f"{self._fmt(a)} > {self._fmt(b)} → {a > b}")
                self.pc += 1

            elif opcode == Opcode.LTE:
                b, a = self.pop(), self.pop()
                self.push(a <= b)
                self._trace_op("LTE", f"{self._fmt(a)} <= {self._fmt(b)} → {a <= b}")
                self.pc += 1

            elif opcode == Opcode.GTE:
                b, a = self.pop(), self.pop()
                self.push(a >= b)
                self._trace_op("GTE", f"{self._fmt(a)} >= {self._fmt(b)} → {a >= b}")
                self.pc += 1

            elif opcode == Opcode.NOT:
                a = self.pop()
                self.push(not self._is_truthy(a))
                self._trace_op("NOT", f"not {self._fmt(a)}")
                self.pc += 1

            elif opcode == Opcode.JUMP:
                target = self.code.code[self.pc + 1]
                self._trace_op("JUMP", f"-> {target}")
                self.pc = target

            elif opcode == Opcode.JUMP_IF_FALSE:
                target = self.code.code[self.pc + 1]
                cond = self.pop()
                if not self._is_truthy(cond):
                    self._trace_op("JUMP_IF_FALSE", f"{self._fmt(cond)} is falsy -> {target}")
                    self.pc = target
                else:
                    self._trace_op("JUMP_IF_FALSE", f"{self._fmt(cond)} is truthy, continue")
                    self.pc += 2

            elif opcode == Opcode.JUMP_IF_TRUE:
                target = self.code.code[self.pc + 1]
                cond = self.pop()
                if self._is_truthy(cond):
                    self._trace_op("JUMP_IF_TRUE", f"{self._fmt(cond)} is truthy -> {target}")
                    self.pc = target
                else:
                    self._trace_op("JUMP_IF_TRUE", f"{self._fmt(cond)} is falsy, continue")
                    self.pc += 2

            elif opcode == Opcode.JUMP_BACK:
                target = self.code.code[self.pc + 1]
                self._trace_op("JUMP_BACK", f"-> {target}")
                self.pc = target

            elif opcode == Opcode.CALL:
                num_args = self.code.code[self.pc + 1]
                self._trace_op("CALL", f"{num_args} args")
                self._call_function(num_args)

            elif opcode == Opcode.RETURN:
                val = self.pop()
                self._trace_op("RETURN", f"returning {self._fmt(val)}")
                if not self.call_stack:
                    # 主程序返回
                    if self.trace:
                        print(f"\n  === VM HALTED ===  result = {self._fmt(val)}")
                        print(f"  Total steps: {self.step_count}")
                    return val
                # 恢复调用者的状态
                frame = self.call_stack.pop()
                # 清除被调用函数的局部变量（栈回卷到调用前的状态）
                self.stack = self.stack[:self.bp]
                self.code = frame['code']
                self.pc = frame['pc']
                self.bp = frame['bp']
                self.push(val)

            elif opcode == Opcode.MAKE_FUNCTION:
                name_idx = self.code.code[self.pc + 1]
                param_count = self.code.code[self.pc + 2]
                code_idx = self.code.code[self.pc + 3]
                func_code = self.code.constants[code_idx]
                func_name = self.code.names[name_idx]
                closure = Closure(code=func_code, name=func_name)
                self.push(closure)
                self._trace_op("MAKE_FUNCTION", f"{func_name}({param_count} params)")
                self.pc += 4

            elif opcode == Opcode.BUILD_ARRAY:
                count = self.code.code[self.pc + 1]
                arr = []
                for _ in range(count):
                    arr.append(self.pop())
                arr.reverse()
                self.push(arr)
                self._trace_op("BUILD_ARRAY", f"{count} elements -> {self._fmt(arr)}")
                self.pc += 2

            elif opcode == Opcode.INDEX_GET:
                index = self.pop()
                array = self.pop()
                if not isinstance(index, int):
                    raise VMError("Index must be an integer")
                if isinstance(array, (list, str)):
                    if index < 0:
                        index += len(array)
                    if index < 0 or index >= len(array):
                        raise VMError(f"Index out of bounds: {index}")
                    self.push(array[index])
                    self._trace_op("INDEX_GET", f"{self._fmt(array)}[{index}] = {self._fmt(array[index])}")
                else:
                    raise VMError("Cannot index non-array/non-string")
                self.pc += 1

            elif opcode == Opcode.INDEX_SET:
                value = self.pop()
                index = self.pop()
                array = self.pop()
                if not isinstance(index, int):
                    raise VMError("Index must be an integer")
                if isinstance(array, list):
                    if index < 0:
                        index += len(array)
                    if index < 0 or index >= len(array):
                        raise VMError(f"Index out of bounds: {index}")
                    array[index] = value
                    self._trace_op("INDEX_SET", f"[{index}] = {self._fmt(value)}")
                else:
                    raise VMError("Cannot index-set on non-array")
                self.pc += 1

            elif opcode == Opcode.PRINT:
                val = self.pop()
                self._trace_op("PRINT", f"{self._fmt(val)}")
                print(self._fmt(val))
                self.pc += 1

            elif opcode == Opcode.HALT:
                self._trace_op("HALT")
                if self.trace:
                    print(f"\n  === VM HALTED ===")
                    print(f"  Total steps: {self.step_count}")
                    if self.stack:
                        print(f"  Final stack: {[self._fmt(v) for v in self.stack]}")
                return None

            else:
                raise VMError(f"Unknown opcode: {opcode} at pc={self.pc}")

    def _call_function(self, num_args: int):
        """调用函数"""
        # 弹出参数（从右到左）
        args = []
        for _ in range(num_args):
            args.append(self.pop())
        args.reverse()

        # 弹出函数对象
        callee = self.pop()

        if isinstance(callee, Closure):
            if len(args) != callee.code.num_params:
                raise VMError(
                    f"Function '{callee.name}' expects {callee.code.num_params} args, got {len(args)}"
                )
            # 保存当前状态到调用栈
            self.call_stack.append({
                'code': self.code,
                'pc': self.pc + 2,  # 返回到 CALL 的下一条指令
                'bp': self.bp,
            })
            # 切换到新函数
            self.code = callee.code
            self.pc = 0
            self.bp = len(self.stack)
            # 将参数压入栈（作为局部变量的前几个槽位）
            for arg in args:
                self.push(arg)
        else:
            raise VMError(f"Not callable: {callee}")

    @staticmethod
    def _is_truthy(value: Any) -> bool:
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

    @staticmethod
    def _fmt(value: Any) -> str:
        if value is None:
            return "nil"
        if isinstance(value, bool):
            return "true" if value else "false"
        if isinstance(value, float) and value == int(value):
            return str(int(value))
        if isinstance(value, list):
            return "[" + ", ".join(VM._fmt(v) for v in value) + "]"
        if isinstance(value, Closure):
            return repr(value)
        return str(value)


# =============================================================================
# 第五部分：主程序和示例
# =============================================================================

EXAMPLE_PROGRAM = """
# ==============================================
# Bytecode VM 示例程序
# ==============================================

# --- 1. 基本算术 ---
let a = 10
let b = 3
let result = a + b * 2

# --- 2. 条件语句 ---
let x = 42
let category = 0
if x > 100 {
    category = 3
} elif x > 10 {
    category = 2
} else {
    category = 1
}

# --- 3. while 循环 ---
let sum = 0
let i = 0
while i < 5 {
    sum = sum + i
    i = i + 1
}

# --- 4. for 循环 ---
let factorial = 1
for j = 1, 7 {
    factorial = factorial * j
}

# --- 5. 函数定义和调用 ---
fn square(n) {
    return n * n
}

fn add(a, b) {
    return a + b
}

let sq = square(6)
let total = add(100, 200)

# --- 6. 递归 ---
fn fib(n) {
    if n <= 1 {
        return n
    }
    return fib(n - 1) + fib(n - 2)
}

let fib8 = fib(8)

# --- 7. 数组 ---
let arr = [10, 20, 30, 40, 50]
let first = arr[0]
let third = arr[2]
arr[1] = 99
"""


def main():
    """主程序"""
    trace = True
    if "--no-trace" in sys.argv:
        trace = False

    print("=" * 70)
    print("  Bytecode Virtual Machine")
    print("  A complete compiler + stack-based VM implementation")
    print("=" * 70)

    # 步骤1：词法分析
    print("\n[Step 1] Lexing...")
    lexer = SimpleLexer(EXAMPLE_PROGRAM)
    tokens = lexer.tokenize()
    print(f"  Generated {len(tokens)} tokens")

    # 步骤2：语法分析
    print("\n[Step 2] Parsing...")
    parser = SimpleParser(tokens)
    ast = parser.parse()
    print(f"  Generated {len(ast)} AST nodes")

    # 步骤3：编译为字节码
    print("\n[Step 3] Compiling to bytecode...")
    compiler = Compiler()
    code_obj = compiler.compile(ast)
    print(f"  Generated {len(code_obj.code)} bytes of bytecode")
    print(f"  Constants: {len(code_obj.constants)}")
    print(f"  Names: {len(code_obj.names)}")
    print(f"  Locals: {len(code_obj.local_names)}")

    # 显示反汇编
    print("\n[Disassembly]")
    print(disassemble(code_obj))

    # 步骤4：执行字节码
    print("\n[Step 4] Executing bytecode...\n")
    vm = VM(trace=trace)
    vm.run(code_obj)

    # 显示最终的全局变量状态
    print("\n[Final Global Variables]")
    for name, val in sorted(vm.globals.items()):
        print(f"  {name} = {VM._fmt(val)}")


if __name__ == "__main__":
    main()
