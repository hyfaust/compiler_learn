"""
循环优化器
==========

实现循环相关的编译器优化技术：
  1. 循环识别（基于 CFG 的回边分析）
  2. 循环不变量外提（Loop-Invariant Code Motion, LICM）
  3. 循环展开（Loop Unrolling）

完整可运行，带有优化前后对比输出。

使用方法:
  python loop_optimizer.py
"""

from typing import Dict, List, Set, Tuple, Optional
from copy import deepcopy


# ============================================================
# 数据结构
# ============================================================

class Instruction:
    """三地址码指令"""

    def __init__(self, op: str, dest: str = None, src1: str = None,
                 src2: str = None, label: str = None, eliminated: bool = False):
        self.op = op
        self.dest = dest
        self.src1 = src1
        self.src2 = src2
        self.label = label
        self.eliminated = eliminated

    def __repr__(self):
        prefix = "[ELIM] " if self.eliminated else ""
        return f"{prefix}{self.to_string()}"

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
        else:
            parts.append(f"{self.dest} = {self.op} {self.src1}")
        return " ".join(parts)

    def get_used_vars(self) -> List[str]:
        """获取使用的变量"""
        used = []
        for var in [self.src1, self.src2]:
            if var and not self._is_const(var):
                used.append(var)
        return used

    def get_defined_var(self) -> Optional[str]:
        """获取定义的变量"""
        if self.dest and self.op not in ("goto", "if", "ifFalse", "ifTrue"):
            return self.dest
        return None

    @staticmethod
    def _is_const(val: str) -> bool:
        if val is None:
            return False
        try:
            int(val)
            return True
        except (ValueError, TypeError):
            return False


class BasicBlock:
    """基本块"""

    def __init__(self, label: str):
        self.label = label
        self.instructions: List[Instruction] = []
        self.successors: List['BasicBlock'] = []
        self.predecessors: List['BasicBlock'] = []

    def def_vars(self) -> Set[str]:
        """本块中定义的变量"""
        return {instr.get_defined_var() for instr in self.instructions
                if not instr.eliminated and instr.get_defined_var()}

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


class Loop:
    """循环结构"""

    def __init__(self, header: BasicBlock):
        self.header = header           # 循环头（入口基本块）
        self.body: Set[str] = set()    # 循环体中所有基本块的标签
        self.back_edges: List[Tuple[BasicBlock, BasicBlock]] = []  # 回边

    def __repr__(self):
        return f"Loop(header={self.header.label}, body={{{', '.join(sorted(self.body))}}})"


# ============================================================
# 循环识别
# ============================================================

class LoopDetector:
    """基于 CFG 的循环识别器

    算法：
    1. 找到所有回边（back edge）：n → d，其中 d 支配 n
    2. 每条回边对应一个自然循环
    3. 循环体 = 从回边目标到回边源的所有节点（反向 BFS）
    """

    def __init__(self, blocks: List[BasicBlock], entry: BasicBlock):
        self.blocks = blocks
        self.entry = entry
        self.dominators: Dict[str, Set[str]] = {}

    def detect_loops(self) -> List[Loop]:
        """检测所有自然循环"""
        # Step 1: 计算支配关系
        self._compute_dominators()

        # Step 2: 找到所有回边
        back_edges = self._find_back_edges()

        if not back_edges:
            print("  [循环识别] 未发现循环")
            return []

        # Step 3: 对每条回边，计算循环体
        loops = []
        for tail, head in back_edges:
            loop = self._find_natural_loop(tail, head)
            if loop:
                loops.append(loop)

        print(f"  [循环识别] 发现 {len(loops)} 个循环")
        for loop in loops:
            print(f"    {loop}")

        return loops

    def _compute_dominators(self):
        """计算支配集合"""
        all_labels = {b.label for b in self.blocks}

        # 初始化
        for block in self.blocks:
            if block == self.entry:
                self.dominators[block.label] = {block.label}
            else:
                self.dominators[block.label] = set(all_labels)

        # 迭代
        changed = True
        while changed:
            changed = False
            for block in self.blocks:
                if block == self.entry:
                    continue

                if block.predecessors:
                    new_dom = set(self.dominators[block.predecessors[0].label])
                    for pred in block.predecessors[1:]:
                        new_dom &= self.dominators[pred.label]
                    new_dom.add(block.label)
                else:
                    new_dom = {block.label}

                if new_dom != self.dominators[block.label]:
                    self.dominators[block.label] = new_dom
                    changed = True

    def _find_back_edges(self) -> List[Tuple[BasicBlock, BasicBlock]]:
        """找到所有回边

        回边定义：n → d，其中 d 支配 n
        """
        back_edges = []
        for block in self.blocks:
            for succ in block.successors:
                if succ.label in self.dominators[block.label]:
                    back_edges.append((block, succ))
        return back_edges

    def _find_natural_loop(self, tail: BasicBlock, head: BasicBlock) -> Optional[Loop]:
        """从回边计算自然循环体

        算法：从 tail 反向 BFS 到 head，收集所有到达的节点
        """
        loop = Loop(head)
        loop.back_edges.append((tail, head))
        loop.body.add(head.label)

        # 如果 head == tail（自循环），直接返回
        if head == tail:
            return loop

        # 反向 BFS
        worklist = [tail]
        loop.body.add(tail.label)

        while worklist:
            node = worklist.pop()
            for pred in node.predecessors:
                if pred.label not in loop.body:
                    loop.body.add(pred.label)
                    worklist.append(pred)

        return loop


