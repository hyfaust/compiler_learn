/**
 * 调用约定演示 (Calling Convention Demo)
 * =======================================
 *
 * 本文件演示 C 语言中各种调用约定的使用方式和行为差异。
 *
 * 编译方式：
 *   32位: gcc -m32 -O0 -o demo32 calling_convention_demo.c
 *   64位: gcc -O0 -o demo64 calling_convention_demo.c
 *
 * 注意：
 *   - __cdecl, __stdcall, __fastcall 是 Windows/MSVC 扩展
 *   - GCC 中使用 __attribute__((cdecl)) 等来指定
 *   - 本示例在 Windows + MinGW/MSVC 环境下编译最佳
 */

#include <stdio.h>
#include <stdarg.h>
#include <string.h>

/* ============================================================
 * 1. cdecl 调用约定（C 默认）
 * ============================================================
 *
 * 特点：
 *   - 参数从右到左压栈
 *   - 调用者清理栈
 *   - 支持变参函数（因为调用者知道压了多少参数）
 *   - 返回值在 EAX/RAX 中
 *
 * 栈布局（32位）：
 *
 *   高地址
 *   ┌──────────────────┐
 *   │  arg N (最右)     │  [EBP + 8 + 4*(N-1)]
 *   │  ...              │
 *   │  arg 2            │  [EBP + 12]
 *   │  arg 1 (最左)     │  [EBP + 8]
 *   ├──────────────────┤
 *   │  返回地址          │  [EBP + 4]
 *   ├──────────────────┤
 *   │  保存的 EBP       │  [EBP]  ← EBP 指向这里
 *   ├──────────────────┤
 *   │  局部变量          │  [EBP - 4], [EBP - 8], ...
 *   └──────────────────┘  ← ESP
 *   低地址
 */

#ifdef _WIN32
/* Windows: 显式指定 cdecl */
int __cdecl add_cdecl(int a, int b, int c)
#else
/* Linux/macOS: 默认就是 cdecl */
int add_cdecl(int a, int b, int c)
#endif
{
    int result = a + b + c;
    printf("  cdecl: add(%d, %d, %d) = %d\n", a, b, c, result);
    return result;
}

/* 调用 cdecl 函数时，编译器生成的代码大致如下（32位 x86）：
 *
 *   ; 调用 add_cdecl(1, 2, 3)
 *   pushl $3          ; 第3个参数（从右到左压栈）
 *   pushl $2          ; 第2个参数
 *   pushl $1          ; 第1个参数
 *   call  add_cdecl
 *   addl  $12, %esp   ; 调用者清理栈（3 × 4 = 12 字节）
 *
 * 注意：call 指令会自动压入返回地址
 */


/* ============================================================
 * 2. stdcall 调用约定（Win32 API 默认）
 * ============================================================
 *
 * 与 cdecl 的区别：
 *   - 由被调用者（callee）清理栈
 *   - 函数返回时使用 RET n 指令
 *   - 不支持变参函数（因为被调用者必须知道清理多少字节）
 *
 * 栈布局与 cdecl 相同，区别仅在于栈清理方。
 */

#ifdef _WIN32
int __stdcall add_stdcall(int a, int b, int c)
#else
int __attribute__((stdcall)) add_stdcall(int a, int b, int c)
#endif
{
    int result = a + b + c;
    printf("  stdcall: add(%d, %d, %d) = %d\n", a, b, c, result);
    return result;
}

/* 调用 stdcall 函数时，编译器生成的代码大致如下（32位 x86）：
 *
 *   ; 调用 add_stdcall(1, 2, 3)
 *   pushl $3
 *   pushl $2
 *   pushl $1
 *   call  add_stdcall
 *   ; 注意：没有 addl $12, %esp
 *   ; 因为被调用者会在 ret 12 中清理栈
 *
 * add_stdcall 函数尾声：
 *   movl  %ebp, %esp
 *   popl  %ebp
 *   ret   $12          ; 返回并清理 12 字节参数空间
 */


/* ============================================================
 * 3. fastcall 调用约定
 * ============================================================
 *
 * 特点（32位 Windows 版本）：
 *   - 前两个整数参数通过 ECX 和 EDX 传递
 *   - 其余参数通过栈传递（从右到左）
 *   - 被调用者清理栈上参数
 *
 * 特点（64位 Windows 版本）：
 *   - 前4个整数参数通过 RCX, RDX, R8, R9 传递
 *   - 这其实就是 Windows x64 的默认约定
 */

#ifdef _WIN32
int __fastcall add_fastcall(int a, int b, int c)
#else
int __attribute__((fastcall)) add_fastcall(int a, int b, int c)
#endif
{
    int result = a + b + c;
    printf("  fastcall: add(%d, %d, %d) = %d\n", a, b, c, result);
    return result;
}

