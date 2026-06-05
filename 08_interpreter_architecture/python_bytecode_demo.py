#!/usr/bin/env python3
"""
python_bytecode_demo.py - Python 字节码演示

使用 Python 的 dis 模块分析各种 Python 代码的字节码，帮助理解 CPython 虚拟机的工作原理。

内容包括：
  1. 算术表达式的字节码
  2. 变量赋值和读取的字节码
  3. 控制流（if/elif/else）的字节码
  4. 循环（while/for）的字节码
  5. 函数定义和调用的字节码
  6. 闭包和自由变量的字节码
  7. 列表推导的字节码
  8. 异常处理（try/except）的字节码
  9. 上下文管理器（with）的字节码
  10. 生成器的字节码
  11. 类定义的字节码
  12. Code Object 深度分析
  13. 栈操作可视化

运行方式：
  python python_bytecode_demo.py

作者：compiler_learn 教学项目
"""

import dis
import sys
import types
import opcode
import inspect


# =============================================================================
# 辅助工具函数
# =============================================================================

SEPARATOR = "=" * 70
SUB_SEPARATOR = "-" * 50


def title(text: str):
    """打印标题"""
    print(f"\n{SEPARATOR}")
    print(f"  {text}")
    print(SEPARATOR)


def subtitle(text: str):
    """打印副标题"""
    print(f"\n{SUB_SEPARATOR}")
    print(f"  {text}")
    print(SUB_SEPARATOR)


def show_bytecode(code_str: str, label: str = ""):
    """
    显示代码字符串的字节码。

    使用 compile() 函数将代码字符串编译为 Code Object，
    然后使用 dis 模块进行反汇编。
    """
    if label:
        print(f"\n  >>> {label}")
    print(f"  源代码: {code_str!r}")
    print()
    code_obj = compile(code_str, "<demo>", "exec")
    # 使用自定义的缩进来美化输出
    for line in dis.Bytecode(code_obj).dis().split('\n'):
        print(f"    {line}")
    print()


def show_func_bytecode(func, label: str = ""):
    """显示函数的字节码"""
    if label:
        print(f"\n  >>> {label}")
    print(f"  函数: {func.__name__}")
    print(f"  参数: {inspect.signature(func)}")
    print()
    dis.dis(func)
    print()


def explain(text: str):
    """打印解释说明"""
    print(f"  [TIP] {text}")


# =============================================================================
# 1. 算术表达式的字节码
# =============================================================================

def demo_arithmetic():
    """演示算术表达式的字节码"""
    title("1. 算术表达式的字节码")

    # --- 1.1 简单加法 ---
    subtitle("1.1 简单加法: 10 + 20")
    show_bytecode("10 + 20", "简单加法")
    explain("LOAD_CONST 将常量压入栈，BINARY_ADD 弹出两个值相加后将结果入栈")
    explain("栈变化: [] -> [10] -> [10, 20] -> [30]")

    # --- 1.2 复合运算 ---
    subtitle("1.2 复合运算: 10 + 20 * 30")
    show_bytecode("10 + 20 * 30", "运算优先级")
    explain("Python编译器自动处理了运算优先级：先计算 20*30，再加 10")
    explain("栈变化: [] -> [10] -> [10, 20] -> [10, 20, 30] -> [10, 600] -> [610]")

    # --- 1.3 除法 ---
    subtitle("1.3 真除法和地板除: 17 / 5, 17 // 5, 17 % 5")
    show_bytecode("17 / 5", "真除法 (true division)")
    show_bytecode("17 // 5", "地板除 (floor division)")
    show_bytecode("17 % 5", "取模 (modulo)")

    # --- 1.4 幂运算 ---
    subtitle("1.4 幂运算: 2 ** 10")
    show_bytecode("2 ** 10", "幂运算")

    # --- 1.5 负数 ---
    subtitle("1.5 一元运算: -x, +x")
    show_bytecode("x = 42\n-x", "一元取负")
    explain("UNARY_NEGATIVE 操作符对栈顶值取负")

    # --- 1.6 布尔运算 ---
    subtitle("1.6 布尔运算")
    show_bytecode("True and False or True", "布尔运算（短路求值）")
    explain("注意 Python 对常量布尔表达式做了优化，直接折叠为结果")


