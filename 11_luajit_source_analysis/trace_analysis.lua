#!/usr/bin/env luajit
-- ============================================================================
-- trace_analysis.lua
-- LuaJIT Trace 编译分析工具
--
-- 演示 LuaJIT 的 trace 录制机制，包括：
--   1. 触发 JIT 编译
--   2. 查看 trace 信息
--   3. 演示 trace 编译的触发条件
--   4. 对比 JIT 前后的性能
--
-- 用法：
--   luajit trace_analysis.lua              -- 正常运行
--   luajit -jv trace_analysis.lua          -- 查看 JIT 编译日志
--   luajit -jdump trace_analysis.lua       -- 查看 trace dump（IR + 汇编）
--   luajit -joff trace_analysis.lua        -- 禁用 JIT（纯解释执行）
-- ============================================================================

local jit = require("jit")
local ju = jit.util

-- ============================================================================
-- 辅助函数
-- ============================================================================

local function separator(title)
    print(string.rep("=", 70))
    if title then
        print("  " .. title)
        print(string.rep("=", 70))
    end
    print()
end

local function sub_separator(title)
    print(string.rep("-", 70))
    if title then
        print("  " .. title)
    end
    print()
end

-- 高精度计时器
local function time_it(func, iterations, warmup)
    warmup = warmup or 0
    -- 预热
    for i = 1, warmup do
        func()
    end
    -- 计时
    local start = os.clock()
    for i = 1, iterations do
        func()
    end
    local elapsed = os.clock() - start
    return elapsed
end

-- 格式化时间
local function fmt_time(seconds)
    if seconds < 0.001 then
        return string.format("%.3f us", seconds * 1000000)
    elseif seconds < 1 then
        return string.format("%.3f ms", seconds * 1000)
    else
        return string.format("%.3f s", seconds)
    end
end

-- ============================================================================
-- 第一部分：Trace 编译触发条件
-- ============================================================================

separator("第一部分：Trace 编译触发条件")
print("LuaJIT 使用热计数器（Hot Counter）检测热点代码。")
print("当循环回跳执行次数超过阈值（默认 hotloop=56）时，触发 trace 录制。")
print()

-- 1.1 简单循环 —— 最基本的触发场景
sub_separator("1.1 简单数值循环")
print("这是最容易被 JIT 编译的场景：纯数值计算的循环。")
print()

local function simple_loop(n)
    local sum = 0
    for i = 1, n do
        sum = sum + i
    end
    return sum
end

-- 先关闭 JIT，测量解释执行的性能
jit.off()
local interp_time = time_it(function() simple_loop(100000) end, 50, 5)

-- 再开启 JIT，测量编译后的性能
jit.on()
-- 预热以触发编译
simple_loop(100000)
simple_loop(100000)
local jit_time = time_it(function() simple_loop(100000) end, 50, 5)

print(string.format("  解释执行: %s (50 次迭代)", fmt_time(interp_time)))
print(string.format("  JIT 编译: %s (50 次迭代)", fmt_time(jit_time)))
if interp_time > 0 then
    print(string.format("  加速比:   %.1fx", interp_time / jit_time))
end
print()

-- 1.2 类型稳定 vs 类型不稳定
sub_separator("1.2 类型稳定性对 JIT 的影响")
print("LuaJIT 的 trace 编译依赖类型稳定性。")
print("如果循环中变量类型不变，trace 编译高效；否则频繁 side exit。")
print()

-- 类型稳定的循环
local function type_stable(n)
    local sum = 0
    for i = 1, n do
        sum = sum + i * 2
    end
    return sum
end

-- 类型不稳定的循环（混合数字和字符串）
local function type_unstable(n)
    local sum = 0
    local t = {}
    for i = 1, n do
        if i % 2 == 0 then
            t[i] = i          -- 数字
        else
            t[i] = tostring(i) -- 字符串
        end
    end
    -- 求和时需要类型检查
    for i = 1, n do
        local v = t[i]
        if type(v) == "number" then
            sum = sum + v
        end
    end
    return sum
end

jit.off()
local ts_interp = time_it(function() type_stable(100000) end, 30, 3)
local tu_interp = time_it(function() type_unstable(100000) end, 30, 3)

jit.on()
type_stable(100000) -- 预热
type_stable(100000)
local ts_jit = time_it(function() type_stable(100000) end, 30, 3)

