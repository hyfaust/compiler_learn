# 第2章 编译器架构

## 2.1 编译器的总体架构

### 经典三阶段架构

现代编译器普遍采用**前端-中端-后端**三阶段架构。这种分离设计的核心思想是：将**源语言相关的分析**、**语言无关的优化**、**目标机器相关的代码生成**三者解耦，使得同一中端可服务于多种源语言和多种目标平台。

```
                    ┌─────────────────────────────────────────────────────┐
                    │                  编译器总体架构                       │
                    └─────────────────────────────────────────────────────┘

    源代码 (.c)                                                          目标代码 (.o / .exe)
        │                                                                     ▲
        ▼                                                                     │
   ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌──────────────┐
   │  词法    │     │  语法    │     │  语义    │     │  中间    │     │   目标代码   │
   │  分析    │────▶│  分析    │────▶│  分析    │────▶│  代码    │────▶│    生成      │
   │(Lexer)  │     │(Parser) │     │(Semantic)│     │  生成    │     │ (Code Gen)   │
   └─────────┘     └─────────┘     └─────────┘     └────┬────┘     └──────────────┘
        │                     │                          │                    │
        ▼                     ▼                          ▼                    ▼
    Token流              语法树(AST)               中间表示(IR)           汇编/机器码
                                                                │
                           ◀──── 前端(Fe) ────▶    ◀─ 中端(Opt) ─▶   ◀── 后端(Be) ──▶
                                                                │
                                                    ┌───────────┴───────────┐
                                                    │      优化遍(Passes)    │
                                                    │  常量折叠/死代码消除   │
                                                    │  公共子表达式消除      │
                                                    │  循环优化/内联展开     │
                                                    │  寄存器分配           │
                                                    └───────────────────────┘
```

### 各阶段职责

| 阶段 | 职责 | 输入 | 输出 |
|------|------|------|------|
| **词法分析 (Lexical Analysis)** | 将字符流分割为Token | 源代码字符流 | Token序列 |
| **语法分析 (Syntax Analysis)** | 根据文法规则构建语法树 | Token序列 | 抽象语法树(AST) |
| **语义分析 (Semantic Analysis)** | 类型检查、作用域分析、符号表管理 | AST | 带标注的AST |
| **中间代码生成** | 生成与语言/机器无关的IR | AST | IR(如三地址码/SSA) |
| **优化** | 对IR进行各种等价变换以提升性能 | IR | 优化后的IR |
| **代码生成** | 将IR翻译为目标机器代码 | 优化后IR | 汇编/机器码 |

### 多语言多目标的复用

```
         C前端 ──┐                    ┌── x86后端
                 ├──▶  共享中端/优化  ├── ARM后端
  Java前端 ─────┘    (GCC/LLVM IR)    ├── RISC-V后端
                                       └── WASM后端
```

以GCC为例：C、C++、Fortran、Go等语言各自拥有独立前端，但共享同一后端。以LLVM为例：各语言前端统一生成LLVM IR，由LLVM中端优化，再由不同后端生成目标代码。

---

## 2.2 GCC架构详解

GCC (GNU Compiler Collection) 是最广泛使用的开源编译器套件，支持C、C++、Fortran、Ada、Go、D等语言。

### 2.2.1 GCC的编译流水线

当执行 `gcc hello.c -o hello` 时，GCC实际上依次执行了四个子阶段：

```
  hello.c ──▶ 【预处理】──▶ hello.i ──▶【编译】──▶ hello.s ──▶【汇编】──▶ hello.o ──▶【链接】──▶ hello
              (cpp)                     (cc1)                 (as)                  (ld)
```

#### 阶段一：预处理 (Preprocessing)

由 `cpp` (C Preprocessor) 完成：
- 展开所有 `#include` 指令（递归插入头文件内容）
- 展开所有宏定义 (`#define`)
- 处理条件编译 (`#if`, `#ifdef`, `#ifndef`, `#else`, `#elif`, `#endif`)
- 删除注释（替换为空格）
- 处理 `#pragma`、`#line`、`#error` 等指令
- 保留行号信息（`#line` 标记）

```bash
gcc -E hello.c -o hello.i    # 仅执行预处理，输出到 hello.i
```

#### 阶段二：编译 (Compilation)

由 `cc1`（真正的编译器本体）完成，将预处理后的C源码翻译为汇编代码：
1. **词法分析**：字符流 → Token流
2. **语法分析**：Token流 → AST（在GCC中先转为GENERIC，再转为GIMPLE）
3. **语义分析**：类型检查、符号解析
4. **生成中间表示**：GIMPLE → 优化 → RTL
5. **优化**：在GIMPLE和RTL两级上执行数十个优化遍
6. **汇编代码生成**：RTL → 目标机器汇编

```bash
gcc -S hello.c -o hello.s    # 仅执行到编译阶段，输出汇编文件
```

#### 阶段三：汇编 (Assembly)

由 `as`（GNU汇编器）完成：
- 将汇编代码翻译为机器指令
- 生成ELF (Linux) 或 PE (Windows) 格式的目标文件(.o)
- 包含机器码、数据段、符号表、重定位信息

```bash
gcc -c hello.c -o hello.o    # 执行预处理+编译+汇编，输出目标文件
```

#### 阶段四：链接 (Linking)

由 `ld` (GNU Linker) 完成：
- 合并多个目标文件和库文件
- 符号解析：将未定义的符号引用关联到其定义
- 地址重定位：为代码和数据分配最终虚拟地址
- 生成可执行文件（ELF/PE格式）

