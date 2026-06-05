#!/usr/bin/env luajit
-- ============================================================================
-- bytecode_inspector.lua
-- LuaJIT 字节码检查工具
--
-- 使用 jit.util 和 jit.bc 库检查 LuaJIT 字节码，包括：
--   1. 显示函数的字节码
--   2. 统计字节码使用频率
--   3. 演示 trace 信息查看
--
-- 用法：luajit bytecode_inspector.lua
-- ============================================================================

local jit = require("jit")
-- jit.util 提供低级 JIT 信息查询接口
-- jit.bc   提供字节码 dump 功能

-- ============================================================================
-- 辅助函数
-- ============================================================================

local function separator(title)
    print(string.rep("=", 70))
    if title then
        print("  " .. title)
        print(string.rep("=", 70))
    end
end

local function sub_separator(title)
    print(string.rep("-", 70))
    if title then
        print("  " .. title)
        print(string.rep("-", 70))
    end
end

-- ============================================================================
-- 第一部分：使用 jit.bc.dump 显示函数字节码
-- ============================================================================

separator("第一部分：函数字节码显示")
print()

-- 定义一些示例函数
local function simple_add(a, b)
    return a + b
end

local function loop_sum(n)
    local sum = 0
    for i = 1, n do
        sum = sum + i
    end
    return sum
end

local function table_ops(t)
    local count = 0
    for k, v in pairs(t) do
        if type(v) == "number" then
            count = count + v
        end
    end
    return count
end

local function closure_factory(x)
    return function(y)
        return x + y
    end
end

-- 显示 simple_add 的字节码
sub_separator("simple_add(a, b) 的字节码")
-- jit.bc.dump 将函数的字节码输出到 stdout
-- 第二个参数开启详细模式（显示行号和常量）
jit.bc.dump(simple_add, true)

print()
sub_separator("loop_sum(n) 的字节码")
jit.bc.dump(loop_sum, true)

print()
sub_separator("table_ops(t) 的字节码")
jit.bc.dump(table_ops, true)

print()
sub_separator("closure_factory(x) 的字节码")
jit.bc.dump(closure_factory, true)

-- ============================================================================
-- 第二部分：使用 jit.util 获取函数的详细信息
-- ============================================================================

separator("第二部分：使用 jit.util 获取函数详细信息")
print()

-- jit.util 模块提供以下关键函数：
--   jit.util.funcinfo(func)      -- 获取函数信息
--   jit.util.funcbc(func, pc)    -- 获取指定位置的字节码
--   jit.util.funck(func, idx)    -- 获取常量表中的值
--   jit.util.funcuvname(func, i) -- 获取上值名称
--   jit.util.traceinfo(tr)       -- 获取 trace 信息
--   jit.util.traceir(tr, idx)    -- 获取 trace 的 IR 指令
--   jit.util.tracesnap(tr, idx)  -- 获取 trace 的快照
--   jit.util.tracemcode(tr)      -- 获取 trace 的机器码

local ju = jit.util

-- 检查 simple_add 函数
sub_separator("simple_add 的函数信息")
local info = ju.funcinfo(simple_add)
print("函数信息：")
print("  指令数量 (sizebc):   " .. tostring(info.sizebc))
print("  帧大小 (framesize):  " .. tostring(info.framesize))
print("  参数数量 (params):   " .. tostring(info.params))
print("  上值数量 (upvalues): " .. tostring(info.upvalues))
print("  GC常量数 (sizekgc):  " .. tostring(info.sizekgc))
print("  数字常量数 (sizekn): " .. tostring(info.sizekn))
print("  是否可变参数:        " .. tostring((info.flags or 0) % 2 == 1))

-- 显示常量表
print()
sub_separator("loop_sum 的常量表")
local loop_info = ju.funcinfo(loop_sum)
print("GC 常量 (sizekgc = " .. tostring(loop_info.sizekgc) .. "):")
for i = -1, -(loop_info.sizekgc or 0), -1 do
    local k = ju.funck(loop_sum, i)
    print(string.format("  KGC[%d] = %s (type: %s)", i, tostring(k), type(k)))
