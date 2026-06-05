#!/usr/bin/env python3
"""
parser.py - 完整的递归下降语法分析器

支持简单 C 语言子集的语法分析，包括：
  - 内嵌词法分析器（Tokenizer）
  - 完整的 AST 节点定义
  - 递归下降解析器实现
  - 错误处理（带行号报告）
  - AST 打印/可视化

使用方法：
  python parser.py <source_file>
  python parser.py              # 使用内置演示代码
"""

import sys
from typing import List, Optional
from dataclasses import dataclass, field
from enum import Enum, auto


# ============================================================================
# 第一部分：Token 定义
# ============================================================================

class TokenType(Enum):
    """Token 类型枚举"""
    NUM = auto()        # 数字字面量
    ID = auto()         # 标识符
    PLUS = auto()       # +
    MINUS = auto()      # -
    STAR = auto()       # *
    SLASH = auto()      # /
    PERCENT = auto()    # %
    ASSIGN = auto()     # =
    EQ = auto()         # ==
    NEQ = auto()        # !=
    LT = auto()         # <
    GT = auto()         # >
    LTE = auto()        # <=
    GTE = auto()        # >=
    AND = auto()        # &&
    OR = auto()         # ||
    NOT = auto()        # !
    BITNOT = auto()     # ~
    LPAREN = auto()     # (
    RPAREN = auto()     # )
    LBRACE = auto()     # {
    RBRACE = auto()     # }
    SEMI = auto()       # ;
    COMMA = auto()      # ,
    IF = auto()         # if
    ELSE = auto()       # else
    WHILE = auto()      # while
    RETURN = auto()     # return
    EOF = auto()        # 文件结束


@dataclass
class Token:
    """Token 数据类"""
    type: TokenType
    value: str
    line: int
    column: int

    def __repr__(self):
        if self.type == TokenType.EOF:
            return "EOF"
        return f"{self.type.name}({self.value!r})"


KEYWORDS = {
    'if': TokenType.IF,
    'else': TokenType.ELSE,
    'while': TokenType.WHILE,
    'return': TokenType.RETURN,
}


# ============================================================================
# 第二部分：AST 节点定义
# ============================================================================

@dataclass
class ASTNode:
    """AST 节点基类"""
    line: int = 0
    column: int = 0


@dataclass
class Program(ASTNode):
    """程序节点"""
    stmts: List[ASTNode] = field(default_factory=list)

    def __repr__(self):
        return f"Program({len(self.stmts)} stmts)"


@dataclass
class Assignment(ASTNode):
    """赋值语句"""
    name: str = ""
    value: ASTNode = None

    def __repr__(self):
        return f"Assignment({self.name})"


@dataclass
class IfStmt(ASTNode):
    """if 语句"""
    condition: ASTNode = None
    then_body: ASTNode = None
    else_body: Optional[ASTNode] = None

    def __repr__(self):
        return "IfStmt"


@dataclass
class Block(ASTNode):
    """代码块"""
    stmts: List[ASTNode] = field(default_factory=list)

    def __repr__(self):
        return f"Block({len(self.stmts)} stmts)"


@dataclass
class BinaryOp(ASTNode):
    """二元运算"""
    op: str = ""
    left: ASTNode = None
    right: ASTNode = None

    def __repr__(self):
        return f"BinaryOp({self.op})"


@dataclass
class UnaryOp(ASTNode):
    """一元运算"""
    op: str = ""
    operand: ASTNode = None

    def __repr__(self):
        return f"UnaryOp({self.op})"


@dataclass
class Number(ASTNode):
    """数字字面量"""
    value: float = 0.0
    raw: str = ""

    def __repr__(self):
        return f"Number({self.raw})"


@dataclass
class Identifier(ASTNode):
    """标识符"""
    name: str = ""

    def __repr__(self):
        return f"Identifier({self.name})"