# =============================================================================
# 2. 变量赋值和读取的字节码
# =============================================================================

def demo_variables():
    """演示变量操作的字节码"""
    title("2. 变量赋值和读取的字节码")

    # --- 2.1 全局变量 ---
    subtitle("2.1 模块级变量 (STORE_NAME / LOAD_NAME)")
    show_bytecode("x = 10\ny = 20\nz = x + y", "模块级变量操作")
    explain("模块级代码使用 STORE_NAME / LOAD_NAME")
    explain("这些指令在名称空间（dict）中查找，速度较慢")

    # --- 2.2 函数局部变量 ---
    subtitle("2.2 函数局部变量 (STORE_FAST / LOAD_FAST)")

    def local_vars_example(a, b):
        c = a + b
        d = c * 2
        return d

    show_func_bytecode(local_vars_example, "函数局部变量")
    explain("函数内部使用 STORE_FAST / LOAD_FAST")
    explain("通过数组索引直接访问，比名称查找快得多")
    explain("这就是为什么在函数内访问局部变量比全局变量快")

    # --- 2.3 全局变量访问 ---
    subtitle("2.3 函数内访问全局变量 (LOAD_GLOBAL)")

    global_var = 100

    def access_global():
        return global_var + 1

    show_func_bytecode(access_global, "函数内访问全局变量")
    explain("LOAD_GLOBAL 需要在全局字典中查找，比 LOAD_FAST 慢")

    # --- 2.4 名称查找顺序 ---
    subtitle("2.4 名称查找顺序: Local -> Enclosing -> Global -> Built-in")
    explain("Python 的 LEGB 规则:")
    explain("  L - Local: 当前函数的局部变量 (LOAD_FAST)")
    explain("  E - Enclosing: 外层函数的局部变量 (LOAD_DEREF)")
    explain("  G - Global: 全局变量 (LOAD_GLOBAL)")
    explain("  B - Built-in: 内置函数/常量 (LOAD_NAME)")


# =============================================================================
# 3. 控制流的字节码
# =============================================================================

def demo_control_flow():
    """演示控制流的字节码"""
    title("3. 控制流的字节码")

    # --- 3.1 简单 if ---
    subtitle("3.1 简单 if 语句")

    def simple_if(x):
        if x > 0:
            return "positive"

    show_func_bytecode(simple_if, "简单 if")
    explain("COMPARE_OP 执行比较，POP_JUMP_IF_FALSE 在条件为假时跳转")

    # --- 3.2 if/else ---
    subtitle("3.2 if/else 语句")

    def if_else(x):
        if x > 0:
            return "positive"
        else:
            return "non-positive"

    show_func_bytecode(if_else, "if/else")
    explain("then 分支末尾需要 JUMP_FORWARD 跳过 else 分支")

    # --- 3.3 if/elif/else ---
    subtitle("3.3 if/elif/else 语句")

    def if_elif_else(x):
        if x > 0:
            return "positive"
        elif x == 0:
            return "zero"
        else:
            return "negative"

    show_func_bytecode(if_elif_else, "if/elif/else")
    explain("每个 elif 都是一个新的比较 + JUMP_IF_FALSE")
    explain("最后的 else 不需要条件检查")

    # --- 3.4 条件表达式（三元运算符）---
    subtitle("3.4 条件表达式: x if cond else y")

    def ternary(x):
        return "positive" if x > 0 else "non-positive"

    show_func_bytecode(ternary, "条件表达式")

    # --- 3.5 复杂条件 ---
    subtitle("3.5 复合条件: a and b, a or b")

    def complex_cond(a, b, c):
        if a > 0 and b > 0 or c > 0:
            return True
        return False

    show_func_bytecode(complex_cond, "复合条件")
    explain("and 和 or 是短路求值运算符")
    explain("and: 如果左操作数为假，直接返回左操作数（不求值右边）")
    explain("or:  如果左操作数为真，直接返回左操作数（不求值右边）")


# =============================================================================
# 4. 循环的字节码
# =============================================================================

