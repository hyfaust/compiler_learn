"""
TinyLang 测试套件

全面测试编译器/解释器的各个组件：
- 词法分析器 (Lexer)
- 语法分析器 (Parser)
- 树遍历解释器 (Interpreter)
- 字节码编译器 (Compiler)
- 虚拟机 (VM)
- 内置函数
- 示例程序

测试同时验证解释器和虚拟机的输出一致性。
"""

import unittest
import sys
import os

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tinylang.lexer import Lexer, TokenType
from tinylang.parser import Parser
from tinylang.ast_nodes import *
from tinylang.interpreter import Interpreter
from tinylang.compiler import Compiler
from tinylang.vm import VM
from tinylang.builtins import get_builtins
from tinylang.errors import TinyLangError, LexerError, ParserError, CompileError


def run_with_interpreter(source: str) -> list:
    """用树遍历解释器执行源码，返回输出列表"""
    output = []
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    interp = Interpreter(output_list=output)
    interp.run(ast)
    return output


def run_with_vm(source: str) -> list:
    """用编译器+虚拟机执行源码，返回输出列表"""
    output = []
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()
    builtins = get_builtins(output)
    compiler = Compiler(builtins)
    main_func = compiler.compile(ast)
    vm = VM(builtins)
    vm.output = output
    vm.run(main_func)
    return output


def run_both(source: str) -> tuple:
    """同时用解释器和虚拟机执行，返回 (interp_output, vm_output)"""
    interp_out = run_with_interpreter(source)
    vm_out = run_with_vm(source)
    return interp_out, vm_out


# ============================================================
#  词法分析器测试
# ============================================================

class TestLexer(unittest.TestCase):
    """测试词法分析器"""

    def test_basic_tokens(self):
        """测试基本 Token 类型"""
        source = "let x = 42;"
        tokens = Lexer(source).tokenize()
        types = [t.type for t in tokens]
        self.assertIn(TokenType.LET, types)
        self.assertIn(TokenType.IDENTIFIER, types)
        self.assertIn(TokenType.ASSIGN, types)
        self.assertIn(TokenType.INTEGER, types)
        self.assertIn(TokenType.SEMICOLON, types)
        self.assertIn(TokenType.EOF, types)

    def test_numbers(self):
        """测试数字解析"""
        tokens = Lexer("42 3.14 0").tokenize()
        self.assertEqual(tokens[0].value, 42)
        self.assertEqual(tokens[1].value, 3.14)
        self.assertEqual(tokens[2].value, 0)

    def test_strings(self):
        """测试字符串解析"""
        tokens = Lexer('"hello world"').tokenize()
        self.assertEqual(tokens[0].value, "hello world")

    def test_string_escape(self):
        """测试字符串转义"""
        tokens = Lexer(r'"line1\nline2"').tokenize()
        self.assertEqual(tokens[0].value, "line1\nline2")

    def test_keywords(self):
        """测试关键字识别"""
        for kw in ["let", "if", "elif", "else", "while", "for", "in",
                    "func", "return", "break", "continue", "true", "false",
                    "none", "and", "or", "not"]:
            tokens = Lexer(kw).tokenize()
            self.assertNotEqual(tokens[0].type, TokenType.IDENTIFIER,
                                f"'{kw}' 应该被识别为关键字")

    def test_operators(self):
        """测试运算符"""
        source = "+ - * / % == != < > <= >= ="
        tokens = Lexer(source).tokenize()
        self.assertEqual(tokens[0].type, TokenType.PLUS)
        self.assertEqual(tokens[1].type, TokenType.MINUS)
        self.assertEqual(tokens[2].type, TokenType.STAR)
        self.assertEqual(tokens[3].type, TokenType.SLASH)
        self.assertEqual(tokens[4].type, TokenType.PERCENT)
        self.assertEqual(tokens[5].type, TokenType.EQ)
        self.assertEqual(tokens[6].type, TokenType.NEQ)
        self.assertEqual(tokens[7].type, TokenType.LT)
        self.assertEqual(tokens[8].type, TokenType.GT)
        self.assertEqual(tokens[9].type, TokenType.LTE)
        self.assertEqual(tokens[10].type, TokenType.GTE)
        self.assertEqual(tokens[11].type, TokenType.ASSIGN)

    def test_comments(self):
        """测试注释被跳过"""
        source = "let x = 1; // this is a comment\nlet y = 2;"
        tokens = Lexer(source).tokenize()
        values = [t.value for t in tokens if t.type != TokenType.EOF]
        self.assertNotIn("this is a comment", values)

    def test_error_on_unterminated_string(self):
        """测试未闭合字符串报错"""
        with self.assertRaises(LexerError):
            Lexer('"unterminated').tokenize()