# ============================================================================
# 第三部分：词法分析器
# ============================================================================

class TokenizerError(Exception):
    def __init__(self, message, line, column):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(f"Tokenizer error at line {line}, column {column}: {message}")


class Tokenizer:
    """词法分析器：将源代码字符串转换为 Token 流"""

    def __init__(self, source: str):
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []

    def error(self, message: str):
        raise TokenizerError(message, self.line, self.column)

    def peek(self) -> str:
        if self.pos < len(self.source):
            return self.source[self.pos]
        return '\0'

    def advance(self) -> str:
        ch = self.source[self.pos]
        self.pos += 1
        if ch == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    def skip_whitespace_and_comments(self):
        while self.pos < len(self.source):
            ch = self.peek()
            if ch in ' \t\n\r':
                self.advance()
            elif ch == '/' and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == '/':
                while self.pos < len(self.source) and self.peek() != '\n':
                    self.advance()
            elif ch == '/' and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == '*':
                start_line = self.line
                self.advance()
                self.advance()
                while self.pos < len(self.source):
                    if self.peek() == '*' and self.pos + 1 < len(self.source) and self.source[self.pos + 1] == '/':
                        self.advance()
                        self.advance()
                        break
                    self.advance()
                else:
                    self.error(f"Unterminated comment starting at line {start_line}")
            else:
                break

    def read_number(self) -> Token:
        start_col = self.column
        start_line = self.line
        result = ''
        has_dot = False
        while self.pos < len(self.source) and (self.peek().isdigit() or self.peek() == '.'):
            if self.peek() == '.':
                if has_dot:
                    break
                has_dot = True
            result += self.advance()
        return Token(TokenType.NUM, result, start_line, start_col)

    def read_identifier_or_keyword(self) -> Token:
        start_col = self.column
        start_line = self.line
        result = ''
        while self.pos < len(self.source) and (self.peek().isalnum() or self.peek() == '_'):
            result += self.advance()
        token_type = KEYWORDS.get(result, TokenType.ID)
        return Token(token_type, result, start_line, start_col)

    def tokenize(self) -> List[Token]:
        while self.pos < len(self.source):
            self.skip_whitespace_and_comments()
            if self.pos >= len(self.source):
                break
            ch = self.peek()
            start_col = self.column
            start_line = self.line

            if ch.isdigit():
                self.tokens.append(self.read_number())
                continue
            if ch.isalpha() or ch == '_':
                self.tokens.append(self.read_identifier_or_keyword())
                continue

            self.advance()
            if ch == '+':
                self.tokens.append(Token(TokenType.PLUS, '+', start_line, start_col))
            elif ch == '-':
                self.tokens.append(Token(TokenType.MINUS, '-', start_line, start_col))
            elif ch == '*':
                self.tokens.append(Token(TokenType.STAR, '*', start_line, start_col))
            elif ch == '/':
                self.tokens.append(Token(TokenType.SLASH, '/', start_line, start_col))
            elif ch == '%':
                self.tokens.append(Token(TokenType.PERCENT, '%', start_line, start_col))
            elif ch == '(':
                self.tokens.append(Token(TokenType.LPAREN, '(', start_line, start_col))
            elif ch == ')':
                self.tokens.append(Token(TokenType.RPAREN, ')', start_line, start_col))
            elif ch == '{':
                self.tokens.append(Token(TokenType.LBRACE, '{', start_line, start_col))
            elif ch == '}':
                self.tokens.append(Token(TokenType.RBRACE, '}', start_line, start_col))
            elif ch == ';':
                self.tokens.append(Token(TokenType.SEMI, ';', start_line, start_col))
            elif ch == ',':
                self.tokens.append(Token(TokenType.COMMA, ',', start_line, start_col))
            elif ch == '~':
                self.tokens.append(Token(TokenType.BITNOT, '~', start_line, start_col))
            elif ch == '=':
                if self.peek() == '=':
                    self.advance()
                    self.tokens.append(Token(TokenType.EQ, '==', start_line, start_col))
                else:
                    self.tokens.append(Token(TokenType.ASSIGN, '=', start_line, start_col))
            elif ch == '!':
                if self.peek() == '=':
                    self.advance()
                    self.tokens.append(Token(TokenType.NEQ, '!=', start_line, start_col))
                else:
                    self.tokens.append(Token(TokenType.NOT, '!', start_line, start_col))
            elif ch == '<':
                if self.peek() == '=':
                    self.advance()
                    self.tokens.append(Token(TokenType.LTE, '<=', start_line, start_col))
                else:
                    self.tokens.append(Token(TokenType.LT, '<', start_line, start_col))
            elif ch == '>':
                if self.peek() == '=':
                    self.advance()
                    self.tokens.append(Token(TokenType.GTE, '>=', start_line, start_col))
                else:
                    self.tokens.append(Token(TokenType.GT, '>', start_line, start_col))
            elif ch == '&':
                if self.peek() == '&':
                    self.advance()
                    self.tokens.append(Token(TokenType.AND, '&&', start_line, start_col))
                else:
                    self.error("Unexpected character '&' (did you mean '&&'?)")
            elif ch == '|':
                if self.peek() == '|':
                    self.advance()
                    self.tokens.append(Token(TokenType.OR, '||', start_line, start_col))
                else:
                    self.error("Unexpected character '|' (did you mean '||'?)")
            else:
                self.error(f"Unexpected character '{ch}'")

        self.tokens.append(Token(TokenType.EOF, '', self.line, self.column))
        return self.tokens


