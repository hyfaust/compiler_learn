"""
字节码指令集定义

定义了 TinyLang 虚拟机使用的操作码（Opcode）、
字节码块（Chunk）以及编译后的函数对象（CompiledFunction）。

字节码设计原则：
- 栈式架构：大多数操作从栈上取操作数，结果也压入栈
- 每条指令由一个操作码字节和零个或多个操作数字节组成
- 常量通过常量池索引引用
- 变量通过常量池中的变量名字符串引用
"""

from enum import IntEnum


# ============================================================
#  操作码定义
# ============================================================

class Opcode(IntEnum):
    """TinyLang 虚拟机的字节码操作码

    每个操作码后面可能跟着操作数。操作数的个数和含义
    由具体的操作码决定。
    """

    # ---- 常量和字面量 ----
    LOAD_CONST = 1       # 加载常量        操作数: 常量池索引
    LOAD_TRUE = 2        # 压入 true
    LOAD_FALSE = 3       # 压入 false
    LOAD_NONE = 4        # 压入 none (空值)
    POP = 5              # 弹出并丢弃栈顶值
    DUP = 6              # 复制栈顶值

    # ---- 变量操作 ----
    LOAD_VAR = 10        # 加载变量值      操作数: 常量池中变量名的索引
    STORE_VAR = 11       # 存储变量值      操作数: 常量池中变量名的索引

    # ---- 算术运算 ----
    ADD = 20             # 加法: a + b
    SUB = 21             # 减法: a - b
    MUL = 22             # 乘法: a * b
    DIV = 23             # 除法: a / b
    MOD = 24             # 取模: a % b
    NEGATE = 25          # 取负: -a

    # ---- 比较运算 ----
    CMP_EQ = 30          # 等于: a == b
    CMP_NEQ = 31         # 不等于: a != b
    CMP_LT = 32          # 小于: a < b
    CMP_GT = 33          # 大于: a > b
    CMP_LTE = 34         # 小于等于: a <= b
    CMP_GTE = 35         # 大于等于: a >= b

    # ---- 逻辑运算 ----
    AND = 40             # 逻辑与 (短路求值由编译器通过跳转实现)
    OR = 41              # 逻辑或 (短路求值由编译器通过跳转实现)
    NOT = 42             # 逻辑非: not a

    # ---- 控制流 ----
    JUMP = 50            # 无条件跳转      操作数: 目标地址
    JUMP_IF_FALSE = 51   # 弹出栈顶，为假则跳转   操作数: 目标地址
    JUMP_IF_TRUE = 52    # 弹出栈顶，为真则跳转   操作数: 目标地址

    # ---- 函数调用 ----
    CALL = 60            # 调用函数        操作数: 参数个数
    RETURN = 61          # 从函数返回（栈顶为返回值）

    # ---- 数组操作 ----
    BUILD_ARRAY = 70     # 构建数组        操作数: 元素个数
    GET_INDEX = 71       # 索引读取: arr[i]
    SET_INDEX = 72       # 索引写入: arr[i] = val
    GET_LEN = 73         # 获取长度: len(val)

    # ---- 特殊 ----
    HALT = 99            # 停止执行


# ============================================================
#  字节码块 (Chunk)
# ============================================================

class Chunk:
    """字节码块 —— 存储一组字节码指令及其关联的常量池

    每个编译单元（主程序或函数体）对应一个 Chunk。
    Chunk 包含：
    - code:       字节码指令序列（操作码和操作数交替存放）
    - constants:  常量池（存放字面量和变量名等）
    - line_info:  每个字节对应的源代码行号（用于错误报告）
    """

    def __init__(self):
        self.code: list[int] = []
        self.constants: list = []
        self.line_info: list[int] = []

    def emit(self, byte: int, line: int = 0):
        """写入一个字节（操作码或操作数）"""
        self.code.append(byte)
        self.line_info.append(line)

    def emit_op(self, opcode: int, operand: int = None, line: int = 0):
        """写入一条指令（可选操作数）

        Args:
            opcode:  操作码
            operand: 操作数（可选，部分指令不需要操作数）
            line:    源代码行号
        """
        self.emit(opcode, line)
        if operand is not None:
            self.emit(operand, line)

    def add_constant(self, value) -> int:
        """向常量池添加一个常量，返回其索引

        注意：不会去重，每次调用都会添加新条目。
        """
        self.constants.append(value)
        return len(self.constants) - 1

    def get_line(self, ip: int) -> int:
        """获取指定指令地址对应的源代码行号"""
        if 0 <= ip < len(self.line_info):
            return self.line_info[ip]
        return 0

    def __len__(self):
        return len(self.code)


# ============================================================
#  编译后的函数
# ============================================================

class CompiledFunction:
    """编译后的函数对象

    包含函数的基本信息和编译后的字节码。
    """

    def __init__(self, name: str, params: list[str], chunk: Chunk):
        self.name = name
        self.params = params
        self.arity = len(params)
        self.chunk = chunk

    def __repr__(self):
        return f"<CompiledFunction {self.name}/{self.arity}>"


# ============================================================
#  反汇编器
# ============================================================

def disassemble(chunk: Chunk) -> str:
    """反汇编字节码块，返回可读的文本表示

    输出格式示例：
        0000  LOAD_CONST  0  (42)
        0002  STORE_VAR   1  ('x')
        0004  HALT

    Args:
        chunk: 要反汇编的字节码块

    Returns:
        格式化的反汇编文本
    """
    lines = []
    i = 0
    code = chunk.code
    constants = chunk.constants

    while i < len(code):
        addr = i
        op = code[i]
        i += 1

        try:
            name = Opcode(op).name
        except ValueError:
            lines.append(f"{addr:04d}  UNKNOWN({op})")
            continue

        # 带有一个操作数的指令
        if op in (Opcode.LOAD_CONST, Opcode.LOAD_VAR, Opcode.STORE_VAR,
                  Opcode.BUILD_ARRAY, Opcode.CALL, Opcode.GET_LEN):
            if i < len(code):
                operand = code[i]
                i += 1
                # 尝试显示常量值
                if constants and 0 <= operand < len(constants):
                    const_val = constants[operand]
                    lines.append(f"{addr:04d}  {name:<14s} {operand}  ({const_val!r})")
                else:
                    lines.append(f"{addr:04d}  {name:<14s} {operand}")
            else:
                lines.append(f"{addr:04d}  {name:<14s} <missing operand>")

        # 跳转指令（操作数为目标地址）
        elif op in (Opcode.JUMP, Opcode.JUMP_IF_FALSE, Opcode.JUMP_IF_TRUE):
            if i < len(code):
                target = code[i]
                i += 1
                lines.append(f"{addr:04d}  {name:<14s} -> {target:04d}")
            else:
                lines.append(f"{addr:04d}  {name:<14s} <missing target>")

        # 无操作数的指令
        else:
            lines.append(f"{addr:04d}  {name}")

    return "\n".join(lines)
