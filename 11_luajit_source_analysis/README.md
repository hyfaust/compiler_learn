# 11. LuaJIT 源代码深度分析

> 本文档基于 LuaJIT 2.1 源代码的实际阅读和分析编写。LuaJIT 是一个教学价值极高的项目——它将解释器、编译器、虚拟机、垃圾回收、JIT编译等几乎所有系统编程核心技术融合在约 3 万行精炼的 C 代码中。

---

## 11.1 LuaJIT 项目概述

### 11.1.1 LuaJIT 是什么

LuaJIT 是 Lua 编程语言的高性能实现，由 **Mike Pall** 于 2005 年开始开发。它包含一个基于寄存器的解释器和一个追踪式即时编译器（Tracing JIT Compiler），能够在运行时将热点代码编译为高效的本机机器码。

LuaJIT 兼容 Lua 5.1 语言规范，并在此基础上扩展了以下特性：

- **FFI（Foreign Function Interface）**：允许直接在 Lua 中调用 C 函数和访问 C 数据结构，无需编写绑定代码
- **JIT 编译**：自动将热点循环和函数编译为本机机器码
- **扩展库**：`bit`（位操作）、`jit`（JIT控制）、`ffi`（C FFI）、`buffer`（字符串缓冲区）等

### 11.1.2 作者与许可证

```
LuaJIT -- a Just-In-Time Compiler for Lua. https://luajit.org/
Copyright (C) 2005-2026 Mike Pall. All rights reserved.
MIT License
```

LuaJIT 包含来自 Lua 5.1/5.2 的代码（Lua.org, PUC-Rio）和来自 dlmalloc 的内存分配器代码（Doug Lea，公共领域）。

### 11.1.3 LuaJIT 的核心特点

| 特点 | 说明 |
|------|------|
| **追踪式 JIT** | 基于热循环检测的 trace 编译，而非方法级编译 |
| **NaN Tagging** | 利用 IEEE 754 双精度浮点数的 NaN 载荷位来存储类型标签和值 |
| **SSA IR** | JIT 编译使用严格的 SSA（静态单赋值）中间表示 |
| **FFI** | 零开销的 C 互操作，直接在 JIT 编译的代码中内联 C 调用 |
| **增量 GC** | 三色标记-清除增量垃圾回收器 |
| **DynASM** | 内嵌的动态汇编器，用于生成多平台机器码 |
| **极小代码体** | 核心源代码约 3 万行 C，加上 DynASM 模板 |

### 11.1.4 版本历史

- **LuaJIT 1.x**（2005）：基于 Lua 5.0，仅包含解释器优化
- **LuaJIT 2.0**（2008-2012）：完全重写，引入追踪 JIT 编译器、SSA IR、FFI
- **LuaJIT 2.1**（2012-至今）：持续改进，增加 GC64 模式、ARM64 支持、各种优化 pass、buffer 库等。当前仓库版本即为 2.1 的滚动发布版

---

## 11.2 LuaJIT 源代码目录结构

```
luajit/
├── COPYRIGHT              # MIT 许可证
├── Makefile               # 顶层构建文件
├── README                 # 项目说明
├── .relver                # 版本信息（git commit timestamp）
├── doc/                   # HTML 文档
│   ├── luajit.html        # 主文档入口
│   ├── ext_ffi.html       # FFI 扩展文档
│   ├── ext_jit.html       # JIT 库文档
│   └── ...                # 其他文档页面
├── dynasm/                # DynASM 动态汇编器
│   ├── dynasm.lua         # DynASM 核心（Lua 实现）
│   ├── dasm_x86.h/lua     # x86 后端
│   ├── dasm_x64.lua       # x64 后端
│   ├── dasm_arm.h/lua     # ARM 后端
│   ├── dasm_arm64.h/lua   # ARM64 后端
│   ├── dasm_mips.h/lua    # MIPS 后端
│   ├── dasm_ppc.h/lua     # PowerPC 后端
│   └── dasm_proto.h       # DynASM 协议定义
├── etc/                   # 辅助文件
│   ├── luajit.1           # man page
│   └── luajit.pc          # pkg-config 文件
└── src/                   # ★ 核心源代码（详见下文）
    ├── host/              # 构建工具（buildvm）
    ├── jit/               # Lua 实现的 JIT 辅助模块
    └── *.c, *.h, *.dasc   # 核心 C 源码和 DynASM 模板
```

### `src/host/` — 构建工具

`host/` 目录包含 **buildvm** 的源代码，这是 LuaJIT 构建过程中使用的代码生成工具：

| 文件 | 作用 |
|------|------|
| `buildvm.c/h` | buildvm 主程序 |
| `buildvm_asm.c` | 生成 VM 汇编代码 |
| `buildvm_fold.c` | 生成 FOLD 优化的哈希表 |
| `buildvm_lib.c` | 生成内置库的字节码 |
| `buildvm_libbc.h` | 内置库字节码头 |
| `buildvm_peobj.c` | 生成 PE/COFF 目标文件（Windows） |
| `minilua.c` | 构建时使用的精简 Lua 解释器（用于运行 DynASM） |
| `genlibbc.lua` | 生成内置库字节码的脚本 |
| `genminilua.lua` | 生成 minilua 的脚本 |
| `genversion.lua` | 生成版本号的脚本 |

### `src/jit/` — JIT 辅助模块（Lua 实现）

| 文件 | 作用 |
|------|------|
| `bc.lua` | 字节码定义和辅助函数 |
| `bcsave.lua` | 字节码保存/反汇编 |
| `dump.lua` | Trace dump 工具 |
| `p.lua` | 精简的 Lua 代码美化打印 |
| `v.lua` | 字节码/IR verbose 输出 |
| `zone.lua` | 内存 zone 分配器 |
| `dis_*.lua` | 各架构的反汇编器（x86、x64、ARM、ARM64、MIPS、PPC） |

---

## 11.3 LuaJIT 核心源代码文件详解

LuaJIT 的 `src/` 目录包含约 190 个文件。以下按功能模块分类详细说明。

### 11.3.1 前端：词法分析、语法分析、字节码生成

#### `lj_lex.c` / `lj_lex.h` — 词法分析器

词法分析器将源代码文本转换为 token 流。定义在 `lj_lex.h` 中的 `LexState` 结构体保存了词法分析器的全部状态：

```c
typedef struct LexState {
  struct FuncState *fs;     /* 当前函数状态 */
  struct lua_State *L;      /* Lua 状态 */
  TValue tokval;            /* 当前 token 的值 */
  const char *p;            /* 输入缓冲区当前位置 */
  const char *pe;           /* 输入缓冲区末尾 */
  LexChar c;                /* 当前字符 */
  LexToken tok;             /* 当前 token */
  LexToken lookahead;       /* 前瞻 token */
  SBuf sb;                  /* token 字符串缓冲区 */
  lua_Reader rfunc;         /* 读取器回调 */
  BCLine linenumber;        /* 行号计数器 */
  GCstr *chunkname;         /* 当前 chunk 名称 */
  VarInfo *vstack;          /* 局部变量信息栈 */
  BCInsLine *bcstack;       /* 字节码/行号栈 */
  uint32_t level;           /* 语法嵌套层级 */
  int fr2;                  /* 是否为 LJ_FR2 模式生成字节码 */
} LexState;
```

Token 定义使用宏 `TKDEF` 同时定义关键字和符号：

```c
#define TKDEF(_, __) \
  _(and) _(break) _(do) _(else) _(elseif) _(end) _(false) \
  _(for) _(function) _(goto) _(if) _(in) _(local) _(nil) _(not) _(or) \
  _(repeat) _(return) _(then) _(true) _(until) _(while) \
  __(concat, ..) __(dots, ...) __(eq, ==) __(ge, >=) __(le, <=) __(ne, ~=) \
  __(label, ::) __(number, <number>) __(name, <name>) __(string, <string>) \
  __(eof, <eof>)
```

核心函数：
- `lj_lex_setup()` — 初始化词法分析器
- `lj_lex_next()` — 获取下一个 token
- `lj_lex_lookahead()` — 前瞻一个 token（不消耗）

#### `lj_parse.c` / `lj_parse.h` — 语法分析器与字节码生成器

这是 LuaJIT 前端最核心的文件（约 2736 行），负责将 Lua 源代码解析为字节码。它是一个 **单遍编译器**——在语法分析的同时直接生成字节码，不构建 AST。

表达式类型定义：

```c
typedef enum {
  VKNIL, VKFALSE, VKTRUE, VKSTR, VKNUM,   /* 常量表达式 */
  VKCDATA,                                   /* FFI C 数据常量 */
  VLOCAL,    /* 局部变量：info = 寄存器号 */
  VUPVAL,    /* 上值：info = 上值索引 */
  VGLOBAL,   /* 全局变量：sval = 字符串值 */
  VINDEXED,  /* 索引访问：info = 表寄存器, aux = 索引 */
  VJMP,      /* 条件跳转 */
  VRELOCABLE, /* 可重定位指令 */
  VNONRELOC,  /* 已分配寄存器的结果 */
  /* ... */
} ExpKind;
```

核心函数：
- `lj_parse()` — 主入口，解析一个 chunk 并返回 `GCproto`

#### `lj_bcread.c` — 字节码读取器

负责加载和验证预编译的字节码文件（`.luac` 格式）。处理字节序交换、版本校验等。

#### `lj_bcwrite.c` — 字节码写入器

将 `GCproto` 序列化为可存储的字节码格式。使用确定性排序（堆排序）来保证输出的可重现性。

### 11.3.2 字节码定义与虚拟机

#### `lj_bc.h` — 字节码指令格式定义

字节码指令为 32 位宽，支持两种格式：

```
+----+----+----+----+
| B  | C  | A  | OP |  格式 ABC
+----+----+----+----+
|    D    | A  | OP |  格式 AD
+--------------------
MSB               LSB
```

字段提取宏：

```c
#define bc_op(i)  ((BCOp)((i)&0xff))
#define bc_a(i)   ((BCReg)(((i)>>8)&0xff))
#define bc_b(i)   ((BCReg)((i)>>24))
#define bc_c(i)   ((BCReg)(((i)>>16)&0xff))
#define bc_d(i)   ((BCReg)((i)>>16))
#define bc_j(i)   ((ptrdiff_t)bc_d(i)-BCBIAS_J)
```

所有字节码通过 `BCDEF` 宏一次性定义（X-macro 模式），详见 11.5 节。

#### `lj_bc.c` — 字节码模式表

包含生成的字节码操作数模式表 `lj_bc_mode[]` 和偏移表 `lj_bc_ofs[]`。

#### `lj_vm.h` — 虚拟机汇编接口

声明了所有 VM 汇编入口点。这些函数的实际实现位于 `vm_*.dasc` 文件中（DynASM 模板）：

```c
/* VM 入口点 */
LJ_ASMF void lj_vm_call(lua_State *L, TValue *base, int nres1);
LJ_ASMF int lj_vm_pcall(lua_State *L, TValue *base, int nres1, ptrdiff_t ef);
LJ_ASMF int lj_vm_resume(lua_State *L, TValue *base, int nres1, ptrdiff_t ef);

/* Trace 退出处理 */
LJ_ASMF char lj_vm_exit_handler[];
LJ_ASMF char lj_vm_exit_interp[];

/* 录制和钩子调度 */
LJ_ASMF void lj_vm_record(void);
LJ_ASMF void lj_vm_inshook(void);
LJ_ASMF void lj_vm_rethook(void);

/* 元方法延续 */
LJ_ASMF void lj_cont_cat(void);    /* 字符串连接延续 */
LJ_ASMF void lj_cont_ra(void);     /* 存储结果到 RA */
LJ_ASMF void lj_cont_stitch(void); /* Trace stitching */
```