```bash
gcc hello.o -o hello          # 仅执行链接
gcc hello.c -o hello          # 完整流程（预处理+编译+汇编+链接）
```

### 2.2.2 GCC的内部中间表示

GCC内部使用**四级**中间表示，逐级降低抽象层次：

```
  源代码
    │
    ▼
 ┌──────────────────────────────────────────────────────────────┐
 │  GENERIC                                                      │
 │  ── 源语言无关的树状表示                                      │
 │  ── 前端将AST转换为GENERIC                                   │
 │  ── 保留完整的程序结构信息                                    │
 └──────────────┬───────────────────────────────────────────────┘
                │  gimplify
                ▼
 ┌──────────────────────────────────────────────────────────────┐
 │  GIMPLE                                                        │
 │  ── 三地址码形式的SSA表示                                     │
 │  ── GCC主要的优化工作在此层级进行                              │
 │  ── 每条语句最多3个操作数，形式: a = b op c                    │
 │  ── SSA形式：每个变量只被赋值一次                              │
 │  ── 关键优化遍：                                              │
 │      * -O1: 死代码消除、常量折叠、CSE                          │
 │      * -O2: 循环优化、内联、别名分析                           │
 │      * -O3: 向量化、循环展开、更激进的内联                     │
 └──────────────┬───────────────────────────────────────────────┘
                │  expand
                ▼
 ┌──────────────────────────────────────────────────────────────┐
 │  RTL (Register Transfer Language)                              │
 │  ── 接近目标机器的低级表示                                     │
 │  ── 描述寄存器之间的数据传送和运算                             │
 │  ── 与目标机器的指令集紧密相关                                 │
 │  ── 寄存器分配、指令调度、窥孔优化在此进行                     │
 └──────────────┬───────────────────────────────────────────────┘
                │  final
                ▼
          目标汇编代码
```

#### GENERIC → GIMPLE 示例

C源码：
```c
int foo(int a, int b) {
    int c = a + b;
    if (c > 10) {
        return c * 2;
    }
    return c;
}
```

对应的GIMPLE（简化）：
```
foo (int a, int b)
{
  int c;
  int _1;
  int _2;

  _1 = a + b;          // 三地址码：结果 = 操作数1 + 操作数2
  c = _1;
  if (c > 10) goto <D.1234>; else goto <D.1235>;

  <D.1234>:
  _2 = c * 2;
  return _2;

  <D.1235>:
  return c;
}
```

#### RTL 示例

对应的RTL（x86-64，简化）：
```
(insn 5 3 6 2 (set (reg:SI 88 [ c ])
        (plus:SI (reg:SI 91 [ a ])
                 (reg:SI 92 [ b ]))) "demo.c":3 130 {addsi3}
     (nil))

(insn 9 8 10 3 (set (reg:CC 17 flags)
        (compare:CC (reg:SI 88 [ c ])
                    (const_int 10))) "demo.c":4 4 {*cmpsi_ccno_1}
     (nil))

(jump_insn 10 9 11 3 (set (pc)
        (if_then_else (gt (reg:CC 17 flags)
                          (const_int 0))
            (label_ref 14)
            (pc))) "demo.c":4 520 {*jcc}
     (nil))
```

### 2.2.3 GCC常用命令行选项

```bash
# ============ 编译阶段控制 ============
gcc -E file.c                # 仅预处理
gcc -S file.c                # 预处理 + 编译（输出汇编）
gcc -c file.c                # 预处理 + 编译 + 汇编（输出 .o）
gcc file.c -o file           # 完整流程

# ============ 优化级别 ============
gcc -O0 file.c               # 无优化（默认，调试用）
gcc -O1 file.c               # 基本优化
gcc -O2 file.c               # 推荐优化级别（生产环境）
gcc -O3 file.c               # 激进优化（可能增大代码体积）
gcc -Os file.c               # 优化代码体积
gcc -Ofast file.c            # 最激进（可能违反IEEE浮点标准）

# ============ 警告控制 ============
gcc -Wall file.c             # 开启常用警告
gcc -Wextra file.c           # 额外警告
gcc -Werror file.c           # 将警告视为错误
gcc -pedantic file.c         # 严格遵循ISO标准

# ============ 调试信息 ============
gcc -g file.c                # 生成DWARF调试信息
gcc -g3 file.c               # 生成最详细的调试信息（含宏）

# ============ 输出控制 ============
gcc -S -masm=intel file.c    # 输出Intel语法汇编（默认AT&T）
gcc -E file.c -o file.i      # 预处理结果输出到文件
gcc -save-temps file.c       # 保留所有中间文件（.i, .s, .o）

# ============ 查看内部表示 ============
gcc -fdump-tree-all file.c   # 转储所有GIMPLE树文件
gcc -fdump-rtl-all file.c    # 转储所有RTL文件
gcc -fdump-ipa-all file.c    # 转储所有过程间分析
gcc -fdump-tree-gimple file.c # 仅转储GIMPLE

# ============ 架构相关 ============
gcc -m32 file.c              # 生成32位代码
gcc -m64 file.c              # 生成64位代码
gcc -march=native file.c     # 针对当前CPU架构优化
gcc -march=x86-64-v3 file.c  # 针对特定微架构级别
```

---

## 2.3 MinGW架构详解

### 2.3.1 历史背景