/* 调用 fastcall(1, 2, 3) 时，编译器生成的代码大致如下（32位 x86）：
 *
 *   pushl $3          ; 第3个参数通过栈
 *   movl  $2, %edx    ; 第2个参数通过 EDX
 *   movl  $1, %ecx    ; 第1个参数通过 ECX
 *   call  add_fastcall
 *   ; 栈由被调用者清理（ret $4，只清理栈上的1个参数）
 */


/* ============================================================
 * 4. 变参函数（Variadic Functions）与 cdecl
 * ============================================================
 *
 * 变参函数（如 printf）必须使用 cdecl 约定，因为：
 *   - 调用者知道传递了多少个参数
 *   - 只有调用者能正确清理栈
 *   - 被调用者无法知道参数数量
 */

/**
 * 变参求和函数：使用 va_list 处理可变数量的参数。
 *
 * @param count  参数个数
 * @param ...    要求和的整数
 * @return 所有参数的总和
 */
#ifdef _WIN32
int __cdecl variadic_sum(int count, ...)
#else
int variadic_sum(int count, ...)
#endif
{
    va_list args;
    int sum = 0;

    /* va_start: 初始化 va_list，指向 count 之后的参数 */
    va_start(args, count);

    /* 逐个取出参数并累加 */
    for (int i = 0; i < count; i++) {
        int val = va_arg(args, int);  /* 取出下一个 int 参数 */
        sum += val;
    }

    /* va_end: 清理 va_list */
    va_end(args);

    printf("  variadic_sum(%d args): ", count);
    printf("sum = %d\n", sum);
    return sum;
}

/* 变参函数的工作原理（32位 x86）：
 *
 * 调用 variadic_sum(3, 10, 20, 30)：
 *
 *   pushl $30          ; 第4个参数（栈顶 → 最后取到）
 *   pushl $20          ; 第3个参数
 *   pushl $10          ; 第2个参数
 *   pushl $3           ; 第1个参数 count
 *   call  variadic_sum
 *   addl  $16, %esp    ; 调用者清理栈
 *
 * 在 variadic_sum 内部：
 *   va_start(args, count)  → args 指向 count 后面的地址
 *                             即 args = &count + sizeof(int)
 *   va_arg(args, int)      → 读取 *(int*)args，然后 args += sizeof(int)
 *
 * 栈布局：
 *   高地址
 *   ┌──────────┐
 *   │ 30       │  args 第3次指向这里 → val = 30
 *   ├──────────┤
 *   │ 20       │  args 第2次指向这里 → val = 20
 *   ├──────────┤
 *   │ 10       │  args 第1次指向这里 → val = 10
 *   ├──────────┤
 *   │ count=3  │  va_start 从这里之后开始
 *   ├──────────┤
 *   │ 返回地址  │
 *   ├──────────┤
 *   │ 保存的EBP │
 *   └──────────┘
 */


/* ============================================================
 * 5. 64 位调用约定对比
 * ============================================================
 *
 * === Windows x64 ===
 *   整数参数: RCX, RDX, R8, R9
 *   浮点参数: XMM0, XMM1, XMM2, XMM3
 *   返回值: RAX
 *   Shadow space: 调用者预留 32 字节
 *   栈清理: 调用者
 *
 * === System V AMD64 ABI (Linux/macOS) ===
 *   整数参数: RDI, RSI, RDX, RCX, R8, R9
 *   浮点参数: XMM0-XMM7
 *   返回值: RAX (整数), XMM0 (浮点)
 *   Red zone: RSP 下 128 字节 (叶子函数可用)
 *   栈清理: 调用者
 *
 * 关键区别：
 *   1. 参数寄存器不同 (RCX vs RDI 作为第1个参数)
 *   2. Windows 有 shadow space，Linux 有 red zone
 *   3. Linux 支持更多浮点参数寄存器 (8个 vs 4个)
 */

/* 以下函数展示64位参数传递 */
long add_many_args(long a, long b, long c, long d, long e, long f, long g)
{
    /*
     * 64位 Linux (System V):
     *   a → RDI, b → RSI, c → RDX, d → RCX, e → R8, f → R9, g → 栈
     *
     * 64位 Windows:
     *   a → RCX, b → RDX, c → R8, d → R9, e → 栈, f → 栈, g → 栈
     *   （前4个在寄存器，后面全部在栈上）
     */
    long result = a + b + c + d + e + f + g;
    printf("  add_many_args: %ld + %ld + %ld + %ld + %ld + %ld + %ld = %ld\n",
           a, b, c, d, e, f, g, result);
    return result;
}


/* ============================================================
 * 6. 函数指针与调用约定
 * ============================================================
 *
 * 函数指针类型必须匹配调用约定，否则会导致栈损坏！
 */