#### `vm_*.dasc` — 各架构的虚拟机实现

| 文件 | 目标架构 |
|------|----------|
| `vm_x86.dasc` | x86 (32-bit) |
| `vm_x64.dasc` | x86-64 |
| `vm_arm.dasc` | ARM (32-bit) |
| `vm_arm64.dasc` | AArch64 |
| `vm_mips.dasc` | MIPS (32-bit) |
| `vm_mips64.dasc` | MIPS (64-bit) |
| `vm_ppc.dasc` | PowerPC |

这些文件使用 DynASM 宏汇编编写，包含：
- 字节码分派循环（dispatch loop）
- 所有字节码指令的执行代码
- Trace 入口/退出代码
- 元方法调用桩
- C 函数调用/返回处理

#### `lj_dispatch.c` / `lj_dispatch.h` — 指令分派

管理字节码的执行分派和热计数器。核心数据结构 `GG_State` 将全局状态、JIT 状态和分派表分配在一起：

```c
typedef struct GG_State {
  lua_State L;               /* 主线程 */
  global_State g;            /* 全局状态 */
  jit_State J;               /* JIT 状态 */
  HotCount hotcount[HOTCOUNT_SIZE];  /* 热计数器 */
  ASMFunction dispatch[GG_LEN_DISP]; /* 指令分派表 */
  BCIns bcff[GG_NUM_ASMFF];  /* ASM 快速函数字节码 */
} GG_State;
```

热计数器是 16 位递减计数器，通过 PC 的哈希索引到 64 个槽位中：

```c
#define HOTCOUNT_SIZE    64
#define HOTCOUNT_PCMASK  ((HOTCOUNT_SIZE-1)*sizeof(HotCount))
#define HOTCOUNT_LOOP    2   /* 循环指令的递减量 */
#define HOTCOUNT_CALL    1   /* 调用指令的递减量 */

#define hotcount_get(gg, pc) \
  (gg)->hotcount[(u32ptr(pc)>>2) & (HOTCOUNT_SIZE-1)]
```

### 11.3.3 JIT 编译器

#### `lj_trace.c` / `lj_trace.h` — Trace 管理

管理 trace 的生命周期：创建、编译、链接、释放。

Trace 编译器状态机：

```c
typedef enum {
  LJ_TRACE_IDLE,        /* 空闲 */
  LJ_TRACE_RECORD,      /* 正在录制字节码 */
  LJ_TRACE_START,       /* 新 trace 开始 */
  LJ_TRACE_END,         /* trace 录制结束 */
  LJ_TRACE_ASM,         /* 汇编阶段 */
  LJ_TRACE_ERR          /* 编译出错 */
} TraceState;
```

核心函数：
- `lj_trace_hot()` — 热计数器溢出时调用，启动 trace 录制
- `lj_trace_ins()` — 每条字节码执行时调用（录制模式下）
- `lj_trace_flushall()` — 刷新所有 traces

#### `lj_record.c` / `lj_record.h` — Trace 录制器（字节码 -> SSA IR）

这是 JIT 编译器的第一个阶段，将字节码指令逐条"录制"为 SSA IR。录制时同时执行字节码以获取运行时类型信息。

录制索引操作的上下文：

```c
typedef struct RecordIndex {
  TValue tabv;     /* 表的运行时值 */
  TValue keyv;     /* 键的运行时值 */
  TValue valv;     /* 存储值的运行时值 */
  TValue mobjv;    /* 元方法对象的运行时值 */
  GCtab *mtv;      /* 元表的运行时值 */
  TRef tab;        /* 表的 IR 引用 */
  TRef key;        /* 键的 IR 引用 */
  TRef val;        /* 值的 IR 引用（存储时） */
  TRef mt;         /* 元表的 IR 引用 */
  int idxchain;    /* 剩余的索引间接层数 */
} RecordIndex;
```

核心函数：
- `lj_record_ins()` — 录制一条字节码指令
- `lj_record_setup()` — 初始化录制状态

IR 发射宏（经过优化管线）：

```c
#define emitir(ot, a, b)  (lj_ir_set(J, (ot), (a), (b)), lj_opt_fold(J))
#define emitir_raw(ot, a, b)  (lj_ir_set(J, (ot), (a), (b)), lj_ir_emit(J))
```

#### `lj_ffrecord.c` / `lj_ffrecord.h` — 快速函数录制器

为内置快速函数（如 `table.insert`、`string.sub` 等）提供专用的录制处理函数。每个快速函数都有对应的 `recff_*` 录制处理器。

#### `lj_ir.c` / `lj_ir.h` — SSA IR 定义与发射

**IR 指令格式**（64 位）：

```
    16      16     8   8   8   8
 +-------+-------+---+---+---+---+
 |  op1  |  op2  | t | o | r | s |
 +-------+-------+---+---+---+---+
 |  op12/i/gco32 |   ot  | prev  |  (联合体中的替代字段)
 +-------+-------+---+---+---+---+
 |  TValue/gco64                 |  (64位常量的第二个 IR 槽)
 +---------------+-------+-------+
```

IR 引用系统使用 16 位引用号，以 `REF_BIAS = 0x8000` 为分界：

```c
enum {
  REF_BIAS  = 0x8000,
  REF_TRUE  = REF_BIAS-3,
  REF_FALSE = REF_BIAS-2,
  REF_NIL   = REF_BIAS-1,  /* 常量向下增长 */
  REF_BASE  = REF_BIAS,    /* /--- IR 向上增长 */
  REF_FIRST = REF_BIAS+1,
  REF_DROP  = 0xffff
};
```

`TRef` 是带标签的 IR 引用（32 位），包含 IRType 和引用号：

```c
#define TREF(ref, t)    ((TRef)((ref) + ((t)<<24)))
#define tref_ref(tr)    ((IRRef1)(tr))
#define tref_type(tr)   ((IRType)(((tr)>>24) & IRT_TYPE))
```

#### `lj_opt_fold.c` — 常量折叠、代数简化和 CSE

这是优化管线中最复杂的文件（约 2656 行）。FOLD 引擎的工作原理：

1. 接收一条 IR 指令，存储在 `J->fold.ins`（fins）
2. 操作码 + 两个操作数的操作码形成 24 位键 `ins left right`
3. 从最具体到最不具体进行模式匹配：
   ```
   ins left right  →  ins any right  →  ins left any  →  ins any any
   ```
4. 匹配的折叠函数可以返回：
   - `NEXTFOLD` — 未折叠，继续匹配
   - `RETRYFOLD` — 指令被原地修改，重试折叠
   - `INTFOLD(i)` — 返回整数常量引用
   - `LEFTFOLD` / `RIGHTFOLD` — 直接返回操作数
   - `CSEFOLD` / `EMITFOLD` — 传递给 CSE 或直接发射
   - `FAILFOLD` / `DROPFOLD` / `CONDFOLD` — 处理 guard 指令

#### `lj_opt_dce.c` — 死代码消除

在 LOOP pass 之前运行。算法：

1. 扫描所有快照（snapshot），标记被引用的 IR 指令
2. 反向传播标记：对于有标记的指令，标记其操作数
3. 无标记且无副作用的指令被替换为 NOP

```c
void lj_opt_dce(jit_State *J)
{
  if ((J->flags & JIT_F_OPT_DCE)) {
    dce_marksnap(J);      /* 标记快照引用的指令 */
    dce_propagate(J);     /* 反向传播并消除死代码 */
    memset(J->bpropcache, 0, sizeof(J->bpropcache));
  }
}
```

#### `lj_opt_loop.c` — 循环优化

使用 **copy-substitution 展开** 而非传统的 LICM（循环不变代码外提）。原因是动态语言的 IR 中有大量 guard，传统 LICM 效果有限。

算法将录制的指令流重新发射到编译管线，用替换表替换操作数引用。这生成两个代码段：
1. **Pre-roll**：录制的指令（一次循环迭代的"预热"）
2. **Loop body**：仅包含变体指令

#### `lj_opt_narrow.c` — 数字窄化（double -> int32）

将浮点数运算窄化为整数运算，因为整数运算在 JIT 编译的紧密循环中延迟更低。采用保守策略——仅在确认安全时窄化，避免丢失 -0 或 NaN 语义。

#### `lj_opt_mem.c` — 内存访问优化

包含三个子优化：
- **AA（Alias Analysis）**：高级语义别名分析，利用 Lua 对象类型的已知语义
- **FWD（Load/Store Forwarding）**：消除冗余的加载和存储
- **DSE（Dead Store Elimination）**：消除不会被读取的存储

#### `lj_opt_sink.c` — 分配下沉

将循环中创建但不在循环外使用的对象分配下沉到 trace 退出路径，避免不必要的内存分配。

#### `lj_opt_split.c` — 64位 IR 指令拆分

仅在软浮点目标或 32 位 CPU + FFI 场景下激活。将 64 位 IR 指令拆分为多个 32 位指令，通过 `HIOP` 指令处理高 32 位。

#### `lj_asm.c` / `lj_asm.h` — IR 汇编器（SSA IR -> 机器码）

JIT 编译器的最后阶段，将优化后的 SSA IR 转换为目标平台的机器码。汇编器状态：

```c
typedef struct ASMState {
  RegCost cost[RID_MAX];  /* 寄存器分配代价 */
  MCode *mcp;             /* 当前机器码指针（向下增长） */
  MCode *mclim;           /* 机器码下限 + 红区 */
  IRIns *ir;              /* IR 指令副本指针 */
  jit_State *J;           /* JIT 状态 */
  RegSet freeset;         /* 空闲寄存器集合 */
  RegSet modset;          /* 循环内修改的寄存器 */
  RegSet weakset;         /* 弱引用寄存器 */
  RegSet phiset;          /* PHI 寄存器 */
  /* ... */
} ASMState;
```

各架构的汇编器实现在独立的头文件中：

| 文件 | 架构 |
|------|------|
| `lj_asm_x86.h` | x86/x64 |
| `lj_asm_arm.h` | ARM |
| `lj_asm_arm64.h` | AArch64 |
| `lj_asm_mips.h` | MIPS |
| `lj_asm_ppc.h` | PowerPC |

指令发射器也按架构分离：
- `lj_emit_x86.h` — x86/x64 指令编码
- `lj_emit_arm.h` — ARM 指令编码
- `lj_emit_arm64.h` — ARM64 指令编码
- `lj_emit_mips.h` — MIPS 指令编码
- `lj_emit_ppc.h` — PowerPC 指令编码

目标架构定义：
- `lj_target.h` — 目标架构通用定义
- `lj_target_x86.h` — x86/x64 寄存器、标志等
- `lj_target_arm.h` — ARM 寄存器、条件码等
- `lj_target_arm64.h` — ARM64 寄存器
- `lj_target_mips.h` — MIPS 寄存器
- `lj_target_ppc.h` — PPC 寄存器

#### `lj_ircall.h` — IR CALL* 指令定义

定义了 IR 中 `CALLN`/`CALLA`/`CALLL`/`CALLS` 指令调用的 C 函数表。

#### `lj_iropt.h` — IR 优化公共头文件

声明了所有优化 pass 的接口、常量内联函数、特殊返回值（`NEXTFOLD`、`RETRYFOLD` 等）。

### 11.3.4 数据结构与对象模型

#### `lj_obj.h` — 核心对象定义

