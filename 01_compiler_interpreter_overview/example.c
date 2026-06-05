/*
 * example.c — 编译原理学习系列贯穿示例
 *
 * 这个文件包含了多种 C 语言特性，将被用于贯穿讲解编译器的每个阶段：
 *   - 词法分析：标识符、关键字、运算符、字面量的识别
 *   - 语法分析：函数定义、控制流、表达式的语法结构
 *   - 语义分析：类型检查、作用域、符号表
 *   - 中间代码：三地址码、SSA 表示
 *   - 优化：常量折叠、内联、循环优化
 *   - 代码生成：寄存器分配、调用约定、栈帧管理
 *
 * 同时也用于与 example.py 和 example.js 进行对比，
 * 展示编译型语言与解释型/JIT型语言的差异。
 */

#include <stdio.h>

/* ============================================================
 * 1. 简单函数 —— 用于演示基本的词法分析和语法分析
 * ============================================================ */

/**
 * 计算 n 的平方
 *
 * 词法分析：识别 int, square, (, int, n, ), {, return, n, *, n, ;, }
 * 语法分析：函数声明 → 参数列表 → 复合语句 → return 语句 → 乘法表达式
 * 语义分析：n 的类型为 int，返回类型匹配
 * 优化示例：可内联展开为 n * n
 */
int square(int n) {
    return n * n;
}

/**
 * 计算绝对值
 *
 * 用于演示条件分支（if-else）的编译
 * 控制流图将产生两个分支路径
 */
int abs_value(int x) {
    if (x < 0) {
        return -x;
    } else {
        return x;
    }
}

/* ============================================================
 * 2. 循环与累加 —— 用于演示循环优化
 * ============================================================ */

/**
 * 计算 1² + 2² + ... + n²
 *
 * 用于演示：
 *   - for 循环的编译（循环初始化、条件检查、递增、循环体）
 *   - 函数调用的编译（调用 square）
 *   - 循环优化（内联 square、常量传播、循环展开）
 *   - 控制流图的构建（循环头、循环体、出口块）
 */
int sum_of_squares(int n) {
    int total = 0;
    for (int i = 1; i <= n; i++) {
        total = total + square(i);
    }
    return total;
}

/**
 * 斐波那契数列（迭代版本）
 *
 * 用于演示：
 *   - while 循环的编译
 *   - 多变量赋值
 *   - 变量活跃性分析（a, b, temp 的生命周期）
 */
int fibonacci(int n) {
    if (n <= 1) {
        return n;
    }
    int a = 0;
    int b = 1;
    int i = 2;
    while (i <= n) {
        int temp = a + b;
        a = b;
        b = temp;
        i++;
    }
    return b;
}

/* ============================================================
 * 3. 数组操作 —— 用于演示内存访问和指针分析
 * ============================================================ */

/**
 * 计算数组元素之和
 *
 * 用于演示：
 *   - 数组访问的编译（基地址 + 偏移量）
 *   - 循环中的地址计算
 *   - 指针别名分析的必要性
 */
int array_sum(int arr[], int size) {
    int sum = 0;
    for (int i = 0; i < size; i++) {
        sum += arr[i];
    }
    return sum;
}

/**
 * 冒泡排序
 *
 * 用于演示：
 *   - 嵌套循环的编译
 *   - 数组元素交换（涉及地址计算和临时变量）
 *   - 循环嵌套的优化机会（循环交换等）
 */
void bubble_sort(int arr[], int size) {
    for (int i = 0; i < size - 1; i++) {
        for (int j = 0; j < size - 1 - i; j++) {
            if (arr[j] > arr[j + 1]) {
                int temp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = temp;
            }
        }
    }
}

/* ============================================================
 * 4. 递归 —— 用于演示函数调用栈和尾调用优化
 * ============================================================ */

/**
 * 阶乘（递归版本）
 *
 * 用于演示：
 *   - 递归函数调用的栈帧管理
 *   - 尾调用优化的可能性（虽然这个版本不是尾递归）
 */
int factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}

/**
 * 二分查找
 *
 * 用于演示：
 *   - 递归中的分支结构
 *   - 中间值计算 (low + high) / 2
 *   - 比较链的编译
 */
