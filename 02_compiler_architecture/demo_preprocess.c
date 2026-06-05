/* ============================================================
 * demo_preprocess.c - 演示C预处理器的各种特性
 *
 * 使用方法:
 *   gcc -E demo_preprocess.c -o demo_preprocess.i   # 查看预处理结果
 *   gcc -E -P demo_preprocess.c                     # 去掉行标记，更易读
 *   gcc -dM -E demo_preprocess.c                    # 列出所有预定义宏
 *   gcc -Wall -o demo_preprocess demo_preprocess.c  # 正常编译运行
 *
 * 预处理阶段在编译之前执行，主要职责:
 *   1. 展开 #include 头文件
 *   2. 展开宏 (#define)
 *   3. 处理条件编译 (#ifdef, #if, ...)
 *   4. 删除注释
 *   5. 处理特殊指令 (#pragma, #error, #line)
 * ============================================================ */

#include <stdio.h>
#include <string.h>

/* ============================================================
 * 1. 对象宏（简单宏替换）
 *
 * 预处理器将代码中所有出现的宏名替换为定义的文本。
 * 习惯上宏名用大写字母，以区别于普通变量和函数。
 * ============================================================ */

#define BUFFER_SIZE  256
#define TRUE         1
#define FALSE        0
#define PI           3.14159265358979
#define NEWLINE      '\n'
#define GREETING     "Hello from the preprocessor!"

/* 注意: 宏是简单的文本替换，没有类型信息。
 * 下面的宏展开时可能有陷阱: */
#define AVERAGE_BAD  a + b / 2       /* 危险! 缺少括号 */
#define AVERAGE_GOOD ((a) + (b)) / 2 /* 正确: 加括号保护 */

/* ============================================================
 * 2. 函数宏（带参数的宏）
 *
 * 函数宏看起来像函数调用，但实际是文本替换。
 * 参数在替换文本中被实际参数替换。
 *
 * 关键注意点:
 *   - 参数要用括号保护: (x) 而不是 x
 *   - 整个表达式要用括号保护
 *   - 避免副作用: MAX(i++, j++) 会展开为 ((i++) > (j++) ? (i++) : (j++))
 * ============================================================ */

/* 基本数学宏 */
#define SQUARE(x)     ((x) * (x))
#define CUBE(x)       ((x) * (x) * (x))
#define ABS(x)        ((x) < 0 ? -(x) : (x))
#define MIN(a, b)     ((a) < (b) ? (a) : (b))
#define MAX(a, b)     ((a) > (b) ? (a) : (b))
#define CLAMP(val, lo, hi)  (MIN(MAX((val), (lo)), (hi)))

/* 类型无关的宏（利用GCC扩展 __typeof__） */
#define SWAP(a, b) do {         \
    __typeof__(a) _tmp = (a);   \
    (a) = (b);                  \
    (b) = _tmp;                 \
} while (0)

/* 数组长度 */
#define ARRAY_SIZE(arr)  (sizeof(arr) / sizeof((arr)[0]))

/* 偏移量宏（模拟标准库 offsetof） */
#define OFFSETOF(type, member)  ((size_t)&((type*)0)->member)

/* ============================================================
 * 3. # 运算符 —— 字符串化 (Stringification)
 *
 * # 运算符将其后的宏参数转换为字符串字面量。
 * 例如: STR(hello) → "hello"
 *       STR(3 + 4) → "3 + 4"  （参数先被替换再转为字符串）
 * ============================================================ */

/* 将宏参数转换为字符串 */
#define STRINGIFY(x)   #x

/* 辅助宏: 先展开再字符串化（处理嵌套宏的情况） */
#define STRINGIFY_EXPAND(x)  STRINGIFY(x)

/* 调试打印宏: 打印变量名和值 */
#define DEBUG_INT(var)    printf("  %s = %d\n", #var, (var))
#define DEBUG_DOUBLE(var) printf("  %s = %f\n", #var, (var))
#define DEBUG_STR(var)    printf("  %s = \"%s\"\n", #var, (var))