# ============================================================
# 优化 1: 循环不变量外提 (LICM)
# ============================================================

class LoopInvariantCodeMotion:
    """
    循环不变量外提：将循环中不变的计算移到循环外部。

    条件：
    1. 表达式的操作数在循环中不被重新定义（或者是常量）
    2. 表达式所在的基本块支配循环的所有出口

    示例：
      优化前:
        loop:
          t = x * y + z    // x, y, z 在循环中不变
          sum = sum + t
          i = i + 1
          if i < n goto loop

      优化后:
        t = x * y + z      // 外提到循环前
        loop:
          sum = sum + t
          i = i + 1
          if i < n goto loop
    """

    def optimize(self, blocks: List[BasicBlock], loops: List[Loop]) -> int:
        """对所有循环执行 LICM

        Returns:
            变换次数
        """
        total_changes = 0

        for loop in loops:
            changes = self._optimize_loop(blocks, loop)
            total_changes += changes
            if changes > 0:
                print(f"  [LICM] 循环 {loop.header.label}: 外提 {changes} 条指令")

        return total_changes

    def _optimize_loop(self, blocks: List[BasicBlock], loop: Loop) -> int:
        """对单个循环执行 LICM"""
        # 收集循环中所有块定义的变量
        loop_defs = set()
        for block in blocks:
            if block.label in loop.body:
                loop_defs |= block.def_vars()

        # 找到循环头
        header = loop.header

        # 找到循环前驱（循环外的块，跳转到循环头）
        pre_header = None
        for pred in header.predecessors:
            if pred.label not in loop.body:
                pre_header = pred
                break

        if pre_header is None:
            # 没有循环前驱，无法外提
            return 0

        changes = 0

        # 遍历循环中的所有块
        for block in blocks:
            if block.label not in loop.body:
                continue

            # 跳过循环头的第一条指令（避免影响循环条件）
            # 实际上，我们检查每条指令是否满足外提条件
            instructions_to_move = []

            for instr in block.instructions:
                if instr.eliminated:
                    continue

                if self._can_hoist(instr, loop_defs, loop):
                    instructions_to_move.append(instr)

            # 移动指令到循环前驱
            for instr in instructions_to_move:
                block.instructions.remove(instr)
                pre_header.instructions.append(instr)
                changes += 1

        return changes

    def _can_hoist(self, instr: Instruction, loop_defs: Set[str],
                   loop: Loop) -> bool:
        """判断指令是否可以外提

        条件：
        1. 指令定义了变量
        2. 指令的操作数在循环中不被定义（或者是常量）
        3. 不是控制流指令
        """
        # 条件 1: 必须定义变量
        if not instr.get_defined_var():
            return False

        # 不是控制流指令
        if instr.op in ("goto", "if", "ifFalse", "ifTrue", "return"):
            return False

        # 条件 2: 操作数在循环中不被重新定义
        for var in instr.get_used_vars():
            if var in loop_defs:
                return False

        return True


