"""
TinyLang 编译器主文件

一个小型教学语言的完整编译器前端，包含：
- Token 类型定义和词法分析器 (Lexer)
- 递归下降语法分析器 (Parser)
- AST 节点定义
- 字节码编译器 (将 AST 编译为栈式字节码)

TinyLang 语法示例：
    let x = 10;
    let y = x * 2 + 5;
    print(y);  // 25

    if (x > 5) {
        print("big");
    } else {
        print("small");
    }

    fn factorial(n) {
        if (n <= 1) return 1;
        return n * factorial(n - 1);
    }
    print(factorial(5));  // 120

用法：
    python tinylang.py <file.tl>              # 编译并显示字节码
    python tinylang.py --interpret <file.tl>  # 使用解释器执行
"""

from enum import Enum, IntEnum
from dataclasses import dataclass, field
from typing import Any, Optional
import sys as _sys

# 将当前模块注册到 sys.modules，使其他文件能通过相同名称导入
_tinylang_mod_key = "_tinylang_standalone_mod"
if _tinylang_mod_key not in _sys.modules:
    _sys.modules[_tinylang_mod_key] = _sys.modules[__name__]


# ============================================================
#  错误类型
# ============================================================

class TinyLangError(Exception):
    def __init__(self, message, line=None, column=None):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(self._fmt())

    def _fmt(self):
        if self.line is not None:
            return f"[行 {self.line}, 列 {self.column or '?'}] {self.message}"
        return self.message

class LexerError(TinyLangError): pass
class ParserError(TinyLangError): pass
class CompileError(TinyLangError): pass


# ============================================================
#  Token 类型
# ============================================================

class TokenType(Enum):
    # 字面量
    INTEGER = "INTEGER"
    FLOAT = "FLOAT"
    STRING = "STRING"
    # 标识符
    IDENTIFIER = "IDENTIFIER"
    # 关键字
    LET = "LET"
    IF = "IF"
    ELIF = "ELIF"
    ELSE = "ELSE"
    WHILE = "WHILE"
    FOR = "FOR"
    IN = "IN"
    FN = "FN"
    RETURN = "RETURN"
    BREAK = "BREAK"
    CONTINUE = "CONTINUE"
    AND = "AND"
    OR = "OR"
    NOT = "NOT"
    TRUE = "TRUE"
    FALSE = "FALSE"
    NONE = "NONE"
    # 运算符
    PLUS = "PLUS"
    MINUS = "MINUS"
    STAR = "STAR"
    SLASH = "SLASH"
    PERCENT = "PERCENT"
    ASSIGN = "ASSIGN"
    EQ = "EQ"
    NEQ = "NEQ"
    LT = "LT"
    GT = "GT"
    LTE = "LTE"
    GTE = "GTE"
    # 分隔符
    LPAREN = "LPAREN"
    RPAREN = "RPAREN"
    LBRACKET = "LBRACKET"
    RBRACKET = "RBRACKET"
    LBRACE = "LBRACE"
    RBRACE = "RBRACE"
    COMMA = "COMMA"
    SEMICOLON = "SEMICOLON"
    # 特殊
    EOF = "EOF"


KEYWORDS = {
    "let": TokenType.LET, "if": TokenType.IF, "elif": TokenType.ELIF,
    "else": TokenType.ELSE, "while": TokenType.WHILE, "for": TokenType.FOR,
    "in": TokenType.IN, "fn": TokenType.FN, "func": TokenType.FN,
    "return": TokenType.RETURN, "break": TokenType.BREAK, "continue": TokenType.CONTINUE,
    "and": TokenType.AND, "or": TokenType.OR, "not": TokenType.NOT,
    "true": TokenType.TRUE, "false": TokenType.FALSE, "none": TokenType.NONE,
}


class Token:
    __slots__ = ("type", "value", "line", "column")

    def __init__(self, type, value, line, column):
        self.type = type
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, 行{self.line})"


# ============================================================
#  词法分析器
# ============================================================

