// factorial.tl —— 阶乘计算
// 展示递归、条件判断和数学运算。

// 递归阶乘
func factorial(n) {
    if n <= 1 {
        return 1;
    }
    return n * factorial(n - 1);
}

// 尾递归优化版本（虽然 TinyLang 不做尾递归优化，但展示写法）
func factorial_tail(n, acc) {
    if n <= 1 {
        return acc;
    }
    return factorial_tail(n - 1, n * acc);
}

print("=== 阶乘表 ===");
let i = 0;
while i <= 12 {
    let result = factorial(i);
    let result2 = factorial_tail(i, 1);
    print(str(i) + "! = " + str(result) + " (尾递归: " + str(result2) + ")");
    i = i + 1;
}

// 组合数 C(n, k) = n! / (k! * (n-k)!)
func combination(n, k) {
    if k > n {
        return 0;
    }
    if k == 0 or k == n {
        return 1;
    }
    return factorial(n) / (factorial(k) * factorial(n - k));
}

print("");
print("=== 帕斯卡三角形（前10行） ===");
let row = 0;
while row < 10 {
    let line = "";
    let col = 0;
    while col <= row {
        line = line + str(combination(row, col)) + " ";
        col = col + 1;
    }
    print(line);
    row = row + 1;
}