**MinGW** (Minimalist GNU for Windows) 是一个将GCC移植到Windows平台的项目，使开发者可以在Windows上使用GNU工具链编译原生Windows程序。

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │                        MinGW 发展历史                                │
  ├─────────────────────────────────────────────────────────────────────┤
  │  1998年  Colin Peters 创建 MinGW32 项目                             │
  │  1999年  Mumit Khan 接手维护，开始系统化开发                        │
  │  2005年  MinGW.org 成为主要维护站点                                 │
  │  2009年  MinGW-w64 项目启动（支持64位和更多API）                    │
  │  2013年  MinGW.org 项目趋于停滞                                     │
  │  至今    MinGW-w64 成为事实标准，被MSYS2、Git for Windows等采用      │
  └─────────────────────────────────────────────────────────────────────┘
```

### 2.3.2 MinGW工具链架构

```
  源代码 (.c)                                                          Windows可执行文件 (.exe)
        │                                                                     ▲
        ▼                                                                     │
   ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌──────────────┐
   │  cpp     │     │  cc1    │     │  as      │     │  ld      │     │   PE格式      │
   │(预处理器)│────▶│(编译器) │────▶│(汇编器) │────▶│ (链接器) │────▶│  (PE/COFF)   │
   └─────────┘     └─────────┘     └─────────┘     └────┬────┘     └──────────────┘
                                                         │
                                                         │ 链接时额外处理：
                                                         │ • PE头生成
                                                         │ • 导入表构建
                                                         │ • DLL绑定
                                                         ▼
                                                    ┌──────────┐
                                                    │ Windows  │
                                                    │  系统库  │
                                                    │kernel32  │
                                                    │msvcrt    │
                                                    │ucrtbase  │
                                                    └──────────┘
```

#### MinGW的关键组件

| 组件 | 作用 |
|------|------|
| `gcc` / `g++` | C/C++编译器驱动 |
| `as` (GNU as) | 汇编器，生成COFF格式目标文件 |
| `ld` (GNU ld) | 链接器，生成PE格式可执行文件 |
| `ar` | 静态库打包工具（创建 .a 文件） |
| `windres` | Windows资源编译器（处理 .rc 文件） |
| `dlltool` | DLL导入库生成工具 |
| `mingw-w64-crt` | C运行时启动代码（crt0.o, crtbegin.o等） |
| `winpthreads` | POSIX线程库的Windows实现 |
| Windows头文件 | `windows.h`、`winnt.h` 等SDK头文件 |

### 2.3.3 Windows PE文件生成

MinGW链接器将目标文件转换为PE (Portable Executable) 格式：

```
  ┌──────────────────────────────────────────┐
  │              PE文件结构                    │
  ├──────────────────────────────────────────┤
  │  DOS Header (MZ签名)                      │
  │  DOS Stub ("This program cannot be run...")│
  │  PE Signature ("PE\0\0")                  │
  │  COFF File Header                         │
  │  Optional Header                          │
  │    ├─ Entry Point RVA                     │
  │    ├─ Image Base (默认 0x400000)          │
  │    ├─ Section Alignment                   │
  │    ├─ Import Directory Table              │
  │    └─ Export Directory Table (DLL)        │
  │  Section Headers                          │
  │    ├─ .text    (代码段)                   │
  │    ├─ .data    (已初始化数据)             │
  │    ├─ .rdata   (只读数据/导入表)          │
  │    ├─ .bss     (未初始化数据)             │
  │    ├─ .rsrc    (资源段)                   │
  │    └─ .reloc   (重定位表)                 │
  └──────────────────────────────────────────┘
```

### 2.3.4 MinGW vs MSVC 对比

```
  ┌──────────────────┬────────────────────────────┬────────────────────────────┐
  │     特性          │        MinGW-w64           │         MSVC               │
  ├──────────────────┼────────────────────────────┼────────────────────────────┤
  │ 编译器           │ GCC                        │ cl.exe                     │
  │ 链接器           │ GNU ld                     │ link.exe                   │
  │ C运行时          │ msvcrt.dll / ucrt          │ msvcrt140.dll (VC Runtime) │
  │ C++标准库        │ libstdc++                  │ MSVC STL                   │
  │ 静态库格式       │ .a (ar archive)            │ .lib (COFF archive)        │
  │ 调试信息格式     │ DWARF                      │ PDB                        │
  │ ABI              │ Itanium C++ ABI            │ Microsoft C++ ABI          │
  │ 默认异常处理     │ SJLJ / SEH / Dwarf SEH     │ SEH (结构化异常处理)       │
  │ 线程模型         │ posix / win32              │ 原生Win32线程              │
  │ 优化能力         │ 强（GCC优化框架）          │ 强（MSVC优化框架）         │
  │ SIMD支持         │ SSE/AVX通过-march控制      │ /arch:SSE2 /arch:AVX2等   │
  │ 包管理           │ MSYS2/pacman               │ vcpkg / NuGet              │
  │ 构建系统         │ Makefiles, CMake, Meson    │ MSBuild, CMake, Ninja      │
  │ 跨平台能力       │ 天然跨平台（同一工具链）    │ 主要用于Windows             │
  │ 与Linux库兼容性  │ 较好（POSIX兼容层）        │ 较差                       │
  └──────────────────┴────────────────────────────┴────────────────────────────┘
```

#### 编译同一文件的命令对比

```bash
# MinGW-w64 (GCC)
gcc -Wall -O2 -o hello.exe hello.c -lkernel32

# MSVC
cl.exe /W4 /O2 /Fe:hello.exe hello.c

# MinGW链接静态库
gcc -o app.exe main.o -L./lib -lmylib

