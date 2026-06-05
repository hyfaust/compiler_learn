# fibonacci.asm
# 斐波那契数列计算程序
# 使用栈式虚拟机汇编语言编写
# 计算斐波那契数列的第n项
#
# 使用方法：作为stack_vm.py的测试程序

# 主程序入口
# 计算斐波那契数列的第10项

# 设置参数 n = 10
ICONST 10
CALL fibonacci
PRINT
HALT

# 斐波那契函数定义
# 参数: n (栈顶)
# 返回值: fibonacci(n)
.function fibonacci 1 3
# 局部变量:
#   0: n (参数)
#   1: 临时变量 (保存n)
#   2: 临时变量 (保存fib(n-1))

# 检查基础情况: n <= 1
LOAD 0
ICONST 1
ICMP_LE
JMP_IF_FALSE recursive_case

# 基础情况: 返回 n
LOAD 0
RETURN

recursive_case:
# 递归情况: fibonacci(n-1) + fibonacci(n-2)

# 保存 n 到局部变量1
LOAD 0
STORE 1

# 计算 fibonacci(n-1)
LOAD 1
ICONST 1
ISUB
CALL fibonacci
STORE 2  # 保存 fibonacci(n-1) 到局部变量2

# 计算 fibonacci(n-2)
LOAD 1
ICONST 2
ISUB
CALL fibonacci

# 相加 fibonacci(n-1) + fibonacci(n-2)
LOAD 2
IADD
RETURN

.end fibonacci