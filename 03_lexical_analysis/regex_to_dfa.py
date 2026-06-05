"""
正则表达式到DFA转换实现
========================

本模块实现了正则表达式到DFA的完整转换流程：
1. 正则表达式解析
2. Thompson构造法：正则表达式 → NFA
3. 子集构造法：NFA → DFA（包含ε-闭包计算）
4. DFA最小化：最小化DFA状态数

转换流程:
  正则表达式 → 后缀表达式 → NFA → DFA → 最小化DFA
"""

from dataclasses import dataclass, field
from typing import Dict, FrozenSet, List, Optional, Set, Tuple
from collections import deque


# ============================================================
# 数据结构定义
# ============================================================

@dataclass
class State:
    """NFA/DFA状态"""
    id: int
    is_accept: bool = False
    
    def __hash__(self):
        return hash(self.id)
    
    def __eq__(self, other):
        return isinstance(other, State) and self.id == other.id
    
    def __repr__(self):
        return f"S{self.id}"


@dataclass
class Transition:
    """状态转移"""
    from_state: State
    symbol: Optional[str]  # None表示ε转移
    to_state: State
    
    def __repr__(self):
        if self.symbol is None:
            return f"{self.from_state} --ε--> {self.to_state}"
        return f"{self.from_state} --{self.symbol}--> {self.to_state}"


@dataclass
class NFA:
    """非确定性有限自动机"""
    start: State
    accept: State
    states: Set[State] = field(default_factory=set)
    transitions: List[Transition] = field(default_factory=list)
    
    def add_transition(self, from_state: State, symbol: Optional[str], to_state: State):
        """添加转移"""
        self.transitions.append(Transition(from_state, symbol, to_state))
    
    def get_transitions(self, state: State, symbol: Optional[str]) -> Set[State]:
        """获取从某状态通过某符号可达的状态集合"""
        result = set()
        for t in self.transitions:
            if t.from_state == state and t.symbol == symbol:
                result.add(t.to_state)
        return result
    
    def epsilon_closure(self, states: Set[State]) -> Set[State]:
        """计算ε-闭包"""
        closure = set(states)
        stack = list(states)
        
        while stack:
            state = stack.pop()
            for t in self.transitions:
                if t.from_state == state and t.symbol is None:
                    if t.to_state not in closure:
                        closure.add(t.to_state)
                        stack.append(t.to_state)
        
        return frozenset(closure)
    
    def display(self):
        """显示NFA"""
        print("NFA:")
        print(f"  起始状态: {self.start}")
        print(f"  接受状态: {self.accept}")
        print(f"  状态数: {len(self.states)}")
        print(f"  转移数: {len(self.transitions)}")
        print()
        print("  转移表:")
        
        # 收集所有符号
        symbols = set()
        for t in self.transitions:
            if t.symbol is not None:
                symbols.add(t.symbol)
        symbols = sorted(symbols)
        
        # 打印表头
        header = f"  {'状态':<10} {'ε':<15}"
        for s in symbols:
            header += f" {s:<15}"
        print(header)
        print("  " + "-" * (10 + 15 + 15 * len(symbols)))
        
        # 打印每行
        for state in sorted(self.states, key=lambda s: s.id):
            row = f"  {str(state):<10} "
            
            # ε转移
            eps_targets = self.get_transitions(state, None)
            if eps_targets:
                row += f"{','.join(str(s) for s in sorted(eps_targets, key=lambda s: s.id)):<15}"
            else:
                row += f"{'-':<15}"
            
            # 其他符号
            for symbol in symbols:
                targets = self.get_transitions(state, symbol)
                if targets:
                    row += f" {','.join(str(s) for s in sorted(targets, key=lambda s: s.id)):<15}"
                else:
                    row += f" {'-':<15}"
            
            print(row)


