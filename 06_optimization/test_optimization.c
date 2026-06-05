/**
 * test_optimization.c
 * ===================
 *
 * 展示各种优化机会的 C 代码示例。
 *
 * 每个函数展示一种或多种编译器可以应用的优化技术。
 * 使用 gcc 编译时，对比不同优化级别的汇编输出：
 *
 *   gcc -O0 -S test_optimization.c -o unoptimized.s
 *   gcc -O2 -S test_optimization.c -o optimized.s
 *   diff unoptimized.s optimized.s
 *
 * 或者查看优化报告（GCC 4.6+）：
 *   gcc -O2 -fopt-info-optimized test_optimization.c
 *
 * 注意：某些优化在 -O0 下完全不执行，这有助于对比理解。
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ============================================================
 * 1. 常量折叠 (Constant Folding)
 *
 * 编译器在编译时计算常量表达式的值。
 * ============================================================ */

int constant_folding_demo(void)
{
    /* 基本常量折叠 */
    int a = 3 + 5;              /* 编译时计算为 8 */
    int b = 10 * 4;             /* 编译时计算为 40 */
    int c = 100 / 5;            /* 编译时计算为 20 */
    int d = 7 - 3;              /* 编译时计算为 4 */

    /* 链式常量折叠 */
    int e = a + b;              /* 如果 a, b 都是常量，则 e = 48 */
    int f = e * 2;              /* f = 96 */

    /* 条件常量折叠 */
    int g = (1 > 0);            /* g = 1 (true) */
    int h = (3 == 5);           /* h = 0 (false) */

    /* 浮点常量折叠 */
    double pi_times_2 = 3.14159 * 2.0;  /* 编译时计算为 6.28318 */

    return (int)(a + b + c + d + e + f + g + h + pi_times_2);
}

/* ============================================================
 * 2. 常量传播 (Constant Propagation)
 *
 * 如果变量被赋值为常量且之后未修改，则用常量替换。
 * ============================================================ */

int constant_propagation_demo(int x)
{
    int a = 10;           /* a 是常量 10 */
    int b = a + 5;        /* b = 10 + 5 = 15 (常量折叠 + 传播) */
    int c = a * b;        /* c = 10 * 15 = 150 (常量折叠 + 传播) */
    int d = c - a;        /* d = 150 - 10 = 140 (常量折叠 + 传播) */

    /* 常量传播到条件分支 */
    if (a > 0) {          /* 条件恒为 true */
        return d + x;     /* 只有这条路径可达 */
    } else {
        return 0;         /* 不可达代码，可以消除 */
    }
}

/* ============================================================
 * 3. 死代码消除 (Dead Code Elimination)
 *
 * 删除计算结果从未被使用的代码。
 * ============================================================ */

int dead_code_elimination_demo(int n)
{
    int result = 0;

    /* 死代码：未使用的变量 */
    int unused1 = 42;
    int unused2 = n * 2 + 1;
    int unused3 = unused1 + unused2;  /* unused3 也未使用 */

    /* 不可达代码 */
    if (0) {
        /* 编译器知道这个条件永远为 false */
        printf("This will never execute\n");
        result = 999;
    }

    /* 恒为真的条件 → else 分支不可达 */
    if (1) {
        result = n * 2;
    } else {
        /* 不可达代码 */
        result = n * 3;
        int dead = n * 4;  /* 死代码 */
        (void)dead;
    }

    /* 赋值后立即覆盖（前一个赋值是死代码） */
    int x = compute_something(n);  /* 如果 compute 是纯函数，可消除 */
    x = n + 1;                     /* 覆盖了上面的赋值 */

    (void)unused1;
    (void)unused2;
    (void)unused3;

    return result + x;
}

/* 辅助函数 */
static int compute_something(int x)
{
    return x * x;
}

/* ============================================================
 * 4. 公共子表达式消除 (CSE)
 *
 * 如果表达式之前已计算且操作数未变，复用结果。
 * ============================================================ */

int cse_demo(int a, int b, int c, int d)
{
    /* 明显的公共子表达式 */
    int x = a + b;
    int y = a + b;        /* y = x (CSE) */
    int z = (a + b) * c;  /* z = x * c (CSE) */

    /* 数组索引中的公共子表达式 */
    /* 假设有数组 arr[100] */
    int arr[100];
    arr[a * 4] = 10;       /* 计算 a * 4 */
    arr[a * 4 + 1] = 20;   /* 复用 a * 4 的结果 */
    arr[a * 4 + 2] = 30;   /* 再次复用 */

    /* 结构体字段访问中的公共子表达式 */
    /* a + b 被多次计算 */
    int w = (a + b) + c;
    int v = (a + b) + d;   /* 复用 a + b */

    return x + y + z + w + v + arr[a * 4];
}

/* ============================================================
 * 5. 循环不变量外提 (LICM)
 *
 * 循环中不变的计算可以移到循环外部。
 * ============================================================ */

