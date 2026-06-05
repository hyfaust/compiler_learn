"""
三地址码 IR 生成器
==================
本模块将 AST 翻译为三地址码（Three-Address Code）中间表示。
包括：
- 自包含的 AST 节点定义
- ThreeAddressCode 指令类
- IRGenerator 主类（临时变量管理、标签管理、表达式/语句翻译）
- 支持：赋值、算术运算、条件分支、循环、函数调用、短路求值

运行方式: python ir_generator.py
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Tuple
from enum import Enum, auto


# ============================================================
# AST 节点定义（自包含）
# ============================================================

class ASTNodeType(Enum):
    """AST 节点类型"""
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


class NumberNode(ASTNode):
    def __init__(self, value: float, is_float: bool = False, line: int = 0):
        super().__init__(ASTNodeType.NUMBER, line)
        self.value = value
        self.is_float = is_float


class StringNode(ASTNode):
    def __init__(self, value: str = "", line: int = 0):
        super().__init__(ASTNodeType.STRING, line)
        self.value = value


class BoolNode(ASTNode):
    def __init__(self, value: bool = False, line: int = 0):
        super().__init__(ASTNodeType.BOOL, line)
        self.value = value


class IdentifierNode(ASTNode):
    def __init__(self, name: str = "", line: int = 0):
        super().__init__(ASTNodeType.IDENTIFIER, line)
        self.name = name


class BinOpNode(ASTNode):
    def __init__(self, op: str = "", left: ASTNode = None, right: ASTNode = None, line: int = 0):
        super().__init__(ASTNodeType.BINOP, line)
        self.op = op
        self.left = left
        self.right = right


class UnaryOpNode(ASTNode):
    def __init__(self, op: str = "", operand: ASTNode = None, line: int = 0):
        super().__init__(ASTNodeType.UNARYOP, line)
        self.op = op
        self.operand = operand


class AssignNode(ASTNode):
    def __init__(self, target: str = "", value: ASTNode = None, line: int = 0):
        super().__init__(ASTNodeType.ASSIGN, line)
        self.target = target
        self.value = value


class ParamNode(ASTNode):
    def __init__(self, name: str = "", type_name: str = "", line: int = 0):
        super().__init__(ASTNodeType.PARAM, line)
        self.name = name
        self.type_name = type_name


class VarDeclNode(ASTNode):
    def __init__(self, name: str = "", type_name: str = "",
                 init_value: ASTNode = None, is_const: bool = False, line: int = 0):
        super().__init__(ASTNodeType.VAR_DECL, line)
        self.name = name
        self.type_name = type_name
        self.init_value = init_value
        self.is_const = is_const


class FuncDeclNode(ASTNode):
    def __init__(self, name: str = "", return_type: str = "",
                 params: list = None, body: ASTNode = None, line: int = 0):
        super().__init__(ASTNodeType.FUNC_DECL, line)
        self.name = name
        self.return_type = return_type
        self.params = params or []
        self.body = body


class FuncCallNode(ASTNode):
    def __init__(self, name: str = "", args: list = None, line: int = 0):
        super().__init__(ASTNodeType.FUNC_CALL, line)
        self.name = name
        self.args = args or []


class IfNode(ASTNode):
    def __init__(self, condition: ASTNode = None, then_body: ASTNode = None,
                 else_body: ASTNode = None, line: int = 0):
        super().__init__(ASTNodeType.IF, line)
        self.condition = condition
        self.then_body = then_body
        self.else_body = else_body


class WhileNode(ASTNode):
    def __init__(self, condition: ASTNode = None, body: ASTNode = None, line: int = 0):
        super().__init__(ASTNodeType.WHILE, line)
        self.condition = condition
        self.body = body


class ForNode(ASTNode):
    def __init__(self, init: ASTNode = None, condition: ASTNode = None,
                 update: ASTNode = None, body: ASTNode = None, line: int = 0):
        super().__init__(ASTNodeType.FOR, line)
        self.init = init
        self.condition = condition
        self.update = update
        self.body = body


class ReturnNode(ASTNode):
    def __init__(self, value: ASTNode = None, line: int = 0):
        super().__init__(ASTNodeType.RETURN, line)
        self.value = value


class BlockNode(ASTNode):
    def __init__(self, statements: list = None, line: int = 0):
        super().__init__(ASTNodeType.BLOCK, line)
        self.statements = statements or []


class ProgramNode(ASTNode):
    def __init__(self, declarations: list = None, line: int = 0):
        super().__init__(ASTNodeType.PROGRAM, line)
        self.declarations = declarations or []


# ============================================================
# 三地址码指令
# ============================================================

class ThreeAddressCode:
    """
    三地址码指令
    
    支持的指令格式：
    - result = arg1 op arg2     （二元运算）
    - result = op arg1          （一元运算）
    - result = arg1             （赋值/复制）
    - label L                   （标签）
    - goto L                    （无条件跳转）
    - if arg1 goto L            （条件跳转真）
    - ifFalse arg1 goto L       （条件跳转假）
    - param arg1                （函数参数）
    - call func_name, n         （函数调用，n 为参数数量）
    - result = call func_name, n（带返回值的函数调用）
    - return arg1               （返回值）
    - return                    （无返回值返回）
    """

    def __init__(self, op: str, result: Optional[str] = None,
                 arg1: Optional[str] = None, arg2: Optional[str] = None):
        self.op = op
        self.result = result
        self.arg1 = arg1
        self.arg2 = arg2

    def __str__(self) -> str:
        """格式化输出三地址码"""
        if self.op == "label":
            return f"{self.result}:"
        elif self.op == "goto":
            return f"  goto {self.result}"
        elif self.op == "if":
            return f"  if {self.arg1} goto {self.result}"
        elif self.op == "ifFalse":
            return f"  ifFalse {self.arg1} goto {self.result}"
        elif self.op == "param":
            return f"  param {self.arg1}"
        elif self.op == "call":
            if self.result:
                return f"  {self.result} = call {self.arg1}, {self.arg2}"
            else:
                return f"  call {self.arg1}, {self.arg2}"
        elif self.op == "return":
            if self.arg1:
                return f"  return {self.arg1}"
            else:
                return f"  return"
        elif self.op == "=":
            return f"  {self.result} = {self.arg1}"
        elif self.arg2 is not None:
            return f"  {self.result} = {self.arg1} {self.op} {self.arg2}"
        elif self.arg1 is not None:
            return f"  {self.result} = {self.op} {self.arg1}"
        else:
            return f"  {self.op}"

    def __repr__(self) -> str:
        return f"TAC({self.op}, {self.result}, {self.arg1}, {self.arg2})"


# ============================================================
# IR 生成器
# ============================================================

class IRGenerator:
    """
    三地址码 IR 生成器
    
    将 AST 递归翻译为三地址码序列。
    
    核心策略：
    - 表达式翻译：递归翻译子表达式，返回结果所在的"地址"（变量名或临时变量）
    - 语句翻译：生成控制流指令（跳转、标签等）
    - 短路求值：&& 和 || 使用条件跳转而非普通二元运算
    """

    def __init__(self):
        self.instructions: List[ThreeAddressCode] = []
        self._temp_count = 0
        self._label_count = 0

    def new_temp(self) -> str:
        """生成新的临时变量名"""
        self._temp_count += 1
        return f"t{self._temp_count}"

    def new_label(self) -> str:
        """生成新的标签名"""
        self._label_count += 1
        return f"L{self._label_count}"

    def emit(self, op: str, result: str = None, arg1: str = None, arg2: str = None):
        """发射一条三地址码指令"""
        self.instructions.append(ThreeAddressCode(op, result, arg1, arg2))

    # ============================================================
    # 表达式翻译
    # ============================================================

    def translate_expr(self, node: ASTNode) -> str:
        """
        翻译表达式节点。
        返回该表达式结果所在的地址（变量名或临时变量名）。
        """
        if node.node_type == ASTNodeType.NUMBER:
            return self._translate_number(node)
        elif node.node_type == ASTNodeType.STRING:
            return self._translate_string(node)
        elif node.node_type == ASTNodeType.BOOL:
            return self._translate_bool(node)
        elif node.node_type == ASTNodeType.IDENTIFIER:
            return self._translate_identifier(node)
        elif node.node_type == ASTNodeType.BINOP:
            return self._translate_binop(node)
        elif node.node_type == ASTNodeType.UNARYOP:
            return self._translate_unaryop(node)
        elif node.node_type == ASTNodeType.FUNC_CALL:
            return self._translate_func_call_expr(node)
        else:
            raise ValueError(f"无法翻译表达式节点: {node.node_type}")

    def _translate_number(self, node: NumberNode) -> str:
        """数字字面量直接返回值的字符串表示"""
        if node.is_float:
            return str(node.value)
        return str(int(node.value))

    def _translate_string(self, node: StringNode) -> str:
        """字符串字面量"""
        return f'"{node.value}"'

    def _translate_bool(self, node: BoolNode) -> str:
        """布尔字面量"""
        return "true" if node.value else "false"

    def _translate_identifier(self, node: IdentifierNode) -> str:
        """标识符引用，直接返回变量名"""
        return node.name

    def _translate_binop(self, node: BinOpNode) -> str:
        """
        翻译二元运算。
        
        对于逻辑运算 && 和 || 使用短路求值，
        其他运算生成标准的三地址码指令。
        """
        # 逻辑运算使用短路求值
        if node.op == "&&":
            return self._translate_short_circuit_and(node)
        elif node.op == "||":
            return self._translate_short_circuit_or(node)

        # 普通二元运算
        left_addr = self.translate_expr(node.left)
        right_addr = self.translate_expr(node.right)
        temp = self.new_temp()
        self.emit(node.op, temp, left_addr, right_addr)
        return temp

    def _translate_short_circuit_and(self, node: BinOpNode) -> str:
        """
        短路求值 &&
        
        a && b 等价于：
            ifFalse a goto L_false
            ifFalse b goto L_false
            result = true
            goto L_end
        L_false:
            result = false
        L_end:
        """
        result = self.new_temp()
        false_label = self.new_label()
        end_label = self.new_label()

        left_addr = self.translate_expr(node.left)
        self.emit("ifFalse", false_label, left_addr)

        right_addr = self.translate_expr(node.right)
        self.emit("ifFalse", false_label, right_addr)

        self.emit("=", result, "true")
        self.emit("goto", end_label)
        self.emit("label", false_label)
        self.emit("=", result, "false")
        self.emit("label", end_label)

        return result

    def _translate_short_circuit_or(self, node: BinOpNode) -> str:
        """
        短路求值 ||
        
        a || b 等价于：
            if a goto L_true
            if b goto L_true
            result = false
            goto L_end
        L_true:
            result = true
        L_end:
        """
        result = self.new_temp()
        true_label = self.new_label()
        end_label = self.new_label()

        left_addr = self.translate_expr(node.left)
        self.emit("if", true_label, left_addr)

        right_addr = self.translate_expr(node.right)
        self.emit("if", true_label, right_addr)

        self.emit("=", result, "false")
        self.emit("goto", end_label)
        self.emit("label", true_label)
        self.emit("=", result, "true")
        self.emit("label", end_label)

        return result

    def _translate_unaryop(self, node: UnaryOpNode) -> str:
        """翻译一元运算"""
        operand_addr = self.translate_expr(node.operand)
        temp = self.new_temp()
        self.emit(node.op, temp, operand_addr)
        return temp

    def _translate_func_call_expr(self, node: FuncCallNode) -> str:
        """翻译函数调用表达式（返回结果）"""
        # 先翻译所有参数
        arg_addrs = []
        for arg in node.args:
            arg_addrs.append(self.translate_expr(arg))

        # 发射参数指令
        for addr in arg_addrs:
            self.emit("param", arg1=addr)

        # 发射调用指令
        temp = self.new_temp()
        self.emit("call", temp, node.name, str(len(node.args)))
        return temp

    # ============================================================
    # 语句翻译
    # ============================================================

    def translate_stmt(self, node: ASTNode):
        """翻译语句节点"""
        if node.node_type == ASTNodeType.PROGRAM:
            self._translate_program(node)
        elif node.node_type == ASTNodeType.VAR_DECL:
            self._translate_var_decl(node)
        elif node.node_type == ASTNodeType.ASSIGN:
            self._translate_assign(node)
        elif node.node_type == ASTNodeType.IF:
            self._translate_if(node)
        elif node.node_type == ASTNodeType.WHILE:
            self._translate_while(node)
        elif node.node_type == ASTNodeType.FOR:
            self._translate_for(node)
        elif node.node_type == ASTNodeType.RETURN:
            self._translate_return(node)
        elif node.node_type == ASTNodeType.BLOCK:
            self._translate_block(node)
        elif node.node_type == ASTNodeType.FUNC_DECL:
            self._translate_func_decl(node)
        elif node.node_type == ASTNodeType.FUNC_CALL:
            self._translate_func_call_stmt(node)
        else:
            raise ValueError(f"无法翻译语句节点: {node.node_type}")

    def _translate_program(self, node: ProgramNode):
        """翻译程序根节点"""
        for decl in node.declarations:
            self.translate_stmt(decl)

    def _translate_var_decl(self, node: VarDeclNode):
        """翻译变量声明"""
        if node.init_value is not None:
            value_addr = self.translate_expr(node.init_value)
            self.emit("=", node.name, value_addr)

    def _translate_assign(self, node: AssignNode):
        """翻译赋值语句"""
        value_addr = self.translate_expr(node.value)
        self.emit("=", node.target, value_addr)

    def _translate_if(self, node: IfNode):
        """
        翻译 if 语句
        
        if (cond) { then_body } else { else_body }
        
        生成：
          ifFalse cond goto L_else
          ... then_body ...
          goto L_end
        L_else:
          ... else_body ...
        L_end:
        """
        else_label = self.new_label()
        end_label = self.new_label()

        # 条件表达式
        cond_addr = self.translate_expr(node.condition)
        self.emit("ifFalse", else_label, cond_addr)

        # then 分支
        self.translate_stmt(node.then_body)

        if node.else_body:
            self.emit("goto", end_label)
            self.emit("label", else_label)
            self.translate_stmt(node.else_body)
            self.emit("label", end_label)
        else:
            self.emit("label", else_label)

    def _translate_while(self, node: WhileNode):
        """
        翻译 while 循环
        
        while (cond) { body }
        
        生成：
        L_loop:
          ifFalse cond goto L_end
          ... body ...
          goto L_loop
        L_end:
        """
        loop_label = self.new_label()
        end_label = self.new_label()

        self.emit("label", loop_label)
        cond_addr = self.translate_expr(node.condition)
        self.emit("ifFalse", end_label, cond_addr)
        self.translate_stmt(node.body)
        self.emit("goto", loop_label)
        self.emit("label", end_label)

    def _translate_for(self, node: ForNode):
        """
        翻译 for 循环
        
        for (init; cond; update) { body }
        
        生成：
          ... init ...
        L_loop:
          ifFalse cond goto L_end
          ... body ...
          ... update ...
          goto L_loop
        L_end:
        """
        loop_label = self.new_label()
        end_label = self.new_label()

        # 初始化
        if node.init:
            self.translate_stmt(node.init)

        # 循环头
        self.emit("label", loop_label)

        # 条件
        if node.condition:
            cond_addr = self.translate_expr(node.condition)
            self.emit("ifFalse", end_label, cond_addr)

        # 循环体
        self.translate_stmt(node.body)

        # 更新
        if node.update:
            self.translate_stmt(node.update)

        self.emit("goto", loop_label)
        self.emit("label", end_label)

    def _translate_return(self, node: ReturnNode):
        """翻译 return 语句"""
        if node.value:
            value_addr = self.translate_expr(node.value)
            self.emit("return", arg1=value_addr)
        else:
            self.emit("return")

    def _translate_block(self, node: BlockNode):
        """翻译代码块"""
        for stmt in node.statements:
            self.translate_stmt(stmt)

    def _translate_func_decl(self, node: FuncDeclNode):
        """
        翻译函数声明
        
        生成：
        func_begin func_name:
          param p1
          param p2
          ... body ...
          return
        func_end func_name:
        """
        self.emit("label", f"func_begin {node.name}")
        # 声明参数
        for param in node.params:
            self.emit("param", arg1=f"decl:{param.name}:{param.type_name}")
        # 翻译函数体
        if node.body:
            self.translate_stmt(node.body)
        # 确保函数末尾有隐式 return
        self.emit("label", f"func_end {node.name}")

    def _translate_func_call_stmt(self, node: FuncCallNode):
        """翻译函数调用语句（不使用返回值）"""
        arg_addrs = []
        for arg in node.args:
            arg_addrs.append(self.translate_expr(arg))
        for addr in arg_addrs:
            self.emit("param", arg1=addr)
        self.emit("call", arg1=node.name, arg2=str(len(node.args)))

    # ============================================================
    # 输出
    # ============================================================

    def get_output(self) -> str:
        """将所有指令格式化为文本"""
        lines = []
        for instr in self.instructions:
            lines.append(str(instr))
        return "\n".join(lines)

    def print_ir(self, title: str = ""):
        """打印生成的 IR"""
        if title:
            print(f"\n{'=' * 50}")
            print(f"  {title}")
            print(f"{'=' * 50}")
        for i, instr in enumerate(self.instructions):
            print(f"  [{i:3d}] {instr}")
        print()


# ============================================================
# 测试用例
# ============================================================

def build_test_program_1() -> ProgramNode:
    """
    测试程序1：基本运算和控制流
    
    void main() {
        int a = 10;
        int b = 20;
        int c;
        c = a + b * 3;
        if (c > 50) {
            c = c - 10;
        } else {
            c = c + 10;
        }
        int i = 0;
        int sum = 0;
        while (i < c) {
            sum = sum + i;
            i = i + 1;
        }
    }
    """
    return ProgramNode([
        FuncDeclNode("main", "void",
            body=BlockNode([
                # int a = 10;
                VarDeclNode("a", "int", NumberNode(10), line=2),
                # int b = 20;
                VarDeclNode("b", "int", NumberNode(20), line=3),
                # int c;
                VarDeclNode("c", "int", line=4),
                # c = a + b * 3;
                AssignNode("c",
                    BinOpNode("+",
                        IdentifierNode("a", 5),
                        BinOpNode("*",
                            IdentifierNode("b", 5),
                            NumberNode(3), 5
                        ), 5
                    ), line=5
                ),
                # if (c > 50) { c = c - 10; } else { c = c + 10; }
                IfNode(
                    BinOpNode(">", IdentifierNode("c", 6), NumberNode(50), 6),
                    BlockNode([
                        AssignNode("c",
                            BinOpNode("-", IdentifierNode("c", 7), NumberNode(10), 7),
                            line=7
                        )
                    ], line=6),
                    BlockNode([
                        AssignNode("c",
                            BinOpNode("+", IdentifierNode("c", 9), NumberNode(10), 9),
                            line=9
                        )
                    ], line=6),
                    line=6
                ),
                # int i = 0;
                VarDeclNode("i", "int", NumberNode(0), line=11),
                # int sum = 0;
                VarDeclNode("sum", "int", NumberNode(0), line=12),
                # while (i < c) { sum = sum + i; i = i + 1; }
                WhileNode(
                    BinOpNode("<", IdentifierNode("i", 13), IdentifierNode("c", 13), 13),
                    BlockNode([
                        AssignNode("sum",
                            BinOpNode("+", IdentifierNode("sum", 14), IdentifierNode("i", 14), 14),
                            line=14
                        ),
                        AssignNode("i",
                            BinOpNode("+", IdentifierNode("i", 15), NumberNode(1), 15),
                            line=15
                        )
                    ], line=13),
                    line=13
                ),
            ], line=1),
            line=1
        )
    ])


def build_test_program_2() -> ProgramNode:
    """
    测试程序2：函数调用和嵌套控制流
    
    int add(int a, int b) {
        return a + b;
    }
    
    void main() {
        int x = add(3, 4);
        int y = 0;
        for (int i = 0; i < 10; i = i + 1) {
            if (i % 2 == 0) {
                y = y + i;
            }
        }
        bool flag = (x > 5) && (y > 10);
    }
    """
    return ProgramNode([
        # int add(int a, int b) { return a + b; }
        FuncDeclNode("add", "int",
            params=[ParamNode("a", "int", line=1), ParamNode("b", "int", line=1)],
            body=BlockNode([
                ReturnNode(
                    BinOpNode("+", IdentifierNode("a", 2), IdentifierNode("b", 2), 2),
                    line=2
                )
            ], line=1),
            line=1
        ),
        # void main() { ... }
        FuncDeclNode("main", "void",
            body=BlockNode([
                # int x = add(3, 4);
                VarDeclNode("x", "int",
                    FuncCallNode("add", [NumberNode(3), NumberNode(4)], line=6),
                    line=6
                ),
                # int y = 0;
                VarDeclNode("y", "int", NumberNode(0), line=7),
                # for (int i = 0; i < 10; i = i + 1) {
                #     if (i % 2 == 0) { y = y + i; }
                # }
                ForNode(
                    init=VarDeclNode("i", "int", NumberNode(0), line=8),
                    condition=BinOpNode("<", IdentifierNode("i", 8), NumberNode(10), 8),
                    update=AssignNode("i",
                        BinOpNode("+", IdentifierNode("i", 8), NumberNode(1), 8), line=8
                    ),
                    body=BlockNode([
                        IfNode(
                            BinOpNode("==",
                                BinOpNode("%", IdentifierNode("i", 9), NumberNode(2), 9),
                                NumberNode(0), 9
                            ),
                            BlockNode([
                                AssignNode("y",
                                    BinOpNode("+", IdentifierNode("y", 10), IdentifierNode("i", 10), 10),
                                    line=10
                                )
                            ], line=9),
                            line=9
                        )
                    ], line=8),
                    line=8
                ),
                # bool flag = (x > 5) && (y > 10);
                VarDeclNode("flag", "bool",
                    BinOpNode("&&",
                        BinOpNode(">", IdentifierNode("x", 12), NumberNode(5), 12),
                        BinOpNode(">", IdentifierNode("y", 12), NumberNode(10), 12),
                        line=12
                    ),
                    line=12
                ),
            ], line=5),
            line=5
        ),
    ])


def main():
    print("=" * 60)
    print("三地址码 IR 生成器测试")
    print("=" * 60)

    # 测试1：基本运算和控制流
    print("\n>>> 测试1: 基本运算和控制流")
    print("源代码概述:")
    print("  int a=10; int b=20; c=a+b*3;")
    print("  if(c>50) c-=10; else c+=10;")
    print("  while(i<c) { sum+=i; i++; }")
    print()

    gen1 = IRGenerator()
    prog1 = build_test_program_1()
    gen1.translate_stmt(prog1)
    gen1.print_ir("测试1 三地址码输出")

    # 测试2：函数调用和嵌套控制流
    print("\n>>> 测试2: 函数调用、for循环、短路求值")
    print("源代码概述:")
    print("  int add(int a, int b) { return a+b; }")
    print("  x = add(3,4);")
    print("  for(i=0;i<10;i++) if(i%2==0) y+=i;")
    print("  flag = (x>5) && (y>10);")
    print()

    gen2 = IRGenerator()
    prog2 = build_test_program_2()
    gen2.translate_stmt(prog2)
    gen2.print_ir("测试2 三地址码输出")

    print("=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
