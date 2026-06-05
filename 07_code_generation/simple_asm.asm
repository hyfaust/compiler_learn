; ============================================================
; 简单 x86 汇编示例（NASM 语法）
; ============================================================
;
; 本文件演示 x86 汇编的基本指令和常用模式。
; 使用 NASM (Netwide Assembler) 语法。
;
; 编译和链接（Linux 32位）：
;   nasm -f elf32 -o simple_asm.o simple_asm.asm
;   ld -m elf_i386 -o simple_asm simple_asm.o
;
; 编译和链接（Windows 32位 + MinGW）：
;   nasm -f win32 -o simple_asm.obj simple_asm.asm
;   gcc -m32 -o simple_asm.exe simple_asm.obj
;
; 编译和链接（macOS 32位）：
;   nasm -f macho -o simple_asm.o simple_asm.asm
;   ld -macosx_version_min 10.7 -o simple_asm simple_asm.o -lSystem
;
; 注意：现代 macOS 已不支持 32 位。
;       本示例以 Linux 32 位为主要目标平台。
;
; ============================================================


; ============================================================
;  第1节：数据段 — 定义已初始化数据
; ============================================================

section .data

; ---- 字符串定义 ----
; 0xA = 换行符 (LF), 0x0 = 字符串结束符
msg_hello       db  "Hello, x86 Assembly!", 0xA, 0
msg_hello_len   equ $ - msg_hello               ; $ 表示当前地址，自动计算长度

msg_add         db  "ADD result: ", 0
msg_add_len     equ $ - msg_add

msg_loop        db  "Loop iteration: ", 0
msg_loop_len    equ $ - msg_loop

msg_done        db  "Done!", 0xA, 0
msg_done_len    equ $ - msg_done

msg_newline     db  0xA, 0
msg_newline_len equ $ - msg_newline

; ---- 数值数据 ----
; db = define byte (1字节)
; dw = define word (2字节)
; dd = define doubleword (4字节)
; dq = define quadword (8字节)

byte_val        db  42
word_val        dw  1000
dword_val       dd  123456

; ---- 数组定义 ----
array           dd  10, 20, 30, 40, 50          ; 5个32位整数
array_len       equ ($ - array) / 4              ; 数组长度 = 总字节数 / 4


; ============================================================
;  第2节：BSS段 — 定义未初始化数据（零初始化）
; ============================================================

section .bss

buffer          resb 64                          ; 预留64字节缓冲区
result_buf      resb 16                          ; 用于数字转字符串的缓冲区


; ============================================================
;  第3节：代码段
; ============================================================

section .text

; 全局入口点
global _start


; ============================================================
;  _start — 程序入口
; ============================================================

_start:
    ; ──────────────────────────────────
    ; 演示1：基本数据移动指令
    ; ──────────────────────────────────
    call demo_mov

    ; ──────────────────────────────────
    ; 演示2：算术指令
    ; ──────────────────────────────────
    call demo_arithmetic

    ; ──────────────────────────────────
    ; 演示3：逻辑指令和位操作
    ; ──────────────────────────────────
    call demo_logic

    ; ──────────────────────────────────
    ; 演示4：比较和条件跳转
    ; ──────────────────────────────────
    call demo_comparison

    ; ──────────────────────────────────
    ; 演示5：循环结构
    ; ──────────────────────────────────
    call demo_loop

    ; ──────────────────────────────────
    ; 演示6：函数调用和栈帧
    ; ──────────────────────────────────
    call demo_function_call

    ; ──────────────────────────────────
    ; 演示7：栈操作
    ; ──────────────────────────────────
    call demo_stack

    ; ──────────────────────────────────
    ; 演示8：数组遍历
    ; ──────────────────────────────────
    call demo_array

    ; ──────────────────────────────────
    ; 退出程序
    ; ──────────────────────────────────
    mov  eax, 1          ; 系统调用号 1 = sys_exit (Linux)
    xor  ebx, ebx        ; 退出码 0
    int  0x80             ; 触发系统调用


; ============================================================
;  演示1：基本数据移动指令
; ============================================================
;
; MOV 指令是最常用的指令，用于在寄存器、内存、立即数之间传输数据。
;
; 格式：MOV 目标, 源
;
; 合法的 MOV 组合：
;   MOV reg, imm        ; 立即数 → 寄存器
;   MOV reg, reg        ; 寄存器 → 寄存器
;   MOV reg, [mem]      ; 内存 → 寄存器
;   MOV [mem], reg      ; 寄存器 → 内存
;   MOV [mem], imm      ; 立即数 → 内存
;
; 非法的 MOV：
;   MOV [mem], [mem]    ; 不能内存到内存（必须通过寄存器中转）
;   MOV cs, ...         ; 段寄存器有特殊限制
;
; LEA 指令：计算地址但不访问内存
;   LEA reg, [addr]     ; reg = addr 的计算结果
;   常用于算术：LEA eax, [ebx + ecx*4 + 8] 等价于 eax = ebx + ecx*4 + 8