这是 LuaJIT 最重要的头文件，定义了所有 Lua 值和对象的内存布局。

**TValue（Tagged Value）** 使用 NaN Tagging 技术：

```c
typedef LJ_ALIGN(8) union TValue {
  uint64_t u64;      /* 64 位模式 */
  lua_Number n;      /* 数字（双精度浮点） */
  GCRef gcr;         /* GC 对象引用 */
  int64_t it64;
  struct {
    LJ_ENDIAN_LOHI(
      int32_t i;     /* 整数值 */
    , uint32_t it;   /* 内部标签 */
    )
  };
  /* ... 帧链接字段 ... */
  struct {
    LJ_ENDIAN_LOHI(
      uint32_t lo;   /* 数字低 32 位 */
    , uint32_t hi;   /* 数字高 32 位 */
    )
  } u32;
} TValue;
```

**NaN Tagging 原理**：IEEE 754 双精度浮点中，NaN 的指数位全为 1。合法的 NaN 只需一个特定的位模式（`0xfff8_0000_0000_0000`），其余 NaN 位模式可用于存储类型标签和值。对于 32 位 GC 引用（非 GC64 模式），类型标签放在高 32 位（MSW），GC 引用放在低 32 位。

内部类型标签（使用补码编码，便于类型比较）：

```c
#define LJ_TNIL      (~0u)
#define LJ_TFALSE    (~1u)
#define LJ_TTRUE     (~2u)
#define LJ_TLIGHTUD  (~3u)
#define LJ_TSTR      (~4u)
#define LJ_TUPVAL    (~5u)
#define LJ_TTHREAD   (~6u)
#define LJ_TPROTO    (~7u)
#define LJ_TFUNC     (~8u)
#define LJ_TTRACE    (~9u)
#define LJ_TCDATA    (~10u)
#define LJ_TTAB      (~11u)
#define LJ_TUDATA    (~12u)
```

**GC 对象公共头**：

```c
#define GCHeader  GCRef nextgc; uint8_t marked; uint8_t gct
```

所有 GC 对象（字符串、表、函数、线程等）都以此 6 字节头开始。

**字符串对象**：

```c
typedef struct GCstr {
  GCHeader;
  uint8_t reserved;  /* 保留字快速查找标志 */
  uint8_t hashalg;   /* 哈希算法 */
  StrID sid;         /* 内部化字符串 ID */
  StrHash hash;      /* 字符串哈希值 */
  MSize len;         /* 字符串长度 */
} GCstr;
```

**表对象**：

```c
typedef struct GCtab {
  GCHeader;
  uint8_t nomm;      /* 元方法负缓存 */
  int8_t colo;       /* 数组共置（colocation） */
  MRef array;        /* 数组部分 */
  GCRef gclist;      /* GC 链表 */
  GCRef metatable;   /* 元表 */
  MRef node;         /* 哈希部分 */
  uint32_t asize;    /* 数组部分大小 */
  uint32_t hmask;    /* 哈希部分掩码 */
  MRef freetop;      /* 空闲元素顶部 */
} GCtab;
```

哈希节点：

```c
typedef struct Node {
  TValue val;   /* 值对象（必须是第一个字段） */
  TValue key;   /* 键对象 */
  MRef next;    /* 哈希链 */
} Node;
```

**函数对象**（闭包）：

```c
/* C 函数 */
typedef struct GCfuncC {
  GCfuncHeader;
  lua_CFunction f;    /* C 函数指针 */
  TValue upvalue[1];  /* 上值数组（TValue） */
} GCfuncC;

/* Lua 函数 */
typedef struct GCfuncL {
  GCfuncHeader;
  GCRef uvptr[1];     /* 上值对象指针数组（GCupval） */
} GCfuncL;
```

**原型对象**（函数原型/字节码容器）：

```c
typedef struct GCproto {
  GCHeader;
  uint8_t numparams;   /* 参数数量 */
  uint8_t framesize;   /* 固定帧大小 */
  MSize sizebc;        /* 字节码指令数量 */
  GCRef gclist;
  MRef k;              /* 常量数组（指向中间） */
  MRef uv;             /* 上值列表 */
  MSize sizekgc;       /* 可收集常量数量 */
  MSize sizekn;        /* 数字常量数量 */
  MSize sizept;        /* 总大小（含共置数组） */
  uint8_t sizeuv;      /* 上值数量 */
  uint8_t flags;       /* 杂项标志 */
  uint16_t trace;      /* 根 trace 链锚点 */
  GCRef chunkname;     /* chunk 名称 */
  BCLine firstline;    /* 函数定义首行 */
  BCLine numline;      /* 函数定义行数 */
  MRef lineinfo;       /* 行号信息（压缩） */
  MRef uvinfo;         /* 上值名称 */
  MRef varinfo;        /* 局部变量名称和范围 */
} GCproto;
```

**线程状态对象（lua_State）**：

```c
struct lua_State {
  GCHeader;
  uint8_t dummy_ffid;
  uint8_t status;        /* 线程状态 */
  MRef glref;            /* 全局状态链接 */
  GCRef gclist;          /* GC 链 */
  TValue *base;          /* 当前执行函数的栈基 */
  TValue *top;           /* 栈顶（第一个空闲槽） */
  TValue *maxstack;      /* 栈上限 */
  MRef stack;            /* 栈底 */
  /* ... */
};
```

**全局状态**：

```c
typedef struct global_State {
  lua_Alloc allocf;      /* 内存分配器 */
  void *allocd;          /* 分配器数据 */
  GCState gc;            /* 垃圾回收状态 */
  GCstr strempty;        /* 空字符串 */
  uint8_t hookmask;      /* 钩子掩码 */
  StrInternState str;    /* 字符串内部化状态 */
  volatile int32_t vmstate;  /* VM 状态 */
  GCRef mainthref;       /* 主线程链接 */
  SBuf tmpbuf;           /* 临时字符串缓冲区 */
  TValue registrytv;     /* 注册表锚点 */
  GCupval uvhead;        /* 开放上值双向链表头 */
  int32_t hookcount;     /* 指令钩子倒计时 */
  lua_Hook hookf;        /* 钩子函数 */
  lua_CFunction panic;   /* panic 函数 */
  BCIns bc_cfunc_int;    /* 内部 C 函数调用字节码 */
  BCIns bc_cfunc_ext;    /* 外部 C 函数调用字节码 */
  GCRef cur_L;           /* 当前执行的 lua_State */
  MRef jit_base;         /* JIT 代码的 L->base */
  MRef ctype_state;      /* C 类型状态指针 */
  PRNGState prng;        /* 全局 PRNG 状态 */
  GCRef gcroot[GCROOT_MAX];  /* GC 根 */
} global_State;
```

#### `lj_func.c` / `lj_func.h` — 函数处理

管理原型（prototype）、闭包（closure）和上值（upvalue）的创建和释放。

#### `lj_tab.c` / `lj_tab.h` — 表处理

表的哈希函数经过精心调优：

```c
#define HASH_BIAS  (-0x04c11db7)
#define HASH_ROT1  14
#define HASH_ROT2  5
#define HASH_ROT3  13

static LJ_AINLINE uint32_t hashrot(uint32_t lo, uint32_t hi)
{
  lo ^= hi; hi = lj_rol(hi, HASH_ROT1);
  lo -= hi; hi = lj_rol(hi, HASH_ROT2);
  hi ^= lo; hi -= lj_rol(lo, HASH_ROT3);
  return hi;
}
```

核心函数：
- `lj_tab_new()` — 创建新表
- `lj_tab_get()` / `lj_tab_set()` — 表的读写
- `lj_tab_next()` — 迭代器
- `lj_tab_resize()` — 表重哈希
- `lj_tab_len()` — 获取表长度（`#` 操作符）

#### `lj_str.c` / `lj_str.h` — 字符串处理

字符串内部化（interning）：所有字符串在创建时被去重并缓存在全局哈希表中。

```c
LJ_FUNCA GCstr *lj_str_new(lua_State *L, const char *str, size_t len);
LJ_FUNC void LJ_FASTCALL lj_str_free(global_State *g, GCstr *s);
LJ_FUNC void LJ_FASTCALL lj_str_init(lua_State *L);
LJ_FUNC void lj_str_resize(lua_State *L, MSize newmask);
```

### 11.3.5 垃圾回收

#### `lj_gc.c` / `lj_gc.h` — 垃圾回收器

实现增量三色标记-清除 GC。GC 状态：

```c
enum {
  GCSpause, GCSpropagate, GCSatomic, GCSsweepstring, GCSsweep, GCSfinalize
};
```

颜色标记：

```c
#define LJ_GC_WHITE0   0x01
#define LJ_GC_WHITE1   0x02
#define LJ_GC_BLACK    0x04
#define LJ_GC_FINALIZED 0x08
#define LJ_GC_FIXED    0x20
#define LJ_GC_SFIXED   0x40
```

写屏障（write barrier）是增量 GC 正确性的关键：

```c
/* 向后屏障：将黑色对象变回灰色 */
static LJ_AINLINE void lj_gc_barrierback(global_State *g, GCtab *t)
{
  GCobj *o = obj2gco(t);
  black2gray(o);
  setgcrefr(t->gclist, g->gc.grayagain);
  setgcref(g->gc.grayagain, o);
}

/* 表存储的屏障宏 */
#define lj_gc_anybarriert(L, t) \
  { if (LJ_UNLIKELY(isblack(obj2gco(t)))) lj_gc_barrierback(G(L), (t)); }
```

### 11.3.6 FFI（Foreign Function Interface）

FFI 子系统是 LuaJIT 最复杂的扩展之一，允许 Lua 代码直接操作 C 类型。

| 文件 | 作用 |
|------|------|
| `lj_ctype.c/h` | C 类型管理（类型 ID、类型信息） |
| `lj_cdata.c/h` | C 数据对象（`GCcdata`） |
| `lj_cparse.c/h` | C 类型声明解析器 |
| `lj_cconv.c/h` | C 类型转换 |
| `lj_carith.c/h` | C 算术运算 |
| `lj_ccall.c/h` | C 函数调用（参数传递） |
| `lj_ccallback.c/h` | C 回调（Lua 函数作为 C 回调） |
| `lj_clib.c/h` | C 共享库加载 |
| `lj_crecord.c/h` | C 数据操作的 trace 录制 |
| `lib_ffi.c` | `ffi.*` 库的 Lua 绑定 |

### 11.3.7 内置库

| 文件 | 库名 | 说明 |
|------|------|------|
| `lib_init.c` | — | 库初始化，`luaL_openlibs()` 实现 |
| `lib_base.c` | base | `print`、`type`、`tostring`、`pcall`、`require` 等 |
| `lib_math.c` | math | `math.*` 函数 |
| `lib_string.c` | string | `string.*` 函数 |
| `lib_table.c` | table | `table.*` 函数 |
| `lib_io.c` | io | `io.*` 文件 I/O |
| `lib_os.c` | os | `os.*` 系统调用 |
| `lib_debug.c` | debug | `debug.*` 调试接口 |
| `lib_bit.c` | bit | 位操作库 |
| `lib_jit.c` | jit | JIT 控制库（`jit.on/off/flush/opt`） |
| `lib_ffi.c` | ffi | FFI 库 |
| `lib_buffer.c` | buffer | 字符串缓冲区库 |
| `lib_package.c` | package | 模块加载系统 |
| `lj_lib.c/h` | — | 库辅助函数 |
| `lj_load.c` | — | 加载器（`luaL_loadfile`、`luaL_loadstring`） |

