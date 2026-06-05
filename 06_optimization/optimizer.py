"""
代码优化器
==========

实现多种编译器优化技术：
  1. 常量折叠（Constant Folding）
  2. 常量传播（Constant Propagation）
  3. 死代码消除（Dead Code Elimination）
  4. 公共子表达式消除（CSE, Common Subexpression Elimination）
  5. 活跃变量分析（Live Variable Analysis）

优化前后对比输出，完整可运行。

使用方法:
  python optimizer.py
"""

from typing import Dict, List, Set, Tuple, Optional
from copy import deepcopy
import re


# ============================================================
# 中间表示（IR）数据结构
# ============================================================

class IRInstruction:
    """中间代码指令（三地址码形式）"""

    def __init__(self, op: str, dest: str = None, src1: str = None,
                 src2: str = None, label: str = None):
        self.op = op            # 操作符: "=", "+", "-", "*", "/", "<", ">", "if", "goto", "return", "nop"
        self.dest = dest        # 目标变量
        self.src1 = src1        # 源操作数 1
        self.src2 = src2        # 源操作数 2
        self.label = label      # 标签（可选）
        self.eliminated = False  # 是否被消除

    def __repr__(self):
        if self.eliminated:
            return f"[ELIM] {self.to_string()}"
        return self.to_string()

    def to_string(self) -> str:
        parts = []
        if self.label:
            parts.append(f"{self.label}:")
        if self.op == "=":
            parts.append(f"{self.dest} = {self.src1}")
        elif self.op in ("+", "-", "*", "/", "<", ">", "<=", ">=", "==", "!="):
            parts.append(f"{self.dest} = {self.src1} {self.op} {self.src2}")
        elif self.op == "if":
            parts.append(f"if {self.src1} goto {self.dest}")
        elif self.op == "ifFalse":
            parts.append(f"ifFalse {self.src1} goto {self.dest}")
        elif self.op == "goto":
            parts.append(f"goto {self.dest}")
        elif self.op == "return":
            parts.append(f"return {self.dest}")
        elif self.op == "param":
            parts.append(f"param {self.src1}")
        elif self.op == "call":
            if self.dest:
                parts.append(f"{self.dest} = call {self.src1}")
            else:
                parts.append(f"call {self.src1}")
        elif self.op == "nop":
            parts.append("nop")
        else:
            parts.append(f"{self.dest} = {self.op} {self.src1}")
        return " ".join(parts)

    def is_constant(self, value: str) -> bool:
        """判断一个操作数是否是常量"""
        try:
            int(value)
            return True
        except (ValueError, TypeError):
            pass
        try:
            float(value)
            return True
        except (ValueError, TypeError):
            pass
        return False

    def get_used_vars(self) -> List[str]:
        """获取指令中使用的变量"""
        used = []
        if self.src1 and not self.is_constant(self.src1):
            used.append(self.src1)
        if self.src2 and not self.is_constant(self.src2):
            used.append(self.src2)
        return used

    def get_defined_var(self) -> Optional[str]:
        """获取指令定义的变量"""
        if self.dest and self.op not in ("goto", "if", "ifFalse", "ifTrue"):
            return self.dest
        return None


class IRBlock:
    """基本块"""

    def __init__(self, label: str):
        self.label = label
        self.instructions: List[IRInstruction] = []
        self.successors: List['IRBlock'] = []
        self.predecessors: List['IRBlock'] = []

    def def_vars(self) -> Set[str]:
        """本块中定义的变量"""
        defs = set()
        for instr in self.instructions:
            if not instr.eliminated:
                d = instr.get_defined_var()
                if d:
                    defs.add(d)
        return defs

    def use_vars(self) -> Set[str]:
        """本块中使用且在使用前未定义的变量"""
        used = set()
        defined = set()
        for instr in self.instructions:
            if instr.eliminated:
                continue
            for u in instr.get_used_vars():
                if u not in defined:
                    used.add(u)
            d = instr.get_defined_var()
            if d:
                defined.add(d)
        return used


# ============================================================
# 优化 1: 常量折叠 (Constant Folding)
# ============================================================

