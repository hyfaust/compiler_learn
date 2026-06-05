#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
inline_cache_demo.py - 内联缓存和隐藏类演示

本模块演示JIT编译中内联缓存（Inline Caching）和隐藏类（Hidden Classes）的核心概念：
1. 隐藏类（Hidden Classes/Maps）- 将动态属性访问静态化
2. 内联缓存（Inline Caching）- 缓存属性查找的结果
3. 单态、多态、超态缓存的行为和性能差异
4. 属性访问的性能对比

这些概念是V8、JVM等现代JIT编译器优化动态语言的核心技术。

运行方式：
    python inline_cache_demo.py
"""

import time
import sys
from typing import Dict, Any, Optional, List, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum, auto


# ============================================================================
# 隐藏类（Hidden Class / Map）
# ============================================================================

class HiddenClass:
    """
    隐藏类

    隐藏类描述了对象的"形状"——对象有哪些属性，以及这些属性在内存中的布局。

    类似于V8中的Map概念：
    - 每个对象都有一个隐藏类
    - 具有相同属性添加顺序的对象共享隐藏类
    - 属性访问通过隐藏类映射到固定的内存偏移量

    示例：
        obj = {}        -> Map0: {}
        obj.x = 1       -> Map1: {x: offset 0}
        obj.y = 2       -> Map2: {x: offset 0, y: offset 1}
    """

    def __init__(self, class_id: int, parent: Optional['HiddenClass'] = None,
                 added_property: Optional[str] = None):
        self.class_id = class_id
        self.parent = parent
        self.property_offsets: Dict[str, int] = {}
        self.transitions: Dict[str, 'HiddenClass'] = {}  # 属性添加 -> 新的隐藏类

        # 继承父类的属性布局
        if parent:
            self.property_offsets = dict(parent.property_offsets)

        # 添加新属性
        if added_property:
            self.property_offsets[added_property] = len(self.property_offsets)

    def get_offset(self, property_name: str) -> Optional[int]:
        """获取属性在内存中的偏移量"""
        return self.property_offsets.get(property_name)

    def has_property(self, property_name: str) -> bool:
        """检查是否有某个属性"""
        return property_name in self.property_offsets

    @property
    def num_properties(self) -> int:
        return len(self.property_offsets)

    def __repr__(self):
        props = ", ".join(f"{k}:offset{v}" for k, v in
                          sorted(self.property_offsets.items(), key=lambda x: x[1]))
        return f"Map{self.class_id}({{{props}}})"

    def __eq__(self, other):
        if not isinstance(other, HiddenClass):
            return False
        return self.class_id == other.class_id

    def __hash__(self):
        return hash(self.class_id)


class HiddenClassSystem:
    """
    隐藏类系统

    管理所有隐藏类，负责：
    1. 创建新的隐藏类
    2. 维护隐藏类之间的转换关系
    3. 共享具有相同属性布局的隐藏类

    这模拟了V8引擎中Map的转换图（Transition Graph）。
    """

    def __init__(self):
        self.next_id = 0
        self.classes: Dict[int, HiddenClass] = {}
        # 根隐藏类（空对象）
        self.root = self._create_class()
        # 转换缓存：(parent_id, property_name) -> child_class
        self.transition_cache: Dict[Tuple[int, str], HiddenClass] = {}

    def _create_class(self, parent: Optional[HiddenClass] = None,
                      added_property: Optional[str] = None) -> HiddenClass:
        """创建新的隐藏类"""
        cls = HiddenClass(self.next_id, parent, added_property)
        self.classes[self.next_id] = cls
        self.next_id += 1
        return cls

    def add_property(self, hidden_class: HiddenClass,
                     property_name: str) -> HiddenClass:
        """
        为隐藏类添加一个属性，返回新的隐藏类

        这模拟了V8中的属性转换（Property Transition）：
        - 如果从当前隐藏类添加该属性的转换已存在，复用它
        - 否则创建新的隐藏类
        """
        # 检查转换缓存
        cache_key = (hidden_class.class_id, property_name)
        if cache_key in self.transition_cache:
            return self.transition_cache[cache_key]

        # 检查是否已有该属性
        if hidden_class.has_property(property_name):
            return hidden_class

        # 创建新的隐藏类
        new_class = self._create_class(hidden_class, property_name)

        # 注册转换
        hidden_class.transitions[property_name] = new_class
        self.transition_cache[cache_key] = new_class

        return new_class

    def get_stats(self) -> Dict[str, Any]:
        """获取隐藏类系统的统计信息"""
        return {
            "total_classes": len(self.classes),
            "total_transitions": len(self.transition_cache),
            "max_properties": max(c.num_properties for c in self.classes.values()),
        }


# ============================================================================
# 带隐藏类的对象
# ============================================================================

class JSObject:
    """
    模拟JavaScript对象

    每个对象都有：
    - hidden_class: 隐藏类（描述对象形状）
    - properties: 属性值数组（按偏移量索引）
    """

    def __init__(self, hidden_class: HiddenClass):
        self.hidden_class = hidden_class
        self.properties: List[Any] = [None] * hidden_class.num_properties

    def get_property(self, name: str) -> Any:
        """获取属性值"""
        offset = self.hidden_class.get_offset(name)
        if offset is None:
            raise AttributeError(f"对象没有属性: {name}")
        if offset >= len(self.properties):
            return None
        return self.properties[offset]

    def set_property(self, name: str, value: Any, class_system: HiddenClassSystem):
        """设置属性值"""
        offset = self.hidden_class.get_offset(name)
        if offset is None:
            # 属性不存在，需要转换隐藏类
            self.hidden_class = class_system.add_property(self.hidden_class, name)
            offset = self.hidden_class.get_offset(name)
            # 扩展属性数组
            while len(self.properties) <= offset:
                self.properties.append(None)
        self.properties[offset] = value

    def __repr__(self):
        props = {}
        for name, offset in self.hidden_class.property_offsets.items():
            if offset < len(self.properties):
                props[name] = self.properties[offset]
        return f"JSObject(Map{self.hidden_class.class_id}, {props})"


# ============================================================================
# 内联缓存
# ============================================================================

class CacheState(Enum):
    """内联缓存的状态"""
    UNINITIALIZED = auto()  # 未初始化
    MONOMORPHIC = auto()    # 单态：只见过一种隐藏类
    POLYMORPHIC = auto()    # 多态：见过2-4种隐藏类
    MEGAMORPHIC = auto()    # 超态：见过太多隐藏类，退化为字典查找


@dataclass
class CacheEntry:
    """内联缓存条目"""
    hidden_class: HiddenClass   # 对象的隐藏类
    property_offset: int        # 属性在对象中的偏移量
    hit_count: int = 0          # 命中次数


class InlineCache:
    """
    内联缓存

    在每个属性访问点维护一个内联缓存，记录：
    - 对象的隐藏类
    - 属性的偏移量

    缓存状态机：
    Uninitialized -> Monomorphic -> Polymorphic -> Megamorphic
    """

    # 多态缓存的最大条目数（超过则退化为超态）
    MAX_POLYMORPHIC_ENTRIES = 4

    def __init__(self, property_name: str):
        self.property_name = property_name
        self.state = CacheState.UNINITIALIZED
        self.entries: List[CacheEntry] = []
        self.total_accesses = 0
        self.hits = 0
        self.misses = 0

    def access(self, obj: JSObject) -> Tuple[Any, bool]:
        """
        访问对象的属性

        Args:
            obj: 要访问的对象

        Returns:
            (属性值, 是否缓存命中)
        """
        self.total_accesses += 1
        obj_class = obj.hidden_class

        if self.state == CacheState.UNINITIALIZED:
            # 首次访问，初始化缓存
            offset = obj_class.get_offset(self.property_name)
            if offset is not None:
                self.entries.append(CacheEntry(obj_class, offset))
                self.state = CacheState.MONOMORPHIC
                self.misses += 1
                return obj.properties[offset], False
            raise AttributeError(f"对象没有属性: {self.property_name}")

        elif self.state == CacheState.MONOMORPHIC:
            # 单态缓存：直接比较隐藏类
            entry = self.entries[0]
            if obj_class.class_id == entry.hidden_class.class_id:
                # 缓存命中！
                entry.hit_count += 1
                self.hits += 1
                return obj.properties[entry.property_offset], True
            else:
                # 缓存未命中，升级为多态缓存
                offset = obj_class.get_offset(self.property_name)
                if offset is not None:
                    self.entries.append(CacheEntry(obj_class, offset))
                    self.state = CacheState.POLYMORPHIC
                    self.misses += 1
                    return obj.properties[offset], False
                raise AttributeError(f"对象没有属性: {self.property_name}")

        elif self.state == CacheState.POLYMORPHIC:
            # 多态缓存：线性搜索
            for entry in self.entries:
                if obj_class.class_id == entry.hidden_class.class_id:
                    entry.hit_count += 1
                    self.hits += 1
                    return obj.properties[entry.property_offset], True

            # 缓存未命中
            offset = obj_class.get_offset(self.property_name)
            if offset is not None:
                if len(self.entries) < self.MAX_POLYMORPHIC_ENTRIES:
                    self.entries.append(CacheEntry(obj_class, offset))
                else:
                    # 超过最大条目数，退化为超态
                    self.state = CacheState.MEGAMORPHIC
                    self.entries.clear()
                self.misses += 1
                return obj.properties[offset], False
            raise AttributeError(f"对象没有属性: {self.property_name}")

        elif self.state == CacheState.MEGAMORPHIC:
            # 超态缓存：字典查找（最慢的路径）
            self.misses += 1
            offset = obj_class.get_offset(self.property_name)
            if offset is not None:
                return obj.properties[offset], False
            raise AttributeError(f"对象没有属性: {self.property_name}")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息"""
        hit_rate = self.hits / self.total_accesses * 100 if self.total_accesses > 0 else 0
        return {
            "property": self.property_name,
            "state": self.state.name,
            "total_accesses": self.total_accesses,
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": hit_rate,
            "entries": len(self.entries),
            "entry_details": [
                {"class_id": e.hidden_class.class_id, "offset": e.property_offset,
                 "hits": e.hit_count}
                for e in self.entries
            ]
        }

    def reset(self):
        """重置缓存"""
        self.state = CacheState.UNINITIALIZED
        self.entries.clear()
        self.total_accesses = 0
        self.hits = 0
        self.misses = 0