type_unstable(100000) -- 预热
type_unstable(100000)
local tu_jit = time_it(function() type_unstable(100000) end, 30, 3)

print("  类型稳定循环 (纯数字运算):")
print(string.format("    解释执行: %s", fmt_time(ts_interp)))
print(string.format("    JIT 编译: %s  (加速比: %.1fx)", fmt_time(ts_jit),
    ts_interp > 0 and (ts_interp / ts_jit) or 0))

print()
print("  类型不稳定循环 (数字+字符串混合):")
print(string.format("    解释执行: %s", fmt_time(tu_interp)))
print(string.format("    JIT 编译: %s  (加速比: %.1fx)", fmt_time(tu_jit),
    tu_interp > 0 and (tu_interp / tu_jit) or 0))
print()

-- 1.3 Guard 失败和 Side Exit
sub_separator("1.3 Guard 失败和 Side Exit")
print("当 JIT 编译的 trace 中的类型假设失败时，发生 side exit。")
print("频繁的 side exit 会降低性能。")
print()

-- 演示：大多数时候是整数，偶尔是字符串
local function mostly_integer(n, inject_string_at)
    local sum = 0
    for i = 1, n do
        local val
        if i == inject_string_at then
            val = "oops"  -- 在特定位置注入一个字符串
        else
            val = i
        end
        if type(val) == "number" then
            sum = sum + val
        end
    end
    return sum
end

jit.on()
-- 不注入字符串（纯数字路径）
mostly_integer(100000, -1) -- 预热
mostly_integer(100000, -1)
local no_exit_time = time_it(function() mostly_integer(100000, -1) end, 30, 3)

-- 在中途注入字符串（触发 side exit）
mostly_integer(100000, 50000) -- 预热
local with_exit_time = time_it(function() mostly_integer(100000, 50000) end, 30, 3)

print(string.format("  无 side exit:     %s", fmt_time(no_exit_time)))
print(string.format("  有 side exit:     %s", fmt_time(with_exit_time)))
print("  说明：side exit 触发后回到解释器执行，然后可能录制 side trace。")
print()

-- ============================================================================
-- 第二部分：Trace 录制过程详解
-- ============================================================================

separator("第二部分：Trace 录制过程详解")
print()

-- 2.1 嵌套循环和 Side Trace
sub_separator("2.1 嵌套循环的 trace 编译")
print("LuaJIT 分别为每个热循环录制 trace。")
print("嵌套循环会生成多个独立的 trace。")
print()

local function nested_loops(n)
    local total = 0
    for i = 1, n do
        local sum = 0
        for j = 1, 100 do
            sum = sum + j
        end
        total = total + sum
    end
    return total
end

-- 预热
nested_loops(1000)
nested_loops(1000)

print("nested_loops 函数已执行，应该为内外两个循环各生成一个 trace。")
print("使用 'luajit -jv' 运行可以看到 trace 编号和链接关系。")
print()

-- 2.2 函数调用内联
sub_separator("2.2 函数调用与内联")
print("LuaJIT 可以将小函数的调用内联到 trace 中。")
print("但如果函数体太复杂或包含不可录制的操作，会中止录制。")
print()

local function square(x)
    return x * x
end

local function sum_of_squares(n)
    local sum = 0
    for i = 1, n do
        sum = sum + square(i)  -- square 可能被内联
    end
    return sum
end

-- 预热
sum_of_squares(10000)
sum_of_squares(10000)

print("sum_of_squares 已执行，square() 函数可能被内联到 trace 中。")
print()

-- 2.3 不可录制的操作
sub_separator("2.3 不可录制的操作（NYI 字节码）")
print("某些 Lua 操作无法被 trace 录制，会导致 trace 中止（abort）。")
print("常见的不可录制操作包括：")
print("  - pcall/xpcall 的错误路径")
print("  - 复杂的元方法链")
print("  - 某些 table 库函数")
print("  - os.* 和 io.* 函数")
print()

-- 演示：pcall 会中止 trace
local function with_pcall(n)
    local sum = 0
    for i = 1, n do
        local ok, val = pcall(function() return i * 2 end)
        if ok then
            sum = sum + val
        end
    end
    return sum
end

