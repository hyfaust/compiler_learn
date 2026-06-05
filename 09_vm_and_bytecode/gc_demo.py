"""
垃圾回收演示
============
演示标记-清除垃圾回收算法，包括：
- 简单的标记-清除GC实现
- 对象分配和引用管理
- GC触发和执行
- 可视化GC过程
"""

from typing import Dict, List, Set, Any, Optional
from dataclasses import dataclass, field
from enum import Enum, auto
import time
import random


class GCState(Enum):
    """GC状态"""
    WHITE = auto()   # 未被访问
    GRAY = auto()    # 已被访问，但引用的对象未全部访问
    BLACK = auto()   # 已被访问，且引用的对象全部访问


@dataclass
class GCObject:
    """GC管理的对象"""
    id: int
    name: str
    size: int  # 对象大小（字节）
    references: List[int] = field(default_factory=list)  # 引用的其他对象ID
    state: GCState = GCState.WHITE
    marked: bool = False  # 标记-清除算法使用
    
    def __str__(self):
        return f"Object({self.id}, {self.name}, size={self.size})"


class GarbageCollector:
    """垃圾回收器"""

    def __init__(self, heap_size: int = 1024, verbose: bool = True):
        self.heap_size = heap_size
        self.objects: Dict[int, GCObject] = {}
        self.roots: Set[int] = set()  # 根对象集合
        self.free_memory: int = heap_size
        self.next_id: int = 0
        self.gc_count: int = 0
        self.total_allocated: int = 0
        self.total_freed: int = 0
        self.gc_threshold: int = heap_size // 2  # 触发GC的阈值
        self.verbose = verbose
    
    def allocate(self, name: str, size: int) -> Optional[int]:
        """分配对象"""
        # 检查是否有足够内存
        if size > self.free_memory:
            if self.verbose:
                print(f"[GC] 内存不足，触发垃圾回收...")
            self.collect()
            
            if size > self.free_memory:
                if self.verbose:
                    print(f"[GC] 回收后内存仍然不足，分配失败")
                return None
        
        # 分配对象
        obj_id = self.next_id
        self.next_id += 1
        
        obj = GCObject(id=obj_id, name=name, size=size)
        self.objects[obj_id] = obj
        self.free_memory -= size
        self.total_allocated += size
        
        if self.verbose:
            print(f"[分配] {obj}，剩余内存: {self.free_memory}")
        
        # 检查是否需要触发GC
        if self.free_memory < self.gc_threshold:
            if self.verbose:
                print(f"[GC] 内存使用超过阈值，触发垃圾回收...")
            self.collect()
        
        return obj_id
    
    def add_root(self, obj_id: int):
        """添加根对象"""
        if obj_id in self.objects:
            self.roots.add(obj_id)
            if self.verbose:
                print(f"[根] 添加根对象: {self.objects[obj_id]}")
    
    def remove_root(self, obj_id: int):
        """移除根对象"""
        if obj_id in self.roots:
            self.roots.remove(obj_id)
            if self.verbose:
                print(f"[根] 移除根对象: {obj_id}")
    
    def add_reference(self, from_id: int, to_id: int):
        """添加引用关系"""
        if from_id in self.objects and to_id in self.objects:
            self.objects[from_id].references.append(to_id)
            if self.verbose:
                print(f"[引用] {self.objects[from_id]} -> {self.objects[to_id]}")
    
    def collect(self):
        """执行垃圾回收"""
        self.gc_count += 1
        if self.verbose:
            print(f"\n{'='*50}")
            print(f"[GC] 开始第 {self.gc_count} 次垃圾回收")
            print(f"[GC] 回收前状态:")
            self._print_heap_state()
        
        # 标记阶段
        self._mark_phase()
        
        # 清除阶段
        freed = self._sweep_phase()
        
        if self.verbose:
            print(f"\n[GC] 回收完成，释放了 {freed} 个对象")
            print(f"[GC] 回收后状态:")
            self._print_heap_state()
            print(f"{'='*50}\n")
    
    def _mark_phase(self):
        """标记阶段：标记所有可达对象"""
        if self.verbose:
            print(f"\n[标记阶段] 开始标记...")
        
        # 重置所有对象状态
        for obj in self.objects.values():
            obj.state = GCState.WHITE
            obj.marked = False
        
        # 将根对象标记为灰色
        gray_set: Set[int] = set()
        for root_id in self.roots:
            if root_id in self.objects:
                self.objects[root_id].state = GCState.GRAY
                gray_set.add(root_id)
        
        if self.verbose:
            print(f"[标记阶段] 根对象: {gray_set}")
        
        # 三色标记法
        while gray_set:
            # 选择一个灰色对象
            obj_id = gray_set.pop()
            obj = self.objects[obj_id]
            
            if self.verbose:
                print(f"[标记阶段] 处理灰色对象: {obj}")
            
            # 将其引用的对象标记为灰色
            for ref_id in obj.references:
                if ref_id in self.objects and self.objects[ref_id].state == GCState.WHITE:
                    self.objects[ref_id].state = GCState.GRAY
                    gray_set.add(ref_id)
                    if self.verbose:
                        print(f"[标记阶段] 标记为灰色: {self.objects[ref_id]}")
            
            # 将当前对象标记为黑色
            obj.state = GCState.BLACK
            obj.marked = True
            
            if self.verbose:
                print(f"[标记阶段] 标记为黑色: {obj}")
        
        if self.verbose:
            print(f"[标记阶段] 标记完成")
    
    def _sweep_phase(self) -> int:
        """清除阶段：回收未标记的对象"""
        if self.verbose:
            print(f"\n[清除阶段] 开始清除...")
        
        freed_objects = []
        objects_to_remove = []
        
        for obj_id, obj in self.objects.items():
            if not obj.marked:
                # 未标记的对象将被回收
                freed_objects.append(obj)
                objects_to_remove.append(obj_id)
                self.free_memory += obj.size
                self.total_freed += obj.size
                
                if self.verbose:
                    print(f"[清除阶段] 回收对象: {obj}")
            else:
                # 重置标记状态
                obj.marked = False
                obj.state = GCState.WHITE
        
        # 移除未标记的对象
        for obj_id in objects_to_remove:
            del self.objects[obj_id]
        
        return len(freed_objects)
    
    def _print_heap_state(self):
        """打印堆状态"""
        print(f"  堆大小: {self.heap_size}")
        print(f"  已分配: {self.heap_size - self.free_memory}")
        print(f"  空闲内存: {self.free_memory}")
        print(f"  对象数量: {len(self.objects)}")
        print(f"  根对象数量: {len(self.roots)}")
        
        if self.objects:
            print(f"  对象列表:")
            for obj_id, obj in self.objects.items():
                root_mark = " (根)" if obj_id in self.roots else ""
                print(f"    {obj}{root_mark}")
    
    def print_statistics(self):
        """打印统计信息"""
        print(f"\n{'='*50}")
        print(f"垃圾回收统计:")
        print(f"  总分配次数: {self.total_allocated}")
        print(f"  总释放次数: {self.total_freed}")
        print(f"  GC次数: {self.gc_count}")
        print(f"  当前对象数量: {len(self.objects)}")
        print(f"  当前空闲内存: {self.free_memory}")
        print(f"{'='*50}")


