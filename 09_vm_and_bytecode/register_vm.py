"""
寄存器式虚拟机实现
==================
一个完整的寄存器式虚拟机，包括：
- 寄存器文件
- 指令解码和执行
- 与栈式虚拟机功能对应
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum, auto


class RegisterOpCode(Enum):
    """寄存器式虚拟机操作码定义"""
    # 常量指令
    LOADK = auto()      # 将常量加载到寄存器
    LOADI = auto()      # 将整数立即数加载到寄存器
    LOADF = auto()      # 将浮点数立即数加载到寄存器
    LOADS = auto()      # 将字符串常量加载到寄存器
    LOADNIL = auto()    # 将nil加载到寄存器
    LOADBOOL = auto()   # 将布尔值加载到寄存器
    
    # 算术指令
    ADD = auto()        # 加法: R(A) = R(B) + R(C)
    SUB = auto()        # 减法: R(A) = R(B) - R(C)
    MUL = auto()        # 乘法: R(A) = R(B) * R(C)
    DIV = auto()        # 除法: R(A) = R(B) / R(C)
    MOD = auto()        # 取模: R(A) = R(B) % R(C)
    NEG = auto()        # 取负: R(A) = -R(B)
    
    # 比较指令
    EQ = auto()         # 相等: if R(B) == R(C) then R(A) = 1 else R(A) = 0
    LT = auto()         # 小于: if R(B) < R(C) then R(A) = 1 else R(A) = 0
    LE = auto()         # 小于等于: if R(B) <= R(C) then R(A) = 1 else R(A) = 0
    
    # 逻辑指令
    AND = auto()        # 逻辑与: R(A) = R(B) and R(C)
    OR = auto()         # 逻辑或: R(A) = R(B) or R(C)
    NOT = auto()        # 逻辑非: R(A) = not R(B)
    
    # 跳转指令
    JMP = auto()        # 无条件跳转
    JMP_IF_FALSE = auto()  # 条件跳转（假）
    JMP_IF_TRUE = auto()   # 条件跳转（真）
    
    # 移动指令
    MOVE = auto()       # 移动: R(A) = R(B)
    
    # 函数指令
    CALL = auto()       # 调用函数
    RETURN = auto()     # 从函数返回
    
    # 输入输出指令
    PRINT = auto()      # 打印寄存器值
    INPUT = auto()      # 输入到寄存器
    
    # 其他指令
    HALT = auto()       # 停止执行
    NOP = auto()        # 空操作


@dataclass
class RegisterInstruction:
    """寄存器式指令"""
    opcode: RegisterOpCode
    a: int = 0          # 目标寄存器
    b: int = 0          # 源寄存器1
    c: int = 0          # 源寄存器2
    bx: int = 0         # 扩展操作数（用于LOADK等）
    line: int = 0       # 源代码行号


class RegisterFile:
    """寄存器文件"""
    
    def __init__(self, num_registers: int = 256):
        self.registers: List[Any] = [None] * num_registers
        self.num_registers = num_registers
    
    def get(self, index: int) -> Any:
        """获取寄存器值"""
        if 0 <= index < self.num_registers:
            return self.registers[index]
        raise IndexError(f"寄存器索引越界: {index}")
    
    def set(self, index: int, value: Any):
        """设置寄存器值"""
        if 0 <= index < self.num_registers:
            self.registers[index] = value
        else:
            raise IndexError(f"寄存器索引越界: {index}")
    
    def clear(self):
        """清空所有寄存器"""
        self.registers = [None] * self.num_registers


class RegisterConstantPool:
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


class RegisterStackFrame:
    """寄存器式栈帧"""
    
    def __init__(self, function_name: str, return_address: int, 
                 num_registers: int, num_args: int, base_register: int):
        self.function_name = function_name
        self.return_address = return_address
        self.num_registers = num_registers
        self.num_args = num_args
        self.base_register = base_register  # 寄存器基址
        self.register_file = RegisterFile(num_registers)


class RegisterFunctionInfo:
    """函数信息"""
    
    def __init__(self, name: str, num_params: int, num_registers: int, 
                 start_address: int):
        self.name = name
        self.num_params = num_params
        self.num_registers = num_registers
        self.start_address = start_address


class RegisterAssembler:
    """寄存器式汇编器"""
    
    def __init__(self):
        self.instructions: List[RegisterInstruction] = []
        self.constant_pool = RegisterConstantPool()
        self.functions: Dict[str, RegisterFunctionInfo] = {}
        self.labels: Dict[str, int] = {}
        self.pending_jumps: List[Tuple[int, str, RegisterOpCode]] = []
        self.line_number = 0
    
    def assemble(self, source: str) -> Tuple[List[RegisterInstruction], RegisterConstantPool, Dict[str, RegisterFunctionInfo]]:
        """汇编源代码

        布局策略（与栈式虚拟机汇编器一致）：
        1. 函数体指令放在指令流前面
        2. 主程序指令放在指令流后面
        3. 在位置0放置JMP指令，跳转到主程序起始位置
        """
        lines = source.strip().split('\n')

        # 将源代码分为函数体和主程序两部分
        func_lines: List[str] = []
        main_lines: List[str] = []
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
                    self.functions[func_name] = RegisterFunctionInfo(
                        name=func_name,
                        num_params=int(parts[2]) if len(parts) > 2 else 0,
                        num_registers=int(parts[3]) if len(parts) > 3 else 16,
                        start_address=func_size + 1
                    )
                continue
            if line.startswith('.end'):
                continue
            func_size += 1

        has_functions = func_size > 0
        main_start = func_size + 1 if has_functions else 0

        # 扫描主程序，收集标签
        main_addr = main_start
        for line in main_lines:
            if line.endswith(':'):
                self.labels[line[:-1].strip()] = main_addr
                continue
            main_addr += 1

        # 第二遍：生成指令
        if has_functions:
            self.instructions.append(RegisterInstruction(opcode=RegisterOpCode.JMP, bx=main_start, line=0))

        self.line_number = 0
        for line in func_lines:
            self.line_number += 1
            if line.endswith(':') or line.startswith('.function') or line.startswith('.end'):
                continue
            self._assemble_instruction(line)

        for line in main_lines:
            self.line_number += 1
            if line.endswith(':'):
                continue
            self._assemble_instruction(line)

        # 解析跳转标签
        for i, label, opcode in self.pending_jumps:
            if label in self.labels:
                self.instructions[i].bx = self.labels[label]
            else:
                raise ValueError(f"未定义的标签: {label}")

        return self.instructions, self.constant_pool, self.functions
    
    def _assemble_instruction(self, line: str):
        """汇编单条指令"""
        # 去除注释
        if '#' in line:
            line = line[:line.index('#')]
        # 将逗号替换为空格，然后分割
        line = line.replace(',', ' ')
        parts = line.split()
        opcode_str = parts[0].upper()
        
        try:
            opcode = RegisterOpCode[opcode_str]
        except KeyError:
            raise ValueError(f"未知指令: {opcode_str} (行 {self.line_number})")
        
        instruction = RegisterInstruction(opcode=opcode, line=self.line_number)
        
        # 解析操作数
        if opcode in (RegisterOpCode.LOADI, RegisterOpCode.LOADF, RegisterOpCode.LOADS, 
                      RegisterOpCode.LOADK, RegisterOpCode.LOADNIL, RegisterOpCode.LOADBOOL):
            # LOADK R(A), const
            if len(parts) >= 3:
                instruction.a = self._parse_register(parts[1])
                if opcode == RegisterOpCode.LOADI:
                    instruction.bx = int(parts[2])
                elif opcode == RegisterOpCode.LOADF:
                    instruction.bx = self.constant_pool.add_float(float(parts[2]))
                elif opcode == RegisterOpCode.LOADS:
                    instruction.bx = self.constant_pool.add_string(parts[2].strip('"\''))
                elif opcode == RegisterOpCode.LOADK:
                    instruction.bx = int(parts[2])
                elif opcode == RegisterOpCode.LOADBOOL:
                    instruction.bx = 1 if parts[2].lower() == 'true' else 0
        
        elif opcode in (RegisterOpCode.ADD, RegisterOpCode.SUB, RegisterOpCode.MUL, 
                        RegisterOpCode.DIV, RegisterOpCode.MOD, RegisterOpCode.AND, 
                        RegisterOpCode.OR, RegisterOpCode.EQ, RegisterOpCode.LT, 
                        RegisterOpCode.LE):
            # R(A) = R(B) op R(C)
            if len(parts) >= 4:
                instruction.a = self._parse_register(parts[1])
                instruction.b = self._parse_register(parts[2])
                instruction.c = self._parse_register(parts[3])
        
        elif opcode in (RegisterOpCode.NEG, RegisterOpCode.NOT, RegisterOpCode.MOVE):
            # R(A) = op R(B)
            if len(parts) >= 3:
                instruction.a = self._parse_register(parts[1])
                instruction.b = self._parse_register(parts[2])
        
        elif opcode in (RegisterOpCode.JMP, RegisterOpCode.JMP_IF_FALSE, RegisterOpCode.JMP_IF_TRUE):
            # JMP label 或 JMP_IF_FALSE R(A), label
            if opcode == RegisterOpCode.JMP:
                if len(parts) >= 2:
                    try:
                        instruction.bx = int(parts[1])
                    except ValueError:
                        self.pending_jumps.append((len(self.instructions), parts[1], opcode))
            else:
                if len(parts) >= 3:
                    instruction.a = self._parse_register(parts[1])
                    try:
                        instruction.bx = int(parts[2])
                    except ValueError:
                        self.pending_jumps.append((len(self.instructions), parts[2], opcode))
        
        elif opcode == RegisterOpCode.CALL:
            # CALL func_name, num_args
            if len(parts) >= 3:
                instruction.a = self.constant_pool.add_string(parts[1])  # 函数名
                instruction.b = int(parts[2])  # 参数数量
        
        elif opcode == RegisterOpCode.RETURN:
            # RETURN R(A)
            if len(parts) >= 2:
                instruction.a = self._parse_register(parts[1])
        
        elif opcode in (RegisterOpCode.PRINT, RegisterOpCode.INPUT):
            # PRINT R(A) 或 INPUT R(A)
            if len(parts) >= 2:
                instruction.a = self._parse_register(parts[1])
        
        self.instructions.append(instruction)
    
    def _parse_register(self, reg_str: str) -> int:
        """解析寄存器编号"""
        if reg_str.startswith('R') or reg_str.startswith('r'):
            return int(reg_str[1:])
        return int(reg_str)


class RegisterVM:
    """寄存器式虚拟机"""
    
    def __init__(self, num_registers: int = 256, trace_mode: bool = False):
        self.instructions: List[RegisterInstruction] = []
        self.constant_pool = RegisterConstantPool()
        self.functions: Dict[str, RegisterFunctionInfo] = {}
        self.call_stack: List[RegisterStackFrame] = []
        self.current_frame: Optional[RegisterStackFrame] = None
        self.pc = 0
        self.running = False
        self.trace_mode = trace_mode
        self.output: List[str] = []
        self.num_registers = num_registers
    
    def load(self, instructions: List[RegisterInstruction], constant_pool: RegisterConstantPool,
             functions: Dict[str, RegisterFunctionInfo]):
        """加载程序"""
        self.instructions = instructions
        self.constant_pool = constant_pool
        self.functions = functions
        self.pc = 0
        self.running = False
        self.call_stack = []
        self.output = []
        
        # 创建主栈帧
        self.current_frame = RegisterStackFrame("__main__", -1, self.num_registers, 0, 0)
        self.call_stack.append(self.current_frame)
    
    def run(self):
        """运行程序"""
        self.running = True
        
        if self.trace_mode:
            print("=== 寄存器式虚拟机执行跟踪 ===")
            print(f"指令数量: {len(self.instructions)}")
            print(f"常量池大小: {len(self.constant_pool)}")
            print()
        
        while self.running and self.pc < len(self.instructions):
            instruction = self.instructions[self.pc]
            
            if self.trace_mode:
                self._trace_instruction(instruction)
            
            self._execute_instruction(instruction)
            
            if self.trace_mode:
                self._trace_registers()
        
        if self.trace_mode:
            print("\n=== 执行完成 ===")
            print(f"输出: {self.output}")
    
    def _execute_instruction(self, instruction: RegisterInstruction):
        """执行单条指令"""
        opcode = instruction.opcode
        frame = self.current_frame
        
        # 常量指令
        if opcode == RegisterOpCode.LOADI:
            frame.register_file.set(instruction.a, instruction.bx)
            self.pc += 1
        
        elif opcode == RegisterOpCode.LOADF:
            value = self.constant_pool.get(instruction.bx)
            frame.register_file.set(instruction.a, value)
            self.pc += 1
        
        elif opcode == RegisterOpCode.LOADS:
            value = self.constant_pool.get(instruction.bx)
            frame.register_file.set(instruction.a, value)
            self.pc += 1
        
        elif opcode == RegisterOpCode.LOADK:
            value = self.constant_pool.get(instruction.bx)
            frame.register_file.set(instruction.a, value)
            self.pc += 1
        
        elif opcode == RegisterOpCode.LOADNIL:
            frame.register_file.set(instruction.a, None)
            self.pc += 1
        
        elif opcode == RegisterOpCode.LOADBOOL:
            frame.register_file.set(instruction.a, bool(instruction.bx))
            self.pc += 1
        
        # 算术指令
        elif opcode == RegisterOpCode.ADD:
            b = frame.register_file.get(instruction.b)
            c = frame.register_file.get(instruction.c)
            frame.register_file.set(instruction.a, b + c)
            self.pc += 1
        
        elif opcode == RegisterOpCode.SUB:
            b = frame.register_file.get(instruction.b)
            c = frame.register_file.get(instruction.c)
            frame.register_file.set(instruction.a, b - c)
            self.pc += 1
        
        elif opcode == RegisterOpCode.MUL:
            b = frame.register_file.get(instruction.b)
            c = frame.register_file.get(instruction.c)
            frame.register_file.set(instruction.a, b * c)
            self.pc += 1
        
        elif opcode == RegisterOpCode.DIV:
            b = frame.register_file.get(instruction.b)
            c = frame.register_file.get(instruction.c)
            if c == 0:
                raise RuntimeError("除零错误")
            frame.register_file.set(instruction.a, b / c)
            self.pc += 1
        
        elif opcode == RegisterOpCode.MOD:
            b = frame.register_file.get(instruction.b)
            c = frame.register_file.get(instruction.c)
            if c == 0:
                raise RuntimeError("除零错误")
            frame.register_file.set(instruction.a, b % c)
            self.pc += 1
        
        elif opcode == RegisterOpCode.NEG:
            b = frame.register_file.get(instruction.b)
            frame.register_file.set(instruction.a, -b)
            self.pc += 1
        
        # 比较指令
        elif opcode == RegisterOpCode.EQ:
            b = frame.register_file.get(instruction.b)
            c = frame.register_file.get(instruction.c)
            frame.register_file.set(instruction.a, 1 if b == c else 0)
            self.pc += 1
        
        elif opcode == RegisterOpCode.LT:
            b = frame.register_file.get(instruction.b)
            c = frame.register_file.get(instruction.c)
            frame.register_file.set(instruction.a, 1 if b < c else 0)
            self.pc += 1
        
        elif opcode == RegisterOpCode.LE:
            b = frame.register_file.get(instruction.b)
            c = frame.register_file.get(instruction.c)
            frame.register_file.set(instruction.a, 1 if b <= c else 0)
            self.pc += 1
        
        # 逻辑指令
        elif opcode == RegisterOpCode.AND:
            b = frame.register_file.get(instruction.b)
            c = frame.register_file.get(instruction.c)
            frame.register_file.set(instruction.a, 1 if b and c else 0)
            self.pc += 1
        
        elif opcode == RegisterOpCode.OR:
            b = frame.register_file.get(instruction.b)
            c = frame.register_file.get(instruction.c)
            frame.register_file.set(instruction.a, 1 if b or c else 0)
            self.pc += 1
        
        elif opcode == RegisterOpCode.NOT:
            b = frame.register_file.get(instruction.b)
            frame.register_file.set(instruction.a, 1 if not b else 0)
            self.pc += 1
        
        # 跳转指令
        elif opcode == RegisterOpCode.JMP:
            self.pc = instruction.bx
        
        elif opcode == RegisterOpCode.JMP_IF_FALSE:
            condition = frame.register_file.get(instruction.a)
            if not condition:
                self.pc = instruction.bx
            else:
                self.pc += 1
        
        elif opcode == RegisterOpCode.JMP_IF_TRUE:
            condition = frame.register_file.get(instruction.a)
            if condition:
                self.pc = instruction.bx
            else:
                self.pc += 1
        
        # 移动指令
        elif opcode == RegisterOpCode.MOVE:
            value = frame.register_file.get(instruction.b)
            frame.register_file.set(instruction.a, value)
            self.pc += 1
        
        # 函数指令
        elif opcode == RegisterOpCode.CALL:
            self._call_function(instruction)
        
        elif opcode == RegisterOpCode.RETURN:
            self._return_from_function(instruction)
        
        # 输入输出指令
        elif opcode == RegisterOpCode.PRINT:
            value = frame.register_file.get(instruction.a)
            print(value)
            self.output.append(str(value))
            self.pc += 1
        
        elif opcode == RegisterOpCode.INPUT:
            value = input()
            try:
                value = int(value)
            except ValueError:
                try:
                    value = float(value)
                except ValueError:
                    pass
            frame.register_file.set(instruction.a, value)
            self.pc += 1
        
        # 其他指令
        elif opcode == RegisterOpCode.HALT:
            self.running = False
        
        elif opcode == RegisterOpCode.NOP:
            self.pc += 1
        
        else:
            raise RuntimeError(f"未实现的指令: {opcode}")
    
    def _call_function(self, instruction: RegisterInstruction):
        """调用函数"""
        func_name = self.constant_pool.get(instruction.a)
        num_args = instruction.b
        
        if func_name not in self.functions:
            raise RuntimeError(f"未定义的函数: {func_name}")
        
        func_info = self.functions[func_name]
        
        # 计算新栈帧的寄存器基址
        base_register = self.current_frame.base_register + self.current_frame.num_registers
        
        # 创建新栈帧
        new_frame = RegisterStackFrame(
            func_name,
            self.pc + 1,
            func_info.num_registers,
            num_args,
            base_register
        )
        
        # 传递参数
        for i in range(num_args):
            # 参数在调用者的寄存器中，从R(instruction.a + 1)开始
            arg_value = self.current_frame.register_file.get(instruction.a + 1 + i)
            new_frame.register_file.set(i, arg_value)
        
        self.call_stack.append(new_frame)
        self.current_frame = new_frame
        self.pc = func_info.start_address
        
        if self.trace_mode:
            args = [new_frame.register_file.get(i) for i in range(num_args)]
            print(f"  -> 调用函数 {func_name}，参数: {args}")
    
    def _return_from_function(self, instruction: RegisterInstruction):
        """从函数返回"""
        if len(self.call_stack) <= 1:
            raise RuntimeError("不能从主函数返回")

        # 获取返回值
        return_value = self.current_frame.register_file.get(instruction.a)

        # 保存返回地址（在弹出栈帧之前）
        return_address = self.current_frame.return_address

        # 弹出当前栈帧
        self.call_stack.pop()
        self.current_frame = self.call_stack[-1]

        # 恢复程序计数器
        self.pc = return_address

        # 将返回值存入调用者的寄存器
        # 返回值存入调用者调用CALL指令时的目标寄存器
        # 这里简化处理，存入R0
        self.current_frame.register_file.set(0, return_value)

        if self.trace_mode:
            print(f"  <- 返回，返回值: {return_value}")
    
    def _trace_instruction(self, instruction: RegisterInstruction):
        """跟踪指令执行"""
        print(f"PC={self.pc:3d} | {instruction.opcode.name:15s}", end="")
        if instruction.opcode in (RegisterOpCode.ADD, RegisterOpCode.SUB, RegisterOpCode.MUL, 
                                  RegisterOpCode.DIV, RegisterOpCode.MOD, RegisterOpCode.AND, 
                                  RegisterOpCode.OR, RegisterOpCode.EQ, RegisterOpCode.LT, 
                                  RegisterOpCode.LE):
            print(f" R{instruction.a}, R{instruction.b}, R{instruction.c}", end="")
        elif instruction.opcode in (RegisterOpCode.NEG, RegisterOpCode.NOT, RegisterOpCode.MOVE):
            print(f" R{instruction.a}, R{instruction.b}", end="")
        elif instruction.opcode in (RegisterOpCode.LOADI, RegisterOpCode.LOADF, RegisterOpCode.LOADS, 
                                    RegisterOpCode.LOADK, RegisterOpCode.LOADNIL, RegisterOpCode.LOADBOOL):
            print(f" R{instruction.a}, {instruction.bx}", end="")
        elif instruction.opcode in (RegisterOpCode.PRINT, RegisterOpCode.INPUT, RegisterOpCode.RETURN):
            print(f" R{instruction.a}", end="")
        elif instruction.opcode == RegisterOpCode.CALL:
            func_name = self.constant_pool.get(instruction.a)
            print(f" {func_name}, {instruction.b}", end="")
        elif instruction.opcode == RegisterOpCode.JMP:
            print(f" {instruction.bx}", end="")
        elif instruction.opcode in (RegisterOpCode.JMP_IF_FALSE, RegisterOpCode.JMP_IF_TRUE):
            print(f" R{instruction.a}, {instruction.bx}", end="")
        print()
    
    def _trace_registers(self):
        """跟踪寄存器状态"""
        frame = self.current_frame
        non_null_regs = []
        for i in range(frame.num_registers):
            value = frame.register_file.get(i)
            if value is not None:
                non_null_regs.append(f"R{i}={value}")
        print(f"       | 寄存器: {', '.join(non_null_regs)}")
        print()


def create_assembler() -> RegisterAssembler:
    """创建汇编器实例"""
    return RegisterAssembler()


def create_vm(num_registers: int = 256, trace_mode: bool = False) -> RegisterVM:
    """创建虚拟机实例"""
    return RegisterVM(num_registers=num_registers, trace_mode=trace_mode)


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
# 寄存器式虚拟机示例程序
# 计算 (3 + 4) * 5 并打印结果

# 加载常量到寄存器
LOADI R0, 3
LOADI R1, 4
ADD R2, R0, R1      # R2 = R0 + R1 = 7
LOADI R3, 5
MUL R4, R2, R3      # R4 = R2 * R3 = 35
PRINT R4
HALT
"""


