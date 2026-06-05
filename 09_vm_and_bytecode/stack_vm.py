"""
栈式虚拟机实现
==============
一个完整的栈式虚拟机，包括：
- 完整的指令集
- 汇编器（文本汇编 → 字节码）
- 虚拟机执行引擎
- 栈帧管理
- 函数调用支持
- 常量池
- 错误处理
- 执行跟踪模式
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum, auto
import struct


class OpCode(Enum):
    """操作码定义"""
    # 常量指令
    ICONST = auto()     # 将整数常量压入栈
    DCONST = auto()     # 将双精度浮点数常量压入栈
    SCONST = auto()     # 将字符串常量压入栈
    LOAD_CONST = auto() # 从常量池加载常量
    
    # 算术指令
    IADD = auto()       # 整数加法
    ISUB = auto()       # 整数减法
    IMUL = auto()       # 整数乘法
    IDIV = auto()       # 整数除法
    IMOD = auto()       # 整数取模
    INEG = auto()       # 整数取负
    
    # 浮点算术指令
    DADD = auto()       # 双精度加法
    DSUB = auto()       # 双精度减法
    DMUL = auto()       # 双精度乘法
    DDIV = auto()       # 双精度除法
    
    # 比较指令
    ICMP_EQ = auto()    # 整数相等比较
    ICMP_NE = auto()    # 整数不等比较
    ICMP_LT = auto()    # 整数小于比较
    ICMP_GT = auto()    # 整数大于比较
    ICMP_LE = auto()    # 整数小于等于比较
    ICMP_GE = auto()    # 整数大于等于比较
    
    # 逻辑指令
    AND = auto()        # 逻辑与
    OR = auto()         # 逻辑或
    NOT = auto()        # 逻辑非
    
    # 跳转指令
    JMP = auto()        # 无条件跳转
    JMP_IF_FALSE = auto()  # 条件跳转（假）
    JMP_IF_TRUE = auto()   # 条件跳转（真）
    
    # 栈操作指令
    POP = auto()        # 弹出栈顶值
    DUP = auto()        # 复制栈顶值
    SWAP = auto()       # 交换栈顶两个值
    
    # 变量指令
    LOAD = auto()       # 加载局部变量
    STORE = auto()      # 存储局部变量
    LOAD_GLOBAL = auto()  # 加载全局变量
    STORE_GLOBAL = auto() # 存储全局变量
    
    # 函数指令
    CALL = auto()       # 调用函数
    RETURN = auto()     # 从函数返回
    
    # 输入输出指令
    PRINT = auto()      # 打印栈顶值
    INPUT = auto()      # 从输入读取值
    
    # 其他指令
    HALT = auto()       # 停止执行
    NOP = auto()        # 空操作


@dataclass
class Instruction:
    """指令"""
    opcode: OpCode
    operand: Any = None
    line: int = 0  # 源代码行号（用于调试）


class ConstantPool:
    """常量池"""
    
    def __init__(self):
        self.constants: List[Any] = []
        self.string_table: Dict[str, int] = {}
    
    def add_integer(self, value: int) -> int:
        """添加整数常量"""
        index = len(self.constants)
        self.constants.append(value)
        return index
    
    def add_float(self, value: float) -> int:
        """添加浮点数常量"""
        index = len(self.constants)
        self.constants.append(value)
        return index
    
    def add_string(self, value: str) -> int:
        """添加字符串常量"""
        if value in self.string_table:
            return self.string_table[value]
        index = len(self.constants)
        self.constants.append(value)
        self.string_table[value] = index
        return index
    
    def get(self, index: int) -> Any:
        """获取常量"""
        if 0 <= index < len(self.constants):
            return self.constants[index]
        raise IndexError(f"常量池索引越界: {index}")
    
    def __len__(self) -> int:
        return len(self.constants)


class StackFrame:
    """栈帧"""
    
    def __init__(self, function_name: str, return_address: int, 
                 num_locals: int, num_args: int):
        self.function_name = function_name
        self.return_address = return_address
        self.locals: List[Any] = [None] * num_locals
        self.operand_stack: List[Any] = []
        self.num_args = num_args
    
    def push(self, value: Any):
        """压入操作数栈"""
        self.operand_stack.append(value)
    
    def pop(self) -> Any:
        """弹出操作数栈"""
        if not self.operand_stack:
            raise RuntimeError("操作数栈为空")
        return self.operand_stack.pop()
    
    def peek(self) -> Any:
        """查看栈顶值"""
        if not self.operand_stack:
            raise RuntimeError("操作数栈为空")
        return self.operand_stack[-1]
    
    def load_local(self, index: int) -> Any:
        """加载局部变量"""
        if 0 <= index < len(self.locals):
            return self.locals[index]
        raise IndexError(f"局部变量索引越界: {index}")
    
    def store_local(self, index: int, value: Any):
        """存储局部变量"""
        if 0 <= index < len(self.locals):
            self.locals[index] = value
        else:
            raise IndexError(f"局部变量索引越界: {index}")


class FunctionInfo:
    """函数信息"""
    
    def __init__(self, name: str, num_params: int, num_locals: int, 
                 start_address: int):
        self.name = name
        self.num_params = num_params
        self.num_locals = num_locals
        self.start_address = start_address


class Assembler:
    """汇编器：将文本汇编代码转换为字节码"""
    
    def __init__(self):
        self.instructions: List[Instruction] = []
        self.constant_pool = ConstantPool()
        self.functions: Dict[str, FunctionInfo] = {}
        self.labels: Dict[str, int] = {}
        self.pending_jumps: List[Tuple[int, str]] = []
        self.current_function: Optional[str] = None
        self.line_number = 0

    def assemble(self, source: str) -> Tuple[List[Instruction], ConstantPool, Dict[str, FunctionInfo]]:
        """汇编源代码

        布局策略：
        1. 将源代码分为函数体指令和主程序指令两部分
        2. 函数体指令放在指令流的前面
        3. 主程序指令放在指令流的后面
        4. 在位置0放置JMP指令，跳转到主程序起始位置
        """
        lines = source.strip().split('\n')

        # 将源代码分为函数体和主程序两部分
        func_lines: List[str] = []   # 函数体内的指令行
        main_lines: List[str] = []   # 主程序的指令行
        in_function = False

        for line in lines:
            stripped = line.strip()
            if not stripped or stripped.startswith('#'):
                continue

            if stripped.startswith('.function'):
                in_function = True
                func_lines.append(stripped)
                continue

            if stripped.startswith('.end'):
                in_function = False
                func_lines.append(stripped)
                continue

            if in_function:
                func_lines.append(stripped)
            else:
                main_lines.append(stripped)

        # 第一遍：扫描函数体，收集标签和函数定义，计算函数体大小
        func_size = 0
        for line in func_lines:
            if line.endswith(':'):
                self.labels[line[:-1].strip()] = func_size + 1  # +1 为JMP指令留位
                continue
            if line.startswith('.function'):
                parts = line.split()
                if len(parts) >= 2:
                    func_name = parts[1]
                    self.functions[func_name] = FunctionInfo(
                        name=func_name,
                        num_params=int(parts[2]) if len(parts) > 2 else 0,
                        num_locals=int(parts[3]) if len(parts) > 3 else 0,
                        start_address=func_size + 1  # +1 为JMP指令留位
                    )
                continue
            if line.startswith('.end'):
                continue
            func_size += 1

        has_functions = func_size > 0
        main_start = func_size + 1 if has_functions else 0  # 主程序起始地址

        # 扫描主程序，收集标签
        main_addr = main_start
        for line in main_lines:
            if line.endswith(':'):
                self.labels[line[:-1].strip()] = main_addr
                continue
            main_addr += 1

        # 第二遍：生成指令
        if has_functions:
            # 位置0: JMP跳转到主程序起始位置（稍后修补）
            self.instructions.append(Instruction(OpCode.JMP, main_start, 0))

        # 生成函数体指令
        self.line_number = 0
        for line in func_lines:
            self.line_number += 1
            if line.endswith(':') or line.startswith('.function') or line.startswith('.end'):
                continue
            self._assemble_instruction(line)

        # 生成主程序指令
        for line in main_lines:
            self.line_number += 1
            if line.endswith(':'):
                continue
            self._assemble_instruction(line)

        # 解析跳转标签
        for i, label in self.pending_jumps:
            if label in self.labels:
                self.instructions[i] = Instruction(
                    self.instructions[i].opcode,
                    self.labels[label],
                    self.instructions[i].line
                )
            else:
                raise ValueError(f"未定义的标签: {label}")

        return self.instructions, self.constant_pool, self.functions
    
    def _assemble_instruction(self, line: str):
        """汇编单条指令"""
        parts = line.split()
        opcode_str = parts[0].upper()
        
        try:
            opcode = OpCode[opcode_str]
        except KeyError:
            raise ValueError(f"未知指令: {opcode_str} (行 {self.line_number})")
        
        operand = None
        
        # 处理操作数
        if len(parts) > 1:
            operand_str = parts[1]
            
            # 带操作数的指令
            if opcode in (OpCode.ICONST, OpCode.DCONST, OpCode.SCONST):
                if opcode == OpCode.ICONST:
                    operand = int(operand_str)
                elif opcode == OpCode.DCONST:
                    operand = float(operand_str)
                elif opcode == OpCode.SCONST:
                    operand = operand_str.strip('"\'')
            elif opcode in (OpCode.JMP, OpCode.JMP_IF_FALSE, OpCode.JMP_IF_TRUE):
                # 跳转指令：操作数可能是标签或数字
                try:
                    operand = int(operand_str)
                except ValueError:
                    # 标签，稍后解析
                    operand = operand_str
                    self.pending_jumps.append((len(self.instructions), operand_str))
            elif opcode in (OpCode.LOAD, OpCode.STORE, OpCode.LOAD_GLOBAL, OpCode.STORE_GLOBAL):
                operand = int(operand_str)
            elif opcode == OpCode.CALL:
                operand = operand_str  # 函数名
            elif opcode == OpCode.LOAD_CONST:
                operand = int(operand_str)
        
        self.instructions.append(Instruction(opcode, operand, self.line_number))


class StackVM:
    """栈式虚拟机"""
    
    def __init__(self, trace_mode: bool = False):
        self.instructions: List[Instruction] = []
        self.constant_pool = ConstantPool()
        self.functions: Dict[str, FunctionInfo] = {}
        self.call_stack: List[StackFrame] = []
        self.globals: Dict[str, Any] = {}
        self.pc = 0  # 程序计数器
        self.running = False
        self.trace_mode = trace_mode
        self.output: List[str] = []
    
    def load(self, instructions: List[Instruction], constant_pool: ConstantPool, 
             functions: Dict[str, FunctionInfo]):
        """加载程序"""
        self.instructions = instructions
        self.constant_pool = constant_pool
        self.functions = functions
        self.pc = 0
        self.running = False
        self.call_stack = []
        self.globals = {}
        self.output = []
    
    def run(self):
        """运行程序"""
        self.running = True
        
        # 创建主函数栈帧
        main_frame = StackFrame("__main__", -1, 256, 0)
        self.call_stack.append(main_frame)
        
        if self.trace_mode:
            print("=== 执行跟踪 ===")
            print(f"指令数量: {len(self.instructions)}")
            print(f"常量池大小: {len(self.constant_pool)}")
            print()
        
        while self.running and self.pc < len(self.instructions):
            instruction = self.instructions[self.pc]
            
            if self.trace_mode:
                self._trace_instruction(instruction)
            
            self._execute_instruction(instruction)
            
            if self.trace_mode:
                self._trace_stack()
        
        if self.trace_mode:
            print("\n=== 执行完成 ===")
            print(f"输出: {self.output}")
    
    def _execute_instruction(self, instruction: Instruction):
        """执行单条指令"""
        opcode = instruction.opcode
        operand = instruction.operand
        frame = self.call_stack[-1]
        
        # 常量指令
        if opcode == OpCode.ICONST:
            frame.push(operand)
            self.pc += 1
        
        elif opcode == OpCode.DCONST:
            frame.push(operand)
            self.pc += 1
        
        elif opcode == OpCode.SCONST:
            frame.push(operand)
            self.pc += 1
        
        elif opcode == OpCode.LOAD_CONST:
            value = self.constant_pool.get(operand)
            frame.push(value)
            self.pc += 1
        
        # 算术指令
        elif opcode == OpCode.IADD:
            b = frame.pop()
            a = frame.pop()
            frame.push(a + b)
            self.pc += 1
        
        elif opcode == OpCode.ISUB:
            b = frame.pop()
            a = frame.pop()
            frame.push(a - b)
            self.pc += 1
        
        elif opcode == OpCode.IMUL:
            b = frame.pop()
            a = frame.pop()
            frame.push(a * b)
            self.pc += 1
        
        elif opcode == OpCode.IDIV:
            b = frame.pop()
            a = frame.pop()
            if b == 0:
                raise RuntimeError("除零错误")
            frame.push(a // b)
            self.pc += 1
        
        elif opcode == OpCode.IMOD:
            b = frame.pop()
            a = frame.pop()
            if b == 0:
                raise RuntimeError("除零错误")
            frame.push(a % b)
            self.pc += 1
        
        elif opcode == OpCode.INEG:
            a = frame.pop()
            frame.push(-a)
            self.pc += 1
        
        # 浮点算术指令
        elif opcode == OpCode.DADD:
            b = frame.pop()
            a = frame.pop()
            frame.push(a + b)
            self.pc += 1
        
        elif opcode == OpCode.DSUB:
            b = frame.pop()
            a = frame.pop()
            frame.push(a - b)
            self.pc += 1
        
        elif opcode == OpCode.DMUL:
            b = frame.pop()
            a = frame.pop()
            frame.push(a * b)
            self.pc += 1
        
        elif opcode == OpCode.DDIV:
            b = frame.pop()
            a = frame.pop()
            if b == 0:
                raise RuntimeError("除零错误")
            frame.push(a / b)
            self.pc += 1
        
        # 比较指令
        elif opcode == OpCode.ICMP_EQ:
            b = frame.pop()
            a = frame.pop()
            frame.push(1 if a == b else 0)
            self.pc += 1
        
        elif opcode == OpCode.ICMP_NE:
            b = frame.pop()
            a = frame.pop()
            frame.push(1 if a != b else 0)
            self.pc += 1
        
        elif opcode == OpCode.ICMP_LT:
            b = frame.pop()
            a = frame.pop()
            frame.push(1 if a < b else 0)
            self.pc += 1
        
        elif opcode == OpCode.ICMP_GT:
            b = frame.pop()
            a = frame.pop()
            frame.push(1 if a > b else 0)
            self.pc += 1
        
        elif opcode == OpCode.ICMP_LE:
            b = frame.pop()
            a = frame.pop()
            frame.push(1 if a <= b else 0)
            self.pc += 1
        
        elif opcode == OpCode.ICMP_GE:
            b = frame.pop()
            a = frame.pop()
            frame.push(1 if a >= b else 0)
            self.pc += 1
        
        # 逻辑指令
        elif opcode == OpCode.AND:
            b = frame.pop()
            a = frame.pop()
            frame.push(1 if a and b else 0)
            self.pc += 1
        
        elif opcode == OpCode.OR:
            b = frame.pop()
            a = frame.pop()
            frame.push(1 if a or b else 0)
            self.pc += 1
        
        elif opcode == OpCode.NOT:
            a = frame.pop()
            frame.push(1 if not a else 0)
            self.pc += 1
        
        # 跳转指令
        elif opcode == OpCode.JMP:
            self.pc = operand
        
        elif opcode == OpCode.JMP_IF_FALSE:
            condition = frame.pop()
            if not condition:
                self.pc = operand
            else:
                self.pc += 1
        
        elif opcode == OpCode.JMP_IF_TRUE:
            condition = frame.pop()
            if condition:
                self.pc = operand
            else:
                self.pc += 1
        
        # 栈操作指令
        elif opcode == OpCode.POP:
            frame.pop()
            self.pc += 1
        
        elif opcode == OpCode.DUP:
            value = frame.pop()
            frame.push(value)
            frame.push(value)
            self.pc += 1
        
        elif opcode == OpCode.SWAP:
            b = frame.pop()
            a = frame.pop()
            frame.push(b)
            frame.push(a)
            self.pc += 1
        
        # 变量指令
        elif opcode == OpCode.LOAD:
            value = frame.load_local(operand)
            frame.push(value)
            self.pc += 1
        
        elif opcode == OpCode.STORE:
            value = frame.pop()
            frame.store_local(operand, value)
            self.pc += 1
        
        elif opcode == OpCode.LOAD_GLOBAL:
            # 全局变量通过名称访问
            name = self.constant_pool.get(operand)
            value = self.globals.get(name)
            frame.push(value)
            self.pc += 1
        
        elif opcode == OpCode.STORE_GLOBAL:
            name = self.constant_pool.get(operand)
            value = frame.pop()
            self.globals[name] = value
            self.pc += 1
        
        # 函数指令
        elif opcode == OpCode.CALL:
            self._call_function(operand)
        
        elif opcode == OpCode.RETURN:
            self._return_from_function()
        
        # 输入输出指令
        elif opcode == OpCode.PRINT:
            value = frame.pop()
            print(value)
            self.output.append(str(value))
            self.pc += 1
        
        elif opcode == OpCode.INPUT:
            value = input()
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass
            frame.push(value)
            self.pc += 1
        
        # 其他指令
        elif opcode == OpCode.HALT:
            self.running = False
        
        elif opcode == OpCode.NOP:
            self.pc += 1
        
        else:
            raise RuntimeError(f"未实现的指令: {opcode}")
    
    def _call_function(self, func_name: str):
        """调用函数"""
        if func_name not in self.functions:
            raise RuntimeError(f"未定义的函数: {func_name}")
        
        func_info = self.functions[func_name]
        caller_frame = self.call_stack[-1]
        
        # 创建新的栈帧
        new_frame = StackFrame(
            func_name,
            self.pc + 1,  # 返回地址
            func_info.num_locals,
            func_info.num_params
        )
        
        # 传递参数（从调用者的栈中弹出）
        for i in range(func_info.num_params - 1, -1, -1):
            arg_value = caller_frame.pop()
            new_frame.store_local(i, arg_value)
        
        self.call_stack.append(new_frame)
        self.pc = func_info.start_address
        
        if self.trace_mode:
            print(f"  -> 调用函数 {func_name}，参数: {new_frame.locals[:func_info.num_params]}")
            print(f"     局部变量: {new_frame.locals}")
    
    def _return_from_function(self):
        """从函数返回"""
        if len(self.call_stack) <= 1:
            raise RuntimeError("不能从主函数返回")
        
        # 弹出当前栈帧
        current_frame = self.call_stack.pop()
        return_value = None
        
        # 如果有返回值，从当前栈帧的操作数栈中取出
        if current_frame.operand_stack:
            return_value = current_frame.pop()
        
        # 恢复调用者的上下文
        caller_frame = self.call_stack[-1]
        self.pc = current_frame.return_address
        
        # 将返回值压入调用者的栈
        if return_value is not None:
            caller_frame.push(return_value)
        
        if self.trace_mode:
            print(f"  <- 从函数 {current_frame.function_name} 返回，返回值: {return_value}")
    
    def _trace_instruction(self, instruction: Instruction):
        """跟踪指令执行"""
        print(f"PC={self.pc:3d} | {instruction.opcode.name:15s}", end="")
        if instruction.operand is not None:
            print(f" {instruction.operand}", end="")
        print()
    
    def _trace_stack(self):
        """跟踪栈状态"""
        frame = self.call_stack[-1]
        stack_str = ", ".join(str(x) for x in frame.operand_stack)
        locals_str = ", ".join(str(x) for x in frame.locals if x is not None)
        print(f"       | 栈: [{stack_str}]")
        print(f"       | 局部变量: [{locals_str}]")
        print()


def create_assembler() -> Assembler:
    """创建汇编器实例"""
    return Assembler()


def create_vm(trace_mode: bool = False) -> StackVM:
    """创建虚拟机实例"""
    return StackVM(trace_mode=trace_mode)


def run_program(source: str, trace_mode: bool = False):
    """运行汇编程序"""
    assembler = create_assembler()
    instructions, constant_pool, functions = assembler.assemble(source)
    
    vm = create_vm(trace_mode=trace_mode)
    vm.load(instructions, constant_pool, functions)
    vm.run()
    
    return vm


# 示例程序
EXAMPLE_PROGRAM = """
# 简单的算术运算程序
# 计算 (3 + 4) * 5 并打印结果