# MSVC链接静态库
cl.exe /Fe:app.exe main.c /link /LIBPATH:./lib mylib.lib
```

---

## 2.4 编译器的关键数据结构

编译器在各个阶段使用不同的数据结构来表示和处理程序。理解这些数据结构是理解编译器工作原理的核心。

### 2.4.1 Token（词法单元）

Token是词法分析器的输出，是编译器处理的最小语法单位。每个Token包含**类型**和**值**。

```c
/* ============================================================
 * Token - 词法单元
 *
 * Token是词法分析的输出，每个Token代表源代码中的一个原子
 * 语法单位：关键字、标识符、字面量、运算符、分隔符等。
 * ============================================================ */

typedef enum {
    /* 字面量 */
    TOKEN_INT_LIT,         /* 整数字面量: 42, 0xFF, 0777 */
    TOKEN_FLOAT_LIT,       /* 浮点字面量: 3.14, 1e-5 */
    TOKEN_STRING_LIT,      /* 字符串字面量: "hello" */
    TOKEN_CHAR_LIT,        /* 字符字面量: 'a' */

    /* 标识符和关键字 */
    TOKEN_IDENTIFIER,      /* 标识符: foo, myVar */
    TOKEN_KEYWORD,         /* 关键字: if, while, return, int... */

    /* 运算符 */
    TOKEN_PLUS,            /* + */
    TOKEN_MINUS,           /* - */
    TOKEN_STAR,            /* * */
    TOKEN_SLASH,           /* / */
    TOKEN_PERCENT,         /* % */
    TOKEN_ASSIGN,          /* = */
    TOKEN_EQ,              /* == */
    TOKEN_NEQ,             /* != */
    TOKEN_LT,              /* < */
    TOKEN_GT,              /* > */
    TOKEN_LE,              /* <= */
    TOKEN_GE,              /* >= */
    TOKEN_AND,             /* && */
    TOKEN_OR,              /* || */
    TOKEN_NOT,             /* ! */
    TOKEN_BITAND,          /* & */
    TOKEN_BITOR,           /* | */
    TOKEN_BITXOR,          /* ^ */
    TOKEN_BITNOT,          /* ~ */
    TOKEN_LSHIFT,          /* << */
    TOKEN_RSHIFT,          /* >> */
    TOKEN_PLUS_ASSIGN,     /* += */
    TOKEN_MINUS_ASSIGN,    /* -= */
    TOKEN_STAR_ASSIGN,     /* *= */
    TOKEN_SLASH_ASSIGN,    /* /= */
    TOKEN_PLUS_PLUS,       /* ++ */
    TOKEN_MINUS_MINUS,     /* -- */
    TOKEN_ARROW,           /* -> */
    TOKEN_DOT,             /* . */

    /* 分隔符 */
    TOKEN_LPAREN,          /* ( */
    TOKEN_RPAREN,          /* ) */
    TOKEN_LBRACE,          /* { */
    TOKEN_RBRACE,          /* } */
    TOKEN_LBRACKET,        /* [ */
    TOKEN_RBRACKET,        /* ] */
    TOKEN_SEMICOLON,       /* ; */
    TOKEN_COMMA,           /* , */
    TOKEN_COLON,           /* : */
    TOKEN_QUESTION,        /* ? */

    /* 特殊 */
    TOKEN_EOF,             /* 文件结束 */
    TOKEN_ERROR,           /* 词法错误 */
} TokenKind;

typedef struct {
    TokenKind kind;        /* Token类型 */
    const char *start;     /* 指向源码中Token起始位置 */
    int length;            /* Token长度 */
    int line;              /* 所在行号 */
    int column;            /* 所在列号 */
    union {
        long int_value;    /* TOKEN_INT_LIT 的值 */
        double float_value;/* TOKEN_FLOAT_LIT 的值 */
        /* 字符串值通过 start/length 从源码中提取 */
    } value;
} Token;
```

### 2.4.2 AST（抽象语法树）

AST是语法分析器的输出，以树状结构表示程序的语法结构。与具体语法树(CST)不同，AST省略了括号、分号等语法糖，只保留语义相关的结构。

```c
/* ============================================================
 * AST - 抽象语法树
 *
 * AST以树状结构表示程序结构。每个节点代表一个语法构造
 * （表达式、语句、声明等），子节点代表其组成部分。
 * ============================================================ */

/* ---- 节点类型枚举 ---- */
typedef enum {
    /* 表达式节点 */
    NODE_INT_LITERAL,      /* 整数字面量 */
    NODE_FLOAT_LITERAL,    /* 浮点字面量 */
    NODE_STRING_LITERAL,   /* 字符串字面量 */
    NODE_IDENTIFIER,       /* 标识符引用 */
    NODE_BINARY_OP,        /* 二元运算: a + b */
    NODE_UNARY_OP,         /* 一元运算: -a, !b */
    NODE_ASSIGN,           /* 赋值: a = b */
    NODE_FUNC_CALL,        /* 函数调用: foo(a, b) */
    NODE_ARRAY_ACCESS,     /* 数组访问: arr[i] */
    NODE_MEMBER_ACCESS,    /* 成员访问: obj.field */
    NODE_TERNARY,          /* 三元表达式: a ? b : c */
    NODE_CAST,             /* 类型转换: (int)x */

    /* 语句节点 */
    NODE_COMPOUND,         /* 复合语句(代码块): { ... } */
    NODE_IF,               /* if语句 */
    NODE_WHILE,            /* while循环 */
    NODE_FOR,              /* for循环 */
    NODE_DO_WHILE,         /* do-while循环 */
    NODE_RETURN,           /* return语句 */
    NODE_BREAK,            /* break语句 */
    NODE_CONTINUE,         /* continue语句 */
    NODE_EXPR_STMT,        /* 表达式语句 */

    /* 声明节点 */
    NODE_VAR_DECL,         /* 变量声明 */
    NODE_FUNC_DECL,        /* 函数声明 */
    NODE_PARAM,            /* 函数参数 */
} NodeType;

