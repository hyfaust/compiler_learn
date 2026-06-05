/* ============================================================
 * demo_gcc_stages.c - 演示GCC编译的各个阶段
 *
 * 本文件包含多种C语言特性，用于观察GCC各编译阶段的输出。
 *
 * 使用方法:
 *   gcc -E demo_gcc_stages.c -o demo_gcc_stages.i     # 预处理结果
 *   gcc -S -O0 demo_gcc_stages.c                      # 无优化汇编
 *   gcc -S -O2 demo_gcc_stages.c                      # 优化后汇编
 *   gcc -S -O2 -masm=intel demo_gcc_stages.c          # Intel语法汇编
 *   gcc -save-temps demo_gcc_stages.c                  # 保留所有中间文件
 *   gcc -fdump-tree-gimple demo_gcc_stages.c           # 查看GIMPLE IR
 *   gcc -c demo_gcc_stages.c -o demo_gcc_stages.o     # 生成目标文件
 *   objdump -d demo_gcc_stages.o                       # 反汇编目标文件
 * ============================================================ */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>

/* ============================================================
 * 第一部分: 宏定义和预处理指令
 *
 * 预处理器会在编译前展开这些宏。
 * 使用 -E 选项可以看到展开后的结果。
 * ============================================================ */

#define MAX_SIZE    100
#define SQUARE(x)   ((x) * (x))
#define MAX(a, b)   ((a) > (b) ? (a) : (b))
#define MIN(a, b)   ((a) < (b) ? (a) : (b))
#define ARRAY_LEN(arr) (sizeof(arr) / sizeof((arr)[0]))

/* 条件编译: 根据平台选择不同的定义 */
#ifdef _WIN32
    #define PLATFORM "Windows"
    #include <windows.h>
#elif defined(__linux__)
    #define PLATFORM "Linux"
    #include <unistd.h>
#else
    #define PLATFORM "Unknown"
#endif

/* ============================================================
 * 第二部分: 全局变量和类型定义
 *
 * 这些在汇编中会出现在 .data 或 .bss 段。
 * ============================================================ */

/* 枚举类型 */
typedef enum {
    STATUS_OK = 0,
    STATUS_ERROR = -1,
    STATUS_PENDING = 1,
} Status;

/* 结构体 */
typedef struct {
    int x;
    int y;
} Point;

typedef struct {
    char name[64];
    int age;
    double gpa;
    Point address;     /* 嵌套结构体 */
} Student;

/* 联合体 */
typedef union {
    int int_val;
    float float_val;
    char bytes[4];
} DataUnion;

/* 函数指针类型 */
typedef int (*Comparator)(const void *, const void *);

/* 全局变量 */
static int g_counter = 0;
static const double PI = 3.14159265358979323846;
static const char *g_program_name = "gcc_stages_demo";

/* ============================================================
 * 第三部分: 基础函数
 *
 * 观察简单函数在不同优化级别下的汇编差异。
 * -O0: 直接翻译，每次访问内存
 * -O2: 内联、常量折叠、寄存器分配优化
 * ============================================================ */

/* 简单算术函数 */
int add(int a, int b) {
    return a + b;
}

int multiply(int a, int b) {
    return a * b;
}

/* 使用宏的函数（观察宏展开） */
int compute_area(int width, int height) {
    return SQUARE(width + height);  /* 宏展开后: ((width + height) * (width + height)) */
}

/* 带static inline的函数（观察内联优化） */
static inline int clamp(int value, int lo, int hi) {
    if (value < lo) return lo;
    if (value > hi) return hi;
    return value;
}

/* ============================================================
 * 第四部分: 递归与控制流
 *
 * 递归函数在 -O2 下可能被转化为迭代形式（尾递归优化）。
 * switch语句可能被编译为跳转表(jump table)。
 * ============================================================ */

/* 递归: 阶乘 */
long factorial(int n) {
    if (n <= 1) {
        return 1;
    }
    return n * factorial(n - 1);
}

/* 递归: 斐波那契（指数复杂度，用于观察低效递归的汇编） */
int fibonacci_naive(int n) {
    if (n <= 1) return n;
    return fibonacci_naive(n - 1) + fibonacci_naive(n - 2);
}

/* 迭代: 斐波那契（对比递归版本的汇编效率） */
long fibonacci_iterative(int n) {
    if (n <= 1) return n;

    long prev2 = 0;
    long prev1 = 1;
    long current = 0;

    for (int i = 2; i <= n; i++) {
        current = prev1 + prev2;
        prev2 = prev1;
        prev1 = current;
    }
    return current;
}

