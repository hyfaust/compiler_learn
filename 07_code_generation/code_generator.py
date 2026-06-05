"""
代码生成器：从三地址码生成 x86 汇编代码
==========================================

功能：
  1. 指令选择 — 将三地址码翻译为 x86 指令序列
  2. 简单寄存器分配 — 基于活跃区间的线性扫描分配
  3. 栈帧管理 — 自动生成函数序言/尾声
  4. 函数调用 — 处理参数传递和返回值

支持的三地址码指令：
  - 算术：ADD, SUB, MUL, DIV
  - 赋值：ASSIGN (x = y)
  - 比较：CMP (比较两个值，设置条件码)
  - 跳转：JMP, JZ (条件跳转)
  - 标签：LABEL
  - 函数：CALL, RET, PARAM
  - 内存：LOAD, STORE
"""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional


# ============================================================
#  数据结构定义
# ============================================================

class OpCode(Enum):
    """三地址码操作码"""
    ADD = auto()
    SUB = auto()
    MUL = auto()
    DIV = auto()
    ASSIGN = auto()      # x = y
    CMP = auto()         # 比较，设置条件码
    JMP = auto()         # 无条件跳转
    JZ = auto()          # 条件跳转（等于0时跳转）
    JNZ = auto()         # 条件跳转（不等于0时跳转）
    JG = auto()          # 大于时跳转
    JL = auto()          # 小于时跳转
    LABEL = auto()       # 标签定义
    CALL = auto()        # 函数调用
    RET = auto()         # 函数返回
    PARAM = auto()       # 传递参数
    LOAD = auto()        # 从内存加载: x = [addr]
    STORE = auto()       # 存储到内存: [addr] = x
    FUNC_BEGIN = auto()  # 函数开始
    FUNC_END = auto()    # 函数结束


@dataclass
class Instruction:
    """一条三地址码指令"""
    op: OpCode
    result: Optional[str] = None   # 目标操作数
    arg1: Optional[str] = None     # 源操作数1
    arg2: Optional[str] = None     # 源操作数2
    label: Optional[str] = None    # 标签名（用于跳转/标签指令）

    def __repr__(self):
        parts = [self.op.name]
        if self.result:
            parts.append(f"result={self.result}")
        if self.arg1:
            parts.append(f"arg1={self.arg1}")
        if self.arg2:
            parts.append(f"arg2={self.arg2}")
        if self.label:
            parts.append(f"label={self.label}")
        return f"Inst({', '.join(parts)})"


# ============================================================
#  活性分析
# ============================================================

def liveness_analysis(instructions: list[Instruction]) -> list[set[str]]:
    """
    活性分析：计算每条指令之后的活跃变量集合。

    返回：live_out[i] = 在第 i 条指令执行之后活跃的变量集合
    """
    n = len(instructions)
    live_out: list[set[str]] = [set() for _ in range(n)]

    def uses(inst: Instruction) -> set[str]:
        """获取指令中被读取的变量"""
        result = set()
        if inst.arg1 and not inst.arg1.startswith('#') and not inst.arg1.startswith('.'):
            result.add(inst.arg1)
        if inst.arg2 and not inst.arg2.startswith('#') and not inst.arg2.startswith('.'):
            result.add(inst.arg2)
        return result

    def defs(inst: Instruction) -> set[str]:
        """获取指令中被定义（写入）的变量"""
        if inst.result:
            return {inst.result}
        return set()

    # 迭代求解（固定点算法）
    changed = True
    while changed:
        changed = False
        for i in range(n - 1, -1, -1):
            inst = instructions[i]

            # 计算新的 live_out
            new_live: set[str] = set()

            # 后继指令的活跃输入
            if inst.op in (OpCode.JMP, OpCode.JZ, OpCode.JNZ, OpCode.JG, OpCode.JL):
                # 跳转指令：活跃变量来自跳转目标
                if inst.label:
                    # 找到目标标签的位置
                    for j, other in enumerate(instructions):
                        if other.op == OpCode.LABEL and other.label == inst.label:
                            if j + 1 < n:
                                new_live |= live_out[j]
                            break
                # 也包括顺序执行的下一条（条件跳转）
                if inst.op != OpCode.JMP and i + 1 < n:
                    new_live |= live_out[i + 1]
            elif inst.op == OpCode.RET:
                # 返回指令没有后继
                pass
            elif i + 1 < n:
                new_live |= live_out[i + 1]

            # 加入使用变量，移除定义变量
            new_live = (new_live - defs(inst)) | uses(inst)

            if new_live != live_out[i]:
                live_out[i] = new_live
                changed = True

    return live_out


