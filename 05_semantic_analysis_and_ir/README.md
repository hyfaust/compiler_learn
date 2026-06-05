# 第五章：语义分析与中间代码生成

## 5.1 语义分析概述

语义分析（Semantic Analysis）是编译器前端的第三个阶段，位于词法分析和语法分析之后。语法分析只检查程序的**结构是否合法**，而语义分析则检查程序的**含义是否正确**。

### 5.1.1 语义分析的核心职责

| 职责 | 说明 | 示例 |
|------|------|------|
| 类型检查 | 验证表达式中的类型是否兼容 | `int + string` 应报错 |
| 作用域分析 | 确定每个标识符的可见范围 | 变量是否在当前作用域内可访问 |
| 声明检查 | 确保变量/函数使用前已声明 | 使用未声明的变量应报错 |
| 函数调用检查 | 验证实参与形参的匹配 | 参数数量、类型是否一致 |
| 控制流检查 | 验证控制流的合法性 | `break` 是否在循环内、`return` 是否匹配返回类型 |

### 5.1.2 语义分析与属性文法

语义分析通常基于**属性文法（Attribute Grammar）**来实现。属性文法在上下文无关文法的基础上，为每个文法符号关联**属性**，并为每个产生式关联**语义规则**。

- **综合属性（Synthesized Attribute）**：从子节点向父节点传递信息。例如，表达式 `3 + 5` 中，子节点 `3` 和 `5` 的类型都是 `int`，综合得到父节点 `+` 的结果类型也是 `int`。
- **继承属性（Inherited Attribute）**：从父节点或兄弟节点向子节点传递信息。例如，在变量声明 `int x` 中，类型 `int` 从父节点传递给标识符 `x`。

```
        Expr (type=int, val=8)
       /    |      \
    Expr   '+'    Expr
  (type=int,  |  (type=int,
   val=3)         val=5)
    |
   '3'            '5'
```

### 5.1.3 语义分析在编译器中的位置

```
源代码
  │
  ▼
┌──────────────┐
│ 词法分析器   │ ──→ Token 流
└──────────────┘
  │
  ▼
┌──────────────┐
│ 语法分析器   │ ──→ 语法树 (AST)
└──────────────┘
  │
  ▼
┌──────────────┐     ┌────────────┐
│ 语义分析器   │ ──→ │ 带标注的AST │
└──────────────┘     └────────────┘
  │                      │
  │  ← 符号表交互 →      │
  ▼
┌──────────────┐
│ 中间代码生成 │ ──→ IR (三地址码/SSA/字节码)
└──────────────┘
```

---

## 5.2 类型系统详解

### 5.2.1 类型系统的分类

类型系统可以从两个维度进行分类：

#### 静态类型 vs 动态类型

| 特性 | 静态类型（Static Typing） | 动态类型（Dynamic Typing） |
|------|--------------------------|--------------------------|
| 类型检查时机 | 编译时 | 运行时 |
| 典型语言 | C, C++, Java, Rust | Python, JavaScript, Ruby |
| 优点 | 提前发现类型错误，运行效率高 | 灵活性高，开发速度快 |
| 缺点 | 代码冗长（可被类型推导缓解） | 运行时类型错误 |

```c
// C语言：静态类型 — 编译时检查
int x = 10;       // OK
x = "hello";      // 编译错误：类型不兼容
```

```python
# Python：动态类型 — 运行时检查
x = 10            # OK
x = "hello"       # OK，运行时才确定类型
x + 1             # 运行时错误：str + int 不支持
```

#### 强类型 vs 弱类型

| 特性 | 强类型（Strong Typing） | 弱类型（Weak Typing） |
|------|------------------------|----------------------|
| 隐式转换 | 不允许或极少 | 频繁自动转换 |
| 典型语言 | Python, Java, Rust | C, JavaScript, PHP |
| 优点 | 类型安全，行为可预测 | 代码简洁（但可能引入隐含bug） |
| 缺点 | 需要显式转换 | 隐式转换可能产生意外结果 |

```c
// C语言：弱类型 — 隐式转换
int x = 10;
double y = x;           // OK，int 隐式转为 double
char c = 65;            // OK，int 隐式转为 char
```

```python
# Python：强类型 — 无隐式转换
x = 10
y = "hello"
result = x + y          # TypeError: unsupported operand type(s)
result = str(x) + y     # 必须显式转换
```

#### 四象限分类图

```
              强类型                  弱类型
         ┌─────────────────┬─────────────────┐
  静态   │   Haskell       │   C             │
  类型   │   Rust          │   C++           │
         │   Java          │   Go            │
         ├─────────────────┼─────────────────┤
  动态   │   Python        │   JavaScript    │
  类型   │   Ruby          │   PHP           │
         │   Erlang        │   Perl          │
         └─────────────────┴─────────────────┘
```

### 5.2.2 类型推导（Type Inference）

类型推导是编译器自动推断表达式类型的能力，无需程序员显式标注。

#### Hindley-Milner 类型推导算法

Hindley-Milner（HM）类型系统是 ML、Haskell 等语言的基础。其核心算法是 **Algorithm W**，基于**合一（Unification）**操作。

基本思想：
1. 为每个表达式的类型创建类型变量（如 `α`, `β`）
2. 根据语言规则生成类型约束
3. 通过合一算法求解约束，得到每个变量的具体类型

```
示例：推导 let id = fun x -> x 的类型

1. 为参数 x 引入类型变量 α
2. 函数体返回 x，类型为 α
3. 因此 id 的类型为 α → α
4. 多态化后：∀α. α → α
```

#### 简化的类型推导示例（Python 伪代码）

