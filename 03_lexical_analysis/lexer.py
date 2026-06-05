"""
手写词法分析器实现
================

本模块实现了一个完整的词法分析器，支持：
- 整数和浮点数
- 标识符和关键字
- 运算符和分隔符
- 字符串和字符字面量
- 单行和多行注释
- 错误处理和行号追踪
"""

from enum import Enum, auto
from dataclasses import dataclass
from typing import List, Optional


class TokenType(Enum):
    """Token类型枚举"""
    
    # 字面量
    INTEGER = auto()       # 整数: 42, 0xFF, 077
    FLOAT = auto()         # 浮点数: 3.14, 1e-5
    CHAR = auto()          # 字符: 'a', '\n'
    STRING = auto()        # 字符串: "hello"
    
    # 标识符和关键字
    IDENTIFIER = auto()    # 标识符: count, _temp
    KEYWORD = auto()       # 关键字: if, else, while, int, ...
    
    # 运算符
    PLUS = auto()          # +
    MINUS = auto()         # -
    STAR = auto()          # *
    SLASH = auto()         # /
    PERCENT = auto()       # %
    
    ASSIGN = auto()        # =
    EQUAL = auto()         # ==
    NOT_EQUAL = auto()     # !=
    LESS = auto()          # <
    LESS_EQUAL = auto()    # <=
    GREATER = auto()       # >
    GREATER_EQUAL = auto() # >=
    
    AND = auto()           # &&
    OR = auto()            # ||
    NOT = auto()           # !
    
    BIT_AND = auto()       # &
    BIT_OR = auto()        # |
    BIT_XOR = auto()       # ^
    BIT_NOT = auto()       # ~
    LSHIFT = auto()        # <<
    RSHIFT = auto()        # >>
    
    INCREMENT = auto()     # ++
    DECREMENT = auto()     # --
    
    PLUS_ASSIGN = auto()   # +=
    MINUS_ASSIGN = auto()  # -=
    STAR_ASSIGN = auto()   # *=
    SLASH_ASSIGN = auto()  # /=
    
    ARROW = auto()         # ->
    DOT = auto()           # .
    
    # 分隔符
    LPAREN = auto()        # (
    RPAREN = auto()        # )
    LBRACE = auto()        # {
    RBRACE = auto()        # }
    LBRACKET = auto()      # [
    RBRACKET = auto()      # ]
    SEMICOLON = auto()     # ;
    COMMA = auto()         # ,
    COLON = auto()         # :
    QUESTION = auto()      # ?
    
    # 特殊
    NEWLINE = auto()       # 换行
    EOF = auto()           # 文件结束
    COMMENT = auto()       # 注释
    PREPROCESSOR = auto()  # 预处理指令
    ERROR = auto()         # 错误


# C语言关键字列表
KEYWORDS = {
    'auto', 'break', 'case', 'char', 'const', 'continue',
    'default', 'do', 'double', 'else', 'enum', 'extern',
    'float', 'for', 'goto', 'if', 'inline', 'int',
    'long', 'register', 'restrict', 'return', 'short', 'signed',
    'sizeof', 'static', 'struct', 'switch', 'typedef', 'union',
    'unsigned', 'void', 'volatile', 'while',
    '_Bool', '_Complex', '_Imaginary',
    'bool', 'true', 'false',  # C99+
}


@dataclass
class Position:
    """源代码位置信息"""
    line: int
    column: int
    offset: int
    
    def __str__(self):
        return f"行:{self.line}, 列:{self.column}"


@dataclass
class Token:
    """词法单元"""
    type: TokenType
    value: str
    position: Position
    
    def __repr__(self):
        if self.value:
            return f"Token({self.type.name}, '{self.value}', {self.position})"
        return f"Token({self.type.name}, {self.position})"


class LexerError(Exception):
    """词法分析错误"""
    def __init__(self, message: str, position: Position):
        self.position = position
        super().__init__(f"词法错误 {position}: {message}")