# ============================================================
#  寄存器分配器
# ============================================================

# 可用寄存器（排除 ESP, EBP，保留给栈帧管理）
AVAILABLE_REGS = ['eax', 'ebx', 'ecx', 'edx']


class RegisterAllocator:
    """
    简单的寄存器分配器。

    策略：
    1. 每个变量优先分配寄存器
    2. 寄存器不够时，溢出（spill）到栈上
    3. 使用活性分析确定变量的活跃范围

    注意：这是一个教学用的简化实现。生产级编译器会使用
    图着色或线性扫描算法的完整版本。
    """

    def __init__(self, instructions: list[Instruction]):
        self.instructions = instructions
        self.live_out = liveness_analysis(instructions)
        # 变量 -> 寄存器名 或 None（表示在栈上）
        self.var_to_reg: dict[str, Optional[str]] = {}
        # 寄存器 -> 当前持有变量 或 None
        self.reg_to_var: dict[str, Optional[str]] = {r: None for r in AVAILABLE_REGS}
        # 栈溢出变量 -> 栈偏移
        self.spill_offsets: dict[str, int] = {}
        self.spill_count = 0

    def allocate_for_instruction(self, idx: int) -> dict[str, str]:
        """
        为第 idx 条指令的变量分配寄存器。

        返回：{变量名: 寄存器名} 的映射
        """
        inst = self.instructions[idx]
        live = self.live_out[idx]

        mapping: dict[str, str] = {}

        # 收集本条指令涉及的变量
        vars_needed: set[str] = set()
        if inst.result:
            vars_needed.add(inst.result)
        if inst.arg1 and not inst.arg1.startswith('#') and not inst.arg1.startswith('.'):
            vars_needed.add(inst.arg1)
        if inst.arg2 and not inst.arg2.startswith('#') and not inst.arg2.startswith('.'):
            vars_needed.add(inst.arg2)

        for var in vars_needed:
            reg = self._ensure_in_register(var, live)
            mapping[var] = reg

        return mapping

    def _ensure_in_register(self, var: str, live: set[str]) -> str:
        """确保变量 var 在某个寄存器中，返回寄存器名"""
        # 如果已经在寄存器中
        if var in self.var_to_reg and self.var_to_reg[var] is not None:
            return self.var_to_reg[var]  # type: ignore

        # 尝试找一个空闲寄存器
        free_reg = self._find_free_register()
        if free_reg:
            self._assign(var, free_reg)
            return free_reg

        # 需要溢出某个寄存器
        victim_reg = self._choose_spill(live)
        self._spill(victim_reg)
        self._assign(var, victim_reg)
        return victim_reg

    def _find_free_register(self) -> Optional[str]:
        """查找一个空闲寄存器"""
        for reg, var in self.reg_to_var.items():
            if var is None:
                return reg
        return None

    def _assign(self, var: str, reg: str):
        """将变量分配到寄存器"""
        self.var_to_reg[var] = reg
        self.reg_to_var[reg] = var

    def _spill(self, reg: str):
        """将寄存器中的变量溢出到栈"""
        var = self.reg_to_var[reg]
        if var is not None:
            if var not in self.spill_offsets:
                self.spill_count += 1
                self.spill_offsets[var] = self.spill_count * 4  # 每个变量4字节
            self.var_to_reg[var] = None
        self.reg_to_var[reg] = None

    def _choose_spill(self, live: set[str]) -> str:
        """选择一个寄存器进行溢出（启发式：选择最远使用的）"""
        # 简单策略：选择第一个非活跃变量所在的寄存器
        for reg, var in self.reg_to_var.items():
            if var is not None and var not in live:
                return reg

        # 都活跃，选择第一个（LRU 启发式）
        for reg in self.reg_to_var:
            return reg
        return AVAILABLE_REGS[0]

    def free_dead_registers(self, idx: int):
        """释放本指令后不再活跃的变量的寄存器"""
        live = self.live_out[idx]
        for reg, var in list(self.reg_to_var.items()):
            if var is not None and var not in live:
                self.var_to_reg[var] = None
                self.reg_to_var[reg] = None