class Lexer:
    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: list[Token] = []

    def tokenize(self) -> list[Token]:
        while self.pos < len(self.source):
            self._skip_ws()
            if self.pos >= len(self.source):
                break
            self._read_token()
        self.tokens.append(Token(TokenType.EOF, None, self.line, self.column))
        return self.tokens

    def _ch(self) -> str:
        return self.source[self.pos]

    def _peek(self, offset=1) -> str:
        p = self.pos + offset
        return self.source[p] if p < len(self.source) else "\0"

    def _advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def _skip_ws(self):
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch in " \t\r\n":
                self._advance()
            elif ch == "/" and self._peek() == "/":
                while self.pos < len(self.source) and self.source[self.pos] != "\n":
                    self._advance()
            else:
                break

    def _read_token(self):
        ch = self._ch()
        line, col = self.line, self.column

        if ch.isdigit():
            start = self.pos
            while self.pos < len(self.source) and self.source[self.pos].isdigit():
                self._advance()
            if (self.pos < len(self.source) and self.source[self.pos] == "."
                    and self.pos + 1 < len(self.source) and self.source[self.pos + 1].isdigit()):
                self._advance()
                while self.pos < len(self.source) and self.source[self.pos].isdigit():
                    self._advance()
                self.tokens.append(Token(TokenType.FLOAT, float(self.source[start:self.pos]), line, col))
            else:
                self.tokens.append(Token(TokenType.INTEGER, int(self.source[start:self.pos]), line, col))
            return

        if ch.isalpha() or ch == "_":
            start = self.pos
            while self.pos < len(self.source) and (self.source[self.pos].isalnum() or self.source[self.pos] == "_"):
                self._advance()
            word = self.source[start:self.pos]
            self.tokens.append(Token(KEYWORDS.get(word, TokenType.IDENTIFIER), word, line, col))
            return

        if ch == '"':
            self._advance()
            chars = []
            while self.pos < len(self.source) and self.source[self.pos] != '"':
                if self.source[self.pos] == "\\":
                    self._advance()
                    if self.pos < len(self.source):
                        esc = self._advance()
                        chars.append({"n": "\n", "t": "\t", "\\": "\\", '"': '"'}.get(esc, "\\" + esc))
                else:
                    chars.append(self._advance())
            if self.pos >= len(self.source):
                raise LexerError("未终止的字符串字面量", line, col)
            self._advance()
            self.tokens.append(Token(TokenType.STRING, "".join(chars), line, col))
            return

        two = ch + self._peek()
        two_ops = {"==": TokenType.EQ, "!=": TokenType.NEQ, "<=": TokenType.LTE, ">=": TokenType.GTE}
        if two in two_ops:
            self._advance(); self._advance()
            self.tokens.append(Token(two_ops[two], two, line, col))
            return

        one_ops = {
            "+": TokenType.PLUS, "-": TokenType.MINUS, "*": TokenType.STAR,
            "/": TokenType.SLASH, "%": TokenType.PERCENT, "<": TokenType.LT,
            ">": TokenType.GT, "=": TokenType.ASSIGN, "(": TokenType.LPAREN,
            ")": TokenType.RPAREN, "[": TokenType.LBRACKET, "]": TokenType.RBRACKET,
            "{": TokenType.LBRACE, "}": TokenType.RBRACE, ",": TokenType.COMMA,
            ";": TokenType.SEMICOLON,
        }
        if ch in one_ops:
            self._advance()
            self.tokens.append(Token(one_ops[ch], ch, line, col))
            return

        raise LexerError(f"无法识别的字符: '{ch}'", line, col)


# ============================================================
#  AST 节点
# ============================================================

class ASTNode: pass
class Statement(ASTNode): pass
class Expression(ASTNode): pass

@dataclass
class Program(ASTNode):
    statements: list = field(default_factory=list)

@dataclass
class IntegerLiteral(Expression):
    value: int

@dataclass
class FloatLiteral(Expression):
    value: float

@dataclass
class StringLiteral(Expression):
    value: str

@dataclass
class BooleanLiteral(Expression):
    value: bool

@dataclass
class NoneLiteral(Expression):
    pass

@dataclass
class Identifier(Expression):
    name: str

@dataclass
class BinaryOp(Expression):
    left: Expression
    op: str
    right: Expression

