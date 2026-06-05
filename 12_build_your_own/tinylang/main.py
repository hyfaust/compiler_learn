"""
TinyLang —— 命令行入口

用法：
    # 交互式 REPL
    python -m tinylang.main

    # 执行文件（默认使用树遍历解释器）
    python -m tinylang.main examples/hello.tl

    # 查看 AST
    python -m tinylang.main --ast examples/hello.tl

    # 查看字节码
    python -m tinylang.main --bytecode examples/hello.tl

    # 使用虚拟机执行
    python -m tinylang.main --vm examples/hello.tl
"""

import sys
import os

# 确保可以从 tinylang 包外部运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tinylang.lexer import Lexer
from tinylang.parser import Parser
from tinylang.ast_nodes import ASTNode
from tinylang.interpreter import Interpreter
from tinylang.compiler import Compiler
from tinylang.vm import VM
from tinylang.opcodes import disassemble, CompiledFunction
from tinylang.builtins import get_builtins
from tinylang.errors import TinyLangError


# ============================================================
#  工具函数
# ============================================================

def tokenize_and_parse(source: str):
    """词法分析 + 语法分析，返回 AST"""
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    return ast


def format_ast_node(node, indent: int = 0) -> str:
    """将 AST 节点格式化为可读的树形字符串

    这是一个简单的递归格式化器，为每个节点生成
    类名和关键属性，用缩进表示层级关系。
    """
    prefix = "  " * indent
    cls_name = type(node).__name__

    # 处理 Program 节点
    if cls_name == "Program":
        lines = [f"{prefix}Program ("]
        for stmt in node.statements:
            lines.append(format_ast_node(stmt, indent + 1))
        lines.append(f"{prefix})")
        return "\n".join(lines)

    # 处理各种语句
    if cls_name == "LetStatement":
        lines = [f"{prefix}LetStatement(name={node.name!r},"]
        lines.append(format_ast_node(node.value, indent + 1))
        lines[-1] += ")"
        return "\n".join(lines)

    if cls_name == "AssignmentStatement":
        lines = [f"{prefix}AssignmentStatement("]
        lines.append(format_ast_node(node.target, indent + 1))
        lines.append(format_ast_node(node.value, indent + 1))
        lines.append(f"{prefix})")
        return "\n".join(lines)

    if cls_name == "ExpressionStatement":
        lines = [f"{prefix}ExpressionStatement("]
        lines.append(format_ast_node(node.expression, indent + 1))
        lines.append(f"{prefix})")
        return "\n".join(lines)

    if cls_name == "IfStatement":
        lines = [f"{prefix}IfStatement("]
        lines.append(f"{prefix}  condition=")
        lines.append(format_ast_node(node.condition, indent + 2))
        lines.append(f"{prefix}  then_body=[")
        for stmt in node.then_body:
            lines.append(format_ast_node(stmt, indent + 3))
        lines.append(f"{prefix}  ]")
        for elif_cond, elif_body in node.elif_clauses:
            lines.append(f"{prefix}  elif_cond=")
            lines.append(format_ast_node(elif_cond, indent + 2))
            lines.append(f"{prefix}  elif_body=[")
            for stmt in elif_body:
                lines.append(format_ast_node(stmt, indent + 3))
            lines.append(f"{prefix}  ]")
        if node.else_body:
            lines.append(f"{prefix}  else_body=[")
            for stmt in node.else_body:
                lines.append(format_ast_node(stmt, indent + 3))
            lines.append(f"{prefix}  ]")
        lines.append(f"{prefix})")
        return "\n".join(lines)

    if cls_name == "WhileStatement":
        lines = [f"{prefix}WhileStatement("]
        lines.append(format_ast_node(node.condition, indent + 1))
        for stmt in node.body:
            lines.append(format_ast_node(stmt, indent + 1))
        lines.append(f"{prefix})")
        return "\n".join(lines)

    if cls_name == "ForStatement":
        lines = [f"{prefix}ForStatement(var={node.var_name!r},"]
        lines.append(format_ast_node(node.iterable, indent + 1))
        for stmt in node.body:
            lines.append(format_ast_node(stmt, indent + 1))
        lines.append(f"{prefix})")
        return "\n".join(lines)

    if cls_name == "FunctionDef":
        lines = [f"{prefix}FunctionDef(name={node.name!r}, params={node.params!r},"]
        for stmt in node.body:
            lines.append(format_ast_node(stmt, indent + 1))
        lines.append(f"{prefix})")
        return "\n".join(lines)

    if cls_name == "ReturnStatement":
        if node.value:
            lines = [f"{prefix}ReturnStatement("]
            lines.append(format_ast_node(node.value, indent + 1))
            lines.append(f"{prefix})")
            return "\n".join(lines)
        return f"{prefix}ReturnStatement()"

    if cls_name == "BreakStatement":
        return f"{prefix}BreakStatement()"

    if cls_name == "ContinueStatement":
        return f"{prefix}ContinueStatement()"

    # 处理各种表达式
    if cls_name in ("IntegerLiteral", "FloatLiteral", "StringLiteral", "BooleanLiteral"):
        return f"{prefix}{cls_name}(value={node.value!r})"

    if cls_name == "Identifier":
        return f"{prefix}Identifier(name={node.name!r})"

    if cls_name == "ArrayLiteral":
        lines = [f"{prefix}ArrayLiteral(["]
        for elem in node.elements:
            lines.append(format_ast_node(elem, indent + 1))
        lines.append(f"{prefix}])")
        return "\n".join(lines)

    if cls_name == "IndexExpression":
        lines = [f"{prefix}IndexExpression("]
        lines.append(format_ast_node(node.array, indent + 1))
        lines.append(format_ast_node(node.index, indent + 1))
        lines.append(f"{prefix})")
        return "\n".join(lines)

    if cls_name == "BinaryOp":
        lines = [f"{prefix}BinaryOp(op={node.op!r},"]
        lines.append(format_ast_node(node.left, indent + 1))
        lines.append(format_ast_node(node.right, indent + 1))
        lines.append(f"{prefix})")
        return "\n".join(lines)

    if cls_name == "UnaryOp":
        lines = [f"{prefix}UnaryOp(op={node.op!r},"]
        lines.append(format_ast_node(node.operand, indent + 1))
        lines.append(f"{prefix})")
        return "\n".join(lines)

    if cls_name == "CallExpression":
        lines = [f"{prefix}CallExpression("]
        lines.append(format_ast_node(node.callee, indent + 1))
        for arg in node.args:
            lines.append(format_ast_node(arg, indent + 1))
        lines.append(f"{prefix})")
        return "\n".join(lines)

    # 兜底
    return f"{prefix}{cls_name}(...)"