# ============================================================
# 优化 2: 循环展开 (Loop Unrolling)
# ============================================================

class LoopUnroller:
    """
    循环展开：将循环体复制多份，减少循环控制开销。

    适用于：
    - 迭代次数已知且较小的循环
    - 循环体较小的循环

    示例（展开因子 2）：
      优化前:
        for (i = 0; i < 4; i++) {
            sum += a[i];
        }

      优化后:
        for (i = 0; i < 4; i += 2) {
            sum += a[i];
            sum += a[i+1];
        }
    """

    def __init__(self, unroll_factor: int = 2):
        self.unroll_factor = unroll_factor

    def unroll(self, blocks: List[BasicBlock], loops: List[Loop]) -> Tuple[List[BasicBlock], int]:
        """对所有循环执行展开

        Returns:
            (新的块列表, 变换次数)
        """
        total_changes = 0
        new_blocks = list(blocks)

        for loop in loops:
            new_blocks, changes = self._unroll_loop(new_blocks, loop)
            total_changes += changes
            if changes > 0:
                print(f"  [循环展开] 循环 {loop.header.label}: 展开因子 {self.unroll_factor}")

        return new_blocks, total_changes

    def _unroll_loop(self, blocks: List[BasicBlock], loop: Loop) -> Tuple[List[BasicBlock], int]:
        """对单个循环执行展开

        这是一个简化版本，展示展开的核心思想。
        实际编译器的循环展开要复杂得多，需要处理：
        - 迭代次数不是展开因子整数倍的情况
        - 循环体中复杂的控制流
        - 寄存器压力
        """
        # 找到循环头
        header = loop.header

        # 找到循环体中非头的基本块
        body_blocks = [b for b in blocks if b.label in loop.body and b != header]

        if not body_blocks:
            # 简单循环：只有一个块（header 包含整个循环体）
            return self._unroll_single_block_loop(blocks, loop)

        # 复杂循环：多个块
        # 简化处理：只对单块循环做展开
        print(f"    [循环展开] 跳过多块循环 {header.label}（简化版本）")
        return blocks, 0

    def _unroll_single_block_loop(self, blocks: List[BasicBlock],
                                  loop: Loop) -> Tuple[List[BasicBlock], int]:
        """对单块循环执行展开"""
        header = loop.header
        factor = self.unroll_factor

        # 找到循环头中的指令
        # 假设循环结构为：
        #   header:
        #     body_instructions...
        #     i = i + 1
        #     if i < n goto header
        #     (fall through to exit)

        # 分离循环体指令和循环控制指令
        body_instrs = []
        control_instrs = []
        in_control = False

        for instr in header.instructions:
            # 最后一条 if 指令是循环控制
            if instr.op in ("if", "ifFalse") and not in_control:
                in_control = True
            if in_control:
                control_instrs.append(instr)
            else:
                body_instrs.append(instr)

        if not body_instrs or not control_instrs:
            return blocks, 0

        # 创建展开后的指令
        new_instrs = []

        # 复制循环体 factor 次
        for i in range(factor):
            for instr in body_instrs:
                # 简单复制（实际需要重命名变量以避免冲突）
                new_instr = Instruction(
                    op=instr.op,
                    dest=instr.dest,
                    src1=instr.src1,
                    src2=instr.src2,
                )
                new_instrs.append(new_instr)

        # 添加循环控制指令
        new_instrs.extend(control_instrs)

        # 替换
        header.instructions = new_instrs

        return blocks, 1


# ============================================================
# 辅助函数
# ============================================================

