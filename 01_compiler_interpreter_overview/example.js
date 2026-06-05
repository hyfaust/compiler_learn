// example.js — JavaScript 代码示例
//
// 本文件用于展示 JavaScript 引擎（V8）的工作方式特点：
//   - 动态类型 + JIT 编译：运行时确定类型，但通过 JIT 获得接近 C 的性能
//   - 原型链继承：基于原型的面向对象，而非类继承
//   - 事件循环与异步：单线程 + 异步 I/O 模型
//   - 隐藏类（Hidden Class）：V8 的内部优化机制
//   - 内联缓存（Inline Cache）：加速属性访问
//
// 在 Node.js 环境中运行：node example.js
// 在浏览器控制台中也可以运行（除 Node.js 特有的部分）

// ============================================================
// 1. 基本函数 —— 展示动态类型和 JIT 编译
// ============================================================

/**
 * 计算 n 的平方
 *
 * V8 引擎的处理流程：
 * 1. Parser 将源码解析为 AST
 * 2. Ignition 将 AST 编译为字节码并解释执行
 * 3. 如果 square 被频繁调用，TurboFan 将其编译为优化的机器码
 *
 * 与 C 对比：
 * - C: int square(int n) — 编译时确定类型，一次编译
 * - JS: function square(n) — 运行时收集类型信息，多次编译（解释→优化）
 *
 * TurboFan 的优化策略（假设 n 始终是整数）：
 * - 类型特化：生成专门处理 int32 的乘法指令
 * - 如果某次调用传入字符串，触发去优化（Deoptimization）
 */
function square(n) {
    return n * n;
}

/**
 * 计算绝对值
 *
 * 展示 JS 的条件表达式：
 * - 与 Python 类似，JS 的三元运算符是表达式
 * - 与 C 的语法完全一致：condition ? expr1 : expr2
 */
function absValue(x) {
    return x < 0 ? -x : x;
}

// ============================================================
// 2. 循环与累加 —— 展示 JIT 的类型特化
// ============================================================

/**
 * 计算 1² + 2² + ... + n²
 *
 * V8 的 JIT 编译过程：
 * 1. Ignition 解释执行，同时收集类型反馈（Type Feedback）
 *    - 记录 n 始终是 Smi（小整数）
 *    - 记录 total 始终是 Smi
 * 2. 当函数变"热"（被调用多次），TurboFan 启动优化编译
 * 3. TurboFan 利用类型反馈，生成特化的 int32 算术指令
 * 4. 如果某次 total 超过 int32 范围，触发去优化
 *
 * 与 C 对比：
 * - C 的 int 是固定 32 位，溢出会静默截断
 * - JS 的 Number 是 64 位浮点数，V8 会尝试用 Smi（31位整数）优化
 */
function sumOfSquares(n) {
    let total = 0;
    for (let i = 1; i <= n; i++) {
        total = total + square(i);
    }
    return total;
}

/**
 * 斐波那契数列（迭代版本）
 *
 * 展示 let 变量声明和块级作用域：
 * - var 是函数级作用域（旧式）
 * - let/const 是块级作用域（ES6+，更接近 C 的行为）
 */
function fibonacci(n) {
    if (n <= 1) return n;
    let a = 0;
    let b = 1;
    for (let i = 2; i <= n; i++) {
        const temp = a + b;
        a = b;
        b = temp;
    }
    return b;
}

// ============================================================
// 3. 数组操作 —— 展示 JS 数组的特殊性
// ============================================================

/**
 * 计算数组元素之和
 *
 * JS 数组的特殊性：
 * - JS 数组本质上是对象，索引是字符串属性名（"0", "1", ...）
 * - V8 对"密集数组"（连续整数索引）有特殊优化：
 *   - PACKED_SMI_ELEMENTS：全是小整数
 *   - PACKED_DOUBLE_ELEMENTS：全是浮点数
 *   - PACKED_ELEMENTS：任意对象
 *   - DICTIONARY_ELEMENTS：稀疏数组，退化为字典
 * - 数组类型"降级"是不可逆的！（Smi → Double → Elements）
 *
 * 与 C 对比：
 * - C 的 int arr[] 是连续的 int 内存块
 * - JS 的数组可能是多种内部表示之一
 */