class ObjectGraphVisualizer:
    """对象图可视化器"""
    
    @staticmethod
    def visualize(gc: GarbageCollector):
        """可视化对象图"""
        print(f"\n{'='*50}")
        print("对象图可视化:")
        print(f"{'='*50}")
        
        if not gc.objects:
            print("  (空堆)")
            return
        
        # 创建对象到索引的映射
        obj_to_idx = {obj_id: i for i, obj_id in enumerate(gc.objects.keys())}
        
        # 打印对象节点
        print("\n对象节点:")
        for obj_id, obj in gc.objects.items():
            root_mark = "★" if obj_id in gc.roots else " "
            state_mark = ""
            if obj.state == GCState.WHITE:
                state_mark = "○"
            elif obj.state == GCState.GRAY:
                state_mark = "◐"
            elif obj.state == GCState.BLACK:
                state_mark = "●"
            
            print(f"  {root_mark}{state_mark} [{obj_to_idx[obj_id]}] {obj.name} (大小: {obj.size})")
        
        # 打印引用关系
        print("\n引用关系:")
        for obj_id, obj in gc.objects.items():
            if obj.references:
                refs = [f"[{obj_to_idx[ref]}]" for ref in obj.references if ref in obj_to_idx]
                print(f"  [{obj_to_idx[obj_id]}] {obj.name} -> {', '.join(refs)}")
        
        # 打印ASCII图
        print("\nASCII图:")
        ObjectGraphVisualizer._draw_ascii_graph(gc, obj_to_idx)
    
    @staticmethod
    def _draw_ascii_graph(gc: GarbageCollector, obj_to_idx: Dict[int, int]):
        """绘制ASCII图"""
        if not gc.objects:
            return
        
        # 简单的ASCII图
        for obj_id, obj in gc.objects.items():
            idx = obj_to_idx[obj_id]
            root_mark = "★" if obj_id in gc.roots else " "
            
            # 绘制对象
            print(f"  {root_mark}[{idx}]┌─────────┐")
            print(f"      │{obj.name:^9}│")
            print(f"      │大小:{obj.size:^4}│")
            print(f"      └─────────┘")
            
            # 绘制引用
            for ref_id in obj.references:
                if ref_id in obj_to_idx:
                    ref_idx = obj_to_idx[ref_id]
                    print(f"        │")
                    print(f"        ▼")
                    print(f"      [{ref_idx}]")