class ConstantFolder:
    """
    常量折叠：在编译时计算常量表达式的值。

    例如:
      x = 3 + 5       →  x = 8
      y = 2 * 4 + 1   →  y = 9
      z = 10 / 2       →  z = 5
    """

    BINARY_OPS = {
        '+': lambda a, b: a + b,
        '-': lambda a, b: a - b,
        '*': lambda a, b: a * b,
        '/': lambda a, b: a // b if b != 0 else None,
        '<': lambda a, b: int(a < b),
        '>': lambda a, b: int(a > b),
        '<=': lambda a, b: int(a <= b),
        '>=': lambda a, b: int(a >= b),
        '==': lambda a, b: int(a == b),
        '!=': lambda a, b: int(a != b),
    }

    def fold(self, instructions: List[IRInstruction]) -> Tuple[List[IRInstruction], int]:
        """对指令列表执行常量折叠

        Returns:
            (优化后的指令列表, 变换次数)
        """
        changes = 0
        for instr in instructions:
            if instr.eliminated:
                continue

            # 情况 1: x = const1 op const2
            if instr.op in self.BINARY_OPS:
                if (self._is_const(instr.src1) and self._is_const(instr.src2)):
                    val1 = self._to_number(instr.src1)
                    val2 = self._to_number(instr.src2)
                    result = self.BINARY_OPS[instr.op](val1, val2)
                    if result is not None:
                        # 转换为简单的赋值
                        instr.op = "="
                        instr.src1 = str(int(result))
                        instr.src2 = None
                        changes += 1

            # 情况 2: x = +const（一元正号）
            elif instr.op == "+" and instr.src2 is None:
                if self._is_const(instr.src1):
                    instr.op = "="
                    changes += 1

        return instructions, changes

    @staticmethod
    def _is_const(val: str) -> bool:
        if val is None:
            return False
        try:
            int(val)
            return True
        except (ValueError, TypeError):
            return False

    @staticmethod
    def _to_number(val: str) -> int:
        return int(val)


# ============================================================
# 优化 2: 常量传播 (Constant Propagation)
# ============================================================

class ConstantPropagator:
    """
    常量传播：如果变量被赋值为常量，且之后未被修改，则用常量替换其使用。

    例如:
      x = 5           →  x = 5
      y = x + 3       →  y = 5 + 3  (可继续折叠)
      z = x * 2       →  z = 5 * 2  (可继续折叠)
    """

    def propagate(self, instructions: List[IRInstruction]) -> Tuple[List[IRInstruction], int]:
        """对指令列表执行常量传播

        Returns:
            (优化后的指令列表, 变换次数)
        """
        constants: Dict[str, str] = {}  # var -> const_value
        changes = 0

        for instr in instructions:
            if instr.eliminated:
                continue

            # 替换操作数中的已知常量
            if instr.src1 and instr.src1 in constants:
                instr.src1 = constants[instr.src1]
                changes += 1
            if instr.src2 and instr.src2 in constants:
                instr.src2 = constants[instr.src2]
                changes += 1

            # 如果是赋值 x = const，记录常量映射
            dest = instr.get_defined_var()
            if dest:
                # 先清除旧的常量映射（如果变量被重新定义）
                if dest in constants:
                    del constants[dest]

                if instr.op == "=" and self._is_const(instr.src1):
                    constants[dest] = instr.src1

        return instructions, changes

    @staticmethod
    def _is_const(val: str) -> bool:
        if val is None:
            return False
        try:
            int(val)
            return True
        except (ValueError, TypeError):
            return False


# ============================================================
# 优化 3: 死代码消除 (Dead Code Elimination)
# ============================================================

class DeadCodeEliminator:
    """
    死代码消除：删除计算结果从未被使用的指令。

    策略：
    1. 标记所有被使用的变量
    2. 删除定义了未使用变量的指令（无副作用时）
    """

    def eliminate(self, instructions: List[IRInstruction]) -> Tuple[List[IRInstruction], int]:
        """对指令列表执行死代码消除

        Returns:
            (优化后的指令列表, 变换次数)
        """
        changes = 0

        # 反向扫描：从后往前，构建使用集合
        used_vars: Set[str] = set()
        live_instructions: List[bool] = [True] * len(instructions)

        # 第一遍：从后往前扫描，标记所有被使用的变量
        for i in range(len(instructions) - 1, -1, -1):
            instr = instructions[i]
            if instr.eliminated:
                continue

            dest = instr.get_defined_var()

            # 检查目标变量是否被使用
            if dest and dest not in used_vars:
                # 如果指令没有副作用，标记为死代码
                if not self._has_side_effects(instr):
                    live_instructions[i] = False
                    continue

            # 标记使用到的变量
            for var in instr.get_used_vars():
                used_vars.add(var)

            # 如果指令定义了变量且有副作用，目标变量也"被使用"
            if dest and self._has_side_effects(instr):
                used_vars.add(dest)

        # 第二遍：消除死代码
        for i, instr in enumerate(instructions):
            if not live_instructions[i] and not instr.eliminated:
                instr.eliminated = True
                changes += 1

        return instructions, changes

    @staticmethod
    def _has_side_effects(instr: IRInstruction) -> bool:
        """判断指令是否有副作用"""
        # return、goto、if、call 等有副作用
        return instr.op in ("return", "goto", "if", "ifFalse", "ifTrue", "call", "param")


