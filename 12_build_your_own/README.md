# 第12章：动手实现编译器和解释器

> "The best way to understand a compiler is to build one."
> —— 要理解编译器，最好的方式就是亲手实现一个。

本章将从零开始实现一个完整的编程语言 **TinyLang**，包含词法分析器、语法分析器、树遍历解释器、字节码编译器和栈式虚拟机。通过这个项目，你将深刻理解从源代码到程序执行的完整流程。

---

## 12.1 项目总览

### 12.1.1 TinyLang 是什么

TinyLang 是一个教学用的动态类型编程语言，具备以下特性：

- **数据类型**：整数、浮点数、字符串、布尔值、数组、none
- **变量**：`let` 声明，动态类型
- **运算**：算术、比较、逻辑、字符串拼接
- **控制流**：`if/elif/else`、`while`、`for-in`、`break`、`continue`
- **函数**：一等公民函数、闭包、递归
- **内置函数**：`print`、`len`、`type`、`str`、`int`、`float`、`range`、`append`

### 12.1.2 项目结构

```
12_build_your_own/
├── tinylang/              # 核心代码
│   ├── __init__.py        # 包初始化
│   ├── errors.py          # 错误类型定义
│   ├── ast_nodes.py       # AST 节点定义
│   ├── opcodes.py         # 字节码操作码定义
│   ├── lexer.py           # 词法分析器
│   ├── parser.py          # 语法分析器
│   ├── environment.py     # 作用域环境
│   ├── builtins.py        # 内置函数
│   ├── interpreter.py     # 树遍历解释器
│   ├── compiler.py        # 字节码编译器
│   ├── vm.py              # 栈式虚拟机
│   └── main.py            # 命令行入口
├── examples/              # 示例程序
│   ├── hello.tl           # 入门示例
│   ├── fibonacci.tl       # 斐波那契数列
│   ├── factorial.tl       # 阶乘与组合数
│   ├── sorting.tl         # 排序算法
│   ├── closure.tl         # 闭包与高阶函数
│   └── game.tl            # 猜数字游戏
├── tests/
│   └── test_tinylang.py   # 完整测试套件
└── README.md              # 本文件
```

### 12.1.3 两种执行方式

TinyLang 提供两种执行方式，对应两种经典的程序执行模型：

| 方式 | 文件 | 原理 | 优点 | 缺点 |
|------|------|------|------|------|
| 树遍历解释器 | `interpreter.py` | 直接遍历 AST 求值 | 简单直观 | 速度较慢 |
| 字节码虚拟机 | `compiler.py` + `vm.py` | 编译为字节码后执行 | 速度快 | 实现复杂 |

### 12.1.4 快速开始

```bash
# 交互式 REPL
python -m tinylang.main

# 执行示例文件
python -m tinylang.main examples/hello.tl

# 使用虚拟机执行
python -m tinylang.main --vm examples/fibonacci.tl

# 查看 AST
python -m tinylang.main --ast examples/hello.tl

# 查看字节码
python -m tinylang.main --bytecode examples/hello.tl

# 运行测试
python -m pytest tests/ -v
```

---

## 12.2 词法分析器 (Lexer) —— 从字符到 Token

### 12.2.1 什么是词法分析

词法分析（Lexical Analysis）是编译的第一步，将源代码的字符流转换为 **Token**（词法单元）序列。

```
源代码: let x = 42 + 3.14;
Tokens: [LET] [ID:x] [ASSIGN] [INT:42] [PLUS] [FLOAT:3.14] [SEMICOLON] [EOF]
```

这就像把一句话拆分成单词和标点符号。

### 12.2.2 Token 的类型

TinyLang 定义了以下 Token 类型（`lexer.py` 中的 `TokenType` 枚举）：

**字面量**：`INTEGER`（整数）、`FLOAT`（浮点数）、`STRING`（字符串）

**标识符和关键字**：`IDENTIFIER`（变量名）、`LET`、`IF`、`WHILE`、`FUNC`、`RETURN` 等 16 个关键字

**运算符**：
- 算术：`+` `-` `*` `/` `%`
- 比较：`==` `!=` `<` `>` `<=` `>=`
- 赋值：`=`
- 逻辑：`and` `or` `not`

**分隔符**：`(` `)` `[` `]` `{` `}` `,` `;`