@dataclass
class UnaryOp(Expression):
    op: str
    operand: Expression

@dataclass
class CallExpression(Expression):
    callee: Expression
    args: list = field(default_factory=list)

@dataclass
class ArrayLiteral(Expression):
    elements: list = field(default_factory=list)

@dataclass
class IndexExpression(Expression):
    array: Expression
    index: Expression

@dataclass
class VarDecl(Statement):
    name: str
    value: Expression

@dataclass
class Assignment(Statement):
    target: Expression
    value: Expression

@dataclass
class ExprStatement(Statement):
    expression: Expression

@dataclass
class IfStmt(Statement):
    condition: Expression
    then_body: list = field(default_factory=list)
    elif_clauses: list = field(default_factory=list)
    else_body: Optional[list] = None

@dataclass
class WhileStmt(Statement):
    condition: Expression
    body: list = field(default_factory=list)

@dataclass
class ForStmt(Statement):
    var_name: str
    iterable: Expression
    body: list = field(default_factory=list)

@dataclass
class FuncDef(Statement):
    name: str
    params: list = field(default_factory=list)
    body: list = field(default_factory=list)

@dataclass
class ReturnStmt(Statement):
    value: Optional[Expression] = None

@dataclass
class BreakStmt(Statement): pass

@dataclass
class ContinueStmt(Statement): pass


# ============================================================
#  递归下降 Parser
# ============================================================