print("包含 pcall 的循环不会被 JIT 编译（pcall 是 NYI）。")
print("请使用 'luajit -jv' 查看 trace abort 信息。")
print()

-- ============================================================================
-- 第三部分：Trace 信息查看
-- ============================================================================

separator("第三部分：Trace 信息查看")
print()

-- 触发一些 trace 编译
local function benchmark_func(n)
    local a, b, c = 0, 0, 0
    for i = 1, n do
        a = a + i
        b = b + i * 2
        c = c + i * 3
    end
    return a + b + c
end

-- 充分预热
for _ = 1, 20 do
    benchmark_func(10000)
end

sub_separator("已编译的 trace 信息")

local trace_count = 0
for tr = 1, 100 do
    local ok, info = pcall(ju.traceinfo, tr)
    if ok and info then
        trace_count = trace_count + 1

        print(string.format("Trace #%d:", tr))
        if info.nins then
            print(string.format("  IR 指令数 (nins):  %d", info.nins))
        end
        if info.nsnap then
            print(string.format("  快照数 (nsnap):    %d", info.nsnap))
        end
        if info.nsnapmap then
            print(string.format("  快照映射大小:      %d", info.nsnapmap))
        end
        if info.link then
            print(string.format("  链接目标 (link):   %s", tostring(info.link)))
        end
        if info.root then
            print(string.format("  根 trace (root):   %s", tostring(info.root)))
        end
        if info.nchild then
            print(string.format("  子 trace 数:       %s", tostring(info.nchild)))
        end
        if info.szmcode then
            print(string.format("  机器码大小:        %d 字节", info.szmcode))
        end
        if info.mcode then
            print(string.format("  机器码地址:        %s", tostring(info.mcode)))
        end
        if info.mcloop then
            print(string.format("  循环入口偏移:      %d", info.mcloop))
        end

        -- 显示前几条 IR 指令
        if info.nins and info.nins > 1 then
            print("  IR 指令 (前 15 条):")
            local shown = 0
            for idx = 1, math.min(info.nins - 1, 15) do
                local ir_ok, ir = pcall(ju.traceir, tr, idx)
                if ir_ok and ir then
                    print(string.format("    [%04d] %s", idx, tostring(ir)))
                    shown = shown + 1
                end
            end
            if info.nins - 1 > 15 then
                print(string.format("    ... 共 %d 条 IR", info.nins - 1))
            end
        end

        print()
    end
end

if trace_count == 0 then
    print("未找到已编译的 trace。")
    print()
    print("可能的原因和解决方案：")
    print("  1. JIT 被禁用: 检查 jit.status()")
    print("  2. 循环不够热: 增加循环迭代次数或预热次数")
    print("  3. trace 中止: 使用 'luajit -jv' 查看中止原因")
    print()
    print("当前 JIT 状态: " .. tostring(jit.status()))
else
    print(string.format("共找到 %d 个已编译的 trace。", trace_count))
end

-- ============================================================================
-- 第四部分：JIT 前后性能对比
-- ============================================================================

separator("第四部分：JIT 前后性能对比")
print()

-- 4.1 纯数值计算
sub_separator("4.1 纯数值计算：向量点积")

local function dot_product(n)
    -- 模拟两个向量的点积
    local sum = 0
    for i = 1, n do
        local x = i * 0.5
        local y = i * 0.3
        sum = sum + x * y
    end
    return sum
end

jit.off()
local dp_interp = time_it(function() dot_product(100000) end, 100, 10)

jit.on()
dot_product(100000) -- 预热
dot_product(100000)
local dp_jit = time_it(function() dot_product(100000) end, 100, 10)

print(string.format("  解释执行: %s (100 次)", fmt_time(dp_interp)))
print(string.format("  JIT 编译: %s (100 次)", fmt_time(dp_jit)))
if dp_interp > 0 then
    print(string.format("  加速比:   %.1fx", dp_interp / dp_jit))
end
print()

-- 4.2 整数位运算
sub_separator("4.2 整数位运算")

local bit = require("bit")
local bnot, band, bor, bxor = bit.bnot, bit.band, bit.bor, bit.bxor
local lshift, rshift = bit.lshift, bit.rshift

local function bit_ops(n)
    local x = 0
    for i = 1, n do
        x = bxor(x, lshift(i, 3))
        x = band(x, 0xFFFF)
        x = bor(x, rshift(i, 2))
    end
    return x
