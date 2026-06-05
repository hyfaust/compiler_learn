# LuaJIT 源码文件速查表

> 本文档列出 `luajit/src/` 目录下每个文件的功能，标注关键文件和入口点，并建议源码阅读顺序。

---

## 目录

- [核心头文件与定义](#核心头文件与定义)
- [前端：词法分析与语法分析](#前端词法分析与语法分析)
- [字节码系统](#字节码系统)
- [虚拟机与解释器](#虚拟机与解释器)
- [JIT 编译器核心](#jit-编译器核心)
- [IR 与优化](#ir-与优化)
- [代码生成后端](#代码生成后端)
- [垃圾回收器](#垃圾回收器)
- [FFI 系统](#ffi-系统)
- [运行时核心](#运行时核心)
- [标准库](#标准库)
- [构建系统与辅助工具](#构建系统与辅助工具)
- [建议的源码阅读顺序](#建议的源码阅读顺序)

---

## 核心头文件与定义

这些文件定义了 LuaJIT 的核心数据结构、类型和常量。是理解其他所有模块的基础。

| 文件 | 重要性 | 功能说明 |
|------|--------|----------|
| **`lj_obj.h`** | ★★★★★ | **最核心的头文件**。定义了 TValue（NaN Tagging）、GCobj、GCstr、GCtab、GCfunc、GCproto、GCupval、lua_State、global_State 等所有核心数据结构。类型标签（LJ_TNIL, LJ_TSTR 等）、TValue 操作宏、GC 颜色宏等。**必须首先阅读。** |
| **`lj_bc.h`** | ★★★★★ | **字节码定义**。通过 `BCDEF` 宏一次性定义所有约 80 条字节码指令。定义了指令格式（ABC/AD）、操作数提取宏（bc_op, bc_a, bc_d 等）、操作数模式（BCMode）。 |
| **`lj_ir.h`** | ★★★★★ | **IR 定义**。通过 `IRDEF` 宏定义所有 SSA IR 操作码。定义了 IR 指令格式（64位）、IR 类型系统（IRTDEF）、引用系统（REF_BIAS 等）、操作数模式标志。 |
| `lj_def.h` | ★★★☆☆ | 基础类型定义（uint8_t 等的别名）、编译器属性宏（LJ_AINLINE, LJ_NORET 等）、平台相关的基础定义。 |
| `lj_arch.h` | ★★★☆☆ | 架构检测宏（LJ_TARGET_X86, LJ_TARGET_ARM64 等）、平台特性宏（LJ_64, LJ_GC64, LJ_HASJIT, LJ_HASFFI 等）。构建时决定哪些代码被编译。 |
| `lj_ff.h` | ★★☆☆☆ | Fast function ID 定义。将标准库函数映射为数字 ID，用于 dispatch 和录制。 |
| `lj_frame.h` | ★★☆☆☆ | 栈帧布局定义。不同架构和模式下的帧结构、帧类型和大小的编码方式。 |
| `lj_jit.h` | ★★★★☆ | **JIT 编译器状态定义**。jit_State 结构体（JIT 的"全局状态"）、GCtrace 结构体（编译后的 trace）、SnapShot/SnapEntry、优化标志位（JIT_F_OPT_*）、trace 状态枚举。 |
| `lj_errmsg.h` | ★☆☆☆☆ | 错误消息字符串表。所有错误消息的枚举和字符串定义。 |
| `lj_traceerr.h` | ★★☆☆☆ | Trace 编译错误消息。定义了 trace 中止的所有原因（TREDEF 宏）。 |

---

## 前端：词法分析与语法分析

将 Lua 源代码编译为字节码。LuaJIT 的前端是**单遍编译器**——不构建 AST，直接在语法分析时生成字节码。

| 文件 | 重要性 | 功能说明 |
|------|--------|----------|
| **`lj_lex.c`** | ★★★☆☆ | **词法分析器**。将源代码文本转换为 token 流。支持 Lua 5.1 的所有关键字和符号。通过 `TKDEF` 宏定义 token 类型。核心函数：`lj_lex_setup()`, `lj_lex_next()`, `lj_lex_lookahead()`。 |
| `lj_lex.h` | ★★☆☆☆ | 词法分析器接口。定义 LexState 结构体（词法分析器状态）。 |
| **`lj_parse.c`** | ★★★★☆ | **语法分析器和字节码生成器**（约 2700 行）。这是前端的核心，包含递归下降解析器和字节码发射器。定义了表达式类型（ExpKind）、函数状态（FuncState）。核心入口：`lj_parse()`。 |
| `lj_parse.h` | ★☆☆☆☆ | 语法分析器接口声明。 |
| `lj_char.c` | ★☆☆☆☆ | 字符分类表。用于词法分析器的字符类型判断（字母、数字、空白等）。 |
| `lj_char.h` | ★☆☆☆☆ | 字符分类接口。 |

---

## 字节码系统

字节码的序列化、反序列化和辅助信息。

| 文件 | 重要性 | 功能说明 |
|------|--------|----------|
| `lj_bc.c` | ★★☆☆☆ | 字节码模式表。包含生成的 `lj_bc_mode[]`（每条字节码的操作数模式）和 `lj_bc_ofs[]`（偏移表）。 |
| `lj_bcdump.h` | ★★☆☆☆ | 字节码 dump 格式定义。BCDUMP 文件的头部标志、版本号、标志位。 |
| `lj_bcwrite.c` | ★★★☆☆ | **字节码写入器**。将 GCproto 序列化为 BCDUMP 格式。使用堆排序保证输出确定性。用于 `string.dump()` 和 `luajit -b`。 |
| `lj_bcread.c` | ★★★☆☆ | **字节码读取器**。加载和验证预编译的字节码文件。处理字节序交换、版本校验、GC64 迁移等。用于 `loadfile()` 和 `require`。 |

---

## 虚拟机与解释器

LuaJIT 的解释器用汇编语言（通过 DynASM 宏汇编器）编写，这是其高性能的关键之一。

| 文件 | 重要性 | 功能说明 |
|------|--------|----------|
| **`vm_x64.dasc`** | ★★★★★ | **x86-64 汇编解释器**（约 10000+ 行 DynASM）。包含：dispatch loop、所有字节码的执行代码、trace 入口/退出、元方法桩、C 函数调用/返回。**x86-64 平台的核心文件。** |
| `vm_x86.dasc` | ★★★★★ | x86（32位）汇编解释器。结构与 x64 类似，但使用 32 位寄存器和调用约定。 |
| `vm_arm.dasc` | ★★★★☆ | ARM（32位）汇编解释器。 |
| `vm_arm64.dasc` | ★★★★☆ | ARM64 (AArch64) 汇编解释器。 |
| `vm_mips.dasc` | ★★★☆☆ | MIPS（32位）汇编解释器。 |
| `vm_mips64.dasc` | ★★★☆☆ | MIPS64 汇编解释器。 |
| `vm_ppc.dasc` | ★★★☆☆ | PowerPC 汇编解释器。 |
| **`lj_vm.h`** | ★★★★☆ | **VM 入口点声明**。声明了所有 vm_*.dasc 中实现的汇编函数（lj_vm_call, lj_vm_pcall, lj_vm_resume, lj_vm_exit_handler 等）。 |
| **`lj_dispatch.c`** | ★★★★☆ | **指令分发管理**。初始化 dispatch 表、管理热计数器、处理录制模式下的指令拦截。核心函数：`lj_dispatch_init()`, `lj_dispatch_call()`, `lj_dispatch_ins()`。 |
| **`lj_dispatch.h`** | ★★★★☆ | **分发和 GG_State 定义**。GG_State 将 lua_State + global_State + jit_State + hotcount + dispatch 表连续分配在一起。定义了 hotcount 宏和 GG 各字段的偏移宏。 |
| `lj_vmmath.c` | ★☆☆☆☆ | VM 数学函数辅助。为没有原生数学指令的平台提供软件实现。 |

---

## JIT 编译器核心

Trace 录制、trace 管理和快照系统。

| 文件 | 重要性 | 功能说明 |
|------|--------|----------|
| **`lj_trace.c`** | ★★★★★ | **Trace 管理**（约 800 行）。管理 trace 的完整生命周期：热点检测（`lj_trace_hot()`）、编译调度、trace 分配/释放、trace 链接、惩罚缓存。状态机驱动编译流程。 |
| `lj_trace.h` | ★★★☆☆ | Trace 管理 API 声明。 |
| **`lj_record.c`** | ★★★★★ | **Trace 录制器**（约 2700 行）。JIT 编译器的第一阶段，将字节码逐条"录制"为 SSA IR。边录制边执行以获取运行时类型信息。核心函数：`lj_record_ins()`（每条字节码的录制逻辑）、`lj_record_call()`、`lj_record_ret()`、`lj_record_idx()`。 |
| `lj_record.h` | ★★☆☆☆ | 录制器 API 声明。定义 RecordIndex 结构体（表索引操作的上下文）。 |
| **`lj_ffrecord.c`** | ★★★★☆ | **Fast function 录制器**（约 2800 行）。为内置函数（math.*, string.*, table.*, bit.* 等）提供专用的 IR 生成代码。每个内置函数有对应的 `recff_*` 录制处理函数。 |
| `lj_ffrecord.h` | ★★☆☆☆ | Fast function 录制器声明。 |
| **`lj_snap.c`** | ★★★★☆ | **快照管理**（约 600 行）。管理 trace 的快照（snapshot）——每个 guard 点的栈状态记录。用于 side exit 时恢复解释器状态。核心函数：`lj_snap_add()`, `lj_snap_restore()`。 |
| `lj_snap.h` | ★★☆☆☆ | 快照相关定义。SnapShot 和 SnapEntry 结构体。 |

---

## IR 与优化

SSA IR 的管理和优化 pass。

| 文件 | 重要性 | 功能说明 |
|------|--------|----------|
| `lj_ir.c` | ★★★☆☆ | IR 分配和引用管理。IR 缓冲区的初始化、扩展、指令分配。 |
| **`lj_ir.h`** | ★★★★★ | **IR 指令格式和类型定义**。IRDEF（操作码）、IRTDEF（类型）、IRFLDEF（字段ID）、IRFPMDEF（浮点数学子函数）、IRMDEF（操作数模式）。IRIns 联合体（64位指令格式）。 |
| `lj_ircall.h` | ★★★☆☆ | IR 可调用的运行时函数表。定义了 IR_CALLN/CALLA/CALLL/CALLS 可以调用的 C 函数及其参数类型。 |
| `lj_iropt.h` | ★★☆☆☆ | 优化相关 IR 宏。定义了 FOLD pass 的特殊返回值（NEXTFOLD, RETRYFOLD, INTFOLD, LEFTFOLD 等）和优化辅助函数。 |
| **`lj_opt_fold.c`** | ★★★★★ | **FOLD pass**（约 2700 行）。最复杂的优化文件。实现：常量折叠、代数简化、CSE（公共子表达式消除）。使用 24 位模式匹配键（操作码 + 左操作码 + 右操作码）。FOLD 引擎在每条 IR 发射时在线运行。 |
| **`lj_opt_dce.c`** | ★★★★☆ | **死代码消除**。标记快照引用的 IR 指令，反向传播标记，无标记且无副作用的指令被替换为 NOP。 |
| `lj_opt_mem.c` | ★★★★☆ | **内存访问优化**。包含别名分析（AA）、Load 转发（FWD）、死 Store 消除（DSE）。利用 Lua 对象类型的语义进行精确别名分析。 |
| `lj_opt_loop.c` | ★★★★☆ | **循环优化**。使用 copy-substitution 展开（而非传统 LICM）。生成 pre-roll（预热）和 loop body（循环体）两个代码段。 |
| `lj_opt_narrow.c` | ★★★☆☆ | **数值窄化**。将双精度浮点运算窄化为整数运算。保守策略——仅在确认安全时窄化。 |
| `lj_opt_sink.c` | ★★★☆☆ | **分配下沉**。将循环中创建但不逃逸的对象分配延迟到 side exit 路径。 |
| `lj_opt_split.c` | ★★☆☆☆ | **64位指令分裂**。仅在软浮点目标或 32位 CPU + FFI 场景下激活。将 64 位 IR 指令拆分为 32 位指令。 |

---

## 代码生成后端

从 SSA IR 生成目标平台的机器码。

| 文件 | 重要性 | 功能说明 |
|------|--------|----------|
| **`lj_asm.c`** | ★★★★★ | **通用汇编器**（约 1700 行）。寄存器分配（线性扫描）、溢出处理、指令调度、trace 主入口 `lj_asm_trace()`。驱动整个代码生成流程。 |
| `lj_asm.h` | ★★★☆☆ | 汇编器接口。定义 ASMState 结构体（寄存器状态、机器码指针等）。 |
| **`lj_asm_x86.h`** | ★★★★☆ | **x86/x64 代码生成**（约 4000+ 行）。所有 IR 操作码到 x86 机器码的转换。包含 `asm_intarith()`, `asm_fparith()`, `asm_href()`, `asm_sload()` 等。 |
| `lj_asm_arm.h` | ★★★☆☆ | ARM 代码生成。 |
| `lj_asm_arm64.h` | ★★★☆☆ | ARM64 代码生成。 |
| `lj_asm_mips.h` | ★★★☆☆ | MIPS 代码生成。 |
| `lj_asm_ppc.h` | ★★★☆☆ | PowerPC 代码生成。 |
| **`lj_emit_x86.h`** | ★★★★☆ | **x86/x64 指令编码**。REX 前缀、ModR/M、SIB 字节的编码。提供 `emit_movrm()`, `emit_loadi()`, `emit_call()`, `emit_jmp()` 等编码函数。 |
| `lj_emit_arm.h` | ★★★☆☆ | ARM 指令编码。 |
| `lj_emit_arm64.h` | ★★★☆☆ | ARM64 指令编码。 |
| `lj_emit_mips.h` | ★★★☆☆ | MIPS 指令编码。 |
| `lj_emit_ppc.h` | ★★★☆☆ | PowerPC 指令编码。 |
| `lj_target.h` | ★★☆☆☆ | 目标架构选择头文件。根据平台宏包含对应的 lj_target_*.h。 |
| `lj_target_x86.h` | ★★★☆☆ | x86/x64 寄存器定义（RID_EAX 等）、条件码、调用约定、栈帧布局。 |
| `lj_target_arm.h` | ★★★☆☆ | ARM 寄存器定义。 |
| `lj_target_arm64.h` | ★★★☆☆ | ARM64 寄存器定义。 |
| `lj_target_mips.h` | ★★☆☆☆ | MIPS 寄存器定义。 |
| `lj_target_ppc.h` | ★★☆☆☆ | PowerPC 寄存器定义。 |
| **`lj_mcode.c`** | ★★★☆☆ | **机器码内存管理**。使用 mmap（Linux/Mac）或 VirtualAlloc（Windows）分配可执行内存。管理 mcode 区域的分配、释放和刷新。 |
| `lj_mcode.h` | ★★☆☆☆ | 机器码内存管理接口。 |
| `lj_gdbjit.c` | ★★☆☆☆ | GDB JIT 编译接口。通过 `__jit_debug_register_code` 向 GDB 注册 JIT 生成的代码，支持调试 JIT 代码。 |
| `lj_gdbjit.h` | ★☆☆☆☆ | GDB JIT 接口声明。 |

---

## 垃圾回收器

增量式三色标记-清除 GC。

| 文件 | 重要性 | 功能说明 |
|------|--------|----------|
| **`lj_gc.c`** | ★★★★★ | **GC 实现**（约 1500 行）。增量式标记-清除 GC 的完整实现。状态机：GCSpause → GCSpropagate → GCSatomic → GCSsweepstring → GCSsweep → GCSfinalize。写屏障、终结器、字符串清扫。核心函数：`lj_gc_step()`, `lj_gc_fullgc()`, `lj_gc_barrierf()`。 |
| **`lj_gc.h`** | ★★★★☆ | **GC 接口和写屏障宏**。GC 颜色位定义（WHITE0, WHITE1, BLACK）、颜色测试/设置宏、写屏障宏（lj_gc_barriert, lj_gc_anybarriert 等）。GC 状态结构体定义。 |
| `lj_alloc.c` | ★★☆☆☆ | 内存分配器。基于 dlmalloc 的自定义分配器，使用 mmap 分配大块内存。 |
| `lj_alloc.h` | ★☆☆☆☆ | 分配器接口。 |

---

## FFI 系统

LuaJIT 的 FFI 允许 Lua 代码直接调用 C 函数和操作 C 数据类型。

| 文件 | 重要性 | 功能说明 |
|------|--------|----------|
| **`lj_ctype.c`** | ★★★★☆ | **C 类型系统管理**。C 类型 ID 的分配和查找、类型信息的存储和检索、类型名称解析。 |
| `lj_ctype.h` | ★★★☆☆ | C 类型定义。CType 结构体、类型类别枚举（CT_ARRAY, CT_STRUCT, CT_PTR, CT_FUNC 等）。 |
| `lj_cparse.c` | ★★★☆☆ | **C 声明解析器**。解析 C 类型声明（如 `struct { int x; double y; }`），生成类型信息。 |
| `lj_cparse.h` | ★☆☆☆☆ | C 解析器接口。 |
| `lj_cdata.c` | ★★★☆☆ | C 数据对象管理。GCcdata 的创建、初始化、终结。 |
| `lj_cdata.h` | ★★☆☆☆ | C 数据对象定义。GCcdata 和 GCcdataVar 结构体。 |
| **`lj_ccall.c`** | ★★★★★ | **C 函数调用**（约 2000 行）。FFI 最复杂的部分。实现各平台的调用约定：x86 cdecl/stdcall、x64 System V/Microsoft、ARM AAPCS 等。参数传递、返回值处理、栈对齐。 |
| `lj_ccall.h` | ★★☆☆☆ | C 调用接口。CTState 结构体。 |
| `lj_ccallback.c` | ★★★☆☆ | **C 回调**。将 Lua 函数作为 C 回调使用。运行时生成 trampoline 机器码。 |
| `lj_ccallback.h` | ★★☆☆☆ | 回调接口。 |
| `lj_cconv.c` | ★★★☆☆ | **C 类型转换**。Lua 值与 C 类型之间的转换（number→int, string→char* 等）。 |
| `lj_cconv.h` | ★★☆☆☆ | 转换接口。 |
| `lj_crecord.c` | ★★★☆☆ | **FFI 操作的 trace 录制**。为 FFI 的类型转换、指针操作、结构体访问等生成 IR。 |
| `lj_crecord.h` | ★★☆☆☆ | FFI 录制接口。 |
| `lj_clib.c` | ★★☆☆☆ | 动态库加载。封装 dlopen/dlsym（Unix）和 LoadLibrary/GetProcAddress（Windows）。 |
| `lj_clib.h` | ★★☆☆☆ | 动态库接口。 |
| `lj_carith.c` | ★★☆☆☆ | C 算术运算。FFI 数值类型的算术操作（64 位整数运算等）。 |
| `lj_carith.h` | ★☆☆☆☆ | C 算术接口。 |

---

## 运行时核心

Lua 运行时的核心功能：API、表、字符串、函数、错误处理等。

| 文件 | 重要性 | 功能说明 |
|------|--------|----------|
| **`lj_api.c`** | ★★★★☆ | **Lua C API 实现**（约 1300 行）。实现 `lua_push*`, `lua_to*`, `lua_get*`, `lua_set*`, `lua_call`, `lua_pcall` 等标准 C API 函数。 |
| **`lj_tab.c`** | ★★★★☆ | **表实现**（约 800 行）。数组+哈希表的混合实现。哈希函数（hashrot）、表查找/插入/删除、表重哈希、数组共置（colocation）。核心函数：`lj_tab_new()`, `lj_tab_get()`, `lj_tab_set()`, `lj_tab_next()`, `lj_tab_len()`。 |
| `lj_tab.h` | ★★★☆☆ | 表操作接口。Node 结构体（哈希节点）。 |
| **`lj_str.c`** | ★★★★☆ | **字符串实现**。字符串驻留（interning）、哈希计算、字符串创建和释放。核心函数：`lj_str_new()`, `lj_str_init()`, `lj_str_resize()`。 |
| `lj_str.h` | ★★☆☆☆ | 字符串接口。 |
| **`lj_func.c`** | ★★★☆☆ | **函数/闭包管理**。原型（GCproto）、Lua 闭包（GCfuncL）、C 闭包（GCfuncC）、上值（GCupval）的创建和释放。 |
| `lj_func.h` | ★★☆☆☆ | 函数对象定义和接口。 |
| **`lj_meta.c`** | ★★★★☆ | **元方法实现**（约 700 行）。当操作数类型不匹配时的元方法分发：算术（__add, __sub 等）、比较（__lt, __le, __eq）、索引（__index, __newindex）、长度（__len）、连接（__concat）、调用（__call）。 |
| `lj_meta.h` | ★★☆☆☆ | 元方法接口。MMS 枚举（元方法 ID）。 |
| **`lj_state.c`** | ★★★☆☆ | **线程/协程状态管理**。lua_State 的创建、初始化、栈增长、协程 resume/yield。 |
| `lj_state.h` | ★★☆☆☆ | 状态定义。 |
| `lj_buf.c` | ★★★☆☆ | 可增长字符串缓冲区。SBuf 的操作：追加字符串、数字格式化、缓冲区扩展。 |
| `lj_buf.h` | ★★☆☆☆ | 缓冲区接口。SBuf 和 SBufExt 结构体。 |
| `lj_strfmt.c` | ★★☆☆☆ | 字符串格式化。`format()` 函数的实现。 |
| `lj_strfmt_num.c` | ★★☆☆☆ | 数字到字符串的快速格式化。双精度浮点数到十进制字符串的高效转换。 |
| `lj_strfmt.h` | ★☆☆☆☆ | 字符串格式化接口。 |
| `lj_strscan.c` | ★★☆☆☆ | 字符串到数字扫描器。`tonumber()` 的高效实现。 |
| `lj_strscan.h` | ★☆☆☆☆ | 字符串扫描接口。 |
| `lj_debug.c` | ★★☆☆☆ | 调试信息。行号查询、变量名查询、调用栈回溯。 |
| `lj_debug.h` | ★☆☆☆☆ | 调试接口。 |
| **`lj_err.c`** | ★★★☆☆ | **错误处理和异常**。错误抛出（`lj_err_throw()`）、错误消息格式化、栈回溯显示。使用 C 异常（setjmp/longjmp）或 C++ 异常实现。 |
| `lj_err.h` | ★★☆☆☆ | 错误处理接口。 |
| `lj_load.c` | ★★☆☆☆ | 加载器。实现 `luaL_loadfile()`, `luaL_loadstring()`, `lua_load()`。 |
| `lj_obj.c` | ★☆☆☆☆ | 对象辅助函数。 |
| `lj_assert.c` | ★★☆☆☆ | 断言实现。LuaJIT 的内部一致性检查（lj_assertX 等）。 |
| `lj_udata.c` | ★☆☆☆☆ | userdata 对象管理。 |
| `lj_vmevent.c` | ★☆☆☆☆ | VM 事件系统。GC 开始/结束等事件的回调通知。 |
| `lj_vmevent.h` | ★☆☆☆☆ | VM 事件接口。 |
| `lj_profile.c` | ★★☆☆☆ | 采样 profiler。通过定时信号（SIGPROF/ITIMER）采样 VM 状态。 |
| `lj_profile.h` | ★☆☆☆☆ | Profiler 接口。 |
| `lj_prng.c` | ★☆☆☆☆ | 伪随机数生成器。用于字符串哈希种子和安全随机数。 |
| `lj_prng.h` | ★☆☆☆☆ | PRNG 接口。 |
| `lj_serialize.c` | ★☆☆☆☆ | 序列化/反序列化。将 Lua 值序列化为紧凑的二进制格式。 |
| `lj_serialize.h` | ★☆☆☆☆ | 序列化接口。 |

---

## 标准库

Lua 标准库的实现。每个 `lib_*.c` 文件实现一个库。

| 文件 | 重要性 | 功能说明 |
|------|--------|----------|
| `lib_init.c` | ★★★☆☆ | **标准库初始化入口**。`luaL_openlibs()` 的实现，注册所有标准库。 |
| `lib_base.c` | ★★★☆☆ | **base 库**。`print`, `type`, `tostring`, `tonumber`, `pcall`, `xpcall`, `error`, `assert`, `require`, `select`, `rawget`, `rawset`, `rawequal`, `rawlen`, `setmetatable`, `getmetatable`, `collectgarbage`, `dofile`, `loadfile`, `load`, `next`, `pairs`, `ipairs`。 |
| `lib_math.c` | ★★★☆☆ | **math 库**。`math.abs`, `math.floor`, `math.ceil`, `math.sqrt`, `math.sin`, `math.cos`, `math.log`, `math.exp`, `math.random`, `math.min`, `math.max` 等。 |
| `lib_string.c` | ★★★☆☆ | **string 库**。`string.len`, `string.sub`, `string.byte`, `string.char`, `string.format`, `string.find`, `string.match`, `string.gsub`, `string.rep`, `string.reverse`, `string.lower`, `string.upper` 等。 |
| `lib_table.c` | ★★★☆☆ | **table 库**。`table.insert`, `table.remove`, `table.sort`, `table.concat`, `table.new`, `table.clear` 等。 |
| `lib_io.c` | ★★☆☆☆ | **io 库**。文件 I/O 操作。 |
| `lib_os.c` | ★★☆☆☆ | **os 库**。系统调用（os.time, os.execute 等）。 |
| `lib_debug.c` | ★★☆☆☆ | **debug 库**。调试接口（debug.getinfo, debug.getlocal 等）。 |
| `lib_bit.c` | ★★★☆☆ | **bit 库**。位操作（bit.bor, bit.band, bit.bxor, bit.lshift, bit.rshift, bit.bnot 等）。 |
| **`lib_jit.c`** | ★★★★☆ | **jit 库**。JIT 控制接口：`jit.on/off`, `jit.flush`, `jit.status`, `jit.opt.start`, `jit.bc.dump`, `jit.util.*` 等。 |
| `lib_ffi.c` | ★★★☆☆ | **ffi 库**。FFI 接口：`ffi.new`, `ffi.cast`, `ffi.cdef`, `ffi.load`, `ffi.typeof`, `ffi.sizeof` 等。 |
| `lib_buffer.c` | ★★☆☆☆ | **buffer 库**。字符串缓冲区操作。 |
| `lib_package.c` | ★★☆☆☆ | **package 库**。模块加载系统（`require` 的实现）。 |
| `lib_aux.c` | ★★☆☆☆ | 辅助库函数。`luaL_*` 系列函数的实现。 |
| `lj_lib.c` | ★★☆☆☆ | 库函数框架。内置库的注册和分发机制。 |
| `lj_lib.h` | ★★☆☆☆ | 库函数宏和框架定义。 |

---

## 构建系统与辅助工具

| 文件 | 重要性 | 功能说明 |
|------|--------|----------|
| `luajit.c` | ★★★☆☆ | **命令行入口**（`main()`）。处理命令行参数、执行文件、交互式 REPL。`-jv`, `-jdump`, `-joff` 等参数的处理。 |
| `ljamalg.c` | ★☆☆☆☆ | Amalgamation 编译。将所有 .c 文件 `#include` 到一个文件中，加速编译。 |
| `lua.h` | ★★★☆☆ | Lua C API 头文件（标准）。定义 `lua_push*`, `lua_to*` 等 API 函数原型。 |
| `luaconf.h` | ★★☆☆☆ | Lua 配置头文件。可配置的编译选项。 |
| `lualib.h` | ★★☆☆☆ | 标准库头文件。`luaopen_*` 函数声明。 |
| `lauxlib.h` | ★★☆☆☆ | 辅助库头文件。`luaL_*` 函数声明。 |
| `lua.hpp` | ★☆☆☆☆ | C++ 兼容包装器。 |
| `luajit_rolling.h` | ★☆☆☆☆ | 滚动版本号定义。 |
| `msvcbuild.bat` | ★★☆☆☆ | Windows MSVC 构建脚本。 |
| `xb1build.bat` | ★☆☆☆☆ | Xbox One 构建脚本。 |
| `ps4build.bat` | ★☆☆☆☆ | PS4 构建脚本。 |
| `ps5build.bat` | ★☆☆☆☆ | PS5 构建脚本。 |
| `psvitabuild.bat` | ★☆☆☆☆ | PS Vita 构建脚本。 |
| `nxbuild.bat` | ★☆☆☆☆ | Nintendo Switch 构建脚本。 |
| `xedkbuild.bat` | ★☆☆☆☆ | Xbox 开发工具包构建脚本。 |

---

## src/jit/ — JIT 辅助模块（Lua 实现）

| 文件 | 重要性 | 功能说明 |
|------|--------|----------|
| `bc.lua` | ★★★☆☆ | 字节码定义和辅助函数。字节码名称表、操作码常量。 |
| `bcsave.lua` | ★★☆☆☆ | 字节码保存/反汇编。`luajit -b` 命令的实现。 |
| `dump.lua` | ★★★☆☆ | **Trace dump 工具**。`-jdump` 命令的实现。输出 trace 的字节码、IR、快照和汇编。 |
| `v.lua` | ★★☆☆☆ | Verbose 输出。`-jv` 命令的实现。 |
| `p.lua` | ★☆☆☆☆ | 精简的 Lua 代码美化打印。 |
| `zone.lua` | ★★☆☆☆ | 内存 zone 分配器。用于 JIT 编译器的临时内存分配。 |
| `dis_x86.lua` | ★★☆☆☆ | x86 反汇编器。将机器码反汇编为助记符。 |
| `dis_x64.lua` | ★★☆☆☆ | x64 反汇编器。 |
| `dis_arm.lua` | ★★☆☆☆ | ARM 反汇编器。 |
| `dis_arm64.lua` | ★★☆☆☆ | ARM64 反汇编器。 |
| `dis_arm64be.lua` | ★☆☆☆☆ | ARM64 大端序反汇编器。 |
| `dis_mips.lua` | ★☆☆☆☆ | MIPS 反汇编器。 |
| `dis_mipsel.lua` | ★☆☆☆☆ | MIPS 小端序反汇编器。 |
| `dis_mips64.lua` | ★☆☆☆☆ | MIPS64 反汇编器。 |
| `dis_mips64el.lua` | ★☆☆☆☆ | MIPS64 小端序反汇编器。 |
| `dis_mips64r6.lua` | ★☆☆☆☆ | MIPS64 R6 反汇编器。 |
| `dis_mips64r6el.lua` | ★☆☆☆☆ | MIPS64 R6 小端序反汇编器。 |
| `dis_ppc.lua` | ★☆☆☆☆ | PowerPC 反汇编器。 |

---

## src/host/ — 构建工具

| 文件 | 重要性 | 功能说明 |
|------|--------|----------|
| `buildvm.c` | ★★☆☆☆ | **buildvm 主程序**。构建时使用的代码生成工具，处理 DynASM 模板生成 C/汇编代码。 |
| `buildvm.h` | ★☆☆☆☆ | buildvm 头文件。 |
| `buildvm_asm.c` | ★★☆☆☆ | 生成 VM 汇编代码。 |
| `buildvm_fold.c` | ★★☆☆☆ | 生成 FOLD 优化的哈希表。将 lj_opt_fold.c 中的折叠规则编译为查找表。 |
| `buildvm_lib.c` | ★★☆☆☆ | 生成内置库的字节码。 |
| `buildvm_libbc.h` | ★☆☆☆☆ | 内置库字节码头。 |
| `buildvm_peobj.c` | ★☆☆☆☆ | 生成 PE/COFF 目标文件（Windows）。 |
| `minilua.c` | ★★☆☆☆ | **精简 Lua 解释器**。构建时使用的最小 Lua 实现，用于运行 DynASM 预处理器。 |
| `genlibbc.lua` | ★☆☆☆☆ | 生成内置库字节码的脚本。 |
| `genminilua.lua` | ★☆☆☆☆ | 生成 minilua 的脚本。 |
| `genversion.lua` | ★☆☆☆☆ | 生成版本号的脚本。 |

---

## 建议的源码阅读顺序

以下阅读顺序按从外到内、从简单到复杂的路径设计。每个阶段标注了预计时间和核心文件。

### 阶段 1：数据结构基础（1-2 天）

**目标**：理解 LuaJIT 的核心数据结构和值表示。

1. **`lj_obj.h`** — 最核心的头文件，必须首先阅读
   - TValue（NaN Tagging）
   - GCobj 公共头
   - GCstr, GCtab, GCfunc, GCproto
   - lua_State, global_State
   - 类型标签（LJ_TNIL 等）
2. **`lj_def.h`** — 基础类型定义
3. **`lj_arch.h`** — 平台检测宏

### 阶段 2：字节码系统（1 天）

**目标**：理解 LuaJIT 的字节码指令格式和编码。

1. **`lj_bc.h`** — 字节码定义（BCDEF 宏）
   - 指令格式（ABC/AD）
   - 所有操作码及其操作数模式
2. `lj_bc.c` — 模式表
3. `lj_lex.h` + `lj_lex.c` — 词法分析器概览
4. `lj_parse.c` — 语法分析器概览（重点关注字节码发射部分）

### 阶段 3：虚拟机执行（2-3 天）

**目标**：理解字节码如何被执行，热点如何被检测。

1. **`lj_dispatch.h`** — GG_State 和 dispatch 表
2. **`lj_dispatch.c`** — 分发管理、热计数器
3. **`lj_vm.h`** — VM 入口点声明
4. **`vm_x64.dasc`**（或对应平台的 vm_*.dasc）
   - 从 dispatch loop 开始
   - 看几条字节码的实现（如 ADDVN, TGETS, FORL）
   - 理解 trace 入口/退出代码
5. `lj_meta.c` — 元方法分发（理解类型不匹配时的处理）

### 阶段 4：JIT 录制（2-3 天）

**目标**：理解 trace 编译的触发和录制过程。

1. **`lj_trace.c`** — trace 管理
   - `lj_trace_hot()` — 热点检测入口
   - `lj_trace_ins()` — 录制调度
   - trace 状态机
2. **`lj_record.c`** — trace 录制器
   - `lj_record_setup()` — 初始化
   - `lj_record_ins()` — 核心录制逻辑（逐条看字节码如何转为 IR）
3. `lj_ffrecord.c` — 内置函数录制（挑几个感兴趣的看）
4. `lj_snap.c` — 快照机制

### 阶段 5：IR 与优化（3-4 天）

**目标**：理解 SSA IR 和优化 pass。

1. **`lj_ir.h`** — IR 定义（IRDEF, IRTDEF, 引用系统）
2. `lj_ir.c` — IR 分配
3. **`lj_opt_fold.c`** — FOLD pass（最复杂的文件）
   - 理解模式匹配表
   - 看几个常量折叠和 CSE 的例子
4. `lj_opt_dce.c` — 死代码消除
5. `lj_opt_mem.c` — 内存优化（FWD, DSE）
6. `lj_opt_loop.c` — 循环优化
7. `lj_opt_narrow.c` — 数值窄化
8. `lj_opt_sink.c` — 分配下沉

### 阶段 6：代码生成（3-4 天）

**目标**：理解从 IR 到机器码的转换。

1. **`lj_asm.h`** — ASMState 定义
2. **`lj_asm.c`** — 通用汇编器
   - `lj_asm_trace()` — 主入口
   - 寄存器分配算法
3. **`lj_asm_x86.h`**（或对应架构）
   - 挑选几个代表性的 IR 操作码看其代码生成
4. **`lj_emit_x86.h`** — 指令编码
5. `lj_target_x86.h` — 寄存器和调用约定
6. `lj_mcode.c` — 机器码内存管理

### 阶段 7：运行时系统（2-3 天）

**目标**：理解 GC、FFI 和标准库。

1. **`lj_gc.c`** + **`lj_gc.h`** — 垃圾回收器
2. `lj_str.c` — 字符串驻留
3. `lj_tab.c` — 表实现
4. **`lj_ccall.c`** — FFI C 函数调用
5. `lj_ctype.c` — C 类型系统
6. `lj_api.c` — Lua C API
7. `lj_err.c` — 错误处理

### 阶段 8：深入专题（持续）

**目标**：深入理解特定子系统。

- DynASM：阅读 `dynasm/` 目录
- GDB JIT：阅读 `lj_gdbjit.c`
- Profiler：阅读 `lj_profile.c`
- 构建系统：阅读 `host/buildvm.c`

---

## 文件大小参考

以下是按代码行数排序的主要文件（近似值，供参考）：

| 排名 | 文件 | 约行数 | 说明 |
|------|------|--------|------|
| 1 | `vm_x64.dasc` | ~10000+ | x86-64 汇编解释器 |
| 2 | `lj_asm_x86.h` | ~4500 | x86/x64 代码生成 |
| 3 | `lj_record.c` | ~2700 | Trace 录制器 |
| 4 | `lj_parse.c` | ~2700 | 语法分析器 |
| 5 | `lj_opt_fold.c` | ~2700 | FOLD 优化 pass |
| 6 | `lj_ffrecord.c` | ~2800 | Fast function 录制 |
| 7 | `lj_asm.c` | ~1700 | 通用汇编器 |
| 8 | `lj_gc.c` | ~1500 | 垃圾回收器 |
| 9 | `lj_api.c` | ~1300 | Lua C API |
| 10 | `lj_ccall.c` | ~2000 | FFI C 调用 |
| 11 | `lj_emit_x86.h` | ~1200 | x86 指令编码 |
| 12 | `lj_tab.c` | ~800 | 表实现 |
| 13 | `lj_meta.c` | ~700 | 元方法 |
| 14 | `lj_snap.c` | ~600 | 快照管理 |
| 15 | `lj_obj.h` | ~1090 | 核心头文件 |
| 16 | `lj_ir.h` | ~850 | IR 定义 |
| 17 | `lj_bc.h` | ~230 | 字节码定义 |

> **总计**：核心 C 代码约 6 万行，加上 DynASM 模板和构建工具约 8 万行。