end
print("数字常量 (sizekn = " .. tostring(loop_info.sizekn) .. "):")
for i = 0, (loop_info.sizekn or 1) - 1 do
    local k = ju.funck(loop_sum, i)
    print(string.format("  KNUM[%d] = %s", i, tostring(k)))
end

-- 逐条显示字节码
print()
sub_separator("loop_sum 的逐条字节码")
local bc_info = ju.funcinfo(loop_sum)
if bc_info.sizebc then
    local bc_names = {
        [0] = "ISLT", "ISGE", "ISLE", "ISGT",
        "ISEQV", "ISNEV", "ISEQS", "ISNES",
        "ISEQN", "ISNEN", "ISEQP", "ISNEP",
        "ISTC", "ISFC", "IST", "ISF",
        "ISTYPE", "ISNUM",
        "MOV", "NOT", "UNM", "LEN",
        "ADDVN", "SUBVN", "MULVN", "DIVVN", "MODVN",
        "ADDNV", "SUBNV", "MULNV", "DIVNV", "MODNV",
        "ADDVV", "SUBVV", "MULVV", "DIVVV", "MODVV",
        "POW", "CAT",
        "KSTR", "KCDATA", "KSHORT", "KNUM", "KPRI", "KNIL",
        "UGET", "USETV", "USETS", "USETN", "USETP", "UCLO", "FNEW",
        "TNEW", "TDUP", "GGET", "GSET",
        "TGETV", "TGETS", "TGETB", "TGETR",
        "TSETV", "TSETS", "TSETB", "TSETM", "TSETR",
        "CALLM", "CALL", "CALLMT", "CALLT",
        "ITERC", "ITERN", "VARG", "ISNEXT",
        "RETM", "RET", "RET0", "RET1",
        "FORI", "JFORI", "FORL", "IFORL", "JFORL",
        "ITERL", "IITERL", "JITERL",
        "LOOP", "ILOOP", "JLOOP", "JMP",
        "FUNCF", "IFUNCF", "JFUNCF",
        "FUNCV", "IFUNCV", "JFUNCV",
        "FUNCC", "FUNCCW",
    }

    for pc = 0, bc_info.sizebc - 1 do
        local ins = ju.funcbc(loop_sum, pc)
        if ins then
            -- 从32位指令中提取字段
            local op = bit.band(ins, 0xFF)
            local a  = bit.band(bit.rshift(ins, 8), 0xFF)
            local c  = bit.band(bit.rshift(ins, 16), 0xFF)
            local b  = bit.rshift(ins, 24)
            local d  = bit.rshift(ins, 16)

            local opname = bc_names[op] or ("UNKNOWN_" .. op)
            print(string.format("  [%03d]  %-10s  A=%-3d  B=%-3d  C=%-3d  D=%-5d  (0x%08X)",
                pc, opname, a, b, c, d, ins))
        end
    end
end

-- ============================================================================
-- 第三部分：字节码使用频率统计
-- ============================================================================

separator("第三部分：字节码使用频率统计")
print()

-- 收集多个函数的字节码，统计各操作码的使用频率
local function count_bytecodes(func, counts)
    local info = ju.funcinfo(func)
    if not info.sizebc then return end
    for pc = 0, info.sizebc - 1 do
        local ins = ju.funcbc(func, pc)
        if ins then
            local op = bit.band(ins, 0xFF)
            counts[op] = (counts[op] or 0) + 1
        end
    end
end