end

jit.off()
local bo_interp = time_it(function() bit_ops(100000) end, 100, 10)

jit.on()
bit_ops(100000) -- 预热
bit_ops(100000)
local bo_jit = time_it(function() bit_ops(100000) end, 100, 10)

print(string.format("  解释执行: %s (100 次)", fmt_time(bo_interp)))
print(string.format("  JIT 编译: %s (100 次)", fmt_time(bo_jit)))
if bo_interp > 0 then
    print(string.format("  加速比:   %.1fx", bo_interp / bo_jit))
end
print()

-- 4.3 表操作
sub_separator("4.3 表操作：数组访问")

local function array_sum(n)
    local t = {}
    for i = 1, n do
        t[i] = i
    end
    local sum = 0
    for i = 1, n do
        sum = sum + t[i]
    end
    return sum
end

jit.off()
local ar_interp = time_it(function() array_sum(100000) end, 50, 5)

jit.on()
array_sum(100000) -- 预热
array_sum(100000)
local ar_jit = time_it(function() array_sum(100000) end, 50, 5)

print(string.format("  解释执行: %s (50 次)", fmt_time(ar_interp)))
print(string.format("  JIT 编译: %s (50 次)", fmt_time(ar_jit)))
if ar_interp > 0 then
    print(string.format("  加速比:   %.1fx", ar_interp / ar_jit))
end
print()

-- 4.4 字符串操作（JIT 效果有限）
sub_separator("4.4 字符串连接（JIT 效果有限）")

local function str_concat(n)
    local parts = {}
    for i = 1, n do
        parts[i] = "item" .. i
    end
    return #parts
end

jit.off()
local sc_interp = time_it(function() str_concat(10000) end, 20, 2)

jit.on()
str_concat(10000) -- 预热
str_concat(10000)
local sc_jit = time_it(function() str_concat(10000) end, 20, 2)

print(string.format("  解释执行: %s (20 次)", fmt_time(sc_interp)))
print(string.format("  JIT 编译: %s (20 次)", fmt_time(sc_jit)))
if sc_interp > 0 then
    print(string.format("  加速比:   %.1fx", sc_interp / sc_jit))
end
print("  说明：字符串操作的 JIT 加速比通常较低，因为字符串分配无法消除。")
print()

-- 4.5 FFI vs Lua（LuaJIT 的杀手级特性）
sub_separator("4.5 FFI 调用 vs 纯 Lua")
print("LuaJIT 的 FFI 允许直接调用 C 函数，性能接近原生 C 代码。")
print()

-- 尝试使用 FFI
local ok, ffi = pcall(require, "ffi")
if ok then
    ffi.cdef[[
        typedef struct { double x, y, y2; } Vec3;
        double sqrt(double x);
    ]]

    -- 使用 FFI 进行向量运算
    local function ffi_vector_ops(n)
        local sum = 0.0
        for i = 1, n do
            -- 使用 ffi 构造避免分配
            local x = ffi.new("double[1]", i * 0.5)
            sum = sum + x[0] * x[0]
        end
        -- 使用 C 的 sqrt
        return ffi.C.sqrt(sum)
    end

    -- 纯 Lua 版本
    local function lua_vector_ops(n)
        local sum = 0
        for i = 1, n do
            local x = i * 0.5
            sum = sum + x * x
        end
        return math.sqrt(sum)
    end

    -- 预热
    ffi_vector_ops(100000)
    ffi_vector_ops(100000)
    lua_vector_ops(100000)
    lua_vector_ops(100000)

    local ffi_time = time_it(function() ffi_vector_ops(100000) end, 50, 5)
    local lua_time = time_it(function() lua_vector_ops(100000) end, 50, 5)

    print(string.format("  纯 Lua + math:   %s (50 次)", fmt_time(lua_time)))
    print(string.format("  FFI + C.sqrt:    %s (50 次)", fmt_time(ffi_time)))
    if ffi_time > 0 then
        print(string.format("  加速比:          %.1fx", lua_time / ffi_time))
    end
else
    print("  FFI 不可用（" .. tostring(ffi) .. "），跳过 FFI 测试。")
end

-- ============================================================================
-- 第五部分：Trace 编译的优化效果分析
-- ============================================================================