def demo_loops():
    """演示循环的字节码"""
    title("4. 循环的字节码")

    # --- 4.1 while 循环 ---
    subtitle("4.1 while 循环")

    def while_loop():
        total = 0
        i = 1
        while i <= 10:
            total += i
            i += 1
        return total

    show_func_bytecode(while_loop, "while 循环")
    explain("while 循环的字节码结构:")
    explain("  1. 条件检查 (COMPARE_OP + POP_JUMP_IF_FALSE)")
    explain("  2. 循环体")
    explain("  3. JUMP_ABSOLUTE 回到步骤1")
    explain("  4. 循环结束后的代码")

    # --- 4.2 for 循环 ---
    subtitle("4.2 for 循环")

    def for_loop():
        total = 0
        for i in range(1, 11):
            total += i
        return total

    show_func_bytecode(for_loop, "for 循环")
    explain("for 循环使用迭代器协议:")
    explain("  1. GET_ITER: 获取可迭代对象的迭代器")
    explain("  2. FOR_ITER: 获取下一个元素，如果没有则跳转到循环结束")
    explain("  3. 循环体")
    explain("  4. JUMP_ABSOLUTE 回到 FOR_ITER")

    # --- 4.3 for + break ---
    subtitle("4.3 for 循环 + break")

    def for_break():
        for i in range(100):
            if i >= 5:
                break
        return i

    show_func_bytecode(for_break, "for + break")
    explain("break 编译为 JUMP_ABSOLUTE，跳转到 FOR_ITER 之后的位置")

    # --- 4.4 for + continue ---
    subtitle("4.4 for 循环 + continue")

    def for_continue():
        total = 0
        for i in range(10):
            if i % 2 == 0:
                continue
            total += i
        return total

    show_func_bytecode(for_continue, "for + continue")
    explain("continue 编译为 JUMP_ABSOLUTE，跳转回 FOR_ITER 指令")

    # --- 4.5 for-else ---
    subtitle("4.5 for-else 语句")

    def for_else(items, target):
        for item in items:
            if item == target:
                return "found"
        else:
            return "not found"

    show_func_bytecode(for_else, "for-else")
    explain("for-else 中的 else 块在循环正常结束（没有 break）时执行")
    explain("如果循环被 break 中断，else 块会被跳过")

    # --- 4.6 嵌套循环 ---
    subtitle("4.6 嵌套循环")

    def nested_loop():
        result = []
        for i in range(3):
            for j in range(3):
                result.append(i * 3 + j)
        return result

    show_func_bytecode(nested_loop, "嵌套循环")
    explain("嵌套循环有多个 FOR_ITER 和 JUMP_ABSOLUTE")


# =============================================================================
# 5. 函数定义和调用的字节码
# =============================================================================

def demo_functions():
    """演示函数的字节码"""
    title("5. 函数定义和调用的字节码")

    # --- 5.1 简单函数 ---
    subtitle("5.1 简单函数定义和调用")

    def simple():
        x = 10 + 20
        return x

    print("\n  函数 simple() 的字节码:")
    dis.dis(simple)

    print("\n  外层代码（定义和调用 simple）的字节码:")
    show_bytecode("""
def simple():
    x = 10 + 20
    return x

simple()
""".strip(), "函数定义和调用")
    explain("函数定义的步骤:")
    explain("  1. LOAD_CONST: 加载函数的 Code Object")
    explain("  2. LOAD_CONST: 加载函数名 'simple'")
    explain("  3. MAKE_FUNCTION: 创建函数对象")
    explain("  4. STORE_NAME: 存储到名称空间")
    explain("函数调用的步骤:")
    explain("  1. LOAD_NAME: 加载函数对象")
    explain("  2. CALL_FUNCTION: 调用函数")

    # --- 5.2 带参数的函数 ---
    subtitle("5.2 带参数的函数")

    def add(a, b):
        return a + b

    show_func_bytecode(add, "带参数函数")
    explain("参数通过 LOAD_FAST 以索引方式访问（a=0, b=1）")

    # --- 5.3 默认参数 ---
    subtitle("5.3 默认参数")

    def greet(name, greeting="Hello"):
        return f"{greeting}, {name}!"

    show_func_bytecode(greet, "默认参数")
    explain("默认参数在 MAKE_FUNCTION 之前通过常量加载")

    # --- 5.4 可变参数 ---
    subtitle("5.4 可变参数 (*args, **kwargs)")

    def varargs(*args, **kwargs):
        return len(args), len(kwargs)

    show_func_bytecode(varargs, "可变参数")
    explain("可变参数使用专门的字节码指令来收集参数")

    # --- 5.5 递归 ---
    subtitle("5.5 递归函数")

    def factorial(n):
        if n <= 1:
            return 1
        return n * factorial(n - 1)

    show_func_bytecode(factorial, "递归函数 factorial")
    explain("递归函数在字节码层面就是普通的 CALL_FUNCTION")
    explain("每次递归调用都会创建一个新的栈帧")