@dataclass
class DFA:
    """确定性有限自动机"""
    start: int
    accept_states: Set[int] = field(default_factory=set)
    states: Set[int] = field(default_factory=set)
    transitions: Dict[Tuple[int, str], int] = field(default_factory=dict)
    alphabet: Set[str] = field(default_factory=set)
    
    def add_transition(self, from_state: int, symbol: str, to_state: int):
        """添加转移"""
        self.transitions[(from_state, symbol)] = to_state
        self.alphabet.add(symbol)
    
    def accept(self, input_string: str) -> bool:
        """测试字符串是否被DFA接受"""
        current = self.start
        
        for char in input_string:
            if (current, char) in self.transitions:
                current = self.transitions[(current, char)]
            else:
                return False
        
        return current in self.accept_states
    
    def display(self):
        """显示DFA"""
        print("DFA:")
        print(f"  起始状态: q{self.start}")
        print(f"  接受状态: {{{', '.join(f'q{s}' for s in sorted(self.accept_states))}}}")
        print(f"  状态数: {len(self.states)}")
        print(f"  字母表: {{{', '.join(sorted(self.alphabet))}}}")
        print()
        print("  转移表:")
        
        # 打印表头
        sorted_alphabet = sorted(self.alphabet)
        header = f"  {'状态':<10}"
        for s in sorted_alphabet:
            header += f" {s:<10}"
        print(header)
        print("  " + "-" * (10 + 10 * len(sorted_alphabet)))
        
        # 打印每行
        for state in sorted(self.states):
            prefix = "→" if state == self.start else " "
            if state in self.accept_states:
                prefix = "*" if state == self.start else "*"
            
            row = f"  {prefix}q{state:<8}"
            for symbol in sorted_alphabet:
                if (state, symbol) in self.transitions:
                    target = self.transitions[(state, symbol)]
                    row += f" q{target:<9}"
                else:
                    row += f" {'-':<9}"
            print(row)
        
        print()
        print("  注: → 表示起始状态, * 表示接受状态")


# ============================================================
# 正则表达式解析器
# ============================================================

class RegexParser:
    """
    正则表达式解析器
    
    将正则表达式转换为后缀表达式（逆波兰表示法）。
    支持的运算符:
    - |  选择（或）
    - .  连接（隐式添加）
    - *  闭包（0次或多次）
    - +  正闭包（1次或多次）
    - ?  可选（0次或1次）
    - () 分组
    """
    
    # 运算符优先级
    PRECEDENCE = {
        '|': 1,
        '.': 2,
        '*': 3,
        '+': 3,
        '?': 3,
    }
    
    def __init__(self, regex: str):
        self.regex = regex
        self.pos = 0
    
    def peek(self) -> Optional[str]:
        """预读当前字符"""
        if self.pos < len(self.regex):
            return self.regex[self.pos]
        return None
    
    def advance(self) -> str:
        """前进一个字符"""
        char = self.regex[self.pos]
        self.pos += 1
        return char
    
    def add_explicit_concat(self) -> str:
        """
        添加显式连接运算符
        
        在需要的地方插入 '.' 表示连接:
        - ab → a.b
        - a( → a.(
        - )b → ).b
        - )( → ).(
        - a* → a* (不变)
        - *b → *.b
        """
        result = []
        i = 0
        
        while i < len(self.regex):
            char = self.regex[i]
            
            # 转义字符
            if char == '\\' and i + 1 < len(self.regex):
                result.append(self.regex[i:i+2])
                i += 2
                continue
            
            result.append(char)
            
            # 在这些情况后可能需要插入连接符
            if i + 1 < len(self.regex):
                next_char = self.regex[i + 1]
                
                # 当前字符是操作数或闭合括号或闭包运算符
                if (char not in '(|' and 
                    next_char not in '|)*+?)' and
                    next_char != '\\'):
                    result.append('.')
            
            i += 1
        
        return ''.join(result)
    
    def to_postfix(self) -> str:
        """
        转换为后缀表达式（逆波兰表示法）
        
        使用调度场算法（Shunting-yard algorithm）
        """
        # 首先添加显式连接运算符
        regex = self.add_explicit_concat()
        
        output = []
        operator_stack = []
        
        i = 0
        while i < len(regex):
            char = regex[i]
            
            # 转义字符
            if char == '\\' and i + 1 < len(regex):
                output.append(regex[i:i+2])
                i += 2
                continue
            
            # 操作数（普通字符）
            if char not in '|.*+?().':
                output.append(char)
                i += 1
                continue
            
            # 左括号
            if char == '(':
                operator_stack.append(char)
                i += 1
                continue
            
            # 右括号
            if char == ')':
                while operator_stack and operator_stack[-1] != '(':
                    output.append(operator_stack.pop())
                if operator_stack:
                    operator_stack.pop()  # 弹出 '('
                i += 1
                continue
            
            # 运算符
            while (operator_stack and 
                   operator_stack[-1] != '(' and
                   operator_stack[-1] in self.PRECEDENCE and
                   self.PRECEDENCE.get(operator_stack[-1], 0) >= self.PRECEDENCE.get(char, 0)):
                output.append(operator_stack.pop())
            
            operator_stack.append(char)
            i += 1
        
        # 弹出剩余运算符
        while operator_stack:
            output.append(operator_stack.pop())
        
        return ''.join(output)