```python
# 输入表达式：let x = 5 + 3

# 步骤1：为子表达式分配类型变量
#   5 : t1
#   3 : t2
#   + : t3 → t4 → t5
#   x : t6

# 步骤2：生成约束
#   t1 = int          (字面量5的类型)
#   t2 = int          (字面量3的类型)
#   t3 = int          (+的左操作数)
#   t4 = int          (+的右操作数)
#   t5 = int          (+的返回类型，因为int+int→int)
#   t6 = t5           (赋值)

# 步骤3：求解
#   t1=int, t2=int, t3=int, t4=int, t5=int, t6=int
#   结论：x 的类型为 int
```

### 5.2.3 常见类型表示方法

在编译器内部，类型通常用以下数据结构表示：

```c
// C语言中的类型表示（简化版）
typedef enum {
    TYPE_INT,
    TYPE_FLOAT,
    TYPE_CHAR,
    TYPE_BOOL,
    TYPE_STRING,
    TYPE_VOID,
    TYPE_ARRAY,
    TYPE_POINTER,
    TYPE_FUNCTION,
    TYPE_STRUCT,
} TypeKind;

typedef struct Type {
    TypeKind kind;
    union {
        struct { struct Type *element; int size; } array;     // 数组
        struct { struct Type *pointee; } pointer;             // 指针
        struct { struct Type *return_type; 
                 struct Type **params; int param_count; } func; // 函数
        struct { char *name; struct Field *fields; int count; } struct_type;
    };
} Type;
```

---

## 5.3 符号表详解

### 5.3.1 符号表的作用

符号表（Symbol Table）是编译器中最核心的数据结构之一，用于存储程序中所有**标识符**（变量、函数、类型等）的信息。

符号表需要支持的核心操作：

| 操作 | 时间复杂度要求 | 说明 |
|------|---------------|------|
| `insert(name, info)` | O(1) 平均 | 插入新的符号条目 |
| `lookup(name)` | O(1) 平均 | 查找符号信息 |
| `enter_scope()` | O(1) | 进入新的作用域 |
| `exit_scope()` | O(1) | 退出当前作用域 |

### 5.3.2 基于哈希表的实现

哈希表是实现符号表最常用的数据结构，提供 O(1) 平均查找/插入性能。

```
符号表结构示意：

  ┌──────────────────────────────────────┐
  │           哈希表 (HashTable)          │
  │                                      │
  │  Bucket 0: [ ]                       │
  │  Bucket 1: [x:int] → [count:float]  │
  │  Bucket 2: [ ]                       │
  │  Bucket 3: [main:func]              │
  │  Bucket 4: [y:int]                  │
  │  ...                                 │
  │  Bucket N: [ ]                       │
  └──────────────────────────────────────┘
  
  每个 SymbolEntry 包含：
  ┌────────────────────────────────┐
  │ name: string        // 标识符名 │
  │ kind: VAR/FUNC/TYPE  // 符号种类 │
  │ type: Type           // 类型信息 │
  │ scope_level: int     // 作用域层级│
  │ line: int            // 声明行号  │
  │ ...                            │
  └────────────────────────────────┘
```

### 5.3.3 作用域链

当使用哈希表实现时，嵌套作用域通过**作用域链**来管理。每个作用域都有一个指向外层作用域的指针：

```
作用域链示意：

  全局作用域 (level 0)
  ┌─────────────────────────┐
  │ x: int                  │
  │ main: func              │
  │                         │
  │  ┌────────────────────┐ │  ← main函数作用域 (level 1)
  │  │ a: int             │ │
  │  │ b: int             │ │
  │  │                    │ │
  │  │  ┌───────────────┐ │ │  ← if块作用域 (level 2)
  │  │  │ c: int        │ │ │
  │  │  │ temp: int     │ │ │
  │  │  └───────────────┘ │ │
  │  └────────────────────┘ │
  └─────────────────────────┘

  查找变量 c 的过程（在 if 块内）：
  1. 在 level 2 的表中查找 → 找到！
  
  查找变量 a 的过程（在 if 块内）：
  1. 在 level 2 的表中查找 → 未找到
  2. 沿作用域链到 level 1 的表中查找 → 找到！
```

### 5.3.4 符号表的 C 语言数据结构实现