# ============================================================================
# 第四部分：递归下降语法分析器
# ============================================================================

class ParseError(Exception):
    def __init__(self, message, line=0, column=0):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(message)


class Parser:
    """
    递归下降语法分析器

    文法（消除左递归后的 LL(1) 文法）：
      program    → stmt_list
      stmt_list  → stmt stmt_list | ε
      stmt       → id = expr ; | if ( expr ) stmt [else stmt] | { stmt_list }
      expr       → lor_expr
      lor_expr   → land_expr (|| land_expr)*
      land_expr  → cmp_expr (&& cmp_expr)*
      cmp_expr   → add_expr ((==|!=|<|>|<=|>=) add_expr)*
      add_expr   → mul_expr ((+|-) mul_expr)*
      mul_expr   → unary_expr ((*|/|%) unary_expr)*
      unary_expr → (-|!|~) unary_expr | primary
      primary    → ( expr ) | id | num
    """

    def __init__(self, tokens: List[Token]):
        self.tokens = tokens
        self.pos = 0
        self.errors: List[ParseError] = []

    @property
    def current(self) -> Token:
        if self.pos < len(self.tokens):
            return self.tokens[self.pos]
        return self.tokens[-1]

    def advance(self) -> Token:
        token = self.current
        if self.pos < len(self.tokens) - 1:
            self.pos += 1
        return token

    def expect(self, token_type: TokenType) -> Token:
        if self.current.type == token_type:
            return self.advance()
        else:
            raise ParseError(
                f"Expected {token_type.name}, got {self.current.type.name} ('{self.current.value}')",
                self.current.line, self.current.column,
            )

    def match(self, *token_types: TokenType) -> bool:
        return self.current.type in token_types

    def parse(self) -> Program:
        program = Program(line=1, column=1)
        try:
            program.stmts = self.parse_stmt_list()
        except ParseError as e:
            self.report_error(e)
            self._panic_skip()
        return program

    def parse_stmt_list(self) -> List[ASTNode]:
        stmts = []
        while self.match(TokenType.ID, TokenType.IF, TokenType.LBRACE):
            try:
                stmt = self.parse_stmt()
                if stmt is not None:
                    stmts.append(stmt)
            except ParseError as e:
                self.report_error(e)
                self._panic_skip()
        return stmts

    def parse_stmt(self) -> Optional[ASTNode]:
        if self.match(TokenType.ID):
            return self.parse_assignment()
        elif self.match(TokenType.IF):
            return self.parse_if_stmt()
        elif self.match(TokenType.LBRACE):
            return self.parse_block()
        else:
            raise ParseError(
                f"Expected statement, got {self.current.type.name} ('{self.current.value}')",
                self.current.line, self.current.column,
            )

    def parse_assignment(self) -> Assignment:
        line, col = self.current.line, self.current.column
        name_token = self.expect(TokenType.ID)
        self.expect(TokenType.ASSIGN)
        value = self.parse_expr()
        self.expect(TokenType.SEMI)
        return Assignment(name=name_token.value, value=value, line=line, column=col)

    def parse_if_stmt(self) -> IfStmt:
        line, col = self.current.line, self.current.column
        self.expect(TokenType.IF)
        self.expect(TokenType.LPAREN)
        condition = self.parse_expr()
        self.expect(TokenType.RPAREN)
        then_body = self.parse_stmt()
        else_body = None
        if self.match(TokenType.ELSE):
            self.advance()
            else_body = self.parse_stmt()
        return IfStmt(condition=condition, then_body=then_body, else_body=else_body, line=line, column=col)

    def parse_block(self) -> Block:
        line, col = self.current.line, self.current.column
        self.expect(TokenType.LBRACE)
        stmts = self.parse_stmt_list()
        self.expect(TokenType.RBRACE)
        return Block(stmts=stmts, line=line, column=col)

    def parse_expr(self) -> ASTNode:
        return self.parse_lor_expr()

    def parse_lor_expr(self) -> ASTNode:
        left = self.parse_land_expr()
        while self.match(TokenType.OR):
            op_line, op_col = self.current.line, self.current.column
            self.advance()
            right = self.parse_land_expr()
            left = BinaryOp(op='||', left=left, right=right, line=op_line, column=op_col)
        return left

    def parse_land_expr(self) -> ASTNode:
        left = self.parse_cmp_expr()
        while self.match(TokenType.AND):
            op_line, op_col = self.current.line, self.current.column
            self.advance()
            right = self.parse_cmp_expr()
            left = BinaryOp(op='&&', left=left, right=right, line=op_line, column=op_col)
        return left

    def parse_cmp_expr(self) -> ASTNode:
        left = self.parse_add_expr()
        op_map = {TokenType.EQ: '==', TokenType.NEQ: '!=', TokenType.LT: '<',
                  TokenType.GT: '>', TokenType.LTE: '<=', TokenType.GTE: '>='}
        while self.match(*op_map.keys()):
            op_line, op_col = self.current.line, self.current.column
            op = op_map[self.current.type]
            self.advance()
            right = self.parse_add_expr()
            left = BinaryOp(op=op, left=left, right=right, line=op_line, column=op_col)
        return left

    def parse_add_expr(self) -> ASTNode:
        left = self.parse_mul_expr()
        while self.match(TokenType.PLUS, TokenType.MINUS):
            op_line, op_col = self.current.line, self.current.column
            op = '+' if self.current.type == TokenType.PLUS else '-'
            self.advance()
            right = self.parse_mul_expr()
            left = BinaryOp(op=op, left=left, right=right, line=op_line, column=op_col)
        return left

    def parse_mul_expr(self) -> ASTNode:
        left = self.parse_unary_expr()
        op_map = {TokenType.STAR: '*', TokenType.SLASH: '/', TokenType.PERCENT: '%'}
        while self.match(*op_map.keys()):
            op_line, op_col = self.current.line, self.current.column
            op = op_map[self.current.type]
            self.advance()
            right = self.parse_unary_expr()
            left = BinaryOp(op=op, left=left, right=right, line=op_line, column=op_col)
        return left

    def parse_unary_expr(self) -> ASTNode:
        if self.match(TokenType.MINUS, TokenType.NOT, TokenType.BITNOT):
            op_line, op_col = self.current.line, self.current.column
            op_map = {TokenType.MINUS: '-', TokenType.NOT: '!', TokenType.BITNOT: '~'}
            op = op_map[self.current.type]
            self.advance()
            operand = self.parse_unary_expr()
            return UnaryOp(op=op, operand=operand, line=op_line, column=op_col)
        return self.parse_primary()

    def parse_primary(self) -> ASTNode:
        if self.match(TokenType.LPAREN):
            self.advance()
            expr = self.parse_expr()
            self.expect(TokenType.RPAREN)
            return expr
        elif self.match(TokenType.NUM):
            token = self.advance()
            try:
                value = float(token.value) if '.' in token.value else int(token.value)
            except ValueError:
                value = 0
            return Number(value=value, raw=token.value, line=token.line, column=token.column)
        elif self.match(TokenType.ID):
            token = self.advance()
            return Identifier(name=token.value, line=token.line, column=token.column)
        else:
            raise ParseError(
                f"Expected expression, got {self.current.type.name} ('{self.current.value}')",
                self.current.line, self.current.column,
            )

    def report_error(self, error: ParseError):
        self.errors.append(error)

    def _panic_skip(self):
        sync_tokens = {TokenType.SEMI, TokenType.RBRACE, TokenType.EOF}
        while self.current.type not in sync_tokens:
            self.advance()
        if self.current.type == TokenType.SEMI:
            self.advance()