# =============================================================================
# 6. 闭包和自由变量的字节码
# =============================================================================

def demo_closures():
    """演示闭包的字节码"""
    title("6. 闭包和自由变量的字节码")

    # --- 6.1 简单闭包 ---
    subtitle("6.1 简单闭包")

    def make_greeting(prefix):
        def greet(name):
            return f"{prefix}, {name}!"
        return greet

    print("\n  外层函数 make_greeting 的字节码:")
    dis.dis(make_greeting)

    print("\n  内层函数 greet 的字节码:")
    # 获取内部函数的 Code Object
    inner_code = make_greeting.__code__.co_consts[1]
    if isinstance(inner_code, types.CodeType):
        dis.dis(inner_code)

    explain("闭包的字节码关键点:")
    explain("  外层函数: 使用 STORE_DEREF 将变量存入 cell（单元格）")
    explain("  内层函数: 使用 LOAD_DEREF 从 cell 中加载变量")
    explain("  cell 是引用类型，内层和外层共享同一个 cell")
    explain("  即使外层函数返回，cell 仍然被内层函数引用")

    # --- 6.2 计数器闭包 ---
    subtitle("6.2 计数器闭包")

    def make_counter(start=0):
        count = start
        def counter():
            nonlocal count
            count += 1
            return count
        return counter

    print("\n  make_counter 的字节码:")
    dis.dis(make_counter)

    print("\n  counter (内层) 的字节码:")
    counter_code = make_counter.__code__.co_consts[0]
    if isinstance(counter_code, types.CodeType):
        dis.dis(counter_code)

    explain("nonlocal 关键字告诉编译器 count 是外层变量")
    explain("这使得 count 使用 STORE_DEREF / LOAD_DEREF 而非 STORE_FAST / LOAD_FAST")

    # --- 6.3 多层闭包 ---
    subtitle("6.3 多层闭包")

    def outer(x):
        def middle(y):
            def inner(z):
                return x + y + z
            return inner
        return middle

    print("\n  outer 的字节码:")
    dis.dis(outer)

    print("\n  Code Object 层次结构:")
    def show_code_tree(code, indent=0):
        prefix = "  " * indent
        print(f"{prefix}├── {code.co_name}")
        print(f"{prefix}│   freevars: {code.co_freevars}")
        print(f"{prefix}│   cellvars: {code.co_cellvars}")
        for const in code.co_consts:
            if isinstance(const, types.CodeType):
                show_code_tree(const, indent + 1)

    show_code_tree(outer.__code__)


# =============================================================================
# 7. 列表推导的字节码
# =============================================================================