# ============================================================================
# 不使用内联缓存的属性访问
# ============================================================================

def naive_property_access(obj: JSObject, property_name: str) -> Any:
    """
    不使用内联缓存的属性访问（字典查找）

    这模拟了没有内联缓存的解释器的行为。
    每次属性访问都需要查找隐藏类中的属性偏移量。
    """
    offset = obj.hidden_class.get_offset(property_name)
    if offset is None:
        raise AttributeError(f"对象没有属性: {property_name}")
    return obj.properties[offset]


# ============================================================================
# 演示函数
# ============================================================================

def demo_hidden_classes():
    """演示隐藏类的概念"""
    print("=" * 70)
    print("隐藏类（Hidden Classes）演示")
    print("=" * 70)
    print()
    print("隐藏类将动态语言的对象形状静态化，")
    print("使得属性访问可以通过固定偏移量而不是哈希表查找。")
    print()

    system = HiddenClassSystem()

    print("[1] 属性转换图（Transition Graph）")
    print("-" * 50)

    # 创建对象并逐步添加属性
    print("  模拟JavaScript代码：")
    print("    let obj1 = {};")
    print("    obj1.x = 1;")
    print("    obj1.y = 2;")
    print("    obj1.z = 3;")
    print()

    # 手动追踪转换
    current_class = system.root
    print(f"  初始: {current_class}")

    for prop in ["x", "y", "z"]:
        new_class = system.add_property(current_class, prop)
        print(f"  添加 '{prop}' -> {new_class}")
        current_class = new_class

    print("\n[2] 隐藏类共享")
    print("-" * 50)

    print("  模拟JavaScript代码：")
    print("    let obj1 = {}; obj1.x = 1; obj1.y = 2;")
    print("    let obj2 = {}; obj2.x = 10; obj2.y = 20;")
    print()

    # obj1 的转换路径
    obj1_class = system.root
    obj1_class = system.add_property(obj1_class, "x")
    obj1_class = system.add_property(obj1_class, "y")

    # obj2 的转换路径（相同的属性添加顺序）
    obj2_class = system.root
    obj2_class = system.add_property(obj2_class, "x")
    obj2_class = system.add_property(obj2_class, "y")

    print(f"  obj1 的隐藏类: {obj1_class}")
    print(f"  obj2 的隐藏类: {obj2_class}")
    print(f"  共享同一个隐藏类: {obj1_class.class_id == obj2_class.class_id}")

    print("\n[3] 不同的属性添加顺序 -> 不同的隐藏类")
    print("-" * 50)

    print("  模拟JavaScript代码：")
    print("    let obj3 = {}; obj3.x = 1; obj3.y = 2;")
    print("    let obj4 = {}; obj4.y = 2; obj4.x = 1;  // 顺序不同！")
    print()

    # obj3: 先x后y
    obj3_class = system.root
    obj3_class = system.add_property(obj3_class, "x")
    obj3_class = system.add_property(obj3_class, "y")

    # obj4: 先y后x
    obj4_class = system.root
    obj4_class = system.add_property(obj4_class, "y")
    obj4_class = system.add_property(obj4_class, "x")

    print(f"  obj3 的隐藏类: {obj3_class}")
    print(f"  obj4 的隐藏类: {obj4_class}")
    print(f"  共享同一个隐藏类: {obj3_class.class_id == obj4_class.class_id}")
    print()
    print("  注意：虽然属性名相同，但顺序不同导致内存布局不同，")
    print("  因此它们有不同的隐藏类！")

    print("\n[4] 隐藏类统计")
    print("-" * 50)
    stats = system.get_stats()
    for key, value in stats.items():
        print(f"  {key}: {value}")