separator("第五部分：Trace 编译的优化效果分析")
print()

sub_separator("5.1 数值窄化（Narrowing）")
print("LuaJIT 将双精度浮点运算窄化为整数运算以提升性能。")
print()

-- 整数运算 vs 浮点运算
local function integer_heavy(n)
    local sum = 0
    for i = 1, n do
        sum = sum + (i * 2 + 1)  -- 纯整数运算
    end
    return sum
end

local function float_heavy(n)
    local sum = 0.0
    for i = 1, n do
        sum = sum + (i * 0.5 + 0.1)  -- 浮点运算
    end
    return sum
end

-- 预热
integer_heavy(100000)
integer_heavy(100000)
float_heavy(100000)
float_heavy(100000)

local int_time = time_it(function() integer_heavy(100000) end, 100, 10)
local flt_time = time_it(function() float_heavy(100000) end, 100, 10)

print(string.format("  整数密集运算: %s (100 次)", fmt_time(int_time)))
print(string.format("  浮点密集运算: %s (100 次)", fmt_time(flt_time)))
print("  说明：LuaJIT 的 NARROW pass 会尝试将浮点运算窄化为整数。")
print()

sub_separator("5.2 Guard 和类型检查的开销")
print("LuaJIT 在 trace 入口和关键点插入 guard 指令。")
print("guard 的开销很小，但大量 guard 会累积。")
print()

-- 无 guard 的场景（纯整数循环）
local function no_guard_needed(n)
    local sum = 0
    for i = 1, n do
        sum = sum + i
    end
    return sum
end

-- 需要类型 guard 的场景（混合类型但最终都是数字）
local function needs_guards(n)
    local sum = 0
    local val  -- 值可能是 nil 或 number
    for i = 1, n do
        val = i  -- 每次赋值都需要类型 guard
        sum = sum + val
    end
    return sum
end

-- 预热
no_guard_needed(100000)
needs_guards(100000)

local ng_time = time_it(function() no_guard_needed(100000) end, 100, 10)
local wg_time = time_it(function() needs_guards(100000) end, 100, 10)

print(string.format("  无额外 guard:      %s", fmt_time(ng_time)))
print(string.format("  有类型 guard:      %s", fmt_time(wg_time)))
print()

-- ============================================================================
-- 第六部分：JIT 控制实验
-- ============================================================================

separator("第六部分：JIT 控制实验")
print()

-- 展示如何通过 jit.opt 控制编译行为
sub_separator("6.1 JIT 参数调整")

print("常用的 JIT 控制命令：")
print()
print("  jit.on()                    -- 启用 JIT")
print("  jit.off()                   -- 禁用 JIT")
print("  jit.flush()                 -- 清除所有已编译的 trace")
print()
print("  jit.opt.start(level)        -- 设置优化级别 (0-4)")
print("  jit.opt.start('hotloop=N')  -- 设置热循环阈值")
print("  jit.opt.start('hotexit=N')  -- 设置热退出阈值")
print("  jit.opt.start('maxside=N')  -- 设置最大 side trace 数")
print("  jit.opt.start('maxtrace=N') -- 设置最大 trace 数")
print()
print("  jit.opt.start('-fold')      -- 禁用常量折叠")
print("  jit.opt.start('-cse')       -- 禁用 CSE")
print("  jit.opt.start('-dce')       -- 禁用死代码消除")
print("  jit.opt.start('-narrow')    -- 禁用数值窄化")
print("  jit.opt.start('-abc')       -- 禁用 ABC 消除")
print("  jit.opt.start('-sink')      -- 禁用分配下沉")
print()

-- 演示：降低热循环阈值以更快触发编译
sub_separator("6.2 实验：不同热循环阈值的影响")

local function test_loop(n)
    local sum = 0
    for i = 1, n do
        sum = sum + i * 3
    end
    return sum
end

-- 默认阈值
jit.on()
jit.opt.start(3)  -- 恢复默认优化级别
jit.flush()
test_loop(1000)
test_loop(1000)
local default_time = time_it(function() test_loop(10000) end, 200, 10)

-- 降低阈值，更快触发编译
jit.flush()
jit.opt.start('hotloop=10')
test_loop(1000)
test_loop(1000)
local low_threshold_time = time_it(function() test_loop(10000) end, 200, 10)