function arraySum(arr) {
    let sum = 0;
    for (let i = 0; i < arr.length; i++) {
        sum += arr[i];
    }
    return sum;
}

/**
 * 冒泡排序
 *
 * 展示数组元素交换和嵌套循环。
 * V8 会对这类紧凑循环进行良好的 JIT 优化。
 */
function bubbleSort(arr) {
    const size = arr.length;
    for (let i = 0; i < size - 1; i++) {
        for (let j = 0; j < size - 1 - i; j++) {
            if (arr[j] > arr[j + 1]) {
                // ES6 解构赋值交换
                [arr[j], arr[j + 1]] = [arr[j + 1], arr[j]];
            }
        }
    }
    return arr;
}

// ============================================================
// 4. 递归 —— 展示调用栈和尾调用优化
// ============================================================

/**
 * 阶乘（递归版本）
 *
 * JS 的递归特点：
 * - 与 Python 类似，有调用栈深度限制
 * - ES6 规范了尾调用优化（TCO），但目前只有 Safari 实现了
 * - V8（Chrome/Node.js）尚未实现 TCO
 */
function factorial(n) {
    if (n <= 1) return 1;
    return n * factorial(n - 1);
}

/**
 * 二分查找
 */
function binarySearch(arr, low, high, target) {
    if (low > high) return -1;
    const mid = low + Math.floor((high - low) / 2);
    if (arr[mid] === target) return mid;
    else if (arr[mid] < target) return binarySearch(arr, mid + 1, high, target);
    else return binarySearch(arr, low, mid - 1, target);
}

// ============================================================
// 5. 对象与原型 —— 展示 JS 的对象模型
// ============================================================

/**
 * Point 类（ES6 class 语法）
 *
 * ES6 的 class 是原型继承的语法糖，底层仍然是：
 * - 构造函数 + prototype 对象
 * - 属性查找沿原型链进行
 *
 * V8 的隐藏类（Hidden Class）优化：
 * - 所有相同"形状"的对象共享一个隐藏类
 * - 属性访问通过隐藏类中的偏移量直接定位（而非字典查找）
 * - 这使得 JS 对象的属性访问可以接近 C struct 的速度
 *
 * 关键：保持对象"形状"一致对 V8 优化至关重要！
 */
class Point {
    constructor(x, y) {
        this.x = x;
        this.y = y;
    }

    /**
     * 计算曼哈顿距离
     *
     * V8 对方法调用的优化：
     * 1. 内联缓存（IC）：缓存属性查找的结果
     * 2. 如果所有 Point 对象有相同的隐藏类，IC 变为"单态"（monomorphic）
     * 3. TurboFan 可以将整个方法内联到调用点
     */
    manhattanDistance(other) {
        return absValue(this.x - other.x) + absValue(this.y - other.y);
    }

    toString() {
        return `Point(${this.x}, ${this.y})`;
    }
}

/**
 * 函数式创建对象（传统方式）
 *
 * 与 class 语法对比，展示 JS 对象模型的本质：
 * - 构造函数创建对象
 * - 方法挂在 prototype 上
 * - 所有实例共享 prototype 上的方法
 */
function PointLegacy(x, y) {
    this.x = x;
    this.y = y;
}

PointLegacy.prototype.manhattanDistance = function(other) {
    return absValue(this.x - other.x) + absValue(this.y - other.y);
};

// ============================================================
// 6. 作用域与闭包 —— 展示 JS 的词法作用域
// ============================================================

/**
 * 作用域演示
 *
 * JS 的作用域规则：
 * - var：函数级作用域，有变量提升（hoisting）
 * - let/const：块级作用域，有暂时性死区（TDZ）
 * - 闭包：函数捕获其定义时的词法环境
 */