def demo_comprehensions():
    """演示列表推导的字节码"""
    title("7. 列表推导的字节码")

    # --- 7.1 简单列表推导 ---
    subtitle("7.1 列表推导: [x*x for x in range(10)]")
    show_bytecode("[x*x for x in range(10)]", "列表推导")
    explain("列表推导在 CPython 内部被编译为一个独立的嵌套函数！")
    explain("这个嵌套函数使用 LIST_APPEND 指令逐个添加元素")

    # --- 7.2 带条件的列表推导 ---
    subtitle("7.2 带条件的列表推导: [x for x in range(20) if x % 3 == 0]")
    show_bytecode("[x for x in range(20) if x % 3 == 0]", "带条件的列表推导")
    explain("条件过滤编译为 POP_JUMP_IF_FALSE，跳过 LIST_APPEND")

    # --- 7.3 嵌套列表推导 ---
    subtitle("7.3 嵌套列表推导: [i*j for i in range(3) for j in range(3)]")
    show_bytecode("[i*j for i in range(3) for j in range(3)]", "嵌套列表推导")
    explain("嵌套推导被编译为嵌套的 FOR_ITER 循环")

    # --- 7.4 字典推导 ---
    subtitle("7.4 字典推导: {k: v for k, v in pairs}")
    show_bytecode("""
pairs = [("a", 1), ("b", 2), ("c", 3)]
result = {k: v for k, v in pairs}
""".strip(), "字典推导")

    # --- 7.5 集合推导 ---
    subtitle("7.5 集合推导: {x % 10 for x in range(20)}")
    show_bytecode("{x % 10 for x in range(20)}", "集合推导")

    # --- 7.6 生成器表达式 ---
    subtitle("7.6 生成器表达式: sum(x*x for x in range(100))")
    show_bytecode("result = sum(x*x for x in range(100))", "生成器表达式")
    explain("生成器表达式不创建列表，而是返回一个迭代器")
    explain("使用 YIELD_VALUE 指令逐个产生值")


# =============================================================================
# 8. 异常处理的字节码
# =============================================================================

def demo_exceptions():
    """演示异常处理的字节码"""
    title("8. 异常处理（try/except）的字节码")

    # --- 8.1 简单 try/except ---
    subtitle("8.1 简单 try/except")

    def simple_try():
        try:
            x = 1 / 0
        except ZeroDivisionError as e:
            x = "error"
        return x

    show_func_bytecode(simple_try, "try/except")
    explain("try/except 的字节码使用 SETUP_FINALLY / POP_BLOCK 指令")
    explain("异常发生时，Python 虚拟机沿着调用栈查找匹配的 except 处理器")

    # --- 8.2 多个 except ---
    subtitle("8.2 多个 except 子句")

    def multi_except():
        try:
            x = int("abc")
        except ValueError:
            x = "value error"
        except TypeError:
            x = "type error"
        except Exception:
            x = "other error"
        return x

    show_func_bytecode(multi_except, "多个 except")
    explain("每个 except 子句检查异常类型是否匹配")

    # --- 8.3 try/except/finally ---
    subtitle("8.3 try/except/finally")

    def try_finally():
        try:
            x = 1
        except Exception:
            x = -1
        finally:
            x = x + 100
        return x

    show_func_bytecode(try_finally, "try/finally")
    explain("finally 块保证在任何情况下都执行（正常退出或异常退出）")


# =============================================================================
# 9. 上下文管理器（with）的字节码
# =============================================================================

def demo_with():
    """演示 with 语句的字节码"""
    title("9. 上下文管理器（with）的字节码")

    subtitle("9.1 with 语句")
    show_bytecode("""
with open("test.txt") as f:
    data = f.read()
""".strip(), "with 语句")
    explain("with 语句编译为:")
    explain("  1. SETUP_WITH: 调用 __enter__ 方法")
    explain("  2. with 体")
    explain("  3. WITH_CLEANUP_FINISH: 调用 __exit__ 方法")
    explain("with 语句等价于 try/finally 块，确保资源被正确释放")


# =============================================================================
# 10. 生成器的字节码
# =============================================================================

def demo_generators():
    """演示生成器的字节码"""
    title("10. 生成器的字节码")

    # --- 10.1 简单生成器 ---
    subtitle("10.1 简单生成器")

    def simple_gen():
        yield 1
        yield 2
        yield 3

    show_func_bytecode(simple_gen, "简单生成器")
    explain("YIELD_VALUE 指令暂停生成器并返回值")
    explain("生成器的状态（包括局部变量和程序计数器）被保存")
    explain("下次调用 __next__() 时，从暂停处继续执行")

    # --- 10.2 无限生成器 ---
    subtitle("10.2 无限计数器生成器")

    def count_from(n):
        while True:
            yield n
            n += 1

    show_func_bytecode(count_from, "无限生成器")
    explain("生成器可以表示无限序列，因为它们是惰性求值的")

    # --- 10.3 生成器表达式 vs 列表 ---
    subtitle("10.3 生成器表达式 vs 列表推导")
    explain("列表推导: [x**2 for x in range(10)] → 立即创建完整列表")
    explain("生成器:   (x**2 for x in range(10)) → 返回生成器对象，按需计算")
    explain("对于大数据集，生成器更节省内存")