# ============================================================
# 优化 4: 公共子表达式消除 (CSE)
# ============================================================

class CSEOptimizer:
    """
    公共子表达式消除：如果一个表达式之前已经计算过，且操作数未改变，则复用。

    例如:
      a = b + c       →  a = b + c
      d = b + c       →  d = a      (复用 a)
    """

    def eliminate(self, instructions: List[IRInstruction]) -> Tuple[List[IRInstruction], int]:
        """对指令列表执行 CSE

        Returns:
            (优化后的指令列表, 变换次数)
        """
        # 已计算的表达式: (op, src1, src2) -> dest_var
        available: Dict[Tuple[str, str, str], str] = {}
        changes = 0

        for instr in instructions:
            if instr.eliminated:
                continue

            dest = instr.get_defined_var()

            # 检查是否是可消除的公共子表达式
            if instr.op in ("+", "-", "*", "/", "<", ">", "<=", ">=", "==", "!="):
                expr_key = (instr.op, instr.src1, instr.src2)

                if expr_key in available:
                    # 找到公共子表达式！替换为赋值
                    prev_var = available[expr_key]
                    instr.op = "="
                    instr.src1 = prev_var
                    instr.src2 = None
                    changes += 1

                    # 更新映射：dest 现在也代表这个表达式
                    if dest:
                        # 将所有指向旧变量的映射也更新为指向新变量
                        # （简化处理：只更新当前表达式的映射）
                        available[expr_key] = dest
                else:
                    # 记录新表达式
                    if dest:
                        available[expr_key] = dest

            # 如果变量被重新定义（通过其他方式），清除相关映射
            if dest:
                keys_to_remove = []
                for key, val in available.items():
                    if val == dest and key != (instr.op, instr.src1, instr.src2):
                        keys_to_remove.append(key)
                for key in keys_to_remove:
                    del available[key]

            # 如果使用了某个变量，检查是否有表达式依赖于该变量的旧值
            # （简化处理：在赋值目标变量时清除依赖该变量的表达式）
            if dest:
                keys_to_remove = []
                for key in available:
                    if key[1] == dest or key[2] == dest:
                        if available[key] != dest:
                            keys_to_remove.append(key)
                for key in keys_to_remove:
                    del available[key]

        return instructions, changes


# ============================================================
# 优化 5: 活跃变量分析 (Live Variable Analysis)
# ============================================================

class LiveVariableAnalyzer:
    """
    活跃变量分析：在每个程序点确定哪些变量在后续可能被使用。

    类型：反向数据流分析
    方程：
      OUT[B] = ∪ IN[S]        (S ∈ succ(B))
      IN[B]  = USE[B] ∪ (OUT[B] - DEF[B])
    """

    def analyze(self, blocks: List[IRBlock]) -> Dict[str, Dict[str, Set[str]]]:
        """执行活跃变量分析

        Returns:
            每个块的 IN 和 OUT 信息
        """
        in_sets: Dict[str, Set[str]] = {b.label: set() for b in blocks}
        out_sets: Dict[str, Set[str]] = {b.label: set() for b in blocks}

        changed = True
        iteration = 0
        while changed:
            changed = False
            iteration += 1

            for block in reversed(blocks):
                # OUT[B] = ∪ IN[S]
                new_out = set()
                for succ in block.successors:
                    new_out |= in_sets[succ.label]

                # IN[B] = USE[B] ∪ (OUT[B] - DEF[B])
                use = block.use_vars()
                defs = block.def_vars()
                new_in = use | (new_out - defs)

                if new_in != in_sets[block.label] or new_out != out_sets[block.label]:
                    in_sets[block.label] = new_in
                    out_sets[block.label] = new_out
                    changed = True

        print(f"  [活跃变量分析] 迭代 {iteration} 轮收敛")
        return {"in": in_sets, "out": out_sets}


# ============================================================
# 优化器主类
# ============================================================