```c
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define HASH_SIZE 256

// 符号种类
typedef enum {
    SYMBOL_VARIABLE,
    SYMBOL_FUNCTION,
    SYMBOL_TYPE,
    SYMBOL_CONSTANT,
} SymbolKind;

// 符号条目
typedef struct SymbolEntry {
    char *name;
    SymbolKind kind;
    char *type_name;           // 简化：用字符串表示类型
    int scope_level;
    int line_number;
    // 函数特有信息
    int param_count;
    char **param_types;
    struct SymbolEntry *next;  // 哈希冲突链
} SymbolEntry;

// 符号表
typedef struct SymbolTable {
    SymbolEntry *buckets[HASH_SIZE];
    int current_scope;
    struct SymbolTable *parent;  // 作用域链：指向外层符号表
} SymbolTable;

// 哈希函数
unsigned int hash(const char *name) {
    unsigned int h = 0;
    while (*name) {
        h = h * 31 + (unsigned char)*name;
        name++;
    }
    return h % HASH_SIZE;
}

// 创建符号表
SymbolTable *create_symbol_table(SymbolTable *parent) {
    SymbolTable *table = calloc(1, sizeof(SymbolTable));
    table->current_scope = parent ? parent->current_scope + 1 : 0;
    table->parent = parent;
    return table;
}

// 查找符号（仅在当前作用域）
SymbolEntry *lookup_local(SymbolTable *table, const char *name) {
    unsigned int idx = hash(name);
    SymbolEntry *entry = table->buckets[idx];
    while (entry) {
        if (strcmp(entry->name, name) == 0 &&
            entry->scope_level == table->current_scope) {
            return entry;
        }
        entry = entry->next;
    }
    return NULL;
}

// 查找符号（沿作用域链向上查找）
SymbolEntry *lookup(SymbolTable *table, const char *name) {
    SymbolTable *current = table;
    while (current) {
        unsigned int idx = hash(name);
        SymbolEntry *entry = current->buckets[idx];
        while (entry) {
            if (strcmp(entry->name, name) == 0) {
                return entry;
            }
            entry = entry->next;
        }
        current = current->parent;
    }
    return NULL;
}

// 插入符号
int insert_symbol(SymbolTable *table, const char *name,
                  SymbolKind kind, const char *type_name, int line) {
    // 检查当前作用域是否已存在
    if (lookup_local(table, name)) {
        fprintf(stderr, "Error: '%s' already declared in current scope\n", name);
        return 0;
    }
    SymbolEntry *entry = calloc(1, sizeof(SymbolEntry));
    entry->name = strdup(name);
    entry->kind = kind;
    entry->type_name = strdup(type_name);
    entry->scope_level = table->current_scope;
    entry->line_number = line;
    unsigned int idx = hash(name);
    entry->next = table->buckets[idx];
    table->buckets[idx] = entry;
    return 1;
}

// 进入新作用域
SymbolTable *enter_scope(SymbolTable *table) {
    return create_symbol_table(table);
}

// 退出作用域
SymbolTable *exit_scope(SymbolTable *table) {
    SymbolTable *parent = table->parent;
    // 实际编译器中需要释放table的资源
    return parent;
}

// 打印符号表（调试用）
void print_symbol_table(SymbolTable *table) {
    printf("=== Symbol Table (scope level %d) ===\n", table->current_scope);
    for (int i = 0; i < HASH_SIZE; i++) {
        SymbolEntry *entry = table->buckets[i];
        while (entry) {
            printf("  [%d] %s: kind=%d, type=%s, line=%d\n",
                   i, entry->name, entry->kind, entry->type_name,
                   entry->line_number);
            entry = entry->next;
        }
    }
    printf("=====================================\n");
}
```

### 5.3.5 符号表的典型使用流程

```
处理代码：
  int x = 5;           // 在全局作用域插入 (x, int)
  void foo(int a) {    // 在全局作用域插入 (foo, func)
                         // 进入新作用域，插入 (a, int)
    int b = a + 1;     // 在局部作用域插入 (b, int)
    {                   // 进入新作用域
      int c = b * 2;   // 在内层作用域插入 (c, int)
    }                   // 退出内层作用域（c 被销毁）
  }                     // 退出 foo 作用域（a, b 被销毁）
```

---

## 5.4 语义分析任务详解

### 5.4.1 类型检查

类型检查是语义分析中最核心的任务。它验证每个表达式中的操作数类型是否与操作符兼容。

#### 类型检查规则示例

```
类型检查规则（类型推导规则的写法）：

  ─────────────────
  n : int            (整数字面量)

  ─────────────────
  x : T              (变量引用，T来自符号表)

  e1 : int   e2 : int
  ─────────────────────
  e1 + e2 : int       (整数加法)

  e1 : float  e2 : float
  ────────────────────────
  e1 + e2 : float    (浮点加法)

  e1 : int   e2 : int
  ─────────────────────
  e1 < e2 : bool     (比较运算)

  e : bool   s1 : T   s2 : T
  ────────────────────────────
  if e then s1 else s2 : T   (条件表达式)
```

#### 类型检查器实现示例

```python
class TypeChecker:
    """类型检查器示例"""

    # 类型兼容性矩阵
    BINARY_OP_TYPES = {
        ('+', 'int', 'int'): 'int',
        ('+', 'float', 'float'): 'float',
        ('+', 'int', 'float'): 'float',   # 隐式类型提升
        ('+', 'float', 'int'): 'float',
        ('+', 'string', 'string'): 'string',  # 字符串拼接
        ('-', 'int', 'int'): 'int',
        ('-', 'float', 'float'): 'float',
        ('*', 'int', 'int'): 'int',
        ('/', 'int', 'int'): 'int',        # 整数除法
        ('/', 'float', 'float'): 'float',
        ('<', 'int', 'int'): 'bool',
        ('<', 'float', 'float'): 'bool',
        ('==', 'int', 'int'): 'bool',
        ('==', 'bool', 'bool'): 'bool',
        ('&&', 'bool', 'bool'): 'bool',
        ('||', 'bool', 'bool'): 'bool',
    }

    def check_binary_op(self, op, left_type, right_type):
        key = (op, left_type, right_type)
        if key in self.BINARY_OP_TYPES:
            return self.BINARY_OP_TYPES[key]
        raise TypeError(
            f"不支持的操作: {left_type} {op} {right_type}"
        )

    def check_assignment(self, target_type, value_type):
        """检查赋值的类型兼容性"""
        if target_type == value_type:
            return True
        # 允许的隐式转换
        if target_type == 'float' and value_type == 'int':
            return True
        raise TypeError(
            f"无法将 {value_type} 赋值给 {target_type}"
        )
```

#### 类型提升（Type Promotion）

当二元运算的两个操作数类型不同时，编译器需要将较低精度的类型提升为较高精度：

```
类型提升层级：

  bool → char → short → int → long → float → double → long double

  示例：
  int a = 5;
  double b = 3.14;
  double result = a + b;   // a 被提升为 double，结果为 double

  // 编译器生成的等价代码：
  // double result = (double)a + b;
```