int binary_search(int arr[], int low, int high, int target) {
    if (low > high) {
        return -1;  // 未找到
    }
    int mid = low + (high - low) / 2;
    if (arr[mid] == target) {
        return mid;
    } else if (arr[mid] < target) {
        return binary_search(arr, mid + 1, high, target);
    } else {
        return binary_search(arr, low, mid - 1, target);
    }
}

/* ============================================================
 * 5. 结构体与指针 —— 用于演示复杂类型和内存布局
 * ============================================================ */

/**
 * 简单的点结构体
 *
 * 用于演示：
 *   - 结构体的内存布局（字段偏移量计算）
 *   - 成员访问运算符 (.) 的编译
 *   - 符号表中类型信息的存储
 */
typedef struct {
    int x;
    int y;
} Point;

/**
 * 计算两点之间的曼哈顿距离
 *
 * 用于演示：
 *   - 结构体作为参数的传递方式（值传递 vs 指针传递）
 *   - 结构体字段访问的编译（偏移量寻址）
 */
int manhattan_distance(Point p1, Point p2) {
    return abs_value(p1.x - p2.x) + abs_value(p1.y - p2.y);
}

/**
 * 交换两个点的坐标
 *
 * 用于演示：
 *   - 指针参数的编译（间接寻址）
 *   - 指针解引用 (*) 的编译
 */
void swap_points(Point *p1, Point *p2) {
    Point temp = *p1;
    *p1 = *p2;
    *p2 = temp;
}

/* ============================================================
 * 6. 作用域演示 —— 用于演示符号表和作用域链
 * ============================================================ */

int scope_demo(int x) {
    int result = x;

    {   // 内层作用域
        int x = 100;  // 遮蔽外层的 x
        result = result + x;  // 使用内层的 x（100）
    }

    // 此处 x 恢复为参数 x
    result = result + x;

    return result;
    // 对于调用 scope_demo(5)：
    // result = 5 + 100 + 5 = 110
}

/* ============================================================
 * 7. 主函数 —— 综合演示
 * ============================================================ */

int main() {
    // --- 基本函数调用 ---
    printf("=== 基本函数 ===\n");
    printf("square(5) = %d\n", square(5));
    printf("abs_value(-7) = %d\n", abs_value(-7));

    // --- 循环与累加 ---
    printf("\n=== 循环与累加 ===\n");
    printf("sum_of_squares(5) = %d\n", sum_of_squares(5));
    printf("fibonacci(10) = %d\n", fibonacci(10));

    // --- 数组操作 ---
    printf("\n=== 数组操作 ===\n");
    int numbers[] = {64, 34, 25, 12, 22, 11, 90};
    int size = sizeof(numbers) / sizeof(numbers[0]);

    printf("排序前: ");
    for (int i = 0; i < size; i++) {
        printf("%d ", numbers[i]);
    }
    printf("\n");

    printf("数组元素之和: %d\n", array_sum(numbers, size));

    bubble_sort(numbers, size);

    printf("排序后: ");
    for (int i = 0; i < size; i++) {
        printf("%d ", numbers[i]);
    }
    printf("\n");

    // --- 递归 ---
    printf("\n=== 递归 ===\n");
    printf("factorial(6) = %d\n", factorial(6));

    int sorted_arr[] = {2, 5, 8, 12, 16, 23, 38, 56, 72, 91};
    int idx = binary_search(sorted_arr, 0, 9, 23);
    printf("binary_search(23) = %d\n", idx);

    // --- 结构体与指针 ---
    printf("\n=== 结构体与指针 ===\n");
    Point p1 = {3, 4};
    Point p2 = {7, 1};
    printf("曼哈顿距离: %d\n", manhattan_distance(p1, p2));

    printf("交换前: p1=(%d,%d), p2=(%d,%d)\n", p1.x, p1.y, p2.x, p2.y);
    swap_points(&p1, &p2);
    printf("交换后: p1=(%d,%d), p2=(%d,%d)\n", p1.x, p1.y, p2.x, p2.y);

    // --- 作用域 ---
    printf("\n=== 作用域 ===\n");
    printf("scope_demo(5) = %d\n", scope_demo(5));

    return 0;
}