def demo_inline_cache():
    """演示内联缓存的行为"""
    print("\n" + "=" * 70)
    print("内联缓存（Inline Caching）演示")
    print("=" * 70)

    system = HiddenClassSystem()

    # 创建不同形状的对象
    # 形状A: {x, y}
    class_a = system.root
    class_a = system.add_property(class_a, "x")
    class_a = system.add_property(class_a, "y")

    # 形状B: {x, y, z}
    class_b = system.root
    class_b = system.add_property(class_b, "x")
    class_b = system.add_property(class_b, "y")
    class_b = system.add_property(class_b, "z")

    # 形状C: {name, age}
    class_c = system.root
    class_c = system.add_property(class_c, "name")
    class_c = system.add_property(class_c, "age")

    # 形状D: {x, y, z, w}
    class_d = system.root
    class_d = system.add_property(class_d, "x")
    class_d = system.add_property(class_d, "y")
    class_d = system.add_property(class_d, "z")
    class_d = system.add_property(class_d, "w")

    # 创建对象
    def make_obj(cls, values):
        obj = JSObject(cls)
        obj.properties = list(values)
        return obj

    # === 单态缓存演示 ===
    print("\n[1] 单态缓存（Monomorphic）")
    print("-" * 50)
    print("  场景：所有对象都有相同的形状（Map{y:offset0, x:offset1}）")
    print()

    cache_mono = InlineCache("x")

    for i in range(10):
        obj = make_obj(class_a, [float(i * 10), float(i)])
        value, hit = cache_mono.access(obj)
        status = "命中" if hit else "未命中"
        if i < 5 or i == 9:
            print(f"  访问 obj{i}.x = {value} [{status}] 缓存状态: {cache_mono.state.name}")

    stats = cache_mono.get_stats()
    print(f"\n  统计: 命中率={stats['hit_rate']:.1f}%, "
          f"命中={stats['hits']}, 未命中={stats['misses']}")

    # === 多态缓存演示 ===
    print("\n[2] 多态缓存（Polymorphic）")
    print("-" * 50)
    print("  场景：对象有2-4种不同的形状，但都有属性'x'")
    print()

    cache_poly = InlineCache("x")

    shapes = [
        (class_a, [1.0, 2.0], "形状A {x,y}"),
        (class_b, [3.0, 4.0, 5.0], "形状B {x,y,z}"),
        (class_c, [6.0, 7.0], "形状C {name,age}"),  # 注意：没有x属性
    ]

    # 先用形状A和B的对象（都有x属性）
    for i in range(20):
        cls, vals, name = shapes[i % 2]  # 交替使用形状A和B
        obj = make_obj(cls, vals)
        try:
            value, hit = cache_poly.access(obj)
            status = "命中" if hit else "未命中"
            if i < 8 or i == 19:
                print(f"  访问 {name}.x = {value} [{status}] "
                      f"缓存状态: {cache_poly.state.name}")
        except AttributeError:
            pass

    stats = cache_poly.get_stats()
    print(f"\n  统计: 命中率={stats['hit_rate']:.1f}%, "
          f"命中={stats['hits']}, 未命中={stats['misses']}")
    print(f"  缓存条目数: {stats['entries']}")

    # === 超态缓存演示 ===
    print("\n[3] 超态缓存（Megamorphic）")
    print("-" * 50)
    print("  场景：对象有超过4种不同的形状")
    print()

    # 创建更多形状
    many_classes = []
    for i in range(6):
        cls = system.root
        for j in range(i + 2):
            cls = system.add_property(cls, f"prop_{j}")
        # 确保有 'x' 属性
        cls = system.add_property(cls, "x")
        many_classes.append(cls)

    cache_mega = InlineCache("x")

    for i in range(30):
        cls = many_classes[i % len(many_classes)]
        obj = make_obj(cls, list(range(cls.num_properties)))
        value, hit = cache_mega.access(obj)
        status = "命中" if hit else "未命中"
        if i < 10 or i == 29:
            print(f"  访用 Map{cls.class_id}.x = {value} [{status}] "
                  f"缓存状态: {cache_mega.state.name}")

    stats = cache_mega.get_stats()
    print(f"\n  统计: 命中率={stats['hit_rate']:.1f}%, "
          f"命中={stats['hits']}, 未命中={stats['misses']}")