### 5.4.2 作用域分析

作用域分析确保标识符在其合法的作用域内被访问。

#### 静态作用域 vs 动态作用域

| 特性 | 静态作用域（Lexical Scope） | 动态作用域（Dynamic Scope） |
|------|---------------------------|---------------------------|
| 绑定时机 | 编译时，根据代码的词法结构 | 运行时，根据调用栈 |
| 典型语言 | C, C++, Java, Python, JS | Emacs Lisp, Bash（部分） |
| 可预测性 | 高（看代码即可确定） | 低（依赖运行时调用路径） |

```python
# 静态作用域示例（Python）
x = 10

def foo():
    print(x)   # 查找外层作用域，找到全局的 x = 10

def bar():
    x = 20
    foo()      # 即使 bar 中定义了 x=20，foo 中的 x 仍然绑定到全局的 10

bar()          # 输出 10（静态作用域）
               # 如果是动态作用域，会输出 20
```

#### 作用域分析的实现

```python
class ScopeAnalyzer:
    """作用域分析器"""

    def __init__(self):
        self.scope_stack = [{}]  # 作用域栈，第一个是全局作用域

    def enter_scope(self):
        """进入新作用域"""
        self.scope_stack.append({})

    def exit_scope(self):
        """退出当前作用域"""
        if len(self.scope_stack) <= 1:
            raise RuntimeError("无法退出全局作用域")
        self.scope_stack.pop()

    def declare(self, name, info):
        """在当前作用域声明标识符"""
        current = self.scope_stack[-1]
        if name in current:
            raise SyntaxError(f"标识符 '{name}' 在当前作用域中已声明")
        current[name] = info

    def resolve(self, name):
        """沿作用域链查找标识符"""
        for scope in reversed(self.scope_stack):
            if name in scope:
                return scope[name]
        raise NameError(f"标识符 '{name}' 未定义")

    def current_depth(self):
        return len(self.scope_stack) - 1
```

### 5.4.3 变量声明检查

变量声明检查确保：
1. 变量在使用前已被声明
2. 变量在同一作用域内不被重复声明
3. 常量不能被重新赋值
4. 变量的类型合法

```python
class DeclarationChecker:
    """变量声明检查器"""

    def check_use_before_declaration(self, name, scope):
        """检查变量是否在声明前使用"""
        entry = scope.resolve(name)
        if entry is None:
            raise NameError(f"变量 '{name}' 未声明")

    def check_duplicate_declaration(self, name, current_scope):
        """检查重复声明"""
        if name in current_scope:
            raise SyntaxError(f"变量 '{name}' 重复声明")

    def check_const_assignment(self, name, scope):
        """检查是否对常量赋值"""
        entry = scope.resolve(name)
        if entry and entry.get('is_const'):
            raise TypeError(f"不能对常量 '{name}' 赋值")

    def check_type_validity(self, type_name, known_types):
        """检查类型是否合法"""
        if type_name not in known_types:
            raise TypeError(f"未知类型 '{type_name}'")
```

### 5.4.4 函数调用检查

函数调用检查验证：
1. 函数已被声明
2. 参数数量匹配
3. 参数类型匹配
4. 返回值类型正确使用

```python
class FunctionCallChecker:
    """函数调用检查器"""

    def check_call(self, func_entry, args):
        """
        检查函数调用的合法性
        func_entry: 符号表中的函数条目
        args: 实际参数列表（带类型信息）
        """
        # 1. 检查是否是函数
        if func_entry.kind != 'function':
            raise TypeError(f"'{func_entry.name}' 不是函数")

        # 2. 检查参数数量
        expected = func_entry.param_count
        actual = len(args)
        if expected != actual:
            raise TypeError(
                f"函数 '{func_entry.name}' 需要 {expected} 个参数，"
                f"但传入了 {actual} 个"
            )

        # 3. 检查参数类型
        for i, (param_type, arg_type) in enumerate(
            zip(func_entry.param_types, [a.type for a in args])
        ):
            if not self.is_compatible(param_type, arg_type):
                raise TypeError(
                    f"函数 '{func_entry.name}' 的第 {i+1} 个参数"
                    f"期望类型 {param_type}，但传入了 {arg_type}"
                )

    def is_compatible(self, expected, actual):
        """检查类型兼容性"""
        if expected == actual:
            return True
        # int -> float 隐式转换
        if expected == 'float' and actual == 'int':
            return True
        return False
```

### 5.4.5 控制流检查

控制流检查确保程序的控制结构使用正确。

#### 常见的控制流检查

| 检查项 | 说明 | 示例 |
|--------|------|------|
| break/continue 位置 | 必须在循环内 | `if (...) { break; }` 应报错 |
| return 语句 | 函数所有路径必须有返回值 | `int f() { if(x) return 1; }` 应告警 |
| 不可达代码 | return/break 之后的代码 | `return 1; x = 2;` 应告警 |
| switch 穿透 | case 是否缺少 break | 需要明确的穿透意图 |

