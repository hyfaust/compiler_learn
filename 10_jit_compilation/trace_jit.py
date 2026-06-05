#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
trace_jit.py - 追踪JIT编译演示

本模块演示追踪级JIT编译的核心概念：
1. 追踪录制（Trace Recording）- 记录循环的实际执行路径
2. 追踪优化（Trace Optimization）- 常量折叠、死代码消除、强度削减
3. 追踪编译（Trace Compilation）- 将优化后的追踪编译为可执行函数
4. 追踪链接（Trace Linking）- 将多个追踪链接起来
5. 性能对比 - 解释执行 vs 追踪JIT执行

追踪JIT的核心思想（以LuaJIT为代表）：
- 只对热循环进行编译
- 录制循环的单一执行路径（线性化）
- 利用线性代码的特性进行高效优化
- 通过守卫（Guard）处理分支

运行方式：
    python trace_jit.py
"""

import time
import dis
from typing import List, Dict, Any, Optional, Callable, Tuple, Set
from dataclasses import dataclass, field
from enum import Enum, auto
from collections import defaultdict


# ============================================================================
# 追踪JIT的IR（中间表示）
# ============================================================================

class IROpcode(Enum):
    """追踪IR的操作码"""
    # 算术操作
    ADD = auto()         # dst = src1 + src2
    SUB = auto()         # dst = src1 - src2
    MUL = auto()         # dst = src1 * src2
    DIV = auto()         # dst = src1 / src2
    MOD = auto()         # dst = src1 % src2
    NEG = auto()         # dst = -src

    # 常量操作
    CONST = auto()       # dst = value

    # 变量操作
    LOAD = auto()        # dst = memory[var_name]
    STORE = auto()       # memory[var_name] = src

    # 比较操作
    CMP_LT = auto()      # dst = (src1 < src2)
    CMP_GT = auto()      # dst = (src1 > src2)
    CMP_EQ = auto()      # dst = (src1 == src2)
    CMP_LE = auto()      # dst = (src1 <= src2)

    # 守卫（Guard）- 如果条件不满足，退出追踪
    GUARD_TRUE = auto()  # guard(src); 如果src==0，退出追踪
    GUARD_FALSE = auto() # guard(!src); 如果src!=0，退出追踪

    # 控制流
    LOOP_START = auto()  # 循环起点标记
    LOOP_END = auto()    # 循环终点标记（回边）

    # 特殊操作
    PHI = auto()         # dst = phi(src1, src2) - 循环变量的合并
    CALL = auto()        # dst = call(func, args...)
    NOP = auto()         # 空操作（标记为已删除）


@dataclass
class IRNode:
    """追踪IR节点"""
    opcode: IROpcode
    dst: Optional[int] = None       # 目标操作数（虚拟寄存器编号）
    src1: Optional[int] = None      # 源操作数1
    src2: Optional[int] = None      # 源操作数2
    value: Optional[float] = None   # 常量值
    var_name: Optional[str] = None  # 变量名（用于LOAD/STORE）
    label: Optional[str] = None     # 标签
    dead: bool = False              # 是否被DCE标记为死代码
    folded: bool = False            # 是否被常量折叠
    cse_merged: bool = False        # 是否被CSE合并
    line_no: int = 0                # 源代码行号

    def __repr__(self):
        parts = [f"[{self.opcode.name}]"]
        if self.dst is not None:
            parts.append(f"r{self.dst}")
        if self.src1 is not None:
            parts.append(f"r{self.src1}")
        if self.src2 is not None:
            parts.append(f"r{self.src2}")
        if self.value is not None:
            parts.append(f"={self.value}")
        if self.var_name is not None:
            parts.append(f"var:{self.var_name}")
        if self.dead:
            parts.append("(DEAD)")
        if self.folded:
            parts.append("(FOLDED)")
        if self.cse_merged:
            parts.append("(CSE)")
        return " ".join(parts)


@dataclass
class Trace:
    """追踪"""
    name: str
    nodes: List[IRNode] = field(default_factory=list)
    loop_start: int = 0            # 循环起始节点索引
    snapshot_vars: Dict[str, float] = field(default_factory=dict)
    compiled_func: Optional[Callable] = None
    linked_traces: Dict[int, 'Trace'] = field(default_factory=dict)
    side_traces: List['Trace'] = field(default_factory=list)
    execution_count: int = 0       # 执行次数
    guard_failures: Dict[int, int] = field(default_factory=lambda: defaultdict(int))


class Snapshot:
    """快照 - 记录追踪退出时的解释器状态"""
    def __init__(self, bytecode_pc: int, variables: Dict[str, float],
                 registers: Dict[int, float]):
        self.bytecode_pc = bytecode_pc
        self.variables = dict(variables)
        self.registers = dict(registers)

    def __repr__(self):
        return (f"Snapshot(pc={self.bytecode_pc}, "
                f"vars={self.variables}, regs={self.registers})")


# ============================================================================
# 追踪录制器
# ============================================================================

class TraceRecorder:
    """
    追踪录制器

    模拟LuaJIT的追踪录制过程：
    1. 从循环头开始录制
    2. 沿实际执行路径记录IR节点
    3. 在分支处插入守卫
    4. 回到循环头时完成录制
    """

    def __init__(self):
        self.next_register = 0
        self.current_trace: Optional[Trace] = None
        self.is_recording = False
        self.recorded_traces: List[Trace] = []
        self.snapshots: Dict[int, Snapshot] = {}  # 守卫位置 -> 快照

    def _alloc_reg(self) -> int:
        """分配虚拟寄存器"""
        reg = self.next_register
        self.next_register += 1
        return reg

    def start_recording(self, trace_name: str = "trace_0"):
        """开始录制追踪"""
        self.current_trace = Trace(name=trace_name)
        self.is_recording = True
        self.next_register = 0
        self._loop_start_emitted = False
        self._loop_end_emitted = False
        print(f"  [录制开始] 追踪: {trace_name}")

    def mark_loop_start(self):
        """标记循环起点（在初始化代码之后调用）"""
        if self.current_trace is not None:
            self.current_trace.nodes.append(
                IRNode(IROpcode.LOOP_START, label="loop_start"))
            self._loop_start_emitted = True

    def mark_loop_end(self):
        """标记循环终点"""
        if self.current_trace is not None:
            self.current_trace.nodes.append(
                IRNode(IROpcode.LOOP_END, label="loop_end"))
            self._loop_end_emitted = True

    def emit(self, opcode: IROpcode, **kwargs) -> int:
        """发射一个IR节点"""
        if not self.is_recording or self.current_trace is None:
            raise RuntimeError("未在录制状态")

        node = IRNode(opcode=opcode, **kwargs)
        node.line_no = len(self.current_trace.nodes)
        self.current_trace.nodes.append(node)
        return len(self.current_trace.nodes) - 1

    def record_const(self, value: float) -> int:
        """录制常量加载"""
        dst = self._alloc_reg()
        self.emit(IROpcode.CONST, dst=dst, value=value)
        return dst

    def record_load(self, var_name: str) -> int:
        """录制变量加载"""
        dst = self._alloc_reg()
        self.emit(IROpcode.LOAD, dst=dst, var_name=var_name)
        return dst

    def record_store(self, var_name: str, src: int):
        """录制变量存储"""
        self.emit(IROpcode.STORE, src1=src, var_name=var_name)

    def record_add(self, src1: int, src2: int) -> int:
        """录制加法"""
        dst = self._alloc_reg()
        self.emit(IROpcode.ADD, dst=dst, src1=src1, src2=src2)
        return dst

    def record_sub(self, src1: int, src2: int) -> int:
        """录制减法"""
        dst = self._alloc_reg()
        self.emit(IROpcode.SUB, dst=dst, src1=src1, src2=src2)
        return dst

    def record_mul(self, src1: int, src2: int) -> int:
        """录制乘法"""
        dst = self._alloc_reg()
        self.emit(IROpcode.MUL, dst=dst, src1=src1, src2=src2)
        return dst

    def record_div(self, src1: int, src2: int) -> int:
        """录制除法"""
        dst = self._alloc_reg()
        self.emit(IROpcode.DIV, dst=dst, src1=src1, src2=src2)
        return dst

    def record_cmp_lt(self, src1: int, src2: int) -> int:
        """录制小于比较"""
        dst = self._alloc_reg()
        self.emit(IROpcode.CMP_LT, dst=dst, src1=src1, src2=src2)
        return dst

    def record_cmp_le(self, src1: int, src2: int) -> int:
        """录制小于等于比较"""
        dst = self._alloc_reg()
        self.emit(IROpcode.CMP_LE, dst=dst, src1=src1, src2=src2)
        return dst

    def record_guard_true(self, src: int, bytecode_pc: int,
                          variables: Dict[str, float]):
        """录制守卫（条件为真）"""
        # 保存快照
        snapshot = Snapshot(bytecode_pc, variables, {})
        self.snapshots[len(self.current_trace.nodes)] = snapshot
        self.emit(IROpcode.GUARD_TRUE, src1=src)

    def record_guard_false(self, src: int, bytecode_pc: int,
                           variables: Dict[str, float]):
        """录制守卫（条件为假）"""
        snapshot = Snapshot(bytecode_pc, variables, {})
        self.snapshots[len(self.current_trace.nodes)] = snapshot
        self.emit(IROpcode.GUARD_FALSE, src1=src)

    def finish_recording(self) -> Trace:
        """完成追踪录制"""
        if not self.is_recording or self.current_trace is None:
            raise RuntimeError("未在录制状态")

        # 添加循环终点标记（如果尚未添加）
        if not self._loop_end_emitted:
            self.mark_loop_end()

        self.is_recording = False
        trace = self.current_trace
        self.current_trace = None
        self.recorded_traces.append(trace)

        print(f"  [录制完成] 追踪: {trace.name}, IR节点数: {len(trace.nodes)}")
        return trace


# ============================================================================
# 追踪优化器
# ============================================================================

class TraceOptimizer:
    """
    追踪优化器

    实现追踪JIT中的核心优化：
    1. 常量折叠（Constant Folding）
    2. 死代码消除（Dead Code Elimination, DCE）
    3. 公共子表达式消除（Common Subexpression Elimination, CSE）
    4. 强度削减（Strength Reduction）
    5. 类型特化（Type Specialization）
    """

    def __init__(self):
        self.stats = {
            "constants_folded": 0,
            "dead_code_eliminated": 0,
            "cse_merged": 0,
            "strength_reduced": 0,
        }

    def optimize(self, trace: Trace) -> Trace:
        """
        对追踪进行多轮优化

        优化顺序：
        1. 常量折叠（第一轮）
        2. 死代码消除
        3. 公共子表达式消除
        4. 常量折叠（第二轮，处理CSE暴露的新机会）
        5. 强度削减
        """
        print(f"\n  [优化] 开始优化追踪: {trace.name}")

        # 打印优化前的IR
        self._print_ir(trace, "优化前")

        # 第一轮：常量折叠
        self._constant_folding(trace)
        self._print_ir(trace, "常量折叠后")

        # 死代码消除
        self._dead_code_elimination(trace)
        self._print_ir(trace, "死代码消除后")

        # 公共子表达式消除
        self._common_subexpression_elimination(trace)
        self._print_ir(trace, "CSE后")

        # 第二轮常量折叠
        self._constant_folding(trace)

        # 强度削减
        self._strength_reduction(trace)
        self._print_ir(trace, "最终优化结果")

        print(f"\n  [优化统计]")
        for key, value in self.stats.items():
            print(f"    {key}: {value}")

        return trace

    def _constant_folding(self, trace: Trace):
        """
        常量折叠

        如果一个操作的所有输入都是常量，直接计算结果。
        例如：CONST 3 + CONST 4 → CONST 7
        """
        # 构建值映射：寄存器 -> 常量值（如果已知）
        const_map: Dict[int, float] = {}

        for node in trace.nodes:
            if node.dead:
                continue

            if node.opcode == IROpcode.CONST:
                const_map[node.dst] = node.value
                continue

            # 尝试折叠算术操作
            if node.opcode in (IROpcode.ADD, IROpcode.SUB, IROpcode.MUL,
                               IROpcode.DIV, IROpcode.MOD):
                val1 = const_map.get(node.src1)
                val2 = const_map.get(node.src2)

                if val1 is not None and val2 is not None:
                    # 两个操作数都是常量，可以折叠
                    result = self._eval_arith(node.opcode, val1, val2)
                    if result is not None:
                        # 将操作替换为常量加载
                        node.opcode = IROpcode.CONST
                        node.value = result
                        node.src1 = None
                        node.src2 = None
                        node.folded = True
                        const_map[node.dst] = result
                        self.stats["constants_folded"] += 1
                        continue

            # 处理比较操作
            if node.opcode in (IROpcode.CMP_LT, IROpcode.CMP_GT,
                               IROpcode.CMP_EQ, IROpcode.CMP_LE):
                val1 = const_map.get(node.src1)
                val2 = const_map.get(node.src2)

                if val1 is not None and val2 is not None:
                    result = self._eval_cmp(node.opcode, val1, val2)
                    if result is not None:
                        node.opcode = IROpcode.CONST
                        node.value = 1.0 if result else 0.0
                        node.src1 = None
                        node.src2 = None
                        node.folded = True
                        const_map[node.dst] = node.value
                        self.stats["constants_folded"] += 1
                        continue

            # 更新常量映射（LOAD操作可能加载已知的常量变量）
            if node.opcode == IROpcode.LOAD and node.var_name in const_map:
                const_map[node.dst] = const_map[node.var_name]

    def _dead_code_elimination(self, trace: Trace):
        """
        死代码消除

        标记所有未被使用的计算为死代码。
        注意：LOAD/STORE操作有副作用，不能删除。
        GUARD操作也有副作用，不能删除。
        """
        # 第一步：标记所有被使用的寄存器
        used_registers: Set[int] = set()

        for node in trace.nodes:
            if node.dead:
                continue
            # 源操作数被使用
            if node.src1 is not None:
                used_registers.add(node.src1)
            if node.src2 is not None:
                used_registers.add(node.src2)
            # STORE操作的src1被使用
            if node.opcode == IROpcode.STORE and node.src1 is not None:
                used_registers.add(node.src1)
            # GUARD操作的操作数被使用
            if node.opcode in (IROpcode.GUARD_TRUE, IROpcode.GUARD_FALSE):
                if node.src1 is not None:
                    used_registers.add(node.src1)

        # 第二步：标记未使用的计算节点为死代码
        # 注意：LOAD、STORE、GUARD、LOOP_START、LOOP_END、CONST不能删除
        side_effect_ops = {IROpcode.LOAD, IROpcode.STORE, IROpcode.GUARD_TRUE,
                          IROpcode.GUARD_FALSE, IROpcode.LOOP_START,
                          IROpcode.LOOP_END, IROpcode.CALL}

        for node in trace.nodes:
            if node.dead:
                continue
            if node.opcode in side_effect_ops:
                continue
            if node.dst is not None and node.dst not in used_registers:
                node.dead = True
                self.stats["dead_code_eliminated"] += 1

    def _common_subexpression_elimination(self, trace: Trace):
        """
        公共子表达式消除

        如果两个操作的opcode和操作数相同，它们计算的是同一个值。
        只需要计算一次，后续使用缓存的结果。
        """
        # 表达式签名 -> 结果寄存器
        expr_map: Dict[Tuple, int] = {}

        for node in trace.nodes:
            if node.dead:
                continue

            if node.opcode in (IROpcode.ADD, IROpcode.SUB, IROpcode.MUL,
                               IROpcode.DIV, IROpcode.MOD):
                # 构建表达式签名
                # 对于ADD和MUL，操作数顺序不影响结果
                if node.opcode in (IROpcode.ADD, IROpcode.MUL):
                    sig = (node.opcode, min(node.src1, node.src2),
                           max(node.src1, node.src2))
                else:
                    sig = (node.opcode, node.src1, node.src2)

                if sig in expr_map:
                    # 找到重复的表达式
                    existing_reg = expr_map[sig]
                    # 将当前节点替换为NOP，dst映射到existing_reg
                    # 后续使用dst的地方需要替换为existing_reg
                    node.cse_merged = True
                    node.dead = True
                    # 更新后续节点中的dst引用
                    self._replace_register(trace, node.dst, existing_reg,
                                           start_from=len(trace.nodes) - 1)
                    self.stats["cse_merged"] += 1
                else:
                    expr_map[sig] = node.dst

            elif node.opcode == IROpcode.CONST:
                # 常量也可以CSE
                sig = ("CONST", node.value)
                if sig in expr_map:
                    existing_reg = expr_map[sig]
                    node.cse_merged = True
                    node.dead = True
                    self._replace_register(trace, node.dst, existing_reg,
                                           start_from=len(trace.nodes) - 1)
                    self.stats["cse_merged"] += 1
                else:
                    expr_map[sig] = node.dst

    def _strength_reduction(self, trace: Trace):
        """
        强度削减

        将昂贵的操作替换为更便宜的操作：
        - x * 2 → x + x
        - x * 2^n → x << n
        - x / 2^n → x >> n
        - x * 0 → 0
        - x + 0 → x
        - x * 1 → x
        - x - 0 → x
        """
        # 构建值映射
        const_map: Dict[int, float] = {}

        for node in trace.nodes:
            if node.dead:
                continue

            # 更新常量映射
            if node.opcode == IROpcode.CONST:
                const_map[node.dst] = node.value
                continue

            if node.opcode == IROpcode.ADD:
                val1 = const_map.get(node.src1)
                val2 = const_map.get(node.src2)

                # x + 0 → x
                if val2 == 0.0:
                    node.opcode = IROpcode.CONST
                    # 将dst映射到src1
                    self._replace_register(trace, node.dst, node.src1,
                                           start_from=len(trace.nodes) - 1)
                    node.dead = True
                    self.stats["strength_reduced"] += 1
                elif val1 == 0.0:
                    self._replace_register(trace, node.dst, node.src2,
                                           start_from=len(trace.nodes) - 1)
                    node.dead = True
                    self.stats["strength_reduced"] += 1

            elif node.opcode == IROpcode.MUL:
                val1 = const_map.get(node.src1)
                val2 = const_map.get(node.src2)

                # x * 0 → 0
                if val1 == 0.0 or val2 == 0.0:
                    node.opcode = IROpcode.CONST
                    node.value = 0.0
                    node.src1 = None
                    node.src2 = None
                    self.stats["strength_reduced"] += 1
                # x * 1 → x
                elif val2 == 1.0:
                    self._replace_register(trace, node.dst, node.src1,
                                           start_from=len(trace.nodes) - 1)
                    node.dead = True
                    self.stats["strength_reduced"] += 1
                elif val1 == 1.0:
                    self._replace_register(trace, node.dst, node.src2,
                                           start_from=len(trace.nodes) - 1)
                    node.dead = True
                    self.stats["strength_reduced"] += 1

            elif node.opcode == IROpcode.SUB:
                val2 = const_map.get(node.src2)

                # x - 0 → x
                if val2 == 0.0:
                    self._replace_register(trace, node.dst, node.src1,
                                           start_from=len(trace.nodes) - 1)
                    node.dead = True
                    self.stats["strength_reduced"] += 1

    def _replace_register(self, trace: Trace, old_reg: int, new_reg: int,
                          start_from: int):
        """将追踪中对old_reg的引用替换为new_reg"""
        for i in range(start_from, -1, -1):
            node = trace.nodes[i]
            if node.dead:
                continue
            if node.src1 == old_reg:
                node.src1 = new_reg
            if node.src2 == old_reg:
                node.src2 = new_reg

    def _eval_arith(self, opcode: IROpcode, val1: float,
                    val2: float) -> Optional[float]:
        """计算算术操作的结果"""
        if opcode == IROpcode.ADD:
            return val1 + val2
        elif opcode == IROpcode.SUB:
            return val1 - val2
        elif opcode == IROpcode.MUL:
            return val1 * val2
        elif opcode == IROpcode.DIV:
            return val1 / val2 if val2 != 0 else None
        elif opcode == IROpcode.MOD:
            return val1 % val2 if val2 != 0 else None
        return None

    def _eval_cmp(self, opcode: IROpcode, val1: float,
                  val2: float) -> Optional[bool]:
        """计算比较操作的结果"""
        if opcode == IROpcode.CMP_LT:
            return val1 < val2
        elif opcode == IROpcode.CMP_GT:
            return val1 > val2
        elif opcode == IROpcode.CMP_EQ:
            return val1 == val2
        elif opcode == IROpcode.CMP_LE:
            return val1 <= val2
        return None

    def _print_ir(self, trace: Trace, stage: str):
        """打印追踪的IR"""
        print(f"\n  --- {stage} ---")
        for i, node in enumerate(trace.nodes):
            status = ""
            if node.dead:
                status = " [DEAD]"
            elif node.folded:
                status = " [FOLDED]"
            elif node.cse_merged:
                status = " [CSE]"
            print(f"    {i:3d}: {node}{status}")


# ============================================================================
# 追踪编译器
# ============================================================================

class TraceCompiler:
    """
    追踪编译器

    将优化后的追踪IR编译为可执行的Python函数。
    真正的追踪JIT（如LuaJIT）会编译为机器码，这里用Python函数模拟。
    """

    def compile(self, trace: Trace) -> Callable:
        """
        编译追踪为可执行函数

        Args:
            trace: 优化后的追踪

        Returns:
            可执行的Python函数
        """
        # 收集存活的节点（排除死代码）
        live_nodes = [n for n in trace.nodes if not n.dead]

        # 分析循环结构
        loop_start_idx = None
        loop_end_idx = None
        for i, node in enumerate(live_nodes):
            if node.opcode == IROpcode.LOOP_START:
                loop_start_idx = i
            elif node.opcode == IROpcode.LOOP_END:
                loop_end_idx = i

        if loop_start_idx is None or loop_end_idx is None:
            raise ValueError("追踪中未找到循环结构")

        # 构建编译后的函数
        constants = self._extract_constants(trace)

        def compiled_loop(variables: Dict[str, float],
                          max_iterations: int = 1000000) -> Tuple[Dict[str, float], int]:
            """
            执行编译后的追踪

            Args:
                variables: 初始变量字典
                max_iterations: 最大迭代次数

            Returns:
                (最终变量字典, 实际迭代次数)
            """
            regs = {}  # 虚拟寄存器文件
            iterations = 0

            # 执行循环前的初始化节点
            for node in live_nodes[:loop_start_idx]:
                self._execute_node(node, regs, variables)

            # 执行循环体
            for _ in range(max_iterations):
                iterations += 1

                # 执行循环体内的节点
                for node in live_nodes[loop_start_idx + 1:loop_end_idx]:
                    if node.opcode in (IROpcode.GUARD_TRUE, IROpcode.GUARD_FALSE):
                        # 检查守卫
                        src_val = regs.get(node.src1, 0.0)
                        if node.opcode == IROpcode.GUARD_TRUE:
                            if src_val == 0.0:
                                # 守卫失败，退出追踪
                                return variables, iterations
                        else:
                            if src_val != 0.0:
                                return variables, iterations
                    else:
                        self._execute_node(node, regs, variables)

                # 检查是否应该继续循环（LOOP_END处的守卫）
                # 查找LOOP_END之前的最后一个GUARD
                should_continue = True
                for node in reversed(live_nodes[loop_start_idx + 1:loop_end_idx]):
                    if node.opcode == IROpcode.GUARD_TRUE:
                        if regs.get(node.src1, 0.0) == 0.0:
                            should_continue = False
                        break
                    elif node.opcode == IROpcode.GUARD_FALSE:
                        if regs.get(node.src1, 0.0) != 0.0:
                            should_continue = False
                        break

                if not should_continue:
                    break

                # 更新循环变量（STORE操作）
                for node in live_nodes[loop_start_idx + 1:loop_end_idx]:
                    if node.opcode == IROpcode.STORE and not node.dead:
                        variables[node.var_name] = regs.get(node.src1, 0.0)

            return variables, iterations

        return compiled_loop

    def _execute_node(self, node: IRNode, regs: Dict[int, float],
                      variables: Dict[str, float]):
        """执行单个IR节点"""
        if node.dead:
            return

        if node.opcode == IROpcode.CONST:
            regs[node.dst] = node.value

        elif node.opcode == IROpcode.LOAD:
            regs[node.dst] = variables.get(node.var_name, 0.0)

        elif node.opcode == IROpcode.STORE:
            variables[node.var_name] = regs.get(node.src1, 0.0)

        elif node.opcode == IROpcode.ADD:
            regs[node.dst] = regs.get(node.src1, 0.0) + regs.get(node.src2, 0.0)

        elif node.opcode == IROpcode.SUB:
            regs[node.dst] = regs.get(node.src1, 0.0) - regs.get(node.src2, 0.0)

        elif node.opcode == IROpcode.MUL:
            regs[node.dst] = regs.get(node.src1, 0.0) * regs.get(node.src2, 0.0)

        elif node.opcode == IROpcode.DIV:
            divisor = regs.get(node.src2, 0.0)
            if divisor != 0:
                regs[node.dst] = regs.get(node.src1, 0.0) / divisor

        elif node.opcode == IROpcode.MOD:
            divisor = regs.get(node.src2, 0.0)
            if divisor != 0:
                regs[node.dst] = regs.get(node.src1, 0.0) % divisor

        elif node.opcode == IROpcode.NEG:
            regs[node.dst] = -regs.get(node.src1, 0.0)

        elif node.opcode == IROpcode.CMP_LT:
            regs[node.dst] = (1.0 if regs.get(node.src1, 0.0) <
                              regs.get(node.src2, 0.0) else 0.0)

        elif node.opcode == IROpcode.CMP_GT:
            regs[node.dst] = (1.0 if regs.get(node.src1, 0.0) >
                              regs.get(node.src2, 0.0) else 0.0)

        elif node.opcode == IROpcode.CMP_EQ:
            regs[node.dst] = (1.0 if regs.get(node.src1, 0.0) ==
                              regs.get(node.src2, 0.0) else 0.0)

        elif node.opcode == IROpcode.CMP_LE:
            regs[node.dst] = (1.0 if regs.get(node.src1, 0.0) <=
                              regs.get(node.src2, 0.0) else 0.0)

    def _extract_constants(self, trace: Trace) -> Dict[int, float]:
        """从追踪中提取所有常量"""
        constants = {}
        for node in trace.nodes:
            if node.opcode == IROpcode.CONST and not node.dead:
                constants[node.dst] = node.value
        return constants


# ============================================================================
# 追踪JIT虚拟机
# ============================================================================

class TraceJITVM:
    """
    追踪JIT虚拟机

    模拟完整的追踪JIT编译流程：
    1. 解释执行字节码
    2. 检测热循环
    3. 录制追踪
    4. 优化追踪
    5. 编译追踪
    6. 执行编译后的代码
    """

    def __init__(self, hot_loop_threshold: int = 5):
        self.hot_loop_threshold = hot_loop_threshold
        self.loop_counters: Dict[str, int] = defaultdict(int)
        self.traces: Dict[str, Trace] = {}
        self.recorder = TraceRecorder()
        self.optimizer = TraceOptimizer()
        self.compiler = TraceCompiler()
        self.stats = {
            "interpreted_iterations": 0,
            "compiled_iterations": 0,
            "traces_recorded": 0,
            "optimization_time_ms": 0.0,
            "compilation_time_ms": 0.0,
        }

    def run_sum_loop(self, n: int) -> float:
        """
        执行求和循环：sum = 0; for i in range(n): sum += i

        这是展示追踪JIT的经典示例。
        """
        loop_id = "sum_loop"

        # 检查是否有编译后的追踪
        if loop_id in self.traces and self.traces[loop_id].compiled_func:
            trace = self.traces[loop_id]
            trace.execution_count += 1
            variables = {"sum": 0.0, "i": 0.0, "n": float(n)}
            result_vars, iterations = trace.compiled_func(variables, n)
            self.stats["compiled_iterations"] += iterations
            return result_vars["sum"]

        # 热循环检测
        self.loop_counters[loop_id] += 1
        if self.loop_counters[loop_id] >= self.hot_loop_threshold:
            if loop_id not in self.traces:
                # 录制追踪
                self._record_sum_loop_trace(loop_id, n)

                # 编译并执行
                trace = self.traces[loop_id]
                trace.execution_count += 1
                variables = {"sum": 0.0, "i": 0.0, "n": float(n)}
                result_vars, iterations = trace.compiled_func(variables, n)
                self.stats["compiled_iterations"] += iterations
                return result_vars["sum"]

        # 解释执行
        self.stats["interpreted_iterations"] += n
        total = 0.0
        for i in range(n):
            total += i
        return total

    def run_polynomial_loop(self, n: int, coeffs: List[float]) -> float:
        """
        执行多项式求值循环：
            result = 0
            for x in range(n):
                result += coeffs[0] + coeffs[1]*x + coeffs[2]*x*x + ...
        """
        loop_id = "poly_loop"

        # 解释执行
        result = 0.0
        for x in range(n):
            val = 0.0
            for i, c in enumerate(coeffs):
                val += c * (x ** i)
            result += val
        return result

    def run_array_sum(self, arr: List[float]) -> float:
        """
        执行数组求和：
            total = 0
            for i in range(len(arr)):
                total += arr[i]
        """
        loop_id = "array_sum"

        # 解释执行
        total = 0.0
        for i in range(len(arr)):
            total += arr[i]
        return total

    def _record_sum_loop_trace(self, loop_id: str, n: int):
        """录制求和循环的追踪"""
        print(f"\n  [热循环检测] {loop_id} 达到阈值 {self.hot_loop_threshold}")

        recorder = TraceRecorder()
        recorder.start_recording(loop_id)

        # 录制循环前的初始化（在LOOP_START之前）
        # sum = 0
        sum_init = recorder.record_const(0.0)
        recorder.record_store("sum", sum_init)
        # i = 0
        i_init = recorder.record_const(0.0)
        recorder.record_store("i", i_init)
        # n（作为常量，因为在这个简化示例中n在循环外已知）
        n_reg = recorder.record_const(float(n))
        recorder.record_store("n", n_reg)

        # 标记循环起点（初始化之后，循环体之前）
        recorder.mark_loop_start()

        # 录制循环体
        # 加载 sum 和 i
        sum_reg = recorder.record_load("sum")
        i_reg = recorder.record_load("i")

        # sum = sum + i
        new_sum = recorder.record_add(sum_reg, i_reg)
        recorder.record_store("sum", new_sum)

        # i = i + 1
        one = recorder.record_const(1.0)
        new_i = recorder.record_add(i_reg, one)
        recorder.record_store("i", new_i)

        # 循环条件守卫：i < n
        n_reg2 = recorder.record_load("n")
        i_reg2 = recorder.record_load("i")
        cond = recorder.record_cmp_lt(i_reg2, n_reg2)
        recorder.record_guard_true(cond, 0, {"sum": 0.0, "i": 0.0})

        # 完成录制（会自动添加LOOP_END）
        trace = recorder.finish_recording()

        # 优化
        start_opt = time.perf_counter()
        self.optimizer.optimize(trace)
        end_opt = time.perf_counter()
        self.stats["optimization_time_ms"] += (end_opt - start_opt) * 1000

        # 编译
        start_compile = time.perf_counter()
        trace.compiled_func = self.compiler.compile(trace)
        end_compile = time.perf_counter()
        self.stats["compilation_time_ms"] += (end_compile - start_compile) * 1000

        self.traces[loop_id] = trace
        self.stats["traces_recorded"] += 1


# ============================================================================
# 演示函数
# ============================================================================

def demo_trace_recording():
    """演示追踪录制过程"""
    print("=" * 70)
    print("追踪录制演示")
    print("=" * 70)
    print()
    print("场景：录制一个简单的求和循环")
    print("  sum = 0")
    print("  for i in range(n):")
    print("      sum += i")
    print()

    recorder = TraceRecorder()
    recorder.start_recording("sum_loop")

    # 录制初始化（在LOOP_START之前）
    sum_init = recorder.record_const(0.0)
    recorder.record_store("sum", sum_init)
    i_init = recorder.record_const(0.0)
    recorder.record_store("i", i_init)
    n_reg = recorder.record_const(10.0)
    recorder.record_store("n", n_reg)

    # 标记循环起点
    recorder.mark_loop_start()

    # 录制循环体
    sum_reg = recorder.record_load("sum")
    i_reg = recorder.record_load("i")
    new_sum = recorder.record_add(sum_reg, i_reg)
    recorder.record_store("sum", new_sum)

    one = recorder.record_const(1.0)
    new_i = recorder.record_add(i_reg, one)
    recorder.record_store("i", new_i)

    # 循环条件
    n_reg2 = recorder.record_load("n")
    i_reg2 = recorder.record_load("i")
    cond = recorder.record_cmp_lt(i_reg2, n_reg2)
    recorder.record_guard_true(cond, 0, {"sum": 0.0, "i": 0.0})

    trace = recorder.finish_recording()

    print(f"\n  追踪包含 {len(trace.nodes)} 个IR节点")
    return trace


def demo_trace_optimization():
    """演示追踪优化过程"""
    print("\n" + "=" * 70)
    print("追踪优化演示")
    print("=" * 70)
    print()
    print("场景：优化一个包含冗余计算的循环")
    print("  result = 0")
    print("  for i in range(n):")
    print("      temp = 3 + 4          # 常量折叠")
    print("      unused = i * 2         # 可能的死代码")
    print("      result += temp * i + temp * i  # CSE")
    print()

    # 录制追踪
    recorder = TraceRecorder()
    recorder.start_recording("opt_demo")

    # 初始化（在LOOP_START之前）
    result_init = recorder.record_const(0.0)
    recorder.record_store("result", result_init)
    i_init = recorder.record_const(0.0)
    recorder.record_store("i", i_init)
    n_reg = recorder.record_const(10.0)
    recorder.record_store("n", n_reg)

    # 标记循环起点
    recorder.mark_loop_start()

    # 循环体
    i_reg = recorder.record_load("i")

    # temp = 3 + 4（可常量折叠）
    c3 = recorder.record_const(3.0)
    c4 = recorder.record_const(4.0)
    temp = recorder.record_add(c3, c4)

    # unused = i * 2（可能的死代码，如果unused未被使用）
    c2 = recorder.record_const(2.0)
    unused = recorder.record_mul(i_reg, c2)

    # result += temp * i + temp * i（CSE机会）
    t1 = recorder.record_mul(temp, i_reg)
    t2 = recorder.record_mul(temp, i_reg)  # 与t1相同
    sum_t = recorder.record_add(t1, t2)
    result_reg = recorder.record_load("result")
    new_result = recorder.record_add(result_reg, sum_t)
    recorder.record_store("result", new_result)

    # i += 1
    one = recorder.record_const(1.0)
    new_i = recorder.record_add(i_reg, one)
    recorder.record_store("i", new_i)

    # 循环条件
    n_reg2 = recorder.record_load("n")
    i_reg2 = recorder.record_load("i")
    cond = recorder.record_cmp_lt(i_reg2, n_reg2)
    recorder.record_guard_true(cond, 0, {})

    trace = recorder.finish_recording()

    # 优化
    optimizer = TraceOptimizer()
    optimized = optimizer.optimize(trace)

    return optimized


def demo_trace_execution():
    """演示追踪JIT的完整执行流程"""
    print("\n" + "=" * 70)
    print("追踪JIT完整执行流程演示")
    print("=" * 70)
    print()

    vm = TraceJITVM(hot_loop_threshold=3)

    # 第1-2次：解释执行（计数器未达到阈值）
    print("[阶段1] 解释执行（计数器未达到阈值）")
    for i in range(2):
        result = vm.run_sum_loop(100)
        print(f"  调用 {i+1}: sum(100) = {result:.0f}")

    # 第3次：触发追踪录制和JIT编译
    print("\n[阶段2] 触发热循环检测，录制追踪并编译")
    result = vm.run_sum_loop(100)
    print(f"  调用 3: sum(100) = {result:.0f} (JIT编译)")

    # 第4次以后：使用编译后的追踪
    print("\n[阶段3] 使用编译后的追踪执行")
    for i in range(3, 10):
        result = vm.run_sum_loop(100)
        print(f"  调用 {i+1}: sum(100) = {result:.0f}")

    # 统计信息
    print(f"\n[统计信息]")
    print(f"  追踪录制数: {vm.stats['traces_recorded']}")
    print(f"  解释执行迭代数: {vm.stats['interpreted_iterations']}")
    print(f"  编译执行迭代数: {vm.stats['compiled_iterations']}")
    print(f"  优化耗时: {vm.stats['optimization_time_ms']:.3f} ms")
    print(f"  编译耗时: {vm.stats['compilation_time_ms']:.3f} ms")


def demo_performance_comparison():
    """演示追踪JIT的性能对比"""
    print("\n" + "=" * 70)
    print("性能对比：解释执行 vs 追踪JIT")
    print("=" * 70)

    n = 100000
    iterations = 50

    # 纯Python解释执行（模拟解释器）
    print(f"\n[1] 求和循环: sum(range({n})), 迭代{iterations}次")
    print("-" * 50)

    start = time.perf_counter()
    for _ in range(iterations):
        total = 0.0
        for i in range(n):
            total += i
    interp_time = time.perf_counter() - start

    # 使用追踪JIT
    vm = TraceJITVM(hot_loop_threshold=3)

    start = time.perf_counter()
    for _ in range(iterations):
        result = vm.run_sum_loop(n)
    jit_time = time.perf_counter() - start

    speedup = interp_time / jit_time if jit_time > 0 else float('inf')

    print(f"  解释执行: {interp_time*1000:.2f} ms")
    print(f"  追踪JIT:  {jit_time*1000:.2f} ms")
    print(f"  加速比: {speedup:.2f}x")
    print(f"  结果: {result:.0f}")

    # 多项式求值
    print(f"\n[2] 多项式求值循环, n={n}, 迭代{iterations}次")
    print("-" * 50)

    # 纯Python
    start = time.perf_counter()
    for _ in range(iterations):
        result = 0.0
        for x in range(min(n, 10000)):
            result += 3 + 2*x + 5*x*x
    interp_time = time.perf_counter() - start

    # 追踪JIT
    vm2 = TraceJITVM(hot_loop_threshold=3)
    start = time.perf_counter()
    for _ in range(iterations):
        result = vm2.run_polynomial_loop(min(n, 10000), [3.0, 2.0, 5.0])
    jit_time = time.perf_counter() - start

    speedup = interp_time / jit_time if jit_time > 0 else float('inf')

    print(f"  解释执行: {interp_time*1000:.2f} ms")
    print(f"  追踪JIT:  {jit_time*1000:.2f} ms")
    print(f"  加速比: {speedup:.2f}x")
    print(f"  结果: {result:.0f}")

    # 统计
    print(f"\n[追踪JIT统计]")
    print(f"  追踪录制数: {vm.stats['traces_recorded']}")
    print(f"  解释执行迭代数: {vm.stats['interpreted_iterations']}")
    print(f"  编译执行迭代数: {vm.stats['compiled_iterations']}")
    print(f"  优化耗时: {vm.stats['optimization_time_ms']:.3f} ms")
    print(f"  编译耗时: {vm.stats['compilation_time_ms']:.3f} ms")


def demo_side_trace():
    """演示侧追踪（Side Trace）的概念"""
    print("\n" + "=" * 70)
    print("侧追踪（Side Trace）演示")
    print("=" * 70)
    print()
    print("侧追踪是当主追踪中的守卫失败时，从失败点开始录制的新追踪。")
    print()
    print("场景：")
    print("  for i in range(n):")
    print("      if x > 0:")
    print("          result += a[i]   # 路径A（主追踪）")
    print("      else:")
    print("          result -= a[i]   # 路径B（侧追踪）")
    print()

    # 模拟主追踪
    print("[主追踪] 假设 x > 0 总是成立")
    print("  IR:")
    print("    [0] LOOP_START")
    print("    [1] LOAD r0, 'x'")
    print("    [2] CONST r1, 0")
    print("    [3] CMP_GT r2, r0, r1")
    print("    [4] GUARD_TRUE r2        <-- 守卫：x > 0")
    print("    [5] LOAD r3, 'result'")
    print("    [6] LOAD r4, 'a[i]'")
    print("    [7] ADD r5, r3, r4        # result += a[i]")
    print("    [8] STORE 'result', r5")
    print("    [9] ... 循环递增 ...")
    print("    [10] GUARD_TRUE (i < n)")
    print("    [11] LOOP_END")
    print()

    # 模拟侧追踪
    print("[侧追踪] 当 x <= 0 时，从守卫失败点开始录制")
    print("  IR:")
    print("    [0] LOAD r3, 'result'")
    print("    [1] LOAD r4, 'a[i]'")
    print("    [2] SUB r5, r3, r4        # result -= a[i]")
    print("    [3] STORE 'result', r5")
    print("    [4] ... 循环递增 ...")
    print("    [5] GUARD_TRUE (i < n)")
    print("    [6] JUMP -> 主追踪循环头   # 链接回主追踪")
    print()

    # 性能影响分析
    print("[追踪爆炸分析]")
    print("  如果循环中有k个二元分支，理论上最多产生 2^k 条追踪。")
    print("  LuaJIT通过以下机制限制追踪爆炸：")
    print("  - 最大追踪长度限制")
    print("  - 最大侧追踪深度限制")
    print("  - 黑名单机制")
    print("  - 最大追踪数量限制")


def demo_trace_linking():
    """演示追踪链接"""
    print("\n" + "=" * 70)
    print("追踪链接（Trace Linking）演示")
    print("=" * 70)
    print()
    print("追踪链接允许已编译的追踪直接跳转到其他追踪，")
    print("避免返回解释器的开销。")
    print()

    # 创建两个追踪
    print("[示例] 两个追踪的链接")
    print()
    print("  追踪A（外层循环）：")
    print("    LOOP_START")
    print("    LOAD r0, 'i'")
    print("    CONST r1, 100")
    print("    CMP_LT r2, r0, r1")
    print("    GUARD_TRUE r2")
    print("    ... 外层循环体 ...")
    print("    JUMP -> 追踪B循环头        # 链接到追踪B")
    print("    LOOP_END")
    print()
    print("  追踪B（内层循环）：")
    print("    LOOP_START")
    print("    LOAD r0, 'j'")
    print("    CONST r1, 1000")
    print("    CMP_LT r2, r0, r1")
    print("    GUARD_TRUE r2")
    print("    ... 内层循环体 ...")
    print("    JUMP -> 追踪B循环头        # 循环链接")
    print("    LOOP_END")
    print("    JUMP -> 追踪A循环头        # 链接回追踪A")
    print()
    print("  链接后的执行路径：")
    print("    追踪A循环体")
    print("      -> 追踪B循环体 (直接跳转，无解释器开销)")
    print("      -> 追踪B循环体")
    print("      -> ... (重复)")
    print("      -> 追踪A循环体 (直接跳转)")
    print("      -> ...")


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主函数"""
    print("=" * 70)
    print("  第10章：JIT编译 - 追踪JIT编译演示")
    print("=" * 70)
    print()
    print("本演示展示追踪级JIT编译的核心概念：")
    print("  1. 追踪录制（Trace Recording）")
    print("  2. 追踪优化（常量折叠、DCE、CSE）")
    print("  3. 追踪编译和执行")
    print("  4. 侧追踪和追踪链接")
    print("  5. 性能对比")
    print()

    # 演示1：追踪录制
    demo_trace_recording()

    # 演示2：追踪优化
    demo_trace_optimization()

    # 演示3：完整执行流程
    demo_trace_execution()

    # 演示4：性能对比
    demo_performance_comparison()

    # 演示5：侧追踪
    demo_side_trace()

    # 演示6：追踪链接
    demo_trace_linking()

    print("\n" + "=" * 70)
    print("演示完成!")
    print("=" * 70)
    print()
    print("关键要点：")
    print("  1. 追踪JIT只编译热循环的单一执行路径（线性化）")
    print("  2. 线性代码更容易优化（无控制流复杂性）")
    print("  3. 守卫（Guard）处理分支，失败时退出追踪")
    print("  4. 侧追踪处理守卫失败的分支路径")
    print("  5. 追踪链接避免返回解释器的开销")
    print("  6. 追踪爆炸是追踪JIT的主要挑战")


if __name__ == "__main__":
    main()
