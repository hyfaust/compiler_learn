#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
benchmark.py - JIT编译前后的性能对比基准测试

本模块提供多种基准测试场景，对比：
1. 纯Python解释执行（模拟纯解释器）
2. 使用优化后的Python函数（模拟JIT编译效果）
3. 使用Python内置操作（接近原生性能的参考）

基准测试场景：
- 整数求和循环
- 浮点数数学运算
- 多项式求值
- 数组/列表处理
- 对象属性访问（内联缓存效果）
- 条件分支密集计算
- 递归函数

运行方式：
    python benchmark.py
"""

import time
import sys
import math
import statistics
from typing import List, Dict, Any, Callable, Tuple, Optional
from dataclasses import dataclass, field
from functools import lru_cache
from collections import defaultdict


# ============================================================================
# 基准测试基础设施
# ============================================================================

@dataclass
class BenchmarkResult:
    """基准测试结果"""
    name: str
    description: str
    results: Dict[str, float]  # 方法名 -> 耗时（秒）
    iterations: int
    speedups: Dict[str, float] = field(default_factory=dict)  # 方法名 -> 加速比

    def add_speedup(self, method: str, baseline_method: str):
        """计算相对于基准方法的加速比"""
        if baseline_method in self.results and method in self.results:
            baseline_time = self.results[baseline_method]
            method_time = self.results[method]
            if method_time > 0:
                self.speedups[method] = baseline_time / method_time


class Benchmark:
    """基准测试运行器"""

    def __init__(self, warmup_iterations: int = 3, test_iterations: int = 5):
        self.warmup_iterations = warmup_iterations
        self.test_iterations = test_iterations
        self.results: List[BenchmarkResult] = []

    def run(self, name: str, description: str,
            methods: Dict[str, Callable], iterations: int) -> BenchmarkResult:
        """
        运行基准测试

        Args:
            name: 测试名称
            description: 测试描述
            methods: 方法字典 {方法名: 方法函数}
            iterations: 每个方法的迭代次数

        Returns:
            BenchmarkResult
        """
        print(f"\n  运行: {name}")
        print(f"  描述: {description}")
        print(f"  迭代次数: {iterations:,}")

        result = BenchmarkResult(
            name=name,
            description=description,
            results={},
            iterations=iterations,
        )

        for method_name, method_func in methods.items():
            # 预热
            for _ in range(self.warmup_iterations):
                method_func()

            # 正式测试
            times = []
            for _ in range(self.test_iterations):
                start = time.perf_counter()
                method_func()
                elapsed = time.perf_counter() - start
                times.append(elapsed)

            # 使用中位数作为最终结果（更稳定）
            median_time = statistics.median(times)
            result.results[method_name] = median_time

        self.results.append(result)
        return result


# ============================================================================
# 基准测试1：整数求和循环
# ============================================================================

def benchmark_integer_sum():
    """整数求和循环基准测试"""
    n = 500000

    def pure_python_sum():
        """纯Python循环求和（模拟解释器）"""
        total = 0
        for i in range(n):
            total += i
        return total

    def builtin_sum():
        """使用内置sum函数（接近原生性能）"""
        return sum(range(n))

    def generator_sum():
        """使用生成器表达式"""
        return sum(i for i in range(n))

    benchmark = Benchmark()
    result = benchmark.run(
        name="整数求和循环",
        description=f"计算 sum(0..{n-1})",
        methods={
            "纯Python循环": pure_python_sum,
            "内置sum()": builtin_sum,
            "生成器表达式": generator_sum,
        },
        iterations=n,
    )

    # 计算加速比
    result.add_speedup("内置sum()", "纯Python循环")
    result.add_speedup("生成器表达式", "纯Python循环")

    return result


# ============================================================================
# 基准测试2：浮点数数学运算
# ============================================================================

def benchmark_float_math():
    """浮点数数学运算基准测试"""
    n = 200000

    def pure_python_math():
        """纯Python浮点运算"""
        result = 0.0
        for i in range(n):
            x = float(i)
            result += x * x + math.sqrt(x + 1.0) - math.sin(x * 0.001)
        return result

    def optimized_math():
        """优化的浮点运算（减少属性查找）"""
        result = 0.0
        sqrt = math.sqrt
        sin = math.sin
        for i in range(n):
            x = float(i)
            result += x * x + sqrt(x + 1.0) - sin(x * 0.001)
        return result

    def list_comprehension_math():
        """使用列表推导式"""
        return sum(
            i * i + math.sqrt(i + 1.0) - math.sin(i * 0.001)
            for i in range(n)
        )

    benchmark = Benchmark()
    result = benchmark.run(
        name="浮点数数学运算",
        description=f"计算 x*x + sqrt(x+1) - sin(x*0.001) 的和, n={n}",
        methods={
            "纯Python循环": pure_python_math,
            "局部变量优化": optimized_math,
            "生成器表达式": list_comprehension_math,
        },
        iterations=n,
    )

    result.add_speedup("局部变量优化", "纯Python循环")
    result.add_speedup("生成器表达式", "纯Python循环")

    return result


# ============================================================================
# 基准测试3：多项式求值
# ============================================================================

def benchmark_polynomial():
    """多项式求值基准测试"""
    n = 100000
    coeffs = [3.0, 2.0, 5.0, 7.0, 1.0, 4.0]  # 6次多项式

    def naive_polynomial(x: float) -> float:
        """朴素多项式求值：c0 + c1*x + c2*x^2 + ..."""
        result = 0.0
        for i, c in enumerate(coeffs):
            result += c * (x ** i)
        return result

    def horner_polynomial(x: float) -> float:
        """Horner方法：((...((c_n*x + c_{n-1})*x + c_{n-2})*x + ...)*x + c_0"""
        result = 0.0
        for c in reversed(coeffs):
            result = result * x + c
        return result

    # 预编译Horner函数（模拟JIT编译）
    def make_horner_compiled():
        """创建预编译的Horner函数（模拟JIT特化）"""
        # 局部变量捕获，避免闭包中的字典查找
        local_coeffs = list(reversed(coeffs))
        def compiled_horner(x: float) -> float:
            result = 0.0
            for c in local_coeffs:
                result = result * x + c
            return result
        return compiled_horner

    compiled_horner = make_horner_compiled()

    def naive_loop():
        total = 0.0
        for x in range(n):
            total += naive_polynomial(float(x))
        return total

    def horner_loop():
        total = 0.0
        for x in range(n):
            total += horner_polynomial(float(x))
        return total

    def compiled_loop():
        total = 0.0
        for x in range(n):
            total += compiled_horner(float(x))
        return total

    benchmark = Benchmark()
    result = benchmark.run(
        name="多项式求值",
        description=f"6次多项式求值, n={n}",
        methods={
            "朴素方法 (x**i)": naive_loop,
            "Horner方法": horner_loop,
            "预编译Horner": compiled_loop,
        },
        iterations=n,
    )

    result.add_speedup("Horner方法", "朴素方法 (x**i)")
    result.add_speedup("预编译Horner", "朴素方法 (x**i)")

    return result


# ============================================================================
# 基准测试4：列表/数组处理
# ============================================================================

def benchmark_array_processing():
    """列表/数组处理基准测试"""
    n = 100000
    data = [float(i) for i in range(n)]

    def pure_python_map():
        """纯Python映射"""
        result = []
        for x in data:
            result.append(x * 2.0 + 1.0)
        return result

    def list_comprehension():
        """列表推导式"""
        return [x * 2.0 + 1.0 for x in data]

    def builtin_map():
        """内置map函数"""
        return list(map(lambda x: x * 2.0 + 1.0, data))

    def generator_to_list():
        """生成器转列表"""
        return list(x * 2.0 + 1.0 for x in data)

    benchmark = Benchmark()
    result = benchmark.run(
        name="列表处理",
        description=f"对{n}个元素执行 f(x) = x*2+1",
        methods={
            "纯Python循环+append": pure_python_map,
            "列表推导式": list_comprehension,
            "内置map()": builtin_map,
            "生成器表达式": generator_to_list,
        },
        iterations=n,
    )

    result.add_speedup("列表推导式", "纯Python循环+append")
    result.add_speedup("内置map()", "纯Python循环+append")
    result.add_speedup("生成器表达式", "纯Python循环+append")

    return result


# ============================================================================
# 基准测试5：对象属性访问（内联缓存效果）
# ============================================================================

def benchmark_attribute_access():
    """对象属性访问基准测试"""
    n = 200000

    # 使用普通类
    class Point:
        __slots__ = ['x', 'y']  # 使用__slots__优化
        def __init__(self, x, y):
            self.x = x
            self.y = y

    # 使用字典
    def make_dict_point(x, y):
        return {'x': x, 'y': y}

    # 使用namedtuple
    from collections import namedtuple
    NTPoint = namedtuple('NTPoint', ['x', 'y'])

    # 使用dataclass
    from dataclasses import dataclass as dc
    @dc
    class DCPoint:
        x: float
        y: float

    points_class = [Point(float(i), float(i * 2)) for i in range(n)]
    points_dict = [{'x': float(i), 'y': float(i * 2)} for i in range(n)]
    points_nt = [NTPoint(float(i), float(i * 2)) for i in range(n)]
    points_dc = [DCPoint(float(i), float(i * 2)) for i in range(n)]

    def access_class():
        total = 0.0
        for p in points_class:
            total += p.x + p.y
        return total

    def access_dict():
        total = 0.0
        for p in points_dict:
            total += p['x'] + p['y']
        return total

    def access_namedtuple():
        total = 0.0
        for p in points_nt:
            total += p.x + p.y
        return total

    def access_dataclass():
        total = 0.0
        for p in points_dc:
            total += p.x + p.y
        return total

    benchmark = Benchmark()
    result = benchmark.run(
        name="对象属性访问",
        description=f"访问{n}个Point对象的x和y属性",
        methods={
            "普通类 (__slots__)": access_class,
            "字典": access_dict,
            "namedtuple": access_namedtuple,
            "dataclass": access_dataclass,
        },
        iterations=n,
    )

    result.add_speedup("普通类 (__slots__)", "字典")
    result.add_speedup("namedtuple", "字典")
    result.add_speedup("dataclass", "字典")

    return result


# ============================================================================
# 基准测试6：条件分支密集计算
# ============================================================================

def benchmark_branching():
    """条件分支密集计算基准测试"""
    n = 200000
    data = [float(i % 100) for i in range(n)]

    def with_branches():
        """有大量分支的计算"""
        total = 0.0
        for x in data:
            if x < 20:
                total += x * 2
            elif x < 40:
                total += x * 3
            elif x < 60:
                total += x * 4
            elif x < 80:
                total += x * 5
            else:
                total += x * 6
        return total

    def branchless():
        """无分支版本（使用查表）"""
        multipliers = [2, 2, 2, 2, 2, 2, 2, 2, 2, 2,
                       3, 3, 3, 3, 3, 3, 3, 3, 3, 3,
                       4, 4, 4, 4, 4, 4, 4, 4, 4, 4,
                       5, 5, 5, 5, 5, 5, 5, 5, 5, 5,
                       6, 6, 6, 6, 6, 6, 6, 6, 6, 6,
                       7, 7, 7, 7, 7, 7, 7, 7, 7, 7,
                       8, 8, 8, 8, 8, 8, 8, 8, 8, 8,
                       9, 9, 9, 9, 9, 9, 9, 9, 9, 9,
                       10, 10, 10, 10, 10, 10, 10, 10, 10, 10,
                       11, 11, 11, 11, 11, 11, 11, 11, 11, 11]
        total = 0.0
        for x in data:
            total += x * multipliers[int(x)]
        return total

    def with_dict():
        """使用字典查找"""
        multipliers = {i: (i // 20) + 2 for i in range(100)}
        total = 0.0
        for x in data:
            total += x * multipliers[int(x)]
        return total

    benchmark = Benchmark()
    result = benchmark.run(
        name="条件分支密集计算",
        description=f"对{n}个元素执行条件分支计算",
        methods={
            "if-elif分支": with_branches,
            "查表（无分支）": branchless,
            "字典查找": with_dict,
        },
        iterations=n,
    )

    result.add_speedup("查表（无分支）", "if-elif分支")
    result.add_speedup("字典查找", "if-elif分支")

    return result


# ============================================================================
# 基准测试7：递归函数
# ============================================================================

def benchmark_recursion():
    """递归函数基准测试"""
    n = 30  # fib(30)

    def fib_recursive(n):
        """朴素递归"""
        if n <= 1:
            return n
        return fib_recursive(n - 1) + fib_recursive(n - 2)

    @lru_cache(maxsize=None)
    def fib_memoized(n):
        """记忆化递归"""
        if n <= 1:
            return n
        return fib_memoized(n - 1) + fib_memoized(n - 2)

    def fib_iterative(n):
        """迭代版本"""
        if n <= 1:
            return n
        a, b = 0, 1
        for _ in range(2, n + 1):
            a, b = b, a + b
        return b

    def run_recursive():
        return fib_recursive(n)

    def run_memoized():
        fib_memoized.cache_clear()
        return fib_memoized(n)

    def run_iterative():
        return fib_iterative(n)

    benchmark = Benchmark()
    result = benchmark.run(
        name="递归函数",
        description=f"计算斐波那契数列 fib({n})",
        methods={
            "朴素递归": run_recursive,
            "记忆化递归": run_memoized,
            "迭代": run_iterative,
        },
        iterations=1,
    )

    result.add_speedup("记忆化递归", "朴素递归")
    result.add_speedup("迭代", "朴素递归")

    return result


# ============================================================================
# 基准测试8：JIT编译效果模拟
# ============================================================================

def benchmark_jit_simulation():
    """
    模拟JIT编译的效果

    对比：
    1. 模拟解释器（每次操作都有额外的分派开销）
    2. "JIT编译"后的代码（消除分派开销）
    3. Python原生操作（参考基准）
    """
    n = 100000

    # 模拟解释器：每条指令都有分派开销
    class SimulatedInterpreter:
        def __init__(self):
            self.registers = [0.0] * 10
            self.instruction_count = 0

        def dispatch(self, opcode, *args):
            """模拟指令分派（开销来源）"""
            self.instruction_count += 1
            if opcode == 'LOAD_CONST':
                self.registers[args[0]] = args[1]
            elif opcode == 'ADD':
                self.registers[args[0]] = self.registers[args[1]] + self.registers[args[2]]
            elif opcode == 'MUL':
                self.registers[args[0]] = self.registers[args[1]] * self.registers[args[2]]
            elif opcode == 'STORE':
                pass  # 模拟存储

    def simulated_interpreter_loop():
        """模拟解释器执行循环"""
        interp = SimulatedInterpreter()
        total = 0.0
        for i in range(n):
            interp.dispatch('LOAD_CONST', 0, float(i))
            interp.dispatch('LOAD_CONST', 1, float(i))
            interp.dispatch('MUL', 2, 0, 1)      # i * i
            interp.dispatch('LOAD_CONST', 3, 2.0)
            interp.dispatch('MUL', 4, 2, 3)      # i*i * 2
            interp.dispatch('LOAD_CONST', 5, 1.0)
            interp.dispatch('ADD', 6, 4, 5)      # i*i*2 + 1
            total += interp.registers[6]
        return total

    def jit_compiled_loop():
        """"JIT编译"后的循环（消除分派开销）"""
        total = 0.0
        for i in range(n):
            # 直接计算，无分派开销
            r0 = float(i)
            r1 = float(i)
            r2 = r0 * r1
            r3 = 2.0
            r4 = r2 * r3
            r5 = 1.0
            r6 = r4 + r5
            total += r6
        return total

    def native_python_loop():
        """Python原生循环"""
        total = 0.0
        for i in range(n):
            total += i * i * 2 + 1
        return total

    benchmark = Benchmark()
    result = benchmark.run(
        name="JIT编译效果模拟",
        description=f"模拟解释器 vs JIT编译 vs 原生Python, n={n}",
        methods={
            "模拟解释器": simulated_interpreter_loop,
            "JIT编译后": jit_compiled_loop,
            "Python原生": native_python_loop,
        },
        iterations=n,
    )

    result.add_speedup("JIT编译后", "模拟解释器")
    result.add_speedup("Python原生", "模拟解释器")

    return result


# ============================================================================
# 结果报告
# ============================================================================

def print_report(results: List[BenchmarkResult]):
    """打印基准测试报告"""
    print("\n" + "=" * 70)
    print("  JIT编译性能基准测试报告")
    print("=" * 70)

    for result in results:
        print(f"\n{'─' * 70}")
        print(f"  {result.name}")
        print(f"  {result.description}")
        print(f"{'─' * 70}")

        # 找到最慢的方法作为基准
        slowest_name = max(result.results, key=result.results.get)
        slowest_time = result.results[slowest_name]

        print(f"\n  {'方法':<25} {'耗时':>12} {'相对速度':>10} {'加速比':>8}")
        print(f"  {'─' * 55}")

        for method_name, elapsed in sorted(result.results.items(),
                                            key=lambda x: x[1]):
            relative = elapsed / slowest_time if slowest_time > 0 else 1.0
            speedup = result.speedups.get(method_name, None)

            speedup_str = f"{speedup:.2f}x" if speedup is not None else "基准"

            if elapsed >= 1.0:
                time_str = f"{elapsed:.3f} s"
            elif elapsed >= 0.001:
                time_str = f"{elapsed*1000:.2f} ms"
            else:
                time_str = f"{elapsed*1000000:.1f} us"

            bar_len = int(relative * 20)
            bar = "█" * bar_len + "░" * (20 - bar_len)

            print(f"  {method_name:<25} {time_str:>12} "
                  f"{relative:>8.2f}x {speedup_str:>8}")

    # 总结
    print(f"\n{'=' * 70}")
    print("  总结")
    print(f"{'=' * 70}")
    print()
    print("  JIT编译的关键性能优化：")
    print()
    print("  1. 消除解释器分派开销")
    print("     - 每条字节码指令的分派（查表+跳转）约消耗 5-50ns")
    print("     - JIT编译后，指令直接在CPU上执行，无分派开销")
    print()
    print("  2. 类型特化")
    print("     - 解释器需要在每条指令处检查操作数类型")
    print("     - JIT编译器基于运行时类型信息生成特化代码")
    print()
    print("  3. 内联缓存")
    print("     - 属性访问从哈希表查找变为固定偏移访问")
    print("     - 单态缓存可达 ~1ns/次 访问")
    print()
    print("  4. 编译器优化")
    print("     - 常量折叠、死代码消除、循环优化等")
    print("     - 这些优化在编译时（而非运行时）完成")
    print()
    print("  注意：本基准测试在Python中模拟JIT效果，")
    print("  真正的JIT编译器（如LuaJIT、V8）的加速比通常在 10x-100x。")


def print_system_info():
    """打印系统信息"""
    print("=" * 70)
    print("  第10章：JIT编译 - 性能基准测试")
    print("=" * 70)
    print()
    print(f"  Python版本: {sys.version}")
    print(f"  平台: {sys.platform}")
    print()
    print("  本基准测试对比不同实现方式的性能差异，")
    print("  帮助理解JIT编译带来的性能提升。")
    print()
    print("  测试方法：")
    print("  - 每个测试运行多次，取中位数")
    print("  - 预热迭代确保Python内部缓存已填充")
    print("  - 加速比 = 基准时间 / 当前时间")


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主函数"""
    print_system_info()

    all_results = []

    # 运行所有基准测试
    print("\n" + "=" * 70)
    print("  开始基准测试")
    print("=" * 70)

    all_results.append(benchmark_integer_sum())
    all_results.append(benchmark_float_math())
    all_results.append(benchmark_polynomial())
    all_results.append(benchmark_array_processing())
    all_results.append(benchmark_attribute_access())
    all_results.append(benchmark_branching())
    all_results.append(benchmark_recursion())
    all_results.append(benchmark_jit_simulation())

    # 打印报告
    print_report(all_results)


if __name__ == "__main__":
    main()