/* ============================================================
 * 4. ## 运算符 —— 标记粘贴 (Token Pasting)
 *
 * ## 运算符将两个标记(token)粘合在一起，形成一个新的标记。
 * 例如: PASTE(x, 1) → x1
 *       PASTE(token_, foo) → token_foo
 *
 * 常见用途:
 *   - 生成一系列相关的变量名或函数名
 *   - 实现泛型编程的辅助宏
 *   - 枚举值自动生成
 * ============================================================ */

/* 简单的标记粘贴 */
#define CONCAT(a, b)      a##b
#define CONCAT3(a, b, c)  a##b##c

/* 生成变量名: VAR(x) → x_value, x_name */
#define MAKE_VAR(prefix, suffix)  prefix##_##suffix

/* 生成一系列相关的函数声明 */
#define DECLARE_GETTER(type, field) \
    type get_##field(void) { return g_##field; }

#define DECLARE_SETTER(type, field) \
    void set_##field(type val) { g_##field = val; }

#define DECLARE_ACCESSOR(type, field) \
    DECLARE_GETTER(type, field)       \
    DECLARE_SETTER(type, field)

/* ============================================================
 * 使用 ## 生成的访问器示例
 * ============================================================ */

static int g_width = 0;
static int g_height = 0;
static double g_scale = 1.0;

/* 生成 get_width/set_width, get_height/set_height, get_scale/set_scale */
DECLARE_ACCESSOR(int, width)
DECLARE_ACCESSOR(int, height)
DECLARE_ACCESSOR(double, scale)

/* ============================================================
 * 5. 条件编译
 *
 * 条件编译允许根据条件选择性地编译代码段。
 * 主要形式:
 *   #ifdef / #ifndef     —— 检查宏是否已定义
 *   #if / #elif / #else  —— 检查常量表达式的值
 *   #if defined(X)       —— 等价于 #ifdef，但可以在 #if 中组合
 * ============================================================ */

/* === 5a. 平台检测 === */
#if defined(_WIN32) || defined(_WIN64)
    #define OS_NAME "Windows"
    #define PATH_SEPARATOR '\\'
    #define USE_WIN32_API 1
#elif defined(__linux__)
    #define OS_NAME "Linux"
    #define PATH_SEPARATOR '/'
    #define USE_POSIX_API 1
#elif defined(__APPLE__)
    #define OS_NAME "macOS"
    #define PATH_SEPARATOR '/'
    #define USE_POSIX_API 1
#else
    #define OS_NAME "Unknown"
    #define PATH_SEPARATOR '/'
#endif

/* === 5b. 编译器检测 === */
#if defined(__GNUC__) && !defined(__clang__)
    #define COMPILER_NAME "GCC"
    #define COMPILER_VERSION (__GNUC__ * 10000 + __GNUC_MINOR__ * 100 + __GNUC_PATCHLEVEL__)
#elif defined(__clang__)
    #define COMPILER_NAME "Clang"
    #define COMPILER_VERSION (__clang_major__ * 10000 + __clang_minor__ * 100 + __clang_patchlevel__)
#elif defined(_MSC_VER)
    #define COMPILER_NAME "MSVC"
    #define COMPILER_VERSION _MSC_VER
#else
    #define COMPILER_NAME "Unknown"
    #define COMPILER_VERSION 0
#endif

/* === 5c. 调试/发布模式 === */
#ifndef NDEBUG
    #define DEBUG_MODE 1
    #define LOG(msg) printf("[DEBUG %s:%d] %s\n", __FILE__, __LINE__, msg)
#else
    #define DEBUG_MODE 0
    #define LOG(msg)  /* 在发布模式下，LOG宏展开为空 */
#endif

/* === 5d. 特性开关 === */
#define ENABLE_FEATURE_A  1
#define ENABLE_FEATURE_B  0
#define ENABLE_FEATURE_C  1

/* ============================================================
 * 6. 预定义宏
 *
 * C标准和编译器扩展提供了一系列预定义宏，无需手动定义:
 *
 *   __FILE__        当前源文件名
 *   __LINE__        当前行号
 *   __func__        当前函数名 (C99)
 *   __DATE__        编译日期 (如 "Jun  5 2026")
 *   __TIME__        编译时间 (如 "14:30:00")
 *   __STDC__        是否符合ISO C标准 (通常为1)
 *   __STDC_VERSION__ C标准版本 (C99=199901L, C11=201112L, C17=201710L)
 *
 * GCC扩展预定义宏:
 *   __GNUC__        GCC主版本号
 *   __GNUC_MINOR__  GCC次版本号
 *   __OPTIMIZE__    是否开启了优化 (-O1及以上)
 *   __x86_64__      目标架构是否为x86-64
 *   __SIZEOF_INT__  int的字节数
 * ============================================================ */

