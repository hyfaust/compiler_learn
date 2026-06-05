# 第6章 代码优化

> 编译器的核心竞争力在于优化。一个好的优化器可以让程序运行速度提升数倍甚至数十倍。
> 本章将系统地介绍从局部到全局、从过程内到过程间的各类优化技术。

---

## 目录

- [6.1 优化概述](#61-优化概述)
- [6.2 控制流图（CFG）详解](#62-控制流图cfg详解)
- [6.3 局部优化](#63-局部优化)
- [6.4 循环优化](#64-循环优化)
- [6.5 全局优化与数据流分析](#65-全局优化与数据流分析)
- [6.6 过程间优化](#66-过程间优化)
- [6.7 GCC 优化策略](#67-gcc-优化策略)
- [6.8 Python/JS/LuaJIT 的优化策略](#68-pythonjsluajit-的优化策略)
- [6.9 示例代码说明](#69-示例代码说明)

---

## 6.1 优化概述

### 6.1.1 优化的目的

编译器优化的核心目标是在**不改变程序语义**的前提下，改善程序的某些质量指标：

| 指标 | 说明 | 典型场景 |
|------|------|----------|
| **执行速度** | 减少指令数量、提高缓存命中率 | 通用编译器的首要目标 |
| **代码体积** | 减少生成的机器码大小 | 嵌入式系统、固件 |
| **内存使用** | 减少运行时内存分配和占用 | 移动设备、IoT |
| **能耗** | 减少 CPU 计算量和内存访问 | 移动设备、数据中心 |
| **编译时间** | 加快编译速度 | 开发阶段的增量编译 |

> **重要原则**：优化必须保持程序的**可观测行为**（observable behavior）不变。
> 但如果程序员使用了未定义行为（如 C/C++ 中的越界访问），优化器可以假设这类行为不会发生。

### 6.1.2 优化的分类

按优化作用的范围，从窄到宽可分为：

```
┌─────────────────────────────────────────────────────────────┐
│                      优化分类层级                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  局部优化 (Local)                                           │
│  └── 作用于单个基本块内部                                    │
│      ├── 常量折叠                                           │
│      ├── 常量传播                                           │
│      ├── 公共子表达式消除                                    │
│      ├── 死代码消除                                         │
│      └── 强度削弱                                           │
│                                                             │
│  循环优化 (Loop)                                            │
│  └── 作用于循环结构                                         │
│      ├── 循环不变量外提                                      │
│      ├── 循环展开                                           │
│      └── 归纳变量优化                                       │
│                                                             │
│  全局优化 (Global)                                          │
│  └── 作用于整个函数/过程                                    │
│      ├── 活跃变量分析                                       │
│      ├── 到达定义分析                                       │
│      ├── 可用表达式分析                                     │
│      └── 全局公共子表达式消除                                │
│                                                             │
│  过程间优化 (Interprocedural)                               │
│  └── 作用于多个函数/整个程序                                │
│      ├── 函数内联                                           │
│      ├── 过程间常量传播                                     │
│      └── 别名分析                                           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 6.1.3 优化的时机

编译器在不同阶段执行不同类型的优化：

```
源代码
  │
  ▼
┌──────────────┐
│  前端分析     │  ← 语言相关的高层优化（如 AST 变换）
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  中间代码生成 │  ← 生成 IR（三地址码、SSA 等）
└──────┬───────┘
       │
       ▼
┌──────────────────────────────────────┐
│  中端优化（Machine-Independent）      │  ← 主要优化战场
│  • 局部优化                          │
│  • 循环优化                          │
│  • 全局优化 / 数据流分析              │
│  • 过程间优化                        │
└──────┬───────────────────────────────┘
       │
       ▼
┌──────────────────────────────────────┐
│  后端优化（Machine-Dependent）        │
│  • 指令选择                          │
│  • 指令调度                          │
│  • 寄存器分配                        │
│  • 窥孔优化（Peephole Optimization）  │
└──────┬───────────────────────────────┘
       │
       ▼
  目标机器码
```

**前中后端优化的比较**：

| 特性 | 前端优化 | 中端优化 | 后端优化 |
|------|---------|---------|---------|
| 依赖源语言 | 是 | 否 | 否 |
| 依赖目标机器 | 否 | 否 | 是 |
| 代表技术 | 类型推导优化 | SSA 优化、数据流分析 | 指令调度、寄存器分配 |
| 可移植性 | 低 | 高 | 低 |

---

## 6.2 控制流图（CFG）详解

控制流图（Control Flow Graph, CFG）是几乎所有优化的基础数据结构。它将程序的控制流抽象为一个有向图。

### 6.2.1 基本块的定义与划分

**基本块（Basic Block）** 是一段满足以下条件的最大指令序列：
1. **单入口**：控制流只能从第一条指令进入
2. **单出口**：控制流只能从最后一条指令离开
3. **顺序执行**：除最后一条指令外，中间没有跳转，也不会被跳转目标打断

**划分算法**：

```
输入：指令序列 I₁, I₂, ..., Iₙ
输出：基本块集合

步骤1：确定每个基本块的「首指令」（leader）
  - 规则a：第一条指令是 leader
  - 规则b：任何跳转指令的目标指令是 leader
  - 规则c：任何跳转指令之后的那条指令是 leader

步骤2：每个基本块 = 从一个 leader 到下一个 leader 之前的所有指令
```

**示例**：

```
原始三地址码:                    基本块划分:
                                 
(1) i = 0                 ┌──────────────────┐
(2) t1 = i < 10           │  BB1 (leader: 1) │
(3) ifFalse t1 goto (9)   │  (1) i = 0       │
(4) t2 = i * 4            │  (2) t1 = i < 10 │
(5) a[t2] = 0             │  (3) ifFalse t1  │
(6) t3 = i + 1            └────────┬─────────┘
(7) i = t3                        │ t1=true │ t1=false
(8) goto (2)           ┌──────────▼───┐    ┌──▼─────────┐
(9) return              │  BB2         │    │  BB3       │
                        │  (4)-(7)     │    │  (9) return│
                        │  (8) goto BB1│    └────────────┘
                        └──────┬───────┘
                               │ (goto BB1)
                               └──→ BB1
```

### 6.2.2 CFG 的数据结构

一个典型的 CFG 数据结构包含：

```python
class BasicBlock:
    label: str              # 基本块标签
    instructions: list      # 指令列表
    successors: list        # 后继基本块列表
    predecessors: list      # 前驱基本块列表

class CFG:
    entry: BasicBlock       # 入口基本块
    exit: BasicBlock        # 出口基本块（可能有多个）
    blocks: list            # 所有基本块列表
```

### 6.2.3 前驱与后继

对于 CFG 中的边 `A → B`：
- **A 是 B 的前驱**（predecessor）：`pred(B) = {A}`
- **B 是 A 的后继**（successor）：`succ(A) = {B}`

```
       ┌─────┐
       │ BB1 │
       └──┬──┘
       ┌──┴──┐
       ▼     ▼
    ┌─────┐ ┌─────┐
    │ BB2 │ │ BB3 │   pred(BB4) = {BB2, BB3}
    └──┬──┘ └──┬──┘   succ(BB2) = {BB4}
       │       │       succ(BB3) = {BB4}
       └───┬───┘
           ▼
       ┌─────┐
       │ BB4 │
       └─────┘
```

**前驱/后继的用途**：
- **数据流分析**：前驱关系用于反向分析（如活跃变量），后继关系用于正向分析（如到达定义）
- **支配关系计算**：基于前驱关系计算支配树
- **代码移动**：判断能否将代码从一个块移到另一个块

### 6.2.4 支配关系与支配树

**支配（Dominance）**：如果从入口到节点 n 的**所有路径**都必须经过节点 d，则称 **d 支配 n**，记作 `d dom n`。

**性质**：
- 支配关系是**自反的**：`n dom n`
- 支配关系是**传递的**：`a dom b ∧ b dom c → a dom c`
- 支配关系是**反对称的**：`a dom b ∧ b dom a → a = b`

**直接支配者（Immediate Dominator, idom）**：
- 如果 `d dom n` 且 `d ≠ n`，且不存在其他节点 `d'` 使得 `d dom d' ∧ d' dom n`
- 则 d 是 n 的直接支配者，记作 `idom(n) = d`

**支配树（Dominator Tree）**：

```
CFG:                          支配树:

    ┌──→ BB2 ──┐                  BB1
    │          │                /  |  \
   BB1        BB3            BB2 BB3 BB4
    │          │              |    |
    └──→ BB4 ──┘            BB4  BB5
         │                    │
         ▼                   BB5
       BB5
```

**支配边界（Dominance Frontier）**：
- 节点 B 的支配边界 `DF(B)` = { n | B 支配 n 的某个前驱，但 B 不严格支配 n }
- 支配边界在 SSA 构建中至关重要，它决定了 φ 函数的插入位置

**支配边界的直觉理解**：

```
考虑以下 CFG:
        BB1
       / \
     BB2  BB3
       \ /
       BB4

- BB1 支配 BB2、BB3、BB4
- BB2 不支配 BB4（因为 BB3→BB4 的路径不经过 BB2）
- BB3 不支配 BB4（同理）
- 所以 DF(BB2) = {BB4}, DF(BB3) = {BB4}
- 如果在 BB2 和 BB3 中都对变量 x 进行了赋值，
  那么 BB4 需要插入 φ(x) 函数
```

### 6.2.5 CFG 构建的完整示例

考虑以下 C 代码：

```c
int abs_max(int a[], int n) {
    int max = 0;
    for (int i = 0; i < n; i++) {
        int val = a[i];
        if (val < 0) val = -val;
        if (val > max) max = val;
    }
    return max;
}
```

对应的 CFG（简化版）：

```
         ┌───────────────┐
         │ BB_entry      │
         │ max = 0       │
         │ i = 0         │
         └──────┬────────┘
                ▼
         ┌──────────────┐
    ┌──→ │ BB_cond      │◄──────────────────┐
    │    │ t1 = i < n   │                   │
    │    │ if t1 goto   │                   │
    │    └──┬───────────┘                   │
    │       │ true         false            │
    │       ▼               ▼               │
    │  ┌──────────┐  ┌──────────┐           │
    │  │ BB_body1 │  │ BB_exit  │           │
    │  │ val=a[i] │  │ return   │           │
    │  │ if val<0 │  │ max      │           │
    │  └─┬────┬───┘  └──────────┘           │
    │    │    │                              │
    │  false true                            │
    │    │    ▼                              │
    │    │ ┌──────────┐                     │
    │    │ │ BB_neg   │                     │
    │    │ │ val=-val │                     │
    │    │ └────┬─────┘                     │
    │    │      │                            │
    │    └──┬───┘                            │
    │       ▼                                │
    │  ┌──────────┐                          │
    │  │ BB_body2 │                          │
    │  │ if val>m │                          │
    │  └─┬────┬───┘                          │
    │  false true                            │
    │    │    ▼                              │
    │    │ ┌──────────┐                     │
    │    │ │ BB_upd   │                     │
    │    │ │ max=val  │                     │
    │    │ └────┬─────┘                     │
    │    │      │                            │
    │    └──┬───┘                            │
    │       ▼                                │
    │  ┌──────────┐                          │
    │  │ BB_inc   │                          │
    │  │ i = i+1  │──────────────────────────┘
    │  └──────────┘
    └──→ (to BB_cond)
```

配套的 Python 实现请参见 `cfg_builder.py`。

---

## 6.3 局部优化

局部优化在**单个基本块**内部进行，不涉及跨块的信息流动。这是最简单也最基础的优化类型。

### 6.3.1 常量折叠（Constant Folding）

**原理**：在编译时计算常量表达式的值，用计算结果替换原表达式。

**规则**：如果操作数都是编译时常量，则可以在编译时计算结果。

**示例**：

```
优化前:                      优化后:
a = 3 + 5                   a = 8
b = a * 2                   b = 16
c = 3.14 * 2                c = 6.28
d = 1 > 0                   d = true
e = "hel" + "lo"            e = "hello"
```

**实现要点**：
- 需要处理整数溢出（是否是未定义行为取决于语言）
- 浮点运算可能因舍入模式不同而结果不同（`#pragma STDC FENV_ACCESS`）
- 对于 `sizeof`、`alignof` 等编译时运算符，同样适用

**更复杂的例子**：

```
优化前:                           优化后:
x = 100                          x = 100
y = x / 2 + x * 3               y = 350
z = (y > 100) ? 1 : 0           z = 1
```

### 6.3.2 常量传播（Constant Propagation）

**原理**：如果一个变量在某点被确定为常量值，则在该点之后的使用可以用该常量替换。

**与常量折叠的区别**：
- 常量折叠：计算已知常量表达式 → `3+5 → 8`
- 常量传播：将变量替换为已知常量 → `x=5; y=x+1 → x=5; y=5+1`

**示例**：

```
优化前:                      优化后:
x = 5                       x = 5
y = x + 3                   y = 8
z = y * 2                   z = 16
w = x + y + z               w = 29
```

**注意**：常量传播是路径敏感的：

```
x = 5
if (cond) {
    x = 10    // x 可能不是常量了
}
print(x)      // 这里 x 不是常量，不能传播
```

**条件常量传播（CCP）**：

更高级的常量传播会考虑控制流：

```
x = 5
y = 10
if (true) {       // 条件恒为真
    x = 20
}
print(x)           // CCP 可以确定 x = 20
```

### 6.3.3 公共子表达式消除（CSE, Common Subexpression Elimination）

**原理**：如果一个表达式在之前已经被计算过，且其操作数的值没有改变，则可以复用之前的结果。

**示例**：

```
优化前:                         优化后:
a = b + c                      a = b + c
d = b + c                      d = a    ← 复用 a 的值
...
x = b + c                      x = a    ← 仍然可以复用
```

**更实际的例子**：

```
优化前:                                    优化后:
t1 = a[i] * 4 + base                     t1 = a[i] * 4 + base
arr[t1] = 0                               arr[t1] = 0
... // 未修改 a[i], base
t2 = a[i] * 4 + base                     t2 = t1    ← CSE
arr[t2] = 1                               arr[t1] = 1
```

**CSE 的局限性**：
- 仅在操作数未被修改时有效
- 浮点运算由于精度问题，CSE 可能改变结果（通常编译器会保守处理）

### 6.3.4 死代码消除（Dead Code Elimination, DCE）

**原理**：删除那些计算结果从未被使用的指令（"死"代码）。

**分类**：

| 类型 | 说明 | 示例 |
|------|------|------|
| **无用赋值消除** | 变量赋值后未被使用 | `x = 5; x = 10;` → `x = 10;` |
| **不可达代码消除** | 控制流无法到达的代码 | `if (false) { ... }` |
| **不可达分支消除** | 条件恒为真/假的分支 | `if (true) x=1; else x=2;` → `x=1;` |

**示例**：

```
优化前:                         优化后:
x = compute_something()        x = compute_something()
y = x * 2                      y = x * 2    // y 也未使用...
z = y + 1                      // 删除 z = y + 1
w = 42                         // 删除 w = 42
return y                       return y
```

注意：如果 `compute_something()` 有副作用，则 `x = compute_something()` 不能删除。
编译器需要区分**纯函数**（pure function）和有副作用的函数。

**不可达代码消除示例**：

```
优化前:                         优化后:
x = 1                          x = 1
if (x == 1) {                  y = 10
    y = 10                     z = y * 2
} else {
    y = 20   // 不可达，删除
}
z = y * 2
```

### 6.3.5 强度削弱（Strength Reduction）

**原理**：用计算代价更低的等价操作替换原有操作。

**常见替换**：

| 原操作 | 替换为 | 代价比 |
|--------|--------|--------|
| `x * 2` | `x << 1` | 乘法 → 移位 |
| `x * 8` | `x << 3` | 乘法 → 移位 |
| `x / 4` | `x >> 2` | 除法 → 移位（注意符号位） |
| `x * 15` | `(x << 4) - x` | 乘法 → 移位+减法 |
| `x²` | `x * x` | 幂运算 → 乘法 |
| `x * 0` | `0` | 乘法 → 常量 |

**循环中的强度削弱**（最重要的应用）：

```
优化前:                         优化后:
for (i = 0; i < n; i++) {     t = 0;
    a[i] = i * 4;              for (i = 0; i < n; i++) {
}                                  a[i] = t;
                                   t = t + 4;
                               }
```

这里将循环中的乘法 `i * 4` 替换为加法 `t += 4`，因为乘法的代价远高于加法。

**现代处理器的考量**：
- 现代 CPU 的乘法和加法的延迟差距已经缩小（大约 3-4 周期 vs 1 周期）
- 但强度削弱仍然有价值，因为它减少了指令的"关键路径"长度
- 编译器还会考虑移位+加法是否比乘法占用更多指令槽

配套的 Python 实现请参见 `optimizer.py`。

---

## 6.4 循环优化

循环是程序执行的热点——研究表明，程序 90% 以上的执行时间花在循环中。因此，循环优化是提升性能最有效的手段。

### 6.4.1 循环不变量外提（Loop-Invariant Code Motion, LICM）

**原理**：如果一个表达式在循环体内是"不变的"（即每次迭代的值相同），则可以将其提到循环外部。

**条件**：
1. 表达式所在的基本块**支配**循环的所有出口
2. 表达式的操作数在循环中**不被重新定义**
3. 表达式所在的路径是循环中到达出口的**必经之路**

**示例**：

```
优化前:                         优化后:
while (i < n) {                t = x * y + z;  // 外提
    a = x * y + z;             while (i < n) {
    b = a + i;                     b = t + i;
    arr[i] = b;                    arr[i] = b;
    i++;                           i++;
}                              }
```

**更复杂的例子**（需要满足支配条件）：

```
优化前:                              // x*y 不变，但不能无条件外提
for (i = 0; i < n; i++) {            // 因为 if 分支可能不执行
    if (cond) {
        a[i] = x * y;    // 只在 cond 为 true 时执行
    }
}

优化后（如果能证明 cond 恒为 true）:
t = x * y;
for (i = 0; i < n; i++) {
    a[i] = t;
}
```

### 6.4.2 循环展开（Loop Unrolling）

**原理**：将循环体复制多份，减少循环控制的开销（比较、跳转）。

**示例**（展开因子 4）：

```
优化前:                         优化后:
for (i = 0; i < n; i++) {     for (i = 0; i < n - 3; i += 4) {
    sum += a[i];                   sum += a[i];
}                                  sum += a[i+1];
                                   sum += a[i+2];
                                   sum += a[i+3];
                               }
                               // 处理剩余元素
                               for (; i < n; i++) {
                                   sum += a[i];
                               }
```

**循环展开的好处**：
1. **减少循环控制开销**：比较和跳转次数减少
2. **暴露更多优化机会**：展开后可以进行更多的指令调度和 CSE
3. **提高指令级并行（ILP）**：更多的独立指令可以让 CPU 流水线更满
4. **减少分支预测失败**：更少的循环回跳

**循环展开的代价**：
1. **代码体积增大**：可能降低指令缓存命中率
2. **寄存器压力增大**：更多的变量需要同时存活
3. **编译时间增加**

**编译器如何选择展开因子**：
- 通常展开 2、4 或 8 次
- 考虑循环体的大小和寄存器压力
- 有时由编译器选项控制（如 GCC 的 `-funroll-loops`）

### 6.4.3 归纳变量优化（Induction Variable Optimization）

**归纳变量**是循环中以固定增量变化的变量。

**基本归纳变量**：循环控制变量本身，如 `i` 在 `for (i = 0; i < n; i++)` 中。

**派生归纳变量**：由基本归纳变量通过线性变换得到的变量，如 `j = 4*i + 100`。

**优化技术**：

**1. 归纳变量强度削弱**

```
优化前:                         优化后:
for (i = 0; i < n; i++) {     j = 100;
    j = 4 * i + 100;           for (i = 0; i < n; i++) {
    a[j] = 0;                      a[j] = 0;
}                                  j = j + 4;
                               }
```

**2. 归纳变量消除**

```
优化前:                         优化后:
i = 0;                         j = 0;
j = 0;                         while (j < n * 4) {
while (i < n) {                    a[j] = 0;
    a[j] = 0;                      j += 4;
    i++;                        }
    j += 4;
}
```

这里完全消除了 `i`，只使用 `j` 来控制循环。

**3. 线性函数测试替换（Linear Function Test Replacement, LFTR）**

```
优化前:                         优化后:
for (i = 0; i < n; i++) {     t = 4 * n;       // 用 t 替代循环内的 4*i < 4*n
    j = 4 * i;                 j = 0;
    if (j < 4 * n) {           while (j < t) {
        a[j] = 0;                  a[j] = 0;
    }                              j += 4;
}                              }
```

配套的 Python 实现请参见 `loop_optimizer.py`。

---

## 6.5 全局优化与数据流分析

全局优化作用于整个函数，需要通过**数据流分析（Data Flow Analysis, DFA）** 来收集信息。

### 6.5.1 数据流分析框架

所有数据流分析都可以统一在一个框架下：

```
┌──────────────────────────────────────────────────┐
│           数据流分析通用框架                       │
├──────────────────────────────────────────────────┤
│                                                  │
│  格 (Lattice):    信息的取值集合和偏序关系         │
│  方向 (Direction): 正向 或 反向                   │
│  传递函数 (Transfer): 每条指令如何改变数据流信息   │
│  合并操作 (Meet/Join): 多条路径的信息如何合并       │
│  初始值 (Init):      入口/出口的默认值             │
│                                                  │
│  求解方式: 不动点迭代                              │
│                                                  │
└──────────────────────────────────────────────────┘
```

**正向分析 vs 反向分析**：

```
正向分析（如到达定义、可用表达式）：
  信息从入口流向出口
  IN[B] = ∪ OUT[P]    (P 是 B 的前驱)
  OUT[B] = f_B(IN[B])

反向分析（如活跃变量分析）：
  信息从出口流向入口
  OUT[B] = ∪ IN[S]     (S 是 B 的后继)
  IN[B] = f_B(OUT[B])
```

### 6.5.2 活跃变量分析（Live Variable Analysis）

**目的**：在程序的每个点，确定哪些变量在后续可能被使用（即"活跃的"）。这对**寄存器分配**至关重要。

**定义**：变量 v 在点 p 是**活跃的**，当且仅当存在一条从 p 到某个使用 v 的路径，且该路径上没有对 v 的重新定义。

**类型**：反向分析

**数据流方程**：

```
OUT[B] = ∪ IN[S]                    (S ∈ succ(B))
IN[B]  = USE[B] ∪ (OUT[B] - DEF[B])
```

其中：
- `USE[B]`：在 B 中被使用且在使用前未被定义的变量集合
- `DEF[B]`：在 B 中被定义（赋值）的变量集合

**示例**：

```
BB1: a = 1        DEF = {a}, USE = {}
     b = 2        DEF = {b}, USE = {}

BB2: c = a + b    DEF = {c}, USE = {a, b}
     d = a * 2    DEF = {d}, USE = {a}
     if c goto BB4 else BB3

BB3: a = d + 1    DEF = {a}, USE = {d}
     goto BB2

BB4: return d     DEF = {},  USE = {d}
```

活跃变量分析结果（反向计算）：

```
IN[BB4]  = {d}
OUT[BB3] = {a, b}         (来自 BB2 的 IN)
IN[BB3]  = {a, b, d}      (USE ∪ (OUT - DEF) = {d} ∪ {a,b} - {a} = {a,b,d})
OUT[BB2] = IN[BB3] ∪ IN[BB4] = {a, b, d} ∪ {d} = {a, b, d}
IN[BB2]  = {a, b, d}      (USE{a,b} ∪ ({a,b,d} - {c,d})) = {a,b} ∪ {a,b} = {a,b,d}
OUT[BB1] = IN[BB2] = {a, b, d}
IN[BB1]  = {d}            (USE{} ∪ ({a,b,d} - {a,b})) = {d}
```

### 6.5.3 到达定义分析（Reaching Definition Analysis）

**目的**：在程序的每个点，确定哪些变量的定义可能"到达"该点（即从定义点到该点存在一条路径，且该路径上没有对同一变量的重新定义）。

**类型**：正向分析

**数据流方程**：

```
IN[B]  = ∪ OUT[P]                   (P ∈ pred(B))
OUT[B] = GEN[B] ∪ (IN[B] - KILL[B])
```

其中：
- `GEN[B]`：B 中生成的定义（B 中对变量的赋值）
- `KILL[B]`：B 中杀死的定义（B 中的赋值使之前的定义失效）

**示例**：

```
BB1: (1) d1: x = 5         GEN = {d1},  KILL = {d2,d5}
     (2) d2: y = 1         GEN = {d2},  KILL = {}

BB2: (3) d3: x = x + 1    GEN = {d3},  KILL = {d1,d3,d5}
     (4) d4: y = y * x    GEN = {d4},  KILL = {d2,d4}
     if y < 10 goto BB2 else BB3

BB3: (5) d5: x = y - 1    GEN = {d5},  KILL = {d1,d3,d5}
     return x

到达定义计算（正向，固定点迭代）:

迭代1:
  IN[BB1] = {} (入口)
  OUT[BB1] = {d1, d2}
  IN[BB2] = {d1, d2} ∪ OUT[BB2]
  OUT[BB2] = {d3, d4} ∪ ({d1,d2} ∪ OUT[BB2] - {d1,d2,d3,d4,d5}) ...

经过多轮迭代到达不动点后：
  IN[BB3] = {d3, d4}   // 到达 BB3 的定义
  // 表示 x 的最后定义是 d3, y 的最后定义是 d4
```

### 6.5.4 可用表达式分析（Available Expression Analysis）

**目的**：在程序的每个点，确定哪些表达式已经被计算过且操作数未被修改。用于**全局公共子表达式消除（Global CSE）**。

**类型**：正向分析（使用交集作为合并操作）

**数据流方程**：

```
IN[B]  = ∩ OUT[P]                   (P ∈ pred(B))   ← 注意是交集！
OUT[B] = GEN[B] ∪ (IN[B] - KILL[B])
```

- `GEN[B]`：B 中计算的表达式
- `KILL[B]`：B 中修改的操作数所影响的所有表达式

**为什么用交集而不是并集？**
- 可用表达式要求表达式在**所有**路径上都被计算过且未被修改
- 只要有一条路径上操作数被修改了，表达式就不再可用

**示例**：

```
BB1: a = b + c        GEN = {b+c}
     d = b - c        GEN = {b-c}

BB2: e = b + c        // b+c 是否可用？取决于从 BB1 到 BB2 是否有路径修改了 b 或 c
     f = e + d
```

如果 BB1 直接跳转到 BB2（没有其他路径），则 `b+c` 在 BB2 入口可用，`e = b + c` 可以被消除为 `e = a`。

### 6.5.5 不动点迭代算法

所有数据流分析最终都归结为求解一组方程的**不动点（Fixed Point）**。

**算法**：

```
输入: CFG, 传递函数, 合并操作, 初始值
输出: 每个基本块的 IN 和 OUT 信息

1. 初始化所有基本块的 IN/OUT 为初始值
2. 将所有基本块加入工作列表 (worklist)
3. while 工作列表非空:
4.     从工作列表取出一个基本块 B
5.     计算新的 IN[B] = merge(OUT[P] for P in pred(B))
6.     计算新的 OUT[B] = f_B(IN[B])
7.     if OUT[B] 发生了变化:
8.         将 B 的所有后继加入工作列表
9. return 所有基本块的 IN/OUT
```

**为什么一定能收敛？**

数据流分析基于**格理论（Lattice Theory）**：
- 信息的取值构成一个**半格**（semilattice），有上界/下界
- 每次迭代要么使信息值上升（正向分析中的并集）要么下降（交集）
- 值的"高度"是有限的（格是有限高度的）
- 因此迭代必然在有限步内收敛到不动点

**复杂度**：对于有限高度 h 的格，迭代次数 ≤ h × |N|，其中 |N| 是基本块数量。

**遍历策略**：

| 策略 | 说明 | 适用场景 |
|------|------|---------|
| 深度优先 | 沿 DFS 树的后序遍历 | 通常收敛较快 |
| 逆后序 | 后序的逆序 | 正向分析通常用此 |
| 工作列表 | 仅处理变化的块 | 最实用的方法 |

配套的 Python 实现请参见 `optimizer.py`。

---

## 6.6 过程间优化

过程间优化（Interprocedural Optimization, IPO）跨越函数边界，可以发现函数之间相互影响的优化机会。

### 6.6.1 函数内联（Function Inlining）

**原理**：将函数调用替换为函数体本身，消除调用开销并暴露更多优化机会。

**这是最重要的过程间优化**。

**示例**：

```c
// 优化前
inline int square(int x) {
    return x * x;
}

int compute(int a, int b) {
    return square(a) + square(b);
}

// 优化后（内联后）
int compute(int a, int b) {
    return a * a + b * b;
}
```

**内联的好处**：
1. **消除调用开销**：保存/恢复寄存器、参数传递、跳转
2. **暴露优化机会**：内联后可以进行常量折叠、CSE 等
3. **减少间接跳转**：有利于 CPU 分支预测
4. **更好的指令调度**：编译器可以看到更大的代码块

**内联的代价**：
1. **代码膨胀**：可能导致指令缓存不命中
2. **编译时间增加**：更多的代码需要优化
3. **调试困难**：内联后的函数无法设置断点

**内联决策**（编译器如何决定是否内联）：

```
典型的内联启发式规则：
1. 函数体大小 < 阈值（如 GCC 默认约 500 条 RTL 指令）
2. 调用次数少（如只调用 1 次则几乎总是内联）
3. 函数是"热"的（profiling 信息显示频繁调用）
4. 参数是常量（内联后可以常量传播）
5. 不包含递归（直接递归通常不内联，间接递归更复杂）
```

### 6.6.2 过程间常量传播（Interprocedural Constant Propagation）

**原理**：在调用者和被调用者之间传播常量信息。

**示例**：

```c
void process(int mode) {
    if (mode == 0) {
        // 快速路径
    } else {
        // 慢速路径
    }
}

int main() {
    process(0);  // mode 始终为 0
    // ...
}
```

过程间常量传播可以：
1. 确定 `process(0)` 中 `mode` 始终为 0
2. 消除 `else` 分支（死代码消除）
3. 将 `process` 内联后直接使用快速路径

### 6.6.3 别名分析（Alias Analysis）

**问题**：两个指针是否可能指向同一内存位置？

```c
void foo(int *p, int *q) {
    *p = 10;
    *q = 20;
    return *p;  // p 和 q 是否可能相同？
}
```

如果 `p` 和 `q` 不可能别名（指向同一地址），则 `return *p` 可以优化为 `return 10`。

**别名分析方法**：

| 方法 | 精度 | 代价 | 说明 |
|------|------|------|------|
| **流不敏感** | 低 | 低 | 整个函数内统一判断 |
| **流敏感** | 中 | 中 | 考虑控制流顺序 |
| **路径敏感** | 高 | 高 | 考虑具体路径条件 |
| **上下文敏感** | 高 | 高 | 考虑调用上下文 |

**语言层面的别名规则**：
- **C99 `restrict`**：程序员承诺指针不与其他指针别名
- **C++ 引用**：引用一旦绑定不能改变
- **Rust 所有权系统**：编译时保证无别名（`&mut` 独占）

---

## 6.7 GCC 优化策略

GCC 提供了多级优化选项，每级包含不同的优化集合。

### 6.7.1 优化级别对比

| 级别 | 说明 | 编译时间 | 代码大小 | 执行速度 | 适用场景 |
|------|------|---------|---------|---------|---------|
| `-O0` | 无优化 | 最快 | 最大 | 最慢 | 调试阶段 |
| `-O1` | 基本优化 | 快 | 较小 | 较快 | 日常开发 |
| `-O2` | 推荐优化 | 中 | 较小 | 快 | 生产环境 |
| `-O3` | 激进优化 | 慢 | 可能增大 | 最快 | 高性能计算 |
| `-Os` | 优化大小 | 中 | 最小 | 中等 | 嵌入式/移动端 |
| `-Ofast` | 不安全优化 | 慢 | 可能增大 | 最快 | 科学计算 |

### 6.7.2 各级别包含的优化详解

**-O1 包含的优化**：
```
-fauto-inc-dec          自动增量/减量
-fbranch-count-reg      分支计数器
-fcombine-stack-adjustments  合并栈调整
-fcompare-elim          比较消除
-fcprop-registers       寄存器传播
-fdce                   死代码消除
-fdelayed-branch        延迟分支
-fdse                   死存储消除
-fguess-branch-probability  分支概率猜测
-fif-conversion         if 转换
-fif-conversion2        if 转换 v2
-finline-functions-called-once  内联只调用一次的函数
-fipa-modref            模引用分析
-fipa-profile           过程间分析
-fipa-pure-const        纯函数/常量识别
-fipa-reference         引用分析
-fipa-reference-addressable  可寻址引用
-fmerge-constants       合并相同常量
-fmove-loop-invariants  循环不变量外提
-fomit-frame-pointer    省略帧指针
-freorder-blocks        基本块重排
-fshrink-wrap           收缩包装
-fshrink-wrap-separate  分离收缩包装
-fsplit-wide-types      分割宽类型
-fssa-backprop          SSA 反向传播
-fssa-phiprop           SSA phi 传播
-ftree-ccp              条件常量传播
-ftree-ch               循环头复制
-ftree-coalesce-vars    变量合并
-ftree-copy-prop        复制传播
-ftree-dce              树级死代码消除
-ftree-ter              临时表达式替换
-funit-at-a-time        逐编译单元处理
```

**-O2 在 -O1 基础上增加**：
```
-falign-functions       函数对齐
-falign-jumps           跳转对齐
-falign-loops           循环对齐
-falign-labels          标签对弦
-fcaller-saves          调用者保存
-fcode-hoisting         代码提升
-fcrossjumping          交叉跳转
-fcse-follow-jumps      CSE 跟踪跳转
-fdevirtualize          去虚拟化
-fdevirtualize-speculatively  推测去虚拟化
-fexpensive-optimizations  昂贵优化
-fgcse                  全局 CSE
-fhoist-adjacent-loads  提升相邻加载
-finline-small-functions  内联小函数
-findirect-inlining    间接内联
-fipa-bit-cp            位复制传播
-fipa-cp                常量传播
-fipa-cp-clone          常量传播克隆
-fipa-icf               相同代码折叠
-fipa-ra                返回地址优化
-fipa-sra               标量替换聚合体
-fipa-vrp               值范围传播
-fisolate-erroneous-paths-dereference  隔离错误路径
-fisolate-erroneous-paths-attribute    隔离错误路径属性
-flra-remat             寄存器分配重物化
-foptimize-sibling-calls  兄弟调用优化
-fpartial-inlining      部分内联
-fpeephole2             窥孔优化 v2
-freorder-blocks-algorithm=stc  基本块重排算法
-freorder-blocks-and-partition  基本块重排和分区
-freorder-functions     函数重排
-frerun-cse-after-loop  循环后重新 CSE
-fschedule-insns        指令调度
-fschedule-insns2       指令调度 v2
-fsched-interblock      跨块调度
-fsched-spec            推测调度
-fstore-merging         存储合并
-ftree-bit-ccp          位条件常量传播
-ftree-builtin-call-dce 内置函数调用死代码消除
-ftree-cselim           条件存储消除
-ftree-dse              树级死存储消除
-ftree-forwprop         前向传播
-ftree-fre              完全冗余消除
-ftree-loop-distribute-patterns  循环模式分布
-ftree-loop-distribution 循环分布
-ftree-loop-vectorize   循环向量化
-ftree-partial-pre      部分部分冗余消除
-ftree-phiprop          phi 传播
-ftree-pre              部分冗余消除
-ftree-slp-vectorize    SLP 向量化
-ftree-slsr             直线序列重写
-ftree-sra              标量替换聚合体
-ftree-ter              临时表达式替换优化
-fvect-cost-model       向量代价模型
-fipa-modref            过程间 mod-ref
```

**-O3 在 -O2 基础上增加**：
```
-fgcse-after-reload     重载后全局 CSE
-finline-functions      内联所有"合适"的函数
-fipa-cp-clone          常量传播克隆
-floop-interchange      循环交换
-floop-unroll-and-jam   循环展开并融合
-fpeel-loops            循环剥离
-fpredictive-commoning  预测公共化
-fsplit-paths           分割路径
-ftree-loop-distribute-patterns  循环模式分布
-ftree-loop-vectorize   循环向量化
-ftree-partial-pre      部分部分冗余消除
-ftree-slp-vectorize    SLP 向量化
-funswitch-loops        循环外提不变条件
-fvect-cost-model=dynamic  动态向量代价模型
-fversion-loops-to-stride  循环步长化
```

**-Os（优化大小）**：
- 包含 -O2 的大部分优化
- **禁用**增加代码大小的优化：
  - 不对齐函数/循环/跳转
  - 不展开循环
  - 不内联非小函数
  - 更保守的向量化

**-Ofast（不安全优化）**：
- 包含 -O3 的所有优化
- **加上**可能违反标准的优化：
  - `-ffast-math`：不保证浮点精度（不遵守 IEEE 754）
    - 允许重排浮点运算
    - 假设 NaN 和 Inf 不存在
    - 假设没有有符号溢出
  - `-fallow-store-data-races`：允许存储竞争

### 6.7.3 使用建议

```
开发调试阶段:
  gcc -O0 -g -Wall -Wextra source.c    // 禁用优化，保留调试信息

日常开发:
  gcc -O1 source.c                      // 轻量优化，编译快

生产发布:
  gcc -O2 source.c                      // 推荐的平衡点

极致性能:
  gcc -O3 -march=native source.c        // 激进优化 + 本机指令集

极致大小:
  gcc -Os -march=native source.c        // 优化体积

科学计算（可接受浮点误差）:
  gcc -Ofast -march=native source.c     // 不安全但最快

Profile-Guided Optimization (PGO):
  gcc -O2 -fprofile-generate source.c   // 第一步：插桩编译
  ./a.out                                // 第二步：运行收集数据
  gcc -O2 -fprofile-use source.c        // 第三步：使用数据重新编译

Link-Time Optimization (LTO):
  gcc -O2 -flto source1.c source2.c     // 链接时全局优化
```

---

## 6.8 Python/JS/LuaJIT 的优化策略

### 6.8.1 CPython 的优化策略

CPython 作为解释器，优化能力有限，但仍在多个层面进行优化：

**编译时优化（字节码级别）**：

```python
# 常量折叠
x = 3 + 5           # 编译时计算为 x = 8
y = "hello" * 3     # 编译时计算为 y = "hellohellohello"

# 可以用 dis 模块查看
import dis
dis.dis('x = 3 + 5')
#  1           0 LOAD_CONST               0 (8)
#              2 STORE_NAME               0 (x)
#              4 LOAD_CONST               1 (None)
#              6 RETURN_VALUE
```

**运行时优化**：

| 机制 | 说明 |
|------|------|
| **整数小对象池** | -5 到 256 的整数被缓存和复用 |
| **字符串驻留** | 短字符串和标识符字符串被驻留（interning） |
| **字典优化** | 类属性使用共享键（shared keys） |
| **帧对象缓存** | 函数调用的帧对象被缓存和复用 |
| **内联缓存** | 属性访问使用内联缓存加速 |

**CPython 3.11+ 的重大改进**：

```
CPython 3.11 引入了 "Specializing Adaptive Interpreter"（特化自适应解释器）：
1. 字节码在首次执行时被"特化"为针对具体类型的版本
2. 例如 BINARY_ADD 被特化为 BINARY_ADD_INT（纯整数加法）
3. 特化后的字节码跳过了类型检查，直接执行

性能提升：CPython 3.11 比 3.10 平均快 25%
```

**CPython 3.13+ 的 JIT（实验性）**：

```
CPython 3.13 引入了实验性的复制基础 JIT（Copy-and-Patch JIT）：
- 将热点字节码编译为机器码
- 目前仍在积极开发中
- 预期将显著提升纯 Python 代码的性能
```

### 6.8.2 V8（JavaScript）的优化策略

V8 是 Google 的 JavaScript 引擎，采用了**多层编译架构**：

```
JavaScript 源代码
       │
       ▼
┌──────────────┐
│   Parser     │  解析为 AST
└──────┬───────┘
       │
       ▼
┌──────────────┐
│  Ignition    │  字节码解释器（基线执行）
│  (解释器)     │  快速启动，收集类型反馈
└──────┬───────┘
       │ 热点函数
       ▼
┌──────────────┐
│  Sparkplug   │  基线 JIT（快速编译，无优化）
│  (基线编译)   │  直接将字节码转为机器码
└──────┬───────┘
       │ 更热的函数
       ▼
┌──────────────────────────────┐
│  Maglev                      │  中级优化编译器（V8 11.7+）
│  (中级优化编译)               │  替代了之前的 TurboFan 的部分职责
└──────┬───────────────────────┘
       │ 极热函数
       ▼
┌──────────────────────────────┐
│  TurboFan                    │  高级优化编译器
│  (高级优化编译)               │  全面优化（内联、逃逸分析、向量化等）
└──────────────────────────────┘
```

**V8 的关键优化技术**：

| 技术 | 说明 |
|------|------|
| **隐藏类（Hidden Classes）** | 为对象形状创建类型信息，加速属性访问 |
| **内联缓存（Inline Caches, IC）** | 缓存属性查找结果 |
| **逃逸分析** | 如果对象不逃逸函数，可以分配在栈上 |
| **标量替换** | 将对象拆分为单独的变量 |
| **On-Stack Replacement (OSR)** | 在函数执行过程中切换到优化版本 |
| **Deoptimization** | 如果优化假设不成立，回退到未优化版本 |

### 6.8.3 LuaJIT 的优化策略

LuaJIT 是 Lua 的即时编译器，以其惊人的性能著称（接近 C 的速度）。

**LuaJIT 的架构**：

```
Lua 源代码
    │
    ▼
┌──────────────┐
│   解释器     │  极快的字节码解释器
│   (vm_*)     │  手写的汇编解释器
└──────┬───────┘
       │ 热点检测（hotcount）
       ▼
┌──────────────┐
│   Trace      │  跟踪编译器
│   Compiler   │  只编译"热路径"
└──────────────┘
```

**跟踪编译（Trace Compilation）** vs **方法编译（Method Compilation）**：

```
方法编译（如 V8、HotSpot）：
  编译整个函数
  优点：可以处理所有路径
  缺点：需要类型推断，处理多态代码困难

跟踪编译（如 LuaJIT）：
  只编译实际执行的"热路径"
  优点：类型信息在跟踪时已知，编译简单高效
  缺点：只覆盖执行过的路径，需要在路径偏离时"侧出口"
```

**LuaJIT 的关键优化**：

| 技术 | 说明 |
|------|------|
| **类型推断** | 跟踪时记录类型，生成类型特化代码 |
| **SSA 优化** | 对跟踪进行 SSA 变换后做标准优化 |
| **NaN 装箱** | 利用 NaN 的位模式存储类型标签和指针 |
| **分配消除** | 不逃逸的表/闭包不实际分配内存 |
| **FFI** | 直接调用 C 函数，零开销 |
| **SIMD** | 利用 SSE2/AVX 指令加速数值计算 |

---

## 6.9 示例代码说明

本章提供了三个 Python 实现文件和一个 C 示例文件：

### cfg_builder.py

**功能**：从三地址码构建控制流图

```
主要特性：
  - 从文本形式的三地址码自动划分基本块
  - 构建 CFG 数据结构（前驱/后继关系）
  - 计算支配树（使用迭代算法）
  - ASCII 可视化输出 CFG

使用方法：
  python cfg_builder.py

输出示例：
  Basic Blocks:
    BB0: entry
    BB1: loop_header
    ...

  CFG Edges:
    BB0 -> BB1
    BB1 -> BB2 (true), BB1 -> BB3 (false)
    ...

  Dominator Tree:
    BB0
    ├── BB1
    │   ├── BB2
    │   └── BB3
    └── BB4
```

### optimizer.py

**功能**：实现多种局部和全局优化

```
主要特性：
  - 常量折叠（Constant Folding）
  - 常量传播（Constant Propagation）
  - 死代码消除（Dead Code Elimination）
  - 公共子表达式消除（CSE）
  - 活跃变量分析（Live Variable Analysis）
  - 优化前后对比输出

使用方法：
  python optimizer.py

输出示例：
  === 优化前 ===
  BB0:
    x = 3 + 5
    y = x * 2
    z = y + 1
    w = 42       // dead code
    return y

  === 优化后 ===
  BB0:
    y = 16
    return y
```

### loop_optimizer.py

**功能**：实现循环相关的优化

```
主要特性：
  - 循环识别（基于 CFG 的回边分析）
  - 循环不变量外提（LICM）
  - 循环展开（Loop Unrolling）
  - 优化前后对比输出

使用方法：
  python loop_optimizer.py

输出示例：
  === 优化前 ===
  BB_loop:
    t = x * y + z   // 循环不变量
    sum = sum + t
    i = i + 1
    if i < n goto BB_loop

  === 优化后 (LICM) ===
  t = x * y + z     // 外提到循环前
  BB_loop:
    sum = sum + t
    i = i + 1
    if i < n goto BB_loop
```

### test_optimization.c

**功能**：展示各种优化机会的 C 代码示例

```
包含以下优化场景：
  1. 常量折叠    - a = 3 + 5
  2. 常量传播    - x = 5; y = x + 3
  3. 死代码      - 未使用的变量和不可达分支
  4. 循环不变量  - 循环体中的不变计算
  5. 强度削弱    - 循环中的乘法 → 加法
  6. 循环展开    - 简单循环的展开
  7. 公共子表达式 - 重复计算的表达式

编译对比：
  gcc -O0 -S test_optimization.c -o unoptimized.s
  gcc -O2 -S test_optimization.c -o optimized.s
  diff unoptimized.s optimized.s
```

---

## 总结

```
┌────────────────────────────────────────────────────────────┐
│                    优化技术全景图                            │
├────────────────────────────────────────────────────────────┤
│                                                            │
│  基础设施:  CFG → 支配树 → 数据流分析                        │
│                                                            │
│  局部优化:  常量折叠 → 常量传播 → CSE → 死代码消除 → 强度削弱  │
│                                                            │
│  循环优化:  LICM → 循环展开 → 归纳变量优化                    │
│                                                            │
│  全局优化:  活跃变量 → 到达定义 → 可用表达式 → 全局 CSE       │
│                                                            │
│  过程间:    内联 → 过程间常量传播 → 别名分析                   │
│                                                            │
│  实践:      -O0 → -O1 → -O2 → -O3 → -Ofast               │
│             PGO + LTO = 最大性能                             │
│                                                            │
│  现代 JIT:  V8(多层) / LuaJIT(跟踪) / CPython(3.11+特化)   │
│                                                            │
└────────────────────────────────────────────────────────────┘
```

---

## 参考资料

1. **编译器设计**：Aho, Lam, Sethi, Ullman - *Compilers: Principles, Techniques, and Tools* (龙书)
2. **优化技术**：Muchnick - *Advanced Compiler Design and Implementation*
3. **数据流分析**：Nielson, Nielson, Hankin - *Principles of Program Analysis*
4. **GCC 文档**：https://gcc.gnu.org/onlinedocs/gcc/Optimize-Options.html
5. **V8 博客**：https://v8.dev/blog
6. **LuaJIT**：https://luajit.org/luajit.html