def demonstrate_simple_gc():
    """演示简单的垃圾回收"""
    print("="*60)
    print("演示1: 简单的垃圾回收")
    print("="*60)
    
    gc = GarbageCollector(heap_size=100, verbose=True)
    
    # 分配一些对象
    print("\n1. 分配对象:")
    a = gc.allocate("对象A", 20)
    b = gc.allocate("对象B", 15)
    c = gc.allocate("对象C", 25)
    d = gc.allocate("对象D", 10)
    
    # 设置根对象
    print("\n2. 设置根对象:")
    gc.add_root(a)
    gc.add_root(b)
    
    # 建立引用关系
    print("\n3. 建立引用关系:")
    gc.add_reference(a, c)  # A -> C
    gc.add_reference(b, d)  # B -> D
    
    # 可视化对象图
    ObjectGraphVisualizer.visualize(gc)
    
    # 移除根对象B，使其不可达
    print("\n4. 移除根对象B:")
    gc.remove_root(b)
    
    # 触发垃圾回收
    print("\n5. 触发垃圾回收:")
    gc.collect()
    
    # 可视化回收后的对象图
    ObjectGraphVisualizer.visualize(gc)
    
    gc.print_statistics()


def demonstrate_circular_reference():
    """演示循环引用的垃圾回收"""
    print("\n" + "="*60)
    print("演示2: 循环引用的垃圾回收")
    print("="*60)
    
    gc = GarbageCollector(heap_size=100, verbose=True)
    
    # 分配对象
    print("\n1. 分配对象:")
    a = gc.allocate("对象A", 20)
    b = gc.allocate("对象B", 20)
    c = gc.allocate("对象C", 20)
    
    # 设置根对象
    print("\n2. 设置根对象:")
    gc.add_root(a)
    
    # 建立循环引用
    print("\n3. 建立循环引用:")
    gc.add_reference(a, b)  # A -> B
    gc.add_reference(b, c)  # B -> C
    gc.add_reference(c, a)  # C -> A (循环)
    
    # 可视化对象图
    ObjectGraphVisualizer.visualize(gc)
    
    # 移除根对象A
    print("\n4. 移除根对象A:")
    gc.remove_root(a)
    
    # 触发垃圾回收
    print("\n5. 触发垃圾回收:")
    gc.collect()
    
    # 可视化回收后的对象图
    ObjectGraphVisualizer.visualize(gc)
    
    gc.print_statistics()