**特殊**：`EOF`（文件结束）

### 12.2.3 实现原理

词法分析器逐字符扫描源代码，根据字符类型分派到不同的处理函数：

```python
# lexer.py 核心逻辑
class Lexer:
    def _read_token(self):
        char = self._current_char()

        if char.isdigit():
            return self._read_number()      # 读取数字
        if char.isalpha() or char == '_':
            return self._read_identifier()   # 读取标识符/关键字
        if char == '"':
            return self._read_string()       # 读取字符串
        # ... 处理运算符和分隔符
```

**关键设计点**：
- 数字解析：先读取连续数字，遇到 `.` 则为浮点数
- 标识符识别：先读取完整的单词，然后查关键字表判断是否为关键字
- 字符串解析：支持 `\n`、`\t`、`\\`、`\"` 转义
- 注释处理：`//` 开头的行注释被跳过

### 12.2.4 动手实验

```python
from tinylang.lexer import Lexer

tokens = Lexer('let x = 42 + 3.14;').tokenize()
for t in tokens:
    print(f"  {t.type.name:12s} | {t.value!r}")
```

输出：
```
  LET          | 'let'
  IDENTIFIER   | 'x'
  ASSIGN       | '='
  INTEGER      | 42
  PLUS         | '+'
  FLOAT        | 3.14
  SEMICOLON    | ';'
  EOF          | None
```

---

## 12.3 语法分析器 (Parser) —— 从 Token 到 AST

### 12.3.1 什么是语法分析

语法分析（Parsing）将 Token 序列转换为 **抽象语法树**（AST）。AST 是程序结构的树形表示，反映了运算的优先级和嵌套关系。

```
let x = 1 + 2 * 3;

         Program
           |
       LetStatement(name="x")
           |
       BinaryOp(+)
        /        \
  Integer(1)   BinaryOp(*)
               /        \
         Integer(2)   Integer(3)
```

注意 `*` 比 `+` 优先级高，所以 `2 * 3` 先结合。

### 12.3.2 递归下降解析法

TinyLang 使用 **递归下降解析法**（Recursive Descent Parsing），这是最直观的自顶向下语法分析方法。核心思想是：**每条语法规则对应一个解析方法**。

运算符优先级通过方法的层级关系体现：

```
_parse_expression()        # 入口
  └─ _parse_or()           # 优先级 1: or
      └─ _parse_and()      # 优先级 2: and
          └─ _parse_comparison()  # 优先级 3: ==, !=, <, >, <=, >=
              └─ _parse_addition()  # 优先级 4: +, -
                  └─ _parse_multiplication()  # 优先级 5: *, /, %
                      └─ _parse_unary()  # 优先级 6: -, not
                          └─ _parse_postfix()  # 优先级 7: 函数调用(), 索引[]
                              └─ _parse_primary()  # 优先级 8: 字面量, 标识符, 括号
```

### 12.3.3 AST 节点设计

AST 节点使用 Python `dataclass` 定义，分为两大类：

**语句节点**（Statement）：执行操作，不产生值
- `Program` —— 程序（语句列表）
- `LetStatement` —— 变量声明
- `AssignmentStatement` —— 赋值
- `IfStatement` —— 条件分支
- `WhileStatement` —— while 循环
- `ForStatement` —— for-in 循环
- `FunctionDef` —— 函数定义
- `ReturnStatement` / `BreakStatement` / `ContinueStatement`

**表达式节点**（Expression）：求值，产生一个值
- `IntegerLiteral` / `FloatLiteral` / `StringLiteral` / `BooleanLiteral` —— 字面量
- `Identifier` —— 变量引用
- `ArrayLiteral` —— 数组字面量
- `BinaryOp` —— 二元运算
- `UnaryOp` —— 一元运算
- `CallExpression` —— 函数调用
- `IndexExpression` —— 数组索引

### 12.3.4 解析示例

解析 `if x > 0 { print(x); }` 的过程：

```
1. _parse_statement() 看到 IF 关键字
2. 调用 _parse_if()
3. 解析条件表达式: _parse_expression() -> BinaryOp(>, x, 0)
4. 解析代码块: _parse_block()
5. 在块内解析语句: CallExpression(print, [x])
6. 返回 IfStatement 节点
```

---