class Optimizer:
    """编译器优化器，整合所有优化 pass"""

    def __init__(self):
        self.constant_folder = ConstantFolder()
        self.constant_propagator = ConstantPropagator()
        self.dead_code_eliminator = DeadCodeEliminator()
        self.cse_optimizer = CSEOptimizer()
        self.live_var_analyzer = LiveVariableAnalyzer()

    def optimize(self, instructions: List[IRInstruction],
                 max_iterations: int = 5) -> List[IRInstruction]:
        """执行所有优化 pass，迭代直到不再有改进

        Args:
            instructions: 原始指令列表
            max_iterations: 最大迭代次数

        Returns:
            优化后的指令列表
        """
        instructions = deepcopy(instructions)
        total_changes = 0

        for iteration in range(max_iterations):
            changes = 0

            # Pass 1: 常量传播（先传播，为折叠创造条件）
            _, c1 = self.constant_propagator.propagate(instructions)
            changes += c1

            # Pass 2: 常量折叠
            _, c2 = self.constant_folder.fold(instructions)
            changes += c2

            # Pass 3: CSE
            _, c3 = self.cse_optimizer.eliminate(instructions)
            changes += c3

            # Pass 4: 死代码消除
            _, c4 = self.dead_code_eliminator.eliminate(instructions)
            changes += c4

            total_changes += changes

            if changes == 0:
                print(f"  [优化器] 第 {iteration + 1} 轮迭代，无新变换，收敛")
                break
            else:
                print(f"  [优化器] 第 {iteration + 1} 轮迭代，{changes} 次变换")

        print(f"  [优化器] 总计 {total_changes} 次变换")
        return instructions

    def print_ir(self, title: str, instructions: List[IRInstruction]):
        """打印指令列表"""
        print(f"\n  {title}")
        print(f"  {'─' * 50}")
        for instr in instructions:
            if not instr.eliminated:
                print(f"    {instr}")
            else:
                print(f"    {instr}")


# ============================================================
# 辅助函数：从文本创建指令
# ============================================================

def create_instructions_from_text(text: str) -> List[IRInstruction]:
    """从简化的文本格式创建指令列表

    支持的格式：
      x = 5
      y = x + 3
      z = x * y
      if t goto L1
      goto L1
      return x
      # 注释
    """
    instructions = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('//'):
            continue

        # 去掉行首标签
        label = None
        if re.match(r'^L\d+:', line):
            parts = line.split(':', 1)
            label = parts[0].strip()
            line = parts[1].strip()

        # 解析 x = y op z
        m = re.match(r'^(\w+)\s*=\s*(\S+)\s*([+\-*/<>=!]+)\s*(\S+)$', line)
        if m:
            dest, src1, op, src2 = m.groups()
            instructions.append(IRInstruction(op, dest, src1, src2, label))
            continue

        # 解析 x = y
        m = re.match(r'^(\w+)\s*=\s*(.+)$', line)
        if m:
            dest, src = m.groups()
            instructions.append(IRInstruction("=", dest, src.strip(), None, label))
            continue

        # 解析 goto L1
        m = re.match(r'^goto\s+(\w+)$', line)
        if m:
            target = m.group(1)
            instructions.append(IRInstruction("goto", target, None, None, label))
            continue

        # 解析 if x goto L1
        m = re.match(r'^if\s+(\w+)\s+goto\s+(\w+)$', line)
        if m:
            cond, target = m.groups()
            instructions.append(IRInstruction("if", target, cond, None, label))
            continue

        # 解析 ifFalse x goto L1
        m = re.match(r'^ifFalse\s+(\w+)\s+goto\s+(\w+)$', line)
        if m:
            cond, target = m.groups()
            instructions.append(IRInstruction("ifFalse", target, cond, None, label))
            continue

        # 解析 return x
        m = re.match(r'^return\s+(.+)$', line)
        if m:
            val = m.group(1)
            instructions.append(IRInstruction("return", val, None, None, label))
            continue

        print(f"  [警告] 无法解析行: {line}")

    return instructions


# ============================================================
# 主程序：演示
# ============================================================

def demo_constant_folding():
    """演示常量折叠"""
    print("\n" + "━" * 60)
    print("  演示 1: 常量折叠 (Constant Folding)")
    print("━" * 60)

    text = """
    x = 3 + 5
    y = x * 2
    z = 10 / 2
    w = 4 - 1
    a = z + w
    """

    print("\n  原始代码:")
    for line in text.strip().split('\n'):
        print(f"    {line.strip()}")

    instrs = create_instructions_from_text(text)
    optimizer = Optimizer()

    print("\n  优化前:")
    optimizer.print_ir("指令列表", instrs)

    optimized = optimizer.optimize(instrs)

    print("\n  优化后:")
    optimizer.print_ir("指令列表", optimized)