int loop_invariant_demo(int *arr, int n, int x, int y)
{
    int sum = 0;

    /* x * y + 100 是循环不变量 */
    /* x, y 在循环中不被修改，所以 x * y 每次迭代都相同 */
    for (int i = 0; i < n; i++) {
        int invariant = x * y + 100;   /* 应该被外提 */
        sum += arr[i] + invariant;
    }

    return sum;
}

/* 更复杂的循环不变量示例 */
int loop_invariant_complex(int *a, int *b, int n, int scale)
{
    int result = 0;
    int base = scale * 4;   /* 循环外的常量，本身可折叠 */

    for (int i = 0; i < n; i++) {
        /* base 是循环不变量 */
        int offset = base + i;      /* base 不变，但 i 变化 → 不能完全外提 */
        result += a[offset];        /* a[offset] 不是不变量 */

        /* 这部分是循环不变量 */
        int factor = scale * 2;     /* 应被外提 */
        b[i] = i * factor;
    }

    return result;
}

/* ============================================================
 * 6. 强度削弱 (Strength Reduction)
 *
 * 用低代价操作替代高代价操作，尤其在循环中。
 * ============================================================ */

int strength_reduction_demo(int *arr, int n)
{
    int sum = 0;

    /* 循环中的乘法可以被强度削弱为加法 */
    for (int i = 0; i < n; i++) {
        /* i * 4 可以用加法替代:
         *   t = 0;
         *   t += 4;  (每次迭代)
         */
        int index = i * 4;
        sum += arr[index];

        /* i * 8 + 100 也可以被强度削弱 */
        int val = i * 8 + 100;
        sum += val;
    }

    return sum;
}

/* 除法的强度削弱 */
int strength_reduction_div(int n)
{
    int sum = 0;

    for (int i = 0; i < n; i++) {
        /* 除以常量可以转换为乘法 + 移位 */
        int quotient = i / 4;        /* 可转为 (i >> 2) 或乘以 magic number */
        sum += quotient;

        int modulo = i % 8;          /* 可转为 (i & 7) */
        sum += modulo;
    }

    return sum;
}

/* ============================================================
 * 7. 循环展开 (Loop Unrolling)
 *
 * 复制循环体多份，减少循环控制开销。
 * ============================================================ */

int loop_unroll_demo(int *arr, int n)
{
    int sum = 0;

    /* 简单的求和循环，适合展开 */
    for (int i = 0; i < n; i++) {
        sum += arr[i];
    }

    return sum;
}

/* 手动展开 4 次的版本（编译器可以自动做这个） */
int loop_unroll_manual(int *arr, int n)
{
    int sum = 0;
    int i = 0;

    /* 主循环：每次处理 4 个元素 */
    for (; i + 3 < n; i += 4) {
        sum += arr[i];
        sum += arr[i + 1];
        sum += arr[i + 2];
        sum += arr[i + 3];
    }

    /* 处理剩余元素 */
    for (; i < n; i++) {
        sum += arr[i];
    }

    return sum;
}

/* ============================================================
 * 8. 内联优化 (Inlining)
 *
 * 将函数调用替换为函数体，消除调用开销。
 * ============================================================ */

/* 小函数，适合内联 */
static inline int square(int x)
{
    return x * x;
}

static inline int max_int(int a, int b)
{
    return a > b ? a : b;
}

int inlining_demo(int a, int b, int c)
{
    /* 这些调用可以被内联 */
    int s1 = square(a);
    int s2 = square(b);
    int m = max_int(s1, s2);

    /* 内联后还可以进一步优化：
     *   s1 = a * a
     *   s2 = b * b
     *   m = (a*a > b*b) ? a*a : b*b  (CSE 可以进一步优化)
     */
    return m + square(c);
}

/* ============================================================
 * 9. 尾调用优化 (Tail Call Optimization)
 *
 * 如果函数的最后一步是调用另一个函数，可以复用当前栈帧。
 * ============================================================ */

/* 尾递归版本的阶乘 */
int factorial_tail(int n, int acc)
{
    if (n <= 1) return acc;
    return factorial_tail(n - 1, n * acc);  /* 尾调用，可优化为循环 */
}

/* 非尾递归版本（不能做尾调用优化） */
int factorial_normal(int n)
{
    if (n <= 1) return 1;
    return n * factorial_normal(n - 1);  /* 不是尾调用：返回 n * (递归结果) */
}

/* ============================================================
 * 10. 综合优化示例
 *
 * 展示多种优化技术的组合效果。
 * ============================================================ */

/**
 * 计算矩阵乘法的一部分：C[i][j] = sum(A[i][k] * B[k][j])
 *
 * 优化机会：
 * - LICM: A[i][k] 在内层循环中是不变量（如果 k 是内层变量）
 * - CSE: 矩阵索引计算是公共子表达式
 * - 循环展开: 内层循环可以展开
 * - 强度削弱: 多维数组索引的乘法
 * - 向量化: 内层循环可以使用 SIMD 指令
 */