# ============================================================
#  代码生成器
# ============================================================

class CodeGenerator:
    """
    从三地址码生成 x86 (AT&T 语法) 汇编代码。

    生成的汇编使用 GAS (GNU Assembler) AT&T 语法，
    目标平台为 32 位 x86 (cdecl 调用约定)。
    """

    def __init__(self, instructions: list[Instruction]):
        self.instructions = instructions
        self.allocator = RegisterAllocator(instructions)
        self.output: list[str] = []
        self.local_vars: set[str] = set()   # 局部变量集合
        self.temp_vars: set[str] = set()    # 临时变量集合

    def generate(self) -> str:
        """主生成流程，返回完整汇编代码"""
        self._collect_variables()
        self._emit_data_section()
        self._emit_text_section()
        return '\n'.join(self.output)

    def _collect_variables(self):
        """收集所有变量，区分局部变量和临时变量"""
        for inst in self.instructions:
            for var in [inst.result, inst.arg1, inst.arg2]:
                if var and not var.startswith('#') and not var.startswith('.'):
                    if var.startswith('t'):
                        self.temp_vars.add(var)
                    else:
                        self.local_vars.add(var)

    def _emit_data_section(self):
        """生成 .data 段（已初始化数据）"""
        self.output.append("# ============================================================")
        self.output.append("#  由代码生成器自动生成的 x86 汇编代码 (AT&T 语法)")
        self.output.append("#  目标：32 位 x86，cdecl 调用约定")
        self.output.append("# ============================================================")
        self.output.append("")
        self.output.append(".data")
        self.output.append("")

    def _emit_text_section(self):
        """生成 .text 段（代码段）"""
        self.output.append(".text")
        self.output.append("")

        # 检查是否有函数定义
        has_func = any(inst.op == OpCode.FUNC_BEGIN for inst in self.instructions)
        if not has_func:
            # 没有显式函数定义，生成一个 main 函数
            self._emit_main_wrapper()

        # 逐条翻译指令
        for i, inst in enumerate(self.instructions):
            self._emit_instruction(i, inst)

        self.output.append("")

    def _emit_main_wrapper(self):
        """生成 main 函数包装"""
        self.output.append(".globl main")
        self.output.append("main:")
        self._emit_prologue("__main_body")
        self.output.append("")

    def _emit_prologue(self, func_name: str):
        """生成函数序言"""
        # 计算局部变量空间
        total_vars = len(self.local_vars) | len(self.temp_vars)
        stack_size = max((total_vars + self.allocator.spill_count) * 4, 16)
        # 对齐到16字节
        stack_size = (stack_size + 15) & ~15

        self.output.append(f"    # ---- 函数序言 ({func_name}) ----")
        self.output.append(f"    pushl %ebp")
        self.output.append(f"    movl  %esp, %ebp")
        self.output.append(f"    subl  ${stack_size}, %esp")

        # 保存 callee-saved 寄存器
        self.output.append(f"    pushl %ebx")
        self.output.append(f"    pushl %esi")
        self.output.append(f"    pushl %edi")
        self.output.append("")

    def _emit_epilogue(self, func_name: str):
        """生成函数尾声"""
        self.output.append(f"    # ---- 函数尾声 ({func_name}) ----")
        self.output.append(f"    popl  %edi")
        self.output.append(f"    popl  %esi")
        self.output.append(f"    popl  %ebx")
        self.output.append(f"    movl  %ebp, %esp")
        self.output.append(f"    popl  %ebp")
        self.output.append(f"    ret")
        self.output.append("")

    def _emit_instruction(self, idx: int, inst: Instruction):
        """翻译单条三地址码指令为 x86 汇编"""
        mapping = self.allocator.allocate_for_instruction(idx)

        if inst.op == OpCode.FUNC_BEGIN:
            func_name = inst.label or "func"
            self.output.append(f".globl {func_name}")
            self.output.append(f"{func_name}:")
            self._emit_prologue(func_name)

        elif inst.op == OpCode.FUNC_END:
            func_name = inst.label or "func"
            self._emit_epilogue(func_name)

        elif inst.op == OpCode.LABEL:
            self.output.append(f"{inst.label}:")

        elif inst.op == OpCode.ASSIGN:
            # x = y
            self._emit_load_var(mapping, inst.arg1, '%eax')
            self._emit_store_var(mapping, inst.result, '%eax')

        elif inst.op == OpCode.ADD:
            # result = arg1 + arg2
            self._emit_binary_op(mapping, inst, 'addl')

        elif inst.op == OpCode.SUB:
            # result = arg1 - arg2
            self._emit_binary_op(mapping, inst, 'subl')

        elif inst.op == OpCode.MUL:
            # result = arg1 * arg2 (有符号)
            self._emit_load_var(mapping, inst.arg1, '%eax')
            self.output.append(f"    imull {self._operand(mapping, inst.arg2)}, %eax")
            self._emit_store_var(mapping, inst.result, '%eax')

        elif inst.op == OpCode.DIV:
            # result = arg1 / arg2 (有符号整除)
            self._emit_load_var(mapping, inst.arg1, '%eax')
            self.output.append(f"    cltd")  # EAX 符号扩展到 EDX:EAX
            self.output.append(f"    idivl {self._operand(mapping, inst.arg2)}")
            self._emit_store_var(mapping, inst.result, '%eax')  # 商在 EAX

        elif inst.op == OpCode.CMP:
            # 比较 arg1 和 arg2，设置 EFLAGS
            self._emit_load_var(mapping, inst.arg1, '%eax')
            self.output.append(f"    cmpl {self._operand(mapping, inst.arg2)}, %eax")

        elif inst.op == OpCode.JMP:
            self.output.append(f"    jmp {inst.label}")

        elif inst.op == OpCode.JZ:
            self.output.append(f"    je {inst.label}")

        elif inst.op == OpCode.JNZ:
            self.output.append(f"    jne {inst.label}")

        elif inst.op == OpCode.JG:
            self.output.append(f"    jg {inst.label}")

        elif inst.op == OpCode.JL:
            self.output.append(f"    jl {inst.label}")

        elif inst.op == OpCode.CALL:
            # CALL func_name, result
            func_name = inst.label or inst.arg1 or "unknown"
            self.output.append(f"    call {func_name}")
            if inst.result:
                self._emit_store_var(mapping, inst.result, '%eax')

        elif inst.op == OpCode.RET:
            if inst.arg1:
                self._emit_load_var(mapping, inst.arg1, '%eax')
            self.output.append(f"    jmp .Lret")

        elif inst.op == OpCode.PARAM:
            # 参数传递（cdecl：通过栈传递）
            self._emit_load_var(mapping, inst.arg1, '%eax')
            self.output.append(f"    pushl %eax")

        elif inst.op == OpCode.LOAD:
            # result = [arg1]
            self.output.append(f"    movl {inst.arg1}, %eax")
            self._emit_store_var(mapping, inst.result, '%eax')

        elif inst.op == OpCode.STORE:
            # [result] = arg1
            self._emit_load_var(mapping, inst.arg1, '%eax')
            self.output.append(f"    movl %eax, {inst.result}")

        # 释放不再活跃的寄存器
        self.allocator.free_dead_registers(idx)

    def _emit_binary_op(self, mapping: dict[str, str], inst: Instruction, op: str):
        """生成二元运算的汇编"""
        self._emit_load_var(mapping, inst.arg1, '%eax')
        self.output.append(f"    {op} {self._operand(mapping, inst.arg2)}, %eax")
        self._emit_store_var(mapping, inst.result, '%eax')

    def _operand(self, mapping: dict[str, str], var: Optional[str]) -> str:
        """获取变量的操作数表示"""
        if var is None:
            return '$0'
        if var.startswith('#'):
            # 立即数：#42 -> $42
            return f'${var[1:]}'
        if var in mapping:
            return f'%{mapping[var]}'
        # 尝试从分配器获取
        if var in self.allocator.var_to_reg and self.allocator.var_to_reg[var]:
            return f'%{self.allocator.var_to_reg[var]}'
        # 栈溢出变量
        if var in self.allocator.spill_offsets:
            offset = self.allocator.spill_offsets[var]
            return f'-%offset(%ebp)'
        return f'${var}'

    def _emit_load_var(self, mapping: dict[str, str], var: Optional[str], target_reg: str):
        """生成将变量加载到目标寄存器的指令"""
        if var is None:
            return
        if var.startswith('#'):
            # 立即数
            self.output.append(f"    movl ${var[1:]}, {target_reg}")
        elif var in mapping:
            reg = mapping[var]
            if f'%{reg}' != target_reg:
                self.output.append(f"    movl %{reg}, {target_reg}")
        elif var in self.allocator.var_to_reg and self.allocator.var_to_reg[var]:
            reg = self.allocator.var_to_reg[var]
            if f'%{reg}' != target_reg:
                self.output.append(f"    movl %{reg}, {target_reg}")
        else:
            self.output.append(f"    # 加载变量 {var}")

    def _emit_store_var(self, mapping: dict[str, str], var: Optional[str], src_reg: str):
        """生成将寄存器值存储到变量的指令"""
        if var is None:
            return
        if var in mapping:
            reg = mapping[var]
            if f'%{reg}' != src_reg:
                self.output.append(f"    movl {src_reg}, %{reg}")
        elif var in self.allocator.var_to_reg and self.allocator.var_to_reg[var]:
            reg = self.allocator.var_to_reg[var]
            if f'%{reg}' != src_reg:
                self.output.append(f"    movl {src_reg}, %{reg}")
        else:
            self.output.append(f"    # 存储变量 {var}")