### 11.3.8 其他核心文件

| 文件 | 作用 |
|------|------|
| `lj_alloc.c/h` | 内存分配器（基于 dlmalloc） |
| `lj_api.c` | Lua C API 实现（`lua_push*`、`lua_to*` 等） |
| `lj_err.c/h` | 错误处理和异常展开 |
| `lj_errmsg.h` | 错误消息字符串表 |
| `lj_buf.c/h` | 可增长字符串缓冲区 |
| `lj_strscan.c/h` | 字符串到数字扫描器 |
| `lj_strfmt.c/h` | 字符串格式化 |
| `lj_strfmt_num.c` | 数字到字符串格式化 |
| `lj_debug.c/h` | 调试信息（行号、变量名等） |
| `lj_char.c/h` | 字符分类表 |
| `lj_meta.c/h` | 元方法调度 |
| `lj_profile.c/h` | 采样分析器 |
| `lj_prng.c/h` | 伪随机数生成器 |
| `lj_gdbjit.c/h` | GDB JIT 编译接口（`__jit_debug_register_code`） |
| `lj_vmevent.c/h` | VM 事件系统 |
| `lj_serialize.c/h` | 序列化/反序列化 |
| `lj_mcode.c/h` | 机器码内存管理 |
| `lj_vmmath.c` | VM 数学辅助函数 |
| `lj_obj.c` | 对象辅助函数 |
| `lj_assert.c` | 断言实现 |
| `lj_udata.c/h` | 用户数据对象 |
| `lj_arch.h` | 架构检测和平台宏 |
| `lj_def.h` | 基本定义（类型、宏） |
| `lj_frame.h` | 栈帧布局定义 |
| `lj_traceerr.h` | Trace 编译错误消息 |
| `lj_ffdef.h` | 快速函数定义（生成） |
| `lj_bcdef.h` | 字节码定义（生成） |
| `ljamalg.c` | Amalgamated 编译（单文件编译所有 .c） |
| `luajit.c` | 命令行入口（`main()`） |
| `lua.h` / `luaconf.h` / `lualib.h` / `lauxlib.h` | 标准 Lua 头文件 |

### 11.3.9 `lj_ff.h` / `lj_ffdef.h` — 快速函数

LuaJIT 将标准库函数分为"快速函数"（Fast Functions），它们有专用的字节码和 ASM 桩，避免了通用 C 函数调用的开销：

```c
typedef enum {
  FF_LUA_ = FF_LUA,   /* Lua 函数（必须为 0） */
  FF_C_ = FF_C,       /* 普通 C 函数（必须为 1） */
#define FFDEF(name) FF_##name,
#include "lj_ffdef.h"
  FF__MAX
} FastFunc;
```

---

## 11.4 LuaJIT 编译流程详解

LuaJIT 的完整编译和执行流程可以用以下 ASCII 图表示：

```
                    LuaJIT 编译与执行流程
                    =====================

  ┌─────────────────────────────────────────────────────────────┐
  │                    源代码文本 (.lua)                         │
  └──────────────────────────┬──────────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  前端：词法分析 + 语法分析 + 字节码生成                      │
  │  ┌──────────┐    ┌──────────┐    ┌──────────────────┐       │
  │  │ lj_lex.c │───▶│lj_parse.c│───▶│ 字节码 (GCproto) │       │
  │  │ 词法分析  │    │ 语法分析  │    │   lj_bc.h 定义   │       │
  │  └──────────┘    └──────────┘    └──────────────────┘       │
  └─────────────────────────────────────────────────────────────┘
                             │
                             ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  解释器执行（vm_*.dasc）                                     │
  │                                                             │
  │  ┌──────────────────────────────────────────────────────┐   │
  │  │           字节码分派循环 (dispatch loop)              │   │
  │  │                                                      │   │
  │  │   ┌─────────┐    ┌──────────────┐    ┌──────────┐   │   │
  │  │   │ 取指令   │───▶│ 热计数器递减  │───▶│ 分派执行  │   │   │
  │  │   │ fetch PC │    │ hotcount--   │    │ dispatch │   │   │
  │  │   └─────────┘    └──────┬───────┘    └──────────┘   │   │
  │  │                         │                            │   │
  │  │              ┌──────────▼───────────┐                │   │
  │  │              │  热计数器溢出？        │                │   │
  │  │              │  hotcount == 0 ?      │                │   │
  │  │              └──┬──────────────┬────┘                │   │
  │  │                 │ 否           │ 是                   │   │
  │  │                 ▼              ▼                      │   │
  │  │            继续解释执行    lj_trace_hot()             │   │
  │  └─────────────────────────────┼────────────────────────┘   │
  └────────────────────────────────┼────────────────────────────┘
                                   │
                                   ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  JIT 编译管线                                                │
  │                                                             │
  │  Phase 1: Trace 录制 (lj_record.c)                          │
  │  ┌───────────────────────────────────────────────────────┐  │
  │  │  字节码 ──录制──▶ SSA IR (lj_ir.h)                    │  │
  │  │                                                       │  │
  │  │  录制时同时执行字节码，获取运行时类型信息               │  │
  │  │  每条字节码 → 一条或多条 IR 指令                       │  │
  │  │  在循环回边处检测到循环 → 结束录制                      │  │
  │  └───────────────────────────┬───────────────────────────┘  │
  │                              │                              │
  │  Phase 2: 优化 passes                                        │
  │  ┌───────────────────────────▼───────────────────────────┐  │
  │  │                                                       │  │
  │  │   IR 指令流 ──▶ FOLD (常量折叠/CSE)                   │  │
  │  │              ──▶ DCE (死代码消除)                      │  │
  │  │              ──▶ FWD/DSE (内存访问优化)                │  │
  │  │              ──▶ NARROW (数字窄化)                     │  │
  │  │              ──▶ LOOP (循环优化/展开)                  │  │
  │  │              ──▶ SINK (分配下沉)                       │  │
  │  │              ──▶ SPLIT (64位拆分，仅32位平台)          │  │
  │  │                                                       │  │
  │  └───────────────────────────┬───────────────────────────┘  │
  │                              │                              │
  │  Phase 3: 汇编 (lj_asm.c)                                   │
  │  ┌───────────────────────────▼───────────────────────────┐  │
  │  │                                                       │  │
  │  │   SSA IR ──▶ 寄存器分配 ──▶ 机器码生成               │  │
  │  │                                                       │  │
  │  │   输出：GCtrace 对象（包含机器码 + 快照）             │  │
  │  │                                                       │  │
  │  └───────────────────────────┬───────────────────────────┘  │
  └──────────────────────────────┼──────────────────────────────┘
                                 │
                                 ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  执行 JIT 编译的代码                                         │
  │                                                             │
  │  ┌──────────────────────────────────────────────────────┐   │
  │  │  Trace 执行                                           │   │
  │  │                                                       │   │
  │  │   入口 ──▶ 执行机器码 ──▶ 循环回边（继续或退出）     │   │
  │  │                         │                             │   │
  │  │              ┌──────────▼──────────┐                  │   │
  │  │              │ Guard 失败？        │                  │   │
  │  │              └──┬─────────────┬────┘                  │   │
  │  │                 │ 否          │ 是                    │   │
  │  │                 ▼             ▼                       │   │
  │  │            继续执行      Trace Exit                   │   │
  │  │                          │                            │   │
  │  │                 ┌────────▼────────┐                   │   │
  │  │                 │ 恢复解释器状态   │                   │   │
  │  │                 │ (snapshot restore)│                  │   │
  │  │                 └────────┬────────┘                   │   │
  │  │                          │                            │   │
  │  │                 ┌────────▼────────┐                   │   │
  │  │                 │ 退出次数足够多？ │                   │   │
  │  │                 │ exitcount > 10  │                   │   │
  │  │                 └──┬──────────┬───┘                   │   │
  │  │                    │ 否       │ 是                    │   │
  │  │                    ▼          ▼                       │   │
  │  │               继续解释    Side Trace 录制             │   │
  │  │                           (lj_record.c)               │   │
  │  └──────────────────────────────────────────────────────┘   │
  └─────────────────────────────────────────────────────────────┘
```

### Trace 录制的详细流程

```
  热计数器溢出
       │
       ▼
  ┌─────────────────┐
  │ lj_trace_hot()  │
  │ 设置 state =    │
  │ LJ_TRACE_START  │
  └────────┬────────┘
           │
           ▼
  ┌─────────────────┐     ┌──────────────────────┐
  │ 开始录制         │────▶│ lj_record_ins()      │
  │ state =          │     │ 每条字节码生成 IR     │
  │ LJ_TRACE_RECORD  │     │                      │
  └─────────────────┘     │ emitir() 经过优化管线 │
                          └──────────┬───────────┘
                                     │
                          检测到循环回边
                                     │
                                     ▼
                          ┌──────────────────────┐
                          │ lj_record_stop()      │
                          │ state = LJ_TRACE_END  │
                          └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │ lj_opt_dce()          │
                          │ 死代码消除             │
                          └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │ lj_opt_loop()          │
                          │ 循环优化/展开           │
                          └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │ lj_opt_sink()          │
                          │ 分配下沉               │
                          └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │ lj_asm_trace()         │
                          │ SSA IR → 机器码        │
                          │ state = LJ_TRACE_ASM   │
                          └──────────┬───────────┘
                                     │
                          ┌──────────▼───────────┐
                          │ 复制到 GCtrace 对象    │
                          │ 链接到 trace 数组      │
                          │ 修补字节码跳转目标     │
                          └──────────────────────┘
```

---

## 11.5 LuaJIT 字节码指令集

LuaJIT 的字节码指令为 32 位宽，所有指令通过 `BCDEF` 宏一次性定义。以下是完整的指令集分类说明。

### 指令格式

```
+----+----+----+----+
| B  | C  | A  | OP |   格式 ABC（8+8+8+8 位）
+----+----+----+----+
|    D    | A  | OP |   格式 AD（16+8+8 位）
+--------------------
```

操作数类型后缀含义：
- `V` = 变量槽（variable slot）
- `S` = 字符串常量
- `N` = 数字常量
- `P` = 原始类型（primitive，`~itype`）
- `B` = 无符号字节字面量
- `M` = 多参数/结果
- `rbase` = 相对基址寄存器
- `jump` = 跳转偏移

### 比较指令（Comparison）

| 指令 | 格式 | 说明 | 元方法 |
|------|------|------|--------|
| `ISLT` | AD | `if A < D` | lt |
| `ISGE` | AD | `if A >= D` | lt |
| `ISLE` | AD | `if A <= D` | le |
| `ISGT` | AD | `if A > D` | le |
| `ISEQV` | AD | `if A == D`（变量） | eq |
| `ISNEV` | AD | `if A ~= D`（变量） | eq |
| `ISEQS` | AD | `if A == D`（字符串） | eq |
| `ISNES` | AD | `if A ~= D`（字符串） | eq |
| `ISEQN` | AD | `if A == D`（数字） | eq |
| `ISNEN` | AD | `if A ~= D`（数字） | eq |
| `ISEQP` | AD | `if A == D`（原始类型） | eq |
| `ISNEP` | AD | `if A ~= D`（原始类型） | eq |

### 一元测试和复制指令

| 指令 | 格式 | 说明 |
|------|------|------|
| `ISTC` | AD | `A = D; if D` (true copy) |
| `ISFC` | AD | `A = D; if not D` (false copy) |
| `IST` | AD | `if D` (test) |
| `ISF` | AD | `if not D` (test false) |
| `ISTYPE` | AD | 检查 A 的类型是否为 D |
| `ISNUM` | AD | 检查 A 是否为数字 |

