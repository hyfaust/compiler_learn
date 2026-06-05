"""
控制流图（CFG）构建器
=====================

从三地址码构建控制流图，包括：
  1. 基本块划分（Leader 算法）
  2. CFG 数据结构（前驱/后继关系）
  3. 支配树计算（迭代算法）
  4. ASCII 可视化输出

使用方法:
  python cfg_builder.py
"""

from typing import Dict, List, Set, Optional


# ============================================================
# 数据结构
# ============================================================

class Instruction:
    """三地址码指令"""

    def __init__(self, label: str, op: str, args: list):
        """
        Args:
            label: 指令标签（如 "L1"），为空表示延续前一条
            op:    操作符（如 "=", "+", "goto", "if", "ifFalse", "return"）
            args:  操作数列表
        """
        self.label = label
        self.op = op
        self.args = args

    def __repr__(self):
        parts = []
        if self.label:
            parts.append(f"{self.label}:")
        parts.append(self.op)
        parts.extend(str(a) for a in self.args)
        return " ".join(parts)

    def is_jump(self) -> bool:
        return self.op in ("goto", "if", "ifFalse", "ifTrue", "return")

    def get_jump_targets(self) -> List[str]:
        """获取跳转目标标签"""
        if self.op == "goto":
            return [self.args[0]]
        elif self.op in ("if", "ifFalse", "ifTrue"):
            # if condition goto target
            return [self.args[-1]]  # 最后一个参数是目标标签
        return []

    def defines(self) -> Optional[str]:
        """获取定义的变量（赋值语句的目标）"""
        if self.op == "=" and len(self.args) >= 2:
            return self.args[0]
        return None

    def uses(self) -> List[str]:
        """获取使用的变量"""
        used = []
        if self.op == "=":
            # x = expr → 使用 expr 中的变量
            used.extend(self._extract_vars(self.args[1:]))
        elif self.op in ("+", "-", "*", "/", "<", ">", "<=", ">=", "==", "!="):
            used.extend(self._extract_vars(self.args))
        elif self.op in ("if", "ifFalse", "ifTrue"):
            used.extend(self._extract_vars(self.args[:-1]))
        elif self.op == "return":
            used.extend(self._extract_vars(self.args))
        return used

    @staticmethod
    def _extract_vars(args) -> List[str]:
        """从参数列表中提取变量名（排除常量和标签）"""
        vars_found = []
        for a in args:
            s = str(a)
            if s.isdigit() or (s.startswith('-') and s[1:].isdigit()):
                continue  # 跳过整数常量
            try:
                float(s)
                continue  # 跳过浮点常量
            except ValueError:
                pass
            if s.startswith('"') or s.startswith("'"):
                continue  # 跳过字符串常量
            vars_found.append(s)
        return vars_found


class BasicBlock:
    """基本块"""

    _counter = 0

    def __init__(self, label: str = None):
        if label is None:
            label = f"BB{BasicBlock._counter}"
            BasicBlock._counter += 1
        self.label = label
        self.instructions: List[Instruction] = []
        self.successors: List['BasicBlock'] = []
        self.predecessors: List['BasicBlock'] = []
        self.dom: Set[str] = set()        # 支配集合
        self.idom: Optional['BasicBlock'] = None  # 直接支配者

    def __repr__(self):
        return f"BasicBlock({self.label})"

    def def_vars(self) -> Set[str]:
        """本块中定义的变量集合"""
        defs = set()
        for instr in self.instructions:
            d = instr.defines()
            if d:
                defs.add(d)
        return defs

    def use_vars(self) -> Set[str]:
        """本块中使用且在使用前未定义的变量集合"""
        used = set()
        defined = set()
        for instr in self.instructions:
            for u in instr.uses():
                if u not in defined:
                    used.add(u)
            d = instr.defines()
            if d:
                defined.add(d)
        return used