class Parser:
    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    @property
    def cur(self) -> Token:
        return self.tokens[self.pos]

    def advance(self) -> Token:
        t = self.tokens[self.pos]
        self.pos += 1
        return t

    def check(self, tt: TokenType) -> bool:
        return self.cur.type == tt

    def match(self, *types) -> bool:
        if self.cur.type in types:
            self.advance()
            return True
        return False

    def expect(self, tt: TokenType) -> Token:
        if self.cur.type != tt:
            raise ParserError(
                f"期望 {tt.name}，但得到 {self.cur.type.name} ('{self.cur.value}')",
                self.cur.line, self.cur.column)
        return self.advance()

    # ---- 入口 ----

    def parse(self) -> Program:
        stmts = []
        while not self.check(TokenType.EOF):
            stmts.append(self._stmt())
        return Program(stmts)

    # ---- 语句 ----

    def _stmt(self) -> Statement:
        if self.check(TokenType.LET): return self._let()
        if self.check(TokenType.IF): return self._if()
        if self.check(TokenType.WHILE): return self._while()
        if self.check(TokenType.FOR): return self._for()
        if self.check(TokenType.FN): return self._func_def()
        if self.check(TokenType.RETURN): return self._return()
        if self.check(TokenType.BREAK): return self._break()
        if self.check(TokenType.CONTINUE): return self._continue()
        return self._expr_or_assign()

    def _let(self) -> VarDecl:
        self.expect(TokenType.LET)
        name = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.ASSIGN)
        value = self._expr()
        self.expect(TokenType.SEMICOLON)
        return VarDecl(name, value)

    def _if(self) -> IfStmt:
        self.expect(TokenType.IF)
        has_paren = self.match(TokenType.LPAREN)
        cond = self._expr()
        if has_paren:
            self.expect(TokenType.RPAREN)
        then = self._block_or_stmt()
        elifs = []
        while self.match(TokenType.ELIF):
            has_paren = self.match(TokenType.LPAREN)
            ec = self._expr()
            if has_paren:
                self.expect(TokenType.RPAREN)
            eb = self._block_or_stmt()
            elifs.append((ec, eb))
        else_b = self._block_or_stmt() if self.match(TokenType.ELSE) else None
        return IfStmt(cond, then, elifs, else_b)

    def _while(self) -> WhileStmt:
        self.expect(TokenType.WHILE)
        has_paren = self.match(TokenType.LPAREN)
        cond = self._expr()
        if has_paren:
            self.expect(TokenType.RPAREN)
        body = self._block_or_stmt()
        return WhileStmt(cond, body)

    def _for(self) -> ForStmt:
        self.expect(TokenType.FOR)
        var = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.IN)
        iterable = self._expr()
        body = self._block()
        return ForStmt(var, iterable, body)

    def _func_def(self) -> FuncDef:
        self.expect(TokenType.FN)
        name = self.expect(TokenType.IDENTIFIER).value
        self.expect(TokenType.LPAREN)
        params = []
        if not self.check(TokenType.RPAREN):
            params.append(self.expect(TokenType.IDENTIFIER).value)
            while self.match(TokenType.COMMA):
                params.append(self.expect(TokenType.IDENTIFIER).value)
        self.expect(TokenType.RPAREN)
        body = self._block()
        return FuncDef(name, params, body)

    def _anon_func(self) -> FuncDef:
        """匿名函数表达式: fn(params) { body }"""
        self.expect(TokenType.FN)
        self.expect(TokenType.LPAREN)
        params = []
        if not self.check(TokenType.RPAREN):
            params.append(self.expect(TokenType.IDENTIFIER).value)
            while self.match(TokenType.COMMA):
                params.append(self.expect(TokenType.IDENTIFIER).value)
        self.expect(TokenType.RPAREN)
        body = self._block()
        return FuncDef(None, params, body)

    def _return(self) -> ReturnStmt:
        self.expect(TokenType.RETURN)
        val = None
        if not self.check(TokenType.SEMICOLON) and not self.check(TokenType.RBRACE) and not self.check(TokenType.EOF):
            val = self._expr()
        self.expect(TokenType.SEMICOLON)
        return ReturnStmt(val)

    def _break(self) -> BreakStmt:
        self.expect(TokenType.BREAK)
        self.expect(TokenType.SEMICOLON)
        return BreakStmt()

    def _continue(self) -> ContinueStmt:
        self.expect(TokenType.CONTINUE)
        self.expect(TokenType.SEMICOLON)
        return ContinueStmt()

    def _expr_or_assign(self) -> Statement:
        expr = self._expr()
        if self.match(TokenType.ASSIGN):
            val = self._expr()
            self.expect(TokenType.SEMICOLON)
            if isinstance(expr, (Identifier, IndexExpression)):
                return Assignment(expr, val)
            raise ParserError("无效的赋值目标", self.cur.line, self.cur.column)
        self.expect(TokenType.SEMICOLON)
        return ExprStatement(expr)

    def _block(self) -> list:
        self.expect(TokenType.LBRACE)
        stmts = []
        while not self.check(TokenType.RBRACE) and not self.check(TokenType.EOF):
            stmts.append(self._stmt())
        self.expect(TokenType.RBRACE)
        return stmts

    def _block_or_stmt(self) -> list:
        """解析代码块或单条语句（支持 if/while 不加花括号的写法）"""
        if self.check(TokenType.LBRACE):
            return self._block()
        return [self._stmt()]

    # ---- 表达式（优先级递增） ----

    def _expr(self): return self._or()

    def _or(self):
        left = self._and()
        while self.match(TokenType.OR):
            left = BinaryOp(left, "or", self._and())
        return left

    def _and(self):
        left = self._cmp()
        while self.match(TokenType.AND):
            left = BinaryOp(left, "and", self._cmp())
        return left

    def _cmp(self):
        left = self._add()
        while self.cur.type in (TokenType.EQ, TokenType.NEQ, TokenType.LT,
                                TokenType.GT, TokenType.LTE, TokenType.GTE):
            op = self.advance()
            left = BinaryOp(left, op.value, self._add())
        return left

    def _add(self):
        left = self._mul()
        while self.cur.type in (TokenType.PLUS, TokenType.MINUS):
            op = self.advance()
            left = BinaryOp(left, op.value, self._mul())
        return left

    def _mul(self):
        left = self._unary()
        while self.cur.type in (TokenType.STAR, TokenType.SLASH, TokenType.PERCENT):
            op = self.advance()
            left = BinaryOp(left, op.value, self._unary())
        return left

    def _unary(self):
        if self.match(TokenType.MINUS):
            return UnaryOp("-", self._unary())
        if self.match(TokenType.NOT):
            return UnaryOp("not", self._unary())
        return self._postfix()

    def _postfix(self):
        expr = self._primary()
        while True:
            if self.match(TokenType.LPAREN):
                args = []
                if not self.check(TokenType.RPAREN):
                    args.append(self._expr())
                    while self.match(TokenType.COMMA):
                        args.append(self._expr())
                self.expect(TokenType.RPAREN)
                expr = CallExpression(expr, args)
            elif self.match(TokenType.LBRACKET):
                index = self._expr()
                self.expect(TokenType.RBRACKET)
                expr = IndexExpression(expr, index)
            else:
                break
        return expr

    def _primary(self):
        if self.match(TokenType.INTEGER):
            return IntegerLiteral(self.tokens[self.pos - 1].value)
        if self.match(TokenType.FLOAT):
            return FloatLiteral(self.tokens[self.pos - 1].value)
        if self.match(TokenType.STRING):
            return StringLiteral(self.tokens[self.pos - 1].value)
        if self.match(TokenType.TRUE):
            return BooleanLiteral(True)
        if self.match(TokenType.FALSE):
            return BooleanLiteral(False)
        if self.match(TokenType.NONE):
            return NoneLiteral()
        if self.match(TokenType.IDENTIFIER):
            return Identifier(self.tokens[self.pos - 1].value)
        if self.match(TokenType.LPAREN):
            expr = self._expr()
            self.expect(TokenType.RPAREN)
            return expr
        if self.match(TokenType.LBRACKET):
            elems = []
            if not self.check(TokenType.RBRACKET):
                elems.append(self._expr())
                while self.match(TokenType.COMMA):
                    elems.append(self._expr())
            self.expect(TokenType.RBRACKET)
            return ArrayLiteral(elems)
        if self.check(TokenType.FN):
            return self._anon_func()
        raise ParserError(
            f"无法解析的表达式，遇到: {self.cur.type.name} ('{self.cur.value}')",
            self.cur.line, self.cur.column)