## 12.4 树遍历解释器 (Interpreter) —— 直接执行 AST

### 12.4.1 执行模型

树遍历解释器是最直观的程序执行方式：**直接遍历 AST，对每个节点求值**。

- 表达式节点 => 求值，返回一个值
- 语句节点 => 执行，产生副作用

```
执行 print(1 + 2 * 3):

1. 遍历到 ExpressionStatement
2. 求值 CallExpression: print(...)
   3. 求值参数 BinaryOp(+, 1, BinaryOp(*, 2, 3))
      4. 求值 Integer(1) => 1
      5. 求值 BinaryOp(*, 2, 3)
         6. 求值 Integer(2) => 2
         7. 求值 Integer(3) => 3
         8. 计算 2 * 3 => 6
      9. 计算 1 + 6 => 7
   10. 调用 print(7) => 输出 "7"
```

### 12.4.2 作用域管理

变量作用域通过 **Environment 链** 实现：

```
全局环境 (global_env)
  └─ x = 10, print = <builtin>
      │
      └─ 函数环境 (func_env, parent = closure_env)
          └─ a = 3, b = 4
```

- `define(name, value)`：在当前环境定义新变量
- `get(name)`：沿作用域链向上查找变量
- `set(name, value)`：沿作用域链找到变量并更新

### 12.4.3 闭包实现

闭包是函数与其定义时环境的组合：

```python
func make_counter() {
    let count = 0;          # count 属于 make_counter 的环境
    func increment() {
        count = count + 1;  # increment 捕获了 count
        return count;
    }
    return increment;
}
```

当 `make_counter()` 返回 `increment` 函数时，`increment` 仍然持有对 `count` 变量的引用。这就是闭包。

在实现中，`TinyLangFunction` 保存了定义时的 `closure` 环境：
```python
class TinyLangFunction:
    def __init__(self, node, closure):
        self.closure = closure  # 捕获的环境
```

### 12.4.4 控制流实现

`break`、`continue`、`return` 需要跳出当前的执行上下文。我们使用 Python 异常来实现这种 **非局部跳转**：

```python
class ReturnException(Exception):
    def __init__(self, value):
        self.value = value

class BreakException(Exception):
    pass

class ContinueException(Exception):
    pass
```

当执行到 `return` 语句时，抛出 `ReturnException`，在外层的函数调用处捕获并返回值。`break` 和 `continue` 类似。

---

## 12.5 字节码编译器 (Compiler) —— 从 AST 到字节码

### 12.5.1 为什么需要字节码

树遍历解释器虽然简单，但每执行一步都要遍历树结构，效率较低。字节码虚拟机通过以下方式提升性能：

1. **线性化**：将树结构转换为线性的指令序列
2. **紧凑表示**：每条指令只有几个字节
3. **快速分派**：通过操作码直接跳转到处理逻辑

### 12.5.2 字节码基础

字节码是一种介于源代码和机器码之间的中间表示。每条指令由 **操作码**（Opcode）和可选的 **操作数**（Operand）组成：

```
TinyLang 源代码:
    let x = 1 + 2;

编译后的字节码:
    LOAD_CONST  0    # 加载常量 1
    LOAD_CONST  1    # 加载常量 2
    ADD              # 弹出两个值，相加，压入结果
    STORE_VAR   2    # 存储到变量 "x"
    HALT             # 停机
```

### 12.5.3 操作码设计

TinyLang 定义了 30+ 条操作码（`opcodes.py` 中的 `Opcode` 枚举）：

**栈操作**：
- `LOAD_CONST` —— 从常量池加载值到栈
- `LOAD_TRUE` / `LOAD_FALSE` / `LOAD_NONE` —— 加载布尔值/空值
- `POP` —— 弹出栈顶值
- `DUP` —— 复制栈顶值

**变量操作**：
- `LOAD_VAR` —— 加载变量值到栈
- `STORE_VAR` —— 将栈顶值存入变量

**算术运算**：`ADD`、`SUB`、`MUL`、`DIV`、`MOD`、`NEGATE`

**比较运算**：`CMP_EQ`、`CMP_NEQ`、`CMP_LT`、`CMP_GT`、`CMP_LTE`、`CMP_GTE`

**逻辑运算**：`AND`、`OR`、`NOT`