# 主程序
ICONST 3
ICONST 4
IADD
ICONST 5
IMUL
PRINT
HALT
"""


def main():
    """主函数"""
    print("=== 栈式虚拟机演示 ===\n")
    
    # 示例1：简单算术运算
    print("示例1：计算 (3 + 4) * 5")
    print("汇编代码：")
    print(EXAMPLE_PROGRAM)
    print("执行结果：")
    run_program(EXAMPLE_PROGRAM, trace_mode=True)
    
    print("\n" + "="*50 + "\n")
    
    # 示例2：函数调用
    FUNCTION_PROGRAM = """
# 函数调用示例
# 计算斐波那契数列

.function fibonacci 1 3
# 参数: n (局部变量0)
# 局部变量1: 临时变量1
# 局部变量2: 临时变量2

# if n <= 1
LOAD 0
ICONST 1
ICMP_LE
JMP_IF_FALSE recursive_case

# 基础情况：返回n
LOAD 0
RETURN

recursive_case:
# 递归情况：fib(n-1) + fib(n-2)
# 保存n到局部变量1
LOAD 0
STORE 1

# 计算 fib(n-1)
LOAD 1
ICONST 1
ISUB
CALL fibonacci
STORE 2  # 保存 fib(n-1) 到局部变量2

# 计算 fib(n-2)
LOAD 1
ICONST 2
ISUB
CALL fibonacci