# ============================================================
#  语法分析器测试
# ============================================================

class TestParser(unittest.TestCase):
    """测试语法分析器"""

    def _parse(self, source: str) -> Program:
        tokens = Lexer(source).tokenize()
        return Parser(tokens).parse()

    def test_let_statement(self):
        """测试 let 声明"""
        ast = self._parse("let x = 42;")
        self.assertEqual(len(ast.statements), 1)
        stmt = ast.statements[0]
        self.assertIsInstance(stmt, LetStatement)
        self.assertEqual(stmt.name, "x")
        self.assertIsInstance(stmt.value, IntegerLiteral)
        self.assertEqual(stmt.value.value, 42)

    def test_binary_expression(self):
        """测试二元表达式"""
        ast = self._parse("let x = 1 + 2 * 3;")
        stmt = ast.statements[0]
        # 应该解析为 1 + (2 * 3)
        self.assertIsInstance(stmt.value, BinaryOp)
        self.assertEqual(stmt.value.op, "+")
        self.assertIsInstance(stmt.value.right, BinaryOp)
        self.assertEqual(stmt.value.right.op, "*")

    def test_if_statement(self):
        """测试 if 语句"""
        ast = self._parse("if x > 0 { print(x); }")
        stmt = ast.statements[0]
        self.assertIsInstance(stmt, IfStatement)
        self.assertEqual(len(stmt.then_body), 1)
        self.assertEqual(len(stmt.elif_clauses), 0)
        self.assertIsNone(stmt.else_body)

    def test_if_elif_else(self):
        """测试 if/elif/else"""
        ast = self._parse("""
            if x > 0 {
                print("positive");
            } elif x < 0 {
                print("negative");
            } else {
                print("zero");
            }
        """)
        stmt = ast.statements[0]
        self.assertIsInstance(stmt, IfStatement)
        self.assertEqual(len(stmt.elif_clauses), 1)
        self.assertIsNotNone(stmt.else_body)

    def test_while_loop(self):
        """测试 while 循环"""
        ast = self._parse("while x < 10 { x = x + 1; }")
        stmt = ast.statements[0]
        self.assertIsInstance(stmt, WhileStatement)

    def test_for_loop(self):
        """测试 for-in 循环"""
        ast = self._parse("for item in arr { print(item); }")
        stmt = ast.statements[0]
        self.assertIsInstance(stmt, ForStatement)
        self.assertEqual(stmt.var_name, "item")

    def test_function_def(self):
        """测试函数定义"""
        ast = self._parse("func add(a, b) { return a + b; }")
        stmt = ast.statements[0]
        self.assertIsInstance(stmt, FunctionDef)
        self.assertEqual(stmt.name, "add")
        self.assertEqual(stmt.params, ["a", "b"])

    def test_function_call(self):
        """测试函数调用"""
        ast = self._parse("print(42);")
        stmt = ast.statements[0]
        self.assertIsInstance(stmt, ExpressionStatement)
        self.assertIsInstance(stmt.expression, CallExpression)

    def test_array_literal(self):
        """测试数组字面量"""
        ast = self._parse("let arr = [1, 2, 3];")
        stmt = ast.statements[0]
        self.assertIsInstance(stmt.value, ArrayLiteral)
        self.assertEqual(len(stmt.value.elements), 3)

    def test_index_expression(self):
        """测试索引表达式"""
        ast = self._parse("let x = arr[0];")
        stmt = ast.statements[0]
        self.assertIsInstance(stmt.value, IndexExpression)

    def test_assignment(self):
        """测试赋值语句"""
        ast = self._parse("x = 42;")
        stmt = ast.statements[0]
        self.assertIsInstance(stmt, AssignmentStatement)
        self.assertIsInstance(stmt.target, Identifier)

    def test_break_continue(self):
        """测试 break 和 continue"""
        ast = self._parse("while true { break; continue; }")
        stmt = ast.statements[0]
        self.assertIsInstance(stmt.body[0], BreakStatement)
        self.assertIsInstance(stmt.body[1], ContinueStatement)

    def test_operator_precedence(self):
        """测试运算符优先级: 1 + 2 * 3 == 7"""
        ast = self._parse("let x = 1 + 2 * 3;")
        # 顶层应该是 BinaryOp(+, 1, BinaryOp(*, 2, 3))
        expr = ast.statements[0].value
        self.assertIsInstance(expr, BinaryOp)
        self.assertEqual(expr.op, "+")
        self.assertIsInstance(expr.left, IntegerLiteral)
        self.assertEqual(expr.left.value, 1)
        self.assertIsInstance(expr.right, BinaryOp)
        self.assertEqual(expr.right.op, "*")

    def test_parse_error(self):
        """测试语法错误"""
        with self.assertRaises(ParserError):
            self._parse("let = 42;")  # 缺少变量名