# ============================================================
#  字节码指令集
# ============================================================

class Opcode(IntEnum):
    LOAD_CONST = 1
    LOAD_TRUE = 2
    LOAD_FALSE = 3
    LOAD_NONE = 4
    POP = 5
    DUP = 6
    LOAD_VAR = 10
    STORE_VAR = 11
    ADD = 20
    SUB = 21
    MUL = 22
    DIV = 23
    MOD = 24
    NEGATE = 25
    CMP_EQ = 30
    CMP_NEQ = 31
    CMP_LT = 32
    CMP_GT = 33
    CMP_LTE = 34
    CMP_GTE = 35
    NOT = 42
    JUMP = 50
    JUMP_IF_FALSE = 51
    JUMP_IF_TRUE = 52
    CALL = 60
    RETURN = 61
    BUILD_ARRAY = 70
    GET_INDEX = 71
    SET_INDEX = 72
    GET_LEN = 73
    HALT = 99


class Chunk:
    def __init__(self):
        self.code: list[int] = []
        self.constants: list = []
        self.lines: list[int] = []

    def emit(self, byte: int, line: int = 0):
        self.code.append(byte)
        self.lines.append(line)

    def emit_op(self, op: int, operand=None, line: int = 0):
        self.emit(op, line)
        if operand is not None:
            self.emit(operand, line)

    def add_constant(self, value) -> int:
        self.constants.append(value)
        return len(self.constants) - 1

    def __len__(self):
        return len(self.code)


class CompiledFunc:
    def __init__(self, name, params, chunk):
        self.name = name
        self.params = params
        self.arity = len(params)
        self.chunk = chunk

    def __repr__(self):
        return f"<func {self.name}/{self.arity}>"


# ============================================================
#  字节码编译器
# ============================================================

class LoopCtx:
    def __init__(self, continue_addr=None):
        self.continue_addr = continue_addr
        self.break_jumps: list[int] = []