### 一元运算指令

| 指令 | 格式 | 说明 | 元方法 |
|------|------|------|--------|
| `MOV` | AD | `A = D` | — |
| `NOT` | AD | `A = not D` | — |
| `UNM` | AD | `A = -D` | unm |
| `LEN` | AD | `A = #D` | len |

### 二元运算指令

算术指令按操作数类型细分（VN = 变量+数字, NV = 数字+变量, VV = 变量+变量）：

| 指令 | 格式 | 说明 | 元方法 |
|------|------|------|--------|
| `ADDVN` | ABC | `A = B + C`（C为数字常量） | add |
| `SUBVN` | ABC | `A = B - C` | sub |
| `MULVN` | ABC | `A = B * C` | mul |
| `DIVVN` | ABC | `A = B / C` | div |
| `MODVN` | ABC | `A = B % C` | mod |
| `ADDNV` | ABC | `A = C + B`（C为数字常量） | add |
| `SUBNV` | ABC | `A = C - B` | sub |
| `MULNV` | ABC | `A = C * B` | mul |
| `DIVNV` | ABC | `A = C / B` | div |
| `MODNV` | ABC | `A = C % B` | mod |
| `ADDVV` | ABC | `A = B + C`（均为变量） | add |
| `SUBVV` | ABC | `A = B - C` | sub |
| `MULVV` | ABC | `A = B * C` | mul |
| `DIVVV` | ABC | `A = B / C` | div |
| `MODVV` | ABC | `A = B % C` | mod |
| `POW` | ABC | `A = B ^ C` | pow |
| `CAT` | ABC | `A = B .. ... .. C` | concat |

### 常量指令

| 指令 | 格式 | 说明 |
|------|------|------|
| `KSTR` | AD | `A = 字符串常量[D]` |
| `KCDATA` | AD | `A = C 数据常量[D]` |
| `KSHORT` | AD | `A = 有符号 16 位整数 D` |
| `KNUM` | AD | `A = 数字常量[D]` |
| `KPRI` | AD | `A = 原始类型 D`（nil/false/true） |
| `KNIL` | AD | `A..D = nil` |

### 上值和函数指令

| 指令 | 格式 | 说明 |
|------|------|------|
| `UGET` | AD | `A = 上值[D]` |
| `USETV` | AD | `上值[A] = D`（变量） |
| `USETS` | AD | `上值[A] = 字符串常量[D]` |
| `USETN` | AD | `上值[A] = 数字常量[D]` |
| `USETP` | AD | `上值[A] = 原始类型 D` |
| `UCLO` | AD | 关闭 A 以上的所有上值，跳转到 D |
| `FNEW` | AD | `A = new Closure(原型[D])` |

### 表操作指令

| 指令 | 格式 | 说明 |
|------|------|------|
| `TNEW` | AD | `A = new Table(D)` |
| `TDUP` | AD | `A = dup Table(常量[D])` |
| `GGET` | AD | `A = _ENV["D"]`（全局变量读取，D为字符串） |
| `GSET` | AD | `_ENV["D"] = A`（全局变量写入） |
| `TGETV` | ABC | `A = B[C]`（C为变量） |
| `TGETS` | ABC | `A = B["C"]`（C为字符串常量） |
| `TGETB` | ABC | `A = B[C]`（C为字面量） |
| `TGETR` | ABC | `A = B[C]`（raw get，无元方法） |
| `TSETV` | ABC | `B[C] = A`（C为变量） |
| `TSETS` | ABC | `B["C"] = A`（C为字符串常量） |
| `TSETB` | ABC | `B[C] = A`（C为字面量） |
| `TSETM` | AD | `A..top = 多重赋值`（设置数组部分） |
| `TSETR` | ABC | `B[C] = A`（raw set，无元方法） |

### 调用和可变参数指令

| 指令 | 格式 | 说明 |
|------|------|------|
| `CALLM` | ABC | `A..top = A(A+1..B, 多重参数..C)` |
| `CALL` | ABC | `A..A+C-2 = A(A+1..B-1)` |
| `CALLMT` | AD | 尾调用（多重参数） |
| `CALLT` | AD | `return A(A+1..D-1)`（尾调用） |
| `ITERC` | ABC | 迭代器调用 |
| `ITERN` | ABC | 迭代器调用（特化版） |
| `VARG` | ABC | 可变参数访问 |
| `ISNEXT` | AD | 检查 `for in` 迭代器是否为 `next` |

### 返回指令

| 指令 | 格式 | 说明 |
|------|------|------|
| `RETM` | AD | `return A..top, D个结果` |
| `RET` | AD | `return A..A+D-2` |
| `RET0` | AD | `return`（无返回值） |
| `RET1` | AD | `return A`（单返回值） |

### 循环和分支指令

| 指令 | 格式 | 说明 |
|------|------|------|
| `FORI` | AD | `for` 数值循环初始化 |
| `JFORI` | AD | JIT 版 FORI |
| `FORL` | AD | `for` 数值循环体 |
| `IFORL` | AD | 解释器版 FORL |
| `JFORL` | AD | JIT 编译的 FORL |
| `ITERL` | AD | `for in` 迭代器循环 |
| `IITERL` | AD | 解释器版 ITERL |
| `JITERL` | AD | JIT 编译的 ITERL |
| `LOOP` | AD | 通用循环标记 |
| `ILOOP` | AD | 解释器版 LOOP |
| `JLOOP` | AD | JIT 编译的 LOOP |
| `JMP` | AD | 无条件跳转 |

### 函数头指令

| 指令 | 格式 | 说明 |
|------|------|------|
| `FUNCF` | — | 固定参数 Lua 函数头 |
| `IFUNCF` | — | 解释器版 FUNCF |
| `JFUNCF` | AD | JIT 编译的 FUNCF |
| `FUNCV` | — | 可变参数 Lua 函数头 |
| `IFUNCV` | — | 解释器版 FUNCV |
| `JFUNCV` | AD | JIT 编译的 FUNCV |
| `FUNCC` | — | C 函数头 |
| `FUNCCW` | — | 带包装器的 C 函数头 |

### 指令编码布局

```
BC__MAX = 总指令数（约 80+ 条）

指令分组的顺序很重要：
1. 比较指令：ISLT..ISNEP（使用 ^1 编码 eq/ne, lt/ge, le/gt 对）
2. 测试指令：ISTC..ISNUM
3. 一元指令：MOV, NOT, UNM, LEN
4. 二元指令：ADDVN..POW, CAT
5. 常量指令：KSTR..KNIL
6. 上值指令：UGET..FNEW
7. 表指令：TNEW..TSETR
8. 调用指令：CALLM..ISNEXT
9. 返回指令：RETM..RET1
10. 循环指令：FORI..JMP
11. 函数头指令：FUNCF..FUNCCW
```

---

## 11.6 LuaJIT 的 IR（中间表示）

LuaJIT 的 JIT 编译器使用严格的 SSA（Static Single Assignment）形式的中间表示。IR 是 JIT 编译管线的核心数据结构。

### 11.6.1 IR 指令格式

每条 IR 指令占用 64 位（或 128 位用于 64 位常量）：

```
    16      16     8   8   8   8
 +-------+-------+---+---+---+---+
 |  op1  |  op2  | t | o | r | s |
 +-------+-------+---+---+---+---+

 op1/op2:  操作数（IR 引用或字面量）
 t:        结果类型 (IRType)
 o:        操作码 (IROp)
 r:        寄存器分配
 s:        溢出槽分配
```

对于 64 位常量（KNUM、KINT64），使用两个连续的 IR 槽：

```
 +-------+-------+---+---+---+---+
 |  op1  |  op2  | t | o | r | s |  <- KNUM/KINT64 指令
 +-------+-------+---+---+---+---+
 |          TValue (64-bit)       |  <- 常量值
 +---------------+-------+-------+
```

### 11.6.2 IR 操作码分类

所有 IR 操作码通过 `IRDEF` 宏定义。以下是完整分类：

#### Guard（守卫/断言）

| 操作码 | 说明 |
|--------|------|
| `LT`, `GE`, `LE`, `GT` | 有符号比较守卫 |
| `ULT`, `UGE`, `ULE`, `UGT` | 无符号比较守卫 |
| `EQ`, `NE` | 相等性守卫 |
| `ABC` | 数组边界检查 |
| `RETF` | 返回帧守卫 |

#### 杂项

| 操作码 | 说明 |
|--------|------|
| `NOP` | 空操作 |
| `BASE` | 帧基址标记 |
| `PVAL` | PHI 值 |
| `GCSTEP` | GC 步进 |
| `HIOP` | 高 32 位操作（SPLIT pass） |
| `LOOP` | 循环标记 |
| `USE` | 使用标记（DCE） |
| `PHI` | PHI 节点 |
| `RENAME` | 重命名（消除 PHI） |
| `PROF` | 性能分析标记 |

#### 常量

| 操作码 | 说明 |
|--------|------|
| `KPRI` | 原始类型常量（nil/false/true） |
| `KINT` | 32 位整数常量 |
| `KGC` | GC 对象常量 |
| `KPTR` | 指针常量 |
| `KKPTR` | 不可变指针常量 |
| `KNULL` | NULL 指针常量 |
| `KNUM` | 双精度浮点常量 |
| `KINT64` | 64 位整数常量 |
| `KSLOT` | 哈希表槽位常量 |

#### 位运算

| 操作码 | 说明 |
|--------|------|
| `BNOT` | 按位取反 |
| `BSWAP` | 字节序交换 |
| `BAND`, `BOR`, `BXOR` | 按位与/或/异或 |
| `BSHL`, `BSHR`, `BSAR` | 左移/逻辑右移/算术右移 |
| `BROL`, `BROR` | 循环左移/右移 |

#### 算术运算

| 操作码 | 说明 | 可交换 |
|--------|------|--------|
| `ADD` | 加法 | 是 |
| `SUB` | 减法 | — |
| `MUL` | 乘法 | 是 |
| `DIV` | 除法 | — |
| `MOD` | 取模 | — |
| `POW` | 幂运算 | — |
| `NEG` | 取负 | — |
| `ABS` | 绝对值 | — |
| `LDEXP` | ldexp | — |
| `MIN`, `MAX` | 最小/最大值 | — |
| `FPMATH` | 浮点数学函数 | — |

`FPMATH` 的子操作（`IRFPMathOp`）：
- `FLOOR`, `CEIL`, `TRUNC` — 取整
- `SQRT`, `LOG`, `LOG2` — 数学函数

#### 溢出检查算术

| 操作码 | 说明 |
|--------|------|
| `ADDOV` | 带溢出检查的加法 |
| `SUBOV` | 带溢出检查的减法 |
| `MULOV` | 带溢出检查的乘法 |

#### 内存引用

| 操作码 | 说明 |
|--------|------|
| `AREF` | 数组元素引用 |
| `HREFK` | 哈希表键引用（已知键） |
| `HREF` | 哈希表键引用（通用） |
| `NEWREF` | 新建哈希表引用 |
| `UREFO` / `UREFC` | 开放/关闭上值引用 |
| `FREF` | 字段引用 |
| `TMPREF` | 临时引用 |
| `STRREF` | 字符串引用 |
| `LREF` | 栈槽引用 |

#### 加载和存储

加载和存储操作码一一对应（xLOAD 和 xSTORE）：