# ============================================================
#  树遍历解释器测试
# ============================================================

class TestInterpreter(unittest.TestCase):
    """测试树遍历解释器"""

    def _run(self, source: str) -> list:
        return run_with_interpreter(source)

    def test_hello_world(self):
        """测试基本打印"""
        out = self._run('print("Hello, World!");')
        self.assertEqual(out, ["Hello, World!"])

    def test_arithmetic(self):
        """测试算术运算"""
        out = self._run("print(2 + 3 * 4);")
        self.assertEqual(out, ["14"])

    def test_variables(self):
        """测试变量声明和使用"""
        out = self._run("""
            let x = 10;
            let y = 20;
            print(x + y);
        """)
        self.assertEqual(out, ["30"])

    def test_string_concat(self):
        """测试字符串拼接"""
        out = self._run('print("hello" + " " + "world");')
        self.assertEqual(out, ["hello world"])

    def test_if_else(self):
        """测试 if/else 分支"""
        out = self._run("""
            let x = 10;
            if x > 5 {
                print("big");
            } else {
                print("small");
            }
        """)
        self.assertEqual(out, ["big"])

    def test_if_elif_else(self):
        """测试 if/elif/else"""
        out = self._run("""
            let x = 0;
            if x > 0 {
                print("positive");
            } elif x < 0 {
                print("negative");
            } else {
                print("zero");
            }
        """)
        self.assertEqual(out, ["zero"])

    def test_while_loop(self):
        """测试 while 循环"""
        out = self._run("""
            let i = 0;
            while i < 3 {
                print(i);
                i = i + 1;
            }
        """)
        self.assertEqual(out, ["0", "1", "2"])

    def test_for_loop(self):
        """测试 for-in 循环"""
        out = self._run("""
            let arr = [10, 20, 30];
            for item in arr {
                print(item);
            }
        """)
        self.assertEqual(out, ["10", "20", "30"])

    def test_break(self):
        """测试 break"""
        out = self._run("""
            let i = 0;
            while true {
                if i == 3 {
                    break;
                }
                print(i);
                i = i + 1;
            }
        """)
        self.assertEqual(out, ["0", "1", "2"])

    def test_continue(self):
        """测试 continue"""
        out = self._run("""
            let i = 0;
            while i < 5 {
                i = i + 1;
                if i == 3 {
                    continue;
                }
                print(i);
            }
        """)
        self.assertEqual(out, ["1", "2", "4", "5"])

    def test_function(self):
        """测试函数定义和调用"""
        out = self._run("""
            func add(a, b) {
                return a + b;
            }
            print(add(3, 4));
        """)
        self.assertEqual(out, ["7"])

    def test_recursion(self):
        """测试递归"""
        out = self._run("""
            func factorial(n) {
                if n <= 1 {
                    return 1;
                }
                return n * factorial(n - 1);
            }
            print(factorial(5));
        """)
        self.assertEqual(out, ["120"])

    def test_closure(self):
        """测试闭包"""
        out = self._run("""
            func make_counter() {
                let count = 0;
                func increment() {
                    count = count + 1;
                    return count;
                }
                return increment;
            }
            let c = make_counter();
            print(c());
            print(c());
            print(c());
        """)
        self.assertEqual(out, ["1", "2", "3"])

    def test_array_operations(self):
        """测试数组操作"""
        out = self._run("""
            let arr = [1, 2, 3];
            print(arr[0]);
            print(len(arr));
            arr[1] = 20;
            print(arr[1]);
        """)
        self.assertEqual(out, ["1", "3", "20"])

    def test_builtin_len(self):
        """测试 len 内置函数"""
        out = self._run("""
            print(len([1, 2, 3]));
            print(len("hello"));
        """)
        self.assertEqual(out, ["3", "5"])

    def test_builtin_type(self):
        """测试 type 内置函数"""
        out = self._run("""
            print(type(42));
            print(type(3.14));
            print(type("hello"));
            print(type(true));
            print(type([1, 2]));
            print(type(none));
        """)
        self.assertEqual(out, ["integer", "float", "string", "boolean", "array", "none"])

    def test_builtin_range(self):
        """测试 range 内置函数"""
        out = self._run("""
            let r = range(5);
            for i in r {
                print(i);
            }
        """)
        self.assertEqual(out, ["0", "1", "2", "3", "4"])

    def test_builtin_append(self):
        """测试 append 内置函数"""
        out = self._run("""
            let arr = [1, 2];
            append(arr, 3);
            print(len(arr));
            print(arr[2]);
        """)
        self.assertEqual(out, ["3", "3"])

    def test_boolean_logic(self):
        """测试布尔逻辑"""
        out = self._run("""
            print(true and true);
            print(true and false);
            print(false or true);
            print(not true);
            print(not false);
        """)
        self.assertEqual(out, ["true", "false", "true", "false", "true"])

    def test_short_circuit_and(self):
        """测试 and 短路求值"""
        out = self._run("""
            let result = false and true;
            print(result);
            let result2 = true and false;
            print(result2);
            let result3 = true and true;
            print(result3);
        """)
        self.assertEqual(out, ["false", "false", "true"])

    def test_short_circuit_or(self):
        """测试 or 短路求值"""
        out = self._run("""
            let result = true or false;
            print(result);
            let result2 = false or true;
            print(result2);
            let result3 = false or false;
            print(result3);
        """)
        self.assertEqual(out, ["true", "true", "false"])

    def test_nested_functions(self):
        """测试嵌套函数"""
        out = self._run("""
            func outer() {
                let x = 10;
                func inner() {
                    return x + 5;
                }
                return inner();
            }
            print(outer());
        """)
        self.assertEqual(out, ["15"])

    def test_comparison_operators(self):
        """测试所有比较运算符"""
        out = self._run("""
            print(1 == 1);
            print(1 != 2);
            print(1 < 2);
            print(2 > 1);
            print(1 <= 1);
            print(2 >= 1);
        """)
        self.assertEqual(out, ["true", "true", "true", "true", "true", "true"])

    def test_fibonacci(self):
        """测试斐波那契数列"""
        out = self._run("""
            func fib(n) {
                if n <= 1 {
                    return n;
                }
                return fib(n - 1) + fib(n - 2);
            }
            print(fib(10));
        """)
        self.assertEqual(out, ["55"])

    def test_error_undefined_var(self):
        """测试未定义变量错误"""
        with self.assertRaises(TinyLangError):
            self._run("print(x);")

    def test_error_type_mismatch(self):
        """测试类型错误"""
        with self.assertRaises(TinyLangError):
            self._run('let x = "hello" - 1;')

    def test_error_division_by_zero(self):
        """测试除以零错误"""
        with self.assertRaises(TinyLangError):
            self._run("print(10 / 0);")

    def test_error_wrong_arg_count(self):
        """测试参数个数错误"""
        with self.assertRaises(TinyLangError):
            self._run("""
                func add(a, b) { return a + b; }
                add(1);
            """)


