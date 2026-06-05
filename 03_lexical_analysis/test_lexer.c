/**
 * 测试词法分析器的C代码示例
 * =========================
 * 
 * 本文件包含各种C语言词法元素，用于测试词法分析器。
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>

/* 预处理指令 */
#define MAX_SIZE 100
#define SQUARE(x) ((x) * (x))
#define DEBUG

#ifdef DEBUG
    #define LOG(msg) printf("[DEBUG] %s\n", msg)
#else
    #define LOG(msg)
#endif

/* 枚举类型 */
enum Color {
    RED,      /* 0 */
    GREEN,    /* 1 */
    BLUE      /* 2 */
};

/* 结构体 */
struct Point {
    int x;
    int y;
};

/* 联合体 */
union Data {
    int i;
    float f;
    char str[20];
};

/* 类型定义 */
typedef struct {
    char name[50];
    int age;
    float score;
} Student;

/* 全局变量 */
int global_count = 0;
const float PI = 3.14159f;
static char buffer[MAX_SIZE];

/**
 * 函数声明
 */
int fibonacci(int n);
void swap(int *a, int *b);
Student create_student(const char *name, int age, float score);

/**
 * 计算斐波那契数列
 * 使用递归方式实现
 */
int fibonacci(int n) {
    // 基础情况
    if (n <= 0) {
        return 0;
    }
    if (n == 1) {
        return 1;
    }
    
    /* 递归计算 */
    return fibonacci(n - 1) + fibonacci(n - 2);
}

/**
 * 交换两个整数
 */
void swap(int *a, int *b) {
    int temp = *a;
    *a = *b;
    *b = temp;
}

/**
 * 创建学生结构体
 */
Student create_student(const char *name, int age, float score) {
    Student s;
    strncpy(s.name, name, sizeof(s.name) - 1);
    s.name[sizeof(s.name) - 1] = '\0';
    s.age = age;
    s.score = score;
    return s;
}

/**
 * 数组操作示例
 */
void array_demo(void) {
    int arr[10] = {0, 1, 2, 3, 4, 5, 6, 7, 8, 9};
    int *ptr = arr;
    
    // 指针算术
    for (int i = 0; i < 10; i++) {
        printf("arr[%d] = %d, *(ptr+%d) = %d\n", 
               i, arr[i], i, *(ptr + i));
    }
    
    // 数组指针
    int (*ap)[10] = &arr;
    printf("First element: %d\n", (*ap)[0]);
}

/**
 * 位运算示例
 */
void bitwise_demo(void) {
    unsigned int a = 0xFF;    // 十六进制: 255
    unsigned int b = 0x0F;    // 十六进制: 15
    
    printf("a = 0x%X, b = 0x%X\n", a, b);
    printf("a & b = 0x%X\n", a & b);   // 按位与
    printf("a | b = 0x%X\n", a | b);   // 按位或
    printf("a ^ b = 0x%X\n", a ^ b);   // 按位异或
    printf("~a = 0x%X\n", ~a);         // 按位取反
    printf("a << 4 = 0x%X\n", a << 4); // 左移
    printf("a >> 4 = 0x%X\n", a >> 4); // 右移
}

/**
 * 字符串操作示例
 */
void string_demo(void) {
    char str1[] = "Hello";
    char str2[] = "World";
    char result[100];
    
    // 字符串长度
    printf("Length of '%s': %lu\n", str1, strlen(str1));
    
    // 字符串连接
    strcpy(result, str1);
    strcat(result, " ");
    strcat(result, str2);
    printf("Concatenated: %s\n", result);
    
    // 字符串比较
    int cmp = strcmp(str1, str2);
    if (cmp < 0) {
        printf("'%s' < '%s'\n", str1, str2);
    } else if (cmp > 0) {
        printf("'%s' > '%s'\n", str1, str2);
    } else {
        printf("'%s' == '%s'\n", str1, str2);
    }
    
    // 转义字符演示
    printf("Tab:\tHere\n");
    printf("Newline:\nHere\n");
    printf("Backslash: \\\n");
    printf("Quote: \"\n");
    printf("Null: \\0\n");
}

/**
 * 控制流示例
 */
void control_flow_demo(int x) {
    // if-else
    if (x > 0) {
        printf("Positive\n");
    } else if (x < 0) {
        printf("Negative\n");
    } else {
        printf("Zero\n");
    }
    
    // switch-case
    switch (x % 3) {
        case 0:
            printf("Divisible by 3\n");
            break;
        case 1:
            printf("Remainder 1\n");
            break;
        case 2:
            printf("Remainder 2\n");
            break;
        default:
            printf("Impossible\n");
            break;
    }
    
    // while循环
    int count = 0;
    while (count < 5) {
        count++;
    }
    
    // do-while循环
    do {
        count--;
    } while (count > 0);
    
    // for循环
    for (int i = 0; i < 10; i++) {
        if (i == 5) continue;
        if (i == 8) break;
    }
    
    // goto（不推荐使用，仅用于测试）
    goto end;
    printf("This will not be printed\n");
end:
    printf("End of control flow demo\n");
}

/**
 * 运算符测试
 */