def demo_performance_comparison():
    """演示内联缓存的性能差异"""
    print("\n" + "=" * 70)
    print("性能对比：单态 vs 多态 vs 超态缓存")
    print("=" * 70)

    system = HiddenClassSystem()

    # 创建不同数量的形状
    shapes = []
    for i in range(10):
        cls = system.root
        # 每个形状有不同的属性集合，但都有 'x'
        for j in range(i):
            cls = system.add_property(cls, f"extra_{j}")
        cls = system.add_property(cls, "x")
        shapes.append(cls)

    iterations = 10000

    # === 单态场景 ===
    print(f"\n[1] 单态场景: {iterations}次属性访问，所有对象同一形状")
    print("-" * 50)

    cache_mono = InlineCache("x")
    obj = JSObject(shapes[0])
    obj.properties = [42.0] * shapes[0].num_properties

    start = time.perf_counter()
    for _ in range(iterations):
        cache_mono.access(obj)
    mono_time = time.perf_counter() - start

    stats = cache_mono.get_stats()
    print(f"  命中率: {stats['hit_rate']:.1f}%")
    print(f"  耗时: {mono_time*1000:.2f} ms")

    # === 多态场景 ===
    print(f"\n[2] 多态场景: {iterations}次属性访问，4种形状")
    print("-" * 50)

    cache_poly = InlineCache("x")
    objs_poly = []
    for i in range(4):
        obj = JSObject(shapes[i])
        obj.properties = [float(i)] * shapes[i].num_properties
        objs_poly.append(obj)

    start = time.perf_counter()
    for i in range(iterations):
        cache_poly.access(objs_poly[i % 4])
    poly_time = time.perf_counter() - start

    stats = cache_poly.get_stats()
    print(f"  命中率: {stats['hit_rate']:.1f}%")
    print(f"  耗时: {poly_time*1000:.2f} ms")
    print(f"  相对于单态: {poly_time/mono_time:.2f}x")

    # === 超态场景 ===
    print(f"\n[3] 超态场景: {iterations}次属性访问，6种形状（超过阈值）")
    print("-" * 50)

    cache_mega = InlineCache("x")
    objs_mega = []
    for i in range(6):
        obj = JSObject(shapes[i])
        obj.properties = [float(i)] * shapes[i].num_properties
        objs_mega.append(obj)

    start = time.perf_counter()
    for i in range(iterations):
        cache_mega.access(objs_mega[i % 6])
    mega_time = time.perf_counter() - start

    stats = cache_mega.get_stats()
    print(f"  命中率: {stats['hit_rate']:.1f}%")
    print(f"  耗时: {mega_time*1000:.2f} ms")
    print(f"  相对于单态: {mega_time/mono_time:.2f}x")

    # === 无缓存场景（字典查找） ===
    print(f"\n[4] 无缓存场景: {iterations}次属性访问，每次都查找偏移量")
    print("-" * 50)

    start = time.perf_counter()
    for i in range(iterations):
        obj = objs_mega[i % 6]
        naive_property_access(obj, "x")
    dict_time = time.perf_counter() - start

    print(f"  耗时: {dict_time*1000:.2f} ms")
    print(f"  相对于单态: {dict_time/mono_time:.2f}x")

    # 总结
    print(f"\n[性能总结]")
    print("-" * 50)
    print(f"  单态缓存:  {mono_time*1000:.2f} ms (基准)")
    print(f"  多态缓存:  {poly_time*1000:.2f} ms ({poly_time/mono_time:.2f}x)")
    print(f"  超态缓存:  {mega_time*1000:.2f} ms ({mega_time/mono_time:.2f}x)")
    print(f"  无缓存:    {dict_time*1000:.2f} ms ({dict_time/mono_time:.2f}x)")