# ============================================================
#  虚拟机测试
# ============================================================

class TestVM(unittest.TestCase):
    """测试编译器 + 虚拟机"""

    def _run(self, source: str) -> list:
        return run_with_vm(source)

    def test_hello_world(self):
        out = self._run('print("Hello, World!");')
        self.assertEqual(out, ["Hello, World!"])

    def test_arithmetic(self):
        out = self._run("print(2 + 3 * 4);")
        self.assertEqual(out, ["14"])

    def test_variables(self):
        out = self._run("""
            let x = 10;
            let y = 20;
            print(x + y);
        """)
        self.assertEqual(out, ["30"])

    def test_if_else(self):
        out = self._run("""
            let x = 10;
            if x > 5 {
                print("big");
            } else {
                print("small");
            }
        """)
        self.assertEqual(out, ["big"])

    def test_while_loop(self):
        out = self._run("""
            let i = 0;
            while i < 3 {
                print(i);
                i = i + 1;
            }
        """)
        self.assertEqual(out, ["0", "1", "2"])

    def test_for_loop(self):
        out = self._run("""
            let arr = [10, 20, 30];
            for item in arr {
                print(item);
            }
        """)
        self.assertEqual(out, ["10", "20", "30"])

    def test_function(self):
        out = self._run("""
            func add(a, b) {
                return a + b;
            }
            print(add(3, 4));
        """)
        self.assertEqual(out, ["7"])

    def test_recursion(self):
        out = self._run("""
            func factorial(n) {
                if n <= 1 {
                    return 1;
                }
                return n * factorial(n - 1);
            }
            print(factorial(5));
        """)
        self.assertEqual(out, ["120"])

    def test_closure(self):
        out = self._run("""
            func make_counter() {
                let count = 0;
                func increment() {
                    count = count + 1;
                    return count;
                }
                return increment;
            }
            let c = make_counter();
            print(c());
            print(c());
            print(c());
        """)
        self.assertEqual(out, ["1", "2", "3"])

    def test_array_operations(self):
        out = self._run("""
            let arr = [1, 2, 3];
            print(arr[0]);
            print(len(arr));
            arr[1] = 20;
            print(arr[1]);
        """)
        self.assertEqual(out, ["1", "3", "20"])

    def test_boolean_logic(self):
        out = self._run("""
            print(true and true);
            print(true and false);
            print(false or true);
            print(not true);
        """)
        self.assertEqual(out, ["true", "false", "true", "false"])

    def test_break_continue(self):
        out = self._run("""
            let i = 0;
            while i < 5 {
                i = i + 1;
                if i == 3 {
                    continue;
                }
                if i == 5 {
                    break;
                }
                print(i);
            }
        """)
        self.assertEqual(out, ["1", "2", "4"])