# ============================================================
#  功能入口
# ============================================================

def print_ast(source: str):
    """解析并打印 AST"""
    ast = tokenize_and_parse(source)
    print(format_ast_node(ast))


def print_bytecode(source: str):
    """编译并打印字节码反汇编结果"""
    ast = tokenize_and_parse(source)
    compiler = Compiler(get_builtins())
    main_func = compiler.compile(ast)
    print(f"=== 字节码反汇编: {main_func.name} ===")
    print(disassemble(main_func.chunk, main_func.name))


def run_interpreter(source: str):
    """使用树遍历解释器执行"""
    ast = tokenize_and_parse(source)
    interp = Interpreter()
    interp.run(ast)


def run_vm(source: str):
    """使用编译器 + 虚拟机执行"""
    ast = tokenize_and_parse(source)
    builtins = get_builtins()
    compiler = Compiler(builtins)
    main_func = compiler.compile(ast)
    vm = VM(builtins)
    vm.run(main_func)


# ============================================================
#  REPL
# ============================================================

def run_repl(use_vm: bool = False):
    """交互式 REPL（Read-Eval-Print Loop）

    支持多行输入：当检测到未闭合的大括号时，继续读取下一行。

    Args:
        use_vm: 是否使用虚拟机执行（默认使用树遍历解释器）
    """
    mode = "VM" if use_vm else "解释器"
    print(f"TinyLang REPL (模式: {mode})")
    print("输入 'exit' 或 'quit' 退出。")
    print()

    if use_vm:
        builtins = get_builtins()
        compiler = Compiler(builtins)
        vm = VM(builtins)
    else:
        interp = Interpreter()

    while True:
        try:
            # 支持多行输入
            lines = []
            brace_depth = 0
            prompt = ">>> "

            while True:
                try:
                    line = input(prompt)
                except EOFError:
                    print()
                    return

                lines.append(line)
                brace_depth += line.count("{") - line.count("}")

                if brace_depth <= 0:
                    break
                prompt = "... "

            source = "\n".join(lines).strip()

            if not source:
                continue
            if source in ("exit", "quit"):
                print("再见！")
                break

            # 确保以分号结尾（方便单行输入）
            if not source.endswith("}") and not source.endswith(";"):
                source += ";"

            # 解析并执行
            ast = tokenize_and_parse(source)

            if use_vm:
                # 每次 REPL 输入都重新编译
                main_func = compiler.compile(ast)
                # 将现有全局变量传递给新的 VM
                vm.run(main_func)
            else:
                interp.run(ast)

        except TinyLangError as e:
            print(f"错误: {e}")
        except Exception as e:
            print(f"内部错误: {e}")


# ============================================================
#  主函数
# ============================================================

def main():
    """命令行入口

    解析命令行参数，根据选项执行相应的操作。
    """
    args = sys.argv[1:]

    show_ast = "--ast" in args
    show_bytecode = "--bytecode" in args
    use_vm = "--vm" in args
    use_repl = "--repl" in args

    # 移除标志参数，剩下的应该是文件路径
    file_args = [a for a in args if not a.startswith("--")]

    if not file_args and not use_repl:
        # 没有文件参数且没有 --repl，进入 REPL
        run_repl(use_vm)
        return

    if use_repl:
        run_repl(use_vm)
        return

    if not file_args:
        print("错误: 请指定要执行的文件")
        sys.exit(1)

    filepath = file_args[0]

    # 读取源文件
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
    except FileNotFoundError:
        print(f"错误: 找不到文件 '{filepath}'")
        sys.exit(1)
    except Exception as e:
        print(f"错误: 读取文件失败: {e}")
        sys.exit(1)

    try:
        if show_ast:
            print_ast(source)
        elif show_bytecode:
            print_bytecode(source)
        elif use_vm:
            run_vm(source)
        else:
            run_interpreter(source)
    except TinyLangError as e:
        print(f"错误: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"内部错误: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