/* ---- AST节点基类 ---- */
typedef struct ASTNode {
    NodeType type;               /* 节点类型 */
    int line;                    /* 源码行号（用于错误报告） */

    union {
        /* 整数字面量 */
        struct { long value; } int_lit;

        /* 浮点字面量 */
        struct { double value; } float_lit;

        /* 字符串字面量 */
        struct { char *value; } string_lit;

        /* 标识符 */
        struct { char *name; } identifier;

        /* 二元运算 */
        struct {
            int op;                    /* 运算符Token */
            struct ASTNode *left;      /* 左操作数 */
            struct ASTNode *right;     /* 右操作数 */
        } binary;

        /* 一元运算 */
        struct {
            int op;                    /* 运算符Token */
            struct ASTNode *operand;   /* 操作数 */
            int is_prefix;             /* 前缀(1)还是后缀(0) */
        } unary;

        /* 赋值 */
        struct {
            struct ASTNode *target;    /* 赋值目标 */
            struct ASTNode *value;     /* 赋值表达式 */
        } assign;

        /* 函数调用 */
        struct {
            char *name;                /* 函数名 */
            struct ASTNode **args;     /* 参数列表 */
            int arg_count;             /* 参数数量 */
        } func_call;

        /* if语句 */
        struct {
            struct ASTNode *condition; /* 条件表达式 */
            struct ASTNode *then_body; /* then分支 */
            struct ASTNode *else_body; /* else分支(可为NULL) */
        } if_stmt;

        /* while循环 */
        struct {
            struct ASTNode *condition; /* 循环条件 */
            struct ASTNode *body;      /* 循环体 */
        } while_stmt;

        /* for循环 */
        struct {
            struct ASTNode *init;      /* 初始化(可为NULL) */
            struct ASTNode *condition; /* 条件(可为NULL) */
            struct ASTNode *update;    /* 更新(可为NULL) */
            struct ASTNode *body;      /* 循环体 */
        } for_stmt;

        /* return语句 */
        struct {
            struct ASTNode *value;     /* 返回值(可为NULL) */
        } return_stmt;

        /* 复合语句(代码块) */
        struct {
            struct ASTNode **stmts;    /* 语句列表 */
            int stmt_count;            /* 语句数量 */
        } compound;

        /* 变量声明 */
        struct {
            char *type_name;           /* 类型名 */
            char *var_name;            /* 变量名 */
            struct ASTNode *init;      /* 初始化表达式(可为NULL) */
        } var_decl;

        /* 函数声明 */
        struct {
            char *return_type;         /* 返回类型 */
            char *func_name;           /* 函数名 */
            struct ASTNode **params;   /* 参数列表 */
            int param_count;           /* 参数数量 */
            struct ASTNode *body;      /* 函数体 */
        } func_decl;
    } as;
} ASTNode;
```

### 2.4.3 符号表 (Symbol Table)

符号表是编译器中最重要的数据结构之一，用于记录标识符（变量、函数、类型等）的声明信息。在语义分析阶段，符号表用于：
- 检查变量/函数是否已声明
- 进行类型检查
- 管理作用域（嵌套作用域通过链表实现）

```c
/* ============================================================
 * 符号表 - 基于哈希表 + 作用域链
 *
 * 符号表使用哈希表实现O(1)的查找，通过链表处理冲突。
 * 嵌套作用域通过作用域链实现：每次进入新作用域时压栈，
 * 退出时弹栈。查找时从当前作用域向全局作用域逐层搜索。
 * ============================================================ */

/* 符号类型 */
typedef enum {
    SYM_VARIABLE,          /* 变量 */
    SYM_FUNCTION,          /* 函数 */
    SYM_TYPE,              /* 类型定义 (typedef/struct/enum) */
    SYM_CONSTANT,          /* 常量 (enum常量、#define) */
    SYM_LABEL,             /* 标签 (goto目标) */
} SymbolKind;

/* 类型信息（简化版） */
typedef enum {
    TYPE_VOID, TYPE_INT, TYPE_FLOAT, TYPE_CHAR,
    TYPE_STRING, TYPE_ARRAY, TYPE_POINTER, TYPE_STRUCT,
} TypeKind;

typedef struct TypeInfo {
    TypeKind kind;
    int size;              /* 类型大小（字节） */
    struct TypeInfo *base; /* 数组/指针的基类型 */
    int array_len;         /* 数组长度（仅TYPE_ARRAY） */
    /* struct的字段信息可扩展 */
} TypeInfo;

/* 符号条目 */
typedef struct Symbol {
    char *name;            /* 符号名称 */
    SymbolKind kind;       /* 符号类型 */
    TypeInfo *type;        /* 类型信息 */
    int scope_level;       /* 所在作用域层级（0=全局） */
    int is_initialized;    /* 是否已初始化 */
    int is_used;           /* 是否被使用过（用于未使用变量警告） */
    int line_declared;     /* 声明所在行号 */
    /* 函数特有 */
    int param_count;       /* 参数数量（仅函数） */
    struct Symbol *next;   /* 哈希链表的下一个节点（冲突处理） */
} Symbol;