# ============================================================================
# 第五部分：AST 打印器
# ============================================================================

def print_ast(node: ASTNode, indent: str = "", is_last: bool = True):
    """将 AST 以树形结构打印到终端"""
    connector = "└── " if is_last else "├── "
    extension = "    " if is_last else "│   "

    if isinstance(node, Program):
        print(f"{indent}{connector}Program")
        new_indent = indent + extension
        for i, stmt in enumerate(node.stmts):
            print_ast(stmt, new_indent, i == len(node.stmts) - 1)
    elif isinstance(node, Assignment):
        print(f"{indent}{connector}Assignment(\"{node.name}\")")
        print_ast(node.value, indent + extension, True)
    elif isinstance(node, IfStmt):
        print(f"{indent}{connector}IfStmt")
        new_indent = indent + extension
        print(f"{new_indent}├── condition:")
        print_ast(node.condition, new_indent + "│   ", True)
        print(f"{new_indent}├── then:")
        print_ast(node.then_body, new_indent + "│   ", True)
        if node.else_body:
            print(f"{new_indent}└── else:")
            print_ast(node.else_body, new_indent + "    ", True)
    elif isinstance(node, Block):
        print(f"{indent}{connector}Block")
        new_indent = indent + extension
        for i, stmt in enumerate(node.stmts):
            print_ast(stmt, new_indent, i == len(node.stmts) - 1)
    elif isinstance(node, BinaryOp):
        print(f"{indent}{connector}BinaryOp({node.op})")
        new_indent = indent + extension
        print_ast(node.left, new_indent, False)
        print_ast(node.right, new_indent, True)
    elif isinstance(node, UnaryOp):
        print(f"{indent}{connector}UnaryOp({node.op})")
        print_ast(node.operand, indent + extension, True)
    elif isinstance(node, Number):
        print(f"{indent}{connector}Number({node.raw})")
    elif isinstance(node, Identifier):
        print(f"{indent}{connector}Identifier(\"{node.name}\")")
    elif node is None:
        print(f"{indent}{connector}(empty)")