```python
class ControlFlowChecker:
    """控制流检查器"""

    def __init__(self):
        self.in_loop = 0       # 嵌套循环深度
        self.in_switch = 0     # 嵌套 switch 深度
        self.return_type = None # 当前函数返回类型
        self.has_return = False # 当前路径是否有 return

    def enter_loop(self):
        self.in_loop += 1

    def exit_loop(self):
        self.in_loop -= 1
        if self.in_loop < 0:
            self.in_loop = 0

    def check_break(self):
        """检查 break 是否在循环/switch 内"""
        if self.in_loop == 0 and self.in_switch == 0:
            raise SyntaxError("'break' 语句不在循环或 switch 内")

    def check_continue(self):
        """检查 continue 是否在循环内"""
        if self.in_loop == 0:
            raise SyntaxError("'continue' 语句不在循环内")

    def check_return(self, expr_type=None):
        """检查 return 语句的类型"""
        if self.return_type == 'void' and expr_type is not None:
            raise TypeError("void 函数中不应有返回值")
        if self.return_type != 'void' and expr_type is None:
            raise TypeError(f"函数应返回 {self.return_type} 类型的值")
        if expr_type and not self.type_compatible(self.return_type, expr_type):
            raise TypeError(
                f"返回类型不匹配: 期望 {self.return_type}, 得到 {expr_type}"
            )
        self.has_return = True

    def check_all_paths_return(self, body_has_return):
        """检查所有执行路径都有返回值"""
        if self.return_type != 'void' and not body_has_return:
            raise SyntaxError("函数可能没有返回值")

    def type_compatible(self, expected, actual):
        return expected == actual or \
               (expected == 'float' and actual == 'int')
```

---

## 5.5 中间表示（IR）

### 5.5.1 为什么需要中间表示

直接从 AST 生成目标代码存在以下问题：

1. **前端和后端紧耦合**：每种源语言需要为每种目标机器写一个翻译器（M×N 问题）
2. **优化困难**：AST 结构复杂，难以做全局优化
3. **代码复用困难**：不同语言的优化逻辑难以共享

引入 IR 可以将问题分解为：
- 前端：源语言 → IR（M 个翻译器）
- 后端：IR → 目标代码（N 个翻译器）
- 总计 M + N 而非 M × N

```
                    ┌─── C ──→ C前端 ─┐
                    │                  │
                    ├─── Java ─→ Java前端 ─┤     ┌──── x86后端 ──→ x86机器码
                    │                  ├──→ IR ─┤
                    └─── Python → Python前端 ─┘     ├──── ARM后端 ──→ ARM机器码
                                                    │
                                                    └──── RISC-V后端 → RISC-V机器码
```

### 5.5.2 三地址码（Three-Address Code, TAC）

三地址码是最基本的 IR 形式。每条指令最多包含三个"地址"（操作数），格式为：

```
x = y op z
```

#### 三地址码的指令类型

| 指令格式 | 示例 | 说明 |
|----------|------|------|
| `x = y op z` | `t1 = a + b` | 二元运算 |
| `x = op y` | `t1 = -a` | 一元运算 |
| `x = y` | `a = b` | 赋值/复制 |
| `if x goto L` | `if t1 goto L3` | 条件跳转 |
| `ifFalse x goto L` | `ifFalse t1 goto L5` | 条件跳转（假） |
| `goto L` | `goto L2` | 无条件跳转 |
| `label L` | `L1:` | 标签 |
| `x = y[i]` | `t1 = a[4]` | 数组读取 |
| `x[i] = y` | `a[4] = t1` | 数组写入 |
| `x = &y` | `t1 = &a` | 取地址 |
| `x = *y` | `t1 = *p` | 解引用 |
| `param x` | `param t1` | 函数参数 |
| `call f, n` | `call foo, 3` | 函数调用 |
| `return x` | `return t1` | 函数返回 |

#### 三地址码示例

源代码：
```c
// 源代码
if (a > b) {
    x = a + b * 2;
} else {
    x = a - b;
}
y = x + 1;
```

生成的三地址码：
```
L0: if a > b goto L1       // 条件判断
    goto L2                  // 跳到 else 分支
L1: t1 = b * 2             // then 分支
    t2 = a + t1
    x = t2
    goto L3                  // 跳过 else 分支
L2: t3 = a - b             // else 分支
    x = t3
L3: t4 = x + 1             // 后续代码
    y = t4
```

#### 三地址码的内部表示

```python
# 三地址码指令的内部表示
class TACInstruction:
    """
    三地址码指令
    
    属性:
        op: 操作符 (如 '+', '-', '*', 'goto', 'if', 'label', 'call' 等)
        result: 结果变量
        arg1: 第一个操作数
        arg2: 第二个操作数（一元操作时为 None）
    """
    def __init__(self, op, result=None, arg1=None, arg2=None):
        self.op = op
        self.result = result
        self.arg1 = arg1
        self.arg2 = arg2
    
    def __str__(self):
        if self.op == 'label':
            return f"{self.result}:"
        elif self.op == 'goto':
            return f"goto {self.result}"
        elif self.op == 'if':
            return f"if {self.arg1} goto {self.result}"
        elif self.op == 'ifFalse':
            return f"ifFalse {self.arg1} goto {self.result}"
        elif self.op == 'param':
            return f"param {self.arg1}"
        elif self.op == 'call':
            return f"call {self.arg1}, {self.arg2}"
        elif self.op == 'return':
            return f"return {self.arg1}"
        elif self.op == '=':
            return f"{self.result} = {self.arg1}"
        elif self.arg2:
            return f"{self.result} = {self.arg1} {self.op} {self.arg2}"
        else:
            return f"{self.result} = {self.op} {self.arg1}"
```

### 5.5.3 SSA（静态单赋值形式）

SSA（Static Single Assignment）是一种特殊的 IR 形式，其中**每个变量只被赋值一次**。SSA 极大简化了许多编译优化。

#### SSA 的核心特性

**规则**：在 SSA 中，每个变量只有一次定义（赋值）。当一个变量在不同控制流路径中被赋值时，需要引入新的版本号。

#### φ 函数（Phi Function）

当控制流汇合时，需要使用 **φ 函数** 来选择正确的变量版本。