void operator_demo(void) {
    int a = 10, b = 3;
    
    // 算术运算符
    printf("a + b = %d\n", a + b);
    printf("a - b = %d\n", a - b);
    printf("a * b = %d\n", a * b);
    printf("a / b = %d\n", a / b);
    printf("a %% b = %d\n", a % b);
    
    // 自增自减
    printf("a++ = %d\n", a++);
    printf("++a = %d\n", ++a);
    printf("a-- = %d\n", a--);
    printf("--a = %d\n", --a);
    
    // 关系运算符
    printf("a > b: %d\n", a > b);
    printf("a < b: %d\n", a < b);
    printf("a >= b: %d\n", a >= b);
    printf("a <= b: %d\n", a <= b);
    printf("a == b: %d\n", a == b);
    printf("a != b: %d\n", a != b);
    
    // 逻辑运算符
    printf("a && b: %d\n", a && b);
    printf("a || b: %d\n", a || b);
    printf("!a: %d\n", !a);
    
    // 赋值运算符
    int c = a;
    c += b;  // c = c + b
    c -= b;  // c = c - b
    c *= b;  // c = c * b
    c /= b;  // c = c / b
    c %= b;  // c = c % b
    
    // 条件运算符
    int max = (a > b) ? a : b;
    printf("Max of %d and %d is %d\n", a, b, max);
    
    // sizeof运算符
    printf("sizeof(int): %lu\n", sizeof(int));
    printf("sizeof(float): %lu\n", sizeof(float));
    printf("sizeof(double): %lu\n", sizeof(double));
    printf("sizeof(char): %lu\n", sizeof(char));
    printf("sizeof(pointer): %lu\n", sizeof(void*));
}

/**
 * 内存管理示例
 */
void memory_demo(void) {
    // malloc
    int *arr = (int*)malloc(10 * sizeof(int));
    if (arr == NULL) {
        fprintf(stderr, "Memory allocation failed\n");
        return;
    }
    
    // 使用内存
    for (int i = 0; i < 10; i++) {
        arr[i] = i * i;
    }
    
    // calloc
    int *zero_arr = (int*)calloc(10, sizeof(int));
    
    // realloc
    arr = (int*)realloc(arr, 20 * sizeof(int));
    
    // 释放内存
    free(arr);
    free(zero_arr);
}

/**
 * 主函数
 */
int main(int argc, char *argv[]) {
    printf("=== 词法分析器测试程序 ===\n\n");
    
    // 整数和浮点数
    int int_val = 42;
    float float_val = 3.14f;
    double double_val = 1.23e-4;
    long long_val = 100L;
    unsigned int uint_val = 0xFF;
    int oct_val = 077;
    
    printf("整数: %d\n", int_val);
    printf("浮点数: %f\n", float_val);
    printf("科学计数法: %e\n", double_val);
    printf("长整型: %ld\n", long_val);
    printf("十六进制: 0x%X\n", uint_val);
    printf("八进制: 0%o\n", oct_val);
    
    // 字符和字符串
    char ch = 'A';
    char *str = "Hello, World!";
    char str_arr[] = "Array string";
    
    printf("\n字符: '%c'\n", ch);
    printf("字符串指针: \"%s\"\n", str);
    printf("字符串数组: \"%s\"\n", str_arr);
    
    // 布尔值 (C99+)
    bool flag = true;
    printf("\n布尔值: %d\n", flag);
    
    // 调用函数
    printf("\n斐波那契数列:\n");
    for (int i = 0; i < 10; i++) {
        printf("  fib(%d) = %d\n", i, fibonacci(i));
    }
    
    // 数组和指针
    printf("\n--- 数组演示 ---\n");
    array_demo();
    
    // 位运算
    printf("\n--- 位运算演示 ---\n");
    bitwise_demo();
    
    // 字符串操作
    printf("\n--- 字符串演示 ---\n");
    string_demo();
    
    // 控制流
    printf("\n--- 控制流演示 ---\n");
    control_flow_demo(42);
    
    // 运算符
    printf("\n--- 运算符演示 ---\n");
    operator_demo();
    
    // 结构体和联合体
    printf("\n--- 结构体演示 ---\n");
    struct Point p = {10, 20};
    printf("Point: (%d, %d)\n", p.x, p.y);
    
    Student s = create_student("Alice", 20, 95.5f);
    printf("Student: %s, age=%d, score=%.1f\n", s.name, s.age, s.score);
    
    // 枚举
    printf("\n--- 枚举演示 ---\n");
    enum Color color = RED;
    printf("Color: %d\n", color);
    
    // 多行字符串（使用续行符）
    printf("\n--- 多行字符串 ---\n");
    char *multiline = "This is a \
very long \
string";
    printf("%s\n", multiline);
    
    // void指针
    printf("\n--- void指针 ---\n");
    void *vptr = &int_val;
    printf("Value via void*: %d\n", *(int*)vptr);
    
    // 函数指针
    printf("\n--- 函数指针 ---\n");
    int (*func_ptr)(int) = fibonacci;
    printf("fib(10) via function pointer: %d\n", func_ptr(10));
    
    // 类型转换
    printf("\n--- 类型转换 ---\n");
    int numerator = 7, denominator = 2;
    float result = (float)numerator / denominator;
    printf("7 / 2 = %.2f\n", result);
    
    printf("\n=== 测试完成 ===\n");
    
    return 0;
}