def demo_constant_propagation():
    """演示常量传播"""
    print("\n" + "━" * 60)
    print("  演示 2: 常量传播 (Constant Propagation)")
    print("━" * 60)

    text = """
    x = 5
    y = x + 3
    z = x * 2
    w = y + z
    a = x + y + z
    """

    print("\n  原始代码:")
    for line in text.strip().split('\n'):
        print(f"    {line.strip()}")

    instrs = create_instructions_from_text(text)
    optimizer = Optimizer()

    print("\n  优化前:")
    optimizer.print_ir("指令列表", instrs)

    optimized = optimizer.optimize(instrs)

    print("\n  优化后:")
    optimizer.print_ir("指令列表", optimized)


def demo_dead_code_elimination():
    """演示死代码消除"""
    print("\n" + "━" * 60)
    print("  演示 3: 死代码消除 (Dead Code Elimination)")
    print("━" * 60)

    text = """
    x = 10
    y = x * 2
    z = y + 1
    w = 42
    u = z * 3
    v = w + 1
    return y
    """

    print("\n  原始代码:")
    for line in text.strip().split('\n'):
        print(f"    {line.strip()}")

    instrs = create_instructions_from_text(text)
    optimizer = Optimizer()

    print("\n  优化前:")
    optimizer.print_ir("指令列表", instrs)

    optimized = optimizer.optimize(instrs)

    print("\n  优化后:")
    optimizer.print_ir("指令列表", optimized)


def demo_cse():
    """演示公共子表达式消除"""
    print("\n" + "━" * 60)
    print("  演示 4: 公共子表达式消除 (CSE)")
    print("━" * 60)

    text = """
    a = 3
    b = 5
    c = a + b
    d = a + b
    e = c + d
    """

    print("\n  原始代码:")
    for line in text.strip().split('\n'):
        print(f"    {line.strip()}")

    instrs = create_instructions_from_text(text)
    optimizer = Optimizer()

    print("\n  优化前:")
    optimizer.print_ir("指令列表", instrs)

    optimized = optimizer.optimize(instrs)

    print("\n  优化后:")
    optimizer.print_ir("指令列表", optimized)


def demo_combined_optimization():
    """演示综合优化"""
    print("\n" + "━" * 60)
    print("  演示 5: 综合优化（多 pass 组合）")
    print("━" * 60)

    # 模拟以下代码:
    # x = 3 + 5          → 常量折叠 → x = 8
    # y = x + 2          → 常量传播+折叠 → y = 10
    # z = x * 2          → 常量传播+折叠 → z = 16
    # w = y + z          → 常量传播+折叠 → w = 26
    # a = w + 1          → 常量传播+折叠 → a = 27
    # b = a * 0          → 常量折叠 → b = 0
    # c = x + y + z      → 常量传播+折叠 → c = 34
    # d = b + c          → 常量传播+折叠 → d = 34
    # e = 999            → 死代码（未使用）
    # return d           → return 34

    text = """
    x = 3 + 5
    y = x + 2
    z = x * 2
    w = y + z
    a = w + 1
    b = a * 0
    c = x + y + z
    d = b + c
    e = 999
    return d
    """

    print("\n  模拟代码（等价于）:")
    print("    x = 3 + 5       # 常量折叠 → 8")
    print("    y = x + 2       # 常量传播+折叠 → 10")
    print("    z = x * 2       # 常量传播+折叠 → 16")
    print("    w = y + z       # 常量传播+折叠 → 26")
    print("    a = w + 1       # 常量传播+折叠 → 27")
    print("    b = a * 0       # 常量折叠 → 0")
    print("    c = x + y + z   # 常量传播+折叠 → 34")
    print("    d = b + c       # 常量传播+折叠 → 34")
    print("    e = 999         # 死代码消除")
    print("    return d        # return 34")

    instrs = create_instructions_from_text(text)
    optimizer = Optimizer()

    print("\n  优化前:")
    optimizer.print_ir("指令列表", instrs)

    optimized = optimizer.optimize(instrs)

    print("\n  优化后:")
    optimizer.print_ir("指令列表", optimized)