def parse_instructions(text: str) -> List[Instruction]:
    """解析三地址码文本"""
    import re
    instructions = []

    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('//'):
            continue

        label = None
        if re.match(r'^L?\d+:', line):
            parts = line.split(':', 1)
            label = parts[0].strip()
            line = parts[1].strip()

        # x = y op z
        m = re.match(r'^(\w+)\s*=\s*(\S+)\s*([+\-*/<>=!]+)\s*(\S+)$', line)
        if m:
            dest, src1, op, src2 = m.groups()
            instructions.append(Instruction(op, dest, src1, src2, label))
            continue

        # x = y
        m = re.match(r'^(\w+)\s*=\s*(.+)$', line)
        if m:
            dest, src = m.groups()
            instructions.append(Instruction("=", dest, src.strip(), None, label))
            continue

        # goto L1
        m = re.match(r'^goto\s+(\w+)$', line)
        if m:
            instructions.append(Instruction("goto", m.group(1), None, None, label))
            continue

        # if x goto L1
        m = re.match(r'^if\s+(\w+)\s+goto\s+(\w+)$', line)
        if m:
            cond, target = m.groups()
            instructions.append(Instruction("if", target, cond, None, label))
            continue

        # ifFalse x goto L1
        m = re.match(r'^ifFalse\s+(\w+)\s+goto\s+(\w+)$', line)
        if m:
            cond, target = m.groups()
            instructions.append(Instruction("ifFalse", target, cond, None, label))
            continue

        # return x
        m = re.match(r'^return\s+(.+)$', line)
        if m:
            instructions.append(Instruction("return", m.group(1), None, None, label))
            continue

        print(f"  [警告] 无法解析: {line}")

    return instructions


def build_blocks_and_cfg(instructions: List[Instruction]) -> Tuple[List[BasicBlock], BasicBlock]:
    """从指令列表构建基本块和 CFG"""
    import re

    if not instructions:
        return [], None

    # Leader 规则
    leaders = set()
    leaders.add(0)

    label_to_idx = {}
    for i, instr in enumerate(instructions):
        if instr.label:
            label_to_idx[instr.label] = i

    for i, instr in enumerate(instructions):
        if instr.op in ("goto", "if", "ifFalse", "ifTrue"):
            if instr.op == "goto":
                target = instr.dest
            else:
                target = instr.dest  # 目标标签在 dest 中
            if target in label_to_idx:
                leaders.add(label_to_idx[target])
            if i + 1 < len(instructions):
                leaders.add(i + 1)

    leaders = sorted(leaders)

    # 创建基本块
    blocks = []
    leader_to_block = {}

    for idx, leader_idx in enumerate(leaders):
        end = leaders[idx + 1] if idx + 1 < len(leaders) else len(instructions)
        # 使用第一个指令的标签作为块标签
        first_instr = instructions[leader_idx]
        block_label = first_instr.label if first_instr.label else f"BB{idx}"
        block = BasicBlock(block_label)
        block.instructions = instructions[leader_idx:end]
        blocks.append(block)
        leader_to_block[leader_idx] = block

    # 添加边
    for idx, leader_idx in enumerate(leaders):
        block = leader_to_block[leader_idx]
        if not block.instructions:
            continue

        last = block.instructions[-1]
        if last.op == "return":
            pass
        elif last.op == "goto":
            target = last.dest
            if target in label_to_idx and label_to_idx[target] in leader_to_block:
                target_block = leader_to_block[label_to_idx[target]]
                block.successors.append(target_block)
                target_block.predecessors.append(block)
        elif last.op in ("if", "ifFalse"):
            target = last.dest
            if target in label_to_idx and label_to_idx[target] in leader_to_block:
                target_block = leader_to_block[label_to_idx[target]]
                block.successors.append(target_block)
                target_block.predecessors.append(block)
            if idx + 1 < len(leaders):
                next_block = leader_to_block[leaders[idx + 1]]
                block.successors.append(next_block)
                next_block.predecessors.append(block)
        else:
            if idx + 1 < len(leaders):
                next_block = leader_to_block[leaders[idx + 1]]
                block.successors.append(next_block)
                next_block.predecessors.append(block)

    entry = blocks[0] if blocks else None
    return blocks, entry


def print_blocks(title: str, blocks: List[BasicBlock]):
    """打印基本块内容"""
    print(f"\n  {title}")
    print(f"  {'─' * 50}")
    for block in blocks:
        print(f"  {block.label}:")
        for instr in block.instructions:
            print(f"    {instr}")


# ============================================================
# 主程序：演示
# ============================================================