# ============================================================
# Thompson构造法：正则表达式 → NFA
# ============================================================

class ThompsonConstructor:
    """
    Thompson构造法
    
    将正则表达式（后缀形式）转换为NFA。
    
    基本规则:
    - 字符a: 创建两个状态，a转移连接
    - 连接(r1.r2): 将r1的接受状态连接到r2的起始状态
    - 选择(r1|r2): 创建新的起始和接受状态，ε转移到r1和r2
    - 闭包(r*): 创建ε循环和旁路
    """
    
    def __init__(self):
        self.state_counter = 0
    
    def new_state(self) -> State:
        """创建新状态"""
        state = State(self.state_counter)
        self.state_counter += 1
        return state
    
    def create_nfa(self, postfix_regex: str) -> NFA:
        """
        从后缀正则表达式创建NFA
        
        Args:
            postfix_regex: 后缀表示的正则表达式
            
        Returns:
            构造的NFA
        """
        stack = []
        
        i = 0
        while i < len(postfix_regex):
            char = postfix_regex[i]
            
            # 转义字符
            if char == '\\' and i + 1 < len(postfix_regex):
                nfa = self.create_symbol_nfa(postfix_regex[i:i+2])
                stack.append(nfa)
                i += 2
                continue
            
            # 运算符
            if char == '.':
                # 连接
                nfa2 = stack.pop()
                nfa1 = stack.pop()
                result = self.concatenate(nfa1, nfa2)
                stack.append(result)
            elif char == '|':
                # 选择
                nfa2 = stack.pop()
                nfa1 = stack.pop()
                result = self.union(nfa1, nfa2)
                stack.append(result)
            elif char == '*':
                # 闭包
                nfa = stack.pop()
                result = self.closure(nfa)
                stack.append(result)
            elif char == '+':
                # 正闭包
                nfa = stack.pop()
                result = self.positive_closure(nfa)
                stack.append(result)
            elif char == '?':
                # 可选
                nfa = stack.pop()
                result = self.optional(nfa)
                stack.append(result)
            else:
                # 普通字符
                nfa = self.create_symbol_nfa(char)
                stack.append(nfa)
            
            i += 1
        
        if len(stack) != 1:
            raise ValueError(f"无效的正则表达式，栈中剩余 {len(stack)} 个NFA")
        
        return stack[0]
    
    def create_symbol_nfa(self, symbol: str) -> NFA:
        """创建单个符号的NFA: [start] --symbol--> [accept]"""
        start = self.new_state()
        accept = self.new_state()
        accept.is_accept = True
        
        nfa = NFA(start, accept, {start, accept})
        nfa.add_transition(start, symbol, accept)
        
        return nfa
    
    def concatenate(self, nfa1: NFA, nfa2: NFA) -> NFA:
        """
        连接两个NFA: nfa1.nfa2
        
        将nfa1的接受状态通过ε转移到nfa2的起始状态
        """
        # 合并状态和转移
        states = nfa1.states | nfa2.states
        transitions = nfa1.transitions + nfa2.transitions
        
        # 添加ε转移: nfa1.accept → nfa2.start
        nfa1.accept.is_accept = False
        transitions.append(Transition(nfa1.accept, None, nfa2.start))
        
        return NFA(nfa1.start, nfa2.accept, states, transitions)
    
    def union(self, nfa1: NFA, nfa2: NFA) -> NFA:
        """
        选择两个NFA: nfa1|nfa2
        
        创建新的起始和接受状态
        """
        start = self.new_state()
        accept = self.new_state()
        accept.is_accept = True
        
        # 合并状态和转移
        states = nfa1.states | nfa2.states | {start, accept}
        transitions = nfa1.transitions + nfa2.transitions
        
        # 原来的接受状态不再是接受状态
        nfa1.accept.is_accept = False
        nfa2.accept.is_accept = False
        
        # 添加ε转移
        transitions.append(Transition(start, None, nfa1.start))
        transitions.append(Transition(start, None, nfa2.start))
        transitions.append(Transition(nfa1.accept, None, accept))
        transitions.append(Transition(nfa2.accept, None, accept))
        
        return NFA(start, accept, states, transitions)
    
    def closure(self, nfa: NFA) -> NFA:
        """
        Kleene闭包: nfa*
        
        创建ε循环和旁路
        """
        start = self.new_state()
        accept = self.new_state()
        accept.is_accept = True
        
        # 合并状态和转移
        states = nfa.states | {start, accept}
        transitions = nfa.transitions.copy()
        
        # 原来的接受状态不再是接受状态
        nfa.accept.is_accept = False
        
        # 添加ε转移
        transitions.append(Transition(start, None, nfa.start))  # 进入循环
        transitions.append(Transition(start, None, accept))      # 旁路（0次）
        transitions.append(Transition(nfa.accept, None, nfa.start))  # 循环回来
        transitions.append(Transition(nfa.accept, None, accept))      # 退出循环
        
        return NFA(start, accept, states, transitions)
    
    def positive_closure(self, nfa: NFA) -> NFA:
        """
        正闭包: nfa+
        
        至少匹配一次
        """
        start = self.new_state()
        accept = self.new_state()
        accept.is_accept = True
        
        # 合并状态和转移
        states = nfa.states | {start, accept}
        transitions = nfa.transitions.copy()
        
        # 原来的接受状态不再是接受状态
        nfa.accept.is_accept = False
        
        # 添加ε转移
        transitions.append(Transition(start, None, nfa.start))  # 进入
        transitions.append(Transition(nfa.accept, None, nfa.start))  # 循环回来
        transitions.append(Transition(nfa.accept, None, accept))      # 退出
        
        return NFA(start, accept, states, transitions)
    
    def optional(self, nfa: NFA) -> NFA:
        """
        可选: nfa?
        
        匹配0次或1次
        """
        start = self.new_state()
        accept = self.new_state()
        accept.is_accept = True
        
        # 合并状态和转移
        states = nfa.states | {start, accept}
        transitions = nfa.transitions.copy()
        
        # 原来的接受状态不再是接受状态
        nfa.accept.is_accept = False
        
        # 添加ε转移
        transitions.append(Transition(start, None, nfa.start))  # 匹配1次
        transitions.append(Transition(start, None, accept))      # 匹配0次
        transitions.append(Transition(nfa.accept, None, accept))  # 完成匹配
        
        return NFA(start, accept, states, transitions)