def demo_live_variable_analysis():
    """演示活跃变量分析"""
    print("\n" + "━" * 60)
    print("  演示 6: 活跃变量分析 (Live Variable Analysis)")
    print("━" * 60)

    # 构建简单的 CFG：
    # BB1: a = 1; b = 2
    # BB2: c = a + b; d = a - b; if c goto BB4 else BB3
    # BB3: a = d + 1; goto BB2
    # BB4: return d

    print("\n  程序:")
    print("    BB1: a = 1; b = 2")
    print("    BB2: c = a + b; d = a - b; if c goto BB4 else BB3")
    print("    BB3: a = d + 1; goto BB2")
    print("    BB4: return d")

    bb1 = IRBlock("BB1")
    bb1.instructions = [
        IRInstruction("=", "a", "1"),
        IRInstruction("=", "b", "2"),
        IRInstruction("goto", "BB2"),
    ]

    bb2 = IRBlock("BB2")
    bb2.instructions = [
        IRInstruction("+", "c", "a", "b"),
        IRInstruction("-", "d", "a", "b"),
        IRInstruction("if", "BB4", "c"),
    ]

    bb3 = IRBlock("BB3")
    bb3.instructions = [
        IRInstruction("+", "a", "d", "1"),
        IRInstruction("goto", "BB2"),
    ]

    bb4 = IRBlock("BB4")
    bb4.instructions = [
        IRInstruction("return", "d"),
    ]

    # 建立边
    bb1.successors = [bb2]
    bb2.predecessors = [bb1, bb3]
    bb2.successors = [bb4, bb3]
    bb3.predecessors = [bb2]
    bb3.successors = [bb2]
    bb4.predecessors = [bb2]

    blocks = [bb1, bb2, bb3, bb4]

    analyzer = LiveVariableAnalyzer()
    result = analyzer.analyze(blocks)

    print("\n  分析结果:")
    for block in blocks:
        defs = block.def_vars()
        uses = block.use_vars()
        in_vars = sorted(result["in"][block.label])
        out_vars = sorted(result["out"][block.label])

        print(f"\n    {block.label}:")
        print(f"      DEF  = {{{', '.join(sorted(defs)) or '∅'}}}")
        print(f"      USE  = {{{', '.join(sorted(uses)) or '∅'}}}")
        print(f"      IN   = {{{', '.join(in_vars) or '∅'}}}")
        print(f"      OUT  = {{{', '.join(out_vars) or '∅'}}}")

    print("\n  解读:")
    print("    IN(BB2) = {a, b, d}")
    print("    → 进入 BB2 时，a, b, d 都可能在后续被使用")
    print("    → 寄存器分配器应确保 a, b, d 在进入 BB2 时都在寄存器中")
    print("    OUT(BB3) = {a, b}")
    print("    → 离开 BB3 时，只有 a 和 b 是活跃的")
    print("    → d 在 BB3 重新定义后，旧值不再需要（已在 BB3 中被覆盖）")


def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║              代码优化器 - 完整演示                      ║")
    print("╚══════════════════════════════════════════════════════════╝")

    print("""
  本演示展示了编译器中常用的代码优化技术：
  1. 常量折叠 - 编译时计算常量表达式
  2. 常量传播 - 用常量值替换变量
  3. 死代码消除 - 删除未使用的计算
  4. 公共子表达式消除 - 复用已计算的表达式
  5. 活跃变量分析 - 确定变量的活跃范围
  6. 综合优化 - 多 pass 组合的效果
    """)

    demo_constant_folding()
    demo_constant_propagation()
    demo_dead_code_elimination()
    demo_cse()
    demo_combined_optimization()
    demo_live_variable_analysis()

    print("\n\n" + "=" * 60)
    print("  总结")
    print("=" * 60)
    print("""
  优化 pass 的执行顺序很重要：
    1. 常量传播（为折叠创造条件）
    2. 常量折叠（消除传播后的常量表达式）
    3. CSE（消除重复计算）
    4. 死代码消除（清理无用代码）

  这些 pass 通常需要迭代执行多轮，直到不再有改进（不动点）。
  本演示中的优化器会自动迭代直到收敛。

  实际编译器（如 LLVM、GCC）的优化流程要复杂得多：
    - 使用 SSA 形式简化数据流分析
    - 使用支配树优化分析效率
    - 包含数十甚至上百个优化 pass
    - 使用 pass manager 按依赖关系排序执行
    """)


if __name__ == "__main__":
    main()