**控制流**：`JUMP`、`JUMP_IF_FALSE`、`JUMP_IF_TRUE`

**函数**：`CALL`、`RETURN`

**数组**：`BUILD_ARRAY`、`GET_INDEX`、`SET_INDEX`、`GET_LEN`

**特殊**：`HALT`（停机）

### 12.5.4 编译示例

编译 `if x > 0 { print(x); }` 的过程：

```
AST: IfStatement
  condition: BinaryOp(>, x, 0)
  then_body: [ExpressionStatement(CallExpression(print, [x]))]

编译输出:
  LOAD_VAR    "x"          # 压入 x
  LOAD_CONST  0            # 压入常量 0
  CMP_GT                   # 比较: x > 0
  JUMP_IF_FALSE 12         # 为假则跳到地址 12
  LOAD_VAR    "print"      # 压入 print 函数
  LOAD_VAR    "x"          # 压入 x
  CALL        1            # 调用 print(x)
  POP                      # 丢弃返回值
  HALT                     # 停机
```

### 12.5.5 跳转回填

编译 `if` 语句时，编译器还不知道 `JUMP_IF_FALSE` 应该跳到哪里（因为 then 分支的代码还没编译）。解决方案是 **回填**（Patch）：

1. 先发射跳转指令，目标地址用 0 占位
2. 记录占位符在代码中的位置
3. 编译完 then 分支后，将占位符替换为正确的目标地址

```python
def _emit_jump(self, opcode: int) -> int:
    self._emit(opcode)
    pos = len(self._chunk.code)
    self._emit(0)  # 占位符
    return pos

def _patch_jump(self, pos: int):
    self._chunk.code[pos] = len(self._chunk.code)
```

### 12.5.6 短路求值

`and` 和 `or` 运算符使用短路求值，避免不必要的计算：

```
a and b:
  <编译 a>
  DUP                    # 复制 a 的值
  JUMP_IF_FALSE end      # 如果 a 为假，跳到 end（保留 a）
  POP                    # 弹出 a
  <编译 b>               # 压入 b
end:
  # 栈顶是结果

a or b:
  <编译 a>
  DUP
  JUMP_IF_TRUE end       # 如果 a 为真，跳到 end（保留 a）
  POP
  <编译 b>
end:
```

### 12.5.7 函数编译

函数定义时，编译器为函数体创建一个独立的 `Chunk`：

```python
def _compile_func_def(self, node):
    func_chunk = Chunk()                      # 创建新 Chunk
    self._chunk_stack.append(func_chunk)      # 切换到新 Chunk
    self._compile_stmts(node.body)            # 编译函数体
    self._emit(Opcode.LOAD_NONE)              # 隐式 return none
    self._emit(Opcode.RETURN)
    self._chunk_stack.pop()                   # 恢复原 Chunk

    func = CompiledFunction(node.name, node.params, func_chunk)
    const_idx = self._chunk.add_constant(func)
    self._emit(Opcode.LOAD_CONST, const_idx)  # 加载函数对象
    self._emit(Opcode.STORE_VAR, name_idx)    # 绑定到变量名
```

---

## 12.6 栈式虚拟机 (VM) —— 执行字节码

### 12.6.1 虚拟机架构

栈式虚拟机由以下组件构成：

```
┌─────────────────────────────────────────┐
│                   VM                     │
│                                          │
│  ┌──────────┐  ┌──────────────────────┐ │
│  │  Stack    │  │  Call Frames         │ │
│  │  (操作数)  │  │  ┌────────────────┐ │ │
│  │           │  │  │ Frame (当前函数) │ │ │
│  │  [值...]   │  │  │  ip, locals,   │ │ │
│  │           │  │  │  captured,     │ │ │
│  │           │  │  │  stack_base    │ │ │
│  │           │  │  └────────────────┘ │ │
│  │           │  │  ┌────────────────┐ │ │
│  │           │  │  │ Frame (调用者)  │ │ │
│  │           │  │  └────────────────┘ │ │
│  └──────────┘  └──────────────────────┘ │
│                                          │
│  globals: { 变量名 -> 值 }               │
│  builtins: { 函数名 -> BuiltinFunction } │
└─────────────────────────────────────────┘
```

### 12.6.2 执行循环

虚拟机的核心是一个 **取指-解码-执行** 循环：