# ============================================================
# 子集构造法：NFA → DFA
# ============================================================

class SubsetConstructor:
    """
    子集构造法
    
    将NFA转换为等价的DFA。
    
    算法步骤:
    1. 计算NFA起始状态的ε-闭包作为DFA的起始状态
    2. 对每个DFA状态（NFA状态集合），计算每个输入符号的转移
    3. 新的DFA状态是当前状态集合通过某符号转移后的ε-闭包
    4. 重复直到没有新的DFA状态
    """
    
    def __init__(self, nfa: NFA):
        self.nfa = nfa
        self.alphabet = self._get_alphabet()
    
    def _get_alphabet(self) -> Set[str]:
        """获取NFA的字母表"""
        alphabet = set()
        for t in self.nfa.transitions:
            if t.symbol is not None:
                alphabet.add(t.symbol)
        return alphabet
    
    def convert(self) -> DFA:
        """
        将NFA转换为DFA
        
        Returns:
            等价的DFA
        """
        # DFA状态编号
        dfa_state_counter = 0
        
        # NFA状态集合 → DFA状态编号的映射
        state_set_to_dfa: Dict[FrozenSet[State], int] = {}
        
        # DFA状态编号 → NFA状态集合的映射
        dfa_to_state_set: Dict[int, FrozenSet[State]] = {}
        
        # 起始状态：NFA起始状态的ε-闭包
        start_closure = self.nfa.epsilon_closure({self.nfa.start})
        
        # 创建DFA起始状态
        state_set_to_dfa[start_closure] = dfa_state_counter
        dfa_to_state_set[dfa_state_counter] = start_closure
        dfa_state_counter += 1
        
        # 待处理的DFA状态队列
        queue = deque([start_closure])
        
        # DFA转移表
        dfa_transitions: Dict[Tuple[int, str], int] = {}
        
        # 已处理的状态集合
        processed = set()
        
        while queue:
            current_set = queue.popleft()
            
            if current_set in processed:
                continue
            processed.add(current_set)
            
            current_dfa_state = state_set_to_dfa[current_set]
            
            # 对每个输入符号计算转移
            for symbol in self.alphabet:
                # 计算 move(T, a)：从current_set中的状态通过symbol可达的状态集合
                move_result = set()
                for state in current_set:
                    move_result |= self.nfa.get_transitions(state, symbol)
                
                if not move_result:
                    continue
                
                # 计算 ε-closure(move(T, a))
                next_set = self.nfa.epsilon_closure(move_result)
                
                # 如果是新的DFA状态，添加到映射
                if next_set not in state_set_to_dfa:
                    state_set_to_dfa[next_set] = dfa_state_counter
                    dfa_to_state_set[dfa_state_counter] = next_set
                    dfa_state_counter += 1
                    queue.append(next_set)
                
                # 添加DFA转移
                dfa_transitions[(current_dfa_state, symbol)] = state_set_to_dfa[next_set]
        
        # 确定接受状态：包含NFA接受状态的DFA状态
        accept_states = set()
        for state_set, dfa_state in state_set_to_dfa.items():
            if any(state.is_accept for state in state_set):
                accept_states.add(dfa_state)
        
        # 创建DFA
        dfa = DFA(
            start=state_set_to_dfa[start_closure],
            accept_states=accept_states,
            states=set(range(dfa_state_counter)),
            transitions=dfa_transitions,
            alphabet=self.alphabet
        )
        
        return dfa