| 加载 | 存储 | 说明 |
|------|------|------|
| `ALOAD` | `ASTORE` | 数组加载/存储 |
| `HLOAD` | `HSTORE` | 哈希表加载/存储 |
| `ULOAD` | `USTORE` | 上值加载/存储 |
| `FLOAD` | `FSTORE` | 字段加载/存储 |
| `XLOAD` | `XSTORE` | 外部加载/存储 |
| `SLOAD` | — | 栈槽加载（无对应存储） |
| `VLOAD` | — | 可变参数加载 |
| `ALEN` | — | 数组长度 |

`FLOAD` 的字段 ID（`IRFieldID`）定义了可以加载哪些字段：

```c
_(STR_LEN,        offsetof(GCstr, len))
_(FUNC_ENV,       offsetof(GCfunc, l.env))
_(FUNC_PC,        offsetof(GCfunc, l.pc))
_(FUNC_FFID,      offsetof(GCfunc, l.ffid))
_(TAB_META,       offsetof(GCtab, metatable))
_(TAB_ARRAY,      offsetof(GCtab, array))
_(TAB_NODE,       offsetof(GCtab, node))
_(TAB_ASIZE,      offsetof(GCtab, asize))
_(TAB_HMASK,      offsetof(GCtab, hmask))
_(CDATA_CTYPEID,  offsetof(GCcdata, ctypeid))
/* ... */
```

#### 分配

| 操作码 | 说明 |
|--------|------|
| `SNEW` | 创建新字符串 |
| `XSNEW` | 创建新字符串（外部） |
| `TNEW` | 创建新表 |
| `TDUP` | 复制表 |
| `CNEW` | 创建新 C 数据 |
| `CNEWI` | 创建新 C 数据（初始化） |

#### 缓冲区操作

| 操作码 | 说明 |
|--------|------|
| `BUFHDR` | 缓冲区头 |
| `BUFPUT` | 缓冲区写入 |
| `BUFSTR` | 缓冲区转字符串 |

#### 屏障（Barrier）

| 操作码 | 说明 |
|--------|------|
| `TBAR` | 表屏障 |
| `OBAR` | 对象屏障 |
| `XBAR` | 交叉屏障 |

#### 类型转换

| 操作码 | 说明 |
|--------|------|
| `CONV` | 通用类型转换 |
| `TOBIT` | 转换为位整数 |
| `TOSTR` | 转换为字符串 |
| `STRTO` | 字符串转换为数字 |

#### 调用

| 操作码 | 说明 |
|--------|------|
| `CALLN` | 调用（返回数字） |
| `CALLA` | 调用（返回任意） |
| `CALLL` | 调用（返回 Lua 值） |
| `CALLS` | 调用（返回字符串） |
| `CALLXS` | 调用 C 函数 |
| `CARG` | C 函数参数 |

### 11.6.3 IR 类型系统

```c
#define IRTDEF(_) \
  _(NIL, 4) _(FALSE, 4) _(TRUE, 4) _(LIGHTUD, 8) \
  _(STR, PGC) _(P32, 4) _(THREAD, PGC) _(PROTO, PGC) \
  _(FUNC, PGC) _(P64, 8) _(CDATA, PGC) _(TAB, PGC) \
  _(UDATA, PGC) \
  _(FLOAT, 4) _(NUM, 8) \
  _(I8, 1) _(U8, 1) _(I16, 2) _(U16, 2) \
  _(INT, 4) _(U32, 4) _(I64, 8) _(U64, 8) \
  _(SOFTFP, 4)
```

类型分类：
- **原始类型**：`NIL`, `FALSE`, `TRUE`
- **GC 对象**：`STR`, `THREAD`, `PROTO`, `FUNC`, `CDATA`, `TAB`, `UDATA`
- **浮点数**：`FLOAT`（32位）, `NUM`（64位双精度）
- **整数**：`I8`, `U8`, `I16`, `U16`, `INT`（32位有符号）, `U32`, `I64`, `U64`
- **指针**：`LIGHTUD`, `P32`, `P64`

### 11.6.4 IR 操作数模式

每个 IR 操作码的操作数类型通过 `lj_ir_mode[]` 表定义：

```c
typedef enum {
  IRMref,    /* IR 引用 */
  IRMlit,    /* 16 位无符号字面量 */
  IRMcst,    /* 常量字面量（i, gcr 或 ptr） */
  IRMnone    /* 未使用 */
} IRMode;
```

模式标志位：
- `IRM_C` (0x10) — 可交换
- `IRM_N` (0x00) — 普通/引用
- `IRM_A` (0x20) — 分配
- `IRM_L` (0x40) — 加载
- `IRM_S` (0x60) — 存储
- `IRM_W` (0x80) — 非弱守卫

### 11.6.5 优化 Pass 管线

```
  emitir(ot, a, b)
       │
       ▼
  ┌─────────────┐
  │ lj_opt_fold │ ← FOLD: 常量折叠 + 代数简化 + CSE
  │ (lj_opt_    │
  │  fold.c)    │
  └──────┬──────┘
         │
    生成完整 trace 后：
         │
  ┌──────▼──────┐
  │ lj_opt_dce  │ ← DCE: 死代码消除
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │ lj_opt_loop │ ← LOOP: 循环优化（copy-substitution 展开）
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │ lj_opt_sink │ ← SINK: 分配下沉 + 存储下沉
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │lj_opt_split │ ← SPLIT: 64 位拆分（仅 32 位平台）
  └──────┬──────┘
         │
  ┌──────▼──────┐
  │ lj_asm_trace│ ← ASM: 寄存器分配 + 机器码生成
  └─────────────┘
```

FOLD 引擎在每条 IR 指令发射时立即运行（在线优化），其他 pass 在 trace 录制完成后运行（离线优化）。

---

## 11.7 LuaJIT 的 Trace 录制

### 11.7.1 热点检测与 Trace 触发

LuaJIT 使用 **热计数器**（Hot Counter）来检测热点代码。热计数器是一个 16 位递减计数器，通过 PC 的哈希值索引到 64 个槽位的哈希表中。

```c
typedef uint16_t HotCount;
#define HOTCOUNT_SIZE  64

#define hotcount_get(gg, pc) \
  (gg)->hotcount[(u32ptr(pc)>>2) & (HOTCOUNT_SIZE-1)]
```

- 循环指令（`FORL`、`ITERL`、`LOOP`）执行时，热计数器递减 2
- 调用指令（`CALL`、`CALLT`）执行时，热计数器递减 1
- 默认阈值：56（`hotloop` 参数）
- 当热计数器溢出（归零）时，调用 `lj_trace_hot()` 启动 trace 录制

### 11.7.2 Trace 录制过程

录制过程本质上是"边执行边翻译"：

1. **开始录制**：在循环回边处开始，设置 `J->state = LJ_TRACE_START`
2. **逐条录制**：对每条字节码调用 `lj_record_ins()`
3. **生成 IR**：字节码被翻译为一条或多条 IR 指令
4. **获取类型信息**：同时执行字节码，从运行时值中提取类型信息
5. **类型特化**：根据运行时类型生成特化的 IR（如 `ADDVN` 而非通用 `ADD`）
6. **循环检测**：当 PC 回到 trace 起点时，结束录制
7. **优化和汇编**：运行优化 passes，生成机器码

录制的关键宏：

```c
/* 发射 IR 并经过优化管线 */
#define emitir(ot, a, b)  (lj_ir_set(J, (ot), (a), (b)), lj_opt_fold(J))

/* 发射原始 IR，不经过优化 */
#define emitir_raw(ot, a, b)  (lj_ir_set(J, (ot), (a), (b)), lj_ir_emit(J))
```

### 11.7.3 快照（Snapshot）机制

快照是 LuaJIT trace 编译的核心概念之一。快照记录了 trace 执行到某一点时栈上所有活跃值的状态，用于在 guard 失败时恢复解释器状态。

```c
typedef struct SnapShot {
  uint32_t mapofs;  /* 快照映射中的偏移 */
  IRRef1 ref;       /* 此快照的第一个 IR 引用 */
  uint16_t mcofs;   /* 机器码中的偏移 */
  uint8_t nslots;   /* 有效槽数量 */
  uint8_t topslot;  /* 最大帧范围 */
  uint8_t nent;     /* 压缩条目数 */
  uint8_t count;    /* 已执行的退出次数 */
} SnapShot;

/* 压缩的快照条目 */
typedef uint32_t SnapEntry;

#define SNAP(slot, flags, ref)  (((SnapEntry)(slot) << 24) + (flags) + (ref))
```

快照条目的标志位：
- `SNAP_FRAME` (0x010000) — 帧槽
- `SNAP_CONT` (0x020000) — 延续槽
- `SNAP_NORESTORE` (0x040000) — 无需恢复
- `SNAP_SOFTFPNUM` (0x080000) — 软浮点数字
- `SNAP_KEYINDEX` (0x100000) — 遍历键索引

当 guard 失败时：
1. 查找最近的快照
2. 从快照映射中恢复所有栈槽的值
3. 回退到解释器继续执行

### 11.7.4 Side Trace（侧 Trace）

当已编译的 trace 通过某个 guard 退出时，如果该退出点被频繁触发（默认阈值 `hotexit = 10`），LuaJIT 会从该退出点开始录制一个新的 **side trace**。

Side trace 的特点：
- 从父 trace 的某个退出点开始
- 可以链接回父 trace（形成循环）或链接到其他 trace
- 最多 100 个 side trace per root trace（`maxside` 参数）

Trace 链接类型：

```c
typedef enum {
  LJ_TRLINK_NONE,      /* 不完整 trace */
  LJ_TRLINK_ROOT,      /* 链接到其他根 trace */
  LJ_TRLINK_LOOP,      /* 循环到自身 */
  LJ_TRLINK_TAILREC,   /* 尾递归 */
  LJ_TRLINK_UPREC,     /* 上递归 */
  LJ_TRLINK_DOWNREC,   /* 下递归 */
  LJ_TRLINK_INTERP,    /* 回退到解释器 */
  LJ_TRLINK_RETURN,    /* 返回到解释器 */
  LJ_TRLINK_STITCH     /* Trace stitching */
} TraceLink;
```

### 11.7.5 GCtrace 对象

编译完成的 trace 存储为 `GCtrace` 对象：

```c
typedef struct GCtrace {
  GCHeader;
  uint16_t nsnap;       /* 快照数量 */
  IRRef nins;           /* 下一条 IR 指令（偏移 REF_BIAS） */
  GCRef gclist;
  IRIns *ir;            /* IR 指令/常量数组 */
  IRRef nk;             /* 最低 IR 常量 */
  uint32_t nsnapmap;    /* 快照映射元素数 */
  SnapShot *snap;       /* 快照数组 */
  SnapEntry *snapmap;   /* 快照映射 */
  GCRef startpt;        /* 起始原型 */
  MRef startpc;         /* 起始字节码 PC */
  BCIns startins;       /* 起始位置的原始字节码 */
  MSize szmcode;        /* 机器码大小 */
  MCode *mcode;         /* 机器码起始地址 */
  MSize mcloop;         /* 循环起始在机器码中的偏移 */
  uint16_t nchild;      /* 子 trace 数量 */
  uint16_t spadjust;    /* 栈指针调整（字节） */
  TraceNo1 traceno;     /* Trace 编号 */
  TraceNo1 link;        /* 链接的 trace */
  TraceNo1 root;        /* Side trace 的根 trace */
  TraceNo1 nextroot;    /* 同一原型的下一个根 trace */
  TraceNo1 nextside;    /* 同一根 trace 的下一个 side trace */
  uint8_t linktype;     /* 链接类型 */
} GCtrace;
```