local bc_names_full = {
    [0] = "ISLT", "ISGE", "ISLE", "ISGT",
    "ISEQV", "ISNEV", "ISEQS", "ISNES",
    "ISEQN", "ISNEN", "ISEQP", "ISNEP",
    "ISTC", "ISFC", "IST", "ISF", "ISTYPE", "ISNUM",
    "MOV", "NOT", "UNM", "LEN",
    "ADDVN", "SUBVN", "MULVN", "DIVVN", "MODVN",
    "ADDNV", "SUBNV", "MULNV", "DIVNV", "MODNV",
    "ADDVV", "SUBVV", "MULVV", "DIVVV", "MODVV",
    "POW", "CAT",
    "KSTR", "KCDATA", "KSHORT", "KNUM", "KPRI", "KNIL",
    "UGET", "USETV", "USETS", "USETN", "USETP", "UCLO", "FNEW",
    "TNEW", "TDUP", "GGET", "GSET",
    "TGETV", "TGETS", "TGETB", "TGETR",
    "TSETV", "TSETS", "TSETB", "TSETM", "TSETR",
    "CALLM", "CALL", "CALLMT", "CALLT",
    "ITERC", "ITERN", "VARG", "ISNEXT",
    "RETM", "RET", "RET0", "RET1",
    "FORI", "JFORI", "FORL", "IFORL", "JFORL",
    "ITERL", "IITERL", "JITERL",
    "LOOP", "ILOOP", "JLOOP", "JMP",
    "FUNCF", "IFUNCF", "JFUNCF",
    "FUNCV", "IFUNCV", "JFUNCV",
    "FUNCC", "FUNCCW",
}

-- 对所有示例函数进行统计
local counts = {}
local all_funcs = { simple_add, loop_sum, table_ops, closure_factory }

-- 也可以加入一些额外的函数
local function string_manip(s)
    local result = ""
    for i = 1, #s do
        local ch = s:sub(i, i)
        result = result .. ch
    end
    return result
end

local function recursive_fib(n)
    if n <= 1 then return n end
    return recursive_fib(n - 1) + recursive_fib(n - 2)
end

table.insert(all_funcs, string_manip)
table.insert(all_funcs, recursive_fib)

for _, func in ipairs(all_funcs) do
    count_bytecodes(func, counts)
end

-- 按使用频率排序
local sorted = {}
for op, count in pairs(counts) do
    table.insert(sorted, { op = op, count = count, name = bc_names_full[op] or ("OP_" .. op) })
end
table.sort(sorted, function(a, b) return a.count > b.count end)

-- 计算总数
local total = 0
for _, entry in ipairs(sorted) do
    total = total + entry.count
end