# =============================================================================
# 11. 类定义的字节码
# =============================================================================

def demo_classes():
    """演示类定义的字节码"""
    title("11. 类定义的字节码")

    subtitle("11.1 简单类定义")
    show_bytecode("""
class Point:
    def __init__(self, x, y):
        self.x = x
        self.y = y

    def distance(self, other):
        dx = self.x - other.x
        dy = self.y - other.y
        return (dx**2 + dy**2) ** 0.5

p = Point(3, 4)
""".strip(), "类定义")
    explain("类定义的字节码结构:")
    explain("  1. LOAD_BUILD_CLASS: 加载内建的 __build_class__ 函数")
    explain("  2. 加载类体的 Code Object")
    explain("  3. 加载类名")
    explain("  4. CALL_FUNCTION: 调用 __build_class__ 创建类对象")
    explain("  5. STORE_NAME: 存储类名")
    explain("方法定义与普通函数类似，但 __init__ 中的 self.x = x 使用 STORE_ATTR")


# =============================================================================
# 12. Code Object 深度分析
# =============================================================================

def demo_code_object():
    """演示 Code Object 的内部结构"""
    title("12. Code Object 深度分析")

    def example(a, b):
        c = "hello"
        d = [1, 2, 3]
        return a + b + len(c) + len(d)

    code = example.__code__

    subtitle("12.1 Code Object 的属性")
    print(f"""
  Code Object: {code}
  ┌────────────────────────────────────────────────────────────────┐
  │ co_name        = {code.co_name!r:42s} │
  │ co_filename    = {code.co_filename!r:42s} │
  │ co_firstlineno = {code.co_firstlineno:<42d} │
  │ co_argcount    = {code.co_argcount:<42d} │
  │ co_nlocals     = {code.co_nlocals:<42d} │
  │ co_stacksize   = {code.co_stacksize:<42d} │
  │ co_flags       = {code.co_flags:<42d} │
  │ co_consts      = {str(code.co_consts):<42s} │
  │ co_names       = {str(code.co_names):<42s} │
  │ co_varnames    = {str(code.co_varnames):<42s} │
  │ co_freevars    = {str(code.co_freevars):<42s} │
  │ co_cellvars    = {str(code.co_cellvars):<42s} │
  │ co_code (len)  = {len(code.co_code):<42d} │
  └────────────────────────────────────────────────────────────────┘
""")

    subtitle("12.2 co_flags 标志位解析")
    flags = code.co_flags
    flag_names = {
        0x0001: "CO_OPTIMIZED",       # 使用了优化的局部变量访问
        0x0002: "CO_NEWLOCALS",       # 创建新的局部变量名空间
        0x0004: "CO_VARARGS",         # 使用了 *args
        0x0008: "CO_VARKEYWORDS",     # 使用了 **kwargs
        0x0020: "CO_GENERATOR",       # 是生成器函数
        0x0040: "CO_NOFREE",          # 没有自由变量
        0x0100: "CO_COROUTINE",       # 是协程
        0x0200: "CO_ITERABLE_COROUTINE",  # 可迭代协程
        0x1000: "CO_NESTED",          # 嵌套函数
    }
    print(f"  co_flags = {flags} (0x{flags:04x})")
    for mask, name in flag_names.items():
        if flags & mask:
            print(f"    [OK] {name}")
        else:
            print(f"    [X] {name}")

    subtitle("12.3 co_consts 常量池详解")
    print("  常量池中存储了函数中使用的所有常量值：")
    for i, const in enumerate(code.co_consts):
        const_type = type(const).__name__
        if isinstance(const, types.CodeType):
            print(f"    [{i}] <CodeObject: {const.co_name}>(params={const.co_argcount})")
        else:
            print(f"    [{i}] {const_type}: {const!r}")

    subtitle("12.4 原始字节码（bytes）")
    print(f"  co_code = {code.co_code!r}")
    print(f"  长度: {len(code.co_code)} 字节")
    print()
    print("  逐字节分析:")
    i = 0
    while i < len(code.co_code):
        op = code.co_code[i]
        opname = opcode.opname[op] if op < len(opcode.opname) else f"<{op}>"
        has_arg = op >= opcode.HAVE_ARGUMENT
        if has_arg and i + 1 < len(code.co_code):
            arg = code.co_code[i + 1]
            print(f"    {i:4d}: {op:3d} ({opname:20s}) arg={arg}")
            i += 2
        else:
            print(f"    {i:4d}: {op:3d} ({opname:20s})")
            i += 1