class Lexer:
    """
    手写词法分析器
    
    实现了状态机词法分析，支持C语言风格的词法规则。
    """
    
    def __init__(self, source: str):
        """
        初始化词法分析器
        
        Args:
            source: 源代码字符串
        """
        self.source = source
        self.pos = 0
        self.line = 1
        self.column = 1
        self.tokens: List[Token] = []
        self.errors: List[LexerError] = []
    
    @property
    def current_char(self) -> Optional[str]:
        """获取当前字符"""
        if self.pos < len(self.source):
            return self.source[self.pos]
        return None
    
    @property
    def peek_char(self) -> Optional[str]:
        """预读下一个字符"""
        if self.pos + 1 < len(self.source):
            return self.source[self.pos + 1]
        return None
    
    def get_position(self) -> Position:
        """获取当前位置"""
        return Position(self.line, self.column, self.pos)
    
    def advance(self) -> str:
        """前进一个字符"""
        char = self.source[self.pos]
        if char == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        self.pos += 1
        return char
    
    def skip_whitespace(self):
        """跳过空白字符（不包括换行）"""
        while self.current_char and self.current_char in ' \t\r':
            self.advance()
    
    def skip_single_line_comment(self) -> str:
        """跳过单行注释，返回注释内容"""
        comment_start = self.pos
        while self.current_char and self.current_char != '\n':
            self.advance()
        return self.source[comment_start:self.pos]
    
    def skip_multi_line_comment(self) -> str:
        """跳过多行注释，返回注释内容"""
        comment_start = self.pos
        self.advance()  # 跳过 *
        self.advance()  # 跳过 /
        
        while self.current_char:
            if self.current_char == '*' and self.peek_char == '/':
                self.advance()  # 跳过 *
                self.advance()  # 跳过 /
                return self.source[comment_start:self.pos]
            self.advance()
        
        raise LexerError("未结束的多行注释", self.get_position())
    
    def read_number(self) -> Token:
        """读取数字（整数或浮点数）"""
        start_pos = self.get_position()
        num_str = ''
        is_float = False
        
        # 处理十六进制
        if self.current_char == '0' and self.peek_char in 'xX':
            num_str += self.advance()  # 0
            num_str += self.advance()  # x
            while self.current_char and (self.current_char.isdigit() or 
                                         self.current_char.lower() in 'abcdef'):
                num_str += self.advance()
            return Token(TokenType.INTEGER, num_str, start_pos)
        
        # 处理八进制
        if self.current_char == '0' and self.peek_char and self.peek_char.isdigit():
            num_str += self.advance()  # 0
            while self.current_char and self.current_char.isdigit():
                num_str += self.advance()
            return Token(TokenType.INTEGER, num_str, start_pos)
        
        # 处理十进制和浮点数
        while self.current_char and self.current_char.isdigit():
            num_str += self.advance()
        
        # 处理小数点
        if self.current_char == '.' and self.peek_char and self.peek_char.isdigit():
            is_float = True
            num_str += self.advance()  # .
            while self.current_char and self.current_char.isdigit():
                num_str += self.advance()
        
        # 处理科学计数法
        if self.current_char and self.current_char.lower() == 'e':
            is_float = True
            num_str += self.advance()  # e
            if self.current_char in '+-':
                num_str += self.advance()
            while self.current_char and self.current_char.isdigit():
                num_str += self.advance()
        
        # 处理后缀 (L, U, f, ...)
        while self.current_char and self.current_char.lower() in 'luf':
            num_str += self.advance()
        
        token_type = TokenType.FLOAT if is_float else TokenType.INTEGER
        return Token(token_type, num_str, start_pos)
    
    def read_identifier(self) -> Token:
        """读取标识符或关键字"""
        start_pos = self.get_position()
        identifier = ''
        
        while self.current_char and (self.current_char.isalnum() or 
                                      self.current_char == '_'):
            identifier += self.advance()
        
        # 检查是否是关键字
        if identifier in KEYWORDS:
            return Token(TokenType.KEYWORD, identifier, start_pos)
        
        return Token(TokenType.IDENTIFIER, identifier, start_pos)
    
    def read_string(self) -> Token:
        """读取字符串字面量"""
        start_pos = self.get_position()
        quote_char = self.advance()  # 跳过开始的引号
        string_content = ''
        
        while self.current_char and self.current_char != quote_char:
            if self.current_char == '\\':
                self.advance()  # 跳过反斜杠
                if self.current_char:
                    # 处理转义字符
                    escape_chars = {
                        'n': '\n', 't': '\t', 'r': '\r',
                        '\\': '\\', '\'': '\'', '"': '"',
                        '0': '\0', 'a': '\a', 'b': '\b',
                        'f': '\f', 'v': '\v',
                    }
                    char = self.advance()
                    string_content += escape_chars.get(char, char)
            elif self.current_char == '\n':
                raise LexerError("字符串未结束", start_pos)
            else:
                string_content += self.advance()
        
        if not self.current_char:
            raise LexerError("字符串未结束", start_pos)
        
        self.advance()  # 跳过结束的引号
        
        token_type = TokenType.CHAR if quote_char == '\'' else TokenType.STRING
        return Token(token_type, string_content, start_pos)
    
    def read_preprocessor(self) -> Token:
        """读取预处理指令"""
        start_pos = self.get_position()
        directive = ''
        
        # 跳过 #
        self.advance()
        
        # 跳过空白
        while self.current_char and self.current_char in ' \t':
            self.advance()
        
        # 读取指令名
        while self.current_char and (self.current_char.isalnum() or 
                                      self.current_char == '_'):
            directive += self.advance()
        
        # 读取到行尾
        while self.current_char and self.current_char != '\n':
            directive += self.advance()
        
        return Token(TokenType.PREPROCESSOR, directive.strip(), start_pos)
    
    def tokenize(self) -> List[Token]:
        """
        执行词法分析
        
        Returns:
            Token列表
        """
        tokens = []
        
        while self.current_char is not None:
            # 跳过空白字符
            if self.current_char in ' \t\r':
                self.skip_whitespace()
                continue
            
            # 处理换行
            if self.current_char == '\n':
                pos = self.get_position()
                self.advance()
                tokens.append(Token(TokenType.NEWLINE, '\\n', pos))
                continue
            
            # 处理注释
            if self.current_char == '/' and self.peek_char == '/':
                self.advance()  # 跳过第一个 /
                self.advance()  # 跳过第二个 /
                self.skip_single_line_comment()
                continue
            
            if self.current_char == '/' and self.peek_char == '*':
                self.advance()  # 跳过 /
                self.skip_multi_line_comment()
                continue
            
            # 处理预处理指令
            if self.current_char == '#':
                tokens.append(self.read_preprocessor())
                continue
            
            # 处理数字
            if self.current_char.isdigit():
                tokens.append(self.read_number())
                continue
            
            # 处理标识符和关键字
            if self.current_char.isalpha() or self.current_char == '_':
                tokens.append(self.read_identifier())
                continue
            
            # 处理字符串和字符
            if self.current_char in '"\'':
                try:
                    tokens.append(self.read_string())
                except LexerError as e:
                    self.errors.append(e)
                    # 跳过错误字符继续
                    self.advance()
                continue
            
            # 处理运算符和分隔符
            pos = self.get_position()
            char = self.advance()
            
            # 双字符运算符
            if char == '+' and self.current_char == '+':
                self.advance()
                tokens.append(Token(TokenType.INCREMENT, '++', pos))
            elif char == '+' and self.current_char == '=':
                self.advance()
                tokens.append(Token(TokenType.PLUS_ASSIGN, '+=', pos))
            elif char == '-' and self.current_char == '-':
                self.advance()
                tokens.append(Token(TokenType.DECREMENT, '--', pos))
            elif char == '-' and self.current_char == '>':
                self.advance()
                tokens.append(Token(TokenType.ARROW, '->', pos))
            elif char == '-' and self.current_char == '=':
                self.advance()
                tokens.append(Token(TokenType.MINUS_ASSIGN, '-=', pos))
            elif char == '*' and self.current_char == '=':
                self.advance()
                tokens.append(Token(TokenType.STAR_ASSIGN, '*=', pos))
            elif char == '/' and self.current_char == '=':
                self.advance()
                tokens.append(Token(TokenType.SLASH_ASSIGN, '/=', pos))
            elif char == '=' and self.current_char == '=':
                self.advance()
                tokens.append(Token(TokenType.EQUAL, '==', pos))
            elif char == '!' and self.current_char == '=':
                self.advance()
                tokens.append(Token(TokenType.NOT_EQUAL, '!=', pos))
            elif char == '<' and self.current_char == '=':
                self.advance()
                tokens.append(Token(TokenType.LESS_EQUAL, '<=', pos))
            elif char == '<' and self.current_char == '<':
                self.advance()
                tokens.append(Token(TokenType.LSHIFT, '<<', pos))
            elif char == '>' and self.current_char == '=':
                self.advance()
                tokens.append(Token(TokenType.GREATER_EQUAL, '>=', pos))
            elif char == '>' and self.current_char == '>':
                self.advance()
                tokens.append(Token(TokenType.RSHIFT, '>>', pos))
            elif char == '&' and self.current_char == '&':
                self.advance()
                tokens.append(Token(TokenType.AND, '&&', pos))
            elif char == '|' and self.current_char == '|':
                self.advance()
                tokens.append(Token(TokenType.OR, '||', pos))
            # 单字符运算符和分隔符
            elif char == '+':
                tokens.append(Token(TokenType.PLUS, '+', pos))
            elif char == '-':
                tokens.append(Token(TokenType.MINUS, '-', pos))
            elif char == '*':
                tokens.append(Token(TokenType.STAR, '*', pos))
            elif char == '/':
                tokens.append(Token(TokenType.SLASH, '/', pos))
            elif char == '%':
                tokens.append(Token(TokenType.PERCENT, '%', pos))
            elif char == '=':
                tokens.append(Token(TokenType.ASSIGN, '=', pos))
            elif char == '<':
                tokens.append(Token(TokenType.LESS, '<', pos))
            elif char == '>':
                tokens.append(Token(TokenType.GREATER, '>', pos))
            elif char == '!':
                tokens.append(Token(TokenType.NOT, '!', pos))
            elif char == '&':
                tokens.append(Token(TokenType.BIT_AND, '&', pos))
            elif char == '|':
                tokens.append(Token(TokenType.BIT_OR, '|', pos))
            elif char == '^':
                tokens.append(Token(TokenType.BIT_XOR, '^', pos))
            elif char == '~':
                tokens.append(Token(TokenType.BIT_NOT, '~', pos))
            elif char == '(':
                tokens.append(Token(TokenType.LPAREN, '(', pos))
            elif char == ')':
                tokens.append(Token(TokenType.RPAREN, ')', pos))
            elif char == '{':
                tokens.append(Token(TokenType.LBRACE, '{', pos))
            elif char == '}':
                tokens.append(Token(TokenType.RBRACE, '}', pos))
            elif char == '[':
                tokens.append(Token(TokenType.LBRACKET, '[', pos))
            elif char == ']':
                tokens.append(Token(TokenType.RBRACKET, ']', pos))
            elif char == ';':
                tokens.append(Token(TokenType.SEMICOLON, ';', pos))
            elif char == ',':
                tokens.append(Token(TokenType.COMMA, ',', pos))
            elif char == ':':
                tokens.append(Token(TokenType.COLON, ':', pos))
            elif char == '?':
                tokens.append(Token(TokenType.QUESTION, '?', pos))
            elif char == '.':
                tokens.append(Token(TokenType.DOT, '.', pos))
            else:
                error = LexerError(f"非法字符: '{char}'", pos)
                self.errors.append(error)
        
        # 添加EOF
        tokens.append(Token(TokenType.EOF, '', self.get_position()))
        
        return tokens