demo_mov:
    ; --- 立即数到寄存器 ---
    mov  eax, 42             ; eax = 42
    mov  ebx, 0xFF           ; ebx = 255
    mov  ecx, 0x12345678     ; ecx = 305419896

    ; --- 寄存器到寄存器 ---
    mov  edx, eax             ; edx = eax = 42

    ; --- 寄存器到内存 ---
    mov  [result_buf], eax    ; 将 eax 的值存入 result_buf

    ; --- 内存到寄存器 ---
    mov  esi, [dword_val]     ; esi = 123456（从 .data 段加载）

    ; --- 不同大小的移动 ---
    mov  al, [byte_val]       ; al = 42（8位）
    mov  ax, [word_val]       ; ax = 1000（16位）

    ; --- LEA 指令（地址计算，不访问内存）---
    mov  ebx, 10
    mov  ecx, 3
    lea  eax, [ebx + ecx*4]  ; eax = 10 + 3*4 = 22
                              ; 注意：这里不是读取内存地址22的值，
                              ; 而是计算表达式的结果

    ; --- MOVZX / MOVSX（零扩展/符号扩展）---
    mov  bl, 0xFF             ; bl = 255 (0xFF)
    movzx eax, bl             ; eax = 0x000000FF（零扩展，eax = 255）

    mov  cl, 0xFF             ; cl = -1 (有符号)
    movsx edx, cl             ; edx = 0xFFFFFFFF（符号扩展，edx = -1）

    ret


; ============================================================
;  演示2：算术指令
; ============================================================
;
; x86 算术指令会修改 EFLAGS 标志寄存器：
;   ZF (零标志)   — 结果为0时置1
;   SF (符号标志)  — 结果为负数时置1
;   CF (进位标志)  — 无符号溢出时置1
;   OF (溢出标志)  — 有符号溢出时置1

demo_arithmetic:
    ; --- ADD（加法）---
    mov  eax, 100
    mov  ebx, 50
    add  eax, ebx             ; eax = 100 + 50 = 150
    ; 此时 EFLAGS 被更新

    ; --- SUB（减法）---
    sub  eax, 30              ; eax = 150 - 30 = 120

    ; --- INC / DEC（自增/自减）---
    inc  eax                  ; eax = 121（不修改 CF 标志！）
    dec  eax                  ; eax = 120（不修改 CF 标志！）

    ; --- IMUL（有符号乘法）---
    ; 单操作数形式：EDX:EAX = EAX * operand
    mov  eax, 7
    mov  ebx, 6
    imul ebx                  ; EDX:EAX = 7 * 6 = 42
                              ; EDX = 0（高32位），EAX = 42（低32位）

    ; 双操作数形式：dest = dest * src
    mov  eax, 10
    imul eax, ebx             ; eax = 10 * 6 = 60

    ; 三操作数形式：dest = src * imm
    imul ecx, eax, 3          ; ecx = 60 * 3 = 180

    ; --- IDIV（有符号除法）---
    ; 单操作数：EAX = EDX:EAX / operand, EDX = EDX:EAX % operand
    ; 注意：必须先将 EAX 符号扩展到 EDX:EAX（用 CDQ 指令）
    mov  eax, 100
    cdq                       ; EAX 符号扩展到 EDX:EAX（如果 EAX >= 0，则 EDX = 0）
    mov  ebx, 7
    idiv ebx                  ; EAX = 100 / 7 = 14, EDX = 100 % 7 = 2
                              ; 100 = 14 * 7 + 2

    ; --- NEG（取反）---
    mov  eax, 42
    neg  eax                  ; eax = -42 (0xFFFFFFD6)

    ret


; ============================================================
;  演示3：逻辑指令和位操作
; ============================================================