# ============================================================
#  一致性测试（解释器 vs 虚拟机）
# ============================================================

class TestConsistency(unittest.TestCase):
    """验证树遍历解释器和虚拟机产生相同结果"""

    def _assert_same_output(self, source: str):
        """断言解释器和虚拟机的输出一致"""
        interp_out, vm_out = run_both(source)
        self.assertEqual(interp_out, vm_out,
                         f"输出不一致!\n解释器: {interp_out}\n虚拟机: {vm_out}")

    def test_arithmetic_consistency(self):
        self._assert_same_output("""
            print(1 + 2 * 3);
            print(10 - 4 / 2);
            print(7 % 3);
            print(-5 + 10);
        """)

    def test_control_flow_consistency(self):
        self._assert_same_output("""
            let x = 10;
            if x > 5 { print("yes"); } else { print("no"); }
            if x < 5 { print("a"); } elif x == 10 { print("b"); } else { print("c"); }
        """)

    def test_loop_consistency(self):
        self._assert_same_output("""
            let sum = 0;
            let i = 1;
            while i <= 10 {
                sum = sum + i;
                i = i + 1;
            }
            print(sum);
        """)

    def test_function_consistency(self):
        self._assert_same_output("""
            func fib(n) {
                if n <= 1 { return n; }
                return fib(n - 1) + fib(n - 2);
            }
            let i = 0;
            while i < 10 {
                print(fib(i));
                i = i + 1;
            }
        """)

    def test_closure_consistency(self):
        self._assert_same_output("""
            func make_adder(x) {
                func adder(y) {
                    return x + y;
                }
                return adder;
            }
            let add5 = make_adder(5);
            let add10 = make_adder(10);
            print(add5(3));
            print(add10(3));
        """)

    def test_array_consistency(self):
        self._assert_same_output("""
            let arr = [3, 1, 4, 1, 5, 9, 2, 6];
            let sum = 0;
            for item in arr {
                sum = sum + item;
            }
            print(sum);
            print(len(arr));
            print(arr[0]);
            print(arr[len(arr) - 1]);
        """)

    def test_builtin_consistency(self):
        self._assert_same_output("""
            print(type(42));
            print(type("hello"));
            print(type(true));
            print(str(123));
            print(int("456"));
            print(float("3.14"));
            print(len("hello"));
            print(len([1, 2, 3]));
        """)

    def test_complex_consistency(self):
        """综合测试"""
        self._assert_same_output("""
            func is_prime(n) {
                if n < 2 { return false; }
                let i = 2;
                while i * i <= n {
                    if n % i == 0 { return false; }
                    i = i + 1;
                }
                return true;
            }

            let count = 0;
            let n = 2;
            while n < 20 {
                if is_prime(n) {
                    print(n);
                    count = count + 1;
                }
                n = n + 1;
            }
            print("总计: " + str(count));
        """)


# ============================================================
#  示例程序测试
# ============================================================