def demonstrate_memory_pressure():
    """演示内存压力下的垃圾回收"""
    print("\n" + "="*60)
    print("演示3: 内存压力下的垃圾回收")
    print("="*60)
    
    gc = GarbageCollector(heap_size=50, verbose=False)
    
    print("分配大量对象，观察自动垃圾回收...")
    
    for i in range(20):
        # 分配对象
        obj_id = gc.allocate(f"对象{i}", 10)
        if obj_id is not None:
            # 随机添加根对象
            if random.random() < 0.3:
                gc.add_root(obj_id)
            
            # 随机添加引用
            if random.random() < 0.5 and len(gc.objects) > 1:
                ref_id = random.choice(list(gc.objects.keys()))
                if ref_id != obj_id:
                    gc.add_reference(obj_id, ref_id)
        
        # 随机移除根对象
        if random.random() < 0.2 and gc.roots:
            root_to_remove = random.choice(list(gc.roots))
            gc.remove_root(root_to_remove)
    
    print(f"\n最终状态:")
    gc.print_statistics()


def demonstrate_generational_gc_concept():
    """演示分代垃圾回收概念"""
    print("\n" + "="*60)
    print("演示4: 分代垃圾回收概念")
    print("="*60)
    
    print("""
分代垃圾回收基于对象生命周期的观察：
1. 大多数对象生命周期很短（"婴儿死亡率"高）
2. 存活时间长的对象往往继续存活

分代策略：
- 年轻代（Young Generation）：新创建的对象
  - Eden区：新对象分配区
  - Survivor区：存活对象区
- 老年代（Old Generation）：存活时间长的对象
- 永久代（Permanent Generation）：类元数据等

GC过程：
1. 年轻代GC（Minor GC）：频繁，快速
2. 老年代GC（Major GC）：不频繁，较慢
3. 对象晋升：存活多次Minor GC的对象晋升到老年代
""")
    
    # 模拟分代GC
    gc = GarbageCollector(heap_size=200, verbose=False)
    
    print("模拟分代垃圾回收:")
    print("1. 分配年轻代对象:")
    
    young_objects = []
    for i in range(10):
        obj_id = gc.allocate(f"年轻对象{i}", 10)
        if obj_id is not None:
            young_objects.append(obj_id)
    
    print(f"   分配了 {len(young_objects)} 个年轻代对象")
    
    print("\n2. 模拟Minor GC（保留部分对象）:")
    # 保留前3个对象作为"存活"对象
    for obj_id in young_objects[:3]:
        gc.add_root(obj_id)
    
    gc.collect()
    print(f"   Minor GC后剩余对象: {len(gc.objects)}")
    
    print("\n3. 分配更多对象:")
    for i in range(5):
        gc.allocate(f"新对象{i}", 10)
    
    print(f"   当前对象总数: {len(gc.objects)}")
    
    print("\n4. 模拟Major GC:")
    gc.collect()
    print(f"   Major GC后剩余对象: {len(gc.objects)}")
    
    gc.print_statistics()


def main():
    """主函数"""
    print("垃圾回收演示程序")
    print("本程序演示标记-清除垃圾回收算法的工作原理")
    
    # 演示1：简单的垃圾回收
    demonstrate_simple_gc()
    
    # 演示2：循环引用
    demonstrate_circular_reference()
    
    # 演示3：内存压力
    demonstrate_memory_pressure()
    
    # 演示4：分代GC概念
    demonstrate_generational_gc_concept()
    
    print("\n" + "="*60)
    print("演示完成！")
    print("="*60)


if __name__ == "__main__":
    main()