def main():
    """演示词法分析器"""
    
    # 测试代码
    test_code = '''
#include <stdio.h>

// 计算斐波那契数列
int fibonacci(int n) {
    if (n <= 1) {
        return n;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}

/*
 * 主函数
 * 演示词法分析器功能
 */
int main() {
    int count = 10;
    float pi = 3.14159;
    char ch = 'A';
    char *msg = "Hello, World!";
    
    // 打印斐波那契数
    for (int i = 0; i < count; i++) {
        printf("fib(%d) = %d\\n", i, fibonacci(i));
    }
    
    // 各种运算符测试
    int a = 100, b = 200;
    int sum = a + b;
    int diff = a - b;
    int product = a * b;
    
    if (a > 0 && b > 0) {
        printf("Both positive\\n");
    }
    
    // 十六进制和八进制
    int hex = 0xFF;
    int oct = 077;
    
    // 科学计数法
    float e = 1.5e-3;
    
    return 0;
}
'''
    
    print("=" * 60)
    print("词法分析器演示")
    print("=" * 60)
    print()
    
    # 创建词法分析器
    lexer = Lexer(test_code)
    
    # 执行词法分析
    try:
        tokens = lexer.tokenize()
        
        # 过滤掉换行和注释，只显示重要Token
        important_tokens = [t for t in tokens 
                           if t.type not in (TokenType.NEWLINE,)]
        
        print(f"共生成 {len(important_tokens)} 个Token:")
        print("-" * 60)
        
        # 打印Token
        for i, token in enumerate(important_tokens, 1):
            if token.type == TokenType.EOF:
                print(f"{i:4d}: {token.type.name:<20} (结束)")
            else:
                value_repr = repr(token.value) if token.value else '-'
                print(f"{i:4d}: {token.type.name:<20} {value_repr:<20} {token.position}")
        
        # 统计信息
        print("-" * 60)
        print(f"Token类型统计:")
        type_counts = {}
        for token in tokens:
            type_counts[token.type.name] = type_counts.get(token.type.name, 0) + 1
        for type_name, count in sorted(type_counts.items()):
            print(f"  {type_name}: {count}")
        
    except LexerError as e:
        print(f"词法分析错误: {e}")
    
    # 显示错误
    if lexer.errors:
        print(f"\n发现 {len(lexer.errors)} 个错误:")
        for error in lexer.errors:
            print(f"  - {error}")


if __name__ == '__main__':
    main()
