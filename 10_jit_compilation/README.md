# 第10章：JIT编译（Just-In-Time Compilation）

> "JIT编译是解释执行和静态编译之间的最佳折中——它让你在开发时享受解释器的灵活性，在运行时获得编译器的高性能。"

---

## 目录

- [10.1 JIT编译概述](#101-jit编译概述)
- [10.2 JIT编译的基本原理](#102-jit编译的基本原理)
- [10.3 方法级JIT（以JVM为例）](#103-方法级jit以jvm为例)
- [10.4 追踪级JIT（以LuaJIT为例）](#104-追踪级jit以luajit为例)
- [10.5 V8引擎的JIT架构](#105-v8引擎的jit架构)
- [10.6 JIT编译中的优化技术](#106-jit编译中的优化技术)
- [10.7 JIT编译的内存管理](#107-jit编译的内存管理)
- [10.8 示例代码](#108-示例代码)

---

## 10.1 JIT编译概述

### 什么是JIT编译

JIT（Just-In-Time，即时编译）是一种在程序**运行时**将中间表示（通常是字节码）编译为本地机器码的技术。它结合了解释器的灵活性和静态编译器的高性能，是现代语言运行时的核心技术之一。

```
源代码 ──→ 编译器前端 ──→ 字节码 ──→ [解释执行]
                                      │
                                      │ 检测到热点
                                      ▼
                                  [JIT编译为机器码]
                                      │
                                      ▼
                                  [直接执行机器码]
```

JIT编译器的核心思想是：

1. **先解释执行**：程序启动时，使用解释器执行字节码，快速开始运行
2. **识别热点**：在运行过程中，识别出频繁执行的代码段（热点代码）
3. **即时编译**：将热点代码编译为高效的本地机器码
4. **替换执行**：后续执行到该代码段时，直接运行机器码

### JIT vs AOT（Ahead-Of-Time）编译

| 特性 | JIT编译 | AOT编译（静态编译） |
|------|---------|-------------------|
| **编译时机** | 运行时 | 编译时（构建阶段） |
| **启动速度** | 较慢（需要预热） | 快（直接执行机器码） |
| **峰值性能** | 可以超过AOT（利用运行时信息） | 取决于编译器的优化能力 |
| **运行时信息** | 可以利用（类型、分支概率等） | 无法利用 |
| **内存占用** | 较高（需要编译器和代码缓存） | 较低 |
| **平台依赖** | 运行时编译，天然跨平台 | 需要为每个平台编译 |
| **典型代表** | JVM HotSpot, V8, LuaJIT | GCC, Clang, Go |

**JIT的优势**：

- **投机优化（Speculative Optimization）**：基于运行时观察到的类型和行为进行假设性优化。例如，如果一个函数99%的情况下接收整数参数，JIT可以生成专门处理整数的机器码，只在遇到非整数参数时回退到通用路径。
- **运行时特化**：可以根据实际的类层次结构进行去虚化（devirtualization），将虚函数调用替换为直接调用。
- **自适应优化**：可以根据程序的实际行为动态调整优化策略。

**AOT的优势**：

- **启动即峰值**：不需要预热时间，程序启动后立即以最佳性能运行
- **可预测性**：没有JIT编译带来的延迟抖动（jitter）
- **内存效率**：不需要在运行时维护编译器基础设施

### JIT的历史

JIT编译的发展历程可以追溯到上世纪80年代：

**1983-1990：Self语言的开创性工作**

Self语言（由Sun Microsystems的David Ungar和Randall B. Smith设计）是JIT编译技术的先驱。Self团队面临一个严峻的问题：Self是一种高度动态的面向对象语言，纯解释执行的性能比C慢约100倍。

为了解决这个问题，Self团队开发了多项关键技术：
- **类型推测（Type Speculation）**：基于运行时观察推测变量类型
- **内联缓存（Inline Caching）**：缓存方法查找的结果
- **去优化（Deoptimization）**：当推测失败时回退到解释执行
- **自适应编译**：根据代码的热度选择不同的优化级别

这些工作直接影响了后来的JVM HotSpot编译器。

**1996-1999：Java HotSpot VM**

Sun Microsystems在收购了Self团队的核心成员后，将Self的技术应用到了Java虚拟机中。HotSpot VM引入了：
- 分层编译（Tiered Compilation）
- C1（客户端）和C2（服务端）两个编译器
- 成熟的去优化机制

**2008-至今：V8和现代JIT**

Google在2008年发布的V8引擎（用于Chrome浏览器的JavaScript引擎）将JIT技术推向了新的高度：
- 隐藏类（Hidden Classes）将动态语言的属性访问静态化
- 多层编译管线（Ignition → Sparkplug → Maglev → TurboFan）
- 精细的内联缓存（Inline Caching）

**2005-至今：LuaJIT**

Mike Pall开发的LuaJIT是追踪级JIT编译器的巅峰之作。尽管LuaJIT只针对Lua语言，但它的性能经常能媲美C代码，展示了追踪级JIT的强大潜力。

### 为什么需要JIT

**解释器太慢**

解释器在每条指令上都有固定的开销：
- 指令分派（dispatch）：每条指令都需要查表跳转
- 类型检查：动态类型语言每条指令都需要检查操作数类型
- 间接寻址：频繁的指针解引用导致缓存未命中
- 无法利用寄存器：解释器通常使用栈来管理操作数，无法充分利用CPU寄存器

典型的性能差距：纯解释执行比原生代码慢10-100倍。

**静态编译无法利用运行时信息**

静态编译器在编译时无法知道：
- 变量的实际类型分布
- 分支的实际执行概率
- 虚函数调用的实际目标
- 循环的实际迭代次数

JIT编译器可以在运行时收集这些信息，做出更好的优化决策。

---

## 10.2 JIT编译的基本原理

### 热点检测（Hot Spot Detection）

JIT编译器不会编译所有代码——编译本身是有成本的（时间 + 内存）。因此，JIT只编译那些**频繁执行**的代码段，即"热点"代码。

#### 计数器方法

最直观的热点检测方法是使用计数器。常见的策略有：

**方法级计数器**

为每个方法（或函数）维护一个调用计数器。当计数器达到阈值时，将该方法提交给JIT编译器。

```python
class MethodCounter:
    def __init__(self, threshold=10000):
        self.count = 0
        self.threshold = threshold
        self.compiled = False
    
    def increment(self):
        self.count += 1
        if self.count >= self.threshold and not self.compiled:
            self.compiled = True
            return True  # 触发编译
        return False
```

**回边计数器（Back-Edge Counter）**

专门用于检测热循环。每次循环跳转（回边）时递增计数器。JVM HotSpot使用这种方法来检测需要进行OSR（On-Stack Replacement）编译的热循环。

```
loop_start:
    ; ... 循环体 ...
    ; 回边：跳转回 loop_start
    back_edge_counter++
    if back_edge_counter >= threshold:
        trigger_osr_compilation()
    goto loop_start
```

**JVM HotSpot的实际策略**

HotSpot使用两个计数器的组合：
- **方法调用计数器（Invocation Counter）**：每次方法被调用时递增
- **回边计数器（Back-Edge Counter）**：每次循环回边执行时递增

当任一计数器超过阈值时，触发编译。回边计数器的阈值通常比方法调用计数器低，因为循环体通常是性能关键路径。

#### 采样方法

计数器方法的缺点是每次执行都有开销（递增计数器）。采样方法通过定期采样来降低开销：

**基于定时器的采样**

操作系统定时器定期中断程序执行，记录当前正在执行的方法。经过一段时间的采样，可以统计出哪些方法最频繁地被执行。

```python
import threading
import time
import collections

class SamplingProfiler:
    def __init__(self, interval=0.01):  # 10ms采样间隔
        self.interval = interval
        self.samples = collections.Counter()
        self.running = False
        self.current_method = None
    
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._sample_loop, daemon=True)
        self.thread.start()
    
    def _sample_loop(self):
        while self.running:
            if self.current_method:
                self.samples[self.current_method] += 1
            time.sleep(self.interval)
    
    def enter_method(self, name):
        self.current_method = name
    
    def get_hot_methods(self, top_n=10):
        return self.samples.most_common(top_n)
```

**采样的优缺点**：

- 优点：开销低，不会显著影响程序执行
- 缺点：精度较低，可能漏掉执行时间短但频繁调用的热点

**实际系统中的选择**

| 系统 | 方法 |
|------|------|
| JVM HotSpot | 计数器（方法调用计数器 + 回边计数器） |
| V8 | 计数器（反馈向量中的调用计数） |
| LuaJIT | 计数器（热循环阈值） |
| .NET CLR | 采样 + 计数器混合 |

### 编译粒度

JIT编译器可以以不同的粒度来编译代码：

#### 方法级JIT（Method-Based JIT）

将整个方法（函数）作为编译单元。

**工作流程**：

```
1. 方法被调用 → 递增调用计数器
2. 计数器超过阈值 → 将方法提交给JIT编译器
3. JIT编译器编译整个方法 → 生成机器码
4. 后续调用直接执行机器码
```

**优点**：
- 编译单元清晰，易于实现
- 可以对整个方法进行优化（内联、寄存器分配等）
- 与传统的静态编译器技术兼容

**缺点**：
- 可能编译了方法中不常执行的冷路径
- 编译大方法时延迟较高
- 无法有效优化跨越方法边界的热点路径

**典型代表**：JVM的C1/C2编译器

#### 追踪级JIT（Trace-Based JIT）

将一条从某个起点开始、沿单一执行路径的线性指令序列作为编译单元。

**什么是追踪（Trace）**

追踪是一条从某个位置（通常是循环头）开始，沿着程序的实际执行路径记录下来的线性指令序列。追踪中不包含分支——所有条件分支都沿着实际执行的方向展开，失败的分支通过"守卫"（Guard）跳转到"侧追踪"（Side Trace）或回退到解释器。

```
; 原始代码
for i in range(n):
    if x > 0:
        y = a[i] + b[i]
    else:
        y = a[i] - b[i]

; 追踪（假设 x > 0 总是成立）
loop_start:
    guard(x > 0)          ; 守卫：如果x <= 0，退出追踪
    t1 = a[i]              ; 沿着实际路径展开
    t2 = b[i]
    y = t1 + t2
    i += 1
    guard(i < n)          ; 循环条件守卫
    jump loop_start
```

**优点**：
- 自然地捕获跨方法边界的热点路径
- 线性代码序列易于优化
- 可以有效地进行寄存器分配

**缺点**：
- 追踪爆炸问题（见10.4节）
- 分支频繁变化时效果差
- 实现复杂度高

**典型代表**：LuaJIT, TraceMonkey（Firefox的早期JS引擎）

#### 区域级JIT（Region-Based JIT）

方法级和追踪级JIT之间的折中方案。编译单元是一个"区域"——一个包含多个基本块的控制流图子图。

**区域的构建**：

区域通常通过以下方式构建：
1. 从一个热基本块开始
2. 向前扩展：如果后继块也是热的，将其加入区域
3. 向后扩展：如果前驱块也是热的，将其加入区域
4. 限制区域大小，避免包含过多冷代码

```
; 区域示例
BB1 (热) → BB2 (热) → BB3 (冷)
                ↓
            BB4 (热) → BB5 (热)

; 区域 = {BB1, BB2, BB4, BB5}（排除冷块BB3）
; BB3的入口和出口作为守卫
```

**优点**：
- 比方法级JIT更精确地包含热代码
- 比追踪级JIT更好地处理分支
- 编译单元比追踪更大，可以进行更多优化

**典型代表**：V8 TurboFan, GCC的JIT模式

### 去优化（Deoptimization）

#### 为什么需要去优化

JIT编译器的许多优化是基于**投机假设**（speculative assumptions）的。当这些假设在运行时被违反时，必须能够回退到安全的执行模式——这就是去优化。

**典型的投机假设**：

1. **类型假设**："这个变量总是整数"
2. **形状假设**："这个对象总是有相同的属性布局"
3. **调用目标假设**："这个虚调用总是指向同一个方法"
4. **分支假设**："这个分支总是走true路径"

```
; 假设 x 总是整数
; JIT生成的特化代码：
mov eax, [x]
add eax, 10      ; 整数加法，非常快
mov [result], eax

; 如果 x 变成了字符串，上述代码会出错！
; 需要去优化：
; 1. 检测到类型假设被违反
; 2. 重建解释器的执行状态（栈帧、局部变量等）
; 3. 从JIT代码跳回解释器继续执行
```

#### 去优化的实现

去优化的核心挑战是：如何从JIT编译的机器码状态，恢复到解释器可以继续执行的状态？

**栈上替换（On-Stack Replacement, OSR）的逆过程**

去优化需要：
1. **保存机器码的当前状态**：寄存器值、程序计数器
2. **映射到解释器状态**：将机器码状态转换为解释器的栈帧格式
3. **重建解释器栈帧**：在栈上创建解释器可以理解的栈帧
4. **跳转到解释器**：从机器码跳转到解释器的相应位置继续执行

**实现方法**：

方法一：影子栈（Shadow Stack）

在JIT代码执行时，同时维护一个与解释器兼容的"影子栈"。去优化时，直接使用影子栈恢复解释器状态。

```
; JIT代码中的影子栈维护
push_interpreter_frame()      ; 在执行JIT代码前保存解释器帧
mov eax, [x]                  ; JIT代码
add eax, 10
; 如果需要去优化：
pop_interpreter_frame()       ; 恢复解释器帧
jump to_interpreter           ; 跳回解释器
```

方法二：去优化表（Deoptimization Table）

在JIT编译时，为每个可能的去优化点生成一个"去优化描述符"，记录：
- 机器码位置
- 对应的字节码位置
- 机器码寄存器到解释器变量的映射
- 需要重建的栈帧信息

```
; 去优化表条目示例
deopt_entry:
    machine_pc: 0x7FFA1234
    bytecode_pc: offset 42
    register_map:
        rax → local_var_0  (integer)
        rbx → local_var_1  (object)
    stack_frame_size: 32
```

**去优化的性能影响**

去优化本身是昂贵的（需要重建状态），但它只在假设被违反时发生。良好的JIT编译器会：
1. 通过profiling确保假设在大多数情况下成立
2. 对频繁去优化的代码降低优化级别或停止投机优化
3. 使用"去优化计数器"来避免在反复去优化的代码上浪费编译资源

---

## 10.3 方法级JIT（以JVM为例）

### HotSpot JVM的架构

JVM HotSpot是方法级JIT编译器的经典代表。它由Sun Microsystems（后来被Oracle收购）开发，至今仍是Java生态系统中最主要的JVM实现。

```
┌─────────────────────────────────────────────────────┐
│                    Java 源代码                        │
└──────────────────────┬──────────────────────────────┘
                       │ javac
                       ▼
┌─────────────────────────────────────────────────────┐
│                    Java 字节码                        │
│                  (.class 文件)                        │
└──────────────────────┬──────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────┐
│              HotSpot JVM 运行时                       │
│  ┌───────────────────────────────────────────────┐  │
│  │           解释器（Interpreter）                 │  │
│  │    模板解释器 / C++解释器                       │  │
│  └───────────────────────┬───────────────────────┘  │
│                          │ 热点检测                   │
│                          ▼                           │
│  ┌──────────────┐  ┌──────────────┐                 │
│  │  C1 编译器    │  │  C2 编译器    │                 │
│  │ (客户端)     │  │ (服务端)     │                  │
│  │  快速编译     │  │  深度优化     │                  │
│  │  少量优化     │  │  高质量代码   │                  │
│  └──────────────┘  └──────────────┘                 │
│  ┌───────────────────────────────────────────────┐  │
│  │        分层编译策略（Tiered Compilation）        │  │
│  └───────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

#### C1编译器（客户端编译器）

C1编译器的设计目标是**快速编译**和**低内存占用**，适合客户端应用程序（如桌面GUI程序）。

C1的优化Pass相对简单：
1. **平台无关的字节码构建**：将字节码转换为HIR（High-level Intermediate Representation）
2. **局部优化**：常量折叠、死代码消除、公共子表达式消除（局部范围内）
3. **平台相关的代码生成**：将HIR转换为LIR（Low-level IR），再生成机器码
4. **寄存器分配**：使用线性扫描（Linear Scan）算法，速度快

C1编译的代码质量不如C2，但编译速度快（通常在毫秒级），适合需要快速启动的场景。

#### C2编译器（服务端编译器）

C2编译器的设计目标是**生成高质量的机器码**，适合长时间运行的服务端应用程序。

C2的优化Pass非常丰富：
1. **Sea-of-Nodes IR**：使用一种独特的"节点海"中间表示，数据流和控制流统一表示
2. **全局值编号（Global Value Numbering）**：在整个方法范围内消除冗余计算
3. **循环优化**：循环展开、循环不变量外提、循环剥离
4. **逃逸分析**：判断对象是否逃逸当前方法，可能实现栈上分配或标量替换
5. **寄存器分配**：使用图着色（Graph Coloring）算法，分配质量高
6. **指令调度**：重排指令以利用CPU流水线

C2编译的代码质量很高，但编译时间较长（可能在秒级）。

#### 分层编译策略（Tiered Compilation）

现代JVM默认使用分层编译，结合C1和C2的优势：

```
层级    编译器      描述                           触发条件
────────────────────────────────────────────────────────────
 0      解释器      纯解释执行，收集profiling数据    方法首次调用
 1      C1 (简单)   C1编译，不收集profiling数据      方法调用计数 > 阈值1
 2      C1 (受限)   C1编译，收集profiling数据        方法调用计数 > 阈值2
 3      C1 (完整)   C1编译，完整profiling数据        方法调用计数 > 阈值3
 4      C2          C2编译，使用profiling数据优化     收集足够的profiling数据
```

分层编译的工作流程：

```
方法首次调用
    │
    ▼
  层级0：解释执行，收集类型profile、分支profile
    │ 调用计数达到阈值
    ▼
  层级3：C1编译（快速编译，同时继续收集profile）
    │ 收集到足够的profile数据
    ▼
  层级4：C2编译（使用profile进行深度优化）
    │
    ▼
  直接执行C2编译的高质量机器码
```

这种策略的好处：
- **快速启动**：C1编译速度快，程序很快能从解释执行过渡到编译执行
- **峰值性能**：C2编译器利用profiling数据进行深度优化，生成高质量代码
- **渐进式优化**：不需要等待C2编译完成才能执行编译代码

### JVM的内联缓存（Inline Cache）

内联缓存是JVM优化虚方法调用的核心技术。

**问题**：Java中的虚方法调用（invokevirtual）需要在运行时查找目标方法。对于频繁调用的虚方法，这个查找开销是不可接受的。

**解决方案**：在调用点缓存上次调用的实际目标方法。

```java
// Java代码
void process(Shape shape) {
    shape.draw();  // 虚方法调用
}
```

```
; 无内联缓存的调用（每次都需要查找）
invoke_virtual:
    load vtable from object      ; 加载虚方法表
    look up method at slot #5    ; 查找方法
    call method                  ; 调用

; 有内联缓存的调用（如果类型匹配，直接调用）
invoke_virtual_cached:
    load class from object       ; 加载对象类型
    cmp class, cached_class      ; 与缓存的类型比较
    jne miss                     ; 不匹配，跳转到miss处理
    call cached_method           ; 匹配，直接调用缓存的方法
    jmp done
miss:
    ; 慢路径：查找方法，更新缓存
    look up method in vtable
    update cache
    call method
done:
```

**JVM的内联缓存层级**：

- **单态（Monomorphic）**：缓存一个类型。如果只有一个类型经过，命中率接近100%
- **多态（Polymorphic）**：缓存2-4个类型。使用if-else链检查
- **超态（Megamorphic）**：超过阈值后，放弃内联缓存，使用完整的虚方法表查找

### JVM的逃逸分析（Escape Analysis）

逃逸分析判断一个对象是否"逃逸"出当前方法的范围。如果没有逃逸，可以进行激进的优化。

**逃逸的判断**：

```java
// 情况1：对象逃逸（escape）——被传递给外部
Object escape() {
    Object obj = new Object();
    someExternalMethod(obj);  // obj逃逸了
    return obj;               // obj逃逸了
}

// 情况2：对象不逃逸（no escape）——只在当前方法内使用
int noEscape() {
    Point p = new Point(1, 2);  // p不逃逸
    return p.x + p.y;           // 只在当前方法内使用
}
```

**逃逸分析的优化**：

1. **栈上分配（Stack Allocation）**：如果对象不逃逸，可以将对象分配在栈上而非堆上。栈上分配不需要GC回收，方法返回时自动释放。

2. **标量替换（Scalar Replacement）**：更进一步，将对象拆解为其字段（标量），完全消除对象分配。

3. **锁消除（Lock Elision）**：如果对象不逃逸，那么对该对象的同步锁不可能被其他线程竞争，可以安全地消除锁操作。

```java
// 优化前
int calculate() {
    Point p = new Point(3, 4);  // 堆分配
    return p.x * p.x + p.y * p.y;
}

// 逃逸分析后，标量替换：
int calculate() {
    int px = 3;  // 直接使用局部变量
    int py = 4;
    return px * px + py * py;
}
```

### JVM的标量替换（Scalar Replacement）

标量替换是逃逸分析的最激进优化之一。它将对象的字段"展开"为独立的局部变量，完全消除对象的堆分配。

**标量（Scalar）vs 聚合体（Aggregate）**：
- 标量：基本类型值（int, float, 指针等）
- 聚合体：由多个标量组成的复合值（对象、结构体）

```
; 优化前（需要堆分配）
Point p = new Point(3, 4);   // 堆分配：需要初始化对象头、字段
int result = p.x + p.y;       // 需要通过指针访问字段

; 标量替换后（无堆分配）
int p_x = 3;                  // 局部变量，可能在寄存器中
int p_y = 4;
int result = p_x + p_y;       // 直接访问，无指针解引用
```

标量替换的收益：
- 消除了堆内存分配的开销
- 消除了GC的压力
- 字段访问从指针解引用变为寄存器访问
- 后续的优化（常量折叠等）更容易进行

---

## 10.4 追踪级JIT（以LuaJIT为例）

> LuaJIT是由Mike Pall开发的Lua语言JIT编译器，它以极高的性能闻名——即使在今天，LuaJIT生成的代码质量仍然是动态语言JIT编译器中的标杆。

### LuaJIT的JIT编译流程详解

LuaJIT的JIT编译流程可以分为以下几个阶段：

```
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  字节码      │────→│  解释执行     │────→│  热循环检测       │
│  (BC)        │     │  + 计数器     │     │  (Hot Loop)      │
└─────────────┘     └──────────────┘     └────────┬────────┘
                                                   │
                                                   ▼
┌─────────────┐     ┌──────────────┐     ┌─────────────────┐
│  机器码      │←────│  代码生成     │←────│  追踪录制         │
│  (MCode)     │     │  (Code Gen)  │     │  (Recording)     │
└──────┬──────┘     └──────────────┘     └────────┬────────┘
       │                                          │
       │          ┌──────────────┐                │
       └─────────→│  追踪链接     │←───────────────┘
                  │  (Linking)   │     ┌─────────────────┐
                  └──────────────┘     │  追踪优化         │
                                       │  (Optimization)  │
                                       └─────────────────┘
```

#### 第1步：字节码解释执行

LuaJIT首先将Lua源代码编译为字节码，然后使用一个高度优化的汇编解释器来执行字节码。

LuaJIT的字节码是为JIT编译而设计的，与传统Lua字节码有一些重要区别：
- 使用64位指令格式，便于JIT处理
- 字节码设计考虑了追踪录制的需要
- 某些操作被拆分为更细粒度的指令

```lua
-- Lua源代码
local sum = 0
for i = 1, 1000000 do
    sum = sum + i
end
print(sum)
```

```
; 对应的LuaJIT字节码（简化表示）
KSHORT  0 0          ; sum = 0
KSHORT  1 1          ; i = 1
KSHORT  2 1000000    ; limit = 1000000
FORI    1 -> loop_end ; for循环初始化
loop_start:
ADDVV   0 0 1        ; sum = sum + i
FORL    1 -> loop_start ; 循环回边
loop_end:
GGET    1 "print"    ; 获取全局print
CALL    1 0 1        ; 调用print(sum)
RET     0 1          ; 返回
```

#### 第2步：热循环检测（Hot Loop Detection）

LuaJIT使用一个简单而有效的热点检测机制：当循环的回边执行次数超过一个阈值（默认为56次，可配置）时，该循环被标记为"热循环"，触发追踪录制。

```
; 解释器中的热循环检测逻辑（伪代码）
FORL_instruction:
    decrement loop counter
    if counter >= 0:
        jump back to loop start      ; 正常循环
    else:
        counter reached threshold:
            trigger_trace_recording()  ; 触发追踪录制！
        fall through to loop end
```

注意LuaJIT只检测**热循环**，而不检测热函数。这意味着：
- 不在循环中的代码不会被JIT编译
- 程序的大部分时间花在循环中，这是合理的策略
- 检测开销非常低（只需要在回边处检查计数器）

#### 第3步：追踪录制（Trace Recording）

当检测到热循环后，LuaJIT开始**追踪录制**：在解释器继续执行循环的同时，记录下实际执行的字节码序列及其类型信息。

**录制过程**：

```
录制开始于循环头
    │
    ▼
解释器执行一条字节码
    │
    ├─→ 记录该字节码对应的IR（中间表示）节点
    │
    ├─→ 如果遇到条件分支：
    │   ├─→ 沿实际执行路径录制
    │   └─→ 在分支处插入"守卫"（Guard）节点
    │       Guard检查条件是否与录制时一致
    │       如果不一致，退出追踪
    │
    ├─→ 如果遇到函数调用：
    │   └─→ 尝试内联该函数
    │
    └─→ 如果回到循环头：
        └─→ 追踪录制完成，开始优化
```

**IR节点示例**：

追踪录制生成的是LuaJIT的IR（Intermediate Representation），这是一种基于SSA（Static Single Assignment）形式的中间表示。

```
; 对应 sum = sum + i 的IR录制
; 假设 sum 和 i 已知为整数类型

0001 >  int ADD     0001  0002    ; sum + i（> 表示这是一个守卫）
0002 >  int LE      0003  0004    ; i <= limit（循环条件守卫）
```

其中 `>` 标记表示这是一个守卫（Guard）——如果条件不满足，追踪将退出到解释器。

**类型传播**：

追踪录制过程中，LuaJIT会追踪每个值的类型。当一个值首次出现时，解释器记录其运行时类型，后续操作基于这个类型生成特化的IR。

```lua
-- 假设在录制过程中观察到：
local x = obj.field   -- obj的类型是已知的，field的类型是number
local y = x + 1       -- 由于x是number，这是一个浮点加法或整数加法
```

#### 第4步：追踪优化

录制完成后，LuaJIT对IR进行一系列优化。这些优化利用了追踪是线性代码序列这一特性，使得许多优化变得特别简单和高效。

##### 快照（Snapshot）

快照是LuaJIT追踪JIT中的一个关键概念。在每个可能退出追踪的位置（守卫处），LuaJIT保存一个"快照"——记录此时解释器状态的完整描述。

快照包含：
- 所有活跃的解释器栈槽（stack slot）的值
- 活跃的upvalue
- 循环计数器等状态

快照的作用：当守卫失败需要退出追踪时，使用快照快速恢复解释器状态，继续在解释器中执行。

```
; 快照示例
Guard(i < n)  ; 循环条件守卫
  Snapshot: {
    stack[0] = sum    ; 当前的sum值
    stack[1] = i      ; 当前的i值
    stack[2] = n      ; 循环上限
    ...
  }
```

##### 折叠（Folding）

折叠是追踪JIT中最强大的优化之一。由于追踪是线性代码序列，LuaJIT可以像编译器一样进行常量折叠和强度削减。

```
; 折叠前
0001:  int CONV   num  KSHORT 3     ; 3.0
0002:  num MUL    0001  0001         ; 3.0 * 3.0
0003:  num ADD    0002  KNUM 1.0     ; 9.0 + 1.0

; 折叠后
0001:  num KSHORT 10                  ; 直接替换为常量 10.0
```

LuaJIT的折叠引擎是一个基于模式匹配的重写系统。它维护一个哈希表，将已计算的表达式映射到其结果。当新的IR节点被创建时，首先检查是否可以折叠。

##### DCE（Dead Code Elimination，死代码消除）

由于追踪沿着单一执行路径录制，某些操作的结果可能从未被使用（例如，被后续操作覆盖）。DCE移除这些无用的计算。

```
; DCE前
0001:  int ADD    a  b       ; c = a + b
0002:  int MUL    x  y       ; d = x * y  （结果d从未被使用）
0003:  int ADD    0001  1    ; e = c + 1

; DCE后
0001:  int ADD    a  b       ; c = a + b
0003:  int ADD    0001  1    ; e = c + 1
; 节点0002被消除
```

##### CSE（Common Subexpression Elimination，公共子表达式消除）

如果同一个表达式在追踪中出现多次，只计算一次，后续使用缓存的结果。

```
; CSE前
0001:  int ADD    a  b       ; x = a + b
0002:  int MUL    0001  c    ; y = x * c
0003:  int ADD    a  b       ; z = a + b （与0001相同）
0004:  int ADD    0003  d    ; w = z + d

; CSE后
0001:  int ADD    a  b       ; x = a + b
0002:  int MUL    0001  c    ; y = x * c
0004:  int ADD    0001  d    ; w = x + d （复用0001的结果）
```

##### 代码生成（Code Generation）

优化完成后，LuaJIT将IR翻译为本地机器码。LuaJIT的代码生成器直接从IR生成机器码，不经过传统的"IR → 汇编 → 机器码"流程。

LuaJIT支持多种目标架构：x86、x64、ARM、ARM64、MIPS、PowerPC等。

#### 第5步：机器码生成

LuaJIT使用DynASM（Dynamic Assembler）来生成机器码。DynASM是一个嵌入在C代码中的汇编宏预处理器，允许在C代码中直接编写汇编指令。

```c
// DynASM使用示例（伪代码）
| mov eax, [rbp-8]      // 加载变量
| add eax, [rbp-16]     // 加法操作
| jo ->overflow_handler  // 溢出检查
```

生成的机器码被放置在LuaJIT管理的代码缓冲区中。

#### 第6步：追踪链接（Trace Linking）

追踪链接是LuaJIT性能的关键。当一个追踪跳转到另一个已编译的追踪时，LuaJIT会将它们直接链接起来，避免返回解释器。

```
; 追踪链接前
Trace A:                    Trace B:
  ...                         ...
  jump to loop start ──→ 解释器 ──→ Trace B的入口

; 追踪链接后
Trace A:                    Trace B:
  ...                         ...
  jump to Trace B入口 ──────────→ Trace B的入口
  （直接跳转，无需经过解释器）
```

链接类型：
- **循环链接**：追踪跳转回自己的入口，形成一个编译后的循环
- **根链接**：一个追踪跳转到另一个追踪的入口
- **缝合链接（Stitch Link）**：从一个追踪退出到另一个追踪（通过快照匹配）

### Side Trace（侧追踪）

当追踪录制过程中遇到条件分支时，LuaJIT不会停止录制——它沿着实际执行的路径继续录制，在分支处插入一个守卫（Guard）。如果守卫失败，程序退出到解释器。

但如果这个守卫频繁失败（即另一条路径也很热），LuaJIT会从守卫失败的点开始录制一条新的追踪，称为**侧追踪（Side Trace）**。

```
; 主追踪（假设 x > 0 总是成立）
Main Trace:
    L0: a = load i          ; 加载 a[i]
    L1: b = load i          ; 加载 b[i]
    L2: guard(x > 0)        ; 守卫：x > 0
    L3: c = a + b           ; 走true分支
    L4: guard(i < n)        ; 循环条件
    L5: jump L0

; 当 x <= 0 时，从L2失败，录制侧追踪
Side Trace:
    S0: c = a - b           ; 走false分支
    S1: guard(i < n)        ; 循环条件
    S2: jump Main Trace L0  ; 链接回主追踪
```

侧追踪可以递归地产生更多侧追踪，形成一棵追踪树。但这也带来了追踪爆炸的风险。

### 追踪爆炸（Trace Explosion）问题

追踪爆炸是指由于程序中有大量的分支路径，导致产生过多的追踪，消耗过多的内存和编译时间。

```
; 示例：追踪爆炸
for i = 1, n do
    if a[i] > 0 then        -- 分支1
        if b[i] > 0 then    -- 分支2
            if c[i] > 0 then -- 分支3
                -- ...
            end
        end
    end
end

; 每个分支组合都可能产生一条追踪：
; 追踪1: a>0, b>0, c>0
; 追踪2: a>0, b>0, c<=0 (侧追踪)
; 追踪3: a>0, b<=0 (侧追踪)
; 追踪4: a<=0 (侧追踪)
; 追踪5: a>0, b>0, c>0, d>0 ... (更多组合)
```

LuaJIT通过以下机制限制追踪爆炸：
1. **最大追踪长度限制**：追踪的IR节点数有上限
2. **最大侧追踪深度**：限制追踪树的深度
3. **黑名单机制**：对反复产生问题的代码段停止JIT编译
4. **最大追踪数量限制**：限制总追踪数量

---

## 10.5 V8引擎的JIT架构

V8是Google开发的高性能JavaScript和WebAssembly引擎，用于Chrome浏览器和Node.js。V8拥有当今最复杂的JIT编译管线之一。

### V8的编译管线

V8采用多层编译管线，从快速解释到深度优化，逐层提升代码质量：

```
┌──────────────┐
│  JavaScript   │
│  源代码        │
└──────┬───────┘
       │ Parser + Preparser
       ▼
┌──────────────┐
│    AST        │
│  (抽象语法树)  │
└──────┬───────┘
       │ BytecodeGenerator
       ▼
┌──────────────────────────────────────────────────────┐
│                 Ignition 解释器                        │
│  • 生成并执行字节码                                     │
│  • 收集类型反馈（Type Feedback）                        │
│  • 记录调用计数                                        │
└──────────────────────┬───────────────────────────────┘
                       │ 调用计数达到阈值
                       ▼
┌──────────────────────────────────────────────────────┐
│              Sparkplug 基线编译器                       │
│  • 快速将字节码编译为机器码（无优化）                     │
│  • 编译速度极快（直接遍历字节码）                        │
│  • 代码质量中等（消除了解释器开销）                      │
└──────────────────────┬───────────────────────────────┘
                       │ 更多执行数据 + 更高热度
                       ▼
┌──────────────────────────────────────────────────────┐
│              Maglev 中层编译器                          │
│  • 在Sparkplug代码基础上进行优化                        │
│  • 利用类型反馈进行特化                                 │
│  • 编译速度和代码质量的折中                              │
└──────────────────────┬───────────────────────────────┘
                       │ 长时间运行的热点代码
                       ▼
┌──────────────────────────────────────────────────────┐
│              TurboFan 优化编译器                        │
│  • 深度优化，生成高质量机器码                            │
│  • 投机优化 + 去优化                                    │
│  • 逃逸分析、标量替换、内联等                            │
└──────────────────────────────────────────────────────┘
```

#### Ignition解释器

Ignition是V8的字节码解释器，于2016年取代了之前的Full-codegen基线编译器。

**字节码格式**：
V8的字节码使用寄存器式（register-based）格式，每个字节码指令可以操作累加器（accumulator）和寄存器。

```javascript
// JavaScript源代码
function add(a, b) {
    return a + b;
}
```

```
; Ignition字节码
LdaNamedProperty a0, [0]    // 加载参数a
Star r0                      // 保存到寄存器r0
LdaNamedProperty a0, [1]    // 加载参数b
Add r0                       // 累加器 = r0 + 累加器
Return                       // 返回累加器
```

**类型反馈收集**：

Ignition在执行过程中收集类型反馈信息，存储在反馈向量（Feedback Vector）中：

```javascript
function process(x) {
    return x + 1;
}
// 多次调用后，反馈向量记录：
// x 的类型：90% SMI（小整数），10% HeapNumber（浮点数）
// + 操作：主要执行整数加法
```

#### Sparkplug基线编译器

Sparkplug（2021年引入）是一个极快的基线编译器，它直接将Ignition的字节码翻译为机器码，几乎不做任何优化。

**设计理念**：
- 编译速度极快（比TurboFan快约10倍）
- 消除解释器的分派开销
- 不做投机优化（因此不需要去优化）
- 代码质量比解释器好，但不如优化编译器

Sparkplug的工作方式本质上是一个"模板编译器"：每条字节码对应一个预编译的机器码模板，编译过程就是将这些模板拼接起来。

#### Maglev中层编译器

Maglev（2023年引入）是V8在Sparkplug和TurboFan之间插入的中层编译器。

**设计理念**：
- 在Sparkplug的基础上，利用类型反馈进行有限的优化
- 编译速度比TurboFan快约5-10倍
- 代码质量介于Sparkplug和TurboFan之间
- 对于大多数JavaScript代码，Maglev的代码质量已经足够好

Maglev使用SSA形式的IR，但优化Pass比TurboFan简单得多。它主要进行：
- 基于类型反馈的特化
- 简单的内联
- 简单的常量折叠
- 简单的死代码消除

#### TurboFan优化编译器

TurboFan是V8的深度优化编译器，于2015年开始逐步取代Crankshaft编译器。

**TurboFan的IR**：

TurboFan使用"海洋节点"（Sea of Nodes）IR，类似于JVM C2编译器的设计：
- 每个操作是一个节点
- 数据流通过值边（value edges）连接
- 控制流通过控制边（control edges）连接
- 数据流和控制流独立，允许更多的优化机会

```
; TurboFan IR示例（简化）
; function add(a, b) { return a + b; }

[Parameter 0] ──→ [CheckSmi] ──→ ┐
                                  ├──→ [Int32Add] ──→ [Return]
[Parameter 1] ──→ [CheckSmi] ──→ ┘

; CheckSmi: 检查参数是否为小整数（投机假设）
; 如果不是SMI，触发去优化
```

**TurboFan的优化Pass**：

1. **图构建**：从字节码构建初始的节点图
2. **类型推断**：基于反馈向量中的类型信息，推断每个节点的类型
3. **投机简化**：基于类型假设进行简化（如消除类型检查）
4. **内联**：将小函数内联到调用者
5. **逃逸分析**：分析对象是否逃逸
6. **循环优化**：循环不变量外提、循环展开
7. **寄存器分配**：使用线性扫描算法
8. **代码生成**：生成目标机器码

### 隐藏类（Hidden Classes/Maps）

JavaScript是一种基于原型的动态语言，对象的属性可以在运行时任意添加、删除。这使得属性访问在理论上需要哈希表查找，性能很差。

V8通过**隐藏类**（V8内部称为Map）来优化属性访问：

```javascript
// JavaScript
let obj1 = {};      // 创建隐藏类 Map0（空对象）
obj1.x = 1;         // 创建隐藏类 Map1（有属性x，偏移量0）
obj1.y = 2;         // 创建隐藏类 Map2（有属性x、y，偏移量0、1）

let obj2 = {};      // 使用 Map0
obj2.x = 10;        // 使用 Map1
obj2.y = 20;        // 使用 Map2
// obj1 和 obj2 共享相同的隐藏类！
```

```
; 隐藏类的结构
Map0 (空对象):
  {}

Map1 (有属性x):
  x: offset 0

Map2 (有属性x, y):
  x: offset 0
  y: offset 1

; 属性转换链
Map0 ──(添加x)──→ Map1 ──(添加y)──→ Map2
```

**隐藏类的作用**：
- 将属性名映射到固定的内存偏移量
- 属性访问从哈希表查找变为直接内存偏移
- 多个具有相同属性添加顺序的对象共享隐藏类

```javascript
// 属性访问优化
obj.x
// 无隐藏类：hash_table_lookup(obj, "x")  -- O(1)但开销大
// 有隐藏类：memory_load(obj, offset_of_x) -- 直接偏移访问
```

### 内联缓存（Inline Caching）

V8在每个属性访问点（如`obj.x`）维护一个内联缓存，记录上次访问的对象的隐藏类和属性偏移量。

#### 单态、多态、超态

**单态（Monomorphic）**：访问点只见过一种隐藏类。性能最好。

```javascript
function getX(obj) {
    return obj.x;
}

// 如果总是传入相同形状的对象：
getX({x: 1, y: 2});  // Map: {x:offset0, y:offset1}
getX({x: 3, y: 4});  // 同样的Map
// 单态缓存：直接检查Map，然后读取offset0
```

**多态（Polymorphic）**：访问点见过2-4种隐藏类。使用线性搜索。

```javascript
function getX(obj) {
    return obj.x;
}

// 如果传入不同形状的对象：
getX({x: 1, y: 2});          // Map1
getX({x: 1});                 // Map2
getX({x: 1, y: 2, z: 3});    // Map3
// 多态缓存：依次检查Map1、Map2、Map3
```

**超态（Megamorphic）**：访问点见过太多隐藏类（通常>4种）。缓存退化为字典查找。

```javascript
function getX(obj) {
    return obj.x;
}

// 如果传入大量不同形状的对象：
for (let i = 0; i < 100; i++) {
    getX(createRandomObject(i));
}
// 超态缓存：退化为通用的字典查找
// 性能显著下降
```

**性能影响**：

| 缓存状态 | 属性访问开销 | 典型延迟 |
|----------|------------|---------|
| 单态 | Map检查 + 直接偏移 | ~1ns |
| 多态 | 线性搜索 + 直接偏移 | ~3-5ns |
| 超态 | 哈希表查找 | ~10-20ns |

### 逃逸分析和标量替换

V8的TurboFan编译器也实现了逃逸分析和标量替换：

```javascript
function calculate() {
    let point = {x: 3, y: 4};  // 对象创建
    return point.x * point.x + point.y * point.y;
}

// 逃逸分析：point没有逃逸出calculate函数
// 标量替换后（概念上）：
function calculate_optimized() {
    let px = 3;  // 标量
    let py = 4;
    return px * px + py * py;
}
```

V8的逃逸分析还可以进行**锁消除**（对于SharedArrayBuffer相关的操作）和**分配消除**。

### V8的去优化机制

V8的去优化是通过**去优化数据（Deoptimization Data）**实现的。每个优化编译的函数都包含一组去优化入口点。

```javascript
function add(a, b) {
    return a + b;
}
// TurboFan假设 a 和 b 都是SMI（小整数）
// 生成的机器码直接执行整数加法

// 如果某次调用传入了浮点数：
add(3.14, 2.71)
// 触发去优化：
// 1. 找到最近的去优化入口点
// 2. 使用保存的寄存器映射重建解释器状态
// 3. 跳转到Ignition字节码继续执行
```

**去优化的类型**：

- **Eager Deoptimization**（急切去优化）：在编译时就确定某些假设可能被违反，在假设处立即去优化
- **Lazy Deoptimization**（惰性去优化）：在函数调用边界处去优化，允许当前函数先执行完

---

## 10.6 JIT编译中的优化技术

### 类型特化（Type Specialization）

类型特化是JIT编译器最核心的优化技术。动态语言中的变量可以是任意类型，但在实际运行中，大多数变量在大多数时间里都是同一种类型。

**原理**：

```
; 通用代码（处理所有类型）
function add(a, b):
    if is_number(a) and is_number(b):
        return a + b              ; 数值加法
    elif is_string(a) and is_string(b):
        return concat(a, b)       ; 字符串连接
    elif is_number(a) and is_string(b):
        return concat(to_string(a), b)
    ; ... 更多类型组合
    else:
        throw TypeError()

; 特化后的代码（假设a和b总是整数）
function add_specialized(a, b):
    guard(is_number(a))           ; 类型守卫
    guard(is_number(b))           ; 类型守卫
    return integer_add(a, b)      ; 直接的整数加法，无类型检查
```

**Guards和类型检查**：

守卫（Guard）是JIT编译器在投机优化中使用的运行时类型检查。守卫有两种状态：
- **通过**：类型符合假设，继续执行优化后的快速路径
- **失败**：类型违反假设，触发去优化，回退到解释器

```
; 守卫的实现（概念上）
guard(condition):
    if not condition:
        save current state to snapshot
        jump to deoptimization handler
    ; 条件满足，继续执行
```

守卫的开销通常很低——大多数守卫只需要一条比较指令和一个条件跳转。关键是确保守卫在绝大多数情况下都能通过。

### 内联缓存（Inline Caching）

（已在10.5节详细讨论，此处补充一些实现细节）

**内联缓存的状态机**：

```
                    首次访问
Uninitialized ──────────→ Monomorphic (1个类型)
                              │
                              │ 遇到第2种类型
                              ▼
                         Polymorphic (2-4个类型)
                              │
                              │ 遇到第5种类型
                              ▼
                         Megamorphic (字典查找)
```

**内联缓存与JIT编译的协同**：

当JIT编译器编译一个包含属性访问的方法时：
1. 读取该访问点的内联缓存状态
2. 如果是单态缓存：生成直接的偏移访问 + 类型检查守卫
3. 如果是多态缓存：生成一个类型检查链 + 对应的偏移访问
4. 如果是超态缓存：生成通用的字典查找代码

### 逃逸分析

（已在10.3节详细讨论，此处补充跨方法分析）

**跨方法逃逸分析的挑战**：

```java
Object create() {
    Point p = new Point(1, 2);
    return p;  // p逃逸出create方法
}

void use() {
    Point p = create();  // p从create逃逸到use
    System.out.println(p.x);
}
```

跨方法逃逸分析需要分析调用图，判断对象是否逃逸出整个调用链。这在实践中非常复杂，因此大多数JIT编译器只进行方法级的逃逸分析。

**部分逃逸分析**：

有些对象可能在部分执行路径上逃逸，在另一部分路径上不逃逸。部分逃逸分析尝试在这种情况下仍然进行优化：

```java
int calculate(boolean flag) {
    Point p = new Point(1, 2);
    if (flag) {
        globalPoint = p;  // 逃逸！
    }
    return p.x + p.y;     // 不逃逸的使用
}
```

### On-Stack Replacement（OSR）

OSR允许在循环执行过程中，将正在运行的解释器代码替换为JIT编译的机器码。

**为什么需要OSR**：

考虑一个长时间运行的循环：

```javascript
// 这个循环可能运行数百万次
for (let i = 0; i < 10000000; i++) {
    // 复杂的计算
    process(data[i]);
}
```

如果没有OSR，循环必须等到下一次方法调用时才能使用JIT编译的代码。对于长时间运行的循环，这意味着大量的时间浪费在解释执行上。

**OSR的工作原理**：

```
1. 解释器正在执行循环的第N次迭代
2. 回边计数器达到阈值
3. JIT编译器编译该方法（包含循环）
4. OSR机制：
   a. 保存解释器当前的栈帧状态
   b. 将解释器状态映射到JIT代码的入口点
   c. 将栈帧替换为JIT代码的栈帧
   d. 跳转到JIT代码中循环的相应位置继续执行
```

```
; OSR前
解释器执行循环：
  iteration 1  (解释)
  iteration 2  (解释)
  ...
  iteration 10000 (解释) ← 回边计数器达到阈值
  ─── OSR ───
  iteration 10001 (JIT编译的机器码)
  iteration 10002 (JIT编译的机器码)
  ...
```

**OSR的挑战**：

OSR需要在任意循环迭代处将解释器状态映射到JIT代码状态，这比普通的JIT编译更复杂：
- 需要为循环头的OSR入口生成特殊的代码
- 需要处理循环变量在不同迭代中的值
- 需要正确映射所有活跃的局部变量

### Speculative Optimization（投机优化）

投机优化是JIT编译器的核心策略：基于运行时观察到的模式进行假设性优化，并在假设失败时通过去优化回退。

**投机优化的典型场景**：

1. **类型投机**：
```
; 观察：x 总是整数
; 假设：x 永远是整数
; 优化：生成整数加法代码
; 守卫：如果x不是整数，去优化
```

2. **分支概率投机**：
```
; 观察：if分支执行了999次，else分支执行了1次
; 假设：if分支总是执行
; 优化：将if分支作为主路径，else分支作为慢路径
```

3. **调用目标投机**：
```
; 观察：虚调用总是指向同一个实现
; 假设：虚调用总是指向同一个实现
; 优化：将虚调用替换为直接调用（甚至内联）
; 守卫：如果调用目标改变，去优化
```

**投机优化的风险管理**：

- **Profile质量**：需要收集足够的profile数据才能做出可靠的假设
- **去优化成本**：假设失败时的去优化是有成本的，过于激进的投机可能导致频繁去优化
- **编译成本**：投机优化生成的代码如果频繁去优化，浪费了编译资源

良好的JIT编译器会使用各种启发式方法来平衡投机的收益和风险。

---

## 10.7 JIT编译的内存管理

### 代码缓存（Code Cache）

JIT编译的机器码需要存储在内存中，以便后续直接执行。代码缓存管理这些编译后的代码。

**代码缓存的组织**：

```
┌─────────────────────────────────────────┐
│              Code Cache                  │
│  ┌─────────────┐  ┌─────────────┐      │
│  │ 方法A的机器码 │  │ 方法B的机器码 │      │
│  │ (C1编译)     │  │ (C2编译)     │      │
│  └─────────────┘  └─────────────┘      │
│  ┌─────────────┐  ┌─────────────┐      │
│  │ 追踪X的机器码 │  │ 追踪Y的机器码 │      │
│  │ (LuaJIT)     │  │ (LuaJIT)     │      │
│  └─────────────┘  └─────────────┘      │
│  ┌─────────────────────────────────┐   │
│  │        元数据（去优化表等）        │   │
│  └─────────────────────────────────┘   │
└─────────────────────────────────────────┘
```

**代码缓存的大小限制**：

- JVM HotSpot：`-XX:ReservedCodeCacheSize`（默认240MB）
- V8：`--max-old-space-size`间接限制
- LuaJIT：默认64MB（可配置）

**代码缓存满时的策略**：

1. **丢弃最旧的编译代码**：将已编译的方法恢复为解释执行
2. **丢弃最冷的编译代码**：使用profiling数据判断哪些编译代码最少执行
3. **触发GC**：清理不再需要的编译代码

### 编译队列和编译线程

现代JIT编译器通常在后台线程中进行编译，避免阻塞主线程的执行。

```
主线程：
  执行代码 → 检测到热点 → 提交编译请求 → 继续解释执行
                                              │
编译线程：                                      │
  等待编译请求 ← 收到请求 → 编译 → 编译完成 ────┘
                                      │
主线程：                              │
  检查编译是否完成 → 是 → 切换到编译后的代码
```

**编译队列的设计**：

- **优先级**：方法级编译通常比追踪级编译有更高的优先级
- **去重**：同一个方法不应该被重复编译
- **取消**：如果程序已经退出了热点区域，可以取消正在排队的编译请求

### 内存压力和GC的交互

JIT编译与垃圾回收（GC）之间存在复杂的交互：

1. **编译器对象的生命周期**：JIT编译器本身需要分配内存（IR节点、中间数据结构等），这些临时对象需要被GC管理
2. **编译代码中的GC根**：编译后的代码可能引用GC管理的对象，需要正确注册为GC根
3. **去优化与GC**：去优化重建解释器栈帧时，需要正确更新GC的引用图
4. **代码缓存压力**：代码缓存占用了本可用于应用程序堆的内存

**V8的解决方案**：

V8将代码和数据分开存储在不同的堆空间中：
- **代码空间（Code Space）**：存储编译后的机器码
- **老生代空间（Old Space）**：存储长生命周期的对象
- **新生代空间（New Space）**：存储新创建的对象

---

## 10.8 示例代码

本章提供以下示例代码，帮助理解JIT编译的核心概念：

### 文件列表

| 文件 | 描述 | 核心概念 |
|------|------|---------|
| `jit_compiler.py` | 简化的JIT编译器演示 | 热点检测、字节码→机器码编译、性能对比 |
| `trace_jit.py` | 追踪JIT编译演示 | 追踪录制、追踪优化、追踪执行 |
| `inline_cache_demo.py` | 内联缓存演示 | 单态/多态/超态缓存、隐藏类 |
| `benchmark.py` | JIT编译性能基准测试 | 解释器 vs JIT性能对比 |

### jit_compiler.py

一个简化的JIT编译器演示。该演示包含：
- 一个简单的字节码虚拟机
- 基于计数器的热点检测
- 将热点函数的字节码编译为x86-64机器码（使用ctypes + mmap分配可执行内存）
- JIT编译前后的性能对比

运行方式：
```bash
python jit_compiler.py
```

### trace_jit.py

追踪JIT编译演示。该演示包含：
- 简单的循环追踪录制机制
- 追踪优化（常量折叠、死代码消除、强度削减）
- 追踪到机器码的编译
- 与纯解释执行的性能对比

运行方式：
```bash
python trace_jit.py
```

### inline_cache_demo.py

内联缓存和隐藏类的概念演示。该演示包含：
- 隐藏类（Map）的实现
- 单态、多态、超态缓存的行为
- 属性访问的性能对比
- 详细的统计信息

运行方式：
```bash
python inline_cache_demo.py
```

### benchmark.py

JIT编译前后的性能对比基准测试。该演示包含：
- 多种基准测试场景
- 解释器 vs JIT编译器的性能对比
- 详细的性能统计和分析

运行方式：
```bash
python benchmark.py
```

---

## 延伸阅读

### 经典论文

1. **"The Implementation of Lua 5.0"** - Roberto Ierusalimschy et al.
   Lua的实现细节，包括字节码设计

2. **"Trace-based Just-in-Time Type Specialization for Dynamic Languages"** - Andreas Gal et al.
   Mozilla的TraceMonkey论文，系统地介绍了追踪JIT

3. **"Allocation Removal in the Java HotSpot Client Compiler"** - Thomas Kotzmann et al.
   JVM HotSpot逃逸分析和标量替换的实现

4. **"Fast Dispatch for Dynamic Languages"** - Various
   内联缓存和方法分派的优化技术

### 推荐资源

- **LuaJIT源代码**：https://github.com/LuaJIT/LuaJIT
  Mike Pall的代码是学习JIT编译的最佳教材之一

- **V8博客**：https://v8.dev/blog
  V8团队定期发布关于新优化技术的博客文章

- **HotSpot Internals**：https://openjdk.org/groups/hotspot/
  OpenJDK HotSpot的内部文档

- **"Engineering a Compiler"** - Cooper & Torczon
  编译器工程教科书，包含JIT编译的章节

---

## 本章小结

本章深入探讨了JIT编译技术的核心原理和实践。关键要点：

1. **JIT编译是解释执行和静态编译的折中**：它在运行时将热点代码编译为机器码，结合了灵活性和高性能。

2. **热点检测是JIT的基础**：计数器方法和采样方法各有优缺点，现代JIT编译器通常使用计数器方法。

3. **编译粒度决定了优化的空间**：方法级JIT（JVM）、追踪级JIT（LuaJIT）、区域级JIT（V8 TurboFan）各有特色。

4. **投机优化是JIT超越AOT的关键**：基于运行时类型信息的特化、内联缓存、逃逸分析等技术，使JIT编译器能够做出静态编译器无法做出的优化决策。

5. **去优化是投机优化的安全网**：当投机假设失败时，去优化机制确保程序可以安全地回退到解释执行。

6. **现代JIT编译器采用多层编译策略**：从快速的基线编译器到深度优化的编译器，逐层提升代码质量。

7. **JIT编译的挑战**：内存管理、编译延迟、去优化开销、与GC的交互等问题，需要精心设计来解决。

下一章，我们将探讨垃圾回收（Garbage Collection）——与JIT编译密切相关的运行时技术。