/* 定义不同调用约定的函数指针类型 */
typedef int (__cdecl    *CdeclFunc)(int, int);
typedef int (__stdcall *StdcallFunc)(int, int);

/* cdecl 版本 */
int __cdecl multiply_cdecl(int a, int b) {
    return a * b;
}

/* stdcall 版本 */
int __stdcall multiply_stdcall(int a, int b) {
    return a * b;
}

/**
 * 通过函数指针调用，演示调用约定必须匹配。
 *
 * 错误示例（会导致栈损坏！）：
 *   StdcallFunc fp = (StdcallFunc)multiply_cdecl;  // 错误！
 *   fp(3, 4);  // stdcall 期望 callee 清理栈，但 cdecl 不会清理
 */
void demonstrate_function_pointers(void)
{
    /* 正确使用：调用约定匹配 */
    CdeclFunc fp_cdecl = multiply_cdecl;
    StdcallFunc fp_stdcall = multiply_stdcall;

    printf("  cdecl:    multiply(3, 4) = %d\n", fp_cdecl(3, 4));
    printf("  stdcall:  multiply(3, 4) = %d\n", fp_stdcall(3, 4));

    /*
     * 错误用法（取消注释会导致未定义行为）：
     *
     * StdcallFunc bad_fp = (StdcallFunc)multiply_cdecl;
     * bad_fp(3, 4);
     *
     * 为什么是未定义行为？
     *   - stdcall 调用者不会清理栈参数
     *   - 但 multiply_cdecl (cdecl) 也不会清理（它认为调用者会清理）
     *   - 结果：栈上残留4字节垃圾，ESP 不正确
     *   - 后续代码会读到错误的栈数据，导致崩溃
     */
}


/* ============================================================
 * 7. 结构体参数传递与返回
 * ============================================================
 *
 * 不同调用约定对结构体的处理方式不同：
 *   - 小结构体（≤ 8 字节在 x64 上）可能通过寄存器传递
 *   - 大结构体通过栈传递（或传递指针）
 *   - System V ABI 有更复杂的分类规则（INTEGER, SSE, MEMORY 类）
 */

typedef struct {
    int x;
    int y;
} Point;

/* 按值传递结构体（在栈上复制整个结构体） */
Point make_point(int x, int y)
{
    Point p;
    p.x = x;
    p.y = y;
    printf("  make_point(%d, %d) → {%d, %d}\n", x, y, p.x, p.y);
    return p;
}

/* 按值传递结构体参数 */
int point_distance_squared(Point p1, Point p2)
{
    int dx = p1.x - p2.x;
    int dy = p1.y - p2.y;
    int dist2 = dx * dx + dy * dy;
    printf("  dist2({%d,%d}, {%d,%d}) = %d\n", p1.x, p1.y, p2.x, p2.y, dist2);
    return dist2;
}

/*
 * 结构体在 64 位系统上的传递：
 *
 * System V AMD64 ABI：
 *   sizeof(Point) = 8 字节 → 可以放入一个寄存器
 *   编译器会将 Point 打包到 RDI/RSI 中传递
 *
 * Windows x64：
 *   结构体即使很小，也可能通过栈传递（取决于编译器优化级别）
 *   或者调用者在 shadow space 中传递
 */


/* ============================================================
 * 8. 内联汇编查看栈帧（GCC 语法）
 * ============================================================
 *
 * 使用内联汇编可以在运行时查看寄存器和栈的值。
 * 注意：不同编译器的内联汇编语法不同。
 */

#if defined(__GNUC__) && (defined(__i386__) || defined(__x86_64__))

/**
 * 打印当前栈指针和帧指针的值。
 * 仅在 GCC + x86/x86-64 上可用。
 */
void print_stack_info(void)
{
    void *sp, *bp;

#if defined(__x86_64__)
    /* x86-64: 使用 RSP 和 RBP */
    __asm__ __volatile__(
        "movq %%rsp, %0\n\t"
        "movq %%rbp, %1\n\t"
        : "=r"(sp), "=r"(bp)
        :
        : "memory"
    );
    printf("  [x64] RSP = %p, RBP = %p, frame size ≈ %ld bytes\n",
           sp, bp, (long)((char*)bp - (char*)sp));
#else
    /* x86-32: 使用 ESP 和 EBP */
    __asm__ __volatile__(
        "movl %%esp, %0\n\t"
        "movl %%ebp, %1\n\t"
        : "=r"(sp), "=r"(bp)
        :
        : "memory"
    );
    printf("  [x86] ESP = %p, EBP = %p, frame size ≈ %d bytes\n",
           sp, bp, (int)((char*)bp - (char*)sp));
#endif
}

/**
 * 读取调用者传递的参数（从栈上）。
 * 仅在 32 位模式下有意义（64 位参数主要在寄存器中）。
 */