class Compiler:
    def __init__(self, builtins=None):
        self.builtins = builtins or {}
        self._main = Chunk()
        self._chunks: list[Chunk] = [self._main]
        self._loops: list[LoopCtx] = []
        self._temp_id = 0

    @property
    def chunk(self) -> Chunk:
        return self._chunks[-1]

    def _emit(self, op, operand=None, line=0):
        self.chunk.emit_op(op, operand, line)

    def _emit_const(self, value, line=0):
        idx = self.chunk.add_constant(value)
        self._emit(Opcode.LOAD_CONST, idx, line)
        return idx

    def _emit_jump(self, op) -> int:
        self._emit(op)
        pos = len(self.chunk.code)
        self._emit(0)
        return pos

    def _patch(self, pos):
        self.chunk.code[pos] = len(self.chunk.code)

    def _add_name(self, name) -> int:
        return self.chunk.add_constant(name)

    def compile(self, program: Program) -> CompiledFunc:
        for stmt in program.statements:
            self._compile_stmt(stmt)
        self._emit(Opcode.HALT)
        return CompiledFunc("<main>", [], self._main)

    def _compile_stmt(self, node):
        if isinstance(node, VarDecl):
            self._compile_expr(node.value)
            self._emit(Opcode.STORE_VAR, self._add_name(node.name))
            return
        if isinstance(node, Assignment):
            if isinstance(node.target, Identifier):
                self._compile_expr(node.value)
                self._emit(Opcode.STORE_VAR, self._add_name(node.target.name))
            elif isinstance(node.target, IndexExpression):
                self._compile_expr(node.target.array)
                self._compile_expr(node.target.index)
                self._compile_expr(node.value)
                self._emit(Opcode.SET_INDEX)
            return
        if isinstance(node, ExprStatement):
            self._compile_expr(node.expression)
            self._emit(Opcode.POP)
            return
        if isinstance(node, IfStmt):
            self._compile_if(node)
            return
        if isinstance(node, WhileStmt):
            self._compile_while(node)
            return
        if isinstance(node, ForStmt):
            self._compile_for(node)
            return
        if isinstance(node, FuncDef):
            self._compile_func_def(node)
            return
        if isinstance(node, ReturnStmt):
            if node.value is not None:
                self._compile_expr(node.value)
            else:
                self._emit(Opcode.LOAD_NONE)
            self._emit(Opcode.RETURN)
            return
        if isinstance(node, BreakStmt):
            loop = self._loops[-1] if self._loops else None
            if not loop:
                raise CompileError("'break' 必须在循环内部")
            loop.break_jumps.append(self._emit_jump(Opcode.JUMP))
            return
        if isinstance(node, ContinueStmt):
            loop = self._loops[-1] if self._loops else None
            if not loop or loop.continue_addr is None:
                raise CompileError("'continue' 必须在循环内部")
            self._emit(Opcode.JUMP)
            self._emit(loop.continue_addr)
            return
        raise CompileError(f"未知语句: {type(node).__name__}")

    def _compile_stmts(self, stmts):
        for s in stmts:
            self._compile_stmt(s)

    def _compile_if(self, node: IfStmt):
        end_jumps = []
        self._compile_expr(node.condition)
        else_j = self._emit_jump(Opcode.JUMP_IF_FALSE)
        self._compile_stmts(node.then_body)
        end_jumps.append(self._emit_jump(Opcode.JUMP))
        self._patch(else_j)
        for ec, eb in node.elif_clauses:
            self._compile_expr(ec)
            ej = self._emit_jump(Opcode.JUMP_IF_FALSE)
            self._compile_stmts(eb)
            end_jumps.append(self._emit_jump(Opcode.JUMP))
            self._patch(ej)
        if node.else_body is not None:
            self._compile_stmts(node.else_body)
        for p in end_jumps:
            self._patch(p)

    def _compile_while(self, node: WhileStmt):
        start = len(self.chunk.code)
        self._loops.append(LoopCtx(start))
        self._compile_expr(node.condition)
        end_j = self._emit_jump(Opcode.JUMP_IF_FALSE)
        self._compile_stmts(node.body)
        self._emit(Opcode.JUMP)
        self._emit(start)
        self._patch(end_j)
        ctx = self._loops.pop()
        for p in ctx.break_jumps:
            self._patch(p)

    def _compile_for(self, node: ForStmt):
        self._compile_expr(node.iterable)
        tmp_iter = f"__iter_{self._temp_id}__"
        tmp_idx = f"__idx_{self._temp_id}__"
        self._temp_id += 1
        iter_ni = self._add_name(tmp_iter)
        idx_ni = self._add_name(tmp_idx)
        var_ni = self._add_name(node.var_name)
        self._emit(Opcode.STORE_VAR, iter_ni)
        ci = self.chunk.add_constant(0)
        self._emit(Opcode.LOAD_CONST, ci)
        self._emit(Opcode.STORE_VAR, idx_ni)
        loop_start = len(self.chunk.code)
        self._emit(Opcode.LOAD_VAR, idx_ni)
        self._emit(Opcode.LOAD_VAR, iter_ni)
        self._emit(Opcode.GET_LEN)
        self._emit(Opcode.CMP_LT)
        end_j = self._emit_jump(Opcode.JUMP_IF_FALSE)
        self._loops.append(LoopCtx(None))
        self._emit(Opcode.LOAD_VAR, iter_ni)
        self._emit(Opcode.LOAD_VAR, idx_ni)
        self._emit(Opcode.GET_INDEX)
        self._emit(Opcode.STORE_VAR, var_ni)
        self._compile_stmts(node.body)
        self._loops[-1].continue_addr = len(self.chunk.code)
        self._emit(Opcode.LOAD_VAR, idx_ni)
        oi = self.chunk.add_constant(1)
        self._emit(Opcode.LOAD_CONST, oi)
        self._emit(Opcode.ADD)
        self._emit(Opcode.STORE_VAR, idx_ni)
        self._emit(Opcode.JUMP)
        self._emit(loop_start)
        self._patch(end_j)
        ctx = self._loops.pop()
        for p in ctx.break_jumps:
            self._patch(p)

    def _compile_func_def(self, node: FuncDef):
        func_chunk = Chunk()
        self._chunks.append(func_chunk)
        self._compile_stmts(node.body)
        self._emit(Opcode.LOAD_NONE)
        self._emit(Opcode.RETURN)
        self._chunks.pop()
        func = CompiledFunc(node.name or "<anonymous>", node.params, func_chunk)
        ci = self.chunk.add_constant(func)
        self._emit(Opcode.LOAD_CONST, ci)
        if node.name is not None:
            self._emit(Opcode.STORE_VAR, self._add_name(node.name))

    def _compile_expr(self, node: Expression):
        if isinstance(node, IntegerLiteral):
            self._emit_const(node.value); return
        if isinstance(node, FloatLiteral):
            self._emit_const(node.value); return
        if isinstance(node, StringLiteral):
            self._emit_const(node.value); return
        if isinstance(node, BooleanLiteral):
            self._emit(Opcode.LOAD_TRUE if node.value else Opcode.LOAD_FALSE); return
        if isinstance(node, NoneLiteral):
            self._emit(Opcode.LOAD_NONE); return
        if isinstance(node, Identifier):
            self._emit(Opcode.LOAD_VAR, self._add_name(node.name)); return
        if isinstance(node, ArrayLiteral):
            for e in node.elements:
                self._compile_expr(e)
            self._emit(Opcode.BUILD_ARRAY, len(node.elements)); return
        if isinstance(node, IndexExpression):
            self._compile_expr(node.array)
            self._compile_expr(node.index)
            self._emit(Opcode.GET_INDEX); return
        if isinstance(node, BinaryOp):
            self._compile_binary(node); return
        if isinstance(node, UnaryOp):
            self._compile_expr(node.operand)
            self._emit(Opcode.NEGATE if node.op == "-" else Opcode.NOT)
            return
        if isinstance(node, CallExpression):
            self._compile_expr(node.callee)
            for a in node.args:
                self._compile_expr(a)
            self._emit(Opcode.CALL, len(node.args))
            return
        if isinstance(node, FuncDef):
            self._compile_func_def(node)
            return
        raise CompileError(f"未知表达式: {type(node).__name__}")

    def _compile_binary(self, node: BinaryOp):
        if node.op == "and":
            self._compile_expr(node.left)
            self._emit(Opcode.DUP)
            j = self._emit_jump(Opcode.JUMP_IF_FALSE)
            self._emit(Opcode.POP)
            self._compile_expr(node.right)
            self._patch(j)
            return
        if node.op == "or":
            self._compile_expr(node.left)
            self._emit(Opcode.DUP)
            j = self._emit_jump(Opcode.JUMP_IF_TRUE)
            self._emit(Opcode.POP)
            self._compile_expr(node.right)
            self._patch(j)
            return
        self._compile_expr(node.left)
        self._compile_expr(node.right)
        op_map = {
            "+": Opcode.ADD, "-": Opcode.SUB, "*": Opcode.MUL,
            "/": Opcode.DIV, "%": Opcode.MOD,
            "==": Opcode.CMP_EQ, "!=": Opcode.CMP_NEQ,
            "<": Opcode.CMP_LT, ">": Opcode.CMP_GT,
            "<=": Opcode.CMP_LTE, ">=": Opcode.CMP_GTE,
        }
        if node.op in op_map:
            self._emit(op_map[node.op])
        else:
            raise CompileError(f"未知运算符: {node.op}")