```python
def _run_loop(self):
    while True:
        frame = self.current_frame
        opcode = chunk.code[frame.ip]  # 取指
        frame.ip += 1                   # 前进

        if opcode == Opcode.LOAD_CONST:
            idx = chunk.code[frame.ip]
            frame.ip += 1
            self.stack.append(chunk.constants[idx])

        elif opcode == Opcode.ADD:
            b = self.stack.pop()
            a = self.stack.pop()
            self.stack.append(a + b)

        # ... 其他指令
```

### 12.6.3 函数调用机制

函数调用时，VM 执行以下步骤：

```
调用 add(3, 4) 前的栈状态:
  [..., add_func, 3, 4]
                  ^^^^^^^ 参数
         ^^^^^^^^ 被调用者

1. 弹出参数: args = [3, 4]
2. 弹出被调用者: callee = add_func
3. 创建新 CallFrame:
   - locals = {"a": 3, "b": 4}
   - captured = (闭包捕获的变量)
   - stack_base = 当前栈位置
4. 压入调用栈

函数执行完毕后:
5. 弹出返回值
6. 弹出 CallFrame
7. 清理栈到调用前的位置
8. 压入返回值
```

### 12.6.4 变量解析链

VM 中变量的查找顺序：

```
LOAD_VAR "x":

1. frame.locals   —— 当前函数的局部变量
   找到 => 返回值

2. frame.captured —— 闭包捕获的变量
   找到 => 返回值

3. vm.globals     —— 全局变量
   找到 => 返回值

4. 都没找到 => 报错 "未定义的变量"
```

赋值时的查找顺序类似，但如果变量不存在于任何层，则默认存入局部变量。

### 12.6.5 闭包在 VM 中的工作方式

闭包捕获的变量通过 **引用**（而非拷贝）传递。这意味着多个闭包可以共享同一个变量：

```python
func make_counter() {
    let count = 0;
    func increment() {
        count = count + 1;  # 修改的是闭包捕获的 count
        return count;
    }
    return increment;
}

let c = make_counter();
print(c());  // 1
print(c());  # 2 —— count 在调用间保持状态
```

VM 实现中，闭包的 `captured` 字典存储变量的引用。当 `increment` 修改 `count` 时，修改的是同一个字典中的值。

---

## 12.7 扩展与进阶

### 12.7.1 语言扩展建议

以下是一些可以尝试的语言扩展，按难度递增排列：

**入门级**：
1. **字符串插值**：`f"Hello, {name}!"`
2. **多行注释**：`/* ... */`
3. **增强赋值**：`x += 1`、`x *= 2`
4. **三元表达式**：`x > 0 ? "正" : "非正"`

**中级**：
5. **类和对象**：`class Point { ... }`
6. **字典类型**：`let m = {"key": "value"};`
7. **异常处理**：`try { ... } catch(e) { ... }`
8. **模块系统**：`import "math.tl";`

**高级**：
9. **尾调用优化**：避免递归栈溢出
10. **垃圾回收**：自动内存管理
11. **类型检查器**：静态类型系统
12. **JIT 编译**：即时编译为机器码

### 12.7.2 性能优化方向

1. **内联缓存**：缓存变量查找结果
2. **常量折叠**：编译期计算常量表达式
3. **寄存器式虚拟机**：减少栈操作开销
4. **直接线程化**：减少指令分派开销

### 12.7.3 推荐阅读

- *Crafting Interpreters* by Robert Nystrom —— 最好的编译器入门书
- *Writing An Interpreter In Go* by Thorsten Ball —— 动手写解释器
- *Compilers: Principles, Techniques, and Tools* (龙书) —— 经典教材
- *Engineering a Compiler* by Cooper & Torczon —— 工程导向

### 12.7.4 总结

通过本章，你已经了解了编程语言的完整执行流程：

```
源代码 ──词法分析──> Token 序列 ──语法分析──> AST
                                              │
                        ┌─────────────────────┤
                        │                     │
                   树遍历解释器           字节码编译器
                   (直接执行AST)              │
                                         字节码指令
                                              │
                                         栈式虚拟机
                                        (执行字节码)
```

每个阶段都有其对应的理论基础和工程实践。掌握了这些，你就拥有了理解任何编程语言实现的能力。