def demo_v8_style_optimization():
    """演示V8风格的优化"""
    print("\n" + "=" * 70)
    print("V8风格优化演示")
    print("=" * 70)
    print()
    print("V8引擎使用隐藏类和内联缓存来优化JavaScript属性访问。")
    print()

    system = HiddenClassSystem()

    print("[1] 最佳实践：一致的对象形状")
    print("-" * 50)
    print("  好的代码：")
    print("    function Point(x, y) {")
    print("      this.x = x;  // 总是先x")
    print("      this.y = y;  // 再y")
    print("    }")
    print("    let p1 = new Point(1, 2);")
    print("    let p2 = new Point(3, 4);")
    print("    // p1和p2共享同一个隐藏类！")
    print()

    # 模拟
    point_class = system.root
    point_class = system.add_property(point_class, "x")
    point_class = system.add_property(point_class, "y")

    p1 = JSObject(point_class)
    p1.properties = [1.0, 2.0]
    p2 = JSObject(point_class)
    p2.properties = [3.0, 4.0]

    print(f"  p1.hidden_class = {p1.hidden_class}")
    print(f"  p2.hidden_class = {p2.hidden_class}")
    print(f"  共享隐藏类: {p1.hidden_class == p2.hidden_class}")

    print("\n[2] 反模式：不一致的对象形状")
    print("-" * 50)
    print("  坏的代码：")
    print("    let obj1 = {}; obj1.x = 1; obj1.y = 2;")
    print("    let obj2 = {}; obj2.y = 2; obj2.x = 1;  // 顺序不同！")
    print()

    class_system = HiddenClassSystem()

    obj1 = JSObject(class_system.root)
    obj1.set_property("x", 1.0, class_system)
    obj1.set_property("y", 2.0, class_system)

    obj2 = JSObject(class_system.root)
    obj2.set_property("y", 2.0, class_system)
    obj2.set_property("x", 1.0, class_system)

    print(f"  obj1.hidden_class = {obj1.hidden_class}")
    print(f"  obj2.hidden_class = {obj2.hidden_class}")
    print(f"  共享隐藏类: {obj1.hidden_class == obj2.hidden_class}")
    print(f"  obj1.x 的偏移量: {obj1.hidden_class.get_offset('x')}")
    print(f"  obj2.x 的偏移量: {obj2.hidden_class.get_offset('x')}")
    print()
    print("  由于属性添加顺序不同，它们有不同的隐藏类和不同的偏移量！")
    print("  这会导致内联缓存失败，性能下降。")

    print("\n[3] 内联缓存对JIT编译的影响")
    print("-" * 50)
    print("  JIT编译器使用内联缓存信息来生成特化代码：")
    print()
    print("  单态缓存 -> 生成特化代码：")
    print("    if (obj.map === cachedMap) {")
    print("      // 快速路径：直接偏移访问")
    print("      return obj[offset];")
    print("    } else {")
    print("      // 慢路径：更新缓存")
    print("      slowPath(obj);")
    print("    }")
    print()
    print("  多态缓存 -> 生成类型检查链：")
    print("    if (obj.map === map1) return obj[offset1];")
    print("    if (obj.map === map2) return obj[offset2];")
    print("    if (obj.map === map3) return obj[offset3];")
    print("    slowPath(obj);")
    print()
    print("  超态缓存 -> 生成通用的字典查找：")
    print("    return dictionaryLookup(obj, propertyName);")


