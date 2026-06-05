// hello.tl —— TinyLang 入门示例
// 这是最简单的 TinyLang 程序，展示基本语法。

// 打印问候语
print("Hello, TinyLang!");
print("欢迎来到编程语言的世界！");

// 变量声明与基本运算
let name = "TinyLang";
let version = 1;
let pi = 3.14;

print("语言: " + name);
print("版本: " + str(version));
print("圆周率: " + str(pi));

// 布尔值与逻辑运算
let is_fun = true;
let is_easy = true;
let should_learn = is_fun and is_easy;
print("应该学习 TinyLang 吗? " + str(should_learn));

// 数组
let fruits = ["苹果", "香蕉", "橘子"];
print("水果列表: " + str(fruits));
print("第一个水果: " + fruits[0]);
print("水果数量: " + str(len(fruits)));
