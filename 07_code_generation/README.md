# 第7章 目标代码生成

> 代码生成器（Code Generator）是编译器的最后一个重要阶段，负责将前端产生的中间表示（IR）翻译为目标机器可执行的代码。本章深入讲解代码生成的核心技术与实践。

---

## 目录

- [7.1 代码生成概述](#71-代码生成概述)
- [7.2 目标机器架构](#72-目标机器架构)
- [7.3 指令选择](#73-指令选择)
- [7.4 寄存器分配](#74-寄存器分配)
- [7.5 指令调度](#75-指令调度)
- [7.6 栈帧管理与调用约定](#76-栈帧管理与调用约定)
- [7.7 GCC 代码生成流程](#77-gcc-代码生成流程)
- [7.8 MinGW 代码生成与 Windows 平台](#78-mingw-代码生成与-windows-平台)
- [7.9 示例代码说明](#79-示例代码说明)

---

## 7.1 代码生成概述

### 7.1.1 代码生成器的位置

在经典编译器架构中，代码生成器位于优化阶段之后：

```
源代码
  │
  ▼
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────────┐
│ 词法分析  │───▶│ 语法分析  │───▶│ 语义分析  │───▶│ 中间代码生成  │
└──────────┘    └──────────┘    └──────────┘    └──────────────┘
                                                       │
                                                       ▼
                                               ┌──────────────┐
                                               │   代码优化    │
                                               └──────────────┘
                                                       │
                                                       ▼
                                               ┌──────────────┐
                                               │  目标代码生成  │  ◀── 本章重点
                                               └──────────────┘
                                                       │
                                                       ▼
                                                  目标机器代码
```

### 7.1.2 输入与输出

| 项目 | 说明 |
|------|------|
| **输入** | 中间表示（三地址码、SSA形式、控制流图CFG等）+ 符号表信息 |
| **输出** | 目标机器代码（汇编代码或机器码） |
| **核心任务** | 指令选择、寄存器分配、指令调度 |

### 7.1.3 代码生成的主要挑战

1. **指令选择**：如何将IR中的操作映射到目标机器的指令集？一条IR可能对应多种指令序列。
2. **寄存器分配**：目标机器的寄存器数量有限，如何高效利用？何时将变量溢出到内存？
3. **指令调度**：如何重排指令以避免流水线停顿、充分利用指令级并行？
4. **调用约定**：函数调用时参数如何传递？返回值如何处理？栈帧如何管理？

### 7.1.4 代码质量的度量

- **正确性**：生成的代码必须与源程序语义一致
- **速度**：生成的代码执行效率要高
- **代码大小**：嵌入式场景下尤其重要
- **编译时间**：不能过于耗时（调试模式 vs 发布模式的取舍）

---

## 7.2 目标机器架构

### 7.2.1 x86 架构概述

x86 是 CISC（复杂指令集计算机）架构，特点：
- 变长指令编码（1~15字节）
- 大量内存操作数寻址模式
- 通用寄存器数量较少（32位模式仅8个通用寄存器）
- 条件码（EFLAGS）用于条件跳转

### 7.2.2 x86 寄存器

#### 32位寄存器（x86）

```
┌─────────────────────────────────────────────────────────────────┐
│                    x86-32 通用寄存器                              │
├─────────┬─────────┬─────────┬─────────┬─────────────────────────┤
│ 寄存器   │ 全32位   │ 低16位   │ 低8位   │ 高8位（仅AX/BX/CX/DX） │
├─────────┼─────────┼─────────┼─────────┼─────────────────────────┤
│ EAX     │ eax     │ ax      │ al      │ ah                      │
│ EBX     │ ebx     │ bx      │ bl      │ bh                      │
│ ECX     │ ecx     │ cx      │ cl      │ ch                      │
│ EDX     │ edx     │ dx      │ dl      │ dh                      │
│ ESI     │ esi     │ si      │ sil     │ —                       │
│ EDI     │ edi     │ di      │ dil     │ —                       │
│ EBP     │ ebp     │ bp      │ bpl     │ —                       │
│ ESP     │ esp     │ sp      │ spl     │ —                       │
└─────────┴─────────┴─────────┴─────────┴─────────────────────────┘
```

**各寄存器的传统用途：**

| 寄存器 | 用途 | 备注 |
|--------|------|------|
| EAX | 累加器，函数返回值 | `mul`/`div` 隐式使用 |
| EBX | 基址寄存器 | 通用，callee-saved |
| ECX | 计数器 | `loop`/`rep` 隐式使用，`shl`/`shr` 用 CL |
| EDX | 数据寄存器 | `mul`/`div` 隐式使用 |
| ESI | 源索引 | `movsb` 等串操作的源地址 |
| EDI | 目的索引 | `movsb` 等串操作的目的地址 |
| ESP | 栈指针 | 不可随意修改 |
| EBP | 帧指针 | 用于栈帧的基址寻址 |

#### 64位寄存器（x86-64）

x86-64 将通用寄存器扩展到16个：

```
┌─────────────────────────────────────────────────────────────────────┐
│                    x86-64 通用寄存器                                  │
├──────────┬──────────┬──────────┬──────────┬─────────────────────────┤
│ 寄存器    │ 全64位    │ 低32位    │ 低16位    │ 低8位                  │
├──────────┼──────────┼──────────┼──────────┼─────────────────────────┤
│ RAX      │ rax      │ eax      │ ax       │ al                     │
│ RBX      │ rbx      │ ebx      │ bx       │ bl                     │
│ RCX      │ rcx      │ ecx      │ cx       │ cl                     │
│ RDX      │ rdx      │ edx      │ dx       │ dl                     │
│ RSI      │ rsi      │ esi      │ si       │ sil                    │
│ RDI      │ rdi      │ edi      │ di       │ dil                    │
│ RBP      │ rbp      │ ebp      │ bp       │ bpl                    │
│ RSP      │ rsp      │ esp      │ sp       │ spl                    │
│ R8~R15   │ r8~r15   │ r8d~r15d │ r8w~r15w │ r8b~r15b              │
└──────────┴──────────┴──────────┴──────────┴─────────────────────────┘

特殊寄存器：
  RIP  — 指令指针（64位下支持 RIP-relative 寻址）
  RFLAGS — 标志寄存器
  XMM0~XMM15 — 128位SSE寄存器（浮点运算、SIMD）
  YMM0~YMM15 — 256位AVX寄存器
```

**x86-64 中 R8-R15 的命名约定：**
- `R8` = 64位，`R8D` = 低32位，`R8W` = 低16位，`R8B` = 低8位

### 7.2.3 寻址模式

x86 支持丰富的寻址模式，这对指令选择至关重要：

| 寻址模式 | 格式 | 示例 | 含义 |
|----------|------|------|------|
| 立即数 | `$imm` | `mov eax, 42` | 操作数是常数 |
| 寄存器 | `%reg` | `mov eax, ebx` | 操作数在寄存器中 |
| 直接寻址 | `addr` | `mov eax, [0x1234]` | 内存地址为常数 |
| 寄存器间接 | `(%reg)` | `mov eax, [ebx]` | 地址在寄存器中 |
| 基址+偏移 | `disp(%reg)` | `mov eax, [ebx+8]` | 地址 = reg + 偏移 |
| 基址+变址 | `(%base,%index)` | `mov eax, [ebx+esi]` | 地址 = base + index |
| 比例变址 | `disp(%base,%index,s)` | `mov eax, [ebx+esi*4+8]` | 地址 = base + index×scale + disp |

其中 scale 只能是 1、2、4、8（对应数据大小）。

**GAS（AT&T）语法 vs NASM（Intel）语法对比：**

```asm
; AT&T 语法 (GAS)              ; Intel 语法 (NASM)
movl $42, %eax                 mov eax, 42
movl (%ebx), %eax             mov eax, [ebx]
movl 8(%ebx), %eax            mov eax, [ebx + 8]
movl (%ebx,%esi,4), %eax     mov eax, [ebx + esi*4]
addl $1, %eax                 add eax, 1
```

### 7.2.4 指令格式

x86 指令的通用编码格式：

```
┌────────┬────────┬──────┬──────┬──────┬───────┬───────────┐
│ Prefix │ Opcode │ ModR/M │ SIB │ Disp │ Imm   │ 说明      │
│ 0~4 B  │ 1~3 B  │ 0~1 B │ 0~1B│0~4B │ 0~8B  │ 总长≤15B  │
└────────┴────────┴──────┴──────┴──────┴───────┴───────────┘
```

- **Prefix**：段覆盖（如 `FS:`）、操作数大小覆盖（`0x66`）、地址大小覆盖（`0x67`）、REX（64位）
- **Opcode**：操作码，确定操作类型
- **ModR/M**：编码寻址模式和寄存器操作数
- **SIB**：Scale-Index-Base，用于复杂地址计算
- **Displacement**：地址偏移量
- **Immediate**：立即数

### 7.2.5 栈帧结构

#### x86-32 栈帧（cdecl 调用约定）

```
高地址
┌─────────────────────────┐
│   调用者(caller)的栈帧    │
├─────────────────────────┤
│   返回地址 (Return Addr) │  ← call 指令压入
├─────────────────────────┤
│   保存的 EBP             │  ← EBP 指向此处
├─────────────────────────┤
│   局部变量 1             │  [EBP - 4]
├─────────────────────────┤
│   局部变量 2             │  [EBP - 8]
├─────────────────────────┤
│   ...                   │
├─────────────────────────┤
│   保存的寄存器            │  (callee-saved)
├─────────────────────────┤
│   临时空间 / 溢出变量     │  [EBP - N]
├─────────────────────────┤
│   函数参数（反向压栈）     │  [EBP + 8], [EBP + 12], ...
│   (由caller在调用前压入)   │
└─────────────────────────┘  ← ESP 指向当前栈顶
低地址
```

**函数序言（Prologue）和尾声（Epilogue）：**

```asm
; ===== 函数序言 =====
push ebp           ; 保存调用者的帧指针
mov  ebp, esp      ; 建立新的帧指针
sub  esp, N        ; 为局部变量分配空间（N为字节数，通常对齐到16字节）
push ebx           ; 保存 callee-saved 寄存器
push esi
push edi

; ===== 函数体 =====
; ... 业务逻辑 ...

; ===== 函数尾声 =====
pop  edi           ; 恢复 callee-saved 寄存器
pop  esi
pop  ebx
mov  esp, ebp      ; 释放局部变量空间（等价于 add esp, N）
pop  ebp           ; 恢复调用者的帧指针
ret                ; 返回
```

#### x86-64 栈帧（System V AMD64 ABI）

```
高地址
┌──────────────────────────┐
│   调用者的栈帧              │
├──────────────────────────┤
│   返回地址                  │
├──────────────────────────┤
│   保存的 RBP               │  ← RBP
├──────────────────────────┤
│   局部变量                  │
├──────────────────────────┤
│   red zone (128字节)       │  ← leaf function 可直接使用
├──────────────────────────┤
│   ...                     │
└──────────────────────────┘  ← RSP（必须16字节对齐）
低地址
```

**关键区别：**
- x86-64 前6个整数参数通过寄存器传递（RDI, RSI, RDX, RCX, R8, R9）
- 浮点参数使用 XMM0~XMM7
- RSP 必须在 `call` 指令执行时 16 字节对齐
- System V ABI 有 128 字节的 "red zone" 可供叶子函数使用

---

## 7.3 指令选择

### 7.3.1 指令选择的问题

将 IR 中的抽象操作映射到目标机器的具体指令序列。

**同一个 IR 操作可能有多种实现方式：**

```
; IR: t1 = a + b

; 方案1：需要 a 在内存中
mov eax, [a]
add eax, [b]
mov [t1], eax

; 方案2：如果 a 已经在寄存器中
add eax, ebx          ; 更短、更快

; 方案3：如果 t1 = a + 1
inc eax                ; 更短
```

### 7.3.2 模式匹配（Pattern Matching）

最直观的方法：将 IR 看作树结构，通过模式匹配选择指令。

**树形表示示例：**

```
源代码: x = a * b + c

IR 树：
        +
       / \
      *   c
     / \
    a   b

指令选择结果：
    mov eax, [a]      ; eax = a
    imul eax, [b]     ; eax = a * b
    add eax, [c]      ; eax = a * b + c
    mov [x], eax      ; x = eax
```

#### 自底向上树覆盖（Bottom-Up Tree Rewriting）

将树分解为若干子树，每个子树对应一条机器指令：

```
        +                    ┌─────┐
       / \                   │ add │
      *   c      ────▶      ┌┴────┴┐
     / \                     │imul │ c
    a   b                   ┌┴────┐
                            │ a   │ b
                            └─────┘
```

### 7.3.3 树覆盖（Tree Covering / Tiling）

**动态规划求最优覆盖：**

给定目标机器的指令模板集合，找到代价最小的树覆盖方案。

```
指令模板示例（BURG-like 规则）：

规则                          代价
─────────────────────────────────
reg → CONST(c)     => mov reg, c        1
reg → LOAD(mem)    => mov reg, [mem]    2
reg → ADD(reg,reg) => add reg, reg      1
reg → ADD(reg,mem) => add reg, [mem]    2
reg → MUL(reg,reg) => imul reg, reg     3
reg → SUB(reg,reg) => sub reg, reg      1
```

**覆盖过程（DP）：**

```
输入树:  ADD(MUL(LOAD(a), LOAD(b)), LOAD(c))

最优覆盖:
  ┌─────────────────────────────────────────┐
  │  tile 1: LOAD(a)    → mov eax, [a]     │  cost=2
  │  tile 2: LOAD(b)    → mov ecx, [b]     │  cost=2
  │  tile 3: MUL(reg,reg)→ imul eax, ecx   │  cost=3
  │  tile 4: LOAD(c)    → add eax, [c]     │  cost=2
  │  总代价: 9                              │
  └─────────────────────────────────────────┘
```

### 7.3.4 朴素代码生成算法

对于三地址码，可以使用简单的遍历算法：

```python
def generate_code(three_address_code):
    for instruction in three_address_code:
        # 检查 x = y op z
        if instruction is binary op:
            load y into a register R
            emit "op R, z"    # z 可以是寄存器或内存
            store R into x
            mark R 为 x 的持有者
        # 检查 x = y
        elif instruction is copy:
            load y into R
            store R into x
        # ...
```

**关键优化：**
- 如果 y 已经在寄存器 R 中，不需要 load
- 如果 R 中的值后续不再使用，可以直接覆盖
- 利用 LEA 指令进行地址计算（LEA 不修改标志位）

### 7.3.5 复杂指令的匹配

x86 有大量复杂指令，正确利用可以显著减少代码量：

```
; 利用 LEA 进行算术（不修改 EFLAGS）
; t = a + b * 4
lea eax, [ebx + ecx*4]    ; 一条指令替代 mov+shl+add

; 利用 TEST 进行比较
; if (a == 0)
test eax, eax              ; 比 cmp eax, 0 更短
jz   .Lzero

; 利用 MOVZX/MOVSX 进行类型转换
; int32_t x = (uint8_t)byte_val
movzx eax, byte [val]      ; 零扩展

; 利用 CMOV 进行条件赋值（无分支）
; x = (a > b) ? a : b
cmp  eax, ebx
cmovg eax, ebx             ; 如果 eax > ebx，则 eax = ebx
```

---

## 7.4 寄存器分配

### 7.4.1 问题定义

程序中的变量数量通常远超可用寄存器数量。寄存器分配的目标是：**在每个程序点，决定哪些变量保存在寄存器中，哪些溢出（spill）到内存。**

这是一个 NP-完全问题（在一般情况下），但存在高效的近似算法。

### 7.4.2 活性分析（Liveness Analysis）

寄存器分配的前提。变量 `v` 在程序点 `p` 处是**活跃的**，当且仅当存在从 `p` 到 `v` 的某个使用点的路径，且该路径上没有对 `v` 的定值。

```
; 示例：
; ① a = 1
; ② b = 2
; ③ c = a + b
; ④ d = a * b
; ⑤ e = c + d

在指令③处：
  活跃变量: a, b      (c 还未定义，d 还未使用但将被使用)

在指令④处：
  活跃变量: a, b, c   (d 即将被使用)
```

**数据流方程（活跃变量分析）：**

```
OUT[B] = ∪ IN[S]    （S 是 B 的所有后继基本块）
IN[B]  = USE[B] ∪ (OUT[B] - DEF[B])
```

### 7.4.3 干涉图（Interference Graph）

干涉图是寄存器分配的核心数据结构：

- **节点**：程序中的每个变量
- **边**：如果两个变量在同一时刻同时活跃，则它们之间有一条边

```
示例：
  ① a = 1          ; a 活跃
  ② b = 2          ; a, b 活跃
  ③ c = a + b      ; a(最后使用), b(最后使用), c 活跃
  ④ d = a * b      ; 此时 a 已死, c, d 活跃
  ⑤ e = c + d      ; c(最后使用), d(最后使用), e 活跃

干涉关系：
  a -- b    (②处同时活跃)
  a -- c    (③处 a 和 c 同时活跃)
  b -- c    (③处 b 和 c 同时活跃)
  c -- d    (④处同时活跃)
  d -- e    (⑤处同时活跃)

干涉图：
    a ── b
    │
    c ── d
         │
         e
```

### 7.4.4 图着色算法（Graph Coloring）

**核心思想：** 用 k 种颜色对干涉图着色（k = 可用寄存器数量），相邻节点不能同色。每种颜色对应一个寄存器。

#### Chaitin 算法

```
步骤：
  1. 构建干涉图
  2. 简化（Simplify）：
     - 如果存在度 < k 的节点，将其从图中移除并压栈
     - 如果所有节点度 >= k，选择一个节点标记为溢出（spill），移除并压栈
  3. 溢出（Spill）：
     - 如果有节点被标记为溢出，在代码中插入 load/store
     - 重新构建干涉图，重新开始
  4. 选择（Select）：
     - 从栈中依次弹出节点，分配一个与其邻居不同颜色
  5. 如果分配失败（某节点无法着色），需要溢出，回到步骤3
```

**示例：**

```
假设 k=3（3个寄存器），干涉图如下：

    a ── b
    │  ╲ │
    c ── d
         │
         e

简化过程：
  - e 的度为 1 < 3，移除 e，栈: [e]
  - a 的度为 2 < 3，移除 a，栈: [e, a]
  - c 的度为 1 < 3，移除 c，栈: [e, a, c]
  - b 的度为 1 < 3，移除 b，栈: [e, a, c, b]
  - d 的度为 0 < 3，移除 d，栈: [e, a, c, b, d]

选择过程：
  - 弹出 d → 分配 R1
  - 弹出 b → 分配 R2（不与 d 的 R1 冲突）
  - 弹出 c → 分配 R2（不与 d 的 R1 冲突）
  - 弹出 a → 分配 R3（不与 b(R2), c(R2) 冲突）
  - 弹出 e → 分配 R1（不与 d(R1)... wait, e 与 d 相邻）
  - 修正：弹出 e → 分配 R2 或 R3（不与 d(R1) 冲突）→ 分配 R2

最终分配：
  a → R3, b → R2, c → R2, d → R1, e → R2
```

### 7.4.5 溢出处理（Spill Handling）

当变量无法分配寄存器时，需要溢出到栈上：

```
原始代码：              溢出后：
  a = 1                  mov [spill_a], 1     ; a 溢出到栈
  b = 2                  mov [spill_b], 2     ; b 溢出到栈
  c = a + b              mov eax, [spill_a]   ; 溢出后需要每次从栈加载
                         add eax, [spill_b]
                         mov [spill_c], eax   ; c 也可能溢出
```

**溢出的代价：**
- 每次使用溢出变量需要额外的 load
- 每次定义溢出变量需要额外的 store
- 严重增加内存访问压力

### 7.4.6 线性扫描寄存器分配（Linear Scan）

Chaitin 图着色算法复杂度高，**线性扫描**是更快的替代方案，被 JIT 编译器广泛使用（如 LLVM、HotSpot C1）。

**算法：**

```
输入：活跃区间列表（按起始位置排序）
输出：寄存器分配方案

1. 计算每个变量的活跃区间 [start, end]
2. 按起始位置排序
3. 对每个活跃区间 interval:
     a. 过期处理：释放所有已结束的区间的寄存器
     b. 如果有空闲寄存器，分配一个
     c. 否则，选择一个最晚结束的活跃区间
        - 如果该区间结束时间晚于当前区间，溢出它
        - 否则，溢出当前区间
```

**示例：**

```
活跃区间：
  v1: [1, 5]
  v2: [2, 4]
  v3: [3, 8]
  v4: [6, 10]

可用寄存器: 2

处理过程：
  pos 1: v1 → R1
  pos 2: v2 → R2
  pos 4: v2 过期，R2 空闲
  pos 3: v3 → R2 (已在pos3分配)
  pos 5: v1 过期，R1 空闲
  pos 6: v4 → R1
  pos 8: v3 过期
  pos 10: v4 过期

结果：v1→R1, v2→R2, v3→R2, v4→R1，无溢出
```

#### 线性扫描的变种

| 变种 | 特点 |
|------|------|
| **基本线性扫描** | Poletto & Sarkar, 1999 |
| **线性扫描（SSA形式）** | 利用 SSA 的性质简化活跃区间计算 |
| **整数线性规划** | 用 ILP 求最优解，编译慢但代码质量高 |
| **Second-chance binpacking** | LLVM 使用，结合了线性扫描和溢出启发式 |

---

## 7.5 指令调度

### 7.5.1 为什么需要指令调度

现代处理器使用流水线（Pipeline）执行指令。如果下一条指令依赖上一条指令的结果，流水线就会停顿（stall）。

**流水线停顿示例：**

```
; 假设乘法延迟为 3 个周期
imul eax, ebx        ; 结果在 3 个周期后才可用
mov  ecx, eax        ; ← 停顿！eax 还没准备好（RAW 依赖）

; 调度后：
imul eax, ebx
mov  edx, [mem]      ; 插入独立指令，填充延迟
add  esi, edi        ; 继续填充
mov  ecx, eax        ; 现在 eax 已经准备好了
```

### 7.5.2 数据依赖关系

指令间存在三种依赖：

```
1. RAW（Read After Write）— 真依赖
   I1: add eax, ebx
   I2: mov ecx, eax     ; 读取 I1 写入的 eax

2. WAR（Write After Read）— 反依赖
   I1: mov ecx, eax     ; 读取 eax
   I2: add eax, ebx     ; 写入 eax（不能重排到 I1 之前）

3. WAW（Write After Write）— 输出依赖
   I1: mov eax, 1
   I2: mov eax, 2       ; 不能重排到 I1 之前
```

### 7.5.3 基本块内的指令调度

**列表调度（List Scheduling）算法：**

```
1. 构建依赖图（DAG）
2. 为每条指令计算优先级（如：最长路径优先）
3. 循环：
   a. 从就绪队列中选择优先级最高的指令
   b. 如果处理器资源可用，发射（issue）该指令
   c. 更新就绪队列
   d. 重复直到所有指令调度完毕
```

```
示例依赖图：

  I1: load a → R1          优先级: 3
   │
   ├─→ I3: mul R1, R2 → R3   优先级: 2
   │        │
   │        └─→ I5: store R3  优先级: 1
   │
   └─→ I4: add R1, R4 → R5   优先级: 2

  I2: load b → R2          优先级: 2

调度顺序（考虑延迟）：
  I1, I2, I4, I3, I5
  (I2 和 I1 可并行，I4 在 I1 之后但不依赖 I2)
```

### 7.5.4 跨基本块的调度

更复杂的调度策略需要跨越基本块边界：

- **循环展开 + 调度**：展开循环体以提供更大的调度窗口
- **软件流水线**：将不同迭代的操作交错执行
- **Trace Scheduling**：选择最可能执行的路径进行全局调度

---

## 7.6 栈帧管理与调用约定

### 7.6.1 调用约定概述

调用约定（Calling Convention）规定了：
1. 参数如何传递（寄存器 vs 栈）
2. 返回值如何传递
3. 哪些寄存器由调用者保存（caller-saved），哪些由被调用者保存（callee-saved）
4. 栈帧如何维护

### 7.6.2 cdecl（x86-32，C 默认）

```
参数传递：全部通过栈，从右到左压栈
返回值：EAX（整数），ST(0)（浮点）
Caller-saved：EAX, ECX, EDX
Callee-saved：EBX, ESI, EDI, EBP
栈清理：调用者（caller）清理栈

调用示例：foo(1, 2, 3)
  push 3          ; 参数 3（最右）
  push 2          ; 参数 2
  push 1          ; 参数 1（最左）
  call foo
  add  esp, 12    ; 调用者清理栈（3 × 4 字节）
```

### 7.6.3 stdcall（Win32 API 默认）

```
参数传递：全部通过栈，从右到左压栈
返回值：EAX
Callee-saved：EBX, ESI, EDI, EBP
栈清理：被调用者（callee）通过 RET n 清理栈

与 cdecl 的唯一区别：栈由被调用者清理
  ret 12          ; 等价于 pop 返回地址 + add esp, 12 + push 返回地址 + ret
```

### 7.6.4 fastcall（Windows）

```
参数传递：前两个整数参数用 ECX, EDX，其余通过栈
返回值：EAX
栈清理：被调用者

调用示例：foo(1, 2, 3, 4)
  push 4          ; 第4个参数通过栈
  push 3          ; 第3个参数通过栈
  mov  edx, 2     ; 第2个参数用 EDX
  mov  ecx, 1     ; 第1个参数用 ECX
  call foo
  ; 栈由 foo 通过 ret 8 清理
```

### 7.6.5 Microsoft x64 调用约定（Windows x64）

```
参数传递：
  整数/指针：RCX, RDX, R8, R9（前4个）
  浮点：XMM0, XMM1, XMM2, XMM3
  超过4个参数：通过栈传递
返回值：RAX（整数），XMM0（浮点）
Caller-saved：RAX, RCX, RDX, R8-R11, XMM0-XMM5
Callee-saved：RBX, RBP, RDI, RSI, R12-R15, XMM6-XMM15
Shadow space：调用者必须在栈上预留 32 字节的 shadow space
栈清理：调用者

调用示例：foo(1, 2, 3, 4, 5)
  sub  rsp, 32        ; shadow space
  mov  [rsp+32], 5    ; 第5个参数通过栈
  mov  r9d, 4         ; 第4个参数
  mov  r8d, 3         ; 第3个参数
  mov  edx, 2         ; 第2个参数
  mov  ecx, 1         ; 第1个参数
  call foo
  add  rsp, 32        ; 清理 shadow space
```

### 7.6.6 System V AMD64 ABI（Linux/macOS x64）

```
参数传递：
  整数/指针：RDI, RSI, RDX, RCX, R8, R9（前6个）
  浮点：XMM0-XMM7（前8个）
  超过6个整数/8个浮点：通过栈传递
返回值：RAX, RDX（64位可返回128位值），XMM0, XMM1
Caller-saved：RAX, RCX, RDX, RSI, RDI, R8-R11, XMM0-XMM15
Callee-saved：RBX, RBP, R12-R15
Shadow space：无
Red zone：RSP 下方 128 字节，叶子函数可直接使用

调用示例：foo(1, 2, 3, 4, 5, 6, 7)
  sub  rsp, 8         ; 对齐到16字节（如果需要）
  push 7              ; 第7个参数通过栈
  mov  r9d, 6         ; 第6个参数
  mov  r8d, 5         ; 第5个参数
  mov  ecx, 4         ; 第4个参数
  mov  edx, 3         ; 第3个参数
  mov  esi, 2         ; 第2个参数
  mov  edi, 1         ; 第1个参数
  call foo
  add  rsp, 16        ; 清理栈
```

### 7.6.7 各调用约定对比

| 特性 | cdecl | stdcall | fastcall | Win64 | SysV AMD64 |
|------|-------|---------|----------|-------|------------|
| 平台 | x86 | x86 | x86 | x64 Windows | x64 Linux/Mac |
| 整数参数 | 全栈 | 全栈 | ECX,EDX+栈 | RCX,RDX,R8,R9 | RDI,RSI,RDX,RCX,R8,R9 |
| 浮点参数 | 栈 | 栈 | 栈 | XMM0-3 | XMM0-7 |
| 栈清理 | caller | callee | callee | caller | caller |
| Shadow space | 无 | 无 | 无 | 32字节 | 无 |
| Red zone | 无 | 无 | 无 | 无 | 128字节 |

### 7.6.8 栈对齐要求

```
x86-32: 栈通常 4 字节对齐
x86-64: RSP 在 call 指令前必须 16 字节对齐
        （call 会压入 8 字节返回地址，所以函数入口时 RSP ≡ 8 mod 16）

示例（x64 函数需要额外对齐）：
  my_func:
    push rbp            ; RSP 现在 ≡ 0 mod 16
    mov  rbp, rsp
    sub  rsp, 48        ; 48 = 32(shadow) + 16(局部变量)，保持16对齐
    ; ...
    add  rsp, 48
    pop  rbp
    ret
```

---

## 7.7 GCC 代码生成流程

### 7.7.1 GCC 编译管线

GCC 的代码生成经历了多个中间表示的转换：

```
源代码
  │
  ▼
GENERIC（前端产生的通用树）
  │
  ▼
GIMPLE（简化后的三地址码形式）
  │  ← SSA 优化（常量传播、死代码消除、循环优化等）
  ▼
RTL (Register Transfer Language)
  │  ← 寄存器分配、指令调度、窥孔优化
  ▼
汇编代码（.s 文件）
  │
  ▼
目标文件（.o 文件，通过汇编器 as）
```

### 7.7.2 RTL（Register Transfer Language）

RTL 是 GCC 的核心代码生成 IR，它描述了寄存器之间的数据传输：

```lisp
;; RTL 示例：t = a + b

;; 定义一个加法操作
(set (reg:SI 77)                      ; 目标：伪寄存器 77
     (plus:SI (reg:SI 75)            ; 操作数1：伪寄存器 75 (a)
              (reg:SI 76)))          ; 操作数2：伪寄存器 76 (b)

;; 经过寄存器分配后，伪寄存器被替换为物理寄存器：
(set (reg:SI 0 eax)                   ; 目标：EAX
     (plus:SI (reg:SI 0 eax)          ; EAX = EAX + EBX
              (reg:SI 3 ebx)))

;; 最终生成汇编：
;; addl %ebx, %eax
```

**RTL 的关键概念：**
- **RTX (RTL Expression)**：RTL 的基本单元，类型包括 REG, MEM, CONST_INT, PLUS, SET 等
- **Machine Description (MD)**：每个目标机器提供 `.md` 文件，描述可用指令的 RTL 模式
- **Insn（指令）**：RTL 指令是 RTX 的链表

### 7.7.3 从 GIMPLE 到 RTL

GCC 在 `expand` 阶段将 GIMPLE 转换为 RTL：

```c
// GIMPLE（伪代码）
x = a + b;

// expand 为 RTL：
// 1. 将 a 加载到寄存器
// 2. 将 b 加载到寄存器
// 3. 执行加法
// 4. 存储结果到 x 的位置

// 具体 RTL 序列：
(set (reg:SI 75) (mem:SI (symbol_ref:SI "a")))
(set (reg:SI 76) (mem:SI (symbol_ref:SI "b")))
(set (reg:SI 77) (plus:SI (reg:SI 75) (reg:SI 76)))
(set (mem:SI (symbol_ref:SI "x")) (reg:SI 77))
```

### 7.7.4 Machine Description（机器描述）

每个目标架构都有一个 `.md` 文件定义指令模式：

```lisp
;; x86 机器描述片段 (i386.md)

(define_insn "addsi3"                    ; 加法模式名
  [(set (match_operand:SI 0 "register_operand" "=r")    ; 输出
        (plus:SI (match_operand:SI 1 "register_operand" "0")  ; 输入1
                 (match_operand:SI 2 "nonmemory_operand" "ri")))] ; 输入2
  ""
  "add{l}\t{%2, %0|%0, %2}"
  [(set_attr "type" "alu")
   (set_attr "mode" "SI")])
```

这个模式定义告诉 GCC：当需要将两个 32 位值相加并存入寄存器时，可以使用 `addl` 指令。

### 7.7.5 GCC 寄存器分配

GCC 使用基于图着色的寄存器分配器（Chaitin-Briggs 算法的变种）：

1. **构建干涉图**：分析变量的活跃范围
2. **合并（Coalesce）**：尝试将 MOVE 指令的源和目标合并为同一寄存器
3. **简化+选择**：图着色
4. **溢出**：无法着色的变量溢出到栈
5. **重试**：溢出后重新编译受影响的函数

---

## 7.8 MinGW 代码生成与 Windows 平台

### 7.8.1 MinGW 简介

MinGW（Minimalist GNU for Windows）是 GCC 在 Windows 上的移植版本，使用：
- GCC 作为编译器前端和后端
- Windows 的 COFF/PE 目标文件格式
- Windows 的链接器（ld 或 lld）
- MSVCRT（Microsoft Visual C Runtime）或 UCRT 作为 C 运行时

### 7.8.2 COFF（Common Object File Format）

COFF 是 Windows 上目标文件（.obj/.o）的标准格式：

```
┌──────────────────────────────────┐
│ COFF 文件头                       │
│  - Machine (0x14C = i386)       │
│  - NumberOfSections              │
│  - TimeDateStamp                 │
│  - SymbolTable offset            │
│  - NumberOfSymbols               │
├──────────────────────────────────┤
│ Optional Header (可选)            │
│  - Magic (0x10B = PE32)         │
│  - AddressOfEntryPoint           │
│  - ImageBase                     │
│  - SectionAlignment              │
│  - FileAlignment                 │
├──────────────────────────────────┤
│ Section Headers                  │
│  .text  — 代码段                  │
│  .data  — 已初始化数据             │
│  .bss   — 未初始化数据             │
│  .rdata — 只读数据                │
│  .edata — 导出表                  │
│  .idata — 导入表                  │
├──────────────────────────────────┤
│ Section Data                     │
│  .text: 机器码                    │
│  .data: 初始值                    │
│  ...                             │
├──────────────────────────────────┤
│ Symbol Table                     │
│  - 函数名、变量名                  │
│  - 节信息、存储类                  │
├──────────────────────────────────┤
│ String Table                     │
│  - 长名称存储                     │
└──────────────────────────────────┘
```

### 7.8.3 PE（Portable Executable）格式

PE 是 Windows 可执行文件（.exe/.dll）的格式，基于 COFF 扩展：

```
COFF 文件  ──链接──▶  PE 可执行文件

PE 结构：
┌────────────────────┐
│ DOS Header         │  ← "MZ" 签名
│ DOS Stub           │  ← "This program cannot be run in DOS mode"
├────────────────────┤
│ PE Signature       │  ← "PE\0\0"
│ COFF Header        │
│ Optional Header    │  ← PE 特有，包含入口点、导入表地址等
├────────────────────┤
│ Section Table      │
├────────────────────┤
│ .text              │  ← 代码
│ .data              │  ← 已初始化全局变量
│ .bss               │  ← 未初始化全局变量
│ .rdata             │  ← 只读数据、导入目录
│ .edata             │  ← 导出函数表（DLL）
│ .idata             │  ← 导入函数表
│ .reloc             │  ← 重定位表
│ .rsrc              │  ← 资源（图标、对话框等）
└────────────────────┘
```

### 7.8.4 Windows 链接过程

```
源文件 (.c)
    │
    ▼  MinGW GCC 编译
目标文件 (.o)  — COFF 格式
    │
    ▼  链接器 (ld / lld)
    │  - 解析符号引用
    │  - 合并节（sections）
    │  - 处理重定位
    │  - 链接导入库 (.a / .lib)
    ▼
可执行文件 (.exe)  — PE 格式
    │
    ▼  Windows 加载器 (ntdll.dll)
    │  - 映射到内存
    │  - 处理导入表（动态链接 DLL）
    │  - 处理重定位（如果地址不匹配 ImageBase）
    │  - 调用 DllMain / CRT 初始化
    │  - 跳转到入口点
    ▼
进程运行
```

### 7.8.5 MinGW 与 MSVC 的区别

| 特性 | MinGW (GCC) | MSVC |
|------|-------------|------|
| 编译器 | GCC | cl.exe |
| 汇编语法 | AT&T (GAS) | Intel (MASM) |
| 调用约定 | `__attribute__((cdecl))` 等 | `__cdecl`, `__stdcall` 等 |
| C 运行时 | MSVCRT / UCRT | CRT (MSVCRTxx.dll / UCRT) |
| 链接器 | ld | link.exe |
| 调试格式 | DWARF | PDB |
| 异常处理 | SJLJ / SEH / Dwarf2 | SEH (x64) |

### 7.8.6 MinGW 中的 C++ 名称修饰

```
源码：int foo(double x, const char* s)

MinGW (GCC) 修饰:  _Z3foodPKc
  _  — 前缀
  Z  — 表示后面是修饰名
  3foo — 函数名长度 + 名字
  d   — double 参数
  PKc — const char* 参数

MSVC 修饰:  ?foo@@YAHNPEBD@Z
  （不同的修饰方案）
```

---

## 7.9 示例代码说明

本章包含以下示例代码文件：

### 7.9.1 `code_generator.py`

**Python 实现的从三地址码到 x86 汇编的代码生成器。**

功能包括：
- **指令选择**：将三地址码（加、减、乘、除、赋值、比较、跳转、标签）翻译为 x86 指令
- **简单寄存器分配**：基于活跃性的简单寄存器分配策略
- **栈帧管理**：自动生成函数序言/尾声，管理局部变量空间
- **函数调用支持**：处理参数传递和返回值

运行方式：
```bash
python code_generator.py
```

代码结构：
```
RegisterAllocator  — 寄存器分配器
  ├── liveness_analysis()  — 活性分析
  └── allocate()           — 分配寄存器

CodeGenerator      — 代码生成器
  ├── generate()           — 主生成流程
  ├── emit_prologue()      — 函数序言
  ├── emit_epilogue()      — 函数尾声
  └── emit_instruction()   — 单条指令翻译
```

### 7.9.2 `calling_convention_demo.c`

**演示各种调用约定的 C 代码。**

包含：
- cdecl、stdcall、fastcall 调用约定的函数声明和调用
- 变参函数（va_list）在 cdecl 下的工作原理
- 内联汇编查看栈帧布局
- x64 调用约定对比

### 7.9.3 `simple_asm.asm`

**NASM 语法的 x86 汇编示例。**

包含：
- 基本数据移动指令（MOV, LEA, XCHG）
- 算术指令（ADD, SUB, IMUL, IDIV）
- 逻辑指令（AND, OR, XOR, SHL, SHR）
- 比较和条件跳转（CMP, TEST, JE, JNE, JG, JL）
- 栈操作（PUSH, POP）
- 函数调用（CALL, RET）和完整的栈帧管理
- 循环结构的汇编实现
- 字符串操作

---

## 总结

| 主题 | 核心要点 |
|------|---------|
| 指令选择 | 模式匹配、树覆盖、动态规划求最优覆盖 |
| 寄存器分配 | 干涉图、图着色（Chaitin-Briggs）、线性扫描（O(n)） |
| 指令调度 | 依赖图、列表调度、利用流水线并行性 |
| 调用约定 | 参数传递（寄存器 vs 栈）、callee/caller-saved、栈对齐 |
| GCC | GIMPLE → RTL → 汇编，Machine Description 驱动指令选择 |
| MinGW/Windows | COFF/PE 格式、Windows 链接过程、SEH 异常处理 |

---

## 参考资料

1. Aho, Lam, Sethi, Ullman. *Compilers: Principles, Techniques, and Tools* (Dragon Book), Chapter 8
2. Muchnick. *Advanced Compiler Design and Implementation*, Chapters 11-16
3. Poletto & Sarkar. "Linear Scan Register Allocation", ACM TOPLAS, 1999
4. Chaitin. "Register Allocation & Spilling via Graph Coloring", SIGPLAN 1982
5. GCC Internals Manual: https://gcc.gnu.org/onlinedocs/gccint/
6. System V AMD64 ABI: https://gitlab.com/x86-psABIs/x86-64-ABI
7. Microsoft x64 Calling Convention: https://learn.microsoft.com/en-us/cpp/build/x64-calling-convention
8. PE/COFF Specification: https://learn.microsoft.com/en-us/windows/win32/debug/pe-format