-- 恢复默认
jit.opt.start('hotloop=56')

print(string.format("  默认阈值 (hotloop=56):  %s", fmt_time(default_time)))
print(string.format("  低阈值 (hotloop=10):    %s", fmt_time(low_threshold_time)))
print()

-- ============================================================================
-- 第七部分：实际应用场景分析
-- ============================================================================

separator("第七部分：实际应用场景的 JIT 行为")
print()

sub_separator("7.1 矩阵乘法")
print("矩阵乘法是典型的数值密集计算，JIT 编译效果显著。")
print()

local function matrix_multiply(n)
    local A, B, C = {}, {}, {}
    -- 初始化
    for i = 1, n do
        A[i], B[i], C[i] = {}, {}, {}
        for j = 1, n do
            A[i][j] = i + j
            B[i][j] = i - j
            C[i][j] = 0
        end
    end
    -- 乘法
    for i = 1, n do
        for j = 1, n do
            local sum = 0
            for k = 1, n do
                sum = sum + A[i][k] * B[k][j]
            end
            C[i][j] = sum
        end
    end
    return C
end

jit.off()
local mm_interp = time_it(function() matrix_multiply(50) end, 5, 1)

jit.on()
matrix_multiply(50) -- 预热
matrix_multiply(50)
local mm_jit = time_it(function() matrix_multiply(50) end, 5, 1)

print(string.format("  50x50 矩阵乘法 - 解释执行: %s (5 次)", fmt_time(mm_interp)))
print(string.format("  50x50 矩阵乘法 - JIT 编译: %s (5 次)", fmt_time(mm_jit)))
if mm_interp > 0 then
    print(string.format("  加速比: %.1fx", mm_interp / mm_jit))
end
print()

sub_separator("7.2 数值积分（梯形法）")
print()

local function trapezoidal_integration(n)
    local a, b = 0, math.pi
    local h = (b - a) / n
    local sum = 0.5 * (math.sin(a) + math.sin(b))
    for i = 1, n - 1 do
        local x = a + i * h
        sum = sum + math.sin(x)
    end
    return sum * h
end

jit.off()
local ti_interp = time_it(function() trapezoidal_integration(100000) end, 50, 5)

jit.on()
trapezoidal_integration(100000) -- 预热
trapezoidal_integration(100000)
local ti_jit = time_it(function() trapezoidal_integration(100000) end, 50, 5)

print(string.format("  解释执行: %s (50 次)", fmt_time(ti_interp)))
print(string.format("  JIT 编译: %s (50 次)", fmt_time(ti_jit)))
if ti_interp > 0 then
    print(string.format("  加速比:   %.1fx", ti_interp / ti_jit))
end
print()

-- ============================================================================
-- 总结
-- ============================================================================

separator("总结")
print("本脚本演示了 LuaJIT trace 编译的以下关键概念：")
print()
print("  1. 热点检测与 trace 触发")
print("     - 热计数器机制：循环回跳时递减，溢出时触发编译")
print("     - 默认阈值 hotloop=56")
print()
print("  2. Trace 录制过程")
print("     - 边执行边翻译：字节码 → SSA IR")
print("     - 类型特化：利用运行时类型信息生成高效 IR")
print("     - Guard 插入：在类型假设处插入守卫指令")
print()
print("  3. Side Exit 和 Side Trace")
print("     - Guard 失败 → side exit → 回到解释器")
print("     - 频繁的 side exit → 录制 side trace")
print()
print("  4. 性能影响因素")
print("     - 类型稳定性：类型越稳定，JIT 效果越好")
print("     - 循环体复杂度：简单循环更容易被优化")
print("     - 不可录制操作：pcall、os.* 等会导致 trace 中止")
print()
print("  5. JIT 控制")
print("     - jit.on()/off() 控制开关")
print("     - jit.opt.start() 调整参数")
print("     - jit.flush() 清除已编译的 trace")
print()
print("调试提示：")
print("  luajit -jv trace_analysis.lua      -- 查看 JIT 编译日志")
print("  luajit -jdump trace_analysis.lua   -- 查看 IR 和汇编")
print("  luajit -joff trace_analysis.lua    -- 纯解释执行")
print("  luajit -jdump=+b trace_analysis.lua -- 查看字节码和 IR")
print()