class CFG:
    """控制流图"""

    def __init__(self):
        self.entry: Optional[BasicBlock] = None
        self.blocks: List[BasicBlock] = []
        self.label_to_block: Dict[str, BasicBlock] = {}

    def add_block(self, block: BasicBlock):
        self.blocks.append(block)
        if block.label:
            self.label_to_block[block.label] = block

    def get_block_by_label(self, label: str) -> Optional[BasicBlock]:
        return self.label_to_block.get(label)

    def add_edge(self, from_block: BasicBlock, to_block: BasicBlock):
        if to_block not in from_block.successors:
            from_block.successors.append(to_block)
        if from_block not in to_block.predecessors:
            to_block.predecessors.append(from_block)


# ============================================================
# 三地址码解析
# ============================================================

def parse_tac(text: str) -> List[Instruction]:
    """将文本形式的三地址码解析为指令列表

    支持的格式：
      L1: x = y + z     带标签的赋值
      x = y + z          不带标签的赋值
      L2: goto L1        无条件跳转
      if x < 10 goto L3  条件跳转
      ifFalse t1 goto L4 条件为假跳转
      return x           返回
    """
    instructions = []
    for line in text.strip().split('\n'):
        line = line.strip()
        if not line or line.startswith('#') or line.startswith('//'):
            continue

        label = ""
        # 检查是否有标签（格式：L1: ...）
        if ':' in line:
            parts = line.split(':', 1)
            # 判断第一部分是否像标签（不含空格或只含一个标识符）
            possible_label = parts[0].strip()
            if possible_label and ' ' not in possible_label:
                label = possible_label
                line = parts[1].strip()

        # 解析指令体
        tokens = line.split()
        if not tokens:
            continue

        op = tokens[0]
        args = tokens[1:]

        # 解析 "x = y op z" 形式的赋值
        if len(tokens) >= 3 and tokens[1] == '=':
            target = tokens[0]
            if len(tokens) == 3:
                # x = y
                instr = Instruction(label, "=", [target, tokens[2]])
            elif len(tokens) == 5:
                # x = y + z
                instr = Instruction(label, tokens[3], [target, tokens[2], tokens[4]])
            else:
                # x = y (或更复杂的表达式，简化处理)
                instr = Instruction(label, "=", [target] + tokens[2:])
            instructions.append(instr)
        elif op == 'goto':
            instr = Instruction(label, "goto", [args[0]])
            instructions.append(instr)
        elif op in ('if', 'ifFalse', 'ifTrue'):
            # if cond goto label  或  ifFalse cond goto label
            # 找到 "goto" 关键字的位置
            try:
                goto_idx = args.index('goto')
                cond_args = args[:goto_idx]
                target = args[goto_idx + 1]
                instr = Instruction(label, op, list(cond_args) + [target])
            except (ValueError, IndexError):
                instr = Instruction(label, op, list(args))
            instructions.append(instr)
        elif op == 'return':
            instr = Instruction(label, "return", list(args))
            instructions.append(instr)
        else:
            # 未知指令，作为赋值处理
            instr = Instruction(label, "=", [op] + list(args))
            instructions.append(instr)

    return instructions


# ============================================================
# 基本块划分
# ============================================================