function scopeDemo(x) {
    let result = x;

    {
        // 块级作用域
        let x = 100;  // 遮蔽外层的 x（与 C 类似）
        result = result + x;  // 使用内层的 x（100）
    }

    // 此处 x 恢复为参数 x
    result = result + x;

    return result;
    // scopeDemo(5): result = 5 + 100 + 5 = 110
}

/**
 * 闭包示例
 *
 * 闭包是 JS 最强大的特性之一，也是 JIT 编译器需要特殊处理的：
 * - 闭包捕获的变量不能简单地放在栈上（函数返回后还需要访问）
 * - V8 使用"上下文对象"（Context）来存储闭包捕获的变量
 * - 如果闭包变量是不可变的，TurboFan 可以将其内联为常量
 */
function makeCounter(start = 0) {
    let count = start;
    return {
        increment() { return ++count; },
        decrement() { return --count; },
        getValue() { return count; }
    };
}

// ============================================================
// 7. 异步与事件循环 —— 展示 JS 的执行模型
// ============================================================

/**
 * Promise 示例
 *
 * JS 的异步模型：
 * - 单线程 + 事件循环（Event Loop）
 * - 异步操作通过回调/Promise/async-await 实现
 * - 这不是编译器/解释器层面的特性，而是运行时环境的特性
 *
 * V8 引擎本身不提供异步 API（setTimeout、fetch 等），
 * 这些是由宿主环境（浏览器/Node.js）提供的。
 */
function delayedSquare(n) {
    return new Promise((resolve) => {
        // 模拟异步操作
        setTimeout(() => {
            resolve(n * n);
        }, 10);
    });
}

/**
 * async/await —— Promise 的语法糖
 */
async function sumOfSquaresAsync(n) {
    let total = 0;
    for (let i = 1; i <= n; i++) {
        // 注意：这里的 await 是串行的，不是并行的
        // 实际项目中应使用 Promise.all 实现并行
        const sq = await delayedSquare(i);
        total += sq;
    }
    return total;
}

// ============================================================
// 8. JS 特有的特性 —— 展示语言设计的特点
// ============================================================

/**
 * 展示 JS 的类型强制转换（Type Coercion）
 *
 * JS 的 == 运算符会进行隐式类型转换，这是很多 bug 的来源。
 * V8 的 JIT 编译器需要处理这些类型不确定的情况。
 */
function demonstrateTypeCoercion() {
    console.log("=== 类型强制转换 ===");
    console.log(`1 + "2" = ${1 + "2"}`);         // "12"（数字转字符串）
    console.log(`1 + Number("2") = ${1 + Number("2")}`); // 3
    console.log(`"5" == 5: ${"5" == 5}`);          // true（类型转换）
    console.log(`"5" === 5: ${"5" === 5}`);         // false（严格比较）
    console.log(`null == undefined: ${null == undefined}`); // true
    console.log(`null === undefined: ${null === undefined}`); // false
}

/**
 * 展示 JS 的函数式编程特性
 *
 * 高阶函数、箭头函数、链式调用等。
 * 这些特性使得代码更简洁，但也给 JIT 编译器带来更多优化机会（如内联）。
 */
function demonstrateFunctionalStyle() {
    console.log("=== 函数式编程 ===");
    const numbers = [3, 1, 4, 1, 5, 9, 2, 6, 5, 3, 5];

    // map/filter/reduce 链式调用
    const result = numbers
        .filter(x => x % 2 === 0)       // 过滤偶数
        .map(x => x * x)                 // 平方
        .reduce((sum, x) => sum + x, 0); // 求和

    console.log(`偶数的平方之和: ${result}`);

    // 解构赋值
    const [first, second, ...rest] = numbers;
    console.log(`first=${first}, second=${second}, rest=${rest}`);

    // 展开运算符
    const copy = [...numbers];
    console.log(`展开复制: ${copy}`);
}