```
原始代码（非 SSA）：          SSA 形式：
                              
  x = 1                       x1 = 1
  if (cond) {                 if (cond) {
    x = 2                       x2 = 2
  }                           }
  y = x + 1                   x3 = φ(x1, x2)
                               y1 = x3 + 1
```

#### SSA 转换的完整示例

```
原始三地址码：                     SSA 形式：

  x = 0                              x1 = 0
  y = 1                              y1 = 1
L1:                                  L1:
  if x > 10 goto L2                    if x1 > 10 goto L2
  t1 = x + y                            t1 = x1 + y1
  x = t1                                 x2 = t1
  t2 = y * 2                             t2 = y1 * 2
  y = t2                                 y2 = t2
  goto L1                                goto L1
L2:                                  L2:
  z = x + y                            x3 = φ(x1, x2)   ← 循环头
  print(z)                              y3 = φ(y1, y2)   ← 循环头
                                        z1 = x3 + y3
                                        print(z1)
```

#### SSA 的优势

SSA 使得以下优化变得简单：

1. **常量传播（Constant Propagation）**：
   ```
   x1 = 5
   y1 = x1 + 3    →  y1 = 8  （因为 x1 恒为 5）
   ```

2. **死代码消除（Dead Code Elimination）**：
   ```
   x1 = 5       →  删除（x1 从未被使用）
   x2 = 10
   y1 = x2
   ```

3. **公共子表达式消除（CSE）**：
   ```
   a1 = x1 + y1
   b1 = x1 + y1    →  b1 = a1  （相同表达式已计算过）
   ```

4. **寄存器分配**：SSA 中变量的"活跃区间"更容易分析。

### 5.5.4 字节码（Bytecode）

字节码是一种面向虚拟机的 IR，通常使用**紧凑的二进制编码**。

#### 字节码与三地址码的对比

| 特性 | 三地址码 | 字节码 |
|------|---------|--------|
| 表示形式 | 文本/符号 | 二进制/紧凑编码 |
| 主要用途 | 编译器中间优化 | 虚拟机执行 |
| 操作模型 | 寄存器模型 | 栈模型（多数） |
| 目标受众 | 编译器开发者 | VM 执行引擎 |

#### 栈式字节码示例

```
源代码: x = (a + b) * (c - d)

栈式字节码（如 JVM, CPython bytecode）：
  LOAD a          // 栈: [a]
  LOAD b          // 栈: [a, b]
  ADD             // 栈: [a+b]
  LOAD c          // 栈: [a+b, c]
  LOAD d          // 栈: [a+b, c, d]
  SUB             // 栈: [a+b, c-d]
  MUL             // 栈: [(a+b)*(c-d)]
  STORE x         // 栈: []

寄存器式字节码（如 Lua, Dalvik）：
  ADD  R0, a, b    // R0 = a + b
  SUB  R1, c, d    // R1 = c - d
  MUL  x, R0, R1   // x = R0 * R1
```

#### Python 字节码示例

```python
import dis

def example(a, b):
    x = a + b
    y = x * 2
    if y > 10:
        return y
    return 0

dis.dis(example)
```

输出：
```
  2           0 LOAD_FAST                0 (a)
              2 LOAD_FAST                1 (b)
              4 BINARY_ADD
              6 STORE_FAST               2 (x)

  3           8 LOAD_FAST                2 (x)
             10 LOAD_CONST               1 (2)
             12 BINARY_MULTIPLY
             14 STORE_FAST               3 (y)

  4          16 LOAD_FAST                3 (y)
             18 LOAD_CONST               2 (10)
             20 COMPARE_OP               4 (>)
             22 POP_JUMP_IF_FALSE       28

  5          24 LOAD_FAST                3 (y)
             26 RETURN_VALUE

  6     >>   28 LOAD_CONST               3 (0)
             30 RETURN_VALUE
```

---

## 5.6 AST 到 IR 的翻译

### 5.6.1 翻译的基本策略

将 AST 翻译为三地址码的核心思想是**递归下降**：对每个 AST 节点递归地生成 IR 代码，返回该节点结果所在的"地址"（变量名或临时变量）。

#### 表达式翻译

