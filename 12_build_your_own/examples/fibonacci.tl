// fibonacci.tl —— 斐波那契数列
// 展示循环和函数定义。

// 方法1：循环计算斐波那契数
print("=== 斐波那契数列（循环） ===");

let n = 20;
let a = 0;
let b = 1;
let i = 0;

while i < n {
    print("F(" + str(i) + ") = " + str(a));
    let temp = a + b;
    a = b;
    b = temp;
    i = i + 1;
}

// 方法2：递归计算（展示函数定义和递归）
print("");
print("=== 斐波那契数列（递归） ===");

func fibonacci(n) {
    if n <= 1 {
        return n;
    }
    return fibonacci(n - 1) + fibonacci(n - 2);
}

let j = 0;
while j < 15 {
    print("fib(" + str(j) + ") = " + str(fibonacci(j)));
    j = j + 1;
}