print(string.format("统计了 %d 个函数，共 %d 条字节码指令", #all_funcs, total))
print()
print(string.format("  %-10s  %6s  %8s  %s", "操作码", "次数", "占比", "分布"))
print("  " .. string.rep("-", 60))

for _, entry in ipairs(sorted) do
    local pct = entry.count / total * 100
    local bar_len = math.floor(pct * 2)
    local bar = string.rep("#", bar_len)
    print(string.format("  %-10s  %6d  %7.1f%%  %s",
        entry.name, entry.count, pct, bar))
end

-- 分类统计
print()
sub_separator("按类别统计")
local categories = {
    { name = "比较操作", ops = { 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11 } },
    { name = "测试操作", ops = { 12, 13, 14, 15, 16, 17 } },
    { name = "一元操作", ops = { 18, 19, 20, 21 } },
    { name = "算术操作", ops = { 22, 23, 24, 25, 26, 27, 28, 29, 30, 31,
                                  32, 33, 34, 35, 36, 37, 38 } },
    { name = "常量加载", ops = { 39, 40, 41, 42, 43, 44 } },
    { name = "上值操作", ops = { 45, 46, 47, 48, 49, 50, 51 } },
    { name = "表操作",   ops = { 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64 } },
    { name = "调用返回", ops = { 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76 } },
    { name = "循环分支", ops = { 77, 78, 79, 80, 81, 82, 83, 84, 85, 86, 87, 88, 89 } },
    { name = "函数头",   ops = { 90, 91, 92, 93, 94, 95, 96, 97 } },
}

for _, cat in ipairs(categories) do
    local cat_total = 0
    for _, op in ipairs(cat.ops) do
        cat_total = cat_total + (counts[op] or 0)
    end
    if cat_total > 0 then
        local pct = cat_total / total * 100
        print(string.format("  %-12s: %4d 条 (%5.1f%%)", cat.name, cat_total, pct))
    end
end

-- ============================================================================
-- 第四部分：查看 trace 信息
-- ============================================================================

separator("第四部分：Trace 信息查看")
print()

-- 先执行一些代码来触发 JIT 编译
print("执行热循环以触发 JIT 编译...")
print()

-- 热循环：执行足够多次以触发 trace 录制
local function hot_loop(n)
    local sum = 0
    for i = 1, n do
        sum = sum + i * 2
    end
    return sum
end

-- 预热：多次调用以触发 JIT
for round = 1, 10 do
    hot_loop(1000)
end

print("hot_loop 执行完成")
print()

-- 查看 trace 信息
-- jit.util.traceinfo(trace_number) 返回 trace 的信息
print("尝试查询 trace 信息...")
print("(注意：trace 编号从 1 开始，只有成功编译的 trace 才有信息)")
print()

-- 尝试查询前几个 trace
local found_traces = 0
for tr = 1, 20 do
    local ok, info = pcall(ju.traceinfo, tr)
    if ok and info then
        found_traces = found_traces + 1
        sub_separator(string.format("Trace #%d", tr))
        print("  Trace 信息：")
        for k, v in pairs(info) do
            print(string.format("    %-15s = %s", k, tostring(v)))
        end

        -- 尝试获取 IR 信息
        local ok2, ir_count = pcall(function()
            local n = 0
            -- 遍历 IR 指令（从 1 开始到 nins-1）
            if info.nins then
                for idx = 1, info.nins - 1 do
                    local ir_ok, ir = pcall(ju.traceir, tr, idx)
                    if ir_ok and ir then
                        n = n + 1
                        if n <= 10 then  -- 只显示前10条
                            print(string.format("    IR[%04d]: %s", idx, tostring(ir)))
                        end
                    end
                end
                if n > 10 then
                    print(string.format("    ... (共 %d 条 IR，仅显示前 10 条)", n))
                end
            end
            return n
        end)
        if ok2 and ir_count then
            print(string.format("  IR 指令总数: %d", ir_count))
        end
        print()
    end
end

if found_traces == 0 then
    print("  未找到已编译的 trace。")
    print("  可能原因：")
    print("    1. JIT 已禁用（使用 jit.off() 或 -joff 参数）")
    print("    2. 热循环未达到编译阈值")
    print("    3. trace 编译失败（abort）")
    print()
    print("  提示：使用 -jv 参数运行可以看到详细的 JIT 编译日志：")
    print("    luajit -jv bytecode_inspector.lua")
else
    print(string.format("共找到 %d 个已编译的 trace", found_traces))
end

-- ============================================================================
-- 第五部分：JIT 状态和配置查看
-- ============================================================================

separator("第五部分：JIT 状态和配置")
print()

-- 查看 JIT 状态
print("JIT 状态：")
print("  JIT 是否启用: " .. tostring(jit.status()))
print()

-- 显示当前 JIT 优化参数
print("JIT 优化参数（通过 jit.opt 获取）：")
print("  说明：LuaJIT 的优化选项可以通过 jit.opt.start() 设置")
print("  例如：jit.opt.start(3)         -- 设置优化级别为 3")
print("        jit.opt.start('hotloop=10')  -- 设置热循环阈值")
print("        jit.opt.start('hotexit=5')   -- 设置热退出阈值")
print("        jit.opt.start('-abc')         -- 禁用 ABC 消除")
print()

-- 使用 jit.util 查看内部状态
print("可用的 jit.util 函数：")
local util_funcs = {
    "funcinfo(func)      -- 获取函数的编译信息",
    "funcbc(func, pc)    -- 获取指定 PC 处的字节码",
    "funck(func, idx)    -- 获取常量表中的值",
    "funcuvname(func, i) -- 获取上值名称",
    "traceinfo(tr)       -- 获取 trace 的编译信息",
    "traceir(tr, idx)    -- 获取 trace 的 IR 指令",
    "tracesnap(tr, idx)  -- 获取 trace 的快照",
    "tracemcode(tr)      -- 获取 trace 的机器码",
    "traceexit(tr, idx)  -- 获取 trace 的退出信息",
    "traceabort(tr)      -- 获取 trace 的中止信息",
}
for _, desc in ipairs(util_funcs) do
    print("  " .. desc)
end

-- ============================================================================
-- 第六部分：演示 jit.bc 的高级用法
-- ============================================================================

separator("第六部分：字节码 dump 的高级用法")
print()

-- jit.bc.dump 支持输出到文件
-- 格式：jit.bc.dump(func, output, flag)
--   output 可以是 true（stdout）、文件名或文件句柄
--   flag: true = 显示详细信息（行号、常量）

print("jit.bc.dump 的用法：")
print("  jit.bc.dump(func)            -- 简单 dump 到 stdout")
print("  jit.bc.dump(func, true)      -- 详细 dump（含行号和常量）")
print("  jit.bc.dump(func, 'out.txt') -- dump 到文件")
print()

-- 使用 jit.bc.dump 的输出格式分析
-- 格式示例：
-- 0001  KSHORT   0   0       -- PC=1, 操作码=KSHORT, A=0, D=0
-- 0002  ISGE     0   1       -- PC=2, 如果 slot[0] >= slot[1] 则跳转

-- 注意：jit.bc 的输出格式是 LuaJIT 内置的，我们可以解析它
print("示例：将 loop_sum 的字节码输出到字符串（通过 jit.bc.save）")
print()

-- jit.bc.save 可以将字节码保存为字节码文件
-- 但我们这里用 dump 来展示
print("loop_sum 的字节码输出：")
jit.bc.dump(loop_sum, true)

-- ============================================================================
-- 第七部分：上值检查
-- ============================================================================

separator("第七部分：闭包的上值检查")
print()

local function make_counter(start)
    local count = start or 0
    local step = 1
    return function()
        count = count + step
        return count
    end
end

local counter = make_counter(10)
local counter_info = ju.funcinfo(counter)

print("make_counter 返回的闭包信息：")
print("  指令数量:   " .. tostring(counter_info.sizebc))
print("  上值数量:   " .. tostring(counter_info.upvalues))
print()

-- 获取上值名称和值
if counter_info.upvalues then
    for i = 0, counter_info.upvalues - 1 do
        local name = ju.funcuvname(counter, i)
        print(string.format("  上值[%d]: name = %q", i, name or "(unnamed)"))
    end
end

print()
print("闭包的字节码：")
jit.bc.dump(counter, true)

-- ============================================================================
-- 总结
-- ============================================================================

separator("总结")
print()
print("本脚本演示了 LuaJIT 字节码检查的以下技术：")
print()
print("  1. jit.bc.dump(func, verbose)")
print("     - 显示函数的字节码，verbose 模式显示行号和常量")
print()
print("  2. jit.util.funcinfo(func)")
print("     - 获取函数的元信息：指令数、帧大小、参数数等")
print()
print("  3. jit.util.funcbc(func, pc)")
print("     - 获取指定 PC 位置的原始 32 位字节码指令")
print()
print("  4. jit.util.funck(func, idx)")
print("     - 获取常量表中的值（正索引=数字常量，负索引=GC常量）")
print()
print("  5. jit.util.funcuvname(func, i)")
print("     - 获取第 i 个上值的名称")
print()
print("  6. jit.util.traceinfo(tr)")
print("     - 获取已编译 trace 的信息")
print()
print("  7. jit.util.traceir(tr, idx)")
print("     - 获取 trace 的 IR 指令")
print()
print("提示：")
print("  - 使用 'luajit -jv' 可以看到 JIT 编译的详细日志")
print("  - 使用 'luajit -jdump' 可以看到 trace 的 IR 和汇编输出")
print("  - 使用 'luajit -joff' 可以禁用 JIT，纯解释执行")
print()