demo_logic:
    ; --- AND（按位与）---
    mov  eax, 0b11001100      ; 0xCC
    and  eax, 0b10101010      ; 0xAA
    ; 结果：eax = 0b10001000 = 0x88

    ; 常用技巧：AND 用于掩码（清除特定位）
    mov  eax, 0xFF
    and  eax, 0x0F            ; 只保留低4位，eax = 0x0F

    ; --- OR（按位或）---
    mov  eax, 0b11000000
    or   eax, 0b00000011      ; eax = 0b11000011

    ; 常用技巧：OR 用于设置特定位
    mov  eax, 0x00
    or   eax, 0x01            ; 设置最低位

    ; --- XOR（按位异或）---
    mov  eax, 0b11001100
    xor  eax, 0b11111111      ; eax = 0b00110011（翻转所有位）

    ; 常用技巧：XOR 自身 = 清零
    xor  eax, eax             ; eax = 0（比 mov eax, 0 更短更快）

    ; --- NOT（按位取反）---
    mov  eax, 0
    not  eax                  ; eax = 0xFFFFFFFF

    ; --- SHL / SHR（逻辑左移/右移）---
    mov  eax, 1
    shl  eax, 4               ; eax = 1 << 4 = 16
    shr  eax, 2               ; eax = 16 >> 2 = 4

    ; 移位量可以是立即数或 CL 寄存器
    mov  cl, 3
    mov  eax, 10
    shl  eax, cl              ; eax = 10 << 3 = 80

    ; --- SAR（算术右移，保留符号位）---
    mov  eax, -16             ; 0xFFFFFFF0
    sar  eax, 2               ; eax = -4 (0xFFFFFFFC)
                              ; 算术右移用符号位填充高位

    ; --- TEST（按位与，但不存储结果，只设置标志）---
    mov  eax, 0x05
    test eax, 0x01            ; 测试最低位是否为1
    ; ZF = 0（结果非零），所以最低位是1
    ; 常用于：test eax, eax 来检查 eax 是否为零

    ret


; ============================================================
;  演示4：比较和条件跳转
; ============================================================
;
; CMP 指令执行减法但不存储结果，只更新 EFLAGS。
; 条件跳转指令根据 EFLAGS 决定是否跳转。
;
; 常用条件跳转：
;   JE / JZ      — 等于 / 零       (ZF=1)
;   JNE / JNZ    — 不等于 / 非零    (ZF=0)
;   JG / JNLE    — 大于（有符号）    (ZF=0 且 SF=OF)
;   JL / JNGE    — 小于（有符号）    (SF!=OF)
;   JGE / JNL    — 大于等于（有符号） (SF=OF)
;   JLE / JNG    — 小于等于（有符号） (ZF=1 或 SF!=OF)
;   JA / JNBE    — 大于（无符号）    (CF=0 且 ZF=0)
;   JB / JNAE    — 小于（无符号）    (CF=1)

demo_comparison:
    ; --- 简单的 if-else 结构 ---
    ; 伪代码：if (eax > ebx) then ecx = 1; else ecx = 0;

    mov  eax, 10
    mov  ebx, 20

    cmp  eax, ebx             ; 比较 eax 和 ebx（计算 eax - ebx）
    jg   .greater             ; 如果 eax > ebx，跳转
    ; else 分支
    mov  ecx, 0               ; ecx = 0（eax <= ebx）
    jmp  .cmp_done
.greater:
    mov  ecx, 1               ; ecx = 1（eax > ebx）
.cmp_done:
    ; 此时 ecx = 0（因为 10 < 20）

    ; --- 三路分支（if / else if / else）---
    ; 伪代码：
    ;   if (eax == 0)       → edx = 100
    ;   else if (eax > 0)   → edx = 200
    ;   else                → edx = 300

    mov  eax, -5
    cmp  eax, 0
    je   .is_zero             ; eax == 0?
    jg   .is_positive         ; eax > 0?
    ; else: eax < 0
    mov  edx, 300
    jmp  .three_way_done
.is_zero:
    mov  edx, 100
    jmp  .three_way_done
.is_positive:
    mov  edx, 200
.three_way_done:
    ; 此时 edx = 300（因为 eax = -5 < 0）

    ; --- 无符号比较 ---
    mov  eax, 0xFFFFFFFF      ; 无符号 = 4294967295, 有符号 = -1
    mov  ebx, 1

    ; 有符号比较：-1 < 1
    cmp  eax, ebx
    jl   .signed_less         ; 会跳转（有符号 -1 < 1）

    ; 无符号比较：4294967295 > 1
    cmp  eax, ebx
    ja   .unsigned_greater    ; 会跳转（无符号 4294967295 > 1）

.signed_less:
.unsigned_greater:
    ; 两条都会跳转到这里

    ; --- TEST + JZ 检查奇偶 ---
    mov  eax, 42
    test eax, 1               ; 检查最低位
    jz   .is_even             ; 如果最低位为0，是偶数
    ; odd
    jmp  .parity_done
