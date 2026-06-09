# 编译器与解释器学习项目

[English](README.md) | [简体中文](README_zh.md)

---

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9+-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

> 一个全面的、动手实践的编译器与解释器学习项目 —— 从理论到构建自己的编程语言。

## 目录

- [项目简介](#项目简介)
- [章节概览](#章节概览)
- [环境要求](#环境要求)
- [项目结构](#项目结构)
- [使用方法](#使用方法)
- [Web 阅读器](#web-阅读器)
- [项目亮点](#项目亮点)
- [参与贡献](#参与贡献)
- [许可证](#许可证)

## 项目简介

本项目是一个结构化的 12 章课程，带你从编译器和解释器设计的基础知识出发，一路走到构建一门完整的编程语言 —— **TinyLang** —— 它拥有自己的词法分析器、语法分析器、编译器和虚拟机。

每一章都包含：

- **详细的 Markdown 文档**，解释关键概念、数据结构和算法
- **可运行的示例代码**，涵盖 Python、C、JavaScript 和 x86 汇编
- **实践演示**，使用 GCC/MinGW、LuaJIT、CPython 和 V8 等真实工具

## 章节概览

| # | 章节 | 主题 |
|---|------|------|
| 01 | [编译器与解释器概述](01_compiler_interpreter_overview/) | 什么是编译器？什么是解释器？关键区别，编译流水线 |
| 02 | [编译器架构](02_compiler_architecture/) | GCC 编译阶段、预处理、符号表、AST 结构 |
| 03 | [词法分析](03_lexical_analysis/) | 分词、正则表达式、NFA/DFA 构造、词法分析器实现 |
| 04 | [语法分析](04_syntax_analysis/) | 上下文无关文法、递归下降解析、运算符优先级、AST 构造 |
| 05 | [语义分析与中间表示](05_semantic_analysis_and_ir/) | 类型检查、符号解析、三地址码、SSA 形式、Cytron 算法 |
| 06 | [优化](06_optimization/) | 控制流图构造、常量折叠/传播、死代码消除、公共子表达式消除、循环不变代码外提 |
| 07 | [代码生成](07_code_generation/) | x86 汇编、寄存器分配（线性扫描）、调用约定、栈帧 |
| 08 | [解释器架构](08_interpreter_architecture/) | 树遍历解释器、字节码虚拟机、CPython 字节码内部机制 |
| 09 | [虚拟机与字节码](09_vm_and_bytecode/) | 栈式虚拟机、寄存器式虚拟机、垃圾回收、指令设计 |
| 10 | [JIT 编译](10_jit_compilation/) | 方法级 JIT、追踪 JIT、内联缓存、隐藏类、性能基准测试 |
| 11 | [LuaJIT 源码分析](11_luajit_source_analysis/) | LuaJIT 字节码、IR、trace 录制、NaN tagging、增量式 GC |
| 12 | [构建自己的语言](12_build_your_own/) | 完整的 TinyLang 实现：词法分析 → 语法分析 → 编译器 → 虚拟机，含 91 个单元测试 |

## 环境要求

| 依赖 | 版本 | 是否必需 |
|------|------|----------|
| Python | >= 3.9 | 是 |
| GCC / MinGW | 任意近期版本 | 否（仅第 02 章 C 示例需要） |
| LuaJIT | >= 2.1 | 否（仅第 11 章 Lua 示例需要） |

## 项目结构

```
compiler_learn/
├── 01_compiler_interpreter_overview/   # 编译器与解释器入门
│   ├── README.md
│   ├── example.c                       # 编译与解释对比演示
│   ├── example.py
│   └── example.js
├── 02_compiler_architecture/           # GCC 内部机制与编译器阶段
│   ├── README.md
│   ├── demo_gcc_stages.c               # GCC 编译流水线演示
│   ├── demo_preprocess.c               # 预处理指令演示
│   ├── symbol_table.c                  # 符号表实现
│   └── ast_example.c                   # 抽象语法树演示
├── 03_lexical_analysis/                # 分词与 DFA 构造
│   ├── README.md
│   ├── lexer.py                        # 完整的词法分析器实现
│   ├── regex_to_dfa.py                 # 正则表达式 → NFA → DFA 流水线
│   └── test_lexer.c                    # C 词法分析器测试文件
├── 04_syntax_analysis/                 # 解析与 AST 构造
│   ├── README.md
│   ├── parser.py                       # 递归下降解析器
│   ├── ast_visualizer.py               # AST 图形化可视化
│   └── test_parser.c                   # C 语法分析器测试文件
├── 05_semantic_analysis_and_ir/        # 类型检查与中间表示
│   ├── README.md
│   ├── semantic_analyzer.py            # 类型检查器与作用域解析
│   ├── ir_generator.py                 # 三地址码生成器
│   └── ssa_converter.py               # SSA 形式转换（Cytron 算法）
├── 06_optimization/                    # 编译器优化遍
│   ├── README.md
│   ├── cfg_builder.py                  # 控制流图构造
│   ├── optimizer.py                    # 常量折叠、死代码消除、公共子表达式消除
│   ├── loop_optimizer.py               # 循环不变代码外提与循环优化
│   └── test_optimization.c             # C 优化测试文件
├── 07_code_generation/                 # 目标代码生成
│   ├── README.md
│   ├── code_generator.py               # IR → x86 汇编生成器
│   ├── calling_convention_demo.c       # 调用约定示例
│   └── simple_asm.asm                  # x86 汇编示例
├── 08_interpreter_architecture/        # 解释器设计模式
│   ├── README.md
│   ├── tree_walker.py                  # 树遍历解释器（含 REPL）
│   ├── bytecode_vm.py                  # 字节码编译器 + 虚拟机
│   └── python_bytecode_demo.py         # CPython 字节码反汇编
├── 09_vm_and_bytecode/                 # 虚拟机内部机制
│   ├── README.md
│   ├── stack_vm.py                     # 栈式虚拟机
│   ├── register_vm.py                  # 寄存器式虚拟机
│   ├── gc_demo.py                      # 垃圾回收可视化
│   └── fibonacci.asm                   # 汇编斐波那契实现
├── 10_jit_compilation/                 # JIT 编译技术
│   ├── README.md
│   ├── jit_compiler.py                 # 简单 JIT 编译器演示
│   ├── trace_jit.py                    # 追踪 JIT 实现
│   ├── inline_cache_demo.py            # 内联缓存与隐藏类
│   └── benchmark.py                    # 性能基准测试套件
├── 11_luajit_source_analysis/          # LuaJIT 深度分析
│   ├── README.md
│   ├── bytecode_inspector.lua          # LuaJIT 字节码分析
│   ├── trace_analysis.lua              # trace 录制分析
│   └── lj_source_map.md               # LuaJIT 源码结构图
├── 12_build_your_own/                  # 从零构建 TinyLang
│   ├── README.md
│   ├── tinylang.py                     # 一体化编译器（1043 行）
│   ├── tinylang_interpreter.py         # 树遍历解释器（487 行）
│   ├── tinylang_compiler.py            # 字节码编译器 + 虚拟机（555 行）
│   ├── tinylang/                       # 模块化包实现
│   │   ├── __init__.py
│   │   ├── lexer.py
│   │   ├── parser.py
│   │   ├── ast_nodes.py
│   │   ├── compiler.py
│   │   ├── vm.py
│   │   ├── environment.py
│   │   ├── builtins.py
│   │   ├── errors.py
│   │   ├── opcodes.py
│   │   └── main.py
│   ├── examples/                       # TinyLang 示例程序
│   │   ├── fibonacci.tl
│   │   ├── closures.tl
│   │   ├── sorting.tl
│   │   └── ...
│   └── tests/
│       └── test_tinylang.py            # 91 个单元测试
├── luajit/                             # LuaJIT 源代码（参考）
├── index.html                          # 基于 Web 的文档阅读器
├── style.css
├── app.js
├── chapters.js
└── LICENSE                             # GPL v3 许可证
```

## 使用方法

### 阅读文档

每个章节文件夹都包含一个 `README.md`，其中有详细的概念解释。建议从第 01 章开始，按顺序阅读。

### 运行示例

```bash
# Python 示例（大多数章节）
python 03_lexical_analysis/lexer.py
python 05_semantic_analysis_and_ir/ir_generator.py
python 09_vm_and_bytecode/stack_vm.py

# TinyLang - 编译并运行
python 12_build_your_own/tinylang.py --run 12_build_your_own/examples/fibonacci.tl

# TinyLang - 交互式解释器模式
python 12_build_your_own/tinylang_interpreter.py

# 运行 TinyLang 单元测试（91 个测试）
python 12_build_your_own/tests/test_tinylang.py

# JIT 性能基准测试
python 10_jit_compilation/benchmark.py
```

### C 示例（需要 GCC/MinGW）

```bash
# 编译并运行 C 示例
gcc 02_compiler_architecture/demo_gcc_stages.c -o demo && ./demo
gcc 02_compiler_architecture/symbol_table.c -o symtab && ./symtab
```

## Web 阅读器

项目内置了一个 Web 阅读器，提供整洁的暗色主题阅读体验：

```bash
# 在浏览器中打开
start index.html          # Windows
open index.html            # macOS
xdg-open index.html       # Linux
```

功能特性：
- 为长时间阅读优化的暗色主题
- 代码块语法高亮（由 highlight.js 提供支持）
- Markdown 渲染（由 marked.js 提供支持）
- 章节导航侧边栏

## 项目亮点

- **12 个章节**，覆盖完整的编译器/解释器流水线
- **可运行的示例** —— 每个代码文件都经过测试并可正常运行
- **91 个单元测试**，覆盖 TinyLang 实现
- **多范式示例** —— Python、C、JavaScript、x86 汇编、Lua
- **真实工具参考** —— GCC、MinGW、LuaJIT、CPython、V8
- **Web 阅读器**，提供舒适的文档浏览体验
- **完整的语言实现** —— TinyLang 支持变量、函数、闭包、数组、控制流和高阶函数

## 参与贡献

欢迎参与贡献！以下是几种方式：

1. **报告问题** —— 发现 Bug 或不清楚的解释？请提交 Issue。
2. **改进文档** —— 更好的解释、修正错别字、添加图示。
3. **添加示例** —— 更多演示关键概念的代码示例。
4 **修复 Bug** —— 检查测试结果并修复失败的用例。

请确保在提交前所有 Python 示例都能无错误运行。

## 许可证

本项目基于 [GNU 通用公共许可证 v3.0](LICENSE) 授权。

你可以在 GPL v3 许可证的条款下自由使用、修改和分发本软件。完整的许可证文本请参阅 [LICENSE](LICENSE) 文件。