class TestExamples(unittest.TestCase):
    """测试 examples/ 目录下的示例程序"""

    def _run_example(self, filename: str):
        """读取并执行示例文件"""
        examples_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            "examples"
        )
        filepath = os.path.join(examples_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            source = f.read()
        # 用两种方式执行，确保不报错
        interp_out = run_with_interpreter(source)
        vm_out = run_with_vm(source)
        return interp_out, vm_out

    def test_hello(self):
        out, _ = self._run_example("hello.tl")
        self.assertTrue(len(out) > 0)

    def test_fibonacci(self):
        out, _ = self._run_example("fibonacci.tl")
        self.assertTrue(len(out) > 0)

    def test_factorial(self):
        out, _ = self._run_example("factorial.tl")
        self.assertTrue(len(out) > 0)

    def test_sorting(self):
        interp_out, vm_out = self._run_example("sorting.tl")
        self.assertEqual(interp_out, vm_out)

    def test_closure(self):
        interp_out, vm_out = self._run_example("closure.tl")
        self.assertEqual(interp_out, vm_out)

    def test_game(self):
        interp_out, vm_out = self._run_example("game.tl")
        self.assertEqual(interp_out, vm_out)


# ============================================================
#  内置函数测试
# ============================================================

class TestBuiltins(unittest.TestCase):
    """测试内置函数"""

    def _run(self, source: str) -> list:
        return run_with_interpreter(source)

    def test_print_multiple_args(self):
        out = self._run('print("a", "b", "c");')
        self.assertEqual(out, ["a b c"])

    def test_len_string(self):
        out = self._run('print(len("hello"));')
        self.assertEqual(out, ["5"])

    def test_len_array(self):
        out = self._run("print(len([1, 2, 3, 4, 5]));")
        self.assertEqual(out, ["5"])

    def test_str_conversion(self):
        out = self._run("""
            print(str(42));
            print(str(3.14));
            print(str(true));
            print(str(none));
        """)
        self.assertEqual(out, ["42", "3.14", "true", "none"])

    def test_int_conversion(self):
        out = self._run("""
            print(int("42"));
            print(int(3.14));
            print(int(false));
        """)
        self.assertEqual(out, ["42", "3", "0"])

    def test_float_conversion(self):
        out = self._run("""
            print(float("3.14"));
            print(float(42));
        """)
        self.assertEqual(out, ["3.14", "42.0"])

    def test_range_one_arg(self):
        out = self._run("""
            let r = range(3);
            for i in r { print(i); }
        """)
        self.assertEqual(out, ["0", "1", "2"])

    def test_range_two_args(self):
        out = self._run("""
            let r = range(2, 5);
            for i in r { print(i); }
        """)
        self.assertEqual(out, ["2", "3", "4"])

    def test_range_three_args(self):
        out = self._run("""
            let r = range(0, 10, 3);
            for i in r { print(i); }
        """)
        self.assertEqual(out, ["0", "3", "6", "9"])

    def test_append(self):
        out = self._run("""
            let arr = [1, 2];
            append(arr, 3);
            print(arr);
        """)
        self.assertEqual(out, ["[1, 2, 3]"])

    def test_format_values(self):
        """测试值的格式化显示"""
        out = self._run("""
            print(true);
            print(false);
            print(none);
            print([1, 2, 3]);
        """)
        self.assertEqual(out, ["true", "false", "none", "[1, 2, 3]"])


# ============================================================
#  环境测试
# ============================================================

class TestEnvironment(unittest.TestCase):
    """测试作用域环境"""

    def test_define_and_get(self):
        from tinylang.environment import Environment
        env = Environment()
        env.define("x", 42)
        self.assertEqual(env.get("x"), 42)

    def test_scope_chain(self):
        from tinylang.environment import Environment
        parent = Environment()
        parent.define("x", 10)
        child = Environment(parent)
        child.define("y", 20)
        self.assertEqual(child.get("y"), 20)
        self.assertEqual(child.get("x"), 10)

    def test_set_updates_nearest(self):
        from tinylang.environment import Environment
        parent = Environment()
        parent.define("x", 10)
        child = Environment(parent)
        child.set("x", 99)
        self.assertEqual(parent.get("x"), 99)

    def test_undefined_raises(self):
        from tinylang.environment import Environment
        env = Environment()
        with self.assertRaises(TinyLangError):
            env.get("nonexistent")


if __name__ == "__main__":
    unittest.main()