# ============================================================
# DFA最小化
# ============================================================

class DFAMinimizer:
    """
    DFA最小化器
    
    使用分割法（Hopcroft算法的简化版本）最小化DFA。
    
    算法步骤:
    1. 初始分割: {接受状态, 非接受状态}
    2. 对每个分割中的状态组:
       - 如果存在输入a使得组内状态转移到不同的组
       - 则分割该组
    3. 重复直到无法进一步分割
    """
    
    @staticmethod
    def minimize(dfa: DFA) -> DFA:
        """
        最小化DFA
        
        Args:
            dfa: 待最小化的DFA
            
        Returns:
            最小化后的DFA
        """
        # 初始分割：接受状态和非接受状态
        non_accept = dfa.states - dfa.accept_states
        partition = []
        
        if non_accept:
            partition.append(frozenset(non_accept))
        if dfa.accept_states:
            partition.append(frozenset(dfa.accept_states))
        
        # 移除空集
        partition = [p for p in partition if p]
        
        changed = True
        while changed:
            changed = False
            new_partition = []
            
            for group in partition:
                # 尝试按转移目标分割该组
                splits = DFAMinimizer._split_group(group, partition, dfa)
                
                if len(splits) > 1:
                    changed = True
                
                new_partition.extend(splits)
            
            partition = new_partition
        
        # 构建最小化后的DFA
        return DFAMinimizer._build_minimized_dfa(partition, dfa)
    
    @staticmethod
    def _split_group(group: FrozenSet[int], partition: List[FrozenSet[int]], 
                     dfa: DFA) -> List[FrozenSet[int]]:
        """
        尝试分割一个状态组
        
        如果组内状态对某个输入符号转移到不同的组，则分割
        """
        # 计算每个状态的"签名"：对每个输入符号，它转移到哪个组
        signatures: Dict[int, Tuple] = {}
        
        for state in group:
            sig = []
            for symbol in sorted(dfa.alphabet):
                target = dfa.transitions.get((state, symbol))
                if target is None:
                    sig.append(None)
                else:
                    # 找到目标所在的组
                    for i, p in enumerate(partition):
                        if target in p:
                            sig.append(i)
                            break
                    else:
                        sig.append(None)
            signatures[state] = tuple(sig)
        
        # 按签名分组
        groups: Dict[Tuple, List[int]] = {}
        for state, sig in signatures.items():
            if sig not in groups:
                groups[sig] = []
            groups[sig].append(state)
        
        return [frozenset(g) for g in groups.values()]
    
    @staticmethod
    def _build_minimized_dfa(partition: List[FrozenSet[int]], dfa: DFA) -> DFA:
        """从分割结果构建最小化DFA"""
        # 原始状态 → 新状态的映射
        state_to_group: Dict[int, int] = {}
        for i, group in enumerate(partition):
            for state in group:
                state_to_group[state] = i
        
        # 新的起始状态
        new_start = state_to_group[dfa.start]
        
        # 新的接受状态
        new_accept_states = set()
        for state in dfa.accept_states:
            new_accept_states.add(state_to_group[state])
        
        # 新的转移表
        new_transitions: Dict[Tuple[int, str], int] = {}
        for (from_state, symbol), to_state in dfa.transitions.items():
            new_from = state_to_group[from_state]
            new_to = state_to_group[to_state]
            new_transitions[(new_from, symbol)] = new_to
        
        return DFA(
            start=new_start,
            accept_states=new_accept_states,
            states=set(range(len(partition))),
            transitions=new_transitions,
            alphabet=dfa.alphabet
        )