/* 作用域 */
typedef struct Scope {
    int level;                     /* 作用域层级 */
    struct Scope *parent;          /* 父作用域（作用域链） */
    /* 每个作用域有自己的哈希表 */
    Symbol **buckets;              /* 哈希桶数组 */
    int bucket_count;              /* 桶数量 */
} Scope;

/* 符号表（管理作用域栈） */
typedef struct SymbolTable {
    Scope *current;                /* 当前作用域 */
    int scope_depth;               /* 作用域深度 */
    /* 全局统计 */
    int total_symbols;             /* 符号总数 */
} SymbolTable;
```

### 2.4.4 IR：三地址码与SSA

中间表示(IR)是编译器中端的核心数据结构。**三地址码**是最基本的IR形式，每条指令最多包含三个地址（两个操作数和一个结果）。

```
三地址码指令的基本形式：

  x = y op z        二元运算: x = y + z
  x = op y          一元运算: x = -y
  x = y             赋值:     x = y
  goto L            无条件跳转
  if x goto L       条件跳转
  ifFalse x goto L  条件跳转
  param x           传递参数
  call p, n         调用函数p，n个参数
  return x          返回值
  x = y[i]          数组读取
  x[i] = y          数组写入
```

```c
/* ============================================================
 * IR - 三地址码
 *
 * 三地址码是一种线性IR，每条指令形式为:
 *   result = operand1 OP operand2
 * 便于进行数据流分析和各种优化遍。
 * ============================================================ */

typedef enum {
    /* 算术运算 */
    IR_ADD,              /* a = b + c */
    IR_SUB,              /* a = b - c */
    IR_MUL,              /* a = b * c */
    IR_DIV,              /* a = b / c */
    IR_MOD,              /* a = b % c */
    IR_NEG,              /* a = -b */

    /* 位运算 */
    IR_AND,              /* a = b & c */
    IR_OR,               /* a = b | c */
    IR_XOR,              /* a = b ^ c */
    IR_NOT,              /* a = ~b */
    IR_SHL,              /* a = b << c */
    IR_SHR,              /* a = b >> c */

    /* 比较运算 */
    IR_CMP_EQ,           /* a = (b == c) */
    IR_CMP_NE,           /* a = (b != c) */
    IR_CMP_LT,           /* a = (b < c) */
    IR_CMP_GT,           /* a = (b > c) */
    IR_CMP_LE,           /* a = (b <= c) */
    IR_CMP_GE,           /* a = (b >= c) */

    /* 赋值 */
    IR_MOVE,             /* a = b */
    IR_LOAD,             /* a = *b (从内存加载) */
    IR_STORE,            /* *a = b (存入内存) */
    IR_LOAD_ADDR,        /* a = &b (取地址) */

    /* 控制流 */
    IR_JUMP,             /* goto label */
    IR_BRANCH_TRUE,      /* if a goto label */
    IR_BRANCH_FALSE,     /* ifFalse a goto label */
    IR_LABEL,            /* label: (标签定义) */

    /* 函数调用 */
    IR_PARAM,            /* param a (传递参数) */
    IR_CALL,             /* a = call f, n (调用函数f, n个参数) */
    IR_RETURN,           /* return a */

    /* 类型转换 */
    IR_CAST,             /* a = (type)b */

    /* 数组/指针 */
    IR_ARRAY_LOAD,       /* a = b[c] (计算地址并加载) */
    IR_ARRAY_STORE,      /* a[b] = c (计算地址并存储) */

    /* Phi函数（SSA专用） */
    IR_PHI,              /* a = phi(b1, b2, ...) (SSA合并) */
} IROpcode;

/* IR操作数 */
typedef enum {
    OPD_NONE,            /* 空操作数 */
    OPD_TEMP,            /* 临时变量: t1, t2, ... */
    OPD_VAR,             /* 源程序变量: x, y, ... */
    OPD_CONST_INT,       /* 整数常量 */
    OPD_CONST_FLOAT,     /* 浮点常量 */
    OPD_LABEL,           /* 标签: L1, L2, ... */
    OPD_FUNC,            /* 函数名 */
} OperandKind;

typedef struct {
    OperandKind kind;
    union {
        int temp_id;     /* 临时变量编号 */
        char *var_name;  /* 变量名 */
        long int_val;    /* 整数常量值 */
        double float_val;/* 浮点常量值 */
        int label_id;    /* 标签编号 */
        char *func_name; /* 函数名 */
    } as;
} IROperand;

/* 一条IR指令 */
typedef struct IRInstr {
    IROpcode opcode;         /* 操作码 */
    IROperand result;        /* 结果操作数（左值） */
    IROperand op1;           /* 第一操作数 */
    IROperand op2;           /* 第二操作数 */

    /* SSA相关（仅在SSA形式下使用） */
    int *phi_args;           /* PHI函数参数的临时变量ID列表 */
    int phi_arg_count;       /* PHI参数数量 */

    struct IRInstr *next;    /* 链表指向下一条指令 */
    int line_number;         /* 对应源码行号（调试用） */
} IRInstr;

/* 一个基本块 */
typedef struct BasicBlock {
    int id;                  /* 基本块编号 */
    IRInstr *first;          /* 第一条指令 */
    IRInstr *last;           /* 最后一条指令 */

    /* CFG信息 */
    struct BasicBlock **preds;   /* 前驱基本块列表 */
    int pred_count;
    struct BasicBlock **succs;   /* 后继基本块列表 */
    int succ_count;
} BasicBlock;
```

#### 三地址码示例

C代码：
```c
int factorial(int n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}
```

对应的三地址码：
```
factorial:
  t1 = n <= 1
  ifFalse t1 goto L1
  return 1