# ============================================================
#  反汇编
# ============================================================

def disassemble(chunk: Chunk, name="<chunk>") -> str:
    lines = [f"=== {name} ==="]
    i = 0
    while i < len(chunk.code):
        addr = i
        op = chunk.code[i]; i += 1
        try:
            opname = Opcode(op).name
        except ValueError:
            lines.append(f"  {addr:04d}  UNKNOWN({op})")
            continue
        if op in (Opcode.LOAD_CONST, Opcode.LOAD_VAR, Opcode.STORE_VAR):
            if i < len(chunk.code):
                operand = chunk.code[i]; i += 1
                cv = chunk.constants[operand] if operand < len(chunk.constants) else "?"
                lines.append(f"  {addr:04d}  {opname:<14s} {operand}  ({cv!r})")
            else:
                lines.append(f"  {addr:04d}  {opname:<14s} <missing>")
        elif op == Opcode.BUILD_ARRAY:
            if i < len(chunk.code):
                count = chunk.code[i]; i += 1
                lines.append(f"  {addr:04d}  {opname:<14s} {count} elements")
            else:
                lines.append(f"  {addr:04d}  {opname:<14s} <missing>")
        elif op in (Opcode.JUMP, Opcode.JUMP_IF_FALSE, Opcode.JUMP_IF_TRUE):
            if i < len(chunk.code):
                target = chunk.code[i]; i += 1
                lines.append(f"  {addr:04d}  {opname:<14s} -> {target:04d}")
            else:
                lines.append(f"  {addr:04d}  {opname:<14s} <missing>")
        elif op == Opcode.CALL:
            if i < len(chunk.code):
                argc = chunk.code[i]; i += 1
                lines.append(f"  {addr:04d}  {opname:<14s} {argc} args")
            else:
                lines.append(f"  {addr:04d}  {opname:<14s} <missing>")
        else:
            lines.append(f"  {addr:04d}  {opname}")
    return "\n".join(lines)


# ============================================================
#  命令行入口
# ============================================================

def main():
    import sys, os
    args = sys.argv[1:]
    show_dis = "--dis" in args
    interpret = "--interpret" in args
    file_args = [a for a in args if not a.startswith("--")]

    if not file_args:
        print("用法: python tinylang.py [--dis|--interpret] <file.tl>")
        print("  --dis         显示反汇编字节码（默认）")
        print("  --interpret   使用解释器执行")
        sys.exit(1)

    with open(file_args[0], "r", encoding="utf-8") as f:
        source = f.read()

    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()

    if interpret:
        import importlib.util as _ilu2
        _interp_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "tinylang_interpreter.py")
        _s2 = _ilu2.spec_from_file_location("_tinylang_interp", _interp_path)
        _m2 = _ilu2.module_from_spec(_s2)
        _s2.loader.exec_module(_m2)
        interp = _m2.Interpreter()
        interp.run(ast)
    else:
        compiler = Compiler()
        main_func = compiler.compile(ast)
        print(disassemble(main_func.chunk, main_func.name))


if __name__ == "__main__":
    main()