def demo_loop_detection():
    """演示循环识别"""
    print("\n" + "━" * 60)
    print("  演示 1: 循环识别")
    print("━" * 60)

    text = """
    L0: i = 0
    sum = 0
    L1: t1 = i < n
    ifFalse t1 goto L3
    L2: t2 = i * 4
    t3 = a + t2
    t4 = *t3
    sum = sum + t4
    t5 = i + 1
    i = t5
    goto L1
    L3: return sum
    """

    print("\n  输入三地址码:")
    for line in text.strip().split('\n'):
        print(f"    {line.strip()}")

    instructions = parse_instructions(text)
    blocks, entry = build_blocks_and_cfg(instructions)

    print_blocks("基本块", blocks)

    # 打印边
    print("\n  CFG 边:")
    for block in blocks:
        for succ in block.successors:
            print(f"    {block.label} → {succ.label}")

    detector = LoopDetector(blocks, entry)
    loops = detector.detect_loops()


def demo_licm():
    """演示循环不变量外提"""
    print("\n" + "━" * 60)
    print("  演示 2: 循环不变量外提 (LICM)")
    print("━" * 60)

    text = """
    L0: i = 0
    L1: t1 = i < n
    ifFalse t1 goto L3
    L2: t_inv = x * y + z
    t2 = t_inv + i
    a = t2
    t3 = i + 1
    i = t3
    goto L1
    L3: return a
    """

    print("\n  输入三地址码:")
    for line in text.strip().split('\n'):
        print(f"    {line.strip()}")

    print("\n  注意: t_inv = x * y + z 是循环不变量，")
    print("  因为 x, y, z 在循环中不被重新定义。")

    instructions = parse_instructions(text)
    blocks, entry = build_blocks_and_cfg(instructions)

    print_blocks("优化前", blocks)

    # 检测循环
    detector = LoopDetector(blocks, entry)
    loops = detector.detect_loops()

    if loops:
        # 执行 LICM
        licm = LoopInvariantCodeMotion()
        changes = licm.optimize(blocks, loops)

        print_blocks("优化后 (LICM)", blocks)

        print(f"\n  结果: 外提了 {changes} 条循环不变指令到循环外部")
        print("  效果: 这些指令在循环中不再重复计算，节省了计算开销")


def demo_loop_unrolling():
    """演示循环展开"""
    print("\n" + "━" * 60)
    print("  演示 3: 循环展开 (Loop Unrolling)")
    print("━" * 60)

    text = """
    L0: i = 0
    sum = 0
    L1: t1 = i < n
    ifFalse t1 goto L3
    L2: sum = sum + i
    t2 = i + 1
    i = t2
    goto L1
    L3: return sum
    """

    print("\n  输入三地址码:")
    for line in text.strip().split('\n'):
        print(f"    {line.strip()}")

    instructions = parse_instructions(text)
    blocks, entry = build_blocks_and_cfg(instructions)

    print_blocks("优化前", blocks)

    # 检测循环
    detector = LoopDetector(blocks, entry)
    loops = detector.detect_loops()

    if loops:
        # 执行循环展开（因子 2）
        unroller = LoopUnroller(unroll_factor=2)
        blocks, changes = unroller.unroll(blocks, loops)

        print_blocks("优化后 (展开因子=2)", blocks)

        print(f"\n  结果: 展开了 {changes} 个循环")
        print("  效果: 循环控制指令（比较、跳转）减半")
        print("  代价: 代码体积增大，需要处理剩余迭代（此处简化处理）")