L1:
  t2 = n - 1
  param t2
  t3 = call factorial, 1
  t4 = n * t3
  return t4
```

#### SSA（静态单赋值）形式

SSA是三地址码的一种变体，要求**每个变量只被赋值一次**。当控制流汇合时，使用 **φ(phi)函数** 来选择来自不同路径的值。

C代码：
```c
int x = 1;
if (cond) {
    x = 2;
}
use(x);
```

SSA形式：
```
x1 = 1
if cond goto L1 else goto L2
L1:
  x2 = 2
  goto L3
L2:
  goto L3
L3:
  x3 = phi(x1, x2)    // 根据控制流选择x1或x2
  use(x3)
```

### 2.4.5 CFG（控制流图）

控制流图是将程序表示为**基本块**和**边**的有向图。基本块是顺序执行的最大指令序列（只有一个入口和一个出口）。边表示可能的控制转移。

```c
/* ============================================================
 * CFG - 控制流图
 *
 * CFG将程序表示为基本块(BasicBlock)的有向图。
 * - 基本块: 顺序执行的最大指令序列，无分支入/出
 * - 边: 表示可能的控制转移（条件/无条件跳转、顺序执行）
 * - 用于数据流分析、活跃变量分析、寄存器分配等优化
 * ============================================================ */

/* CFG边的类型 */
typedef enum {
    EDGE_NORMAL,             /* 顺序执行（fall-through） */
    EDGE_TRUE,               /* 条件为真分支 */
    EDGE_FALSE,              /* 条件为假分支 */
    EDGE_UNCOND,             /* 无条件跳转 */
    EDGE_CALL,               /* 函数调用边 */
    EDGE_RETURN,             /* 函数返回边 */
    EDGE_EXCEPTION,          /* 异常边 */
} EdgeKind;

/* CFG边 */
typedef struct CFGEdge {
    BasicBlock *from;        /* 源基本块 */
    BasicBlock *to;          /* 目标基本块 */
    EdgeKind kind;           /* 边类型 */
    struct CFGEdge *next_out;/* from的下一条出边（链表） */
    struct CFGEdge *next_in; /* to的下一条入边（链表） */
} CFGEdge;

/* 控制流图 */
typedef struct CFG {
    BasicBlock *entry;       /* 入口基本块 */
    BasicBlock *exit;        /* 出口基本块 */
    BasicBlock **blocks;     /* 所有基本块数组 */
    int block_count;         /* 基本块数量 */
    CFGEdge **edges;         /* 所有边数组 */
    int edge_count;          /* 边的数量 */
} CFG;
```

#### CFG示例

```
C代码:                         对应的CFG:

int abs(int x) {               ┌──────────────┐
    if (x >= 0) {              │   BB0: entry  │
        return x;              │   t1 = x >= 0│
    } else {                   │   if t1 → BB1 │
        return -x;             │         else  │
    }                          │         → BB2 │
}                              └──────┬───┬────┘
                                      │   │
                             true     │   │  false
                                      ▼   ▼
                          ┌────────────┐ ┌────────────┐
                          │  BB1       │ │  BB2       │
                          │  return x  │ │  t2 = -x   │
                          │      ↓     │ │  return t2 │
                          └─────┬──────┘ └─────┬──────┘
                                │              │
                                ▼              ▼
                          ┌──────────────────────┐
                          │   BB3: exit           │
                          │   (合并返回)          │
                          └──────────────────────┘
```

### 2.4.6 RTL（寄存器传送语言）

RTL是GCC中最低层次的中间表示，描述的是寄存器之间的数据传送操作。它与目标机器的指令集紧密相关。

```c
/* ============================================================
 * RTL - 寄存器传送语言（简化模型）
 *
 * RTL描述寄存器之间的数据传送。每条RTL表达式(expr)
 * 描述一个机器操作。GCC使用S-表达式形式的RTL，
 * 这里用C结构体来建模。
 * ============================================================ */

typedef enum {
    RTL_REG,               /* 硬件寄存器: reg:SI 88 */
    RTL_CONST_INT,         /* 整数常量: const_int 42 */
    RTL_CONST_DOUBLE,      /* 浮点常量 */
    RTL_MEM,               /* 内存引用: mem:SI (plus reg offset) */
    RTL_PLUS,              /* 加法: (plus x y) */
    RTL_MINUS,             /* 减法 */
    RTL_MULT,              /* 乘法 */
    RTL_DIV,               /* 除法 */
    RTL_MOD,               /* 取余 */
    RTL_AND,               /* 按位与 */
    RTL_IOR,               /* 按位或 */
    RTL_XOR,               /* 按位异或 */
    RTL_NOT,               /* 按位取反 */
    RTL_ASHIFT,            /* 算术左移 */
    RTL_LSHIFTRT,          /* 逻辑右移 */
    RTL_ASHIFTRT,          /* 算术右移 */
    RTL_SIGN_EXTEND,       /* 符号扩展 */
    RTL_ZERO_EXTEND,       /* 零扩展 */
    RTL_TRUNCATE,          /* 截断 */
    RTL_LABEL_REF,         /* 标签引用 */
    RTL_SYMBOL_REF,        /* 符号引用（全局变量/函数地址） */
} RTLExprKind;