/**
 * 展示 JS 中用闭包实现的模块模式
 *
 * 在 ES6 模块出现之前，闭包是 JS 实现封装的主要手段。
 * IIFE（立即调用函数表达式）+ 闭包 = 私有状态
 */
const MathUtils = (function() {
    // 私有变量
    let callCount = 0;

    // 返回公共 API
    return {
        square(n) {
            callCount++;
            return n * n;
        },
        getCallCount() {
            return callCount;
        }
    };
})();

// ============================================================
// 9. 主程序 —— 综合演示
// ============================================================

async function main() {
    console.log("=== JavaScript (V8 引擎) 演示 ===\n");

    // --- 基本函数 ---
    console.log("=== 基本函数 ===");
    console.log(`square(5) = ${square(5)}`);
    console.log(`absValue(-7) = ${absValue(-7)}`);
    console.log();

    // --- 循环与累加 ---
    console.log("=== 循环与累加 ===");
    console.log(`sumOfSquares(5) = ${sumOfSquares(5)}`);
    console.log(`fibonacci(10) = ${fibonacci(10)}`);
    console.log();

    // --- 数组操作 ---
    console.log("=== 数组操作 ===");
    const numbers = [64, 34, 25, 12, 22, 11, 90];
    console.log(`排序前: [${numbers}]`);
    console.log(`元素之和: ${arraySum(numbers)}`);
    bubbleSort(numbers);
    console.log(`排序后: [${numbers}]`);
    console.log();

    // --- 递归 ---
    console.log("=== 递归 ===");
    console.log(`factorial(6) = ${factorial(6)}`);
    const sortedArr = [2, 5, 8, 12, 16, 23, 38, 56, 72, 91];
    console.log(`binarySearch(23) = ${binarySearch(sortedArr, 0, 9, 23)}`);
    console.log();

    // --- 对象与原型 ---
    console.log("=== 对象与原型 ===");
    const p1 = new Point(3, 4);
    const p2 = new Point(7, 1);
    console.log(`曼哈顿距离: ${p1.manhattanDistance(p2)}`);
    console.log(`p1 的原型链: p1 → Point.prototype → Object.prototype → null`);
    console.log(`p1 是 Point 的实例: ${p1 instanceof Point}`);
    console.log();

    // --- 作用域与闭包 ---
    console.log("=== 作用域 ===");
    console.log(`scopeDemo(5) = ${scopeDemo(5)}`);
    console.log();

    console.log("=== 闭包 ===");
    const counter = makeCounter(10);
    console.log(`初始值: ${counter.getValue()}`);
    console.log(`increment: ${counter.increment()}`);
    console.log(`increment: ${counter.increment()}`);
    console.log(`decrement: ${counter.decrement()}`);
    console.log();

    // --- JS 特有特性 ---
    demonstrateTypeCoercion();
    console.log();
    demonstrateFunctionalStyle();
    console.log();

    console.log("=== 模块模式 ===");
    console.log(`MathUtils.square(5) = ${MathUtils.square(5)}`);
    console.log(`调用次数: ${MathUtils.getCallCount()}`);
    console.log();

    // --- 异步操作 ---
    console.log("=== 异步操作 ===");
    console.log("开始异步计算...");
    const asyncResult = await sumOfSquaresAsync(5);
    console.log(`sumOfSquaresAsync(5) = ${asyncResult}`);
    console.log();

    // --- V8 引擎总结 ---
    console.log("=== V8 引擎执行模型总结 ===");
    console.log("1. 源码 → Parser → AST");
    console.log("2. AST → Ignition → 字节码 → 解释执行");
    console.log("3. 热点函数 → TurboFan → 优化的机器码");
    console.log("4. 类型假设失败 → Deoptimization → 回退到解释器");
    console.log("5. 隐藏类（Hidden Class）优化属性访问");
    console.log("6. 内联缓存（Inline Cache）加速方法调用");
}

// 运行主程序
main().catch(console.error);