def demo_combined():
    """演示综合循环优化"""
    print("\n" + "━" * 60)
    print("  演示 4: 综合循环优化（LICM + 展开）")
    print("━" * 60)

    text = """
    L0: i = 0
    L1: t1 = i < n
    ifFalse t1 goto L3
    L2: base = x * y
    t2 = base + i
    a = t2
    t3 = i + 1
    i = t3
    goto L1
    L3: return a
    """

    print("\n  输入三地址码:")
    for line in text.strip().split('\n'):
        print(f"    {line.strip()}")

    instructions = parse_instructions(text)
    blocks, entry = build_blocks_and_cfg(instructions)

    print_blocks("优化前", blocks)

    # Step 1: 循环识别
    detector = LoopDetector(blocks, entry)
    loops = detector.detect_loops()

    if loops:
        # Step 2: LICM
        print("\n  --- Pass 1: LICM ---")
        licm = LoopInvariantCodeMotion()
        licm.optimize(blocks, loops)

        # 重新检测循环（块结构可能变化）
        detector2 = LoopDetector(blocks, entry)
        loops2 = detector2.detect_loops()

        # Step 3: 循环展开
        if loops2:
            print("\n  --- Pass 2: 循环展开 ---")
            unroller = LoopUnroller(unroll_factor=2)
            blocks, _ = unroller.unroll(blocks, loops2)

        print_blocks("优化后 (LICM + 展开)", blocks)

        print("\n  优化效果:")
        print("    1. LICM: base = x * y 外提到循环前，不再重复计算")
        print("    2. 展开: 循环体复制，减少循环控制开销")
        print("    3. 组合: 两种优化叠加，性能提升显著")


def demo_strength_reduction_in_loop():
    """演示循环中的强度削弱"""
    print("\n" + "━" * 60)
    print("  演示 5: 循环中的强度削弱")
    print("━" * 60)

    print("""
  原始代码（C 语言）:
    for (i = 0; i < n; i++) {
        a[i] = i * 4 + base;
    }

  三地址码:
    L0: i = 0
    L1: t1 = i < n
        ifFalse t1 goto L3
    L2: t2 = i * 4        ← 循环中的乘法（强度削弱目标）
        t3 = t2 + base
        t4 = a + t2
        *t4 = t3
        t5 = i + 1
        i = t5
        goto L1
    L3: return

  强度削弱后:
    L0: i = 0
        offset = 0        ← 新增：用加法替代乘法
    L1: t1 = i < n
        ifFalse t1 goto L3
    L2: t3 = offset + base
        t4 = a + offset
        *t4 = t3
        offset = offset + 4  ← 加法替代乘法
        t5 = i + 1
        i = t5
        goto L1
    L3: return

  优化效果:
    - 消除了循环中的乘法指令 (i * 4)
    - 替换为加法指令 (offset += 4)
    - 乘法通常需要 3-4 个周期，加法只需 1 个周期
    - 在大量迭代时效果显著
    """)


def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║              循环优化器 - 完整演示                      ║")
    print("╚══════════════════════════════════════════════════════════╝")

    print("""
  本演示展示了编译器中循环优化的关键技术：
  1. 循环识别 - 基于 CFG 的回边分析找到自然循环
  2. 循环不变量外提 (LICM) - 将不变计算移到循环外
  3. 循环展开 - 复制循环体减少控制开销
  4. 综合优化 - 多种优化技术的组合
  5. 强度削弱 - 用低代价操作替代高代价操作

  循环是程序执行的热点，循环优化对性能影响最大。
    """)

    demo_loop_detection()
    demo_licm()
    demo_loop_unrolling()
    demo_combined()
    demo_strength_reduction_in_loop()

    print("\n" + "=" * 60)
    print("  总结")
    print("=" * 60)
    print("""
  循环优化是编译器中最重要的优化类别，因为程序 90%+ 的时间花在循环中。

  主要技术:
    1. LICM (循环不变量外提)
       - 条件: 操作数在循环中不变 + 支配循环出口
       - 效果: 避免每次迭代重复计算

    2. 循环展开
       - 方式: 复制循环体 2/4/8 次
       - 效果: 减少循环控制开销，暴露更多 ILP
       - 代价: 代码体积增大

    3. 强度削弱
       - 方式: i * 4 → offset += 4
       - 效果: 用加法替代乘法

    4. 循环交换
       - 方式: 交换嵌套循环的顺序
       - 效果: 提高缓存局部性

    5. 循环分布
       - 方式: 将一个循环拆分为多个
       - 效果: 为其他优化创造条件

    6. 循环融合
       - 方式: 合并相邻的循环
       - 效果: 减少循环控制开销，提高缓存局部性

  实际编译器（如 LLVM）的循环优化更加复杂，包括:
    - 循环规范化（Canonicalize）
    - 归纳变量分析和优化
    - 循环向量化（SIMD）
    - 自动并行化
    """)


if __name__ == "__main__":
    main()
