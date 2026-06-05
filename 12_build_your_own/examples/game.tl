// game.tl —— 猜数字游戏
// 展示综合运用：函数、循环、条件判断、数组。

print("================================");
print("   猜数字游戏 (TinyLang版)");
print("================================");
print("");

// 简单的伪随机数生成器（线性同余法）
let _seed = 42;

func srand(s) {
    _seed = s;
}

func rand() {
    // LCG: seed = (seed * 1103515245 + 12345) % 2^31
    _seed = (_seed * 1103515245 + 12345) % 2147483647;
    if _seed < 0 {
        _seed = 0 - _seed;
    }
    return _seed;
}

func random_range(min_val, max_val) {
    return min_val + (rand() % (max_val - min_val + 1));
}

// 生成目标数字
let secret = random_range(1, 100);
print("我已经想好了一个 1 到 100 之间的数字。");
print("你有 7 次机会来猜它！");
print("");

// 模拟猜测过程（因为 TinyLang 没有用户输入，我们用预设的猜测）
let guesses = [50, 75, 60, 65, 63, 64, 62];
let attempts = 7;
let won = false;
let i = 0;

while i < attempts and not won {
    let guess = guesses[i];
    print("第 " + str(i + 1) + " 次猜测: " + str(guess));

    if guess == secret {
        print("恭喜你猜对了！答案就是 " + str(secret) + "！");
        won = true;
    } elif guess < secret {
        print("太小了！");
    } else {
        print("太大了！");
    }
    i = i + 1;
}

if not won {
    print("很遗憾，机会用完了。答案是 " + str(secret) + "。");
}

// 二分搜索猜数字（AI 策略）
print("");
print("=== AI 二分搜索策略 ===");

func binary_search_guess(min_val, max_val, target) {
    let low = min_val;
    let high = max_val;
    let count = 0;
    let found = false;

    while low <= high and not found {
        let mid = low + (high - low) / 2;
        count = count + 1;

        if mid == target {
            print("  第 " + str(count) + " 次: 猜 " + str(mid) + " -> 命中！");
            found = true;
        } elif mid < target {
            print("  第 " + str(count) + " 次: 猜 " + str(mid) + " -> 太小");
            low = mid + 1;
        } else {
            print("  第 " + str(count) + " 次: 猜 " + str(mid) + " -> 太大");
            high = mid - 1;
        }
    }

    return count;
}

let target = 73;
print("目标数字: " + str(target));
print("范围: 1-100");
let ai_count = binary_search_guess(1, 100, target);
print("AI 共用了 " + str(ai_count) + " 次找到答案。");
print("（理论上最多需要 " + str(7) + " 次）");

// 成绩统计系统
print("");
print("=== 成绩统计系统 ===");

let scores = [85, 92, 78, 96, 88, 73, 91, 82, 95, 87];

func average(arr) {
    let sum = 0;
    let i = 0;
    while i < len(arr) {
        sum = sum + arr[i];
        i = i + 1;
    }
    return sum / len(arr);
}

func find_max(arr) {
    let max_val = arr[0];
    let i = 1;
    while i < len(arr) {
        if arr[i] > max_val {
            max_val = arr[i];
        }
        i = i + 1;
    }
    return max_val;
}

func find_min(arr) {
    let min_val = arr[0];
    let i = 1;
    while i < len(arr) {
        if arr[i] < min_val {
            min_val = arr[i];
        }
        i = i + 1;
    }
    return min_val;
}

func count_above(arr, threshold) {
    let count = 0;
    let i = 0;
    while i < len(arr) {
        if arr[i] >= threshold {
            count = count + 1;
        }
        i = i + 1;
    }
    return count;
}

print("成绩列表: " + str(scores));
print("平均分:   " + str(average(scores)));
print("最高分:   " + str(find_max(scores)));
print("最低分:   " + str(find_min(scores)));
print("90分以上: " + str(count_above(scores, 90)) + " 人");
print("80分以上: " + str(count_above(scores, 80)) + " 人");
print("不及格:   " + str(len(scores) - count_above(scores, 60)) + " 人");