# 相加 fib(n-1) + fib(n-2)
LOAD 2
IADD
RETURN

.end fibonacci

# 主程序
ICONST 10
CALL fibonacci
PRINT
HALT
"""
    
    print("示例2：斐波那契数列（递归）")
    print("汇编代码：")
    print(FUNCTION_PROGRAM)
    print("执行结果：")
    try:
        run_program(FUNCTION_PROGRAM, trace_mode=False)
    except Exception as e:
        print(f"错误: {e}")
    
    print("\n" + "="*50 + "\n")
    
    # 示例3：简单函数调用
    SIMPLE_FUNCTION = """
# 简单函数调用示例
# 计算平方

.function square 1 1
# 参数: n (局部变量0)

# 计算 n * n
LOAD 0
LOAD 0
IMUL
RETURN

.end square

# 主程序
ICONST 5
CALL square
PRINT
HALT
"""
    
    print("示例3：简单函数调用（计算平方）")
    print("汇编代码：")
    print(SIMPLE_FUNCTION)
    print("执行结果：")
    run_program(SIMPLE_FUNCTION, trace_mode=True)
    
    print("\n" + "="*50 + "\n")
    
    # 示例4：循环和条件
    LOOP_PROGRAM = """
# 循环示例：计算1到10的和

# 初始化
ICONST 0      # sum = 0
STORE 0       # 局部变量0 = sum
ICONST 1      # i = 1
STORE 1       # 局部变量1 = i

loop_start:
# 检查条件 i <= 10
LOAD 1
ICONST 10
ICMP_LE
JMP_IF_FALSE loop_end

# sum += i
LOAD 0
LOAD 1
IADD
STORE 0

# i++
LOAD 1
ICONST 1
IADD
STORE 1

JMP loop_start

loop_end:
# 打印结果
LOAD 0
PRINT
HALT
"""
    
    print("示例3：循环计算1到10的和")
    print("汇编代码：")
    print(LOOP_PROGRAM)
    print("执行结果：")
    run_program(LOOP_PROGRAM, trace_mode=True)


if __name__ == "__main__":
    main()