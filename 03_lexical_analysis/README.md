# 03 - 词法分析 (Lexical Analysis)

词法分析是编译器的第一个阶段，负责将源代码字符流转换为有意义的词法单元（Token）序列。

## 目录

- [3.1 概述](#31-概述)
- [3.2 关键概念：Token、词素、模式](#32-关键概念token词素模式)
- [3.3 C语言Token类型](#33-c语言token类型)
- [3.4 正则表达式与有限自动机](#34-正则表达式与有限自动机)
- [3.5 手写词法分析器 vs 自动生成](#35-手写词法分析器-vs-自动生成)
- [3.6 GCC词法分析器](#36-gcc词法分析器)
- [3.7 Python词法分析：INDENT/DEDENT处理](#37-python词法分析indentdedent处理)
- [3.8 JavaScript词法分析：ASI机制](#38-javascript词法分析asi机制)
- [3.9 示例代码](#39-示例代码)

---

## 3.1 概述

词法分析器（Lexer/Scanner）是编译器的"眼睛"，它读取源代码的字符流，识别出一个个有意义的词法单元。

```
源代码字符流 ──→ [词法分析器] ──→ Token序列 ──→ [语法分析器]
                    │
                    ▼
              去除空白、注释
              识别词法单元
              记录位置信息
```

**词法分析器的主要职责：**

1. **读取字符**：逐个读取源代码字符
2. **跳过无关内容**：空白字符、注释等
3. **识别Token**：将字符序列识别为Token
4. **报告错误**：发现非法字符时报告错误位置

**为什么词法分析是独立阶段？**

- **简化设计**：将字符处理与语法分析分离
- **提高效率**：词法分析可以用高效的状态机实现
- **增强可移植性**：字符集相关的处理隔离在词法分析器中
- **支持工具生成**：lex/flex等工具可以自动生成词法分析器

---

## 3.2 关键概念：Token、词素、模式

### Token（词法单元）

Token是词法分析的输出，由类型和可选的值组成：

```
Token = (类型, 属性值, 位置信息)

示例：
  (INT_CONST, 42, line:1, col:10)
  (IDENTIFIER, "count", line:2, col:5)
  (KEYWORD_IF, -, line:3, col:1)
```

### Lexeme（词素）

词素是源代码中实际出现的字符序列，是Token的原始文本：

```c
int count = 42;
// 词素: "int", "count", "=", "42", ";"
```

### Pattern（模式）

模式是描述词素形式的规则，通常用正则表达式表示：

```
Token类型        模式（正则表达式）        词素示例
─────────────────────────────────────────────────
INTEGER          [0-9]+                  42, 100, 0
IDENTIFIER       [a-zA-Z_][a-zA-Z0-9_]* count, _temp
IF               "if"                    if
ASSIGN           "="                     =
STRING           "[^"]*"                "hello"
```

### 三者关系

```
Pattern（模式）──定义规则──→ 识别 Lexeme（词素）──生成──→ Token
                  │
                  ▼
            [a-zA-Z_][a-zA-Z0-9_]*  ←─ 模式（正则表达式）
                  │
                  ▼
              "count"  ←─ 词素（匹配的字符序列）
                  │
                  ▼
        (IDENTIFIER, "count")  ←─ Token（类型+属性）
```

---

## 3.3 C语言Token类型

C语言的Token可以分为以下几类：

### Token类型总览

| 类别 | Token类型 | 示例 |
|------|-----------|------|
| **关键字** | KEYWORD | `if`, `else`, `while`, `for`, `return`, `int`, `float`, `char`, `void`, `struct` |
| **标识符** | IDENTIFIER | `count`, `main`, `_temp`, `MAX_SIZE` |
| **整数字面量** | INT_LITERAL | `42`, `0xFF`, `077`, `100L` |
| **浮点字面量** | FLOAT_LITERAL | `3.14`, `1.0e-5`, `.5`, `2.` |
| **字符字面量** | CHAR_LITERAL | `'a'`, `'\n'`, `'\x41'` |
| **字符串字面量** | STRING_LITERAL | `"hello"`, `""`, `"line1\nline2"` |
| **运算符** | OPERATOR | `+`, `-`, `*`, `/`, `=`, `==`, `!=`, `<=`, `>=`, `&&`, `\|\|`, `++`, `--` |
| **分隔符** | SEPARATOR | `(`, `)`, `{`, `}`, `[`, `]`, `;`, `,`, `.` |
| **预处理指令** | PREPROCESSOR | `#include`, `#define`, `#ifdef` |
| **注释** | COMMENT | `/* ... */`, `// ...` |

### C语言关键字完整列表

```
auto       break      case       char       const      continue
default    do         double     else       enum       extern
float      for        goto       if         inline     int
long       register   restrict   return     short      signed
sizeof     static     struct     switch     typedef    union
unsigned   void       volatile   while      _Bool      _Complex
_Imaginary
```

### 运算符优先级与Token

```
单字符运算符:   + - * / % = < > ! & | ^ ~
双字符运算符:   ++ -- == != <= >= && || << >> += -= *= /= %=
三字符运算符:   <<= >>= ...
```

---

## 3.4 正则表达式与有限自动机

正则表达式是描述Token模式的标准方式，可以转换为有限自动机来高效匹配。

### 正则表达式基础

```
运算符      含义              示例
─────────────────────────────────────────
a          字面字符           a 匹配 "a"
a|b        选择（或）         a|b 匹配 "a" 或 "b"
ab         连接（concat）     ab 匹配 "ab"
a*         闭包（0次或多次）  a* 匹配 "", "a", "aa", ...
a+         正闭包（1次或多次）a+ 匹配 "a", "aa", ...
a?         可选（0次或1次）   a? 匹配 "" 或 "a"
[a-z]      字符类             [a-z] 匹配 a到z
.          任意字符           . 匹配任意字符
```

### NFA（非确定性有限自动机）

NFA在某个状态下对同一输入可以有多个转移，也可以有ε转移（不需要输入）。

**示例：识别 `a|b` 的NFA**

```
    ┌───a───┐
    │       ▼
 [0]──ε──[1]──a──→ [2] (接受)
    │       ▲
    └───b───┘
    
状态转移表:
State │ a      │ b      │ ε
──────┼────────┼────────┼─────
  0   │ {}     │ {}     │ {1}
  1   │ {2}    │ {2}    │ {}
  2   │ {}     │ {}     │ {}
```

**示例：识别 `ab` 的NFA**

```
 [0]──a──→ [1]──b──→ [2] (接受)

状态转移表:
State │ a      │ b
──────┼────────┼────
  0   │ {1}    │ {}
  1   │ {}     │ {2}
  2   │ {}     │ {}
```

**示例：识别 `a*` 的NFA**

```
        ┌─────┐
        │     ▼
 [0]──ε──→ [1]──a──→ [2] (接受)
              ▲     │
              └─ε───┘
              
状态转移表:
State │ a      │ ε
──────┼────────┼──────
  0   │ {}     │ {1}
  1   │ {2}    │ {}
  2   │ {}     │ {1}
```

### ε-闭包（Epsilon Closure）

ε-闭包是NFA中通过ε转移可达的所有状态集合：

```
ε-closure({0}) = {0, 1}    (从0可通过ε到达1)
ε-closure({1}) = {1}       (从1没有ε转移)
ε-closure({2}) = {2, 1}    (从2可通过ε到达1)
```

### DFA（确定性有限自动机）

DFA在每个状态下对每个输入符号恰好有一个转移，没有ε转移。

**示例：识别 `a(a|b)*b` 的DFA**

```
        ┌────a────┐
        ▼         │
 [0]──a──→ [1]──b──→ [2] (接受)
              │    ▲
              └─a──┘
              
简化图:
      a        b
→[0] ──→ [1] ──→ [2]*
    ←─a─┘

状态转移表:
State │ a      │ b
──────┼────────┼────
→ 0   │ 1      │ -
  1   │ 1      │ 2
* 2   │ -      │ -
```

### NFA到DFA的转换（子集构造法）

子集构造法将NFA转换为等价的DFA：

```
NFA状态集合        →  DFA状态    a      b
────────────────────────────────────────────
ε-closure({0})   →   A         B      -
ε-closure({A,a}) →   B         B      C
ε-closure({B,b}) →   C (接受)  -      -
```

### DFA最小化

DFA最小化将状态数减少到最少：

```
最小化算法（分割法）:
1. 初始分割: P = {接受状态, 非接受状态}
2. 对每个分割中的状态组:
   - 如果存在输入a使得组内状态转移到不同的组
   - 则分割该组
3. 重复直到无法进一步分割

示例:
原始DFA: 3个状态
最小化后: 可能合并等价状态
```

### Thompson构造法

Thompson构造法将正则表达式递归转换为NFA：

```
基础情况:
  单字符a:  [0]──a──→ [1]
  
递归情况:
  r1|r2:    合并两个NFA的起始和接受状态
  r1r2:     将r1的接受状态连接到r2的起始状态
  r*:       添加ε循环和旁路
```

---

## 3.5 手写词法分析器 vs 自动生成

### 手写词法分析器

**优点：**
- 完全控制输出格式和错误处理
- 可以处理复杂的上下文相关词法
- 通常更容易调试
- 可以进行手工优化

**缺点：**
- 开发时间长
- 容易出错
- 难以维护和修改

**适用场景：**
- 需要特殊处理的语言特性（如Python的缩进）
- 对性能有极高要求
- 词法规则简单

### 自动生成（lex/flex）

**优点：**
- 开发快速
- 基于正规表达式，形式化定义
- 易于修改和维护
- 自动生成高效的DFA

**缺点：**
- 生成的代码可读性差
- 难以处理上下文相关的词法
- 错误处理不灵活

**适用场景：**
- 标准的词法规则
- 快速原型开发
- 需要频繁修改词法规则

### 对比示例

```
lex/flex定义:
%%
[0-9]+        { return INT_CONST; }
[a-zA-Z_][a-zA-Z0-9_]*  { return IDENTIFIER; }
"if"          { return IF; }
"+"           { return PLUS; }
[ \t\n]       { /* 跳过空白 */ }
.             { error("非法字符"); }
%%

手写Python:
def next_token(self):
    self.skip_whitespace()
    if self.current_char.isdigit():
        return self.read_number()
    elif self.current_char.isalpha() or self.current_char == '_':
        return self.read_identifier()
    ...
```

---

## 3.6 GCC词法分析器

GCC使用手写的词法分析器，位于 `libcpp/lex.c`。

### 主要特点

1. **宏展开集成**：词法分析与预处理器紧密集成
2. **位置追踪**：精确的源位置信息（行、列、文件）
3. **Token缓存**：支持Token的前瞻和回退
4. **多语言支持**：通过钩子函数支持C、C++、Objective-C等

### GCC Token类型

```c
/* GCC中的Token类型（简化） */
enum cpp_ttype {
  CPP_EOF,           /* 文件结束 */
  CPP_NAME,          /* 标识符 */
  CPP_NUMBER,        /* 数字字面量 */
  CPP_CHAR,          /* 字符字面量 */
  CPP_STRING,        /* 字符串字面量 */
  CPP_OPERATOR,      /* 运算符 */
  CPP_PUNCT,         /* 标点符号 */
  CPP_COMMENT,       /* 注释 */
  CPP_PRAGMA,        /* 编译指示 */
  ...
};
```

### 位置信息追踪

```c
/* GCC的源位置表示 */
typedef unsigned int source_location;

/* 位置信息包含：
   - 文件名
   - 行号
   - 列号
   - 系统头文件标记
   - 编译器生成代码标记
*/
```

---

## 3.7 Python词法分析：INDENT/DEDENT处理

Python使用缩进来表示代码块，这给词法分析带来特殊挑战。

### INDENT/DEDENT机制

```python
# Python代码示例
if x > 0:
    print("positive")    # INDENT
    if y > 0:
        print("both")    # INDENT
    print("done")        # DEDENT
print("end")             # DEDENT
```

### Token流

```
源代码:
if x > 0:
    print("positive")
print("end")

Token序列:
IF IDENTIFIER(x) GT INT(0) COLON NEWLINE
    INDENT
    IDENTIFIER(print) LPAREN STRING("positive") RPAREN NEWLINE
    DEDENT
IDENTIFIER(print) LPAREN STRING("end") RPAREN NEWLINE
```

### 实现策略

```python
class PythonLexer:
    def __init__(self):
        self.indent_stack = [0]  # 缩进栈
        self.paren_depth = 0     # 括号深度（括号内忽略换行）
    
    def handle_newline(self):
        """处理换行时的缩进"""
        if self.paren_depth > 0:
            return  # 在括号内，忽略换行
        
        indent = self.calculate_indent()
        
        if indent > self.indent_stack[-1]:
            self.indent_stack.append(indent)
            return INDENT
        elif indent < self.indent_stack[-1]:
            while indent < self.indent_stack[-1]:
                self.indent_stack.pop()
                yield DEDENT
            return
```

### 特殊情况处理

```
1. 括号内的换行被忽略:
   x = (1 +
        2 + 3)  # 不产生INDENT/DEDENT

2. 续行符(\):
   x = 1 + \
       2 + 3    # 不产生NEWLINE

3. 空行和注释不影响缩进:
   if True:
       x = 1
       
       # 这是注释
       y = 2    # 缩进保持不变
```

---

## 3.8 JavaScript词法分析：ASI机制

JavaScript的自动分号插入（Automatic Semicolon Insertion，ASI）是一个独特的词法特性。

### ASI规则

**规则1：** 当遇到语法错误时，如果错误前有换行符，则在换行符处插入分号。

```javascript
// 原始代码
let x = 1
let y = 2

// ASI处理后
let x = 1;
let y = 2;
```

**规则2：** 在`}`之前，如果语法错误，则插入分号。

```javascript
// 原始代码
function foo() {
  return
  {
    name: "bar"
  }
}

// ASI处理后（注意：这不是我们期望的！）
function foo() {
  return;    // 这里插入了分号！
  {
    name: "bar"
  }
}
```

**规则3：** 在输入流结束处，如果语法错误，则插入分号。

### ASI的"禁止"规则

ASI不会在以下情况插入分号：

```javascript
// 这些地方不会插入分号
return
x++    // 错误！ASI不会在这里插入分号

// 等价于
return x++;  // 语法错误

// 正确写法
return x++;
// 或
return;
x++;
```

### 词法分析器实现

```javascript
class JavaScriptLexer {
  constructor(source) {
    this.source = source;
    this.pos = 0;
    this.lineTerminatorBeforeNext = false;
  }
  
  nextToken() {
    // 检查是否需要插入分号
    if (this.shouldInsertSemicolon()) {
      return { type: 'SEMICOLON', value: ';' };
    }
    
    // 正常词法分析...
  }
  
  shouldInsertSemicolon() {
    // ASI规则判断
    return this.lineTerminatorBeforeNext && 
           this.isRestrictedProduction();
  }
}
```

### ASI带来的问题

```javascript
// 问题1：意外的返回值
function getData() {
  return
  {
    key: "value"
  }
}
// 返回undefined，不是对象！

// 问题2：自增/自减
let x = 1
++x
// 等价于 x++; x，不是 1; ++x
```

---

## 3.9 示例代码

本目录包含以下示例文件：

### lexer.py - 手写词法分析器

完整的Python实现，包含：

- `TokenType` 枚举定义所有Token类型
- `Token` 类表示词法单元（类型、值、位置）
- `Lexer` 类实现状态机词法分析
- 支持：整数、浮点数、标识符、关键字、运算符、分隔符、字符串、注释
- 错误处理和行号追踪
- `main()` 函数演示使用方法

**运行示例：**
```bash
python lexer.py
```

### regex_to_dfa.py - 正则表达式到DFA转换

实现正则表达式到DFA的完整转换流程：

- Thompson构造法：正则表达式 → NFA
- 子集构造法：NFA → DFA（包含ε-闭包计算）
- DFA最小化：最小化DFA状态数
- 完整可运行的实现

**运行示例：**
```bash
python regex_to_dfa.py
```

### test_lexer.c - C语言测试代码

用于测试词法分析器的C语言示例代码，包含：

- 各种关键字和标识符
- 整数和浮点数字面量
- 字符和字符串字面量
- 各种运算符
- 注释（单行和多行）
- 预处理指令

---

## 参考资源

1. **Compilers: Principles, Techniques, and Tools** (龙书) - 第3章：词法分析
2. **Engineering a Compiler** - 第2章：词法分析
3. **GCC源码** - `libcpp/lex.c` 词法分析实现
4. **Python源码** - `Parser/tokenizer.c` 词法分析实现
5. **V8源码** - `src/parsing/scanner.cc` JavaScript词法分析

---

## 延伸阅读

- Unicode处理：UTF-8编码下的词法分析
- 错误恢复：发现非法字符后如何继续分析
- 增量词法分析：编辑器中的实时词法分析
- 词法分析器生成器：lex/flex的原理和使用