### 11.7.6 Trace 编译错误

Trace 编译可能因多种原因失败（abort）。错误消息定义在 `lj_traceerr.h` 中：

```c
/* 录制错误 */
TREDEF(RECERR,  "error thrown or hook called during recording")
TREDEF(TRACEUV, "trace too short")
TREDEF(TRACEOV, "trace too long")
TREDEF(STACKOV, "trace too deep")
TREDEF(SNAPOV,  "too many snapshots")
TREDEF(BLACKL,  "blacklisted")
TREDEF(NYIBC,   "NYI: bytecode %s")

/* 循环错误 */
TREDEF(LLEAVE,  "leaving loop in root trace")
TREDEF(LINNER,  "inner loop in root trace")
TREDEF(LUNROLL, "loop unroll limit reached")

/* 调用/返回错误 */
TREDEF(BADTYPE, "bad argument type")
TREDEF(CUNROLL, "call unroll limit reached")
TREDEF(DOWNREC, "down-recursion, restarting")

/* 汇编错误 */
TREDEF(MCODEAL, "failed to allocate mcode memory")
TREDEF(MCODEOV, "machine code too long")
TREDEF(SPILLOV, "too many spill slots")
```

频繁失败的 trace 起点会被加入 **惩罚缓存**（Penalty Cache），降低其热计数器初始值，避免反复尝试编译：

```c
typedef struct HotPenalty {
  MRef pc;        /* 起始字节码 PC */
  uint16_t val;   /* 惩罚值（热计数器起始值） */
  uint16_t reason; /* 中止原因 */
} HotPenalty;

#define PENALTY_SLOTS  64
#define PENALTY_MIN    (36*2)
#define PENALTY_MAX    60000
```

---

## 11.8 LuaJIT 的对象模型

### 11.8.1 TValue 与 NaN Tagging

LuaJIT 使用 IEEE 754 双精度浮点数的 NaN 载荷位来存储 Lua 值的类型标签和数据。这是 LuaJIT 性能的关键技术之一——所有 Lua 值都可以用一个 64 位的 `TValue` 表示，无需堆分配。

**非 GC64 模式（32 位 GC 引用）**：

```
                  ---MSW---.---LSW---
 原始类型         |  itype  |         |
 轻量 userdata    |  itype  |  void*  |  (32位平台)
 GC 对象          |  itype  |  GCRef  |
 整数 (DUALNUM)   |  itype  |   int   |
 数字              -------double------
```

**GC64 模式（64 位 GC 引用）**：

```
                  ------MSW------.------LSW------
 原始类型         |1..1|itype|1..................1|
 GC 对象          |1..1|itype|-------GCRef--------|
 轻量 userdata    |1..1|itype|seg|------ofs-------|
 整数 (DUALNUM)   |1..1|itype|0..0|-----int-------|
 数字              ------------double-------------
```

关键宏：

```c
/* 类型检查 */
#define tvisnil(o)     (itype(o) == LJ_TNIL)
#define tvisfalse(o)   (itype(o) == LJ_TFALSE)
#define tvistrue(o)    (itype(o) == LJ_TTRUE)
#define tvisstr(o)     (itype(o) == LJ_TSTR)
#define tvisfunc(o)    (itype(o) == LJ_TFUNC)
#define tvistab(o)     (itype(o) == LJ_TTAB)
#define tvisnum(o)     (itype(o) <= LJ_TISNUM)
#define tvisint(o)     (LJ_DUALNUM && itype(o) == LJ_TISNUM)

/* 值提取 */
#define strV(o)        (strref((o)->gcr))
#define tabV(o)        (tabref((o)->gcr))
#define funcV(o)       (gco2func((o)->gcr))
#define numV(o)        ((o)->n)
#define intV(o)        ((o)->i)
```

### 11.8.2 GC 对象层次

```
                    GCobj (联合体)
                       │
          ┌────────────┼────────────┐
          │            │            │
       GCstr        GCfunc       GCtab
     (字符串)       (函数)        (表)
          │            │
          │     ┌──────┴──────┐
          │  GCfuncC      GCfuncL
          │  (C函数)      (Lua函数)
          │
       GCupval        GCproto         GCudata
       (上值)        (原型/字节码)     (用户数据)
                          │
                       GCcdata
                     (C 数据，FFI)
```

### 11.8.3 Table 实现

LuaJIT 的表使用 **混合实现**：一部分是连续数组（array part），一部分是开放寻址哈希表（hash part）。

```
GCtab
  ├── array ──▶ [0] [1] [2] ... [asize-1]   (数组部分)
  │
  └── node  ──▶ Node[0] Node[1] ... Node[hmask]  (哈希部分)
                  │
                  ├── val (值)
                  ├── key (键)
                  └── next (哈希链)
```

哈希函数使用精心调优的旋转哈希：

```c
static LJ_AINLINE uint32_t hashrot(uint32_t lo, uint32_t hi)
{
  lo ^= hi; hi = lj_rol(hi, 14);
  lo -= hi; hi = lj_rol(hi, 5);
  hi ^= lo; hi -= lj_rol(lo, 13);
  return hi;
}
```

**数组共置（Array Colocation）**：小表的数组部分可以直接嵌入 `GCtab` 结构体后面，避免额外的内存分配。`colo` 字段记录共置的大小（正值）或需要的额外分配（负值）。

### 11.8.4 字符串 Interning

所有 Lua 字符串在创建时都被 **内部化**（interned）——相同的字符串内容只存储一份。字符串哈希表使用链式哈希，支持动态调整大小。

```c
typedef struct StrInternState {
  GCRef *tab;        /* 字符串哈希表锚点 */
  MSize mask;        /* 哈希掩码（表大小 - 1） */
  MSize num;         /* 表中字符串数量 */
  StrID id;          /* 下一个字符串 ID */
  uint8_t second;    /* 是否使用二次哈希 */
  LJ_ALIGN(8) uint64_t seed;  /* 随机字符串种子 */
} StrInternState;
```

字符串 ID（`sid`）是单调递增的唯一标识符，可用于快速比较——两个字符串相等当且仅当它们的 `sid` 相等。

### 11.8.5 上值（Upvalue）

上值是闭包捕获的外部局部变量的引用。开放上值（指向栈槽）通过双向链表维护：

```c
typedef struct GCupval {
  GCHeader;
  uint8_t closed;     /* 是否已关闭 */
  uint8_t immutable;  /* 是否不可变 */
  union {
    TValue tv;        /* 关闭时：值本身 */
    struct {          /* 开放时：双向链表 */
      GCRef prev;
      GCRef next;
    };
  };
  MRef v;             /* 指向栈槽（开放）或上方（关闭） */
  uint32_t dhash;     /* 消歧哈希 */
} GCupval;
```

---

## 11.9 LuaJIT 的垃圾回收

### 11.9.1 GC 总体设计

LuaJIT 使用 **增量三色标记-清除** 垃圾回收器。这是一个非分代、非压缩的 GC，通过增量执行来减少暂停时间。

### 11.9.2 GC 状态机

```
         ┌──────────────────────────────────────────┐
         │                                          │
         ▼                                          │
    ┌─────────┐    ┌─────────────┐    ┌──────────┐  │
    │ GCSpause │───▶│GCSpropagate │───▶│ GCSatomic│  │
    │  暂停    │    │  增量传播   │    │  原子阶段│  │
    └─────────┘    └─────────────┘    └─────┬────┘  │
                                           │       │
                   ┌───────────────┐       │       │
                   │ GCSsweepstring│◀──────┘       │
                   │  清扫字符串   │                │
                   └───────┬───────┘                │
                           │                        │
                   ┌───────▼───────┐                │
                   │   GCSsweep    │                │
                   │  清扫对象     │                │
                   └───────┬───────┘                │
                           │                        │
                   ┌───────▼───────┐                │
                   │  GCSfinalize  │                │
                   │  终结器       │────────────────┘
                   └───────────────┘
```

### 11.9.3 三色标记

GC 对象使用 `marked` 字段中的 2 位来表示颜色：

```c
#define LJ_GC_WHITE0  0x01   /* 白色 0 */
#define LJ_GC_WHITE1  0x02   /* 白色 1 */
#define LJ_GC_BLACK   0x04   /* 黑色 */

/* 灰色 = 非白非黑 */
#define iswhite(x)  ((x)->gch.marked & LJ_GC_WHITES)
#define isblack(x)  ((x)->gch.marked & LJ_GC_BLACK)
#define isgray(x)   (!((x)->gch.marked & (LJ_GC_BLACK|LJ_GC_WHITES)))
```

颜色含义：
- **白色**：未被标记的对象，是回收候选。使用两个白色位在 GC 周期之间交替
- **灰色**：已被标记但子对象尚未扫描的对象
- **黑色**：已被标记且子对象也已扫描的对象

### 11.9.4 写屏障（Write Barrier）

增量 GC 的正确性依赖于 **强三色不变式**：黑色对象永远不直接指向白色对象。写屏障在每次存储 GC 引用时检查并维护这个不变式。

```c
/* 向后屏障：将黑色表变回灰色 */
static LJ_AINLINE void lj_gc_barrierback(global_State *g, GCtab *t)
{
  GCobj *o = obj2gco(t);
  black2gray(o);
  setgcrefr(t->gclist, g->gc.grayagain);
  setgcref(g->gc.grayagain, o);
}
```

在 `lj_obj.h` 的注释中，Mike Pall 详细说明了可以省略写屏障的特殊情况：
- 源不是 GC 对象（NULL）
- 目标是 GC 根
- 目标是 `lua_State` 字段（线程永远不是黑色）
- 目标是栈槽
- 目标是开放上值
- 目标是新创建的对象（白色）
- 目标和源是同一个对象（自引用）

### 11.9.5 GC 参数

```c
#define GCSTEPSIZE     1024u    /* 每步的内存增量 */
#define GCSWEEPMAX     40       /* 每步最多清扫的对象数 */
#define GCSWEEPCOST    10       /* 清扫一个对象的代价 */
#define GCFINALIZECOST 100      /* 终结一个对象的代价 */
```

GC 驱动：

```c
#define lj_gc_check(L) \
  { if (LJ_UNLIKELY(G(L)->gc.total >= G(L)->gc.threshold)) \
      lj_gc_step(L); }
```

### 11.9.6 GC 状态

```c
typedef struct GCState {
  GCSize total;         /* 当前已分配内存 */
  GCSize threshold;     /* GC 触发阈值 */
  uint8_t currentwhite; /* 当前白色颜色 */
  uint8_t state;        /* GC 状态 */
  MSize sweepstr;       /* 字符串表中的清扫位置 */
  GCRef root;           /* 所有可收集对象的链表 */
  MRef sweep;           /* 根链表中的清扫位置 */
  GCRef gray;           /* 灰色对象链表 */
  GCRef grayagain;      /* 原子遍历的对象链表 */
  GCRef weak;           /* 弱引用表链表 */
  GCRef mmudata;        /* 待终结的用户数据链表 */
  GCSize debt;          /* GC 欠债 */
  GCSize estimate;      /* 实际使用内存的估计值 */
  MSize stepmul;        /* 增量 GC 步进粒度 */
  MSize pause;          /* 连续 GC 周期之间的暂停 */
} GCState;
```

### 11.9.7 死键处理

LuaJIT 的 GC 有一个独特的设计决策：**不特别标记表中的死键**。当一个键对应的值被设为 nil 时，键引用被留在表中但保证不会被解引用。这有助于：