# ============================================================
#  示例程序：三地址码
# ============================================================

def create_example_program() -> list[Instruction]:
    """
    创建示例三地址码程序。

    对应的源代码（伪C）：

        int compute(int a, int b) {
            int t1 = a + b;
            int t2 = a - b;
            int t3 = t1 * t2;
            int t4 = t3 / #2;
            return t4;
        }

        int main() {
            int result = compute(10, 3);
            return result;
        }
    """
    instructions = [
        # ---- compute 函数 ----
        Instruction(OpCode.FUNC_BEGIN, label="compute"),
        # compute 的参数 a, b 在栈上 [ebp+8], [ebp+12]
        # 这里简化处理，假设 a 在 eax，b 在 ecx

        # t1 = a + b
        Instruction(OpCode.ADD, result="t1", arg1="a", arg2="b"),

        # t2 = a - b
        Instruction(OpCode.SUB, result="t2", arg1="a", arg2="b"),

        # t3 = t1 * t2
        Instruction(OpCode.MUL, result="t3", arg1="t1", arg2="t2"),

        # t4 = t3 / 2
        Instruction(OpCode.DIV, result="t4", arg1="t3", arg2="#2"),

        # return t4
        Instruction(OpCode.RET, arg1="t4"),

        Instruction(OpCode.FUNC_END, label="compute"),

        # ---- main 函数 ----
        Instruction(OpCode.FUNC_BEGIN, label="main"),

        # 传递参数：先压栈（从右到左，但这里只有一个调用）
        Instruction(OpCode.PARAM, arg1="#3"),   # b = 3
        Instruction(OpCode.PARAM, arg1="#10"),  # a = 10

        # 调用 compute
        Instruction(OpCode.CALL, label="compute", result="result"),

        # 清理栈参数（2个参数 × 4字节）
        # （实际代码生成器应该自动处理，这里简化）

        # return result
        Instruction(OpCode.RET, arg1="result"),

        Instruction(OpCode.FUNC_END, label="main"),
    ]

    return instructions