def build_cfg(instructions: List[Instruction]) -> CFG:
    """从指令列表构建控制流图

    算法步骤：
    1. 确定 leader 指令
    2. 根据 leader 划分基本块
    3. 添加基本块之间的边
    """
    if not instructions:
        return CFG()

    # 标记指令的索引映射
    label_to_index: Dict[str, int] = {}
    for i, instr in enumerate(instructions):
        if instr.label:
            label_to_index[instr.label] = i

    # Step 1: 确定 leader
    leaders = set()
    leaders.add(0)  # 规则 a: 第一条指令是 leader

    for i, instr in enumerate(instructions):
        if instr.is_jump():
            # 规则 b: 跳转目标是 leader
            for target in instr.get_jump_targets():
                if target in label_to_index:
                    leaders.add(label_to_index[target])
            # 规则 c: 跳转之后的指令是 leader
            if i + 1 < len(instructions):
                leaders.add(i + 1)

    leaders = sorted(leaders)

    # Step 2: 划分基本块
    cfg = CFG()
    blocks_map: Dict[int, BasicBlock] = {}  # leader 索引 -> 基本块

    for idx, leader_idx in enumerate(leaders):
        block = BasicBlock()
        # 确定基本块的范围：从当前 leader 到下一个 leader 之前
        end = leaders[idx + 1] if idx + 1 < len(leaders) else len(instructions)
        block.instructions = instructions[leader_idx:end]
        cfg.add_block(block)
        blocks_map[leader_idx] = block

    if cfg.blocks:
        cfg.entry = cfg.blocks[0]

    # Step 3: 添加边
    for idx, leader_idx in enumerate(leaders):
        block = blocks_map[leader_idx]
        if not block.instructions:
            continue

        last_instr = block.instructions[-1]

        if last_instr.op == 'return':
            # return 指令没有后继（或连接到 exit）
            pass
        elif last_instr.op == 'goto':
            # 无条件跳转：连接到目标块
            target_label = last_instr.args[0]
            target_block = None
            for b in cfg.blocks:
                if b.label and b.label == target_label:
                    target_block = b
                    break
            if target_block:
                cfg.add_edge(block, target_block)
        elif last_instr.op in ('if', 'ifFalse', 'ifTrue'):
            # 条件跳转：连接到目标块和下一个块（fall-through）
            target_label = last_instr.args[-1]
            target_block = None
            for b in cfg.blocks:
                if b.label and b.label == target_label:
                    target_block = b
                    break
            if target_block:
                cfg.add_edge(block, target_block)
            # fall-through 到下一个块
            if idx + 1 < len(leaders):
                next_block = blocks_map[leaders[idx + 1]]
                cfg.add_edge(block, next_block)
        else:
            # 普通指令：顺序执行到下一个块
            if idx + 1 < len(leaders):
                next_block = blocks_map[leaders[idx + 1]]
                cfg.add_edge(block, next_block)

    return cfg


# ============================================================
# 支配树计算
# ============================================================

def compute_dominators(cfg: CFG) -> None:
    """计算每个节点的支配集合

    使用迭代算法：
    1. 初始化 Dom(entry) = {entry}
    2. 对于其他节点 n: Dom(n) = {所有节点}
    3. 迭代: Dom(n) = {n} ∪ ∩(Dom(p) for p in pred(n))
    4. 直到所有 Dom 集合不再变化
    """
    if not cfg.entry:
        return

    all_labels = set(b.label for b in cfg.blocks)

    # 初始化
    for block in cfg.blocks:
        if block == cfg.entry:
            block.dom = {cfg.entry.label}
        else:
            block.dom = set(all_labels)

    # 迭代直到不动点
    changed = True
    iteration = 0
    while changed:
        changed = False
        iteration += 1
        for block in cfg.blocks:
            if block == cfg.entry:
                continue

            if block.predecessors:
                # Dom(n) = {n} ∩ ∪(Dom(p) for p in pred(n))
                new_dom = set(block.predecessors[0].dom)
                for pred in block.predecessors[1:]:
                    new_dom &= pred.dom
                new_dom.add(block.label)
            else:
                new_dom = {block.label}

            if new_dom != block.dom:
                block.dom = new_dom
                changed = True

    print(f"  支配集合计算完成，迭代 {iteration} 轮")