1. 保持键哈希槽位稳定
2. 避免 `HREFK` 的特化回退
3. 允许安全地将 `HREF`/`HREFK` 跨 GC 步骤提升

代价是写屏障必须同时考虑键和值。

---

## 11.10 关键源代码片段分析

### 11.10.1 GC 标记函数（lj_gc.c）

```c
/* 标记一个白色 GCobj。 */
static void gc_mark(global_State *g, GCobj *o)
{
  int gct = o->gch.gct;
  lj_assertG(iswhite(o), "mark of non-white object");
  lj_assertG(!isdead(g, o), "mark of dead object");
  white2gray(o);  /* 白色 -> 灰色 */
  if (LJ_UNLIKELY(gct == ~LJ_TUDATA)) {
    /* 用户数据：直接变黑，标记元表和环境 */
    GCtab *mt = tabref(gco2ud(o)->metatable);
    gray2black(o);
    if (mt) gc_markobj(g, mt);
    gc_markobj(g, tabref(gco2ud(o)->env));
  } else if (LJ_UNLIKELY(gct == ~LJ_TUPVAL)) {
    /* 上值：标记值，关闭的上值直接变黑 */
    GCupval *uv = gco2uv(o);
    gc_marktv(g, uvval(uv));
    if (uv->closed) gray2black(o);
  } else if (gct != ~LJ_TSTR && gct != ~LJ_TCDATA) {
    /* 其他复杂对象：加入灰色链表，稍后遍历 */
    setgcrefr(o->gch.gclist, g->gc.gray);
    setgcref(g->gc.gray, o);
  }
}
```

这段代码展示了 GC 标记的核心逻辑：
- 用户数据和关闭的上值直接变黑（叶子节点或简单结构）
- 字符串和 C 数据不需要进一步遍历（直接变为灰色后完成）
- 其他对象（表、函数、线程、原型、trace）加入灰色链表等待遍历

### 11.10.2 DCE 优化（lj_opt_dce.c）

```c
/* 反向传播标记。将未使用的指令替换为 NOP。 */
static void dce_propagate(jit_State *J)
{
  IRRef1 *pchain[IR__MAX];
  IRRef ins;
  uint32_t i;
  for (i = 0; i < IR__MAX; i++) pchain[i] = &J->chain[i];
  for (ins = J->cur.nins-1; ins >= REF_FIRST; ins--) {
    IRIns *ir = IR(ins);
    if (irt_ismarked(ir->t)) {
      irt_clearmark(ir->t);  /* 有标记：清除标记，保留指令 */
    } else if (!ir_sideeff(ir)) {
      /* 无标记且无副作用：删除指令 */
      *pchain[ir->o] = ir->prev;  /* 重新路由指令链 */
      lj_ir_nop(ir);               /* 替换为 NOP */
      continue;
    }
    pchain[ir->o] = &ir->prev;
    /* 传播标记到操作数 */
    if (ir->op1 >= REF_FIRST) irt_setmark(IR(ir->op1)->t);
    if (ir->op2 >= REF_FIRST) irt_setmark(IR(ir->op2)->t);
  }
}
```

关键设计：
- 从最后一条指令向前扫描（反向）
- 有标记的指令保留（它是活跃的）
- 无标记但有副作用的指令也保留（如存储、守卫）
- 无标记无副作用的指令被删除
- 保留指令的传播标记到其操作数

### 11.10.3 FOLD 引擎入口（lj_opt_fold.c）

```c
/* FOLD 引擎如何处理指令的简要说明：
**
** FOLD 引擎接收存储在 fins (J->fold.ins) 中的单条指令。
** 指令及其操作数用于选择匹配的折叠规则。
** 这些规则被迭代应用，直到达到不动点。
**
** 指令的 8 位操作码加上其两个操作数引用的指令的操作码
** 形成 24 位键 'ins left right'
** （未使用的操作数 -> 0, 字面量 -> 最低 8 位）。
**
** 此键用于与折叠规则进行部分匹配。操作数字段
** 从最具体到最不具体依次用 'any' 通配符掩码：
**
**   ins left right   （最具体）
**   ins any  right
**   ins left any
**   ins any  any     （最不具体）
**
** 掩码后的键在半完美哈希表中查找匹配的折叠规则。*/
```

### 11.10.4 字节码比较指令的编码技巧（lj_bc.h）

```c
/* 确保比较指令的编码满足位操作约束 */
LJ_STATIC_ASSERT((int)BC_ISEQV+1 == (int)BC_ISNEV);
LJ_STATIC_ASSERT(((int)BC_ISEQV^1) == (int)BC_ISNEV);
LJ_STATIC_ASSERT(((int)BC_ISLT^1) == (int)BC_ISGE);
LJ_STATIC_ASSERT(((int)BC_ISLE^1) == (int)BC_ISGT);
LJ_STATIC_ASSERT(((int)BC_ISLT^3) == (int)BC_ISGT);
```

这些静态断言确保：
- `EQ` 和 `NE` 相差 1（可以用 `^1` 互换）
- `LT` 和 `GE` 相差 1
- `LE` 和 `GT` 相差 1
- `LT` 和 `GT` 相差 3

这使得 VM 可以用简单的位操作来实现条件分支的取反和转换。

### 11.10.5 循环优化的注释（lj_opt_loop.c）

```c
/* 循环优化：
**
** 传统的循环不变代码外提（LICM）将指令分为不变和变体指令。
** 不变指令被提升到循环外，只有变体指令留在循环体内。
**
** 不幸的是，LICM 对于编译动态语言基本无用。
** IR 有许多 guard，大多数后续指令都依赖于它们。
** 第一个不可提升的 guard 会有效地阻止所有后续指令的提升。
**
** 所以我们使用一种特殊的 copy-substitution 展开形式，
** 结合冗余消除：
**
** 录制的指令流被重新发射到编译管线，带有替换操作数。
** 替换表被填充为重新发射每条指令返回的引用。
** 这可以在线完成，因为 IR 是严格的 SSA 形式，
** 每个引用都在使用之前定义。
**
** 这种方法生成两个代码段，由 LOOP 指令分隔：
**
** 1. 录制的指令形成循环的一种预热。它包含不变和变体指令的混合，
**    并执行恰好一次循环迭代（但不一定是第 1 次迭代）。
**
** 2. 循环体只包含变体指令，执行一次迭代。*/
```

### 11.10.6 窄化优化的注释（lj_opt_narrow.c）

```c
/* 窄化优化的理由：
**
** Lua 只有一种数字类型，默认是 FP 双精度。
** 对于当前一代 x86/x64 机器上的解释器，将双精度窄化为整数并不划算。
** 大多数 FP 操作需要与整数对应操作相同的执行资源，
** 只是延迟略长。对于解释器来说，较长的延迟不是问题，
** 因为它们通常被其他开销所隐藏。
**
** 总 CPU 执行带宽是 FP 和整数单元带宽之和，
** 因为它们并行执行。不使用它们意味着失去执行带宽。
** 将工作从它们转移到已经相当繁忙的整数单元是一个亏本的买卖。
**
** JIT 编译代码的情况有所不同：更高的代码密度使额外的延迟更加明显。
** 紧密循环暴露了更新归纳变量的延迟。数组索引需要
** 高延迟的窄化转换和额外的 guard。许多常见优化只对整数有效。
**
** 一种解决方案是投机性的、急切的窄化所有数字加载。
** 这会导致许多问题，如丢失 -0 或需要解决 trace 之间的类型不匹配。
** 它还有效地强制整数类型具有溢出检查语义。
** 这阻碍了许多基本优化，并需要为所有整数算术操作添加溢出检查。*/
```

这段注释展示了 LuaJIT 设计中的工程权衡——窄化不是简单的"整数更快"，而是一个需要仔细考虑正确性、性能和复杂性的综合决策。

---

## 附录 A：LuaJIT JIT 编译器参数

```
参数名          默认值    说明
──────────────────────────────────────────────────
maxtrace        1000    trace 缓存中的最大 trace 数
maxrecord       4000    一条 trace 的最大 IR 指令数
maxirconst      500     一条 trace 的最大 IR 常量数
maxside         100     一个根 trace 的最大 side trace 数
maxsnap         500     一条 trace 的最大快照数
minstitch       0       缝合 trace 的最小 IR 指令数

hotloop         56      检测热点循环/调用的迭代次数
hotexit         10      开始 side trace 的退出次数
tryside         4       编译 side trace 的尝试次数

instunroll      4       不稳定循环的最大展开
loopunroll      15      side trace 中循环操作的最大展开
callunroll      3       递归调用的最大展开
recunroll       2       真递归的最小展开

sizemcode       64      每个机器码区域的大小（KB）
maxmcode        2048    所有机器码区域的最大总大小（KB）
```

优化级别：
- `-O0`：无优化
- `-O1`：FOLD + CSE + DCE
- `-O2`：O1 + NARROW + LOOP
- `-O3`（默认）：O2 + FWD + DSE + ABC + SINK + FUSE
- FMA 默认不启用

---

## 附录 B：推荐的源代码阅读顺序

1. **入门**：`lj_obj.h` — 理解 TValue、GC 对象的基本概念
2. **前端**：`lj_lex.h` → `lj_parse.c` — 理解源代码如何变成字节码
3. **字节码**：`lj_bc.h` — 理解指令格式和完整指令集
4. **对象模型**：`lj_tab.h`、`lj_func.h`、`lj_str.h` — 理解核心数据结构
5. **GC**：`lj_gc.h` → `lj_gc.c` — 理解内存管理
6. **JIT 概念**：`lj_jit.h` — 理解 JIT 编译器的状态和参数
7. **IR**：`lj_ir.h` → `lj_ir.c` — 理解中间表示
8. **录制**：`lj_record.h` → `lj_record.c` — 理解 trace 录制
9. **优化**：`lj_opt_dce.c` → `lj_opt_fold.c` → `lj_opt_loop.c` — 理解优化 passes
10. **汇编**：`lj_asm.h` → `lj_asm.c` — 理解机器码生成
11. **VM**：`lj_vm.h` → `vm_x64.dasc` — 理解解释器执行

---

## 附录 C：文件大小参考

| 文件 | 行数 | 复杂度 |
|------|------|--------|
| `lj_parse.c` | 2736 | 高（单遍编译器） |
| `lj_opt_fold.c` | 2656 | 高（优化规则表） |
| `lj_asm.c` | 2644 | 高（寄存器分配+代码生成） |
| `lj_record.c` | 2941 | 高（trace 录制） |
| `lj_obj.h` | 1090 | 中（核心类型定义） |
| `lj_snap.c` | 1035 | 中（快照处理） |
| `lj_gc.c` | 908 | 中（垃圾回收） |
| `lj_opt_mem.c` | 993 | 中（内存优化） |
| `lj_opt_loop.c` | 454 | 中（循环优化） |
| `lj_ir.h` | 516 | 中（IR 定义） |
| `lj_jit.h` | 394 | 中（JIT 状态） |
| `lj_bc.h` | 279 | 低（字节码定义） |
| `lj_dispatch.h` | 147 | 低（分派表） |
| `lj_gc.h` | 148 | 低（GC 接口） |

---

> **总结**：LuaJIT 是一个工程杰作，用约 3 万行 C 代码实现了一个完整的语言运行时——包括词法分析器、语法分析器、字节码编译器、寄存器虚拟机、追踪 JIT 编译器（含 SSA IR、多种优化 pass、多平台汇编器）、增量垃圾回收器和 FFI 系统。它的设计哲学是"简单但正确"，每个组件都经过精心优化以实现极致性能。