def ast_to_string(node: ASTNode, indent: int = 0) -> str:
    """将 AST 转换为纯文本字符串"""
    prefix = "  " * indent
    lines = []
    if isinstance(node, Program):
        lines.append(f"{prefix}Program")
        for stmt in node.stmts:
            lines.append(ast_to_string(stmt, indent + 1))
    elif isinstance(node, Assignment):
        lines.append(f"{prefix}Assignment(\"{node.name}\") [line {node.line}]")
        lines.append(ast_to_string(node.value, indent + 1))
    elif isinstance(node, IfStmt):
        lines.append(f"{prefix}IfStmt [line {node.line}]")
        lines.append(f"{prefix}  condition:")
        lines.append(ast_to_string(node.condition, indent + 2))
        lines.append(f"{prefix}  then:")
        lines.append(ast_to_string(node.then_body, indent + 2))
        if node.else_body:
            lines.append(f"{prefix}  else:")
            lines.append(ast_to_string(node.else_body, indent + 2))
    elif isinstance(node, Block):
        lines.append(f"{prefix}Block [line {node.line}]")
        for stmt in node.stmts:
            lines.append(ast_to_string(stmt, indent + 1))
    elif isinstance(node, BinaryOp):
        lines.append(f"{prefix}BinaryOp({node.op}) [line {node.line}]")
        lines.append(ast_to_string(node.left, indent + 1))
        lines.append(ast_to_string(node.right, indent + 1))
    elif isinstance(node, UnaryOp):
        lines.append(f"{prefix}UnaryOp({node.op}) [line {node.line}]")
        lines.append(ast_to_string(node.operand, indent + 1))
    elif isinstance(node, Number):
        lines.append(f"{prefix}Number({node.raw}) [line {node.line}]")
    elif isinstance(node, Identifier):
        lines.append(f"{prefix}Identifier(\"{node.name}\") [line {node.line}]")
    elif node is None:
        lines.append(f"{prefix}(empty)")
    return "\n".join(lines)