def demo_real_world_patterns():
    """演示真实世界中的模式"""
    print("\n" + "=" * 70)
    print("真实世界模式分析")
    print("=" * 70)
    print()
    print("以下是一些在JavaScript/V8中常见的模式及其对性能的影响。")
    print()

    system = HiddenClassSystem()

    # 模式1：构造函数模式
    print("[1] 构造函数模式（推荐）")
    print("-" * 50)

    class PointFactory:
        def __init__(self, cs: HiddenClassSystem):
            self.cs = cs
            self.cls = cs.root
            self.cls = cs.add_property(self.cls, "x")
            self.cls = cs.add_property(self.cls, "y")

        def create(self, x: float, y: float) -> JSObject:
            obj = JSObject(self.cls)
            obj.properties = [x, y]
            return obj

    factory = PointFactory(system)
    points = [factory.create(float(i), float(i * 2)) for i in range(100)]

    # 所有点共享同一个隐藏类
    unique_classes = set(p.hidden_class.class_id for p in points)
    print(f"  创建了 {len(points)} 个点对象")
    print(f"  唯一隐藏类数: {len(unique_classes)}")
    print(f"  所有对象共享隐藏类: {len(unique_classes) == 1}")

    # 模式2：动态添加属性（不推荐）
    print("\n[2] 动态添加属性模式（不推荐）")
    print("-" * 50)

    cs2 = HiddenClassSystem()
    objects = []

    for i in range(10):
        obj = JSObject(cs2.root)
        # 每个对象以不同的顺序添加不同的属性
        if i % 3 == 0:
            obj.set_property("x", float(i), cs2)
            obj.set_property("y", float(i), cs2)
        elif i % 3 == 1:
            obj.set_property("y", float(i), cs2)
            obj.set_property("x", float(i), cs2)
        else:
            obj.set_property("x", float(i), cs2)
            obj.set_property("z", float(i), cs2)
        objects.append(obj)

    unique_classes = set(o.hidden_class.class_id for o in objects)
    print(f"  创建了 {len(objects)} 个对象")
    print(f"  唯一隐藏类数: {len(unique_classes)}")
    print(f"  隐藏类碎片化: 是（内联缓存效率低）")

    # 模式3：单态函数（推荐）
    print("\n[3] 单态函数（推荐）")
    print("-" * 50)

    cache = InlineCache("x")

    def process_points(points_list):
        total = 0.0
        for p in points_list:
            value, hit = cache.access(p)
            total += value
        return total

    total = process_points(points)
    stats = cache.get_stats()
    print(f"  处理 {len(points)} 个点对象")
    print(f"  结果: {total:.0f}")
    print(f"  缓存命中率: {stats['hit_rate']:.1f}%")
    print(f"  缓存状态: {stats['state']} (单态 = 最佳)")

    # 模式4：多态函数（可接受）
    print("\n[4] 多态函数（可接受）")
    print("-" * 50)

    cache2 = InlineCache("x")
    mixed_objects = []

    # 混合不同形状的对象
    for i in range(100):
        if i % 2 == 0:
            obj = factory.create(float(i), float(i))
        else:
            obj2 = JSObject(system.add_property(system.add_property(
                system.root, "x"), "z"))
            obj2.properties = [float(i), float(i)]
            mixed_objects.append(obj2)
            continue
        mixed_objects.append(obj)

    total = 0.0
    for obj in mixed_objects:
        try:
            value, hit = cache2.access(obj)
            total += value
        except AttributeError:
            pass

    stats = cache2.get_stats()
    print(f"  处理 {len(mixed_objects)} 个混合形状对象")
    print(f"  结果: {total:.0f}")
    print(f"  缓存命中率: {stats['hit_rate']:.1f}%")
    print(f"  缓存状态: {stats['state']}")


