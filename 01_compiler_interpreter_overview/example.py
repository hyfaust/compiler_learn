# example.py — Python 代码示例
#
# 本文件用于展示 Python 解释器（CPython）的工作方式特点：
#   - 动态类型：变量无需声明类型，类型在运行时确定
#   - 一切皆对象：整数、函数、类都是对象
#   - 字节码编译：源码先编译为 .pyc 字节码，再由虚拟机执行
#   - GIL（全局解释器锁）：影响多线程并行
#   - 鸭子类型：不检查类型，只检查行为
#
# 可以用 dis 模块查看每个函数编译后的字节码：
#   import dis
#   dis.dis(函数名)

import dis
import sys

# ============================================================
# 1. 基本函数 —— 展示动态类型和字节码编译
# ============================================================

def square(n):
    """计算 n 的平方

    与 C 版本对比：
    - C: int square(int n) — 编译时确定类型，生成固定的乘法指令
    - Python: def square(n) — 运行时检查类型，n 可以是任何支持 * 的对象

    查看字节码：dis.dis(square)
    输出类似：
      2           0 LOAD_FAST                0 (n)
                  2 LOAD_FAST                0 (n)
                  4 BINARY_MULTIPLY
                  6 RETURN_VALUE
    """
    return n * n


def abs_value(x):
    """计算绝对值

    展示 Python 的条件表达式（三元运算符）：
    - C: if (x < 0) { return -x; } else { return x; }
    - Python: return -x if x < 0 else x（表达式，不是语句）

    Python 的 if 是语句，不是表达式，但可以用条件表达式模拟。
    """
    return -x if x < 0 else x


# ============================================================
# 2. 循环与累加 —— 展示 Python 的迭代方式
# ============================================================

def sum_of_squares(n):
    """计算 1² + 2² + ... + n²

    与 C 版本对比：
    - C: for (int i = 1; i <= n; i++) — 显式的循环控制
    - Python: for i in range(1, n+1) — 迭代器协议

    Python 的 for 循环底层使用迭代器协议：
    1. 调用 range(1, n+1) 创建 range 对象
    2. 调用 __iter__() 获取迭代器
    3. 重复调用 __next__() 获取下一个值
    4. 抛出 StopIteration 时结束循环

    这意味着 Python 的 for 循环比 C 的 for 循环有更多的函数调用开销。
    """
    total = 0
    for i in range(1, n + 1):
        total = total + square(i)
    return total


def fibonacci(n):
    """计算第 n 个斐波那契数（迭代版本）

    展示 Python 的多重赋值：
    - C: temp = a; a = b; b = temp; (需要临时变量)
    - Python: a, b = b, a + b (元组解包，原子操作)

    Python 的多重赋值在字节码层面是：
    1. 先计算右侧表达式，创建元组
    2. 再解包赋值给左侧变量
    """
    if n <= 1:
        return n
    a, b = 0, 1
    for _ in range(2, n + 1):
        a, b = b, a + b
    return b


# ============================================================
# 3. 列表操作 —— 展示 Python 的内置数据结构
# ============================================================

def array_sum(arr):
    """计算列表元素之和

    与 C 版本对比：
    - C: arr[i] — 直接的内存偏移计算，O(1)
    - Python: arr[i] — 调用列表对象的 __getitem__ 方法，有额外开销

    Python 的列表底层是动态数组（PyObject 指针数组），
    每个元素都是一个指向 Python 对象的指针。
    """
    total = 0
    for item in arr:
        total += item
    return total


def bubble_sort(arr):
    """冒泡排序

    展示 Python 的就地修改：
    - Python 列表是可变对象，可以就地修改
    - 但 Python 的整数是不可变对象，所以 a, b = b, a 会创建新对象

    性能注意：
    - C 版本的冒泡排序交换元素是直接的内存操作
    - Python 版本涉及对象引用的重新赋值，开销更大
    - 实际项目中应使用 sorted() 或 list.sort()（底层用 C 实现的 Timsort）
    """
    size = len(arr)
    for i in range(size - 1):
        for j in range(size - 1 - i):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]


# ============================================================
# 4. 递归 —— 展示 Python 的函数调用开销
# ============================================================

def factorial(n):
    """阶乘（递归版本）

    Python 的递归限制：
    - 默认递归深度限制为 1000（sys.getrecursionlimit()）
    - 每次函数调用都会创建新的栈帧对象（PyFrameObject）
    - 没有尾调用优化（TCO）

    与 C 对比：
    - C 的函数调用开销：压栈参数、压栈返回地址、跳转（几条指令）
    - Python 的函数调用开销：创建 PyFrameObject、设置局部变量字典等（大量对象操作）
    """
    if n <= 1:
        return 1
    return n * factorial(n - 1)


def binary_search(arr, low, high, target):
    """二分查找

    展示 Python 的列表索引操作和递归。
    注意：Python 的列表索引是 O(1) 的，但每次访问都有类型检查开销。
    """
    if low > high:
        return -1
    mid = low + (high - low) // 2  # // 是整数除法
    if arr[mid] == target:
        return mid
    elif arr[mid] < target:
        return binary_search(arr, mid + 1, high, target)
    else:
        return binary_search(arr, low, mid - 1, target)


# ============================================================
# 5. 类与对象 —— 展示 Python 的对象模型
# ============================================================