def create_branch_example() -> list[Instruction]:
    """
    创建带分支的示例程序。

    对应的源代码：

        int max(int a, int b) {
            if (a > b) {
                return a;
            } else {
                return b;
            }
        }
    """
    instructions = [
        Instruction(OpCode.FUNC_BEGIN, label="max"),

        # if (a > b)
        Instruction(OpCode.CMP, arg1="a", arg2="b"),
        Instruction(OpCode.JG, label=".Lthen"),

        # else 分支
        Instruction(OpCode.ASSIGN, result="t1", arg1="b"),
        Instruction(OpCode.JMP, label=".Lend"),

        # then 分支
        Instruction(OpCode.LABEL, label=".Lthen"),
        Instruction(OpCode.ASSIGN, result="t1", arg1="a"),

        Instruction(OpCode.LABEL, label=".Lend"),
        Instruction(OpCode.RET, arg1="t1"),

        Instruction(OpCode.FUNC_END, label="max"),
    ]

    return instructions


def create_loop_example() -> list[Instruction]:
    """
    创建带循环的示例程序。

    对应的源代码：

        int sum(int n) {
            int total = 0;
            int i = 1;
            while (i <= n) {
                total = total + i;
                i = i + 1;
            }
            return total;
        }
    """
    instructions = [
        Instruction(OpCode.FUNC_BEGIN, label="sum"),

        # total = 0
        Instruction(OpCode.ASSIGN, result="total", arg1="#0"),
        # i = 1
        Instruction(OpCode.ASSIGN, result="i", arg1="#1"),

        # loop:
        Instruction(OpCode.LABEL, label=".Lloop"),

        # if i > n, break
        Instruction(OpCode.CMP, arg1="i", arg2="n"),
        Instruction(OpCode.JG, label=".Ldone"),

        # total = total + i
        Instruction(OpCode.ADD, result="total", arg1="total", arg2="i"),

        # i = i + 1
        Instruction(OpCode.ADD, result="i", arg1="i", arg2="#1"),

        # goto loop
        Instruction(OpCode.JMP, label=".Lloop"),

        # done:
        Instruction(OpCode.LABEL, label=".Ldone"),
        Instruction(OpCode.RET, arg1="total"),

        Instruction(OpCode.FUNC_END, label="sum"),
    ]

    return instructions