def compute_idom(cfg: CFG) -> None:
    """计算直接支配者（Immediate Dominator）

    idom(n) = d, 当且仅当:
      - d dom n 且 d ≠ n
      - 不存在 d' 使得 d dom d' 且 d' dom n
    """
    for block in cfg.blocks:
        if block == cfg.entry:
            block.idom = None
            continue

        # 找到直接支配者：在 Dom(n) - {n} 中，支配关系最强的那个
        dom_candidates = [
            b for b in cfg.blocks
            if b.label in block.dom and b != block
        ]

        idom_candidate = None
        for candidate in dom_candidates:
            is_idom = True
            for other in dom_candidates:
                if other != candidate and candidate.label in other.dom:
                    # candidate 被 other 支配，说明 candidate 不是直接支配者
                    is_idom = False
                    break
            if is_idom:
                idom_candidate = candidate
                break

        block.idom = idom_candidate


def compute_dominance_frontier(cfg: CFG) -> Dict[str, Set[str]]:
    """计算支配边界（Dominance Frontier）

    DF(B) = { n | B 支配 n 的某个前驱，但 B 不严格支配 n }
    即: n ∈ pred(m) 且 B dom m 且 ¬(B dom n 且 B ≠ n)
    """
    df: Dict[str, Set[str]] = {b.label: set() for b in cfg.blocks}

    for block in cfg.blocks:
        if len(block.predecessors) >= 2:
            for pred in block.predecessors:
                runner = pred
                while runner and runner != block.idom:
                    df[runner.label].add(block.label)
                    runner = runner.idom

    return df


# ============================================================
# ASCII 可视化
# ============================================================

def print_cfg(cfg: CFG) -> None:
    """打印 CFG 的 ASCII 可视化"""

    print("=" * 60)
    print("  控制流图 (CFG) ASCII 可视化")
    print("=" * 60)

    # 基本块列表
    print("\n【基本块】")
    for block in cfg.blocks:
        is_entry = " ← entry" if block == cfg.entry else ""
        print(f"  {block.label}{is_entry}:")
        for instr in block.instructions:
            print(f"    {instr}")

    # 边
    print("\n【边 (Edges)】")
    for block in cfg.blocks:
        for succ in block.successors:
            print(f"  {block.label} → {succ.label}")

    # 前驱/后继
    print("\n【前驱/后继关系】")
    for block in cfg.blocks:
        preds = [p.label for p in block.predecessors]
        succs = [s.label for s in block.successors]
        print(f"  {block.label}:")
        print(f"    pred = {{{', '.join(preds) if preds else '∅'}}}")
        print(f"    succ = {{{', '.join(succs) if succs else '∅'}}}")


def print_dominator_tree(cfg: CFG) -> None:
    """打印支配树的 ASCII 表示"""

    print("\n" + "=" * 60)
    print("  支配树 (Dominator Tree)")
    print("=" * 60)

    # 打印支配集合
    print("\n【支配集合 Dom(n)】")
    for block in cfg.blocks:
        dom_str = ", ".join(sorted(block.dom))
        print(f"  Dom({block.label}) = {{{dom_str}}}")

    # 打印直接支配者
    print("\n【直接支配者 idom(n)】")
    for block in cfg.blocks:
        if block == cfg.entry:
            print(f"  idom({block.label}) = (entry, 无)")
        else:
            idom_label = block.idom.label if block.idom else "None"
            print(f"  idom({block.label}) = {idom_label}")

    # 构建支配树的子节点映射
    children: Dict[str, List[str]] = {b.label: [] for b in cfg.blocks}
    for block in cfg.blocks:
        if block.idom:
            children[block.idom.label].append(block.label)

    # 打印树形结构
    print("\n【支配树结构】")
    if cfg.entry:
        print_tree_node(cfg.entry.label, children, "", True)

    # 打印支配边界
    df = compute_dominance_frontier(cfg)
    print("\n【支配边界 DF(n)】")
    for block in cfg.blocks:
        frontier = sorted(df.get(block.label, set()))
        frontier_str = ", ".join(frontier) if frontier else "∅"
        print(f"  DF({block.label}) = {{{frontier_str}}}")