# ============================================================
# 完整的转换流程
# ============================================================

def regex_to_dfa(regex: str, display_steps: bool = True) -> DFA:
    """
    将正则表达式转换为最小化DFA
    
    Args:
        regex: 正则表达式
        display_steps: 是否显示中间步骤
        
    Returns:
        最小化后的DFA
    """
    print("=" * 60)
    print(f"正则表达式: {regex}")
    print("=" * 60)
    
    # Step 1: 解析正则表达式为后缀形式
    parser = RegexParser(regex)
    postfix = parser.to_postfix()
    
    if display_steps:
        print(f"\n后缀表达式: {postfix}")
        print(f"显式连接: {parser.add_explicit_concat()}")
    
    # Step 2: Thompson构造法生成NFA
    constructor = ThompsonConstructor()
    nfa = constructor.create_nfa(postfix)
    
    if display_steps:
        print("\n" + "-" * 40)
        print("步骤1: Thompson构造法生成NFA")
        print("-" * 40)
        nfa.display()
    
    # Step 3: 子集构造法转换为DFA
    subset_constructor = SubsetConstructor(nfa)
    dfa = subset_constructor.convert()
    
    if display_steps:
        print("\n" + "-" * 40)
        print("步骤2: 子集构造法生成DFA")
        print("-" * 40)
        dfa.display()
    
    # Step 4: DFA最小化
    minimized_dfa = DFAMinimizer.minimize(dfa)
    
    if display_steps:
        print("\n" + "-" * 40)
        print("步骤3: DFA最小化")
        print("-" * 40)
        minimized_dfa.display()
    
    return minimized_dfa


