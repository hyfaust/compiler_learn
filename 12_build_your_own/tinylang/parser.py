"""
语法分析器 (Parser)

将 Token 序列转换为抽象语法树 (AST)。使用递归下降解析法
（Recursive Descent Parsing），这是一种直观且易于实现的
自顶向下的语法分析方法。

递归下降解析法的核心思想：
- 每条语法规则对应一个解析方法
- 方法之间通过递归调用来处理嵌套结构
- 运算符优先级通过方法的层级关系来体现

TinyLang 的运算符优先级（从低到高）：
    1. or
    2. and
    3. 比较: ==, !=, <, >, <=, >=
    4. 加减: +, -
    5. 乘除: *, /, %
    6. 一元: -, not
    7. 后缀: 函数调用(), 数组索引[]
    8. 基本: 字面量, 标识符, 括号表达式
"""

from .lexer import Token, TokenType
from .ast_nodes import *
from .errors import ParserError

# 为了方便，导入常用的 TokenType
INTEGER = TokenType.INTEGER
FLOAT = TokenType.FLOAT
STRING = TokenType.STRING
IDENTIFIER = TokenType.IDENTIFIER
LET = TokenType.LET
IF = TokenType.IF
ELIF = TokenType.ELIF
ELSE = TokenType.ELSE
WHILE = TokenType.WHILE
FOR = TokenType.FOR
IN = TokenType.IN
FUNC = TokenType.FUNC
RETURN = TokenType.RETURN
BREAK = TokenType.BREAK
CONTINUE = TokenType.CONTINUE
AND = TokenType.AND
OR = TokenType.OR
NOT = TokenType.NOT
TRUE = TokenType.TRUE
FALSE = TokenType.FALSE
NONE = TokenType.NONE
PLUS = TokenType.PLUS
MINUS = TokenType.MINUS
STAR = TokenType.STAR
SLASH = TokenType.SLASH
PERCENT = TokenType.PERCENT
ASSIGN = TokenType.ASSIGN
EQ = TokenType.EQ
NEQ = TokenType.NEQ
LT = TokenType.LT
GT = TokenType.GT
LTE = TokenType.LTE
GTE = TokenType.GTE
LPAREN = TokenType.LPAREN
RPAREN = TokenType.RPAREN
LBRACKET = TokenType.LBRACKET
RBRACKET = TokenType.RBRACKET
LBRACE = TokenType.LBRACE
RBRACE = TokenType.RBRACE
COMMA = TokenType.COMMA
SEMICOLON = TokenType.SEMICOLON
EOF = TokenType.EOF


