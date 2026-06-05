// sorting.tl —— 排序算法
// 展示数组操作、嵌套循环和算法实现。

// 冒泡排序
func bubble_sort(arr) {
    let n = len(arr);
    let i = 0;
    while i < n - 1 {
        let j = 0;
        while j < n - i - 1 {
            if arr[j] > arr[j + 1] {
                let temp = arr[j];
                arr[j] = arr[j + 1];
                arr[j + 1] = temp;
            }
            j = j + 1;
        }
        i = i + 1;
    }
    return arr;
}

// 选择排序
func selection_sort(arr) {
    let n = len(arr);
    let i = 0;
    while i < n - 1 {
        let min_idx = i;
        let j = i + 1;
        while j < n {
            if arr[j] < arr[min_idx] {
                min_idx = j;
            }
            j = j + 1;
        }
        if min_idx != i {
            let temp = arr[i];
            arr[i] = arr[min_idx];
            arr[min_idx] = temp;
        }
        i = i + 1;
    }
    return arr;
}

// 线性搜索
func linear_search(arr, target) {
    let i = 0;
    while i < len(arr) {
        if arr[i] == target {
            return i;
        }
        i = i + 1;
    }
    return -1;
}

// 测试排序
print("=== 冒泡排序 ===");
let data1 = [64, 34, 25, 12, 22, 11, 90];
print("排序前: " + str(data1));
let sorted1 = bubble_sort(data1);
print("排序后: " + str(sorted1));

print("");
print("=== 选择排序 ===");
let data2 = [64, 34, 25, 12, 22, 11, 90];
print("排序前: " + str(data2));
let sorted2 = selection_sort(data2);
print("排序后: " + str(sorted2));

print("");
print("=== 搜索测试 ===");
let target = 22;
let index = linear_search(sorted1, target);
print("在排序数组中搜索 " + str(target) + ": 索引 = " + str(index));

let target2 = 99;
let index2 = linear_search(sorted1, target2);
print("在排序数组中搜索 " + str(target2) + ": 索引 = " + str(index2));
