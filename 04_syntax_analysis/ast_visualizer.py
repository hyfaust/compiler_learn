#!/usr/bin/env python3
"""
ast_visualizer.py - AST 树形可视化工具

使用方法：
  python ast_visualizer.py <source_file>
  python ast_visualizer.py              # 使用内置演示代码
"""

import sys
from parser import (
    Tokenizer, Parser, TokenType,
    ASTNode, Program, Assignment, IfStmt, Block,
    BinaryOp, UnaryOp, Number, Identifier,
    ast_to_string,
)


class ASTVisualizer:
    """AST 树形可视化渲染器"""

    TEE = "├── "
    ELBOW = "└── "
    PIPE = "│   "
    SPACE = "    "

    def __init__(self):
        self.lines = []

    def visualize(self, node: ASTNode) -> str:
        self.lines = []
        self._render_node(node, "", True)
        return "\n".join(self.lines)

    def _render_node(self, node: ASTNode, prefix: str, is_last: bool):
        if node is None:
            return
        connector = self.ELBOW if is_last else self.TEE
        extension = self.SPACE if is_last else self.PIPE

        if isinstance(node, Program):
            self.lines.append(f"{prefix}{connector}Program")
            child_prefix = prefix + extension
            for i, stmt in enumerate(node.stmts):
                self._render_node(stmt, child_prefix, i == len(node.stmts) - 1)
        elif isinstance(node, Assignment):
            self.lines.append(f"{prefix}{connector}Assignment(\"{node.name}\")")
            self._render_node(node.value, prefix + extension, True)
        elif isinstance(node, IfStmt):
            self.lines.append(f"{prefix}{connector}IfStmt")
            child_prefix = prefix + extension
            self.lines.append(f"{child_prefix}├── condition:")
            self._render_node(node.condition, child_prefix + self.PIPE, True)
            self.lines.append(f"{child_prefix}├── then:")
            self._render_node(node.then_body, child_prefix + self.PIPE, True)
            if node.else_body:
                self.lines.append(f"{child_prefix}└── else:")
                self._render_node(node.else_body, child_prefix + self.SPACE, True)
        elif isinstance(node, Block):
            self.lines.append(f"{prefix}{connector}Block ({len(node.stmts)} stmts)")
            child_prefix = prefix + extension
            for i, stmt in enumerate(node.stmts):
                self._render_node(stmt, child_prefix, i == len(node.stmts) - 1)
        elif isinstance(node, BinaryOp):
            self.lines.append(f"{prefix}{connector}BinaryOp({node.op})")
            child_prefix = prefix + extension
            self._render_node(node.left, child_prefix, False)
            self._render_node(node.right, child_prefix, True)
        elif isinstance(node, UnaryOp):
            self.lines.append(f"{prefix}{connector}UnaryOp({node.op})")
            self._render_node(node.operand, prefix + extension, True)
        elif isinstance(node, Number):
            self.lines.append(f"{prefix}{connector}Number({node.raw})")
        elif isinstance(node, Identifier):
            self.lines.append(f"{prefix}{connector}Identifier(\"{node.name}\")")
        else:
            self.lines.append(f"{prefix}{connector}{type(node).__name__}")


class ASTStats:
    """AST 统计信息收集器"""

    def __init__(self):
        self.node_counts = {}
        self.max_depth = 0
        self.total_nodes = 0

    def collect(self, node: ASTNode, depth: int = 0):
        if node is None:
            return
        self.total_nodes += 1
        self.max_depth = max(self.max_depth, depth)
        type_name = type(node).__name__
        self.node_counts[type_name] = self.node_counts.get(type_name, 0) + 1

        if isinstance(node, Program):
            for stmt in node.stmts:
                self.collect(stmt, depth + 1)
        elif isinstance(node, Assignment):
            self.collect(node.value, depth + 1)
        elif isinstance(node, IfStmt):
            self.collect(node.condition, depth + 1)
            self.collect(node.then_body, depth + 1)
            if node.else_body:
                self.collect(node.else_body, depth + 1)
        elif isinstance(node, Block):
            for stmt in node.stmts:
                self.collect(stmt, depth + 1)
        elif isinstance(node, BinaryOp):
            self.collect(node.left, depth + 1)
            self.collect(node.right, depth + 1)
        elif isinstance(node, UnaryOp):
            self.collect(node.operand, depth + 1)

    def report(self) -> str:
        lines = ["AST Statistics:"]
        lines.append(f"  Total nodes: {self.total_nodes}")
        lines.append(f"  Max depth:   {self.max_depth}")
        lines.append(f"  Node types:")
        for type_name, count in sorted(self.node_counts.items()):
            lines.append(f"    {type_name}: {count}")
        return "\n".join(lines)


def main():
    demo_source = """\
x = 3 + 4 * 5;
if (x > 10) {
    y = (a + b) * c;
} else {
    y = 0;
}
result = (price * quantity) - discount + tax;
"""

    if len(sys.argv) > 1:
        filename = sys.argv[1]
        try:
            with open(filename, 'r', encoding='utf-8') as f:
                source = f.read()
            print(f"Visualizing AST for: {filename}")
        except FileNotFoundError:
            print(f"Error: File '{filename}' not found.")
            sys.exit(1)
    else:
        source = demo_source
        print("No file specified, using built-in demo code.")
        print("(Usage: python ast_visualizer.py <source_file>)")

    print("=" * 60)
    print()

    try:
        tokenizer = Tokenizer(source)
        tokens = tokenizer.tokenize()
    except Exception as e:
        print(f"Lexer Error: {e}")
        sys.exit(1)

    parser = Parser(tokens)
    ast = parser.parse()

    if parser.errors:
        print(f"Found {len(parser.errors)} syntax error(s):")
        for err in parser.errors:
            print(f"  Line {err.line}: {err.message}")
        print()

    print("--- AST Tree View ---")
    print()
    visualizer = ASTVisualizer()
    print(visualizer.visualize(ast))
    print()

    print("--- AST Text View ---")
    print()
    print(ast_to_string(ast))
    print()

    print("--- AST Statistics ---")
    print()
    stats = ASTStats()
    stats.collect(ast)
    print(stats.report())
    print()

    print("=" * 60)
    print("Visualization complete.")


if __name__ == "__main__":
    main()