```python
class IRTranslator:
    """AST 到三地址码的翻译器"""
    
    def __init__(self):
        self.instructions = []
        self.temp_count = 0
        self.label_count = 0
    
    def new_temp(self):
        """生成新的临时变量"""
        self.temp_count += 1
        return f"t{self.temp_count}"
    
    def new_label(self):
        """生成新的标签"""
        self.label_count += 1
        return f"L{self.label_count}"
    
    def emit(self, op, result=None, arg1=None, arg2=None):
        """生成一条三地址码指令"""
        self.instructions.append((op, result, arg1, arg2))
    
    def translate_expr(self, node):
        """翻译表达式节点，返回结果所在的地址"""
        
        if node.type == 'NUMBER':
            # 数字字面量：直接返回值
            return str(node.value)
        
        elif node.type == 'ID':
            # 变量引用：直接返回变量名
            return node.name
        
        elif node.type == 'BINOP':
            # 二元运算：递归翻译两个操作数
            left_addr = self.translate_expr(node.left)
            right_addr = self.translate_expr(node.right)
            temp = self.new_temp()
            self.emit(node.op, temp, left_addr, right_addr)
            return temp
        
        elif node.type == 'UNARY':
            # 一元运算
            operand_addr = self.translate_expr(node.operand)
            temp = self.new_temp()
            self.emit(node.op, temp, operand_addr)
            return temp
        
        elif node.type == 'CALL':
            # 函数调用
            arg_addrs = [self.translate_expr(arg) for arg in node.args]
            for addr in arg_addrs:
                self.emit('param', None, addr)
            temp = self.new_temp()
            self.emit('call', temp, node.name, str(len(arg_addrs)))
            return temp
    
    def translate_stmt(self, node):
        """翻译语句节点"""
        
        if node.type == 'ASSIGN':
            # 赋值语句
            addr = self.translate_expr(node.value)
            self.emit('=', node.target, addr)
        
        elif node.type == 'IF':
            # if 语句
            cond_addr = self.translate_expr(node.condition)
            else_label = self.new_label()
            end_label = self.new_label()
            
            self.emit('ifFalse', else_label, cond_addr)
            self.translate_stmt(node.then_body)
            
            if node.else_body:
                self.emit('goto', end_label)
                self.emit('label', else_label)
                self.translate_stmt(node.else_body)
                self.emit('label', end_label)
            else:
                self.emit('label', else_label)
        
        elif node.type == 'WHILE':
            # while 循环
            loop_label = self.new_label()
            end_label = self.new_label()
            
            self.emit('label', loop_label)
            cond_addr = self.translate_expr(node.condition)
            self.emit('ifFalse', end_label, cond_addr)
            self.translate_stmt(node.body)
            self.emit('goto', loop_label)
            self.emit('label', end_label)
        
        elif node.type == 'BLOCK':
            # 语句块
            for stmt in node.statements:
                self.translate_stmt(stmt)
        
        elif node.type == 'RETURN':
            # 返回语句
            if node.value:
                addr = self.translate_expr(node.value)
                self.emit('return', None, addr)
            else:
                self.emit('return')
```

### 5.6.2 if-else 的翻译策略

```
源代码:                 三地址码:

if (a > b) {           L_cond:
  x = a + b;             t1 = a > b
} else {                 ifFalse t1 goto L_else
  x = a - b;             t2 = a + b
}                         x = t2
                          goto L_end
                      L_else:
                          t3 = a - b
                          x = t3
                      L_end:
```

### 5.6.3 while 循环的翻译策略

```
源代码:                 三地址码:

while (i < n) {        L_loop:
  sum = sum + i;          t1 = i < n
  i = i + 1;              ifFalse t1 goto L_end
}                          t2 = sum + i
                           sum = t2
                           t3 = i + 1
                           i = t3
                           goto L_loop
                       L_end:
```

### 5.6.4 for 循环的翻译策略

```
源代码:                 三地址码:

for (i = 0; i < n; i++) {
  sum = sum + arr[i];   i = 0
}                       L_loop:
                          t1 = i < n
                          ifFalse t1 goto L_end
                          t2 = arr[i]
                          t3 = sum + t2
                          sum = t3
                          t4 = i + 1
                          i = t4
                          goto L_loop
                        L_end:
```

### 5.6.5 短路求值的翻译

逻辑运算符 `&&` 和 `||` 应使用短路求值，不翻译为普通的二元运算：

```
源代码: if (a && b) { ... }

短路求值的三地址码:
  ifFalse a goto L_false    // a 为假则跳过
  ifFalse b goto L_false    // a 为真时再检查 b
  goto L_true
L_false:
  ... (else 部分)
L_true:
  ... (then 部分)
```

---

## 5.7 GCC 与 Python 中的实现

### 5.7.1 GCC 的语义分析

GCC（GNU Compiler Collection）的语义分析主要在 **C 前端**（`c-family/`）和 **GENERIC/GIMPLE 层**完成。

#### GCC 的类型系统实现

```c
// GCC 中的类型表示（简化）
// 文件：gcc/tree.h

// GCC 使用 tree 结构来表示所有语言构造，包括类型
// 
// tree 核心结构：
//   tree_type: 包含类型的所有信息
//     - TYPE_MAIN_VARIANT: 类型的主变体
//     - TYPE_SIZE: 类型的大小（位）
//     - TYPE_ALIGN: 类型的对齐
//     - TYPE_FIELDS: 结构体/联合体的字段链表
//     - TYPE_ARG_TYPES: 函数类型的参数类型链表

// GCC 的语义检查流程：
// 1. c_parser_declaration_or_f: 解析声明
// 2. start_decl / finish_decl: 处理变量声明
// 3. build_binary_op: 构建二元运算（含类型检查）
// 4. convert_for_assignment: 赋值时的类型转换
```

#### GCC 的符号表

```c
// GCC 使用两层符号表结构：
// 
// 1. binding_level: 表示一个作用域
//    struct binding_level {
//        tree names;          // 本作用域中声明的标识符链表
//        binding_level *superior;  // 外层作用域
//        ...
//    };
//
// 2. c_binding: 将标识符与其声明关联
//    struct c_binding {
//        tree decl;           // 声明的树节点
//        tree type;           // 类型
//        binding_level *scope; // 所属作用域
//        ...
//    };
//
// 3. identifier 节点包含指向 c_binding 的指针，
//    通过 binding 链（同名标识符在不同作用域的声明）
//    支持作用域查找。
```

#### GCC 的 IR：GENERIC 和 GIMPLE

```
GCC 的 IR 层次：

  C 源代码
    │
    ▼
  AST (tree 结构)
    │ 语义分析完成后的带类型标注的树
    ▼
  GENERIC
    │ 与语言无关的树形 IR
    ▼
  GIMPLE
    │ 三地址码形式的 IR（GCC 的核心优化层）
    │ - GIMPLE 三地址码：每个语句最多3个操作数
    │ - SSA GIMPLE：带 SSA 信息的 GIMPLE
    ▼
  RTL (Register Transfer Language)
    │ 接近机器指令的 IR
    ▼
  目标机器代码
```