# ============================================================
# 测试用例
# ============================================================

def test_regex_to_dfa():
    """测试正则表达式到DFA的转换"""
    
    test_cases = [
        # (正则表达式, 测试字符串, 预期结果)
        ("a", "a", True),
        ("a", "b", False),
        ("a|b", "a", True),
        ("a|b", "b", True),
        ("a|b", "c", False),
        ("ab", "ab", True),
        ("ab", "a", False),
        ("a*", "", True),
        ("a*", "a", True),
        ("a*", "aaa", True),
        ("a+", "", False),
        ("a+", "a", True),
        ("a+", "aaa", True),
        ("a?", "", True),
        ("a?", "a", True),
        ("a?", "aa", False),
        ("(a|b)*", "", True),
        ("(a|b)*", "abba", True),
        ("(a|b)*", "abc", False),
        ("a(b|c)*d", "ad", True),
        ("a(b|c)*d", "abcbd", True),
        ("a(b|c)*d", "abcb", False),
    ]
    
    print("\n" + "=" * 60)
    print("测试用例")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for regex, test_str, expected in test_cases:
        try:
            dfa = regex_to_dfa(regex, display_steps=False)
            result = dfa.accept(test_str)
            status = "✓" if result == expected else "✗"
            
            if result == expected:
                passed += 1
            else:
                failed += 1
            
            print(f"  {status} regex='{regex}', input='{test_str}', "
                  f"expected={expected}, got={result}")
        except Exception as e:
            failed += 1
            print(f"  ✗ regex='{regex}', 错误: {e}")
    
    print(f"\n结果: {passed} 通过, {failed} 失败")


def demo_detailed():
    """详细的演示示例"""
    
    # 示例1: 简单的 a|b
    print("\n" + "=" * 60)
    print("示例1: a|b")
    print("=" * 60)
    dfa = regex_to_dfa("a|b")
    
    print("\n测试:")
    print(f"  'a' -> {dfa.accept('a')}")
    print(f"  'b' -> {dfa.accept('b')}")
    print(f"  'c' -> {dfa.accept('c')}")
    
    # 示例2: a*b
    print("\n" + "=" * 60)
    print("示例2: a*b")
    print("=" * 60)
    dfa = regex_to_dfa("a*b")
    
    print("\n测试:")
    print(f"  'b' -> {dfa.accept('b')}")
    print(f"  'ab' -> {dfa.accept('ab')}")
    print(f"  'aab' -> {dfa.accept('aab')}")
    print(f"  'a' -> {dfa.accept('a')}")
    
    # 示例3: (a|b)*abb
    print("\n" + "=" * 60)
    print("示例3: (a|b)*abb (经典的abb结尾检测)")
    print("=" * 60)
    dfa = regex_to_dfa("(a|b)*abb")
    
    print("\n测试:")
    test_strings = ["abb", "aabb", "babb", "ab", "abc", "abba"]
    for s in test_strings:
        print(f"  '{s}' -> {dfa.accept(s)}")


def main():
    """主函数"""
    print("正则表达式到DFA转换器")
    print("=" * 60)
    
    # 详细演示
    demo_detailed()
    
    # 测试用例
    test_regex_to_dfa()
    
    # 交互式测试
    print("\n" + "=" * 60)
    print("交互式测试")
    print("=" * 60)
    
    test_regexes = [
        "[0-9]+",           # 整数（注意：这里用简化表示）
        "(a|b)(a|b)*",      # a和b组成的字符串
        "a*b*",             # a后跟b
    ]
    
    for regex in test_regexes:
        print(f"\n测试正则表达式: {regex}")
        print("-" * 40)
        try:
            dfa = regex_to_dfa(regex, display_steps=True)
            print(f"\n  'ab' -> {dfa.accept('ab')}")
            print(f"  'aabb' -> {dfa.accept('aabb')}")
        except Exception as e:
            print(f"  错误: {e}")


if __name__ == '__main__':
    main()