def main():
    """主函数"""
    print("=== 寄存器式虚拟机演示 ===\n")
    
    # 示例1：简单算术运算
    print("示例1：计算 (3 + 4) * 5")
    print("汇编代码：")
    print(EXAMPLE_PROGRAM)
    print("执行结果：")
    run_program(EXAMPLE_PROGRAM, trace_mode=True)
    
    print("\n" + "="*50 + "\n")
    
    # 示例2：循环计算
    LOOP_PROGRAM = """
# 循环示例：计算1到10的和

# 初始化
LOADI R0, 0        # sum = 0
LOADI R1, 1        # i = 1
LOADI R2, 10       # limit = 10

loop_start:
# 检查条件 i <= 10
LE R3, R1, R2      # R3 = (R1 <= R2)
JMP_IF_FALSE R3, loop_end

# sum += i
ADD R0, R0, R1     # R0 = R0 + R1

# i++
LOADI R4, 1
ADD R1, R1, R4     # R1 = R1 + 1

JMP loop_start

loop_end:
# 打印结果
PRINT R0
HALT
"""
    
    print("示例2：循环计算1到10的和")
    print("汇编代码：")
    print(LOOP_PROGRAM)
    print("执行结果：")
    run_program(LOOP_PROGRAM, trace_mode=True)
    
    print("\n" + "="*50 + "\n")
    
    # 示例3：函数调用
    FUNCTION_PROGRAM = """
# 函数调用示例
# 计算斐波那契数列

.function fibonacci 1 8
# 参数: n (R0)
# 返回值: fib(n) (R0)
# 局部寄存器使用:
#   R0: n (参数)
#   R1: 1 (常量)
#   R2: 比较结果
#   R3: n-1
#   R4: n-2
#   R5: fib(n-1)结果
#   R6: fib(n-2)结果

# 检查基础情况 n <= 1
LOADI R1, 1
LE R2, R0, R1
JMP_IF_FALSE R2, recursive_case

# 基础情况：返回n
RETURN R0

recursive_case:
# 递归情况：fib(n-1) + fib(n-2)

# 保存n到寄存器，计算n-1和n-2
LOADI R1, 1
SUB R3, R0, R1     # R3 = n - 1
LOADI R1, 2
SUB R4, R0, R1     # R4 = n - 2

# 计算 fib(n-1)
# 参数需要放在R(constant_pool_index + 1)的位置
# constant_pool_index=0 for 'fibonacci', so param in R1
MOVE R1, R3        # 参数 n-1 放到 R1
CALL fibonacci, 1
MOVE R5, R0        # 保存 fib(n-1) 到 R5

# 计算 fib(n-2)
MOVE R1, R4        # 参数 n-2 放到 R1
CALL fibonacci, 1
MOVE R6, R0        # 保存 fib(n-2) 到 R6

# 相加 fib(n-1) + fib(n-2)
ADD R0, R5, R6
RETURN R0

.end fibonacci

# 主程序
LOADI R1, 5        # 参数: fib(5)
CALL fibonacci, 1
PRINT R0
HALT
"""
    
    print("示例3：斐波那契数列（函数调用）")
    print("汇编代码：")
    print(FUNCTION_PROGRAM)
    print("执行结果：")
    run_program(FUNCTION_PROGRAM, trace_mode=False)


if __name__ == "__main__":
    main()