class Point:
    """简单的点类

    展示 Python 的对象模型：
    - 每个实例都是一个字典（__dict__），存储属性
    - 属性访问是字典查找，不是固定的内存偏移
    - 类本身也是对象（type 类的实例）

    与 C 的 struct 对比：
    - C struct: Point p1; p1.x = 3; — 编译时确定偏移量，直接内存访问
    - Python: p1 = Point(3, 4); p1.x — 运行时字典查找，有额外开销

    使用 __slots__ 可以优化内存和访问速度（避免使用 __dict__）。
    """

    def __init__(self, x, y):
        self.x = x
        self.y = y

    def manhattan_distance(self, other):
        """计算曼哈顿距离

        方法调用在 Python 中的开销：
        - self 参数是隐式传递的（通过描述符协议）
        - 方法查找涉及 MRO（方法解析顺序）的搜索
        """
        return abs_value(self.x - other.x) + abs_value(self.y - other.y)

    def __repr__(self):
        return f"Point({self.x}, {self.y})"


# ============================================================
# 6. 作用域演示 —— 展示 Python 的 LEGB 规则
# ============================================================

def scope_demo(x):
    """Python 作用域演示（LEGB 规则）

    Python 的变量查找顺序：
    L - Local（局部作用域）
    E - Enclosing（嵌套函数的外层作用域）
    G - Global（模块级作用域）
    B - Built-in（内置作用域）

    与 C 对比：
    - C 的作用域是词法的、静态的，在编译时确定
    - Python 的作用域也是词法的，但变量查找在运行时通过命名空间进行
    """
    result = x

    def inner():
        nonlocal result  # 声明使用外层函数的变量
        result += 100
        return result

    inner()
    result += x
    return result
    # scope_demo(5): result = 5, inner: result = 105, result = 105 + 5 = 110


# ============================================================
# 7. Python 特有的特性 —— 展示解释器/动态语言的优势
# ============================================================

def demonstrate_dynamic_typing():
    """展示 Python 的动态类型特性

    同一个变量可以在不同时刻持有不同类型的值。
    这在 C 中是不可能的（需要显式类型转换或 union）。
    """
    x = 42          # x 是 int
    print(f"x = {x}, type = {type(x).__name__}")

    x = "hello"     # x 现在是 str
    print(f"x = {x}, type = {type(x).__name__}")

    x = [1, 2, 3]   # x 现在是 list
    print(f"x = {x}, type = {type(x).__name__}")


def demonstrate_list_comprehension():
    """展示列表推导式

    列表推导式是 Python 的语法糖，底层编译为高效的字节码：
    [x**2 for x in range(10)]
    比等价的 for 循环 + append 更快（减少了方法调用的开销）
    """
    squares = [x ** 2 for x in range(10)]
    evens = [x for x in range(20) if x % 2 == 0]
    return squares, evens


def demonstrate_higher_order_functions():
    """展示高阶函数

    Python 中函数是一等公民（first-class citizen），
    可以作为参数传递、作为返回值、赋值给变量。
    这在 C 中需要函数指针来实现。
    """
    numbers = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5]

    # map: 对每个元素应用函数
    squared = list(map(square, numbers))

    # filter: 过滤元素
    evens = list(filter(lambda x: x % 2 == 0, numbers))

    # sorted + key: 自定义排序
    sorted_desc = sorted(numbers, reverse=True)

    return squared, evens, sorted_desc


# ============================================================
# 8. 主程序 —— 综合演示
# ============================================================

if __name__ == "__main__":
    print(f"Python 版本: {sys.version}")
    print(f"字节码指令数: {len(dis.opmap)} 种操作码")
    print()

    # --- 基本函数 ---
    print("=== 基本函数 ===")
    print(f"square(5) = {square(5)}")
    print(f"abs_value(-7) = {abs_value(-7)}")
    print()

    # --- 循环与累加 ---
    print("=== 循环与累加 ===")
    print(f"sum_of_squares(5) = {sum_of_squares(5)}")
    print(f"fibonacci(10) = {fibonacci(10)}")
    print()

    # --- 列表操作 ---
    print("=== 列表操作 ===")
    numbers = [64, 34, 25, 12, 22, 11, 90]
    print(f"排序前: {numbers}")
    print(f"元素之和: {array_sum(numbers)}")
    bubble_sort(numbers)
    print(f"排序后: {numbers}")
    print()

    # --- 递归 ---
    print("=== 递归 ===")
    print(f"factorial(6) = {factorial(6)}")
    sorted_arr = [2, 5, 8, 12, 16, 23, 38, 56, 72, 91]
    print(f"binary_search(23) = {binary_search(sorted_arr, 0, 9, 23)}")
    print()

    # --- 类与对象 ---
    print("=== 类与对象 ===")
    p1 = Point(3, 4)
    p2 = Point(7, 1)
    print(f"曼哈顿距离: {p1.manhattan_distance(p2)}")
    print()

    # --- 作用域 ---
    print("=== 作用域 ===")
    print(f"scope_demo(5) = {scope_demo(5)}")
    print()

    # --- Python 特有特性 ---
    print("=== 动态类型 ===")
    demonstrate_dynamic_typing()
    print()

    print("=== 列表推导式 ===")
    sq, ev = demonstrate_list_comprehension()
    print(f"平方数: {sq}")
    print(f"偶数: {ev}")
    print()

    # --- 查看字节码 ---
    print("=== 字节码示例: square 函数 ===")
    dis.dis(square)
    print()

    print("=== Python 执行模型总结 ===")
    print("1. 源码 (.py) → 编译器 → 字节码 (.pyc)")
    print("2. 字节码 → Python 虚拟机 (CEval) → 执行结果")
    print("3. 每个 .py 文件编译为一个 code object")
    print("4. 每个函数/类也有独立的 code object")
    print("5. 字节码是基于栈的指令集（类似 JVM）")