.is_even:
    ; eax 是偶数
.parity_done:

    ret


; ============================================================
;  演示5：循环结构
; ============================================================
;
; x86 没有专门的高级循环指令，循环通过 条件跳转 实现。
; 但有一个 LOOP 指令：LOOP label 等价于 DEC ECX + JNZ label
; （不推荐使用 LOOP，因为它比手动实现慢）

demo_loop:
    ; ─── 示例1：基本 while 循环 ───
    ; 伪代码：
    ;   int i = 0;
    ;   int sum = 0;
    ;   while (i < 10) {
    ;       sum += i;
    ;       i++;
    ;   }

    xor  eax, eax             ; i = 0
    xor  ebx, ebx             ; sum = 0

.loop_while:
    cmp  eax, 10              ; i < 10?
    jge  .loop_while_end      ; 如果 i >= 10，退出循环

    add  ebx, eax             ; sum += i
    inc  eax                  ; i++

    jmp  .loop_while           ; 继续循环
.loop_while_end:
    ; 此时 ebx = 0+1+2+...+9 = 45

    ; ─── 示例2：do-while 循环 ───
    ; 伪代码：
    ;   int count = 5;
    ;   do {
    ;       count--;
    ;   } while (count > 0);

    mov  ecx, 5

.loop_dowhile:
    dec  ecx                  ; count--

    test ecx, ecx             ; count == 0?
    jnz  .loop_dowhile        ; 如果不为零，继续

    ; ─── 示例3：for 循环（倒序）───
    ; 伪代码：
    ;   for (int i = 10; i > 0; i--) { ... }

    mov  ecx, 10              ; i = 10

.loop_for:
    test ecx, ecx             ; i == 0?
    jz   .loop_for_end        ; 退出

    ; 循环体（这里为空）

    dec  ecx                  ; i--
    jmp  .loop_for
.loop_for_end:

    ret


; ============================================================
;  演示6：函数调用和栈帧
; ============================================================
;
; CALL 指令：
;   1. 将返回地址压入栈（ESP -= 4, [ESP] = 返回地址）
;   2. 跳转到目标地址
;
; RET 指令：
;   1. 从栈顶弹出返回地址（EIP = [ESP], ESP += 4）
;   2. 跳转到返回地址
;
; 标准栈帧管理：
;   函数序言（Prologue）：
;     push ebp          ; 保存调用者的帧指针
;     mov  ebp, esp     ; 建立新帧指针
;     sub  esp, N       ; 为局部变量分配空间
;
;   函数尾声（Epilogue）：
;     mov  ebp, esp     ; 或 leave（等价于 mov esp, ebp + pop ebp）
;     pop  ebp          ; 恢复调用者的帧指针
;     ret

demo_function_call:
    ; ─── 调用 add_numbers(30, 12) ───
    ; cdecl 调用约定：参数从右到左压栈，调用者清理栈

    push 12                   ; 第2个参数（右）
    push 30                   ; 第1个参数（左）
    call add_numbers           ; 调用函数（返回值在 eax 中）
    add  esp, 8               ; 调用者清理栈（2个参数 × 4字节）
    ; 此时 eax = 30 + 12 = 42

    ; ─── 调用 factorial(5) ───
    push 5                    ; 参数 n = 5
    call factorial
    add  esp, 4               ; 清理栈
    ; 此时 eax = 5! = 120

    ; ─── 调用 swap_and_add ───
    ; 展示通过栈传递指针（按引用传递）
    mov  eax, 100
    mov  ebx, 200
    push eax                  ; 传递 a 的值
    push ebx                  ; 传递 b 的值
    call swap_and_add
    add  esp, 8
    ; eax = 300 (100 + 200)

    ret


; ============================================================
;  add_numbers — 两数相加（简单函数示例）
; ============================================================
; 参数：
;   [ebp+8]  = 第1个参数 (a)
;   [ebp+12] = 第2个参数 (b)
; 返回值：
;   eax = a + b

add_numbers:
    push ebp                  ; 序言：保存帧指针
    mov  ebp, esp             ; 序言：建立新帧

    mov  eax, [ebp+8]         ; eax = a（第1个参数）
    add  eax, [ebp+12]        ; eax += b（第2个参数）

    pop  ebp                  ; 尾声：恢复帧指针
    ret                       ; 返回（返回值在 eax 中）