# ============================================================================
# 第六部分：主函数
# ============================================================================

def main():
    demo_source = """\
// 简单 C 语言子集示例
x = 3 + 4 * 5;
y = (a + b) * (c - d) / e;
if (x > 0) y = 1;
if (x > 0)
    y = 1;
else
    y = 0;
{
    a = 10;
    b = 20;
    c = a + b;
}
if (a > b) {
    result = a - b;
} else {
    result = b - a;
}
total = (price * quantity) + (tax * amount) - discount;
neg = -value;
flag = !condition;
"""

    if len(sys.argv) > 1:
        filename = sys.argv[1]
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                source = f.read()
            print(f"Parsing file: {filename}")
        except FileNotFoundError:
            print(f"Error: File '{filename}' not found.")
            sys.exit(1)
    else:
        source = demo_source
        print("No file specified, using built-in demo code.")
        print("(Usage: python parser.py <source_file>)")

    print("=" * 60)
    print()

    print("--- Lexing ---")
    try:
        tokenizer = Tokenizer(source)
        tokens = tokenizer.tokenize()
        print(f"Generated {len(tokens)} tokens.")
        for tok in tokens:
            if tok.type != TokenType.EOF:
                print(f"  {tok}")
        print()
    except TokenizerError as e:
        print(f"Lexer Error: {e}")
        sys.exit(1)

    print("--- Parsing ---")
    parser = Parser(tokens)
    ast = parser.parse()

    if parser.errors:
        print(f"\nFound {len(parser.errors)} syntax error(s):")
        for err in parser.errors:
            print(f"  Line {err.line}, Column {err.column}: {err.message}")
        print()

    print("--- AST (tree view) ---")
    print()
    print("Program")
    for i, stmt in enumerate(ast.stmts):
        print_ast(stmt, "", i == len(ast.stmts) - 1)
    print()

    print("--- AST (text view) ---")
    print()
    print(ast_to_string(ast))
    print()

    print("=" * 60)
    print("Parsing complete.")
    if parser.errors:
        print(f"  {len(parser.errors)} error(s) found.")
    else:
        print("  No errors found.")


if __name__ == "__main__":
    main()