/* 通用的断言宏（显示文件名、行号、函数名） */
#define ASSERT(cond)                                              \
    do {                                                          \
        if (!(cond)) {                                            \
            fprintf(stderr, "Assertion failed: %s\n"              \
                    "  in file: %s\n"                             \
                    "  at line: %d\n"                             \
                    "  in func: %s\n",                            \
                    #cond, __FILE__, __LINE__, __func__);         \
        }                                                         \
    } while (0)

/* 带条件的编译器消息 */
#define COMPILER_MESSAGE(msg) _Pragma(#msg)

/* 统一的错误/警告报告宏 */
#define COMPILE_ERROR(msg)    "Error: " msg " at " __FILE__ ":" STRINGIFY_EXPAND(__LINE__)

/* ============================================================
 * 7. 可变参数宏 (Variadic Macros, C99)
 *
 * ...  接收可变数量的参数
 * __VA_ARGS__  代表所有可变参数
 *
 * ##__VA_ARGS__  (GCC扩展): 当可变参数为空时，
 *   去掉前面的逗号，避免语法错误。
 * ============================================================ */

/* 带日志级别的日志宏 */
#define LOG_FMT(level, fmt, ...) \
    printf("[" level " %s:%d] " fmt "\n", __FILE__, __LINE__, ##__VA_ARGS__)

#define LOG_INFO(fmt, ...)   LOG_FMT("INFO", fmt, ##__VA_ARGS__)
#define LOG_WARN(fmt, ...)   LOG_FMT("WARN", fmt, ##__VA_ARGS__)
#define LOG_ERROR(fmt, ...)  LOG_FMT("ERROR", fmt, ##__VA_ARGS__)

/* 简单的 printf 包装（无格式化参数版本） */
#define TRACE(msg) \
    printf("[TRACE %s:%d:%s] %s\n", __FILE__, __LINE__, __func__, msg)

/* ============================================================
 * 8. #undef 和 #pragma
 *
 * #undef  取消已定义的宏
 * #pragma 提供编译器特定的指令
 * ============================================================ */

/* 临时使用一个宏然后取消 */
#define TEMP_MACRO 42
/* ... 使用 TEMP_MACRO ... */
#undef TEMP_MACRO
/* 此后 TEMP_MACRO 不再有定义 */

/* 常见的 #pragma 指令 */
#pragma message("Compiling demo_preprocess.c")  /* MSVC: 编译时输出消息 */
                                               /* GCC: 需要 GCC 4.4+ */

/* 防止重复包含的常用模式（header guard）*/
#ifndef DEMO_PREPROCESS_INCLUDED
#define DEMO_PREPROCESS_INCLUDED
/* 头文件内容放这里 */
#endif /* DEMO_PREPROCESS_INCLUDED */

/* ============================================================
 * 9. X-Macro 技术
 *
 * X-Macro是一种高级预处理器技巧，通过重复包含同一宏
 * 定义但改变宏的行为，来生成重复的代码模式。
 *
 * 典型用途:
 *   - 生成枚举和对应的字符串数组
 *   - 自动生成序列化/反序列化代码
 *   - 生成结构体字段的反射信息
 * ============================================================ */

/* X-Macro: 定义颜色列表 */
#define COLOR_LIST(X)   \
    X(RED,   0xFF0000)  \
    X(GREEN, 0x00FF00)  \
    X(BLUE,  0x0000FF)  \
    X(WHITE, 0xFFFFFF)  \
    X(BLACK, 0x000000)

/* 使用X-Macro生成枚举 */
#define GENERATE_ENUM(name, value) name = value,
typedef enum {
    COLOR_LIST(GENERATE_ENUM)
    COLOR_COUNT  /* 颜色数量（需要单独处理） */
} Color;
#undef GENERATE_ENUM

/* 使用X-Macro生成字符串表 */
#define GENERATE_STRING(name, value) #name,
static const char *color_names[] = {
    COLOR_LIST(GENERATE_STRING)
};
#undef GENERATE_STRING

/* 使用X-Macro生成十六进制值表 */
#define GENERATE_VALUE(name, value) value,
static const unsigned int color_values[] = {
    COLOR_LIST(GENERATE_VALUE)
};
#undef GENERATE_VALUE

/* ============================================================
 * 10. 辅助函数
 * ============================================================ */

/* 演示函数宏的副作用问题 */
void demo_macro_side_effects(void) {
    printf("\n=== Macro Side Effects Demo ===\n");

    int a = 5, b = 3;

    /* 正确使用: 无副作用 */
    printf("MAX(%d, %d) = %d\n", a, b, MAX(a, b));
    printf("SQUARE(%d) = %d\n", a, SQUARE(a));

    /* 副作用警告: i++ 会被求值多次 */
    int i = 5;
    printf("\nSide effect demo with MAX:\n");
    printf("  Before: i = %d\n", i);
    /* 下面的宏展开为: ((i++) > (b) ? (i++) : (b))
     * i++ 被求值两次! 结果可能出乎意料 */
    int result = MAX(i++, b);
    printf("  MAX(i++, %d) = %d, i = %d  (i was incremented twice!)\n",
           b, result, i);
    printf("  (Expected i=7 if both increments happen, or i=6 otherwise)\n");
}

/* 演示字符串化 */
void demo_stringification(void) {
    printf("\n=== Stringification Demo ===\n");

    /* 基本字符串化 */
    printf("STRINGIFY(Hello) = %s\n", STRINGIFY(Hello));
    printf("STRINGIFY(3 + 4) = %s\n", STRINGIFY(3 + 4));
    printf("STRINGIFY(PI)    = %s\n", STRINGIFY(PI));

    /* 展开后再字符串化 */
    int value = 42;
    printf("\nDEBUG_INT demo:\n");
    DEBUG_INT(value);
    DEBUG_INT(value * 2);
    DEBUG_INT(SQUARE(5));
}

/* 演示标记粘贴 */
void demo_token_pasting(void) {
    printf("\n=== Token Pasting Demo ===\n");

    /* 简单的标记粘贴 */
    int x1 = 10, x2 = 20, x3 = 30;
    printf("CONCAT(x, 1) = %d\n", CONCAT(x, 1));
    printf("CONCAT(x, 2) = %d\n", CONCAT(x, 2));
    printf("CONCAT(x, 3) = %d\n", CONCAT(x, 3));

    /* 生成的变量名 */
    int hello_world = 100;
    printf("MAKE_VAR(hello, world) = %d\n", MAKE_VAR(hello, world));

    /* 使用 ## 生成的访问器 */
    printf("\nGenerated accessors:\n");
    set_width(800);
    set_height(600);
    set_scale(2.5);
    printf("  get_width()  = %d\n", get_width());
    printf("  get_height() = %d\n", get_height());
    printf("  get_scale()  = %f\n", get_scale());
}

/* 演示预定义宏 */
void demo_predefined_macros(void) {
    printf("\n=== Predefined Macros Demo ===\n");
    printf("  __FILE__        = %s\n", __FILE__);
    printf("  __LINE__        = %d\n", __LINE__);
    printf("  __func__        = %s\n", __func__);
    printf("  __DATE__        = %s\n", __DATE__);
    printf("  __TIME__        = %s\n", __TIME__);
    printf("  __STDC__        = %d\n", __STDC__);

#ifdef __STDC_VERSION__
    printf("  __STDC_VERSION__ = %ldL\n", __STDC_VERSION__);
#else
    printf("  __STDC_VERSION__ = (not defined)\n");
#endif

    printf("  Compiler: %s\n", COMPILER_NAME);
    printf("  OS: %s\n", OS_NAME);
    printf("  Debug mode: %s\n", DEBUG_MODE ? "yes" : "no");

    /* 平台信息 */
#ifdef __SIZEOF_INT__
    printf("  sizeof(int) = %d bytes\n", __SIZEOF_INT__);
#endif
#ifdef __SIZEOF_POINTER__
    printf("  sizeof(void*) = %d bytes\n", __SIZEOF_POINTER__);
#endif
}

/* 演示X-Macro技术 */
void demo_x_macro(void) {
    printf("\n=== X-Macro Demo ===\n");

    /* 枚举值和颜色名称来自同一个X-Macro定义 */
    const char *names[] = {"RED", "GREEN", "BLUE", "WHITE", "BLACK"};
    unsigned int values[] = {0xFF0000, 0x00FF00, 0x0000FF, 0xFFFFFF, 0x000000};

    printf("  Color enum values:\n");
    for (int i = 0; i < 5; i++) {
        printf("    %-8s = 0x%06X  (enum: %d, table: %s, table_val: 0x%06X)\n",
               names[i], values[i],
               color_values[i],  /* 使用X-Macro生成的值表 */
               color_names[i],   /* 使用X-Macro生成的名称表 */
               color_values[i]);
    }
    printf("\n  Note: All tables (enum, name array, value array) are generated\n");
    printf("  from a single COLOR_LIST(X) macro definition!\n");
}

/* 演示条件编译 */
void demo_conditional_compilation(void) {
    printf("\n=== Conditional Compilation Demo ===\n");

    /* 平台信息 */
    printf("  Platform: %s\n", OS_NAME);
    printf("  Path separator: '%c'\n", PATH_SEPARATOR);

    /* 编译器信息 */
    printf("  Compiler: %s %d\n", COMPILER_NAME, COMPILER_VERSION);

    /* 特性开关 */
    printf("  Feature A: %s\n", ENABLE_FEATURE_A ? "enabled" : "disabled");
    printf("  Feature B: %s\n", ENABLE_FEATURE_B ? "enabled" : "disabled");
    printf("  Feature C: %s\n", ENABLE_FEATURE_C ? "enabled" : "disabled");

#if ENABLE_FEATURE_A && ENABLE_FEATURE_C
    printf("  Both A and C are enabled -> special code path\n");
#elif ENABLE_FEATURE_A
    printf("  Only A is enabled\n");
#endif
}

/* ============================================================
 * 11. 主函数
 * ============================================================ */

int main(void) {
    printf("=== C Preprocessor Features Demo ===\n");
    printf("Compiled by: %s\n", COMPILER_NAME);
    printf("Date: %s %s\n\n", __DATE__, __TIME__);

    /* 基本宏 */
    printf("=== Object Macros ===\n");
    printf("  BUFFER_SIZE = %d\n", BUFFER_SIZE);
    printf("  PI = %.15f\n", PI);
    printf("  GREETING = %s\n", GREETING);

    /* 函数宏 */
    printf("\n=== Function Macros ===\n");
    printf("  SQUARE(7) = %d\n", SQUARE(7));
    printf("  CUBE(3) = %d\n", CUBE(3));
    printf("  ABS(-42) = %d\n", ABS(-42));
    printf("  MIN(10, 20) = %d\n", MIN(10, 20));
    printf("  MAX(10, 20) = %d\n", MAX(10, 20));
    printf("  CLAMP(15, 0, 10) = %d\n", CLAMP(15, 0, 10));

    /* 括号的重要性 */
    int a = 2, b = 3;
    printf("\n  Parentheses matter:\n");
    printf("    AVERAGE_BAD  of %d,%d = %d  (wrong: should be %d)\n",
           a, b, AVERAGE_BAD, ((a) + (b)) / 2);
    /* AVERAGE_BAD 展开为: a + b / 2 = 2 + 3/2 = 2 + 1 = 3
     * 而不是 (2+3)/2 = 2 */

    /* 各种演示 */
    demo_macro_side_effects();
    demo_stringification();
    demo_token_pasting();
    demo_predefined_macros();
    demo_x_macro();
    demo_conditional_compilation();

    /* LOG宏（带可变参数） */
    printf("\n=== Variadic Macros Demo ===\n");
    LOG_INFO("Application started");
    LOG_WARN("Memory usage at %d%%", 75);
    LOG_ERROR("File not found: %s", "config.ini");
    TRACE("Entering main loop");

    /* 断言演示 */
    printf("\n=== Assert Demo ===\n");
    ASSERT(1 + 1 == 2);   /* 通过 */
    ASSERT(2 * 3 == 6);   /* 通过 */

    printf("\n=== Preprocessor demo complete ===\n");
    return 0;
}
