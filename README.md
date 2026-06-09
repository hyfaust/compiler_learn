# Compiler & Interpreter Learning

[English](README.md) | [简体中文](README_zh.md)

---

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9+-green.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey.svg)]()

> A comprehensive, hands-on learning project covering compilers and interpreters — from theory to building your own language.

## Table of Contents

- [Introduction](#introduction)
- [Chapters Overview](#chapters-overview)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Usage](#usage)
- [Web Reader](#web-reader)
- [Highlights](#highlights)
- [Contributing](#contributing)
- [License](#license)

## Introduction

This project is a structured, 12-chapter curriculum that takes you from the fundamentals of compiler and interpreter design all the way to building a complete programming language — **TinyLang** — with its own lexer, parser, compiler, and virtual machine.

Each chapter includes:

- **Detailed Markdown documentation** explaining key concepts, data structures, and algorithms
- **Runnable example code** in Python, C, JavaScript, and x86 assembly
- **Practical demonstrations** using real-world tools like GCC/MinGW, LuaJIT, CPython, and V8

## Chapters Overview

| # | Chapter | Topics |
|---|---------|--------|
| 01 | [Compiler & Interpreter Overview](01_compiler_interpreter_overview/) | What is a compiler? What is an interpreter? Key differences, compilation pipeline |
| 02 | [Compiler Architecture](02_compiler_architecture/) | GCC compilation stages, preprocessing, symbol tables, AST structure |
| 03 | [Lexical Analysis](03_lexical_analysis/) | Tokenization, regular expressions, NFA/DFA construction, lexer implementation |
| 04 | [Syntax Analysis](04_syntax_analysis/) | Context-free grammars, recursive descent parsing, operator precedence, AST construction |
| 05 | [Semantic Analysis & IR](05_semantic_analysis_and_ir/) | Type checking, symbol resolution, three-address code, SSA form, Cytron algorithm |
| 06 | [Optimization](06_optimization/) | CFG construction, constant folding/propagation, dead code elimination, CSE, LICM |
| 07 | [Code Generation](07_code_generation/) | x86 assembly, register allocation (linear scan), calling conventions, stack frames |
| 08 | [Interpreter Architecture](08_interpreter_architecture/) | Tree-walk interpreter, bytecode VM, CPython bytecode internals |
| 09 | [VM & Bytecode](09_vm_and_bytecode/) | Stack-based VM, register-based VM, garbage collection, instruction design |
| 10 | [JIT Compilation](10_jit_compilation/) | Method JIT, tracing JIT, inline caches, hidden classes, performance benchmarks |
| 11 | [LuaJIT Source Analysis](11_luajit_source_analysis/) | LuaJIT bytecode, IR, trace recording, NaN tagging, incremental GC |
| 12 | [Build Your Own Language](12_build_your_own/) | Complete TinyLang implementation: lexer → parser → compiler → VM, with 91 unit tests |

## Prerequisites

| Dependency | Version | Required |
|------------|---------|----------|
| Python | >= 3.9 | Yes |
| GCC / MinGW | Any recent version | No (for Ch02 C examples) |
| LuaJIT | >= 2.1 | No (for Ch11 Lua examples) |

## Project Structure

```
compiler_learn/
├── 01_compiler_interpreter_overview/   # Introduction to compilers & interpreters
│   ├── README.md
│   ├── example.c                       # Compiled vs interpreted demo
│   ├── example.py
│   └── example.js
├── 02_compiler_architecture/           # GCC internals & compiler stages
│   ├── README.md
│   ├── demo_gcc_stages.c               # GCC compilation pipeline demo
│   ├── demo_preprocess.c               # Preprocessor directives demo
│   ├── symbol_table.c                  # Symbol table implementation
│   └── ast_example.c                   # Abstract syntax tree demo
├── 03_lexical_analysis/                # Tokenization & DFA construction
│   ├── README.md
│   ├── lexer.py                        # Complete lexer implementation
│   ├── regex_to_dfa.py                 # Regex → NFA → DFA pipeline
│   └── test_lexer.c                    # C lexer test file
├── 04_syntax_analysis/                 # Parsing & AST construction
│   ├── README.md
│   ├── parser.py                       # Recursive descent parser
│   ├── ast_visualizer.py               # AST graph visualization
│   └── test_parser.c                   # C parser test file
├── 05_semantic_analysis_and_ir/        # Type checking & intermediate representation
│   ├── README.md
│   ├── semantic_analyzer.py            # Type checker & scope resolver
│   ├── ir_generator.py                 # Three-address code generator
│   └── ssa_converter.py               # SSA form conversion (Cytron)
├── 06_optimization/                    # Compiler optimization passes
│   ├── README.md
│   ├── cfg_builder.py                  # Control flow graph construction
│   ├── optimizer.py                    # Constant folding, DCE, CSE
│   ├── loop_optimizer.py               # LICM & loop optimization
│   └── test_optimization.c             # C optimization test file
├── 07_code_generation/                 # Target code generation
│   ├── README.md
│   ├── code_generator.py               # IR → x86 assembly generator
│   ├── calling_convention_demo.c       # Calling convention examples
│   └── simple_asm.asm                  # x86 assembly examples
├── 08_interpreter_architecture/        # Interpreter design patterns
│   ├── README.md
│   ├── tree_walker.py                  # Tree-walk interpreter (with REPL)
│   ├── bytecode_vm.py                  # Bytecode compiler + VM
│   └── python_bytecode_demo.py         # CPython bytecode disassembly
├── 09_vm_and_bytecode/                 # Virtual machine internals
│   ├── README.md
│   ├── stack_vm.py                     # Stack-based virtual machine
│   ├── register_vm.py                  # Register-based virtual machine
│   ├── gc_demo.py                      # Garbage collection visualization
│   └── fibonacci.asm                   # Assembly Fibonacci implementation
├── 10_jit_compilation/                 # JIT compilation techniques
│   ├── README.md
│   ├── jit_compiler.py                 # Simple JIT compiler demo
│   ├── trace_jit.py                    # Tracing JIT implementation
│   ├── inline_cache_demo.py            # Inline cache & hidden classes
│   └── benchmark.py                    # Performance benchmark suite
├── 11_luajit_source_analysis/          # LuaJIT deep dive
│   ├── README.md
│   ├── bytecode_inspector.lua          # LuaJIT bytecode analysis
│   ├── trace_analysis.lua              # Trace recording analysis
│   └── lj_source_map.md               # LuaJIT source code map
├── 12_build_your_own/                  # Build TinyLang from scratch
│   ├── README.md
│   ├── tinylang.py                     # All-in-one compiler (1043 lines)
│   ├── tinylang_interpreter.py         # Tree-walk interpreter (487 lines)
│   ├── tinylang_compiler.py            # Bytecode compiler + VM (555 lines)
│   ├── tinylang/                       # Modular package implementation
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
│   ├── examples/                       # TinyLang example programs
│   │   ├── fibonacci.tl
│   │   ├── closures.tl
│   │   ├── sorting.tl
│   │   └── ...
│   └── tests/
│       └── test_tinylang.py            # 91 unit tests
├── luajit/                             # LuaJIT source code (reference)
├── index.html                          # Web-based document reader
├── style.css
├── app.js
├── chapters.js
└── LICENSE                             # GPL v3 License
```

## Usage

### Reading the Documentation

Each chapter folder contains a `README.md` with detailed explanations. Start from Chapter 01 and work through sequentially.

### Running Examples

```bash
# Python examples (most chapters)
python 03_lexical_analysis/lexer.py
python 05_semantic_analysis_and_ir/ir_generator.py
python 09_vm_and_bytecode/stack_vm.py

# TinyLang - compile and run
python 12_build_your_own/tinylang.py --run 12_build_your_own/examples/fibonacci.tl

# TinyLang - interactive interpreter mode
python 12_build_your_own/tinylang_interpreter.py

# Run TinyLang unit tests (91 tests)
python 12_build_your_own/tests/test_tinylang.py

# JIT benchmark suite
python 10_jit_compilation/benchmark.py
```

### C Examples (requires GCC/MinGW)

```bash
# Compile and run C examples
gcc 02_compiler_architecture/demo_gcc_stages.c -o demo && ./demo
gcc 02_compiler_architecture/symbol_table.c -o symtab && ./symtab
```

## Web Reader

A built-in web reader provides a clean, dark-themed reading experience for all chapters:

```bash
# Open in browser
start index.html          # Windows
open index.html            # macOS
xdg-open index.html       # Linux
```

Features:
- Dark theme optimized for long reading sessions
- Syntax-highlighted code blocks (powered by highlight.js)
- Markdown rendering (powered by marked.js)
- Chapter navigation sidebar

## Highlights

- **12 chapters** covering the full compiler/interpreter pipeline
- **Runnable examples** — every code file is tested and working
- **91 unit tests** for the TinyLang implementation
- **Multi-paradigm examples** — Python, C, JavaScript, x86 assembly, Lua
- **Real-world references** — GCC, MinGW, LuaJIT, CPython, V8
- **Web reader** for comfortable document browsing
- **Complete language implementation** — TinyLang supports variables, functions, closures, arrays, control flow, and higher-order functions

## Contributing

Contributions are welcome! Here's how you can help:

1. **Report issues** — Found a bug or unclear explanation? Open an issue.
2. **Improve documentation** — Better explanations, fix typos, add diagrams.
3. **Add examples** — More code examples demonstrating key concepts.
4. **Fix bugs** — Check the test results and fix any failing cases.

Please ensure all Python examples run without errors before submitting.

## License

This project is licensed under the [GNU General Public License v3.0](LICENSE).

You are free to use, modify, and distribute this software under the terms of the GPL v3 license. See the [LICENSE](LICENSE) file for the full text.
