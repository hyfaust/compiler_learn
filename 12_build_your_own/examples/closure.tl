// closure.tl —— 闭包示例
// 展示函数作为一等公民、闭包和高阶函数。

// 计数器工厂 —— 展示闭包捕获外部变量
func make_counter(start) {
    let count = start;
    func increment() {
        count = count + 1;
        return count;
    }
    return increment;
}

print("=== 计数器闭包 ===");
let counter1 = make_counter(0);
let counter2 = make_counter(100);

print("计数器1: " + str(counter1()));  // 1
print("计数器1: " + str(counter1()));  // 2
print("计数器1: " + str(counter1()));  // 3
print("计数器2: " + str(counter2()));  // 101
print("计数器2: " + str(counter2()));  // 102

// 累加器 —— 展示闭包的持久化状态
func make_accumulator(initial) {
    let total = initial;
    func add(value) {
        total = total + value;
        return total;
    }
    return add;
}

print("");
print("=== 累加器闭包 ===");
let acc = make_accumulator(0);
print("累加 10: " + str(acc(10)));   // 10
print("累加 20: " + str(acc(20)));   // 30
print("累加 5:  " + str(acc(5)));    // 35

// 函数作为参数 —— 对数组每个元素应用函数
func map_array(arr, callback) {
    let result = [];
    let i = 0;
    while i < len(arr) {
        result = append(result, callback(arr[i]));
        i = i + 1;
    }
    return result;
}

print("");
print("=== 高阶函数: map ===");
let numbers = [1, 2, 3, 4, 5];

let doubled = map_array(numbers, fn(x) { return x * 2; });
print("原数组: " + str(numbers));
print("翻倍:   " + str(doubled));

let squared = map_array(numbers, fn(x) { return x * x; });
print("平方:   " + str(squared));

// 函数式编程：filter
func filter_array(arr, predicate) {
    let result = [];
    let i = 0;
    while i < len(arr) {
        if predicate(arr[i]) {
            result = append(result, arr[i]);
        }
        i = i + 1;
    }
    return result;
}

print("");
print("=== 高阶函数: filter ===");
let is_even = fn(x) { return x % 2 == 0; };
let evens = filter_array(numbers, is_even);
print("原数组:     " + str(numbers));
print("偶数过滤:   " + str(evens));

let is_positive = fn(x) { return x > 0; };
let mixed = [-3, -1, 0, 2, 5, -7, 8];
let positives = filter_array(mixed, is_positive);
print("混合数组:   " + str(mixed));
print("正数过滤:   " + str(positives));

// reduce / fold
func reduce_array(arr, callback, initial) {
    let acc = initial;
    let i = 0;
    while i < len(arr) {
        acc = callback(acc, arr[i]);
        i = i + 1;
    }
    return acc;
}

print("");
print("=== 高阶函数: reduce ===");
let sum = reduce_array(numbers, fn(acc, x) { return acc + x; }, 0);
print("数组求和: " + str(sum));

let product = reduce_array(numbers, fn(acc, x) { return acc * x; }, 1);
print("数组求积: " + str(product));
