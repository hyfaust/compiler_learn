"""
SSA 转换器
==========
本模块将三地址码（TAC）转换为静态单赋值形式（SSA）。
包括：
- 基本块划分
- 支配树构建
- φ 函数插入（基于支配边界）
- 变量重命名

运行方式: python ssa_converter.py
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Dict, List, Set, Tuple
from collections import defaultdict, OrderedDict


# ============================================================
# 三地址码指令
# ============================================================

@dataclass
class TACInstruction:
    """三地址码指令"""
    op: str
    result: Optional[str] = None
    arg1: Optional[str] = None
    arg2: Optional[str] = None
    # SSA 信息（转换后填充）
    ssa_result: Optional[str] = None
    ssa_arg1: Optional[str] = None
    ssa_arg2: Optional[str] = None

    def __str__(self) -> str:
        # 优先显示 SSA 版本
        res = self.ssa_result or self.result
        a1 = self.ssa_arg1 or self.arg1
        a2 = self.ssa_arg2 or self.arg2

        if self.op == "label":
            return f"{self.result}:"
        elif self.op == "goto":
            return f"  goto {self.result}"
        elif self.op == "if":
            return f"  if {a1} goto {self.result}"
        elif self.op == "ifFalse":
            return f"  ifFalse {a1} goto {self.result}"
        elif self.op == "phi":
            args = ", ".join(str(a) for a in (self.ssa_arg1_list if hasattr(self, 'ssa_arg1_list') else [a1, a2]))
            return f"  {res} = φ({args})"
        elif self.op == "=":
            return f"  {res} = {a1}"
        elif self.op == "return":
            if a1:
                return f"  return {a1}"
            return "  return"
        elif a2 is not None:
            return f"  {res} = {a1} {self.op} {a2}"
        elif a1 is not None:
            return f"  {res} = {self.op} {a1}"
        else:
            return f"  {self.op}"


# ============================================================
# 基本块
# ============================================================

@dataclass
class BasicBlock:
    """基本块"""
    label: str
    instructions: List[TACInstruction] = field(default_factory=list)
    predecessors: List[BasicBlock] = field(default_factory=list)
    successors: List[BasicBlock] = field(default_factory=list)
    # 支配信息
    dominators: Set[str] = field(default_factory=set)
    idom: Optional[str] = None  # 直接支配者
    # 支配边界
    dominance_frontier: Set[str] = field(default_factory=set)

    def __str__(self):
        return f"BB({self.label})"

    def __repr__(self):
        return self.__str__()


# ============================================================
# SSA 转换器
# ============================================================

class SSAConverter:
    """
    SSA 转换器
    
    实现经典的 Cytron 算法：
    1. 基本块划分
    2. 控制流图（CFG）构建
    3. 支配树构建（迭代算法）
    4. 支配边界计算
    5. φ 函数插入
    6. 变量重命名
    """

    def __init__(self):
        self.blocks: OrderedDict[str, BasicBlock] = OrderedDict()
        self.entry_block: Optional[BasicBlock] = None
        # 所有变量名（排除临时变量管理用的标签等）
        self.variables: Set[str] = set()
        # 变量定义所在的基本块集合: var_name -> set of block labels
        self.def_sites: Dict[str, Set[str]] = defaultdict(set)
        # SSA 重命名栈: var_name -> [versioned_name, ...]
        self._rename_stacks: Dict[str, List[str]] = defaultdict(list)
        self._version_counter: Dict[str, int] = defaultdict(int)
        # φ 函数参数列表（临时存储）
        self._phi_args: Dict[Tuple[str, str], List[str]] = {}

    # ============================================================
    # 步骤1：基本块划分
    # ============================================================

    def build_basic_blocks(self, instructions: List[TACInstruction]):
        """
        将线性的三地址码序列划分为基本块。
        
        基本块的入口（leader）规则：
        1. 第一条指令是 leader
        2. 跳转目标是 leader
        3. 跳转指令的下一条指令是 leader
        """
        if not instructions:
            return

        # 第一步：识别所有 leader
        leaders: Set[int] = {0}  # 第一条指令是 leader
        label_to_index: Dict[str, int] = {}

        for i, instr in enumerate(instructions):
            if instr.op == "label":
                leaders.add(i)
                label_to_index[instr.result] = i

        for i, instr in enumerate(instructions):
            if instr.op in ("goto", "if", "ifFalse"):
                target = instr.result
                if target in label_to_index:
                    leaders.add(label_to_index[target])
                if i + 1 < len(instructions):
                    leaders.add(i + 1)

        leaders = sorted(leaders)

        # 第二步：根据 leader 划分基本块
        self.blocks.clear()
        for idx, start in enumerate(leaders):
            end = leaders[idx + 1] if idx + 1 < len(leaders) else len(instructions)
            # 确定块名
            block_instrs = instructions[start:end]
            block_label = None
            # 用第一条指令的标签作为块名，否则用编号
            for instr in block_instrs:
                if instr.op == "label":
                    block_label = instr.result
                    break
            if block_label is None:
                block_label = f"BB_{start}"

            block = BasicBlock(label=block_label, instructions=list(block_instrs))
            self.blocks[block_label] = block

        # 设置入口块
        first_key = next(iter(self.blocks))
        self.entry_block = self.blocks[first_key]

        # 第三步：构建 CFG（前驱/后继关系）
        self._build_cfg()

        # 收集变量和定义点
        self._collect_variable_info()

    def _build_cfg(self):
        """构建控制流图"""
        block_list = list(self.blocks.values())

        for i, block in enumerate(block_list):
            if not block.instructions:
                continue
            last_instr = block.instructions[-1]

            if last_instr.op == "goto":
                # 无条件跳转
                target = last_instr.result
                if target in self.blocks:
                    self._add_edge(block, self.blocks[target])
            elif last_instr.op in ("if", "ifFalse"):
                # 条件跳转：跳转目标 + 顺序后继
                target = last_instr.result
                if target in self.blocks:
                    self._add_edge(block, self.blocks[target])
                if i + 1 < len(block_list):
                    self._add_edge(block, block_list[i + 1])
            elif last_instr.op == "return":
                # return 没有后继
                pass
            else:
                # 顺序流：连接到下一个块
                if i + 1 < len(block_list):
                    self._add_edge(block, block_list[i + 1])

    def _add_edge(self, from_block: BasicBlock, to_block: BasicBlock):
        """添加 CFG 边"""
        if to_block not in from_block.successors:
            from_block.successors.append(to_block)
        if from_block not in to_block.predecessors:
            to_block.predecessors.append(from_block)

    def _collect_variable_info(self):
        """收集所有变量名和定义点"""
        self.variables.clear()
        self.def_sites.clear()

        for block_label, block in self.blocks.items():
            for instr in block.instructions:
                # 跳过控制流指令和标签
                if instr.op in ("label", "goto", "if", "ifFalse", "return", "param", "call"):
                    # 但操作数可能引用变量
                    for arg in (instr.arg1, instr.arg2):
                        if arg and self._is_variable(arg):
                            self.variables.add(arg)
                    continue
                # 赋值/运算指令
                if instr.result and self._is_variable(instr.result):
                    self.variables.add(instr.result)
                    self.def_sites[instr.result].add(block_label)
                for arg in (instr.arg1, instr.arg2):
                    if arg and self._is_variable(arg):
                        self.variables.add(arg)

    def _is_variable(self, name: str) -> bool:
        """判断是否是用户变量（非常量、非临时标签）"""
        if not name:
            return False
        # 排除纯数字
        try:
            float(name)
            return False
        except ValueError:
            pass
        # 排除标签
        if name.startswith("L") and name[1:].isdigit():
            return False
        # 排除字符串字面量
        if name.startswith('"') or name.startswith("'"):
            return False
        # 排除 true/false
        if name in ("true", "false"):
            return False
        return True

    # ============================================================
    # 步骤2：支配树构建
    # ============================================================

    def compute_dominators(self):
        """
        使用迭代算法计算每个基本块的支配者集合。
        
        算法：
        - Dom(entry) = {entry}
        - Dom(n) = {n} ∪ (∩ Dom(p) for p in predecessors(n))
        - 迭代直到不动点
        """
        if not self.entry_block:
            return

        all_labels = set(self.blocks.keys())

        # 初始化
        for label, block in self.blocks.items():
            if block == self.entry_block:
                block.dominators = {self.entry_block.label}
            else:
                block.dominators = set(all_labels)

        # 迭代求不动点
        changed = True
        while changed:
            changed = False
            for label, block in self.blocks.items():
                if block == self.entry_block:
                    continue

                if block.predecessors:
                    # 取所有前驱支配者的交集
                    new_dom = set(block.predecessors[0].dominators)
                    for pred in block.predecessors[1:]:
                        new_dom &= pred.dominators
                    new_dom.add(label)
                else:
                    new_dom = {label}

                if new_dom != block.dominators:
                    block.dominators = new_dom
                    changed = True

        # 计算直接支配者 (idom)
        self._compute_idom()

    def _compute_idom(self):
        """
        计算直接支配者。
        idom(n) = 唯一满足以下条件的块 m：
            m ∈ Dom(n), m ≠ n, 且不存在 k 使得 m ∈ Dom(k) ∧ k ∈ Dom(n) ∧ k ≠ m ∧ k ≠ n
        即：Dom(n) 中除 n 自身外，最"靠近" n 的那个支配者。
        """
        for label, block in self.blocks.items():
            if block == self.entry_block:
                block.idom = None
                continue
            # idom 是 Dom(n) - {n} 中，不被其他任何 Dom(n)-{n} 中的元素所支配的块
            strict_doms = block.dominators - {label}
            idom_candidate = None
            for candidate in strict_doms:
                is_idom = True
                for other in strict_doms:
                    if other != candidate and candidate in self.blocks[other].dominators:
                        is_idom = False
                        break
                if is_idom:
                    idom_candidate = candidate
                    break
            block.idom = idom_candidate

    # ============================================================
    # 步骤3：支配边界计算
    # ============================================================

    def compute_dominance_frontiers(self):
        """
        计算支配边界。
        
        支配边界 DF(n) 的定义：
        n 的支配边界是所有满足以下条件的节点 y：
        n 支配 y 的某个前驱，但 n 不严格支配 y。
        
        算法（每个节点与其前驱的关系）：
        for each block n:
            if |predecessors(n)| >= 2:
                for each predecessor p of n:
                    runner = p
                    while runner != idom(n):
                        DF(runner) ∪= {n}
                        runner = idom(runner)
        """
        # 清空
        for block in self.blocks.values():
            block.dominance_frontier.clear()

        for label, block in self.blocks.items():
            if len(block.predecessors) >= 2:
                for pred in block.predecessors:
                    runner = pred
                    while runner and runner.label != block.idom:
                        runner.dominance_frontier.add(label)
                        runner = self.blocks.get(runner.idom) if runner.idom else None

    # ============================================================
    # 步骤4：φ 函数插入
    # ============================================================

    def insert_phi_functions(self):
        """
        使用 Cytron 算法插入 φ 函数。
        
        对于每个变量 v：
        1. 收集 v 的所有定义点 W
        2. 计算 W 的迭代支配边界
        3. 在支配边界对应的块中插入 φ 函数
        """
        for var in self.variables:
            if var not in self.def_sites:
                continue
            worklist = list(self.def_sites[var])
            phi_inserted: Set[str] = set()

            while worklist:
                block_label = worklist.pop(0)
                if block_label not in self.blocks:
                    continue
                block = self.blocks[block_label]
                for df_label in block.dominance_frontier:
                    if df_label not in phi_inserted:
                        # 需要为 var 在 df_label 块中插入 φ 函数
                        df_block = self.blocks[df_label]
                        self._insert_phi(df_block, var, len(df_block.predecessors))
                        phi_inserted.add(df_label)
                        # 如果该块不是变量的定义点，加入 worklist
                        if df_label not in self.def_sites[var]:
                            worklist.append(df_label)
                            self.def_sites[var].add(df_label)

    def _insert_phi(self, block: BasicBlock, var: str, num_preds: int):
        """在基本块的开头插入 φ 函数"""
        phi_instr = TACInstruction(
            op="phi", result=var,
            arg1=f"[{num_preds} args]",
            arg2=None
        )
        phi_instr._phi_args_count = num_preds
        phi_instr._phi_var = var
        # φ 函数放在其他指令之前（但 label 之后）
        insert_pos = 0
        for i, instr in enumerate(block.instructions):
            if instr.op == "label":
                insert_pos = i + 1
            else:
                break
        block.instructions.insert(insert_pos, phi_instr)

    # ============================================================
    # 步骤5：变量重命名
    # ============================================================

    def rename_variables(self):
        """
        使用 DFS 遍历支配树，对变量进行重命名。
        
        算法：
        1. 对每个变量 v，维护一个栈 rename_stack[v]
        2. DFS 遍历支配树：
           a. 对块中的每条指令：
              - 如果是 φ 函数 result = φ(...)，先为 result 创建新版本
              - 对于使用的变量 x，用 rename_stack[x] 的栈顶替换
              - 对于定义的变量 x，创建新版本 x_N，压入栈
           b. 对每个后继块中的 φ 函数，添加对应的参数
           c. 递归处理支配树中的子节点
           d. 回溯时弹出栈
        """
        self._rename_stacks.clear()
        self._version_counter.clear()
        self._phi_args.clear()

        # 初始化：为每个变量压入版本 0
        for var in self.variables:
            self._rename_stacks[var] = [var]  # 初始版本为变量名本身

        # DFS 从入口块开始
        self._rename_block(self.entry_block)

    def _rename_block(self, block: BasicBlock):
        """递归重命名基本块中的变量"""
        # 记录本块中定义的变量，用于回溯时弹栈
        defined_vars: List[Tuple[str, int]] = []

        # 处理块中的每条指令
        for instr in block.instructions:
            if instr.op == "label" or instr.op == "goto":
                continue

            if instr.op == "phi":
                # φ 函数的结果：创建新版本
                var = getattr(instr, '_phi_var', instr.result)
                new_name = self._new_version(var)
                instr.ssa_result = new_name
                self._rename_stacks[var].append(new_name)
                defined_vars.append((var, 0))  # 0 表示不需要额外弹出
                continue

            if instr.op in ("if", "ifFalse"):
                # 使用变量
                if instr.arg1 and self._is_variable(instr.arg1):
                    instr.ssa_arg1 = self._get_current_version(instr.arg1)
                continue

            if instr.op == "return":
                if instr.arg1 and self._is_variable(instr.arg1):
                    instr.ssa_arg1 = self._get_current_version(instr.arg1)
                continue

            if instr.op in ("param",):
                if instr.arg1 and self._is_variable(instr.arg1):
                    instr.ssa_arg1 = self._get_current_version(instr.arg1)
                continue

            if instr.op == "call":
                if instr.result and self._is_variable(instr.result):
                    new_name = self._new_version(instr.result)
                    instr.ssa_result = new_name
                    self._rename_stacks[instr.result].append(new_name)
                    defined_vars.append((instr.result, 0))
                continue

            # 普通赋值/运算指令
            # 先处理使用的变量 (arg1, arg2)
            if instr.arg1 and self._is_variable(instr.arg1):
                instr.ssa_arg1 = self._get_current_version(instr.arg1)
            if instr.arg2 and self._is_variable(instr.arg2):
                instr.ssa_arg2 = self._get_current_version(instr.arg2)

            # 再处理定义的变量 (result)
            if instr.result and self._is_variable(instr.result):
                new_name = self._new_version(instr.result)
                instr.ssa_result = new_name
                self._rename_stacks[instr.result].append(new_name)
                defined_vars.append((instr.result, 0))

        # 为后继块中的 φ 函数添加参数
        for succ in block.successors:
            for instr in succ.instructions:
                if instr.op == "phi":
                    var = getattr(instr, '_phi_var', instr.result)
                    if var in self._rename_stacks and self._rename_stacks[var]:
                        current = self._rename_stacks[var][-1]
                    else:
                        current = var
                    # 记录参数
                    key = (succ.label, var)
                    if key not in self._phi_args:
                        self._phi_args[key] = []
                    self._phi_args[key].append(f"{current} (from {block.label})")

        # 递归处理支配树中的子节点
        for child_label, child_block in self.blocks.items():
            if child_block.idom == block.label:
                self._rename_block(child_block)

        # 回溯：弹出本块中定义的变量
        for var, _ in reversed(defined_vars):
            if self._rename_stacks[var]:
                self._rename_stacks[var].pop()

    def _new_version(self, var: str) -> str:
        """为变量创建新的 SSA 版本"""
        self._version_counter[var] += 1
        version = self._version_counter[var]
        return f"{var}_{version}"

    def _get_current_version(self, var: str) -> str:
        """获取变量的当前版本"""
        if var in self._rename_stacks and self._rename_stacks[var]:
            return self._rename_stacks[var][-1]
        return var

    # ============================================================
    # 完整转换流程
    # ============================================================

    def convert(self, instructions: List[TACInstruction]):
        """执行完整的 SSA 转换流程"""
        print("步骤1: 基本块划分...")
        self.build_basic_blocks(instructions)

        print("步骤2: 支配树构建...")
        self.compute_dominators()

        print("步骤3: 支配边界计算...")
        self.compute_dominance_frontiers()

        print("步骤4: φ 函数插入...")
        self.insert_phi_functions()

        print("步骤5: 变量重命名...")
        self.rename_variables()

    # ============================================================
    # 输出
    # ============================================================

    def print_cfg(self):
        """打印控制流图"""
        print("\n--- 控制流图 (CFG) ---")
        for label, block in self.blocks.items():
            preds = [p.label for p in block.predecessors]
            succs = [s.label for s in block.successors]
            print(f"  {label}: preds={preds}, succs={succs}")

    def print_dominators(self):
        """打印支配者信息"""
        print("\n--- 支配者集合 ---")
        for label, block in self.blocks.items():
            doms = sorted(block.dominators)
            idom = block.idom or "(entry)"
            print(f"  {label}: Dom={{{', '.join(doms)}}}, idom={idom}")

    def print_dominance_frontiers(self):
        """打印支配边界"""
        print("\n--- 支配边界 ---")
        for label, block in self.blocks.items():
            df = sorted(block.dominance_frontier)
            if df:
                print(f"  DF({label}) = {{{', '.join(df)}}}")

    def print_ssa_ir(self):
        """打印 SSA 形式的 IR"""
        print("\n--- SSA 形式 IR ---")
        for label, block in self.blocks.items():
            print(f"\n  [{block.label}]")
            for instr in block.instructions:
                if instr.op == "phi":
                    var = getattr(instr, '_phi_var', instr.result)
                    key = (label, var)
                    args = self._phi_args.get(key, ["..."])
                    ssa_res = instr.ssa_result or instr.result
                    args_str = ", ".join(args)
                    print(f"    {ssa_res} = φ({args_str})")
                else:
                    print(f"    {instr}")

    def print_all(self, title: str = ""):
        """打印所有信息"""
        if title:
            print(f"\n{'=' * 60}")
            print(f"  {title}")
            print(f"{'=' * 60}")
        self.print_cfg()
        self.print_dominators()
        self.print_dominance_frontiers()
        self.print_ssa_ir()
        print()


# ============================================================
# 测试用例
# ============================================================

def build_tac_instructions_1() -> List[TACInstruction]:
    """
    构建测试用的三地址码（含循环和条件分支）
    
    对应源代码：
        x = 0
        y = 1
    L_loop:
        if x > 10 goto L_end
        t1 = x + y
        x = t1
        t2 = y * 2
        y = t2
        goto L_loop
    L_end:
        z = x + y
        print(z)
    """
    return [
        TACInstruction("=", "x", "0"),                          # 0: x = 0
        TACInstruction("=", "y", "1"),                          # 1: y = 1
        TACInstruction("label", "L_loop"),                      # 2: L_loop:
        TACInstruction("if", "L_end", "x > 10"),               # 3: if x > 10 goto L_end
        TACInstruction("+", "t1", "x", "y"),                   # 4: t1 = x + y
        TACInstruction("=", "x", "t1"),                         # 5: x = t1
        TACInstruction("*", "t2", "y", "2"),                   # 6: t2 = y * 2
        TACInstruction("=", "y", "t2"),                         # 7: y = t2
        TACInstruction("goto", "L_loop"),                       # 8: goto L_loop
        TACInstruction("label", "L_end"),                       # 9: L_end:
        TACInstruction("+", "z", "x", "y"),                    # 10: z = x + y
        TACInstruction("return", arg1="z"),                     # 11: return z
    ]


def build_tac_instructions_2() -> List[TACInstruction]:
    """
    构建测试用的三地址码（含 if-else 和合并点）
    
    对应源代码：
        x = 1
        y = 2
        if x > y goto L_then
        goto L_else
    L_then:
        z = x + y
        goto L_end
    L_else:
        z = x - y
    L_end:
        w = z * 2
        return w
    """
    return [
        TACInstruction("=", "x", "1"),                          # 0: x = 1
        TACInstruction("=", "y", "2"),                          # 1: y = 2
        TACInstruction("if", "L_then", "x > y"),               # 2: if x > y goto L_then
        TACInstruction("goto", "L_else"),                       # 3: goto L_else
        TACInstruction("label", "L_then"),                      # 4: L_then:
        TACInstruction("+", "z", "x", "y"),                    # 5: z = x + y
        TACInstruction("goto", "L_end"),                        # 6: goto L_end
        TACInstruction("label", "L_else"),                      # 7: L_else:
        TACInstruction("-", "z", "x", "y"),                    # 8: z = x - y
        TACInstruction("label", "L_end"),                       # 9: L_end:
        TACInstruction("*", "w", "z", "2"),                    # 10: w = z * 2
        TACInstruction("return", arg1="w"),                     # 11: return w
    ]


def build_tac_instructions_3() -> List[TACInstruction]:
    """
    构建测试用的三地址码（含菱形控制流和多变量 φ）
    
    对应源代码：
        a = 1
        b = 2
        c = 0
        if a > 0 goto L1
        goto L2
    L1:
        d = a + b
        goto L3
    L2:
        d = a - b
        c = b * 3
    L3:
        e = d + c
        return e
    
    L3 的前驱有 L1 和 L2，在 L3 处 d 和 c 都需要 φ 函数。
    """
    return [
        TACInstruction("=", "a", "1"),                          # 0
        TACInstruction("=", "b", "2"),                          # 1
        TACInstruction("=", "c", "0"),                          # 2
        TACInstruction("if", "L1", "a > 0"),                   # 3
        TACInstruction("goto", "L2"),                           # 4
        TACInstruction("label", "L1"),                          # 5
        TACInstruction("+", "d", "a", "b"),                    # 6
        TACInstruction("goto", "L3"),                           # 7
        TACInstruction("label", "L2"),                          # 8
        TACInstruction("-", "d", "a", "b"),                    # 9
        TACInstruction("*", "c", "b", "3"),                    # 10
        TACInstruction("label", "L3"),                          # 11
        TACInstruction("+", "e", "d", "c"),                    # 12
        TACInstruction("return", arg1="e"),                     # 13
    ]


def main():
    print("=" * 60)
    print("SSA 转换器测试")
    print("=" * 60)

    # 测试1：含循环的程序
    print("\n>>> 测试1: 循环 (x=0,y=1; while(x>10){x+=y; y*=2})")
    print("原始 TAC:")
    tac1 = build_tac_instructions_1()
    for i, instr in enumerate(tac1):
        print(f"  [{i:3d}] {instr}")

    converter1 = SSAConverter()
    converter1.convert(tac1)
    converter1.print_all("测试1 SSA 转换结果")

    # 测试2：含 if-else 的程序
    print("\n>>> 测试2: if-else 分支")
    print("原始 TAC:")
    tac2 = build_tac_instructions_2()
    for i, instr in enumerate(tac2):
        print(f"  [{i:3d}] {instr}")

    converter2 = SSAConverter()
    converter2.convert(tac2)
    converter2.print_all("测试2 SSA 转换结果")

    # 测试3：菱形控制流（多变量 φ）
    print("\n>>> 测试3: 菱形控制流（多变量 φ 函数）")
    print("原始 TAC:")
    tac3 = build_tac_instructions_3()
    for i, instr in enumerate(tac3):
        print(f"  [{i:3d}] {instr}")

    converter3 = SSAConverter()
    converter3.convert(tac3)
    converter3.print_all("测试3 SSA 转换结果")

    print("=" * 60)
    print("测试完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