def print_tree_node(label: str, children: Dict[str, List[str]],
                    prefix: str, is_last: bool):
    """递归打印树节点"""
    connector = "└── " if is_last else "├── "
    print(f"  {prefix}{connector}{label}")

    child_prefix = prefix + ("    " if is_last else "│   ")
    node_children = children.get(label, [])
    for i, child in enumerate(node_children):
        print_tree_node(child, children, child_prefix, i == len(node_children) - 1)


def print_simple_cfg_diagram(cfg: CFG) -> None:
    """打印简化的 CFG 图形（适用于简单线性+分支结构）"""

    print("\n" + "=" * 60)
    print("  CFG 简化图示")
    print("=" * 60)
    print()

    # 为每个块分配一个简短的显示内容
    for block in cfg.blocks:
        # 提取关键指令（最多显示 2 行）
        key_instrs = []
        for instr in block.instructions[:3]:
            s = str(instr)
            if len(s) > 25:
                s = s[:22] + "..."
            key_instrs.append(s)

        width = max(len(s) for s in key_instrs) + 4 if key_instrs else 10
        width = max(width, len(block.label) + 4)

        # 打印块头
        print(f"  {'─' * width}")
        # 打印标签
        padding = (width - len(block.label) - 2) // 2
        extra = (width - len(block.label) - 2) % 2
        print(f"  │{' ' * padding}{block.label}{' ' * (padding + extra)}│")
        print(f"  {'┼' + '─' * (width - 2) + '┤'}")
        # 打印指令
        for instr in key_instrs:
            p = (width - len(instr) - 2)
            print(f"  │ {instr}{' ' * (p - 1)}│")
        print(f"  {'─' * width}")

        # 打印连接线
        succs = block.successors
        if not succs:
            pass  # 无后继
        elif len(succs) == 1:
            print(f"       │")
            print(f"       ▼  {succs[0].label}")
        elif len(succs) == 2:
            print(f"      ┌┴─┐")
            print(f"      │  │")
            print(f"      ▼  ▼")
            print(f"    {succs[0].label}  {succs[1].label}")
        print()


# ============================================================
# 活跃变量分析（作为附加功能展示）
# ============================================================

def live_variable_analysis(cfg: CFG) -> Dict[str, Set[str]]:
    """活跃变量分析（反向数据流分析）

    OUT[B] = ∪ IN[S]        (S ∈ succ(B))
    IN[B]  = USE[B] ∪ (OUT[B] - DEF[B])

    Returns:
        每个块的 IN 和 OUT 信息
    """
    in_sets: Dict[str, Set[str]] = {b.label: set() for b in cfg.blocks}
    out_sets: Dict[str, Set[str]] = {b.label: set() for b in cfg.blocks}

    changed = True
    iteration = 0
    while changed:
        changed = False
        iteration += 1

        # 逆序处理（反向分析，从出口到入口）
        for block in reversed(cfg.blocks):
            # OUT[B] = ∪ IN[S]
            new_out = set()
            for succ in block.successors:
                new_out |= in_sets[succ.label]

            # IN[B] = USE[B] ∪ (OUT[B] - DEF[B])
            new_in = block.use_vars() | (new_out - block.def_vars())

            if new_in != in_sets[block.label] or new_out != out_sets[block.label]:
                in_sets[block.label] = new_in
                out_sets[block.label] = new_out
                changed = True

    print(f"\n  活跃变量分析完成，迭代 {iteration} 轮")
    return {"in": in_sets, "out": out_sets}


def print_live_variable_results(cfg: CFG, live_info: Dict[str, Set[str]]) -> None:
    """打印活跃变量分析结果"""

    print("\n" + "=" * 60)
    print("  活跃变量分析结果")
    print("=" * 60)

    in_sets = live_info["in"]
    out_sets = live_info["out"]

    for block in cfg.blocks:
        defs = block.def_vars()
        uses = block.use_vars()
        in_vars = sorted(in_sets[block.label])
        out_vars = sorted(out_sets[block.label])

        print(f"\n  {block.label}:")
        print(f"    DEF  = {{{', '.join(sorted(defs)) or '∅'}}}")
        print(f"    USE  = {{{', '.join(sorted(uses)) or '∅'}}}")
        print(f"    IN   = {{{', '.join(in_vars) or '∅'}}}")
        print(f"    OUT  = {{{', '.join(out_vars) or '∅'}}}")