/* switch语句 —— 观察是否生成跳转表 */
const char* status_to_string(Status s) {
    switch (s) {
        case STATUS_OK:      return "OK";
        case STATUS_ERROR:   return "Error";
        case STATUS_PENDING: return "Pending";
        default:             return "Unknown";
    }
}

/* 嵌套控制流 */
int classify_number(int n) {
    if (n > 0) {
        if (n % 2 == 0) {
            return 2;  /* 正偶数 */
        } else {
            return 1;  /* 正奇数 */
        }
    } else if (n < 0) {
        return -1;     /* 负数 */
    } else {
        return 0;      /* 零 */
    }
}

/* ============================================================
 * 第五部分: 数组和指针操作
 *
 * 数组访问会被编译为基址+偏移的内存访问。
 * 指针运算在汇编中体现为地址计算。
 * ============================================================ */

/* 数组求和 */
int array_sum(const int arr[], int len) {
    int sum = 0;
    for (int i = 0; i < len; i++) {
        sum += arr[i];
    }
    return sum;
}

/* 指针版本的数组求和（对比数组下标版本） */
int array_sum_ptr(const int *arr, int len) {
    int sum = 0;
    const int *end = arr + len;
    while (arr < end) {
        sum += *arr++;
    }
    return sum;
}

/* 冒泡排序（观察嵌套循环的汇编结构） */
void bubble_sort(int arr[], int n) {
    for (int i = 0; i < n - 1; i++) {
        int swapped = 0;
        for (int j = 0; j < n - 1 - i; j++) {
            if (arr[j] > arr[j + 1]) {
                int temp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = temp;
                swapped = 1;
            }
        }
        if (!swapped) break;  /* 优化: 已有序则提前退出 */
    }
}

/* 字符串处理（观察对 libc 函数的调用） */
int count_char(const char *str, char target) {
    int count = 0;
    while (*str) {
        if (*str == target) {
            count++;
        }
        str++;
    }
    return count;
}

/* ============================================================
 * 第六部分: 结构体和动态内存
 *
 * 结构体字段访问编译为 基址+字段偏移。
 * 动态内存分配体现为对 malloc/free 的调用。
 * ============================================================ */

/* 创建学生（动态分配） */
Student* create_student(const char *name, int age, double gpa, int px, int py) {
    Student *s = (Student*)malloc(sizeof(Student));
    if (s == NULL) {
        return NULL;
    }

    strncpy(s->name, name, sizeof(s->name) - 1);
    s->name[sizeof(s->name) - 1] = '\0';
    s->age = age;
    s->gpa = gpa;
    s->address.x = px;
    s->address.y = py;

    return s;
}

/* 释放学生 */
void destroy_student(Student *s) {
    if (s != NULL) {
        free(s);
    }
}

/* 结构体数组排序（使用函数指针） */
int compare_by_gpa(const void *a, const void *b) {
    const Student *sa = (const Student*)a;
    const Student *sb = (const Student*)b;

    if (sa->gpa < sb->gpa) return -1;
    if (sa->gpa > sb->gpa) return 1;
    return 0;
}

/* ============================================================
 * 第七部分: 位操作和算术优化
 *
 * 编译器可能将某些乘除法转化为移位操作。
 * 例如: x * 8 → x << 3, x / 4 → x >> 2 (对无符号数)
 * ============================================================ */

/* 判断是否为2的幂 */
int is_power_of_two(unsigned int n) {
    return n > 0 && (n & (n - 1)) == 0;
}

/* 计算下一个2的幂（向上取整） */
unsigned int next_power_of_two(unsigned int n) {
    if (n == 0) return 1;
    n--;
    n |= n >> 1;
    n |= n >> 2;
    n |= n >> 4;
    n |= n >> 8;
    n |= n >> 16;
    n++;
    return n;
}

/* 无分支的绝对值（观察条件移动指令 cmov） */
int abs_no_branch(int x) {
    int mask = x >> 31;  /* 算术右移: 负数全1, 非负全0 */
    return (x ^ mask) - mask;
}

/* ============================================================
 * 第八部分: 浮点运算
 *
 * 观察SSE/AVX浮点指令的使用。
 * 注意: -Ofast可能违反IEEE 754标准。
 * ============================================================ */

/* 向量点积 */
double dot_product(const double *a, const double *b, int n) {
    double sum = 0.0;
    for (int i = 0; i < n; i++) {
        sum += a[i] * b[i];
    }
    return sum;
}