void inspect_arguments(int a, int b, int c)
{
    printf("  inspect_arguments: a=%d, b=%d, c=%d\n", a, b, c);
    print_stack_info();

#if defined(__i386__)
    /* 在 32 位 cdecl 下，参数在栈上：
     *   [EBP + 8]  = a
     *   [EBP + 12] = b
     *   [EBP + 16] = c
     */
    int stack_a, stack_b, stack_c;
    __asm__ __volatile__(
        "movl 8(%%ebp), %0\n\t"
        "movl 12(%%ebp), %1\n\t"
        "movl 16(%%ebp), %2\n\t"
        : "=r"(stack_a), "=r"(stack_b), "=r"(stack_c)
        :
        : "memory"
    );
    printf("  [x86] 从栈上读取: a=%d, b=%d, c=%d\n", stack_a, stack_b, stack_c);
#else
    printf("  [x64] 参数在寄存器中，无法直接从栈上读取\n");
#endif
}

#endif /* GCC + x86/x86-64 */


/* ============================================================
 * 9. 调用约定对比总结表
 * ============================================================
 *
 * ┌────────────┬──────────────┬──────────────┬──────────────┐
 * │            │   cdecl      │   stdcall    │   fastcall   │
 * ├────────────┼──────────────┼──────────────┼──────────────┤
 * │ 参数传递    │ 全部通过栈    │ 全部通过栈    │ ECX,EDX+栈   │
 * │ 参数顺序    │ 右→左        │ 右→左        │ 右→左(栈部分) │
 * │ 栈清理      │ 调用者        │ 被调用者      │ 被调用者      │
 * │ 变参支持    │ ✓            │ ✗            │ ✗            │
 * │ 返回值      │ EAX          │ EAX          │ EAX          │
 * │ 名称修饰    │ _name        │ _name@N      │ @name@N      │
 * │ 平台        │ 通用          │ Win32 API    │ Windows      │
 * └────────────┴──────────────┴──────────────┴──────────────┘
 *
 * 64 位调用约定：
 * ┌────────────┬─────────────────────┬─────────────────────┐
 * │            │ Windows x64         │ System V AMD64      │
 * ├────────────┼─────────────────────┼─────────────────────┤
 * │ 整数参数    │ RCX,RDX,R8,R9      │ RDI,RSI,RDX,RCX,R8,R9│
 * │ 浮点参数    │ XMM0-3             │ XMM0-7              │
 * │ 返回值      │ RAX, XMM0          │ RAX,RDX, XMM0,XMM1  │
 * │ Shadow     │ 32字节              │ 无                   │
 * │ Red Zone   │ 无                  │ 128字节              │
 * │ 栈对齐      │ 16字节              │ 16字节               │
 * │ 栈清理      │ 调用者              │ 调用者               │
 * └────────────┴─────────────────────┴─────────────────────┘
 */


/* ============================================================
 * 主函数：运行所有演示
 * ============================================================ */

int main(void)
{
    printf("========================================\n");
    printf("  调用约定演示 (Calling Convention Demo)\n");
    printf("========================================\n\n");

    /* 1. cdecl */
    printf("[1] cdecl 调用约定\n");
    add_cdecl(1, 2, 3);
    printf("\n");

    /* 2. stdcall */
    printf("[2] stdcall 调用约定\n");
    add_stdcall(1, 2, 3);
    printf("\n");

    /* 3. fastcall */
    printf("[3] fastcall 调用约定\n");
    add_fastcall(1, 2, 3);
    printf("\n");

    /* 4. 变参函数 */
    printf("[4] 变参函数（va_list）\n");
    variadic_sum(3, 10, 20, 30);
    variadic_sum(5, 1, 2, 3, 4, 5);
    printf("\n");

    /* 5. 多参数（展示64位寄存器 vs 栈） */
    printf("[5] 多参数函数（64位参数传递）\n");
    add_many_args(1, 2, 3, 4, 5, 6, 7);
    printf("\n");

    /* 6. 函数指针 */
    printf("[6] 函数指针与调用约定\n");
    demonstrate_function_pointers();
    printf("\n");

    /* 7. 结构体传递 */
    printf("[7] 结构体参数传递\n");
    Point p1 = make_point(3, 4);
    Point p2 = make_point(0, 0);
    point_distance_squared(p1, p2);
    printf("\n");

    /* 8. 内联汇编查看栈帧 */
#if defined(__GNUC__) && (defined(__i386__) || defined(__x86_64__))
    printf("[8] 内联汇编查看栈帧信息\n");
    print_stack_info();
    inspect_arguments(100, 200, 300);
    printf("\n");
#endif

    printf("========================================\n");
    printf("  演示结束\n");
    printf("========================================\n");

    return 0;
}