/* 机器模式：描述操作数的大小和类型 */
typedef enum {
    MODE_VOID,             /* 无模式 */
    MODE_QI,               /* 1字节整数 (Quarter Integer) */
    MODE_HI,               /* 2字节整数 (Half Integer) */
    MODE_SI,               /* 4字节整数 (Single Integer) */
    MODE_DI,               /* 8字节整数 (Double Integer) */
    MODE_SF,               /* 4字节浮点 (Single Float) */
    MODE_DF,               /* 8字节浮点 (Double Float) */
    MODE_CC,               /* 条件码寄存器模式 */
} MachineMode;

/* RTL表达式 */
typedef struct RTLExpr {
    RTLExprKind kind;
    MachineMode mode;          /* 操作数模式 */
    int n_operands;            /* 操作数数量 */
    struct RTLExpr **operands; /* 操作数数组 */
} RTLExpr;

/* RTL指令类型 */
typedef enum {
    RTL_INSN,              /* 普通指令: (set dst src) */
    RTL_JUMP_INSN,         /* 跳转指令: (set (pc) (if_then_else ...)) */
    RTL_CALL_INSN,         /* 调用指令: (call (mem func) nargs) */
    RTL_LABEL,             /* 标签: (code_label N) */
    RTL_BARRIER,           /* 屏障（不可达标记） */
    RTL_NOTE,              /* 调试/优化注释 */
} RTLInsnKind;

/* 一条RTL指令 */
typedef struct RTLInsn {
    RTLInsnKind kind;
    int uid;                   /* 唯一编号 */
    int line_number;           /* 源码行号 */
    RTLExpr *pattern;          /* 指令模式（描述具体操作） */
    /* 寄存器使用信息（由编译器分析阶段填充） */
    int *regs_used;            /* 使用的寄存器列表 */
    int *regs_set;             /* 设置的寄存器列表 */
    struct RTLInsn *prev;      /* 前一条指令 */
    struct RTLInsn *next;      /* 下一条指令 */
} RTLInsn;
```

---

## 2.5 示例代码说明

本章包含以下示例文件，帮助理解编译器架构的各个方面：

### demo_gcc_stages.c
演示GCC编译的各个阶段。文件中包含：
- 预处理指令（`#include`, `#define`, 条件编译）
- 多种数据类型和变量声明
- 函数定义和调用（包括递归）
- 控制流语句（`if-else`, `for`, `while`, `switch`）
- 指针和结构体操作
- 数组操作

通过以下命令观察各阶段的输出：
```bash
# 预处理结果
gcc -E demo_gcc_stages.c -o demo_gcc_stages.i

# 汇编代码（AT&T语法）
gcc -S -O2 demo_gcc_stages.c -o demo_gcc_stages.s

# 汇编代码（Intel语法，更易读）
gcc -S -O2 -masm=intel demo_gcc_stages.c -o demo_gcc_stages.s

# 保留所有中间文件
gcc -save-temps -O2 demo_gcc_stages.c -o demo_gcc_stages

# 转储GIMPLE（查看中间表示）
gcc -fdump-tree-gimple demo_gcc_stages.c
```

### demo_preprocess.c
专门演示C预处理器的各种特性：
- 宏定义（对象宏、函数宏）
- `#` 字符串化运算符
- `##` 标记粘贴运算符
- 条件编译（`#ifdef`, `#if defined()`）
- 预定义宏（`__FILE__`, `__LINE__`, `__func__`）
- `#pragma` 指令

```bash
# 查看预处理后的结果
gcc -E demo_preprocess.c -o demo_preprocess.i
```

### symbol_table.c
一个完整的符号表实现，可以独立编译运行。实现包括：
- 基于FNV-1a算法的哈希函数
- 使用开链法处理冲突的哈希表
- 作用域链管理（进入/退出作用域）
- 符号的插入、查找、类型检查
- 演示嵌套作用域中的变量查找

```bash
gcc -Wall -o symbol_table symbol_table.c
./symbol_table
```

### ast_example.c
AST节点的定义和操作，可以独立编译运行。实现包括：
- 完整的节点类型枚举
- 各类AST节点的创建函数
- 带缩进的AST打印函数（可视化树结构）
- 内存管理（节点创建和释放）
- 示例：构建一个简单程序的AST并打印

```bash
gcc -Wall -o ast_example ast_example.c
./ast_example
```

---

## 总结

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │                    本章核心概念                                      │
  ├─────────────────────────────────────────────────────────────────────┤
  │                                                                     │
  │  1. 三阶段架构: 前端(分析) → 中端(优化) → 后端(代码生成)           │
  │     使得多语言多目标可复用中端                                      │
  │                                                                     │
  │  2. GCC四级IR: GENERIC → GIMPLE → RTL → 汇编                      │
  │     逐步降低抽象层次，在不同层级执行不同的优化遍                     │
  │                                                                     │
  │  3. MinGW: GCC移植到Windows，生成PE格式可执行文件                   │
  │     与MSVC在ABI、运行时、调试格式等方面存在差异                     │
  │                                                                     │
  │  4. 关键数据结构: Token → AST → 符号表 → IR(三地址码/SSA)          │
  │     → CFG → RTL，每种结构服务于编译器的不同阶段                     │
  │                                                                     │
  │  5. SSA形式通过φ函数使得每个变量只赋值一次                          │
  │     极大简化了数据流分析和优化                                       │
  │                                                                     │
  └─────────────────────────────────────────────────────────────────────┘
```