/* 欧几里得距离 */
double euclidean_distance(double x1, double y1, double x2, double y2) {
    double dx = x2 - x1;
    double dy = y2 - y1;
    return sqrt(dx * dx + dy * dy);
}

/* 多项式求值 (Horner方法) */
double horner_eval(const double *coeffs, int degree, double x) {
    double result = coeffs[degree];
    for (int i = degree - 1; i >= 0; i--) {
        result = result * x + coeffs[i];
    }
    return result;
}

/* ============================================================
 * 第九部分: 主函数 —— 综合演示
 * ============================================================ */

int main(void) {
    printf("=== GCC Compilation Stages Demo ===\n");
    printf("Program: %s\n", g_program_name);
    printf("Platform: %s\n\n", PLATFORM);

    /* --- 基础运算 --- */
    printf("--- Basic Arithmetic ---\n");
    int a = 15, b = 7;
    printf("%d + %d = %d\n", a, b, add(a, b));
    printf("%d * %d = %d\n", a, b, multiply(a, b));
    printf("compute_area(%d, %d) = %d\n", a, b, compute_area(a, b));
    printf("clamp(%d, 0, 10) = %d\n\n", a, clamp(a, 0, 10));

    /* --- 递归与迭代 --- */
    printf("--- Recursion & Iteration ---\n");
    printf("factorial(10) = %ld\n", factorial(10));
    printf("fibonacci_naive(10) = %d\n", fibonacci_naive(10));
    printf("fibonacci_iterative(10) = %ld\n", fibonacci_iterative(10));
    printf("classify_number(42) = %d\n", classify_number(42));
    printf("classify_number(-7) = %d\n", classify_number(-7));
    printf("status_to_string(STATUS_OK) = %s\n\n", status_to_string(STATUS_OK));

    /* --- 数组操作 --- */
    printf("--- Array Operations ---\n");
    int numbers[] = {64, 34, 25, 12, 22, 11, 90};
    int n = ARRAY_LEN(numbers);

    printf("Original: ");
    for (int i = 0; i < n; i++) printf("%d ", numbers[i]);
    printf("\n");

    printf("array_sum = %d\n", array_sum(numbers, n));
    printf("array_sum_ptr = %d\n", array_sum_ptr(numbers, n));

    bubble_sort(numbers, n);
    printf("Sorted:   ");
    for (int i = 0; i < n; i++) printf("%d ", numbers[i]);
    printf("\n\n");

    /* --- 字符串操作 --- */
    printf("--- String Operations ---\n");
    const char *text = "Hello, World!";
    printf("count_char('%s', 'l') = %d\n\n", text, count_char(text, 'l'));

    /* --- 结构体操作 --- */
    printf("--- Struct Operations ---\n");
    Student *students[3];
    students[0] = create_student("Alice", 20, 3.8, 100, 200);
    students[1] = create_student("Bob", 22, 3.5, 150, 300);
    students[2] = create_student("Charlie", 21, 3.9, 200, 100);

    if (students[0] && students[1] && students[2]) {
        qsort(students, 3, sizeof(Student*), compare_by_gpa);
        for (int i = 0; i < 3; i++) {
            printf("  %s: age=%d, gpa=%.2f, addr=(%d,%d)\n",
                   students[i]->name, students[i]->age, students[i]->gpa,
                   students[i]->address.x, students[i]->address.y);
        }
    }

    for (int i = 0; i < 3; i++) {
        destroy_student(students[i]);
    }
    printf("\n");

    /* --- 位操作 --- */
    printf("--- Bit Operations ---\n");
    for (unsigned int v = 1; v <= 32; v *= 2) {
        printf("is_power_of_two(%u) = %d\n", v, is_power_of_two(v));
    }
    printf("next_power_of_two(100) = %u\n", next_power_of_two(100));
    printf("abs_no_branch(-42) = %d\n\n", abs_no_branch(-42));

    /* --- 浮点运算 --- */
    printf("--- Floating Point ---\n");
    double va[] = {1.0, 2.0, 3.0};
    double vb[] = {4.0, 5.0, 6.0};
    printf("dot_product = %.2f\n", dot_product(va, vb, 3));
    printf("euclidean_distance(0,0,3,4) = %.2f\n", euclidean_distance(0, 0, 3, 4));

    double coeffs[] = {1, -2, 3, -4};  /* 1 - 2x + 3x^2 - 4x^3 */
    printf("horner_eval(coeffs, 3, 2.0) = %.2f\n", horner_eval(coeffs, 3, 2.0));

    printf("\n=== Compilation stages demo complete ===\n");
    return 0;
}
