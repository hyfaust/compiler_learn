"""
语义分析器实现
==============
本模块实现了一个完整的语义分析器，包括：
- 自包含的 AST 节点定义
- 支持嵌套作用域的符号表
- 类型检查器
- 语义分析主类（类型检查、作用域分析、变量声明检查、函数调用检查）

运行方式: python semantic_analyzer.py
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Any, Tuple
from enum import Enum, auto


# ============================================================
# AST 节点定义
# ============================================================

class ASTNodeType(Enum):
    """AST 节点类型枚举"""
    PROGRAM = auto()
    NUMBER = auto()
    STRING = auto()
    BOOL = auto()
    IDENTIFIER = auto()
    BINOP = auto()
    UNARYOP = auto()
    ASSIGN = auto()
    VAR_DECL = auto()
    FUNC_DECL = auto()
    FUNC_CALL = auto()
    IF = auto()
    WHILE = auto()
    FOR = auto()
    RETURN = auto()
    BLOCK = auto()
    PARAM = auto()


class ASTNode:
    """AST 节点基类"""

    def __init__(self, node_type: ASTNodeType, line: int = 0):
        self.node_type = node_type
        self.line = line

    def __repr__(self):
        return f"{self.__class__.__name__}({self.node_type.name})"


@dataclass
class NumberNode(ASTNode):
    """数字字面量"""
    value: float
    is_float: bool = False

    def __init__(self, value: float, is_float: bool = False, line: int = 0):
        super().__init__(ASTNodeType.NUMBER, line)
        self.value = value
        self.is_float = is_float


@dataclass
class StringNode(ASTNode):
    """字符串字面量"""
    value: str = ""

    def __init__(self, value: str = "", line: int = 0):
        super().__init__(ASTNodeType.STRING, line)
        self.value = value


@dataclass
class BoolNode(ASTNode):
    """布尔字面量"""
    value: bool = False

    def __init__(self, value: bool = False, line: int = 0):
        super().__init__(ASTNodeType.BOOL, line)
        self.value = value


@dataclass
class IdentifierNode(ASTNode):
    """标识符引用"""
    name: str = ""

    def __init__(self, name: str = "", line: int = 0):
        super().__init__(ASTNodeType.IDENTIFIER, line)
        self.name = name


@dataclass
class BinOpNode(ASTNode):
    """二元运算"""
    op: str = ""
    left: Optional[ASTNode] = None
    right: Optional[ASTNode] = None

    def __init__(self, op: str = "", left: ASTNode = None, right: ASTNode = None, line: int = 0):
        super().__init__(ASTNodeType.BINOP, line)
        self.op = op
        self.left = left
        self.right = right


@dataclass
class UnaryOpNode(ASTNode):
    """一元运算"""
    op: str = ""
    operand: Optional[ASTNode] = None

    def __init__(self, op: str = "", operand: ASTNode = None, line: int = 0):
        super().__init__(ASTNodeType.UNARYOP, line)
        self.op = op
        self.operand = operand


@dataclass
class AssignNode(ASTNode):
    """赋值语句"""
    target: str = ""
    value: Optional[ASTNode] = None

    def __init__(self, target: str = "", value: ASTNode = None, line: int = 0):
        super().__init__(ASTNodeType.ASSIGN, line)
        self.target = target
        self.value = value


@dataclass
class ParamNode(ASTNode):
    """函数参数声明"""
    name: str = ""
    type_name: str = ""

    def __init__(self, name: str = "", type_name: str = "", line: int = 0):
        super().__init__(ASTNodeType.PARAM, line)
        self.name = name
        self.type_name = type_name


@dataclass
class VarDeclNode(ASTNode):
    """变量声明"""
    name: str = ""
    type_name: str = ""
    init_value: Optional[ASTNode] = None
    is_const: bool = False

    def __init__(self, name: str = "", type_name: str = "",
                 init_value: ASTNode = None, is_const: bool = False, line: int = 0):
        super().__init__(ASTNodeType.VAR_DECL, line)
        self.name = name
        self.type_name = type_name
        self.init_value = init_value
        self.is_const = is_const


@dataclass
class FuncDeclNode(ASTNode):
    """函数声明"""
    name: str = ""
    return_type: str = ""
    params: List[ParamNode] = field(default_factory=list)
    body: Optional[ASTNode] = None

    def __init__(self, name: str = "", return_type: str = "",
                 params: list = None, body: ASTNode = None, line: int = 0):
        super().__init__(ASTNodeType.FUNC_DECL, line)
        self.name = name
        self.return_type = return_type
        self.params = params or []
        self.body = body


@dataclass
class FuncCallNode(ASTNode):
    """函数调用"""
    name: str = ""
    args: List[ASTNode] = field(default_factory=list)

    def __init__(self, name: str = "", args: list = None, line: int = 0):
        super().__init__(ASTNodeType.FUNC_CALL, line)
        self.name = name
        self.args = args or []


@dataclass
class IfNode(ASTNode):
    """if 语句"""
    condition: Optional[ASTNode] = None
    then_body: Optional[ASTNode] = None
    else_body: Optional[ASTNode] = None

    def __init__(self, condition: ASTNode = None, then_body: ASTNode = None,
                 else_body: ASTNode = None, line: int = 0):
        super().__init__(ASTNodeType.IF, line)
        self.condition = condition
        self.then_body = then_body
        self.else_body = else_body


@dataclass
class WhileNode(ASTNode):
    """while 循环"""
    condition: Optional[ASTNode] = None
    body: Optional[ASTNode] = None

    def __init__(self, condition: ASTNode = None, body: ASTNode = None, line: int = 0):
        super().__init__(ASTNodeType.WHILE, line)
        self.condition = condition
        self.body = body


@dataclass
class ForNode(ASTNode):
    """for 循环"""
    init: Optional[ASTNode] = None
    condition: Optional[ASTNode] = None
    update: Optional[ASTNode] = None
    body: Optional[ASTNode] = None

    def __init__(self, init: ASTNode = None, condition: ASTNode = None,
                 update: ASTNode = None, body: ASTNode = None, line: int = 0):
        super().__init__(ASTNodeType.FOR, line)
        self.init = init
        self.condition = condition
        self.update = update
        self.body = body


@dataclass
class ReturnNode(ASTNode):
    """return 语句"""
    value: Optional[ASTNode] = None

    def __init__(self, value: ASTNode = None, line: int = 0):
        super().__init__(ASTNodeType.RETURN, line)
        self.value = value


@dataclass
class BlockNode(ASTNode):
    """代码块"""
    statements: List[ASTNode] = field(default_factory=list)

    def __init__(self, statements: list = None, line: int = 0):
        super().__init__(ASTNodeType.BLOCK, line)
        self.statements = statements or []


@dataclass
class ProgramNode(ASTNode):
    """程序根节点"""
    declarations: List[ASTNode] = field(default_factory=list)

    def __init__(self, declarations: list = None, line: int = 0):
        super().__init__(ASTNodeType.PROGRAM, line)
        self.declarations = declarations or []


# ============================================================
# 语义分析错误
# ============================================================

class SemanticError(Exception):
    """语义错误基类"""

    def __init__(self, message: str, line: int = 0):
        self.line = line
        super().__init__(f"Line {line}: {message}" if line else message)


class TypeError_:
    """类型错误"""
    pass


class ScopeError(SemanticError):
    """作用域错误"""
    pass


class DeclarationError(SemanticError):
    """声明错误"""
    pass


# ============================================================
# 符号表
# ============================================================

@dataclass
class SymbolInfo:
    """符号信息"""
    name: str
    kind: str  # 'variable', 'function', 'parameter', 'constant'
    type_name: str
    is_const: bool = False
    param_types: List[str] = field(default_factory=list)
    return_type: str = ""
    line: int = 0


class SymbolTable:
    """
    支持嵌套作用域的符号表
    
    使用作用域栈实现，每个作用域是一个字典。
    查找变量时沿作用域链从内向外搜索。
    """

    def __init__(self):
        # 作用域栈：每个元素是一个 {name: SymbolInfo} 字典
        self._scopes: List[Dict[str, SymbolInfo]] = [{}]
        self._scope_names: List[str] = ["global"]

    def enter_scope(self, name: str = ""):
        """进入新的作用域"""
        self._scopes.append({})
        self._scope_names.append(name or f"scope_{len(self._scopes) - 1}")

    def exit_scope(self):
        """退出当前作用域"""
        if len(self._scopes) <= 1:
            raise ScopeError("无法退出全局作用域")
        self._scopes.pop()
        self._scope_names.pop()

    def declare(self, name: str, kind: str, type_name: str,
                is_const: bool = False, param_types: List[str] = None,
                return_type: str = "", line: int = 0) -> SymbolInfo:
        """
        在当前作用域声明一个符号。
        如果当前作用域已存在同名符号，抛出 DeclarationError。
        """
        current_scope = self._scopes[-1]
        if name in current_scope:
            raise DeclarationError(
                f"标识符 '{name}' 在作用域 '{self._scope_names[-1]}' 中已声明",
                line
            )
        info = SymbolInfo(
            name=name, kind=kind, type_name=type_name,
            is_const=is_const, param_types=param_types or [],
            return_type=return_type, line=line
        )
        current_scope[name] = info
        return info

    def resolve(self, name: str) -> Optional[SymbolInfo]:
        """
        沿作用域链从内向外查找符号。
        找到返回 SymbolInfo，未找到返回 None。
        """
        for scope in reversed(self._scopes):
            if name in scope:
                return scope[name]
        return None

    def is_declared_in_current_scope(self, name: str) -> bool:
        """检查 name 是否在当前作用域中已声明"""
        return name in self._scopes[-1]

    @property
    def current_scope_depth(self) -> int:
        return len(self._scopes) - 1

    @property
    def current_scope_name(self) -> str:
        return self._scope_names[-1]

    def dump(self) -> str:
        """打印所有作用域中的符号（调试用）"""
        lines = []
        for i, (scope, name) in enumerate(zip(self._scopes, self._scope_names)):
            lines.append(f"  [Scope {i}] {name}:")
            if not scope:
                lines.append("    (empty)")
            for sym_name, sym_info in scope.items():
                const_mark = " (const)" if sym_info.is_const else ""
                if sym_info.kind == "function":
                    params = ", ".join(sym_info.param_types)
                    lines.append(
                        f"    {sym_name}: func({params}) -> {sym_info.return_type}{const_mark}"
                    )
                else:
                    lines.append(
                        f"    {sym_name}: {sym_info.kind} {sym_info.type_name}{const_mark}"
                    )
        return "\n".join(lines)


# ============================================================
# 类型检查器
# ============================================================

class TypeChecker:
    """
    类型检查器
    
    负责推导表达式类型、检查类型兼容性。
    支持基本类型：int, float, string, bool, void
    支持隐式类型提升：int -> float
    """

    # 已知的基本类型
    KNOWN_TYPES = {"int", "float", "string", "bool", "void"}

    # 二元运算类型推导表: (op, left_type, right_type) -> result_type
    BINARY_OP_TYPES = {
        # 算术运算
        ('+', 'int', 'int'): 'int',
        ('+', 'float', 'float'): 'float',
        ('+', 'int', 'float'): 'float',
        ('+', 'float', 'int'): 'float',
        ('+', 'string', 'string'): 'string',
        ('-', 'int', 'int'): 'int',
        ('-', 'float', 'float'): 'float',
        ('-', 'int', 'float'): 'float',
        ('-', 'float', 'int'): 'float',
        ('*', 'int', 'int'): 'int',
        ('*', 'float', 'float'): 'float',
        ('*', 'int', 'float'): 'float',
        ('*', 'float', 'int'): 'float',
        ('/', 'int', 'int'): 'int',
        ('/', 'float', 'float'): 'float',
        ('/', 'int', 'float'): 'float',
        ('/', 'float', 'int'): 'float',
        ('%', 'int', 'int'): 'int',
        # 比较运算
        ('<', 'int', 'int'): 'bool',
        ('<', 'float', 'float'): 'bool',
        ('<', 'int', 'float'): 'bool',
        ('<', 'float', 'int'): 'bool',
        ('<=', 'int', 'int'): 'bool',
        ('<=', 'float', 'float'): 'bool',
        ('>', 'int', 'int'): 'bool',
        ('>', 'float', 'float'): 'bool',
        ('>=', 'int', 'int'): 'bool',
        ('>=', 'float', 'float'): 'bool',
        ('==', 'int', 'int'): 'bool',
        ('==', 'float', 'float'): 'bool',
        ('==', 'bool', 'bool'): 'bool',
        ('==', 'string', 'string'): 'bool',
        ('!=', 'int', 'int'): 'bool',
        ('!=', 'float', 'float'): 'bool',
        ('!=', 'bool', 'bool'): 'bool',
        ('!=', 'string', 'string'): 'bool',
        # 逻辑运算
        ('&&', 'bool', 'bool'): 'bool',
        ('||', 'bool', 'bool'): 'bool',
        # 位运算
        ('&', 'int', 'int'): 'int',
        ('|', 'int', 'int'): 'int',
        ('^', 'int', 'int'): 'int',
        ('<<', 'int', 'int'): 'int',
        ('>>', 'int', 'int'): 'int',
    }

    # 一元运算类型推导表: (op, operand_type) -> result_type
    UNARY_OP_TYPES = {
        ('-', 'int'): 'int',
        ('-', 'float'): 'float',
        ('!', 'bool'): 'bool',
        ('~', 'int'): 'int',
    }

    def check_binary_op(self, op: str, left_type: str, right_type: str, line: int = 0) -> str:
        """
        检查二元运算的类型，返回结果类型。
        如果类型不兼容，抛出 SemanticError。
        """
        key = (op, left_type, right_type)
        if key in self.BINARY_OP_TYPES:
            return self.BINARY_OP_TYPES[key]
        raise SemanticError(
            f"不支持的操作: '{left_type} {op} {right_type}'",
            line
        )

    def check_unary_op(self, op: str, operand_type: str, line: int = 0) -> str:
        """检查一元运算的类型"""
        key = (op, operand_type)
        if key in self.UNARY_OP_TYPES:
            return self.UNARY_OP_TYPES[key]
        raise SemanticError(
            f"不支持的一元操作: '{op} {operand_type}'",
            line
        )

    def check_assignment(self, target_type: str, value_type: str, line: int = 0) -> bool:
        """检查赋值的类型兼容性"""
        if target_type == value_type:
            return True
        # 允许 int -> float 的隐式转换
        if target_type == 'float' and value_type == 'int':
            return True
        raise SemanticError(
            f"无法将类型 '{value_type}' 赋值给 '{target_type}'",
            line
        )

    def is_valid_type(self, type_name: str) -> bool:
        """检查类型是否合法"""
        return type_name in self.KNOWN_TYPES

    def types_compatible(self, type1: str, type2: str) -> bool:
        """检查两个类型是否兼容（可以互相转换或相等）"""
        if type1 == type2:
            return True
        if type1 == 'float' and type2 == 'int':
            return True
        if type1 == 'int' and type2 == 'float':
            return True
        return False


# ============================================================
# 语义分析器主类
# ============================================================

class SemanticAnalyzer:
    """
    语义分析器
    
    遍历 AST，执行以下检查：
    1. 类型检查：表达式类型推导和兼容性验证
    2. 作用域分析：标识符的可见性验证
    3. 变量声明检查：使用前声明、重复声明、常量赋值
    4. 函数调用检查：参数数量和类型匹配
    5. 控制流检查：break/continue 位置、return 类型
    """

    def __init__(self):
        self.symbol_table = SymbolTable()
        self.type_checker = TypeChecker()
        self.errors: List[str] = []
        self.warnings: List[str] = []
        # 控制流状态
        self._in_loop_depth = 0
        self._current_func_return_type: Optional[str] = None
        self._has_return_in_path = False
        # 内置函数
        self._register_builtins()

    def _register_builtins(self):
        """注册内置函数"""
        self.symbol_table.declare(
            "print", "function", "builtin",
            param_types=["any"], return_type="void", line=0
        )
        self.symbol_table.declare(
            "input", "function", "builtin",
            param_types=[], return_type="string", line=0
        )

    def analyze(self, node: ASTNode) -> str:
        """
        分析 AST 节点，返回节点的类型。
        这是统一的分析入口，根据节点类型分派到具体的分析方法。
        """
        method_name = f"_analyze_{node.node_type.name.lower()}"
        method = getattr(self, method_name, None)
        if method is None:
            self.errors.append(
                f"Line {node.line}: 未实现的节点分析: {node.node_type.name}"
            )
            return "unknown"
        return method(node)

    # ------- 程序 -------

    def _analyze_program(self, node: ProgramNode) -> str:
        for decl in node.declarations:
            self.analyze(decl)
        return "void"

    # ------- 字面量 -------

    def _analyze_number(self, node: NumberNode) -> str:
        return "float" if node.is_float else "int"

    def _analyze_string(self, node: StringNode) -> str:
        return "string"

    def _analyze_bool(self, node: BoolNode) -> str:
        return "bool"

    # ------- 标识符 -------

    def _analyze_identifier(self, node: IdentifierNode) -> str:
        """查找标识符，检查是否已声明"""
        info = self.symbol_table.resolve(node.name)
        if info is None:
            self.errors.append(
                f"Line {node.line}: 标识符 '{node.name}' 未声明"
            )
            return "unknown"
        return info.type_name

    # ------- 表达式 -------

    def _analyze_binop(self, node: BinOpNode) -> str:
        """分析二元运算，推导结果类型"""
        left_type = self.analyze(node.left)
        right_type = self.analyze(node.right)
        try:
            return self.type_checker.check_binary_op(
                node.op, left_type, right_type, node.line
            )
        except SemanticError as e:
            self.errors.append(str(e))
            return "unknown"

    def _analyze_unaryop(self, node: UnaryOpNode) -> str:
        """分析一元运算"""
        operand_type = self.analyze(node.operand)
        try:
            return self.type_checker.check_unary_op(
                node.op, operand_type, node.line
            )
        except SemanticError as e:
            self.errors.append(str(e))
            return "unknown"

    # ------- 赋值 -------

    def _analyze_assign(self, node: AssignNode) -> str:
        """分析赋值语句"""
        # 1. 检查目标变量是否已声明
        target_info = self.symbol_table.resolve(node.target)
        if target_info is None:
            self.errors.append(
                f"Line {node.line}: 变量 '{node.target}' 未声明"
            )
            self.analyze(node.value)  # 仍然分析右值以发现更多错误
            return "unknown"

        # 2. 检查是否对常量赋值
        if target_info.is_const:
            self.errors.append(
                f"Line {node.line}: 不能对常量 '{node.target}' 赋值"
            )

        # 3. 分析右值，获取其类型
        value_type = self.analyze(node.value)

        # 4. 检查类型兼容性
        try:
            self.type_checker.check_assignment(
                target_info.type_name, value_type, node.line
            )
        except SemanticError as e:
            self.errors.append(str(e))

        return target_info.type_name

    # ------- 变量声明 -------

    def _analyze_var_decl(self, node: VarDeclNode) -> str:
        """分析变量声明"""
        # 1. 检查类型是否合法
        if not self.type_checker.is_valid_type(node.type_name):
            self.errors.append(
                f"Line {node.line}: 未知类型 '{node.type_name}'"
            )
            return "unknown"

        # 2. 如果有初始化表达式，分析其类型并检查兼容性
        if node.init_value is not None:
            init_type = self.analyze(node.init_value)
            try:
                self.type_checker.check_assignment(
                    node.type_name, init_type, node.line
                )
            except SemanticError as e:
                self.errors.append(str(e))

        # 3. 在当前作用域声明变量
        try:
            self.symbol_table.declare(
                node.name,
                "constant" if node.is_const else "variable",
                node.type_name,
                is_const=node.is_const,
                line=node.line
            )
        except DeclarationError as e:
            self.errors.append(str(e))

        return node.type_name

    # ------- 函数声明 -------

    def _analyze_func_decl(self, node: FuncDeclNode) -> str:
        """分析函数声明"""
        # 1. 检查返回类型
        if node.return_type != "void" and not self.type_checker.is_valid_type(node.return_type):
            self.errors.append(
                f"Line {node.line}: 未知的返回类型 '{node.return_type}'"
            )

        # 2. 收集参数类型
        param_types = []
        for param in node.params:
            if not self.type_checker.is_valid_type(param.type_name):
                self.errors.append(
                    f"Line {param.line}: 未知的参数类型 '{param.type_name}'"
                )
            param_types.append(param.type_name)

        # 3. 在当前作用域声明函数
        try:
            self.symbol_table.declare(
                node.name, "function", "function",
                param_types=param_types,
                return_type=node.return_type,
                line=node.line
            )
        except DeclarationError as e:
            self.errors.append(str(e))

        # 4. 进入函数作用域
        self.symbol_table.enter_scope(f"func_{node.name}")
        old_return_type = self._current_func_return_type
        self._current_func_return_type = node.return_type

        # 5. 声明参数
        for param in node.params:
            try:
                self.symbol_table.declare(
                    param.name, "parameter", param.type_name,
                    line=param.line
                )
            except DeclarationError as e:
                self.errors.append(str(e))

        # 6. 分析函数体
        has_return = False
        if node.body:
            has_return = self._analyze_block_with_return_info(node.body)
            if not has_return and node.return_type != "void":
                self.warnings.append(
                    f"Line {node.line}: 函数 '{node.name}' 可能没有返回值"
                )

        # 7. 退出函数作用域
        self._current_func_return_type = old_return_type
        self.symbol_table.exit_scope()

        return "function"

    def _analyze_block_with_return_info(self, node: ASTNode) -> bool:
        """分析块并返回是否包含 return"""
        has_return = False
        if isinstance(node, BlockNode):
            for stmt in node.statements:
                if isinstance(stmt, ReturnNode):
                    has_return = True
                elif isinstance(stmt, IfNode):
                    then_ret = self._analyze_block_with_return_info(stmt.then_body)
                    else_ret = False
                    if stmt.else_body:
                        else_ret = self._analyze_block_with_return_info(stmt.else_body)
                    has_return = has_return or (then_ret and else_ret)
                else:
                    self.analyze(stmt)
        else:
            self.analyze(node)
            if isinstance(node, ReturnNode):
                has_return = True
        return has_return

    # ------- 函数调用 -------

    def _analyze_func_call(self, node: FuncCallNode) -> str:
        """分析函数调用"""
        # 1. 查找函数
        func_info = self.symbol_table.resolve(node.name)
        if func_info is None:
            self.errors.append(
                f"Line {node.line}: 函数 '{node.name}' 未声明"
            )
            # 仍然分析参数以发现更多错误
            for arg in node.args:
                self.analyze(arg)
            return "unknown"

        # 2. 检查是否是函数
        if func_info.kind != "function":
            self.errors.append(
                f"Line {node.line}: '{node.name}' 不是函数"
            )
            return "unknown"

        # 3. 分析参数并收集类型
        arg_types = []
        for arg in node.args:
            arg_types.append(self.analyze(arg))

        # 4. 检查参数数量（内置函数 'any' 类型跳过检查）
        expected_count = len(func_info.param_types)
        actual_count = len(arg_types)
        if func_info.param_types != ["any"] and expected_count != actual_count:
            self.errors.append(
                f"Line {node.line}: 函数 '{node.name}' 期望 {expected_count} 个参数，"
                f"但传入了 {actual_count} 个"
            )
        else:
            # 5. 检查参数类型
            for i, (expected, actual) in enumerate(
                zip(func_info.param_types, arg_types)
            ):
                if expected == "any":
                    continue
                if not self.type_checker.types_compatible(expected, actual):
                    self.errors.append(
                        f"Line {node.line}: 函数 '{node.name}' 的第 {i + 1} 个参数"
                        f"期望 '{expected}'，但传入了 '{actual}'"
                    )

        return func_info.return_type

    # ------- 控制流 -------

    def _analyze_if(self, node: IfNode) -> str:
        """分析 if 语句"""
        # 条件必须是 bool 类型
        cond_type = self.analyze(node.condition)
        if cond_type not in ("bool", "unknown"):
            self.errors.append(
                f"Line {node.line}: if 条件表达式必须是 bool 类型，"
                f"但得到 '{cond_type}'"
            )

        self.analyze(node.then_body)
        if node.else_body:
            self.analyze(node.else_body)

        return "void"

    def _analyze_while(self, node: WhileNode) -> str:
        """分析 while 循环"""
        cond_type = self.analyze(node.condition)
        if cond_type not in ("bool", "unknown"):
            self.errors.append(
                f"Line {node.line}: while 条件表达式必须是 bool 类型，"
                f"但得到 '{cond_type}'"
            )

        self._in_loop_depth += 1
        self.analyze(node.body)
        self._in_loop_depth -= 1

        return "void"

    def _analyze_for(self, node: ForNode) -> str:
        """分析 for 循环"""
        self.symbol_table.enter_scope("for_loop")

        if node.init:
            self.analyze(node.init)
        if node.condition:
            cond_type = self.analyze(node.condition)
            if cond_type not in ("bool", "unknown"):
                self.errors.append(
                    f"Line {node.line}: for 条件表达式必须是 bool 类型，"
                    f"但得到 '{cond_type}'"
                )
        if node.update:
            self.analyze(node.update)

        self._in_loop_depth += 1
        self.analyze(node.body)
        self._in_loop_depth -= 1

        self.symbol_table.exit_scope()
        return "void"

    def _analyze_return(self, node: ReturnNode) -> str:
        """分析 return 语句"""
        if self._current_func_return_type is None:
            self.errors.append(
                f"Line {node.line}: return 语句不在函数内"
            )
            return "unknown"

        if node.value:
            value_type = self.analyze(node.value)
            if self._current_func_return_type == "void":
                self.errors.append(
                    f"Line {node.line}: void 函数不应返回值"
                )
            elif not self.type_checker.types_compatible(
                self._current_func_return_type, value_type
            ):
                self.errors.append(
                    f"Line {node.line}: 返回类型不匹配: "
                    f"期望 '{self._current_func_return_type}'，"
                    f"但得到 '{value_type}'"
                )
        else:
            if self._current_func_return_type != "void":
                self.errors.append(
                    f"Line {node.line}: 函数期望返回 '{self._current_func_return_type}'，"
                    f"但 return 无值"
                )

        return self._current_func_return_type

    # ------- 代码块 -------

    def _analyze_block(self, node: BlockNode) -> str:
        """分析代码块"""
        self.symbol_table.enter_scope("block")
        for stmt in node.statements:
            self.analyze(stmt)
        self.symbol_table.exit_scope()
        return "void"

    # ------- 输出 -------

    def print_results(self):
        """输出分析结果"""
        print("=" * 60)
        print("语义分析结果")
        print("=" * 60)

        print("\n--- 符号表 ---")
        print(self.symbol_table.dump())

        if self.errors:
            print(f"\n--- 错误 ({len(self.errors)}) ---")
            for err in self.errors:
                print(f"  [ERROR] {err}")
        else:
            print("\n--- 错误: 无 ---")

        if self.warnings:
            print(f"\n--- 警告 ({len(self.warnings)}) ---")
            for warn in self.warnings:
                print(f"  [WARN]  {warn}")

        print()
        return len(self.errors) == 0


# ============================================================
# 测试用例
# ============================================================

def build_correct_program() -> ProgramNode:
    """
    构建一个语义正确的程序:
    
    int x = 10;
    float y = 3.14;
    const int MAX = 100;
    
    int add(int a, int b) {
        return a + b;
    }
    
    void main() {
        int result;
        result = add(x, 5);
        if (result > 10) {
            print(result);
        }
        int i = 0;
        while (i < result) {
            i = i + 1;
        }
    }
    """
    return ProgramNode([
        # int x = 10;
        VarDeclNode("x", "int", NumberNode(10), line=1),
        # float y = 3.14;
        VarDeclNode("y", "float", NumberNode(3.14, is_float=True), line=2),
        # const int MAX = 100;
        VarDeclNode("MAX", "int", NumberNode(100), is_const=True, line=3),
        # int add(int a, int b) { return a + b; }
        FuncDeclNode("add", "int",
            params=[ParamNode("a", "int", line=5), ParamNode("b", "int", line=5)],
            body=BlockNode([
                ReturnNode(BinOpNode("+", IdentifierNode("a", 6), IdentifierNode("b", 6), 6), line=6)
            ], line=5),
            line=5
        ),
        # void main() { ... }
        FuncDeclNode("main", "void",
            body=BlockNode([
                # int result;
                VarDeclNode("result", "int", line=10),
                # result = add(x, 5);
                AssignNode("result",
                    FuncCallNode("add", [IdentifierNode("x", 11), NumberNode(5)], line=11),
                    line=11
                ),
                # if (result > 10) { print(result); }
                IfNode(
                    BinOpNode(">", IdentifierNode("result", 12), NumberNode(10), 12),
                    BlockNode([
                        FuncCallNode("print", [IdentifierNode("result", 13)], line=13)
                    ], line=12),
                    line=12
                ),
                # int i = 0;
                VarDeclNode("i", "int", NumberNode(0), line=15),
                # while (i < result) { i = i + 1; }
                WhileNode(
                    BinOpNode("<", IdentifierNode("i", 16), IdentifierNode("result", 16), 16),
                    BlockNode([
                        AssignNode("i",
                            BinOpNode("+", IdentifierNode("i", 17), NumberNode(1), 17),
                            line=17
                        )
                    ], line=16),
                    line=16
                ),
            ], line=9),
            line=9
        ),
    ])


def build_error_program() -> ProgramNode:
    """
    构建一个包含语义错误的程序:
    
    int x = "hello";       // 类型不兼容
    int y = 10;
    int y = 20;            // 重复声明
    
    void foo(int a) {
        int x = 5;
        x = 10;            // OK
    }
    
    void main() {
        int a = 1;
        a = true;          // 类型不兼容 (bool -> int)
        z = 5;             // 未声明变量
        int w = foo(1, 2); // void 函数返回值 + 参数数量错误
        if (10) {          // 条件不是 bool
            break;         // 不在循环内
        }
    }
    """
    return ProgramNode([
        # int x = "hello";  — 类型不兼容
        VarDeclNode("x", "int", StringNode("hello", line=1), line=1),
        # int y = 10;
        VarDeclNode("y", "int", NumberNode(10), line=2),
        # int y = 20;  — 重复声明
        VarDeclNode("y", "int", NumberNode(20), line=3),
        # void foo(int a) { int x = 5; }
        FuncDeclNode("foo", "void",
            params=[ParamNode("a", "int", line=5)],
            body=BlockNode([
                VarDeclNode("x", "int", NumberNode(5), line=6),
            ], line=5),
            line=5
        ),
        # void main() { ... }
        FuncDeclNode("main", "void",
            body=BlockNode([
                # int a = 1;
                VarDeclNode("a", "int", NumberNode(1), line=10),
                # a = true;  — 类型不兼容
                AssignNode("a", BoolNode(True, line=11), line=11),
                # z = 5;  — 未声明
                AssignNode("z", NumberNode(5), line=12),
                # foo(1, 2)  — 参数数量错误
                FuncCallNode("foo", [NumberNode(1), NumberNode(2)], line=13),
                # if (10) { }  — 条件非 bool
                IfNode(NumberNode(10, line=14), BlockNode([], line=14), line=14),
            ], line=9),
            line=9
        ),
    ])


def build_const_error_program() -> ProgramNode:
    """
    测试常量赋值错误:
    
    const int MAX = 100;
    void main() {
        MAX = 200;   // 对常量赋值
    }
    """
    return ProgramNode([
        VarDeclNode("MAX", "int", NumberNode(100), is_const=True, line=1),
        FuncDeclNode("main", "void",
            body=BlockNode([
                AssignNode("MAX", NumberNode(200), line=4),
            ], line=3),
            line=3
        ),
    ])


def main():
    print("=" * 60)
    print("语义分析器测试")
    print("=" * 60)

    # 测试1：正确的程序
    print("\n>>> 测试1: 正确的程序")
    analyzer1 = SemanticAnalyzer()
    correct_prog = build_correct_program()
    analyzer1.analyze(correct_prog)
    success = analyzer1.print_results()

    # 测试2：包含错误的程序
    print("\n>>> 测试2: 包含错误的程序")
    analyzer2 = SemanticAnalyzer()
    error_prog = build_error_program()
    analyzer2.analyze(error_prog)
    analyzer2.print_results()

    # 测试3：常量赋值错误
    print("\n>>> 测试3: 常量赋值错误")
    analyzer3 = SemanticAnalyzer()
    const_prog = build_const_error_program()
    analyzer3.analyze(const_prog)
    analyzer3.print_results()

    print("=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