; ============================================================
;  factorial — 递归计算阶乘
; ============================================================
; 参数：
;   [ebp+8] = n
; 返回值：
;   eax = n!
;
; 递归栈帧示意（factorial(3)）：
;
;   factorial(3):
;     n=3, 调用 factorial(2)
;       factorial(2):
;         n=2, 调用 factorial(1)
;           factorial(1):
;             n=1, 返回 1
;           eax = 1
;         eax = 2 * 1 = 2
;       eax = 2
;     eax = 3 * 2 = 6

factorial:
    push ebp
    mov  ebp, esp

    mov  eax, [ebp+8]         ; eax = n

    ; 基本情况：n <= 1 时返回 1
    cmp  eax, 1
    jle  .fact_base           ; if (n <= 1) goto base_case

    ; 递归情况：return n * factorial(n-1)
    dec  eax                  ; eax = n - 1
    push eax                  ; 参数 = n - 1
    call factorial             ; eax = factorial(n-1)
    add  esp, 4               ; 清理参数

    ; eax = factorial(n-1)，需要乘以 n
    mov  ebx, [ebp+8]         ; ebx = n（原始参数）
    imul eax, ebx             ; eax = n * factorial(n-1)
    jmp  .fact_return

.fact_base:
    mov  eax, 1               ; 返回 1

.fact_return:
    pop  ebp
    ret


; ============================================================
;  swap_and_add — 演示栈上参数的操作
; ============================================================
; 参数：
;   [ebp+8]  = a
;   [ebp+12] = b
; 返回值：
;   eax = a + b（使用局部变量计算）

swap_and_add:
    push ebp
    mov  ebp, esp
    sub  esp, 8               ; 分配8字节局部变量空间

    ; 局部变量：
    ;   [ebp-4] = local_a
    ;   [ebp-8] = local_b

    mov  eax, [ebp+8]         ; eax = a
    mov  [ebp-4], eax         ; local_a = a

    mov  eax, [ebp+12]        ; eax = b
    mov  [ebp-8], eax         ; local_b = b

    ; 计算 local_a + local_b
    mov  eax, [ebp-4]
    add  eax, [ebp-8]         ; eax = local_a + local_b

    mov  esp, ebp              ; 释放局部变量（等价于 add esp, 8）
    pop  ebp
    ret


; ============================================================
;  演示7：栈操作
; ============================================================

demo_stack:
    ; ─── PUSH / POP 基本操作 ───
    ;
    ; PUSH reg/imm：
    ;   ESP -= 4
    ;   [ESP] = reg/imm
    ;
    ; POP reg：
    ;   reg = [ESP]
    ;   ESP += 4

    push eax                  ; 保存 eax
    push ebx                  ; 保存 ebx

    mov  eax, 111
    mov  ebx, 222

    ; 交换 eax 和 ebx（使用栈）
    push eax
    push ebx
    pop  eax                  ; eax = ebx 的旧值
    pop  ebx                  ; ebx = eax 的旧值
    ; 注意：这个交换方式要求 PUSH/POP 配对

    pop  ebx                  ; 恢复 ebx 的原始值
    pop  eax                  ; 恢复 eax 的原始值

    ; ─── PUSHAD / POPAD（保存/恢复所有通用寄存器）───
    ; PUSHAD 将 EAX, ECX, EDX, EBX, ESP, EBP, ESI, EDI 全部压栈
    ; POPAD  恢复它们
    ; 注意：这在 64 位模式下不可用

    pushad                    ; 保存所有寄存器
    ; ... 可以随意使用任何寄存器 ...
    mov  eax, 0xDEADBEEF
    mov  ecx, 0xCAFEBABE
    popad                     ; 恢复所有寄存器

    ret


; ============================================================
;  演示8：数组遍历
; ============================================================

demo_array:
    ; ─── 遍历数组并求和 ───
    ; 伪代码：
    ;   int sum = 0;
    ;   for (int i = 0; i < array_len; i++) {
    ;       sum += array[i];
    ;   }
    ; 预期结果：10 + 20 + 30 + 40 + 50 = 150

    xor  ebx, ebx             ; sum = 0
    xor  ecx, ecx             ; i = 0 (索引)
    mov  esi, array            ; esi = 数组基地址

.array_loop:
    cmp  ecx, array_len        ; i < array_len?
    jge  .array_done

    ; 计算 array[i] 的地址并加载
    ; array[i] 的地址 = array_base + i * 4
    mov  eax, [esi + ecx*4]   ; eax = array[i]
    add  ebx, eax             ; sum += array[i]

    inc  ecx                  ; i++
    jmp  .array_loop

.array_done:
    ; 此时 ebx = 150
    ; （可以用系统调用将结果打印出来，这里省略）

    ret