# =============================================================================
# 13. 栈操作可视化
# =============================================================================

def demo_stack_visualization():
    """可视化展示栈操作"""
    title("13. 栈操作可视化")

    subtitle("13.1 算术表达式的栈操作")
    print("""
  表达式: (10 + 20) * (30 - 5)

  对应字节码:
    LOAD_CONST  10
    LOAD_CONST  20
    BINARY_ADD
    LOAD_CONST  30
    LOAD_CONST  5
    BINARY_SUBTRACT
    BINARY_MULTIPLY

  栈操作过程:

  指令                    栈状态（栈顶在右）
  ───────────────────────────────────────────
  LOAD_CONST 10          [10]
  LOAD_CONST 20          [10, 20]
  BINARY_ADD             [30]                   ← 弹出10和20，压入30
  LOAD_CONST 30          [30, 30]
  LOAD_CONST 5           [30, 30, 5]
  BINARY_SUBTRACT        [30, 25]               ← 弹出30和5，压入25
  BINARY_MULTIPLY        [750]                  ← 弹出30和25，压入750
""")

    subtitle("13.2 if/else 的栈操作")
    print("""
  代码: if x > 0: y = 1 else: y = -1

  字节码:
    LOAD_NAME    x
    LOAD_CONST   0
    COMPARE_OP   >
    POP_JUMP_IF_FALSE  12
    LOAD_CONST   1
    STORE_NAME   y
    JUMP_FORWARD 4
    LOAD_CONST   -1
    STORE_NAME   y

  执行流程（当 x > 0 时）:

  指令                    栈状态             说明
  ───────────────────────────────────────────────────────
  LOAD_NAME x            [x_val]            加载变量x
  LOAD_CONST 0           [x_val, 0]         加载常量0
  COMPARE_OP >           [True]             弹出两个值，比较后压入结果
  POP_JUMP_IF_FALSE      []                 True，不跳转，继续执行
  LOAD_CONST 1           [1]                压入1
  STORE_NAME y           []                 弹出1，存入y
  JUMP_FORWARD           []                 跳过else分支

  执行流程（当 x <= 0 时）:

  指令                    栈状态             说明
  ───────────────────────────────────────────────────────
  LOAD_NAME x            [x_val]
  LOAD_CONST 0           [x_val, 0]
  COMPARE_OP >           [False]
  POP_JUMP_IF_FALSE      []                 False，跳转到12！
  ... (跳过了then分支) ...
  LOAD_CONST -1          [-1]
  STORE_NAME y           []                 弹出-1，存入y
""")

    subtitle("13.3 函数调用的栈操作")
    print("""
  代码:
    def add(a, b):
        return a + b

    result = add(3, 4)

  函数 add 的字节码:
    LOAD_FAST  0 (a)
    LOAD_FAST  1 (b)
    BINARY_ADD
    RETURN_VALUE

  调用 add(3, 4) 的栈操作:

  主程序:
  指令                    栈状态
  ───────────────────────────────────────────
  LOAD_NAME add          [<fn add>]
  LOAD_CONST 3           [<fn add>, 3]
  LOAD_CONST 4           [<fn add>, 3, 4]
  CALL_FUNCTION 2        [7]                ← 调用函数

  函数内部（新栈帧）:
  指令                    栈状态
  ───────────────────────────────────────────
  LOAD_FAST 0 (a)        [3]                参数a
  LOAD_FAST 1 (b)        [3, 4]             参数b
  BINARY_ADD             [7]                3 + 4
  RETURN_VALUE           (返回7到调用者)
""")


# =============================================================================
# 14. 实用技巧
# =============================================================================