### 5.7.2 CPython 的语义分析与 IR

CPython（标准 Python 实现）的编译过程相对简单，因为它不需要复杂的类型检查（动态类型语言）。

#### CPython 的编译流程

```
Python 源代码 (.py)
    │
    ▼
  Token 流
    │ Parser (pgen)
    ▼
  CST (具体语法树) → AST (抽象语法树)
    │
    ▼  语义分析（作用域分析，确定变量是 local/global/builtin）
  Symbol Table (symtable)
    │
    ▼
  字节码 (bytecode)
    │  Python/compile.c 中生成
    ▼
  .pyc 文件 / 直接在解释器中执行
```

#### CPython 的 Symbol Table

```c
// CPython 的符号表实现
// 文件：Python/symtable.c
//
// struct symtable {
//     PyObject *st_filename;     // 源文件名
//     struct _symtable_entry *st_cur;  // 当前符号表条目
//     PyObject *st_symbols;      // 所有符号表的字典
//     int st_nscopes;            // 作用域计数
// };
//
// struct _symtable_entry {
//     PyObject *ste_id;          // 标识符
//     PyObject *ste_symbols;     // 符号字典 {name: flags}
//     int ste_type;              // Module/Class/Function
//     int ste_scope;             // GLOBAL/LOCAL/FREE/CELL
//     ...
// };
//
// Python 的变量分类：
// - LOCAL: 局部变量
// - GLOBAL: 全局变量（显式声明或首次赋值）
// - FREE: 自由变量（来自外层函数，闭包）
// - CELL: 被内层函数引用的局部变量
// - BUILTIN: 内置名称
```

### 5.7.3 实际编译器中的优化 Pass

在实际编译器中，IR 优化通常由一系列 Pass（遍）组成：

```
GCC 的 GIMPLE 优化 Pass 示例：

  pass_build_ssa          // 构建 SSA 形式
  pass_dce                // 死代码消除
  pass_copy_prop          // 复制传播
  pass_ccp                // 条件常量传播
  pass_phiopt             // φ 节点优化
  pass_inline             // 函数内联
  pass_loop               // 循环优化
    ├── pass_loop_unroll    // 循环展开
    ├── pass_loop_vectorize // 循环向量化
    └── pass_loop_ivcanon   // 归纳变量规范化
  pass_tail_recursion     // 尾递归优化
  pass_expand             // GIMPLE → RTL 扩展
```

---

## 5.8 示例代码说明

本章包含三个 Python 实现文件，从不同角度演示语义分析与中间代码生成：

### 5.8.1 `semantic_analyzer.py` — 语义分析器

**功能**：实现一个完整的语义分析器，包括：

- **AST 节点定义**：自包含的 AST 节点类（`NumberNode`, `BinOpNode`, `AssignNode`, `IfNode`, `WhileNode`, `VarDeclNode`, `FuncDeclNode`, `BlockNode` 等）
- **SymbolTable 类**：支持嵌套作用域的符号表，基于 Python 字典实现，支持 `enter_scope()` / `exit_scope()` / `declare()` / `resolve()` 操作
- **TypeChecker 类**：处理二元运算的类型推导和类型兼容性检查
- **SemanticAnalyzer 主类**：遍历 AST，执行类型检查、作用域分析、变量声明检查、函数调用验证
- **测试代码**：构建测试 AST 并运行分析器，展示正确程序和错误程序的分析结果

**运行方式**：
```bash
python semantic_analyzer.py
```

### 5.8.2 `ir_generator.py` — 三地址码生成器

**功能**：将 AST 翻译为三地址码 IR，包括：

- **自包含 AST 节点**：与 semantic_analyzer.py 共享类似的节点定义
- **ThreeAddressCode 类**：表示单条三地址码指令，支持多种指令格式的字符串化
- **IRGenerator 类**：
  - 临时变量管理（`new_temp()`）
  - 标签管理（`new_label()`）
  - 表达式翻译：递归翻译表达式节点，返回结果地址
  - 语句翻译：支持赋值、if-else、while 循环、for 循环、return
  - 短路求值支持
- **测试代码**：构建包含 if-else、while 循环的 AST，生成并打印三地址码

**运行方式**：
```bash
python ir_generator.py
```

### 5.8.3 `ssa_converter.py` — SSA 转换器

**功能**：将三地址码转换为 SSA 形式，包括：

- **基本块划分**：将线性的三地址码序列划分为基本块（Basic Block），识别前驱/后继关系
- **支配树构建**：使用迭代算法计算每个基本块的支配者集合，构建支配树
- **φ 函数插入**：基于支配边界（Dominance Frontier）计算，在必要位置插入 φ 函数。使用经典的 Cytron 算法
- **变量重命名**：使用栈来追踪每个变量的当前版本号，在赋值时创建新版本，在引用时使用最新版本，在 φ 函数中正确处理参数选择
- **测试代码**：构建包含循环和条件分支的三地址码，演示完整的 SSA 转换过程

**运行方式**：
```bash
python ssa_converter.py
```

### 5.8.4 三个文件的关系

```
                    语义分析器
                  semantic_analyzer.py
                         │
                         │ (验证 AST 的正确性)
                         ▼
                   三地址码生成器
                    ir_generator.py
                         │
                         │ (生成 TAC 指令序列)
                         ▼
                   SSA 转换器
                    ssa_converter.py
                         │
                         │ (转换为 SSA 形式)
                         ▼
                   SSA 形式的 IR
                   (可用于后续优化)
```

这三个文件共同展示了从源代码到优化就绪的 IR 的完整前端流程。
