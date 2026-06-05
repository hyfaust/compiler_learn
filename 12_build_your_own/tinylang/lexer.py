"""
词法分析器 (Lexer / Tokenizer)

将源代码字符串转换为 Token 序列。词法分析是编译流程的第一步，
也称为"扫描"或"词法化"。

工作原理：
- 逐字符扫描源代码
- 根据字符模式识别出 Token（关键字、标识符、字面量、运算符等）
- 跳过空白字符和注释
- 记录每个 Token 的行号和列号，用于错误报告

Token 类型设计要点：
- 关键字和标识符使用不同的 TokenType，虽然它们的词法模式相同
- 运算符根据长度区分（如 == 和 = 是不同的 Token）
- 字符串字面量支持转义序列（\\n, \\t, \\\\, \\"）
"""

from enum import Enum
from .errors import LexerError


# ============================================================
#  Token 类型枚举
# ============================================================

class TokenType(Enum):
    """Token 类型枚举

    分为以下几类：
    - 字面量:   INTEGER, FLOAT, STRING
    - 标识符:   IDENTIFIER
    - 关键字:   LET, IF, ELIF, ELSE, WHILE, FOR, IN, FUNC, RETURN,
                BREAK, CONTINUE, AND, OR, NOT, TRUE, FALSE
    - 运算符:   PLUS, MINUS, STAR, SLASH, PERCENT,
                ASSIGN, EQ, NEQ, LT, GT, LTE, GTE
    - 分隔符:   LPAREN, RPAREN, LBRACKET, RBRACKET, LBRACE, RBRACE,
                COMMA, SEMICOLON
    - 特殊:     EOF
    """

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
    FUNC = "FUNC"
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
    PLUS = "PLUS"           # +
    MINUS = "MINUS"         # -
    STAR = "STAR"           # *
    SLASH = "SLASH"         # /
    PERCENT = "PERCENT"     # %
    ASSIGN = "ASSIGN"       # =
    EQ = "EQ"               # ==
    NEQ = "NEQ"             # !=
    LT = "LT"               # <
    GT = "GT"               # >
    LTE = "LTE"             # <=
    GTE = "GTE"             # >=

    # 分隔符
    LPAREN = "LPAREN"       # (
    RPAREN = "RPAREN"       # )
    LBRACKET = "LBRACKET"   # [
    RBRACKET = "RBRACKET"   # ]
    LBRACE = "LBRACE"       # {
    RBRACE = "RBRACE"       # }
    COMMA = "COMMA"         # ,
    SEMICOLON = "SEMICOLON" # ;

    # 特殊
    EOF = "EOF"


# 关键字映射表：标识符文本 -> TokenType
KEYWORDS = {
    "let":      TokenType.LET,
    "if":       TokenType.IF,
    "elif":     TokenType.ELIF,
    "else":     TokenType.ELSE,
    "while":    TokenType.WHILE,
    "for":      TokenType.FOR,
    "in":       TokenType.IN,
    "func":     TokenType.FUNC,
    "fn":       TokenType.FUNC,
    "return":   TokenType.RETURN,
    "break":    TokenType.BREAK,
    "continue": TokenType.CONTINUE,
    "and":      TokenType.AND,
    "or":       TokenType.OR,
    "not":      TokenType.NOT,
    "true":     TokenType.TRUE,
    "false":    TokenType.FALSE,
    "none":     TokenType.NONE,
}


# ============================================================
#  Token 类
# ============================================================

class Token:
    """Token —— 词法单元

    Attributes:
        type:   Token 类型
        value:  Token 的值（字面量的值、标识符的名称、运算符的文本等）
        line:   Token 所在的行号（从 1 开始）
        column: Token 所在的列号（从 1 开始）
    """

    def __init__(self, type: TokenType, value, line: int, column: int):
        self.type = type
        self.value = value
        self.line = line
        self.column = column

    def __repr__(self):
        return f"Token({self.type.name}, {self.value!r}, 行{self.line})"

    def __eq__(self, other):
        if isinstance(other, Token):
            return self.type == other.type and self.value == other.value
        return False


# ============================================================
#  词法分析器
# ============================================================

