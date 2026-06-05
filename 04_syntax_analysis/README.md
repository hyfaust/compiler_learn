# 第四章：语法分析（Syntax Analysis）

> 语法分析是编译器的核心阶段之一，负责将词法分析器产生的 Token 流转换为抽象语法树（AST）。
> 本章将从理论到实践，系统讲解语法分析的原理与实现。

---

## 目录

- [4.1 语法分析概述](#41-语法分析概述)
- [4.2 上下文无关文法（CFG）详解](#42-上下文无关文法cfg详解)
- [4.3 自顶向下分析](#43-自顶向下分析)
- [4.4 自底向上分析](#44-自底向上分析)
- [4.5 抽象语法树（AST）详解](#45--抽象语法树ast详解)
- [4.6 错误处理](#46-错误处理)
- [4.7 GCC/Python/JavaScript 中的语法分析](#47-gccpythonjavascript-中的语法分析)
- [4.8 示例代码](#48-示例代码)

---

## 4.1 语法分析概述

### 4.1.1 语法分析器的作用

语法分析器（Parser）是编译器的第二个主要阶段。它的核心任务是：

1. **接收 Token 流**：从词法分析器（Lexer）获取扁平的 Token 序列
2. **检查语法正确性**：验证 Token 序列是否符合语言的语法规则
3. **构建语法树**：将线性的 Token 流组织成层次化的树形结构（AST）

```
源代码: x = 3 + 4 * 5;

词法分析器输出（Token 流）:
  [ID("x"), ASSIGN, NUM(3), PLUS, NUM(4), STAR, NUM(5), SEMI]

语法分析器输出（AST）:
  Assignment
  ├── left: Identifier("x")
  └── right: BinaryOp(+)
              ├── left: Number(3)
              └── right: BinaryOp(*)
                          ├── left: Number(4)
                          └── right: Number(5)
```

### 4.1.2 语法分析在编译器中的位置

```
┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐
│  词法分析    │───▶│  语法分析    │───▶│  语义分析    │───▶│  中间代码    │
│  (Lexer)    │    │  (Parser)   │    │ (Semantic)  │    │  生成       │
│ 字符→Token  │    │ Token→AST   │    │ 类型检查    │    │ IR/字节码   │
└─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘
```

### 4.1.3 上下文无关文法（CFG）简介

正则表达式（有限自动机）能识别的模式非常有限，无法处理**嵌套的括号匹配**。CFG 通过**递归**来描述这种嵌套结构。

```
expr → expr + term     // 一个表达式可以是 "表达式 + 项"
       | term           // 或者就是一个项

term → term * factor   // 一个项可以是 "项 * 因子"
       | factor         // 或者就是一个因子

factor → ( expr )      // 一个因子可以是括号括起来的表达式（递归！）
         | number       // 或者是一个数字
```

---

## 4.2 上下文无关文法（CFG）详解

### 4.2.1 CFG 的四元组定义

一个上下文无关文法 G 是一个四元组 **G = (V, T, P, S)**，其中：

| 符号 | 含义 | 说明 |
|------|------|------|
| **V** | 非终结符集合（Variables） | 语法变量，表示语法范畴 |
| **T** | 终结符集合（Terminals） | Token，不能再被展开的符号 |
| **P** | 产生式集合（Productions） | 重写规则，形如 A → α |
| **S** | 开始符号（Start Symbol） | 推导的起点，S ∈ V |

### 4.2.2 终结符与非终结符

**终结符（Terminal）**：Token 流中的基本单位，是语法分析的"原子"。

```
// 终结符的例子
if, else, while, return     // 关键字
+, -, *, /, =, ==           // 运算符
(, ), {, }, ;               // 分隔符
id, num, string             // Token 类别
```

**非终结符（Non-terminal）**：代表一个语法范畴，可以被进一步展开。

```
// 非终结符的例子
program, stmt_list, stmt    // 程序结构
expr, term, factor          // 表达式层次
decl, type, param_list      // 声明结构
```

### 4.2.3 产生式（Productions）

产生式定义了如何将非终结符展开：

```
// 产生式的基本形式
A → α

// 其中 A ∈ V（非终结符），α ∈ (V ∪ T)*（终结符和非终结符的串）

// 例子：
stmt → id = expr ;          // 赋值语句
stmt → if ( expr ) stmt     // if 语句
stmt → { stmt_list }        // 代码块
```

### 4.2.4 推导（Derivation）

推导是从开始符号出发，反复应用产生式，最终得到终结符串的过程。

**最左推导（Leftmost Derivation）**：每一步都替换最左边的非终结符。

```
// 推导 "x = 3 + 4 * 5;"

stmt ⟹ id = expr ;
     ⟹ id = term expr'
     ⟹ id = factor term' expr'
     ⟹ id = num term' expr'
     ⟹ id = num expr'
     ⟹ id = num + term expr'
     ⟹ id = num + factor term' expr'
     ⟹ id = num + num term' expr'
     ⟹ id = num + num * factor term' expr'
     ⟹ id = num + num * num term' expr'
     ⟹ id = num + num * num expr'
     ⟹ id = num + num * num
```

### 4.2.5 语法树（Parse Tree）与抽象语法树（AST）的区别

| 特性 | Parse Tree | AST |
|------|-----------|-----|
| 完整性 | 包含所有语法细节 | 只保留语义关键信息 |
| 辅助节点 | 包含 `expr'`, `term'` 等 | 不包含 |
| 冗余度 | 高 | 低 |
| 用途 | 理论分析 | 实际编译器实现 |

### 4.2.6 贯穿示例文法

```bnf
program    → stmt_list
stmt_list  → stmt stmt_list | ε
stmt       → id = expr ;
            | if ( expr ) stmt
            | if ( expr ) stmt else stmt
            | { stmt_list }
expr       → term expr'
expr'      → + term expr' | - term expr' | ε
term       → factor term'
term'      → * factor term' | / factor term' | ε
factor     → ( expr ) | id | num
            | - factor | ! factor
```

---

## 4.3 自顶向下分析

### 4.3.1 递归下降分析法

递归下降（Recursive Descent）是最直观、最常用的自顶向下分析方法。

**核心思想**：每个非终结符对应一个解析函数。

```python
# 伪代码：非终结符与函数的对应关系

def parse_program():      # program → stmt_list
    return parse_stmt_list()

def parse_stmt_list():    # stmt_list → stmt stmt_list | ε
    stmts = []
    while current_token in STMT_FIRST:
        stmts.append(parse_stmt())
    return stmts

def parse_stmt():         # stmt → id = expr ; | if ( expr ) stmt | { stmt_list }
    if current_token == ID:
        name = match(ID)
        match(ASSIGN)
        expr = parse_expr()
        match(SEMI)
        return Assignment(name, expr)
    elif current_token == IF:
        match(IF)
        match(LPAREN)
        cond = parse_expr()
        match(RPAREN)
        body = parse_stmt()
        return If(cond, body)
    elif current_token == LBRACE:
        match(LBRACE)
        stmts = parse_stmt_list()
        match(RBRACE)
        return Block(stmts)
```

**优点**：代码结构与文法一一对应，易于理解和调试，广泛用于工业级编译器。

**缺点**：不能直接处理左递归，某些文法需要回溯。

### 4.3.2 FIRST 集和 FOLLOW 集

**FIRST 集**：从某个符号出发，所有可能出现在推导串**开头**的终结符。

```
FIRST(α) = { a | α ⟹* aβ, a ∈ T }
         ∪ { ε | α ⟹* ε }

// 计算示例：
FIRST(factor)  = { (, id, num, -, ! }
FIRST(term')   = { *, /, ε }
FIRST(term)    = { (, id, num, -, ! }
FIRST(expr')   = { +, -, ε }
FIRST(expr)    = { (, id, num, -, ! }
FIRST(stmt)    = { id, if, { }
```

**FOLLOW 集**：在某些句型中，紧跟在某个非终结符**后面**的终结符。

```
FOLLOW(A) = { a | S ⟹* ...Aa..., a ∈ T }

// 计算示例：
FOLLOW(program)    = { $ }
FOLLOW(stmt_list)  = { $, } }
FOLLOW(stmt)       = { $, }, id, if, { }
FOLLOW(expr)       = { ), ; }
FOLLOW(term)       = { +, -, ), ; }
FOLLOW(factor)     = { *, /, +, -, ), ; }
```

### 4.3.3 预测分析表

预测分析表 M[A, a] 告诉我们：当前非终结符为 A、当前输入 Token 为 a 时，应该使用哪个产生式。

```
┌──────────────┬─────────────────────────────────────────────────────────────┐
│ 非终结符      │                        输入 Token                           │
│              ├──────┬──────┬──────┬──────┬──────┬──────┬──────┬──────┬─────┤
│              │ id   │ num  │ (    │ )    │ +    │ -    │ *    │ /    │ ;   │
├──────────────┼──────┼──────┼──────┼──────┼──────┼──────┼──────┼──────┼─────┤
│ expr         │ p7   │ p7   │ p7   │      │      │      │      │      │     │
│ expr'        │      │      │      │ p10  │ p8   │ p9   │      │      │ p10 │
│ term         │ p11  │ p11  │ p11  │      │      │      │      │      │     │
│ term'        │ p14  │      │      │ p14  │ p14  │ p14  │ p12  │ p13  │     │
│ factor       │ p15  │ p16  │ p17  │      │      │      │      │      │     │
└──────────────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴──────┴─────┘
```

### 4.3.4 LL(1) 文法的条件

一个文法是 **LL(1)** 的，当且仅当预测分析表中每个单元格最多只有一个产生式。

- **第一个 L**：从左到右扫描输入（Left-to-right）
- **第二个 L**：最左推导（Leftmost derivation）
- **1**：向前看 1 个 Token

### 4.3.5 左递归消除

左递归会导致递归下降分析器无限循环。

```bnf
// 原始文法（直接左递归）
expr → expr + term | term

// 消除左递归后
expr  → term expr'
expr' → + term expr' | - term expr' | ε
```

### 4.3.6 提取左公因子

当多个产生式有相同的前缀时，预测分析器无法决定使用哪个。

```bnf
// 原始文法
stmt → if ( expr ) stmt
     | if ( expr ) stmt else stmt

// 提取左公因子后
stmt      → if ( expr ) stmt stmt_tail
stmt_tail → else stmt | ε
```

---

## 4.4 自底向上分析

### 4.4.1 移进-归约分析

移进-归约（Shift-Reduce）分析使用一个**栈**来保存已处理的符号：

```
两个基本操作：
  - Shift（移进）：将下一个输入 Token 压入栈
  - Reduce（归约）：将栈顶的若干符号按产生式替换为非终结符

示例：分析 "id * id"（简化文法：E → E * T | T, T → id）

步骤    栈              输入           动作
────────────────────────────────────────────────
 1     $               id * id $      Shift
 2     $ id            * id $         Reduce: T → id
 3     $ T             * id $         Shift
 4     $ T *           id $           Shift
 5     $ T * id        $              Reduce: T → id
 6     $ T * T         $              Reduce: E → E * T
 7     $ E             $              Accept
```

### 4.4.2 LR(0) 分析

**LR(0) 项目（Item）**：在产生式右部的某个位置加一个点 `·`，表示已解析到的位置。

```
产生式 A → XYZ 的 LR(0) 项目：
  A → ·XYZ     // 还没开始解析
  A → X·YZ     // 已经解析了 X
  A → XY·Z     // 已经解析了 XY
  A → XYZ·     // 已经完全解析（可以归约）
```

### 4.4.3 SLR 分析

SLR（Simple LR）是 LR(0) 的改进，使用 **FOLLOW 集**来解决冲突。

**核心思想**：只有当下一个输入 Token 在 `FOLLOW(A)` 中时，才执行归约。

### 4.4.4 LR(1) 分析

LR(1) 在 LR(0) 项目的基础上增加了一个**向前看符号**（lookahead）。

**LR(1) 项目**：`[A → α·β, a]`，其中 `a` 是向前看符号。

### 4.4.5 LALR 分析

LALR（Look-Ahead LR）是 LR(1) 和 SLR 的折中方案，将 LR(1) 自动机中具有相同核心的状态合并。

| 特性 | SLR | LALR | LR(1) |
|------|-----|------|-------|
| 状态数 | 少 | 与 SLR 相同 | 多 |
| 分析能力 | 弱 | 中 | 强 |
| 实际使用 | 教学为主 | **最广泛**（yacc/bison） | 理论完备 |

---

## 4.5 抽象语法树（AST）详解

### 4.5.1 AST 的数据结构设计

```c
typedef enum {
    NODE_PROGRAM, NODE_ASSIGNMENT, NODE_IF_STMT, NODE_BLOCK,
    NODE_BINARY_OP, NODE_UNARY_OP, NODE_NUMBER, NODE_IDENTIFIER,
} NodeType;

typedef struct ASTNode {
    NodeType type;
    int line, column;
    union {
        struct { struct ASTNode **stmts; int count; } block;
        struct { char *name; struct ASTNode *value; } assignment;
        struct { struct ASTNode *cond, *then_b, *else_b; } if_stmt;
        struct { int op; struct ASTNode *left, *right; } binary;
        struct { int op; struct ASTNode *operand; } unary;
        struct { double value; char *raw; } number;
        struct { char *name; } identifier;
    } as;
} ASTNode;
```

### 4.5.2 AST 的遍历

- **前序遍历**：根 → 左 → 右，用于代码生成
- **后序遍历**：左 → 右 → 根，用于语义分析和求值
- **中序遍历**：左 → 根 → 右，用于表达式还原输出

### 4.5.3 AST 在后续阶段的作用

```
Parser → AST → 语义分析（类型检查、作用域）
             → IR生成（三地址码）
             → 代码优化
             → 目标代码生成
```

---

## 4.6 错误处理

### 4.6.1 错误恢复策略

| 策略 | 描述 | 适用场景 |
|------|------|---------|
| 恐慌模式 | 跳过Token直到找到同步符号 | 最简单、最常用 |
| 短语级恢复 | 对栈或输入做局部修改 | 中等复杂度 |
| 错误产生式 | 添加特殊产生式匹配常见错误 | 预知常见错误 |

---

## 4.7 GCC/Python/JavaScript 中的语法分析

| 编译器/解释器 | Parser 类型 | 原因 |
|-------------|-----------|------|
| GCC (C/C++) | 手写递归下降 | 性能、错误恢复、C++ 复杂语法 |
| Clang (LLVM) | 手写递归下降 | 同上 |
| CPython (>=3.9) | PEG Parser | 更灵活的语法支持 |
| V8 (JavaScript) | 手写递归下降 + 延迟解析 | 性能优化 |
| Go (gc) | 手写递归下降 | 简洁的语言设计 |

> **趋势**：现代编译器几乎都使用**手写递归下降 Parser**。

---

## 4.8 示例代码

| 文件 | 说明 |
|------|------|
| `parser.py` | 完整的递归下降语法分析器（含内嵌词法分析器） |
| `ast_visualizer.py` | AST 树形终端可视化工具 |
| `test_parser.c` | 测试用的 C 语言代码示例 |

### 使用方法

```bash
# 解析测试文件并打印 AST
python parser.py test_parser.c

# 使用 AST 可视化工具
python ast_visualizer.py test_parser.c
```

---

## 小结

| 分析方法 | 方向 | 文法类 | 向前看 | 典型工具 |
|---------|------|--------|--------|---------|
| 递归下降 | 自顶向下 | LL(k) | k 个 | 手写 |
| LL(1) 表驱动 | 自顶向下 | LL(1) | 1 个 | ANTLR |
| LALR(1) | 自底向上 | LALR(1) | 1 个 | yacc/bison |
| PEG | 混合 | 超 CFG | 无限制 | pegen |