def demo_tips():
    """演示字节码分析的实用技巧"""
    title("14. 实用技巧")

    subtitle("14.1 使用 dis.Bytecode 逐条分析")
    print("""
  import dis

  # 方法1: 直接反汇编
  dis.dis("x = 1 + 2")

  # 方法2: 使用 Bytecode 对象逐条分析
  bc = dis.Bytecode(compile("x = 1 + 2", "<test>", "exec"))
  for instr in bc:
      print(f"  offset={instr.offset:3d}  opname={instr.opname:20s}  arg={instr.arg}  argval={instr.argval}")

  # 方法3: 查看特定函数
  dis.dis(my_function)
""")

    subtitle("14.2 比较不同写法的字节码效率")

    # 列表拼接 vs 列表推导
    print("\n  方式1: 手动循环拼接列表")
    code1 = """
result = []
for x in range(100):
    result.append(x * x)
"""
    code_obj1 = compile(code1, "<test>", "exec")
    instrs1 = list(dis.get_instructions(code_obj1))
    print(f"    指令数: {len(instrs1)}")

    print("\n  方式2: 列表推导")
    code2 = "result = [x * x for x in range(100)]"
    code_obj2 = compile(code2, "<test>", "exec")
    instrs2 = list(dis.get_instructions(code_obj2))
    print(f"    指令数: {len(instrs2)}")

    explain("列表推导通常比手动循环更高效，因为:")
    explain("  1. 减少了 LOAD_METHOD append 的查找开销")
    explain("  2. LIST_APPEND 直接操作列表内部结构")
    explain("  3. 推导式被编译为独立函数，有更优化的字节码")

    subtitle("14.3 字节码优化：常量折叠")
    show_bytecode("x = 2 * 3 * 7", "常量折叠示例")
    explain("CPython 编译器在编译阶段将 2 * 3 * 7 折叠为常量 42")
    explain("这叫做「常量折叠」（Constant Folding），是一种编译期优化")

    subtitle("14.4 窥孔优化")
    show_bytecode("""
x = True
y = not x
""".strip(), "窥孔优化")
    explain("编译器可能会将 NOT_TRUE 优化为 LOAD_CONST False")


# =============================================================================
# 主程序
# =============================================================================

def main():
    """运行所有演示"""
    print(SEPARATOR)
    print("  Python 字节码演示 (CPython Bytecode Demo)")
    print(f"  Python {sys.version}")
    print(SEPARATOR)
    print()
    print("  本程序通过实际运行 dis 模块来展示 Python 代码的字节码。")
    print("  每个示例都附有详细的注释，帮助你理解 CPython 虚拟机的工作原理。")

    demos = [
        ("1. 算术表达式", demo_arithmetic),
        ("2. 变量操作", demo_variables),
        ("3. 控制流", demo_control_flow),
        ("4. 循环", demo_loops),
        ("5. 函数", demo_functions),
        ("6. 闭包", demo_closures),
        ("7. 列表推导", demo_comprehensions),
        ("8. 异常处理", demo_exceptions),
        ("9. with 语句", demo_with),
        ("10. 生成器", demo_generators),
        ("11. 类定义", demo_classes),
        ("12. Code Object", demo_code_object),
        ("13. 栈操作可视化", demo_stack_visualization),
        ("14. 实用技巧", demo_tips),
    ]

    # 如果命令行指定了章节号，只运行对应的演示
    if len(sys.argv) > 1:
        try:
            idx = int(sys.argv[1]) - 1
            if 0 <= idx < len(demos):
                label, func = demos[idx]
                func()
                return
            else:
                print(f"\n  章节号应在 1-{len(demos)} 之间")
                sys.exit(1)
        except ValueError:
            pass

    # 运行所有演示
    for label, func in demos:
        try:
            func()
        except Exception as e:
            print(f"\n  [WARN] 演示 '{label}' 出错: {e}")

    print(f"\n{SEPARATOR}")
    print("  所有演示完成！")
    print("  提示: 可以用 'python python_bytecode_demo.py <N>' 运行单个章节")
    print(f"  例如: python python_bytecode_demo.py 6  (运行闭包演示)")
    print(SEPARATOR)


if __name__ == "__main__":
    main()
