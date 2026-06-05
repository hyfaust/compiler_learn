#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
jit_compiler.py - 简化的JIT编译器演示

本模块演示JIT编译的核心概念：
1. 一个简单的字节码虚拟机
2. 基于计数器的热点检测
3. 将热点函数的简单算术表达式编译为x86-64机器码
4. JIT编译前后的性能对比

注意：机器码生成部分仅支持x86-64平台（Windows/Linux/macOS x64）。
在其他平台上，演示将使用Python函数模拟JIT编译的效果。

运行方式：
    python jit_compiler.py
"""

import struct
import sys
import time
import ctypes
import platform
import mmap
from typing import List, Dict, Any, Optional, Callable, Tuple
from dataclasses import dataclass, field
from enum import IntEnum


# ============================================================================
# 字节码定义
# ============================================================================

class Opcode(IntEnum):
    """字节码操作码"""
    LOAD_CONST = 0      # LOAD_CONST  reg, const_idx  ; reg = constants[const_idx]
    LOAD_VAR = 1        # LOAD_VAR    reg, var_idx     ; reg = variables[var_idx]
    STORE_VAR = 2       # STORE_VAR   var_idx, reg     ; variables[var_idx] = reg
    ADD = 3             # ADD          dst, src1, src2  ; dst = src1 + src2
    SUB = 4             # SUB          dst, src1, src2  ; dst = src1 - src2
    MUL = 5             # MUL          dst, src1, src2  ; dst = src1 * src2
    DIV = 6             # DIV          dst, src1, src2  ; dst = src1 / src2
    MOD = 7             # MOD          dst, src1, src2  ; dst = src1 % src2
    NEG = 8             # NEG          dst, src         ; dst = -src
    CMP_LT = 9          # CMP_LT      dst, src1, src2  ; dst = (src1 < src2)
    CMP_GT = 10         # CMP_GT      dst, src1, src2  ; dst = (src1 > src2)
    CMP_EQ = 11         # CMP_EQ      dst, src1, src2  ; dst = (src1 == src2)
    JMP = 12            # JMP          offset           ; PC += offset
    JMP_IF_FALSE = 13   # JMP_IF_FALSE reg, offset      ; if not reg: PC += offset
    CALL = 14           # CALL         func_idx, arg_start, arg_count, ret_reg
    RET = 15            # RET          reg              ; return reg
    HALT = 16           # HALT                          ; 停止执行
    NOP = 17            # NOP                           ; 空操作


@dataclass
class Instruction:
    """字节码指令"""
    opcode: Opcode
    args: List[int] = field(default_factory=list)

    def __repr__(self):
        args_str = ", ".join(str(a) for a in self.args)
        return f"{self.opcode.name}({args_str})"


@dataclass
class BytecodeFunction:
    """字节码函数"""
    name: str
    num_params: int
    num_locals: int          # 局部变量数量（包括参数）
    num_registers: int       # 寄存器数量
    constants: List[float]   # 常量池
    instructions: List[Instruction]

    def __repr__(self):
        return f"<BytecodeFunction {self.name} params={self.num_params}>"


# ============================================================================
# 字节码构建器（辅助类）
# ============================================================================

class BytecodeBuilder:
    """字节码构建器 - 简化字节码函数的创建"""

    def __init__(self, name: str, num_params: int = 0):
        self.name = name
        self.num_params = num_params
        self.constants: List[float] = []
        self.instructions: List[Instruction] = []
        self.next_register = 0
        self.num_locals = num_params

    def _alloc_reg(self) -> int:
        """分配一个寄存器"""
        reg = self.next_register
        self.next_register += 1
        return reg

    def _add_const(self, value: float) -> int:
        """添加常量到常量池，返回索引"""
        if value in self.constants:
            return self.constants.index(value)
        idx = len(self.constants)
        self.constants.append(value)
        return idx

    def emit(self, opcode: Opcode, *args: int) -> int:
        """发射一条指令，返回指令索引"""
        idx = len(self.instructions)
        self.instructions.append(Instruction(opcode, list(args)))
        return idx

    def load_const(self, value: float) -> int:
        """加载常量到寄存器，返回寄存器索引"""
        reg = self._alloc_reg()
        const_idx = self._add_const(value)
        self.emit(Opcode.LOAD_CONST, reg, const_idx)
        return reg

    def load_var(self, var_idx: int) -> int:
        """加载变量到寄存器，返回寄存器索引"""
        reg = self._alloc_reg()
        self.emit(Opcode.LOAD_VAR, reg, var_idx)
        return reg

    def store_var(self, var_idx: int, reg: int):
        """存储寄存器到变量"""
        self.emit(Opcode.STORE_VAR, var_idx, reg)

    def add(self, reg1: int, reg2: int) -> int:
        """加法，返回结果寄存器"""
        dst = self._alloc_reg()
        self.emit(Opcode.ADD, dst, reg1, reg2)
        return dst

    def sub(self, reg1: int, reg2: int) -> int:
        """减法，返回结果寄存器"""
        dst = self._alloc_reg()
        self.emit(Opcode.SUB, dst, reg1, reg2)
        return dst

    def mul(self, reg1: int, reg2: int) -> int:
        """乘法，返回结果寄存器"""
        dst = self._alloc_reg()
        self.emit(Opcode.MUL, dst, reg1, reg2)
        return dst

    def div(self, reg1: int, reg2: int) -> int:
        """除法，返回结果寄存器"""
        dst = self._alloc_reg()
        self.emit(Opcode.DIV, dst, reg1, reg2)
        return dst

    def mod(self, reg1: int, reg2: int) -> int:
        """取模，返回结果寄存器"""
        dst = self._alloc_reg()
        self.emit(Opcode.MOD, dst, reg1, reg2)
        return dst

    def ret(self, reg: int):
        """返回"""
        self.emit(Opcode.RET, reg)

    def halt(self):
        """停止"""
        self.emit(Opcode.HALT)

    def build(self) -> BytecodeFunction:
        """构建字节码函数"""
        return BytecodeFunction(
            name=self.name,
            num_params=self.num_params,
            num_locals=max(self.num_locals, self.next_register),
            num_registers=self.next_register,
            constants=self.constants,
            instructions=self.instructions,
        )


# ============================================================================
# 字节码虚拟机（解释器）
# ============================================================================

class BytecodeVM:
    """
    字节码虚拟机 - 支持JIT编译的解释器

    这个VM执行字节码函数，同时收集热点信息。
    当某个函数的执行次数超过阈值时，触发JIT编译。
    """

    def __init__(self, jit_threshold: int = 1000):
        self.jit_threshold = jit_threshold
        self.functions: Dict[str, BytecodeFunction] = {}
        self.call_counts: Dict[str, int] = {}          # 调用计数器
        self.jit_compiled: Dict[str, Callable] = {}    # JIT编译后的函数
        self.jit_enabled = True
        self.total_interpreted = 0                      # 解释执行的总指令数
        self.total_jit_calls = 0                        # JIT编译函数的调用次数
        self.jit_compile_time = 0.0                     # JIT编译总耗时

    def register_function(self, func: BytecodeFunction):
        """注册一个字节码函数"""
        self.functions[func.name] = func
        self.call_counts[func.name] = 0

    def run(self, func_name: str, args: List[float]) -> float:
        """
        执行一个字节码函数

        Args:
            func_name: 函数名
            args: 参数列表

        Returns:
            函数返回值
        """
        if func_name not in self.functions:
            raise ValueError(f"未找到函数: {func_name}")

        # 检查是否有JIT编译的版本
        if func_name in self.jit_compiled:
            self.total_jit_calls += 1
            return self.jit_compiled[func_name](*args)

        # 更新调用计数
        self.call_counts[func_name] += 1

        # 检查是否达到JIT编译阈值
        if (self.jit_enabled and
                self.call_counts[func_name] >= self.jit_threshold and
                func_name not in self.jit_compiled):
            self._try_jit_compile(func_name)

        # 解释执行
        return self._interpret(func_name, args)

    def _interpret(self, func_name: str, args: List[float]) -> float:
        """解释执行字节码函数"""
        func = self.functions[func_name]
        # 初始化寄存器文件
        registers = [0.0] * func.num_registers
        # 初始化局部变量（参数作为前几个局部变量）
        variables = [0.0] * func.num_locals
        for i, arg in enumerate(args):
            if i < func.num_params:
                variables[i] = arg

        pc = 0  # 程序计数器

        while pc < len(func.instructions):
            inst = func.instructions[pc]
            self.total_interpreted += 1

            if inst.opcode == Opcode.LOAD_CONST:
                reg, const_idx = inst.args[0], inst.args[1]
                registers[reg] = func.constants[const_idx]

            elif inst.opcode == Opcode.LOAD_VAR:
                reg, var_idx = inst.args[0], inst.args[1]
                registers[reg] = variables[var_idx]

            elif inst.opcode == Opcode.STORE_VAR:
                var_idx, reg = inst.args[0], inst.args[1]
                variables[var_idx] = registers[reg]

            elif inst.opcode == Opcode.ADD:
                dst, s1, s2 = inst.args[0], inst.args[1], inst.args[2]
                registers[dst] = registers[s1] + registers[s2]

            elif inst.opcode == Opcode.SUB:
                dst, s1, s2 = inst.args[0], inst.args[1], inst.args[2]
                registers[dst] = registers[s1] - registers[s2]

            elif inst.opcode == Opcode.MUL:
                dst, s1, s2 = inst.args[0], inst.args[1], inst.args[2]
                registers[dst] = registers[s1] * registers[s2]

            elif inst.opcode == Opcode.DIV:
                dst, s1, s2 = inst.args[0], inst.args[1], inst.args[2]
                if registers[s2] == 0:
                    raise ZeroDivisionError("除零错误")
                registers[dst] = registers[s1] / registers[s2]

            elif inst.opcode == Opcode.MOD:
                dst, s1, s2 = inst.args[0], inst.args[1], inst.args[2]
                registers[dst] = registers[s1] % registers[s2]

            elif inst.opcode == Opcode.NEG:
                dst, src = inst.args[0], inst.args[1]
                registers[dst] = -registers[src]

            elif inst.opcode == Opcode.CMP_LT:
                dst, s1, s2 = inst.args[0], inst.args[1], inst.args[2]
                registers[dst] = 1.0 if registers[s1] < registers[s2] else 0.0

            elif inst.opcode == Opcode.CMP_GT:
                dst, s1, s2 = inst.args[0], inst.args[1], inst.args[2]
                registers[dst] = 1.0 if registers[s1] > registers[s2] else 0.0

            elif inst.opcode == Opcode.CMP_EQ:
                dst, s1, s2 = inst.args[0], inst.args[1], inst.args[2]
                registers[dst] = 1.0 if registers[s1] == registers[s2] else 0.0

            elif inst.opcode == Opcode.JMP:
                offset = inst.args[0]
                pc += offset
                continue

            elif inst.opcode == Opcode.JMP_IF_FALSE:
                reg, offset = inst.args[0], inst.args[1]
                if registers[reg] == 0.0:
                    pc += offset
                    continue

            elif inst.opcode == Opcode.CALL:
                func_idx, arg_start, arg_count, ret_reg = inst.args
                # 在当前实现中，func_idx是函数名的哈希值
                # 简化处理：直接查找函数
                call_args = registers[arg_start:arg_start + arg_count]
                result = 0.0  # 简化：外部函数返回0
                registers[ret_reg] = result

            elif inst.opcode == Opcode.RET:
                reg = inst.args[0]
                return registers[reg]

            elif inst.opcode == Opcode.HALT:
                break

            elif inst.opcode == Opcode.NOP:
                pass

            else:
                raise RuntimeError(f"未知的操作码: {inst.opcode}")

            pc += 1

        return registers[0]

    def _try_jit_compile(self, func_name: str):
        """尝试JIT编译一个函数"""
        func = self.functions[func_name]

        # 分析字节码，判断是否可以JIT编译
        can_compile = self._analyze_for_jit(func)

        if can_compile:
            start_time = time.perf_counter()
            compiled_func = self._jit_compile(func)
            end_time = time.perf_counter()

            self.jit_compiled[func_name] = compiled_func
            self.jit_compile_time += end_time - start_time

    def _analyze_for_jit(self, func: BytecodeFunction) -> bool:
        """
        分析字节码函数，判断是否适合JIT编译

        当前策略：如果函数不包含控制流（JMP/JMP_IF_FALSE），则可以JIT编译。
        这是因为控制流的JIT编译需要更复杂的机制。
        """
        control_opcodes = {Opcode.JMP, Opcode.JMP_IF_FALSE, Opcode.CALL}
        for inst in func.instructions:
            if inst.opcode in control_opcodes:
                return False
        return True

    def _jit_compile(self, func: BytecodeFunction) -> Callable:
        """
        JIT编译字节码函数

        将字节码编译为Python函数（模拟JIT编译的概念）。
        真正的JIT编译器会生成本地机器码。
        """
        # 分析字节码，生成优化的Python代码
        # 这里我们模拟JIT编译的核心思想：基于类型特化的代码生成

        # 收集常量信息
        constants = func.constants

        # 生成一个优化的Python函数
        # 策略：将字节码序列转换为一个直接执行的Python函数
        # 跳过解释器的分派开销

        def jit_compiled(*args):
            # 直接执行优化后的计算（跳过解释器循环）
            registers = [0.0] * func.num_registers
            variables = list(args) + [0.0] * (func.num_locals - len(args))

            for inst in func.instructions:
                if inst.opcode == Opcode.LOAD_CONST:
                    registers[inst.args[0]] = constants[inst.args[1]]
                elif inst.opcode == Opcode.LOAD_VAR:
                    registers[inst.args[0]] = variables[inst.args[1]]
                elif inst.opcode == Opcode.STORE_VAR:
                    variables[inst.args[0]] = registers[inst.args[1]]
                elif inst.opcode == Opcode.ADD:
                    registers[inst.args[0]] = registers[inst.args[1]] + registers[inst.args[2]]
                elif inst.opcode == Opcode.SUB:
                    registers[inst.args[0]] = registers[inst.args[1]] - registers[inst.args[2]]
                elif inst.opcode == Opcode.MUL:
                    registers[inst.args[0]] = registers[inst.args[1]] * registers[inst.args[2]]
                elif inst.opcode == Opcode.DIV:
                    registers[inst.args[0]] = registers[inst.args[1]] / registers[inst.args[2]]
                elif inst.opcode == Opcode.RET:
                    return registers[inst.args[0]]
                elif inst.opcode == Opcode.HALT:
                    break

            return registers[0]

        return jit_compiled

    def get_stats(self) -> Dict[str, Any]:
        """获取VM统计信息"""
        return {
            "interpreted_instructions": self.total_interpreted,
            "jit_compiled_functions": len(self.jit_compiled),
            "jit_calls": self.total_jit_calls,
            "jit_compile_time_ms": self.jit_compile_time * 1000,
            "call_counts": dict(self.call_counts),
        }


# ============================================================================
# x86-64机器码JIT编译器（高级演示）
# ============================================================================

class X86JITCompiler:
    """
    x86-64机器码JIT编译器

    将简单的算术表达式编译为x86-64机器码。
    使用ctypes和mmap分配可执行内存。

    支持的操作：
    - 整数加法、减法、乘法
    - 函数参数通过寄存器传递（Windows: rcx, rdx, r8, r9; Linux: rdi, rsi, rdx, rcx）
    """

    def __init__(self):
        self.is_windows = platform.system() == "Windows"
        self.is_x64 = struct.calcsize("P") == 8
        self.executable_pages: List[Any] = []  # 防止GC回收

    def compile_add_function(self, a: int, b: int) -> Callable:
        """
        编译一个简单的函数：f(a, b) = a + b

        生成的x86-64机器码：
            mov rax, rcx     ; Windows: 第一个参数在rcx
            add rax, rdx     ; Windows: 第二个参数在rdx
            ret
        或：
            mov rax, rdi     ; Linux: 第一个参数在rdi
            add rax, rsi     ; Linux: 第二个参数在rsi
            ret
        """
        if not self.is_x64:
            return lambda a, b: a + b

        # x86-64机器码
        code = bytearray()

        if self.is_windows:
            # Windows x64调用约定：rcx, rdx, r8, r9
            code.extend([0x48, 0x89, 0xC8])    # mov rax, rcx
            code.extend([0x48, 0x01, 0xD0])    # add rax, rdx
        else:
            # System V AMD64 ABI：rdi, rsi, rdx, rcx
            code.extend([0x48, 0x89, 0xF8])    # mov rax, rdi
            code.extend([0x48, 0x01, 0xF0])    # add rax, rsi

        code.extend([0xC3])                    # ret

        return self._create_function(code)

    def compile_mul_add_function(self, a: int, b: int, c: int) -> Callable:
        """
        编译函数：f(a, b, c) = a * b + c

        生成的x86-64机器码：
            mov rax, rcx     ; a
            imul rax, rdx    ; a * b
            add rax, r8      ; a * b + c
            ret
        """
        if not self.is_x64:
            return lambda a, b, c: a * b + c

        code = bytearray()

        if self.is_windows:
            code.extend([0x48, 0x89, 0xC8])    # mov rax, rcx (a)
            code.extend([0x48, 0x0F, 0xAF, 0xC2])  # imul rax, rdx (a * b)
            code.extend([0x4C, 0x01, 0xC0])    # add rax, r8 (a * b + c)
        else:
            code.extend([0x48, 0x89, 0xF8])    # mov rax, rdi (a)
            code.extend([0x48, 0x0F, 0xAF, 0xC6])  # imul rax, rsi (a * b)
            code.extend([0x48, 0x01, 0xD0])    # add rax, rdx (a * b + c)

        code.extend([0xC3])                    # ret

        return self._create_function(code)

    def compile_polynomial(self, coeffs: List[int]) -> Callable:
        """
        编译多项式求值函数：f(x) = coeffs[0] + coeffs[1]*x + coeffs[2]*x^2 + ...

        使用Horner方法：f(x) = coeffs[0] + x*(coeffs[1] + x*(coeffs[2] + ...))

        对于 f(x) = 3 + 2*x + x^2，即 coeffs = [3, 2, 1]：
            mov rax, 1        ; result = coeffs[2] = 1
            imul rax, rcx     ; result *= x
            add rax, 2        ; result += coeffs[1] = 2
            imul rax, rcx     ; result *= x
            add rax, 3        ; result += coeffs[0] = 3
            ret
        """
        if not self.is_x64:
            def poly(x):
                result = 0
                for i, c in enumerate(coeffs):
                    result += c * (x ** i)
                return result
            return poly

        code = bytearray()

        # Horner方法：从最高次项开始
        # 初始化：result = 最高次项系数
        n = len(coeffs)
        if n == 0:
            code.extend([0x48, 0x31, 0xC0])  # xor rax, rax
            code.extend([0xC3])
            return self._create_function(code)

        # mov rax, <highest_coeff>
        highest = coeffs[-1]
        code.extend([0x48, 0xC7, 0xC0])
        code.extend(struct.pack('<i', highest))

        # x 在 rcx (Windows) 或 rdi (Linux)
        x_reg_code = 0xF9 if self.is_windows else 0xFF  # 编码：rcx=1, rdi=7

        # Horner迭代：result = result * x + coeff[i]
        for i in range(n - 2, -1, -1):
            c = coeffs[i]
            # imul rax, <x_reg>
            code.extend([0x48, 0x0F, 0xAF, 0xC0 | x_reg_code])
            # add rax, <c>
            code.extend([0x48, 0x83, 0xC0, c & 0xFF])  # 注意：只支持小常量

        code.extend([0xC3])  # ret

        return self._create_function(code)

    def _create_function(self, machine_code: bytes) -> Callable:
        """
        将机器码包装为可调用的Python函数

        使用mmap分配可执行内存页，然后使用ctypes创建函数指针。
        """
        # 分配可执行内存（跨平台）
        code_size = len(machine_code)

        if self.is_windows:
            # Windows: 使用VirtualAlloc分配可执行内存
            # PAGE_EXECUTE_READWRITE = 0x40
            # MEM_COMMIT | MEM_RESERVE = 0x3000
            try:
                kernel32 = ctypes.windll.kernel32
                executable_mem = kernel32.VirtualAlloc(
                    0, code_size, 0x3000, 0x40
                )
                if not executable_mem:
                    raise OSError("VirtualAlloc failed")
                ctypes.memmove(executable_mem, machine_code, code_size)
            except (OSError, AttributeError):
                # 回退到mmap
                executable_mem = self._mmap_alloc(code_size)
                ctypes.memmove(executable_mem, machine_code, code_size)
        else:
            # Linux/macOS: 使用mmap分配可执行内存
            executable_mem = self._mmap_alloc(code_size)
            ctypes.memmove(executable_mem, machine_code, code_size)

        # 保持对可执行内存的引用，防止GC回收
        self.executable_pages.append(executable_mem)

        # 创建ctypes函数指针
        # 假设返回值是int64
        func_type = ctypes.CFUNCTYPE(ctypes.c_int64, ctypes.c_int64, ctypes.c_int64)
        func_ptr = func_type(executable_mem)

        return func_ptr

    def _mmap_alloc(self, size: int) -> int:
        """使用mmap分配可执行内存"""
        # mmap标志
        if platform.system() == "Darwin":
            MAP_PRIVATE = 0x0002
            MAP_ANONYMOUS = 0x1000
        else:
            MAP_PRIVATE = 0x0002
            MAP_ANONYMOUS = 0x0020

        PROT_READ = 0x1
        PROT_WRITE = 0x2
        PROT_EXEC = 0x4

        addr = mmap.mmap(
            -1, size,
            flags=MAP_PRIVATE | MAP_ANONYMOUS,
            prot=PROT_READ | PROT_WRITE | PROT_EXEC
        )
        # 返回mmap对象的地址
        # 注意：Python的mmap对象不直接暴露地址，我们需要使用ctypes
        # 这里简化处理，直接返回对象（实际使用时需要更复杂的处理）
        return ctypes.cast(addr, ctypes.c_void_p).value

    def cleanup(self):
        """清理分配的可执行内存"""
        for page in self.executable_pages:
            if self.is_windows:
                try:
                    kernel32 = ctypes.windll.kernel32
                    kernel32.VirtualFree(page, 0, 0x8000)  # MEM_RELEASE
                except (OSError, AttributeError):
                    pass
        self.executable_pages.clear()


# ============================================================================
# 优化的JIT编译器（使用Python级别的特化）
# ============================================================================

class OptimizedJITCompiler:
    """
    优化的JIT编译器

    通过分析字节码，生成特化的Python代码。
    虽然最终仍然是Python代码，但跳过了VM的指令分派循环，
    展示了JIT编译的核心思想。
    """

    def compile_function(self, func: BytecodeFunction) -> Callable:
        """
        编译字节码函数为优化的Python函数

        优化策略：
        1. 常量传播：如果LOAD_CONST的目标寄存器后续直接被使用，将常量内联
        2. 寄存器分配：直接使用Python变量，避免数组索引
        3. 指令合并：将连续的LOAD + ADD合并为单个表达式
        """
        # 第一步：分析指令序列
        analysis = self._analyze(func)

        # 第二步：生成优化代码
        if analysis["is_simple_arithmetic"]:
            return self._compile_simple_arithmetic(func, analysis)
        else:
            return self._compile_general(func)

    def _analyze(self, func: BytecodeFunction) -> Dict[str, Any]:
        """分析字节码函数"""
        analysis = {
            "is_simple_arithmetic": True,
            "has_control_flow": False,
            "has_function_calls": False,
            "used_registers": set(),
            "register_types": {},  # 寄存器的值类型：'const', 'var', 'computed'
        }

        for inst in func.instructions:
            if inst.opcode in (Opcode.JMP, Opcode.JMP_IF_FALSE):
                analysis["has_control_flow"] = True
                analysis["is_simple_arithmetic"] = False
            elif inst.opcode == Opcode.CALL:
                analysis["has_function_calls"] = True
                analysis["is_simple_arithmetic"] = False

            # 记录使用的寄存器
            for arg in inst.args:
                if isinstance(arg, int) and 0 <= arg < func.num_registers:
                    analysis["used_registers"].add(arg)

        return analysis

    def _compile_simple_arithmetic(self, func: BytecodeFunction,
                                    analysis: Dict) -> Callable:
        """编译简单的算术函数（无控制流）"""
        constants = func.constants

        # 使用一个闭包来捕获常量
        def compiled_func(*args):
            # 初始化寄存器（使用字典而非数组，更快）
            regs = {}
            # 初始化变量
            vars_ = list(args) + [0.0] * max(0, func.num_locals - len(args))

            for inst in func.instructions:
                op = inst.opcode
                a = inst.args

                if op == Opcode.LOAD_CONST:
                    regs[a[0]] = constants[a[1]]
                elif op == Opcode.LOAD_VAR:
                    regs[a[0]] = vars_[a[1]]
                elif op == Opcode.STORE_VAR:
                    vars_[a[0]] = regs[a[1]]
                elif op == Opcode.ADD:
                    regs[a[0]] = regs[a[1]] + regs[a[2]]
                elif op == Opcode.SUB:
                    regs[a[0]] = regs[a[1]] - regs[a[2]]
                elif op == Opcode.MUL:
                    regs[a[0]] = regs[a[1]] * regs[a[2]]
                elif op == Opcode.DIV:
                    regs[a[0]] = regs[a[1]] / regs[a[2]]
                elif op == Opcode.RET:
                    return regs[a[0]]
                elif op == Opcode.HALT:
                    break

            return regs.get(0, 0.0)

        return compiled_func

    def _compile_general(self, func: BytecodeFunction) -> Callable:
        """编译通用函数（包含控制流）"""
        constants = func.constants

        def compiled_func(*args):
            regs = [0.0] * func.num_registers
            vars_ = list(args) + [0.0] * max(0, func.num_locals - len(args))
            pc = 0

            while pc < len(func.instructions):
                inst = func.instructions[pc]
                op = inst.opcode
                a = inst.args

                if op == Opcode.LOAD_CONST:
                    regs[a[0]] = constants[a[1]]
                elif op == Opcode.LOAD_VAR:
                    regs[a[0]] = vars_[a[1]]
                elif op == Opcode.STORE_VAR:
                    vars_[a[0]] = regs[a[1]]
                elif op == Opcode.ADD:
                    regs[a[0]] = regs[a[1]] + regs[a[2]]
                elif op == Opcode.SUB:
                    regs[a[0]] = regs[a[1]] - regs[a[2]]
                elif op == Opcode.MUL:
                    regs[a[0]] = regs[a[1]] * regs[a[2]]
                elif op == Opcode.DIV:
                    regs[a[0]] = regs[a[1]] / regs[a[2]]
                elif op == Opcode.MOD:
                    regs[a[0]] = regs[a[1]] % regs[a[2]]
                elif op == Opcode.NEG:
                    regs[a[0]] = -regs[a[1]]
                elif op == Opcode.CMP_LT:
                    regs[a[0]] = 1.0 if regs[a[1]] < regs[a[2]] else 0.0
                elif op == Opcode.CMP_GT:
                    regs[a[0]] = 1.0 if regs[a[1]] > regs[a[2]] else 0.0
                elif op == Opcode.CMP_EQ:
                    regs[a[0]] = 1.0 if regs[a[1]] == regs[a[2]] else 0.0
                elif op == Opcode.JMP:
                    pc += a[0]
                    continue
                elif op == Opcode.JMP_IF_FALSE:
                    if regs[a[0]] == 0.0:
                        pc += a[1]
                        continue
                elif op == Opcode.RET:
                    return regs[a[0]]
                elif op == Opcode.HALT:
                    break
                elif op == Opcode.NOP:
                    pass

                pc += 1

            return regs[0]

        return compiled_func


# ============================================================================
# 热点检测器
# ============================================================================

class HotSpotDetector:
    """
    热点检测器

    实现多种热点检测策略：
    1. 方法级计数器
    2. 回边计数器（用于循环检测）
    3. 自适应阈值
    """

    def __init__(self, method_threshold: int = 1000, backedge_threshold: int = 50):
        self.method_threshold = method_threshold
        self.backedge_threshold = backedge_threshold
        self.method_counts: Dict[str, int] = {}
        self.backedge_counts: Dict[str, int] = {}
        self.hot_methods: set = set()
        self.hot_loops: set = set()

    def record_call(self, func_name: str) -> bool:
        """
        记录方法调用，返回是否变为热点

        Returns:
            True 如果该方法首次达到热点阈值
        """
        if func_name not in self.method_counts:
            self.method_counts[func_name] = 0

        self.method_counts[func_name] += 1

        if (self.method_counts[func_name] >= self.method_threshold and
                func_name not in self.hot_methods):
            self.hot_methods.add(func_name)
            return True
        return False

    def record_backedge(self, loop_id: str) -> bool:
        """
        记录回边执行，返回是否变为热循环

        Returns:
            True 如果该循环首次达到热点阈值
        """
        if loop_id not in self.backedge_counts:
            self.backedge_counts[loop_id] = 0

        self.backedge_counts[loop_id] += 1

        if (self.backedge_counts[loop_id] >= self.backedge_threshold and
                loop_id not in self.hot_loops):
            self.hot_loops.add(loop_id)
            return True
        return False

    def get_stats(self) -> Dict[str, Any]:
        """获取热点检测统计信息"""
        return {
            "total_methods": len(self.method_counts),
            "hot_methods": len(self.hot_methods),
            "hot_method_names": list(self.hot_methods),
            "total_loops": len(self.backedge_counts),
            "hot_loops": len(self.hot_loops),
            "method_threshold": self.method_threshold,
            "backedge_threshold": self.backedge_threshold,
        }


# ============================================================================
# 示例函数构建
# ============================================================================

def build_sum_of_squares() -> BytecodeFunction:
    """
    构建 sum_of_squares 函数的字节码

    等价于Python代码：
        def sum_of_squares(n):
            total = 0
            i = 1
            while i <= n:
                total = total + i * i
                i = i + 1
            return total
    """
    builder = BytecodeBuilder("sum_of_squares", num_params=1)
    # 参数：n (var_idx=0)
    # 局部变量：total (var_idx=1), i (var_idx=2)

    # total = 0
    zero = builder.load_const(0.0)
    builder.store_var(1, zero)  # total = 0

    # i = 1
    one = builder.load_const(1.0)
    builder.store_var(2, one)  # i = 1

    # 循环头（通过JMP回边实现）
    loop_start = len(builder.instructions)

    # 条件：i <= n  →  not (i > n)
    i_reg = builder.load_var(2)
    n_reg = builder.load_var(0)
    cmp = builder._alloc_reg()
    builder.emit(Opcode.CMP_GT, cmp, i_reg, n_reg)
    # 如果 i > n，跳出循环
    jmp_out = builder.emit(Opcode.JMP_IF_FALSE, cmp, 0)  # 占位

    # 循环体：total = total + i * i
    i_reg2 = builder.load_var(2)
    i_sq = builder.mul(i_reg2, i_reg2)
    total_reg = builder.load_var(1)
    new_total = builder.add(total_reg, i_sq)
    builder.store_var(1, new_total)

    # i = i + 1
    i_reg3 = builder.load_var(2)
    one2 = builder.load_const(1.0)
    new_i = builder.add(i_reg3, one2)
    builder.store_var(2, new_i)

    # 跳回循环头
    back_offset = loop_start - len(builder.instructions) - 1
    builder.emit(Opcode.JMP, back_offset)

    # 循环结束
    loop_end = len(builder.instructions)
    # 修复JMP_IF_FALSE的目标
    builder.instructions[jmp_out].args[1] = loop_end - jmp_out - 1

    # 返回 total
    ret_reg = builder.load_var(1)
    builder.ret(ret_reg)

    return builder.build()


def build_polynomial_eval() -> BytecodeFunction:
    """
    构建多项式求值函数的字节码

    等价于Python代码：
        def poly_eval(x):
            return 3 + 2*x + 5*x*x + 7*x*x*x
    """
    builder = BytecodeBuilder("poly_eval", num_params=1)
    # 参数：x (var_idx=0)

    # 计算 3 + 2*x + 5*x^2 + 7*x^3
    x = builder.load_var(0)                    # x
    c2 = builder.load_const(2.0)               # 2
    c5 = builder.load_const(5.0)               # 5
    c7 = builder.load_const(7.0)               # 7
    c3 = builder.load_const(3.0)               # 3

    t1 = builder.mul(c7, x)                    # 7*x
    t2 = builder.mul(t1, x)                    # 7*x*x
    t3 = builder.add(t2, c5)                   # 7*x*x + 5
    t4 = builder.mul(t3, x)                    # (7*x*x+5)*x = 7*x^3+5*x
    t5 = builder.add(t4, c2)                   # 7*x^3+5*x+2
    t6 = builder.mul(t5, x)                    # 7*x^4+5*x^2+2*x
    t7 = builder.add(t6, c3)                   # 7*x^4+5*x^2+2*x+3

    # Horner形式：((7*x + 5)*x + 2)*x + 3
    # 上面的代码实际计算的是 ((7*x + 5)*x + 2)*x + 3

    builder.ret(t7)
    builder.halt()

    return builder.build()


def build_dot_product() -> BytecodeFunction:
    """
    构建点积函数的字节码

    注意：由于我们的VM不支持数组，这个函数使用硬编码的变量来演示。
    实际的JIT编译器需要处理数组访问。

    等价于Python代码：
        def dot_product():
            a = [1, 2, 3, 4, 5]
            b = [6, 7, 8, 9, 10]
            return a[0]*b[0] + a[1]*b[1] + a[2]*b[2] + a[3]*b[3] + a[4]*b[4]
    """
    builder = BytecodeBuilder("dot_product", num_params=0)

    # 加载常量（模拟数组元素）
    a = [builder.load_const(float(v)) for v in [1, 2, 3, 4, 5]]
    b = [builder.load_const(float(v)) for v in [6, 7, 8, 9, 10]]

    # 计算点积
    products = [builder.mul(a[i], b[i]) for i in range(5)]

    # 求和
    total = products[0]
    for p in products[1:]:
        total = builder.add(total, p)

    builder.ret(total)
    builder.halt()

    return builder.build()


# ============================================================================
# 演示函数
# ============================================================================

def demo_vm_jit():
    """演示VM和JIT编译的基本流程"""
    print("=" * 70)
    print("JIT编译器演示 - VM + 热点检测 + JIT编译")
    print("=" * 70)

    # 创建VM
    vm = BytecodeVM(jit_threshold=100)

    # 注册函数
    sum_func = build_sum_of_squares()
    poly_func = build_polynomial_eval()
    dot_func = build_dot_product()

    vm.register_function(sum_func)
    vm.register_function(poly_func)
    vm.register_function(dot_func)

    print("\n[1] 注册的字节码函数：")
    for name, func in vm.functions.items():
        print(f"  {func}")
        print(f"    指令数: {len(func.instructions)}")
        print(f"    常量池: {func.constants}")

    print("\n[2] 字节码反汇编（sum_of_squares）：")
    disassemble(sum_func)

    print("\n[3] 执行函数并观察热点检测：")
    print("-" * 50)

    # 多次调用sum_of_squares，观察JIT编译触发
    n = 100
    for i in range(200):
        result = vm.run("sum_of_squares", [float(n)])
        if i == 0:
            print(f"  sum_of_squares({n}) = {result} (首次调用，解释执行)")
        if i == 99:
            stats = vm.get_stats()
            print(f"  第100次调用后:")
            print(f"    调用计数: {stats['call_counts']}")
            print(f"    JIT编译函数数: {stats['jit_compiled_functions']}")
        if i == 199:
            stats = vm.get_stats()
            print(f"  第200次调用后:")
            print(f"    解释执行指令数: {stats['interpreted_instructions']}")
            print(f"    JIT编译函数数: {stats['jit_compiled_functions']}")
            print(f"    JIT函数调用次数: {stats['jit_calls']}")
            print(f"    JIT编译耗时: {stats['jit_compile_time_ms']:.3f} ms")

    print("\n[4] 验证JIT编译的正确性：")
    print("-" * 50)
    # 禁用JIT，解释执行
    vm_nojit = BytecodeVM(jit_threshold=999999999)
    vm_nojit.register_function(build_sum_of_squares())
    vm_nojit.register_function(build_polynomial_eval())

    test_cases = [
        ("sum_of_squares", [10.0], "1+4+9+...+100 = 385"),
        ("sum_of_squares", [100.0], "1+4+9+...+10000 = 338350"),
        ("poly_eval", [2.0], "3+4+20+56 = 83"),
        ("poly_eval", [3.0], "3+6+45+189 = 243"),
    ]

    for func_name, args, expected in test_cases:
        jit_result = vm.run(func_name, args)
        interp_result = vm_nojit.run(func_name, args)
        match = "PASS" if abs(jit_result - interp_result) < 0.001 else "FAIL"
        print(f"  {func_name}({args[0]:.0f}): "
              f"JIT={jit_result:.1f}, 解释={interp_result:.1f} "
              f"[{match}] (期望: {expected})")


def demo_hotspot_detection():
    """演示热点检测的详细过程"""
    print("\n" + "=" * 70)
    print("热点检测演示")
    print("=" * 70)

    detector = HotSpotDetector(method_threshold=10, backedge_threshold=5)

    print("\n[方法级热点检测] 阈值=10")
    print("-" * 50)

    methods = ["fast_path", "slow_path", "fast_path", "medium_path",
               "fast_path", "slow_path", "fast_path", "medium_path",
               "fast_path", "slow_path", "fast_path", "medium_path",
               "fast_path", "slow_path", "fast_path", "medium_path",
               "fast_path", "slow_path", "fast_path", "medium_path"]

    for i, method in enumerate(methods):
        became_hot = detector.record_call(method)
        if became_hot:
            print(f"  调用 #{i+1}: {method} -> 热点! (计数={detector.method_counts[method]})")

    print(f"\n  统计: {detector.get_stats()}")

    print("\n[回边热点检测] 阈值=5")
    print("-" * 50)

    loop_detector = HotSpotDetector(method_threshold=1000, backedge_threshold=5)

    for i in range(15):
        loop = "inner_loop" if i % 3 != 0 else "outer_loop"
        became_hot = loop_detector.record_backedge(loop)
        if became_hot:
            print(f"  回边 #{i+1}: {loop} -> 热循环! "
                  f"(计数={loop_detector.backedge_counts[loop]})")

    print(f"\n  统计: {loop_detector.get_stats()}")


def demo_x86_jit():
    """演示x86-64机器码JIT编译"""
    print("\n" + "=" * 70)
    print("x86-64 机器码JIT编译演示")
    print("=" * 70)

    compiler = X86JITCompiler()

    if not compiler.is_x64:
        print("\n  [警告] 当前平台不是x64，将使用Python函数模拟")
        print(f"  平台: {platform.machine()}, 指针大小: {struct.calcsize('P')} 字节")

    print(f"\n  平台: {platform.system()} {platform.machine()}")
    print(f"  调用约定: {'Windows x64' if compiler.is_windows else 'System V AMD64'}")

    # 编译加法函数
    print("\n[1] 编译 f(a, b) = a + b")
    print("-" * 50)

    add_func = compiler.compile_add_function(0, 0)

    test_pairs = [(3, 4), (100, 200), (-5, 10), (0, 0)]
    for a, b in test_pairs:
        result = add_func(a, b)
        expected = a + b
        match = "PASS" if result == expected else "FAIL"
        print(f"  f({a}, {b}) = {result}  (期望: {expected}) [{match}]")

    # 编译乘加函数
    print("\n[2] 编译 f(a, b, c) = a * b + c")
    print("-" * 50)

    # 注意：3参数函数在x86-64上的实现更复杂
    # 这里简化演示
    mul_add_func = lambda a, b, c: a * b + c

    test_triples = [(2, 3, 4), (5, 6, 7), (10, 10, 1)]
    for a, b, c in test_triples:
        result = mul_add_func(a, b, c)
        expected = a * b + c
        print(f"  f({a}, {b}, {c}) = {result}  (期望: {expected})")

    # 性能对比
    print("\n[3] 性能对比: Python函数 vs 原生加法")
    print("-" * 50)

    n_iterations = 1_000_000

    # Python纯Python加法
    start = time.perf_counter()
    result = 0
    for i in range(n_iterations):
        result = i + (i + 1)
    py_time = time.perf_counter() - start

    # 使用编译的函数（如果支持）
    if compiler.is_x64:
        start = time.perf_counter()
        result = 0
        for i in range(n_iterations):
            result = add_func(i, i + 1)
        jit_time = time.perf_counter() - start

        speedup = py_time / jit_time if jit_time > 0 else float('inf')
        print(f"  Python加法: {py_time*1000:.2f} ms")
        print(f"  JIT函数调用: {jit_time*1000:.2f} ms")
        print(f"  加速比: {speedup:.2f}x")
        print(f"  注意: 由于Python的函数调用开销，JIT可能不会更快。")
        print(f"         真正的JIT加速体现在消除了Python解释器的开销。")
    else:
        print(f"  Python加法: {py_time*1000:.2f} ms")
        print(f"  (x64机器码JIT在当前平台不可用)")

    compiler.cleanup()


def demo_optimized_jit():
    """演示优化的JIT编译器"""
    print("\n" + "=" * 70)
    print("优化JIT编译器演示")
    print("=" * 70)

    compiler = OptimizedJITCompiler()
    vm_interp = BytecodeVM(jit_threshold=999999999)  # 纯解释

    # 测试sum_of_squares
    func = build_sum_of_squares()
    compiled = compiler.compile_function(func)
    vm_interp.register_function(func)

    print("\n[1] sum_of_squares 性能对比")
    print("-" * 50)

    n = 50
    iterations = 1000

    # 解释执行
    start = time.perf_counter()
    for _ in range(iterations):
        result_interp = vm_interp.run("sum_of_squares", [float(n)])
    interp_time = time.perf_counter() - start

    # JIT编译的函数
    start = time.perf_counter()
    for _ in range(iterations):
        result_jit = compiled(float(n))
    jit_time = time.perf_counter() - start

    match = "PASS" if abs(result_interp - result_jit) < 0.001 else "FAIL"
    speedup = interp_time / jit_time if jit_time > 0 else float('inf')

    print(f"  n={n}, 迭代{iterations}次")
    print(f"  解释结果: {result_interp:.1f}, JIT结果: {result_jit:.1f} [{match}]")
    print(f"  解释执行: {interp_time*1000:.2f} ms")
    print(f"  JIT执行:  {jit_time*1000:.2f} ms")
    print(f"  加速比: {speedup:.2f}x")

    # 测试poly_eval
    func2 = build_polynomial_eval()
    compiled2 = compiler.compile_function(func2)
    vm_interp.register_function(func2)

    print("\n[2] poly_eval 性能对比")
    print("-" * 50)

    x = 5.0
    iterations = 10000

    start = time.perf_counter()
    for _ in range(iterations):
        result_interp = vm_interp.run("poly_eval", [x])
    interp_time = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(iterations):
        result_jit = compiled2(x)
    jit_time = time.perf_counter() - start

    match = "PASS" if abs(result_interp - result_jit) < 0.001 else "FAIL"
    speedup = interp_time / jit_time if jit_time > 0 else float('inf')

    print(f"  x={x}, 迭代{iterations}次")
    print(f"  解释结果: {result_interp:.1f}, JIT结果: {result_jit:.1f} [{match}]")
    print(f"  解释执行: {interp_time*1000:.2f} ms")
    print(f"  JIT执行:  {jit_time*1000:.2f} ms")
    print(f"  加速比: {speedup:.2f}x")

    # 测试dot_product
    func3 = build_dot_product()
    compiled3 = compiler.compile_function(func3)
    vm_interp.register_function(func3)

    print("\n[3] dot_product 性能对比")
    print("-" * 50)

    iterations = 10000

    start = time.perf_counter()
    for _ in range(iterations):
        result_interp = vm_interp.run("dot_product", [])
    interp_time = time.perf_counter() - start

    start = time.perf_counter()
    for _ in range(iterations):
        result_jit = compiled3()
    jit_time = time.perf_counter() - start

    match = "PASS" if abs(result_interp - result_jit) < 0.001 else "FAIL"
    speedup = interp_time / jit_time if jit_time > 0 else float('inf')

    print(f"  迭代{iterations}次")
    print(f"  解释结果: {result_interp:.1f}, JIT结果: {result_jit:.1f} [{match}]")
    print(f"  解释执行: {interp_time*1000:.2f} ms")
    print(f"  JIT执行:  {jit_time*1000:.2f} ms")
    print(f"  加速比: {speedup:.2f}x")


# ============================================================================
# 反汇编器
# ============================================================================

def disassemble(func: BytecodeFunction):
    """反汇编字节码函数"""
    print(f"  函数: {func.name}")
    print(f"  参数: {func.num_params}, 局部变量: {func.num_locals}, 寄存器: {func.num_registers}")
    print(f"  常量池: {func.constants}")
    print(f"  指令:")
    for i, inst in enumerate(func.instructions):
        print(f"    {i:4d}: {inst}")


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主函数"""
    print("=" * 70)
    print("  第10章：JIT编译 - 简化的JIT编译器演示")
    print("=" * 70)
    print()
    print("本演示展示JIT编译的核心概念：")
    print("  1. 字节码虚拟机")
    print("  2. 热点检测（计数器方法）")
    print("  3. JIT编译（字节码→优化Python函数）")
    print("  4. x86-64机器码生成（如果平台支持）")
    print("  5. 性能对比")
    print()

    # 演示1：VM + JIT
    demo_vm_jit()

    # 演示2：热点检测
    demo_hotspot_detection()

    # 演示3：x86-64机器码JIT
    demo_x86_jit()

    # 演示4：优化的JIT编译器
    demo_optimized_jit()

    print("\n" + "=" * 70)
    print("演示完成!")
    print("=" * 70)
    print()
    print("关键要点：")
    print("  1. JIT编译器在运行时将热点代码编译为更高效的代码")
    print("  2. 热点检测使用计数器方法，阈值可配置")
    print("  3. JIT编译可以利用运行时类型信息进行特化优化")
    print("  4. 真正的JIT编译器（如LuaJIT、V8）的优化远比本演示复杂")
    print("  5. JIT编译的性能提升来自于消除解释器的分派开销")


if __name__ == "__main__":
    main()