class Parser:
    """递归下降语法分析器

    将 Token 序列解析为 AST。解析过程使用以下辅助方法
    来实现 Token 的消耗和检查：

    - check(type):  检查当前 Token 类型，不消耗
    - match(*types): 如果当前 Token 匹配则消耗并返回 True
    - expect(type):  消耗当前 Token，如果不匹配则报错
    - advance():     消耗并返回当前 Token

    使用方法：
        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()
    """

    def __init__(self, tokens: list[Token]):
        self.tokens = tokens
        self.pos = 0

    # ============================================================
    #  Token 操作辅助方法
    # ============================================================

    @property
    def current_token(self) -> Token:
        """获取当前 Token（不消耗）"""
        return self.tokens[self.pos]

    def advance(self) -> Token:
        """消耗并返回当前 Token，位置前进一位"""
        token = self.tokens[self.pos]
        self.pos += 1
        return token

    def check(self, token_type: TokenType) -> bool:
        """检查当前 Token 是否为指定类型（不消耗）"""
        return self.current_token.type == token_type

    def match(self, *types: TokenType) -> bool:
        """如果当前 Token 类型匹配任一给定类型，则消耗并返回 True"""
        if self.current_token.type in types:
            self.advance()
            return True
        return False

    def expect(self, token_type: TokenType) -> Token:
        """消耗当前 Token，要求其类型匹配指定类型

        如果不匹配，抛出 ParserError。
        """
        if self.current_token.type != token_type:
            raise ParserError(
                f"期望 {token_type.name}，但得到 {self.current_token.type.name} "
                f"('{self.current_token.value}')",
                self.current_token.line,
                self.current_token.column,
            )
        return self.advance()

    # ============================================================
    #  入口
    # ============================================================

    def parse(self) -> Program:
        """解析整个程序，返回 Program AST 节点"""
        statements = []
        while not self.check(EOF):
            statements.append(self._parse_statement())
        return Program(statements)

    # ============================================================
    #  语句解析
    # ============================================================

    def _parse_statement(self) -> Statement:
        """解析一条语句

        根据当前 Token 类型分派到不同的语句解析方法。
        """
        if self.check(LET):
            return self._parse_let()
        if self.check(IF):
            return self._parse_if()
        if self.check(WHILE):
            return self._parse_while()
        if self.check(FOR):
            return self._parse_for()
        if self.check(FUNC):
            return self._parse_func_def()
        if self.check(RETURN):
            return self._parse_return()
        if self.check(BREAK):
            return self._parse_break()
        if self.check(CONTINUE):
            return self._parse_continue()
        return self._parse_expr_or_assign()

    def _parse_let(self) -> LetStatement:
        """解析 let 声明语句: let name = expr;"""
        self.expect(LET)
        name = self.expect(IDENTIFIER).value
        self.expect(ASSIGN)
        value = self._parse_expression()
        self.expect(SEMICOLON)
        return LetStatement(name, value)

    def _parse_if(self) -> IfStatement:
        """解析 if/elif/else 语句（支持可选括号和无花括号单语句）"""
        self.expect(IF)
        has_paren = self.match(LPAREN)
        condition = self._parse_expression()
        if has_paren:
            self.expect(RPAREN)
        then_body = self._parse_block_or_stmt()

        elif_clauses = []
        while self.match(ELIF):
            has_paren = self.match(LPAREN)
            elif_cond = self._parse_expression()
            if has_paren:
                self.expect(RPAREN)
            elif_body = self._parse_block_or_stmt()
            elif_clauses.append((elif_cond, elif_body))

        else_body = None
        if self.match(ELSE):
            else_body = self._parse_block_or_stmt()

        return IfStatement(condition, then_body, elif_clauses, else_body)

    def _parse_while(self) -> WhileStatement:
        """解析 while 循环（支持可选括号和无花括号单语句）"""
        self.expect(WHILE)
        has_paren = self.match(LPAREN)
        condition = self._parse_expression()
        if has_paren:
            self.expect(RPAREN)
        body = self._parse_block_or_stmt()
        return WhileStatement(condition, body)

    def _parse_for(self) -> ForStatement:
        """解析 for-in 循环: for name in expr { stmts }"""
        self.expect(FOR)
        var_name = self.expect(IDENTIFIER).value
        self.expect(IN)
        iterable = self._parse_expression()
        body = self._parse_block()
        return ForStatement(var_name, iterable, body)

    def _parse_func_def(self) -> FunctionDef:
        """解析函数定义: func name(params) { stmts }"""
        self.expect(FUNC)
        name = self.expect(IDENTIFIER).value
        self.expect(LPAREN)
        params = self._parse_param_list()
        self.expect(RPAREN)
        body = self._parse_block()
        return FunctionDef(name, params, body)

    def _parse_anon_func(self) -> FunctionDef:
        """解析匿名函数表达式: fn(params) { body }"""
        self.expect(FUNC)
        self.expect(LPAREN)
        params = self._parse_param_list()
        self.expect(RPAREN)
        body = self._parse_block()
        return FunctionDef(None, params, body)

    def _parse_param_list(self) -> list[str]:
        """解析函数参数列表"""
        params = []
        if not self.check(RPAREN):
            params.append(self.expect(IDENTIFIER).value)
            while self.match(COMMA):
                params.append(self.expect(IDENTIFIER).value)
        return params

    def _parse_return(self) -> ReturnStatement:
        """解析 return 语句: return expr; 或 return;"""
        self.expect(RETURN)
        value = None
        # 如果下一个 Token 不是分号，说明有返回值表达式
        if not self.check(SEMICOLON) and not self.check(RBRACE) and not self.check(EOF):
            value = self._parse_expression()
        self.expect(SEMICOLON)
        return ReturnStatement(value)

    def _parse_break(self) -> BreakStatement:
        """解析 break 语句: break;"""
        self.expect(BREAK)
        self.expect(SEMICOLON)
        return BreakStatement()

    def _parse_continue(self) -> ContinueStatement:
        """解析 continue 语句: continue;"""
        self.expect(CONTINUE)
        self.expect(SEMICOLON)
        return ContinueStatement()

    def _parse_expr_or_assign(self) -> Statement:
        """解析表达式语句或赋值语句

        先解析一个表达式，然后检查是否跟随 '='：
        - 如果是 '='，则为赋值语句（左侧必须是标识符或索引表达式）
        - 否则为表达式语句
        """
        expr = self._parse_expression()

        if self.match(ASSIGN):
            value = self._parse_expression()
            self.expect(SEMICOLON)
            # 验证赋值目标
            if isinstance(expr, (Identifier, IndexExpression)):
                return AssignmentStatement(expr, value)
            raise ParserError(
                "无效的赋值目标",
                self.current_token.line,
                self.current_token.column,
            )

        self.expect(SEMICOLON)
        return ExpressionStatement(expr)

    def _parse_block(self) -> list[Statement]:
        """解析代码块: { stmts }

        代码块由花括号包围，包含零条或多条语句。
        """
        self.expect(LBRACE)
        statements = []
        while not self.check(RBRACE) and not self.check(EOF):
            statements.append(self._parse_statement())
        self.expect(RBRACE)
        return statements

    def _parse_block_or_stmt(self) -> list[Statement]:
        """解析代码块或单条语句（用于 if/while 的无花括号单语句体）"""
        if self.check(LBRACE):
            return self._parse_block()
        return [self._parse_statement()]

    # ============================================================
    #  表达式解析（递归下降，按优先级分层）
    # ============================================================

    def _parse_expression(self) -> Expression:
        """表达式入口 —— 优先级最低（or）"""
        return self._parse_or()

    def _parse_or(self) -> Expression:
        """解析 or 表达式: and_expr ('or' and_expr)*"""
        left = self._parse_and()
        while self.match(OR):
            right = self._parse_and()
            left = BinaryOp(left, "or", right)
        return left

    def _parse_and(self) -> Expression:
        """解析 and 表达式: cmp_expr ('and' cmp_expr)*"""
        left = self._parse_comparison()
        while self.match(AND):
            right = self._parse_comparison()
            left = BinaryOp(left, "and", right)
        return left

    def _parse_comparison(self) -> Expression:
        """解析比较表达式: add_expr (cmp_op add_expr)*

        支持的比较运算符: ==, !=, <, >, <=, >=
        """
        left = self._parse_addition()
        while self.current_token.type in (EQ, NEQ, LT, GT, LTE, GTE):
            op_token = self.advance()
            right = self._parse_addition()
            left = BinaryOp(left, op_token.value, right)
        return left

    def _parse_addition(self) -> Expression:
        """解析加减表达式: mul_expr (('+' | '-') mul_expr)*"""
        left = self._parse_multiplication()
        while self.current_token.type in (PLUS, MINUS):
            op_token = self.advance()
            right = self._parse_multiplication()
            left = BinaryOp(left, op_token.value, right)
        return left

    def _parse_multiplication(self) -> Expression:
        """解析乘除模表达式: unary (('*' | '/' | '%') unary)*"""
        left = self._parse_unary()
        while self.current_token.type in (STAR, SLASH, PERCENT):
            op_token = self.advance()
            right = self._parse_unary()
            left = BinaryOp(left, op_token.value, right)
        return left

    def _parse_unary(self) -> Expression:
        """解析一元表达式: ('-' | 'not') unary | postfix"""
        if self.match(MINUS):
            operand = self._parse_unary()
            return UnaryOp("-", operand)
        if self.match(NOT):
            operand = self._parse_unary()
            return UnaryOp("not", operand)
        return self._parse_postfix()

    def _parse_postfix(self) -> Expression:
        """解析后缀表达式: primary (call | index)*

        后缀操作包括：
        - 函数调用: expr(args)
        - 数组索引: expr[index]
        """
        expr = self._parse_primary()

        while True:
            if self.match(LPAREN):
                # 函数调用
                args = []
                if not self.check(RPAREN):
                    args.append(self._parse_expression())
                    while self.match(COMMA):
                        args.append(self._parse_expression())
                self.expect(RPAREN)
                expr = CallExpression(expr, args)
            elif self.match(LBRACKET):
                # 数组索引
                index = self._parse_expression()
                self.expect(RBRACKET)
                expr = IndexExpression(expr, index)
            else:
                break

        return expr

    def _parse_primary(self) -> Expression:
        """解析基本表达式

        基本表达式是最底层的表达式类型，包括：
        - 整数字面量: 42
        - 浮点数字面量: 3.14
        - 字符串字面量: "hello"
        - 布尔字面量: true, false
        - 标识符: x, foo
        - 括号表达式: (expr)
        - 数组字面量: [1, 2, 3]
        """
        # 整数字面量
        if self.match(INTEGER):
            return IntegerLiteral(self.tokens[self.pos - 1].value)

        # 浮点数字面量
        if self.match(FLOAT):
            return FloatLiteral(self.tokens[self.pos - 1].value)

        # 字符串字面量
        if self.match(STRING):
            return StringLiteral(self.tokens[self.pos - 1].value)

        # 布尔字面量
        if self.match(TRUE):
            return BooleanLiteral(True)
        if self.match(FALSE):
            return BooleanLiteral(False)

        # none 字面量
        if self.match(NONE):
            return NoneLiteral()

        # 标识符
        if self.match(IDENTIFIER):
            return Identifier(self.tokens[self.pos - 1].value)

        # 括号表达式: (expr)
        if self.match(LPAREN):
            expr = self._parse_expression()
            self.expect(RPAREN)
            return expr

        # 数组字面量: [elem, ...]
        if self.match(LBRACKET):
            return self._parse_array_literal()

        # 匿名函数: fn(params) { body }
        if self.check(FUNC):
            return self._parse_anon_func()

        # 无法解析
        raise ParserError(
            f"无法解析的表达式，遇到: {self.current_token.type.name} "
            f"('{self.current_token.value}')",
            self.current_token.line,
            self.current_token.column,
        )

    def _parse_array_literal(self) -> ArrayLiteral:
        """解析数组字面量: [expr, expr, ...]"""
        elements = []
        if not self.check(RBRACKET):
            elements.append(self._parse_expression())
            while self.match(COMMA):
                elements.append(self._parse_expression())
        self.expect(RBRACKET)
        return ArrayLiteral(elements)