# ============================================================================
# 主函数
# ============================================================================

def main():
    """主函数"""
    print("=" * 70)
    print("  第10章：JIT编译 - 内联缓存和隐藏类演示")
    print("=" * 70)
    print()
    print("本演示展示JIT编译中内联缓存和隐藏类的核心概念：")
    print("  1. 隐藏类（Hidden Classes）- 将动态属性访问静态化")
    print("  2. 内联缓存（Inline Caching）- 缓存属性查找结果")
    print("  3. 单态/多态/超态缓存的行为和性能差异")
    print("  4. V8风格的优化策略")
    print()

    # 演示1：隐藏类
    demo_hidden_classes()

    # 演示2：内联缓存
    demo_inline_cache()

    # 演示3：性能对比
    demo_performance_comparison()

    # 演示4：V8风格优化
    demo_v8_style_optimization()

    # 演示5：真实世界模式
    demo_real_world_patterns()

    print("\n" + "=" * 70)
    print("演示完成!")
    print("=" * 70)
    print()
    print("关键要点：")
    print("  1. 隐藏类将动态语言的属性访问转换为静态偏移量访问")
    print("  2. 相同属性添加顺序的对象共享隐藏类（内存效率）")
    print("  3. 内联缓存大幅减少属性查找的开销")
    print("  4. 单态缓存最快，超态缓存退化为字典查找")
    print("  5. JIT编译器利用内联缓存信息生成特化代码")
    print("  6. 编写JIT友好的代码：保持对象形状一致")


if __name__ == "__main__":
    main()