# ============================================================
# 主程序：演示
# ============================================================

def main():
    print("╔══════════════════════════════════════════════════════════╗")
    print("║          控制流图（CFG）构建器 - 完整演示               ║")
    print("╚══════════════════════════════════════════════════════════╝")

    # 示例 1: 简单的 if-else 结构
    print("\n" + "━" * 60)
    print("  示例 1: if-else 结构")
    print("━" * 60)

    tac_text_1 = """
    L1: x = 0
    L2: t1 = x < 10
    ifFalse t1 goto L6
    L3: t2 = x * 2
    y = t2 + 1
    L4: t3 = x + 1
    x = t3
    goto L2
    L5: z = 0
    L6: return x
    """

    print("\n  输入三地址码:")
    for line in tac_text_1.strip().split('\n'):
        print(f"    {line.strip()}")

    instructions = parse_tac(tac_text_1)

    # 重新设置标签映射
    # 我们需要为每条指令分配正确的标签
    label_map = {}
    for instr in instructions:
        if instr.label:
            # 如果标签是 "L1", "L2" 等格式，记录跳转目标
            pass

    cfg = build_cfg(instructions)
    print_cfg(cfg)
    print_dominator_tree(cfg)
    print_simple_cfg_diagram(cfg)

    # 示例 2: 循环结构
    print("\n\n" + "━" * 60)
    print("  示例 2: 循环结构（计算数组和）")
    print("━" * 60)

    tac_text_2 = """
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
    for line in tac_text_2.strip().split('\n'):
        print(f"    {line.strip()}")

    instructions_2 = parse_tac(tac_text_2)
    cfg_2 = build_cfg(instructions_2)
    print_cfg(cfg_2)
    print_dominator_tree(cfg_2)

    # 活跃变量分析
    live_info = live_variable_analysis(cfg_2)
    print_live_variable_results(cfg_2, live_info)

    # 示例 3: 嵌套 if + 循环
    print("\n\n" + "━" * 60)
    print("  示例 3: 嵌套控制流（绝对值最大值）")
    print("━" * 60)

    tac_text_3 = """
    L0: max = 0
    i = 0
    L1: t1 = i < n
    ifFalse t1 goto L5
    L2: t2 = i * 4
    t3 = a + t2
    val = *t3
    t4 = val < 0
    ifFalse t4 goto L3
    t5 = 0 - val
    val = t5
    L3: t6 = val > max
    ifFalse t6 goto L4
    max = val
    L4: t7 = i + 1
    i = t7
    goto L1
    L5: return max
    """

    print("\n  输入三地址码:")
    for line in tac_text_3.strip().split('\n'):
        print(f"    {line.strip()}")

    instructions_3 = parse_tac(tac_text_3)
    cfg_3 = build_cfg(instructions_3)
    print_cfg(cfg_3)
    print_dominator_tree(cfg_3)

    # 活跃变量分析
    live_info_3 = live_variable_analysis(cfg_3)
    print_live_variable_results(cfg_3, live_info_3)

    # 总结
    print("\n\n" + "=" * 60)
    print("  总结")
    print("=" * 60)
    print("""
  本演示展示了：
  1. 基本块划分 - Leader 算法自动划分三地址码
  2. CFG 构建   - 前驱/后继关系建立
  3. 支配树计算 - 迭代算法求 Dom, idom, DF
  4. 数据流分析 - 活跃变量分析（反向分析）

  这些是编译器优化的基础数据结构和分析工具。
  后续的优化 pass（常量传播、CSE、DCE 等）都建立在这些基础之上。
    """)


if __name__ == "__main__":
    main()