# ============================================================
#  主函数
# ============================================================

def main():
    print("=" * 70)
    print("  代码生成器演示：三地址码 → x86 汇编")
    print("=" * 70)
    print()

    # ---------- 示例 1：简单算术 ----------
    print("─" * 70)
    print("示例 1：简单算术运算")
    print("─" * 70)
    print()
    print("源代码（伪C）：")
    print("  int compute(int a, int b) {")
    print("      int t1 = a + b;")
    print("      int t2 = a - b;")
    print("      int t3 = t1 * t2;")
    print("      int t4 = t3 / 2;")
    print("      return t4;")
    print("  }")
    print()

    instructions = create_example_program()

    print("三地址码：")
    for i, inst in enumerate(instructions):
        print(f"  [{i:2d}] {inst}")
    print()

    # 活性分析
    live = liveness_analysis(instructions)
    print("活性分析结果（每条指令后的活跃变量）：")
    for i, inst in enumerate(instructions):
        if live[i]:
            print(f"  [{i:2d}] {inst.op.name:12s}  live_out = {{{', '.join(sorted(live[i]))}}}")
    print()

    # 代码生成
    gen = CodeGenerator(instructions)
    asm = gen.generate()
    print("生成的 x86 汇编（AT&T 语法）：")
    print(asm)
    print()

    # ---------- 示例 2：分支 ----------
    print("─" * 70)
    print("示例 2：条件分支（max 函数）")
    print("─" * 70)
    print()
    print("源代码（伪C）：")
    print("  int max(int a, int b) {")
    print("      if (a > b) return a;")
    print("      else return b;")
    print("  }")
    print()

    instructions = create_branch_example()

    print("三地址码：")
    for i, inst in enumerate(instructions):
        print(f"  [{i:2d}] {inst}")
    print()

    gen = CodeGenerator(instructions)
    asm = gen.generate()
    print("生成的 x86 汇编：")
    print(asm)
    print()

    # ---------- 示例 3：循环 ----------
    print("─" * 70)
    print("示例 3：循环（sum 函数）")
    print("─" * 70)
    print()
    print("源代码（伪C）：")
    print("  int sum(int n) {")
    print("      int total = 0, i = 1;")
    print("      while (i <= n) { total += i; i++; }")
    print("      return total;")
    print("  }")
    print()

    instructions = create_loop_example()

    print("三地址码：")
    for i, inst in enumerate(instructions):
        print(f"  [{i:2d}] {inst}")
    print()

    gen = CodeGenerator(instructions)
    asm = gen.generate()
    print("生成的 x86 汇编：")
    print(asm)
    print()

    # ---------- 寄存器分配说明 ----------
    print("=" * 70)
    print("  寄存器分配说明")
    print("=" * 70)
    print()
    print("可用寄存器: ", AVAILABLE_REGS)
    print()
    print("分配策略:")
    print("  1. 首先尝试复用已有寄存器")
    print("  2. 然后尝试使用空闲寄存器")
    print("  3. 最后进行溢出（spill）到栈上")
    print()
    print("溢出的变量存储在栈帧中 [EBP - N] 位置。")
    print()
    print("注意：这是一个教学用的简化实现。")
    print("生产级编译器会使用 Chaitin-Briggs 图着色或线性扫描算法。")


if __name__ == '__main__':
    main()