class Lexer:
    """词法分析器 —— 将源代码转换为 Token 序列

    使用方法：
        lexer = Lexer(source_code)
        tokens = lexer.tokenize()

    词法分析过程：
    1. 跳过空白字符和注释
    2. 识别下一个 Token 的起始字符
    3. 根据起始字符的类型，选择相应的扫描策略
    4. 重复直到源代码末尾
    """

    def __init__(self, source: str):
        self.source = source
        self.pos = 0          # 当前字符位置
        self.line = 1         # 当前行号
        self.column = 1       # 当前列号
        self.tokens: list[Token] = []

    def tokenize(self) -> list[Token]:
        """执行词法分析，返回 Token 列表

        Token 列表的最后一个元素始终是 EOF Token。
        """
        while self.pos < len(self.source):
            self._skip_whitespace_and_comments()
            if self.pos >= len(self.source):
                break
            self._read_token()

        self.tokens.append(Token(TokenType.EOF, None, self.line, self.column))
        return self.tokens

    # ---- 字符操作辅助方法 ----

    def _current_char(self) -> str:
        """获取当前字符（不前进）"""
        return self.source[self.pos]

    def _peek_char(self, offset: int = 1) -> str:
        """预读前方第 offset 个字符，不前进

        如果超出源代码范围，返回 '\\0'。
        """
        pos = self.pos + offset
        if pos < len(self.source):
            return self.source[pos]
        return "\0"

    def _advance(self) -> str:
        """前进一个字符，返回该字符

        同时更新行号和列号计数器。
        """
        ch = self.source[self.pos]
        self.pos += 1
        if ch == "\n":
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        return ch

    # ---- 跳过空白和注释 ----

    def _skip_whitespace_and_comments(self):
        """跳过空白字符（空格、制表符、换行）和单行注释（// ...）"""
        while self.pos < len(self.source):
            ch = self.source[self.pos]
            if ch in " \t\r\n":
                self._advance()
            elif ch == "/" and self._peek_char() == "/":
                # 单行注释：跳到行末
                while self.pos < len(self.source) and self.source[self.pos] != "\n":
                    self._advance()
            else:
                break

    # ---- Token 识别 ----

    def _read_token(self):
        """识别并读取下一个 Token

        根据当前字符的类型选择不同的读取策略：
        - 数字 -> 数字字面量
        - 字母/下划线 -> 标识符或关键字
        - 双引号 -> 字符串字面量
        - 其他 -> 运算符或分隔符
        """
        ch = self._current_char()
        line, col = self.line, self.column

        # 数字字面量
        if ch.isdigit():
            self._read_number(line, col)
            return

        # 标识符或关键字
        if ch.isalpha() or ch == "_":
            self._read_identifier(line, col)
            return

        # 字符串字面量
        if ch == '"':
            self._read_string(line, col)
            return

        # 双字符运算符（需要先检查，避免与单字符混淆）
        two_char = ch + self._peek_char()
        two_char_ops = {
            "==": TokenType.EQ,
            "!=": TokenType.NEQ,
            "<=": TokenType.LTE,
            ">=": TokenType.GTE,
        }
        if two_char in two_char_ops:
            self._advance()
            self._advance()
            self.tokens.append(Token(two_char_ops[two_char], two_char, line, col))
            return

        # 单字符运算符和分隔符
        single_char_ops = {
            "+": TokenType.PLUS,
            "-": TokenType.MINUS,
            "*": TokenType.STAR,
            "/": TokenType.SLASH,
            "%": TokenType.PERCENT,
            "<": TokenType.LT,
            ">": TokenType.GT,
            "=": TokenType.ASSIGN,
            "(": TokenType.LPAREN,
            ")": TokenType.RPAREN,
            "[": TokenType.LBRACKET,
            "]": TokenType.RBRACKET,
            "{": TokenType.LBRACE,
            "}": TokenType.RBRACE,
            ",": TokenType.COMMA,
            ";": TokenType.SEMICOLON,
        }
        if ch in single_char_ops:
            self._advance()
            self.tokens.append(Token(single_char_ops[ch], ch, line, col))
            return

        # 无法识别的字符
        raise LexerError(f"无法识别的字符: '{ch}'", line, col)

    # ---- 具体类型的读取方法 ----

    def _read_number(self, line: int, col: int):
        """读取数字字面量（整数或浮点数）

        语法规则：
        - 整数: 由一个或多个数字组成
        - 浮点数: 数字 + 小数点 + 数字
        - 不支持科学计数法（如 1e10）
        """
        start = self.pos
        while self.pos < len(self.source) and self.source[self.pos].isdigit():
            self._advance()

        # 检查是否有小数点（浮点数）
        if (self.pos < len(self.source) and self.source[self.pos] == "."
                and self.pos + 1 < len(self.source) and self.source[self.pos + 1].isdigit()):
            self._advance()  # 跳过小数点
            while self.pos < len(self.source) and self.source[self.pos].isdigit():
                self._advance()
            value = float(self.source[start:self.pos])
            self.tokens.append(Token(TokenType.FLOAT, value, line, col))
        else:
            value = int(self.source[start:self.pos])
            self.tokens.append(Token(TokenType.INTEGER, value, line, col))

    def _read_identifier(self, line: int, col: int):
        """读取标识符或关键字

        标识符规则：
        - 以字母或下划线开头
        - 后续可以是字母、数字或下划线
        - 区分大小写
        """
        start = self.pos
        while self.pos < len(self.source) and (
            self.source[self.pos].isalnum() or self.source[self.pos] == "_"
        ):
            self._advance()

        word = self.source[start:self.pos]
        token_type = KEYWORDS.get(word, TokenType.IDENTIFIER)
        self.tokens.append(Token(token_type, word, line, col))

    def _read_string(self, line: int, col: int):
        """读取字符串字面量

        字符串用双引号包围，支持以下转义序列：
        - \\n  -> 换行符
        - \\t  -> 制表符
        - \\\\ -> 反斜杠
        - \\" -> 双引号

        如果字符串没有正确的结束引号，抛出 LexerError。
        """
        self._advance()  # 跳过开头的 "
        chars = []

        while self.pos < len(self.source) and self.source[self.pos] != '"':
            if self.source[self.pos] == "\\":
                self._advance()  # 跳过反斜杠
                if self.pos < len(self.source):
                    escape_char = self._advance()
                    escape_map = {
                        "n": "\n",
                        "t": "\t",
                        "\\": "\\",
                        '"': '"',
                    }
                    if escape_char in escape_map:
                        chars.append(escape_map[escape_char])
                    else:
                        # 未知转义序列，保留原样
                        chars.append("\\")
                        chars.append(escape_char)
            else:
                chars.append(self._advance())

        if self.pos >= len(self.source):
            raise LexerError("未终止的字符串字面量", line, col)

        self._advance()  # 跳过结尾的 "
        self.tokens.append(Token(TokenType.STRING, "".join(chars), line, col))