void matrix_multiply_optimization(int n,
                                   int A[n][n],
                                   int B[n][n],
                                   int C[n][n])
{
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n; j++) {
            int sum = 0;
            for (int k = 0; k < n; k++) {
                /* A[i][k] * B[k][j]
                 *
                 * 优化:
                 * 1. A[i][k] 的地址 = &A[0][0] + i*n*4 + k*4
                 *    其中 i*n*4 是循环不变量（LICM）
                 * 2. B[k][j] 的地址 = &B[0][0] + k*n*4 + j*4
                 *    其中 j*4 在中层循环是不变量（LICM）
                 *    k*n*4 可以用强度削弱 (k*n*4 → t += n*4)
                 * 3. 乘法和累加可以用 SIMD 向量化
                 */
                sum += A[i][k] * B[k][j];
            }
            C[i][j] = sum;
        }
    }
}

/**
 * 字符串处理中的优化机会
 *
 * 优化机会：
 * - strlen 的重复调用可以用 CSE 消除
 * - 循环中的不变量可以外提
 * - 死代码消除可以移除未使用的变量
 */
int string_processing_demo(const char *str)
{
    int len = (int)strlen(str);    /* 计算一次 */
    int upper_count = 0;
    int digit_count = 0;

    for (int i = 0; i < len; i++) {  /* len 是循环不变量 */
        char c = str[i];

        if (c >= 'A' && c <= 'Z') {
            upper_count++;
        }
        if (c >= '0' && c <= '9') {
            digit_count++;
        }

        /* 死代码示例 */
        int unused = c * 2 + 1;  /* 未使用的计算 */
        (void)unused;
    }

    /* 以下 strlen 是重复计算（如果编译器不能证明 str 未变） */
    /* 但由于循环中没有修改 str，编译器可能能优化 */
    int len2 = (int)strlen(str);

    return upper_count + digit_count + len2;
}

/**
 * 位运算优化示例
 *
 * 编译器会自动进行这些强度削弱。
 */
int bit_operation_demo(int x)
{
    int a = x * 2;       /* 可转为 x << 1 */
    int b = x * 4;       /* 可转为 x << 2 */
    int c = x * 8;       /* 可转为 x << 3 */
    int d = x * 16;      /* 可转为 x << 4 */

    int e = x / 2;       /* 可转为 x >> 1 (有符号数需特殊处理) */
    int f = x / 4;       /* 可转为 x >> 2 */
    int g = x / 16;      /* 可转为 x >> 4 */

    int h = x % 8;       /* 可转为 x & 7 (当除数是 2 的幂时) */
    int i = x % 16;      /* 可转为 x & 15 */

    int j = x * 15;      /* 可转为 (x << 4) - x */
    int k = x * 7;       /* 可转为 (x << 3) - x */

    return a + b + c + d + e + f + g + h + i + j + k;
}

/* ============================================================
 * 主函数
 * ============================================================ */

int main(void)
{
    printf("=== 代码优化技术示例 ===\n\n");

    printf("本文件展示了以下优化技术:\n");
    printf("  1. 常量折叠 (Constant Folding)\n");
    printf("  2. 常量传播 (Constant Propagation)\n");
    printf("  3. 死代码消除 (Dead Code Elimination)\n");
    printf("  4. 公共子表达式消除 (CSE)\n");
    printf("  5. 循环不变量外提 (LICM)\n");
    printf("  6. 强度削弱 (Strength Reduction)\n");
    printf("  7. 循环展开 (Loop Unrolling)\n");
    printf("  8. 内联优化 (Inlining)\n");
    printf("  9. 尾调用优化 (Tail Call Optimization)\n");
    printf("  10. 综合优化示例\n\n");

    printf("编译对比方法:\n");
    printf("  gcc -O0 -S test_optimization.c -o unoptimized.s\n");
    printf("  gcc -O2 -S test_optimization.c -o optimized.s\n");
    printf("  diff unoptimized.s optimized.s\n\n");

    /* 测试各种函数 */
    int r1 = constant_folding_demo();
    int r2 = constant_propagation_demo(5);
    int r3 = dead_code_elimination_demo(10);
    int r4 = cse_demo(1, 2, 3, 4);
    int r5 = bit_operation_demo(7);

    int arr[] = {1, 2, 3, 4, 5, 6, 7, 8, 9, 10};
    int r6 = loop_invariant_demo(arr, 10, 3, 4);
    int r7 = strength_reduction_demo(arr, 10);
    int r8 = loop_unroll_demo(arr, 10);
    int r9 = inlining_demo(3, 4, 5);
    int r10 = factorial_tail(10, 1);

    printf("运行结果:\n");
    printf("  常量折叠:        %d\n", r1);
    printf("  常量传播:        %d\n", r2);
    printf("  死代码消除:      %d\n", r3);
    printf("  CSE:             %d\n", r4);
    printf("  位运算优化:      %d\n", r5);
    printf("  循环不变量外提:  %d\n", r6);
    printf("  强度削弱:        %d\n", r7);
    printf("  循环展开:        %d\n", r8);
    printf("  内联优化:        %d\n", r9);
    printf("  尾调用优化:      %d\n", r10);

    printf("\n提示: 使用 gcc -O0 和 -O2 分别编译，对比汇编输出以理解优化效果。\n");

    return 0;
}
