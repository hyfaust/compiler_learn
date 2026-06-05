"""
TinyLang 字节码编译器和虚拟机

一个自包含的栈式虚拟机实现，包含：
- 字节码指令集（基于 tinylang.py 中的 Opcode）
- AST 到字节码的编译器（基于 tinylang.py 中的 Compiler）
- 栈式虚拟机（执行字节码）
- 常量池管理
- 函数调用栈帧
- 闭包支持
- 命令行入口

用法：
    python tinylang_compiler.py <file.tl>         # 编译并执行
    python tinylang_compiler.py --dis <file.tl>   # 显示反汇编
    python tinylang_compiler.py --repl            # REPL 模式
"""

import importlib.util as _ilu
import os as _os
import sys as _sys

# 通过文件路径导入 tinylang.py（避免与 tinylang/ 包冲突）
# 如果 tinylang.py 已经通过主脚本注册到 sys.modules，则直接复用
_mod_key = "_tinylang_standalone_mod"
if _mod_key in _sys.modules:
    _mod = _sys.modules[_mod_key]
else:
    _tinylang_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "tinylang.py")
    _spec = _ilu.spec_from_file_location(_mod_key, _tinylang_path)
    _mod = _ilu.module_from_spec(_spec)
    _sys.modules[_mod_key] = _mod
    _spec.loader.exec_module(_mod)

Lexer = _mod.Lexer
Parser = _mod.Parser
Compiler = _mod.Compiler
Program = _mod.Program
Chunk = _mod.Chunk
CompiledFunc = _mod.CompiledFunc
Opcode = _mod.Opcode
disassemble = _mod.disassemble
TinyLangError = _mod.TinyLangError
CompileError = _mod.CompileError
IntegerLiteral = _mod.IntegerLiteral
FloatLiteral = _mod.FloatLiteral
StringLiteral = _mod.StringLiteral
BooleanLiteral = _mod.BooleanLiteral
NoneLiteral = _mod.NoneLiteral
Identifier = _mod.Identifier
BinaryOp = _mod.BinaryOp
UnaryOp = _mod.UnaryOp
CallExpression = _mod.CallExpression
ArrayLiteral = _mod.ArrayLiteral
IndexExpression = _mod.IndexExpression
VarDecl = _mod.VarDecl
Assignment = _mod.Assignment
ExprStatement = _mod.ExprStatement
IfStmt = _mod.IfStmt
WhileStmt = _mod.WhileStmt
ForStmt = _mod.ForStmt
FuncDef = _mod.FuncDef
ReturnStmt = _mod.ReturnStmt
BreakStmt = _mod.BreakStmt
ContinueStmt = _mod.ContinueStmt


# ============================================================
#  运行时错误
# ============================================================

class RuntimeError_(TinyLangError):
    pass


# ============================================================
#  内置函数（VM 专用）
# ============================================================

class BuiltinFunc:
    """VM 专用的内置函数包装"""
    def __init__(self, name, func):
        self.name = name
        self.func = func
        self.arity = -1

    def __repr__(self):
        return f"<builtin: {self.name}>"


def format_value(value) -> str:
    if value is True: return "true"
    if value is False: return "false"
    if value is None: return "none"
    if isinstance(value, list):
        return "[" + ", ".join(format_value(v) for v in value) + "]"
    return str(value)


def make_vm_builtins(output_list=None):
    builtins = {}

    def _print(args):
        text = " ".join(format_value(a) for a in args)
        if output_list is not None:
            output_list.append(text)
        print(text)
        return None
    builtins["print"] = BuiltinFunc("print", _print)

    def _len(args):
        if len(args) != 1:
            raise RuntimeError_("len() 需要 1 个参数")
        v = args[0]
        if isinstance(v, (list, str)): return len(v)
        raise RuntimeError_(f"len() 不支持 {type(v).__name__}")
    builtins["len"] = BuiltinFunc("len", _len)

    def _type(args):
        if len(args) != 1:
            raise RuntimeError_("type() 需要 1 个参数")
        v = args[0]
        if isinstance(v, bool): return "boolean"
        if isinstance(v, int): return "integer"
        if isinstance(v, float): return "float"
        if isinstance(v, str): return "string"
        if isinstance(v, list): return "array"
        if v is None: return "none"
        return "unknown"
    builtins["type"] = BuiltinFunc("type", _type)

    def _str(args):
        if len(args) != 1:
            raise RuntimeError_("str() 需要 1 个参数")
        return format_value(args[0])
    builtins["str"] = BuiltinFunc("str", _str)

    def _int(args):
        if len(args) != 1:
            raise RuntimeError_("int() 需要 1 个参数")
        v = args[0]
        if isinstance(v, bool): return 1 if v else 0
        if isinstance(v, (int, float)): return int(v)
        if isinstance(v, str):
            try: return int(v)
            except ValueError: return int(float(v))
        raise RuntimeError_(f"无法转换为整数: {type(v).__name__}")
    builtins["int"] = BuiltinFunc("int", _int)

    def _range(args):
        if len(args) == 1: return list(range(int(args[0])))
        if len(args) == 2: return list(range(int(args[0]), int(args[1])))
        if len(args) == 3: return list(range(int(args[0]), int(args[1]), int(args[2])))
        raise RuntimeError_("range() 需要 1-3 个参数")
    builtins["range"] = BuiltinFunc("range", _range)

    def _append(args):
        if len(args) != 2:
            raise RuntimeError_("append() 需要 2 个参数")
        if not isinstance(args[0], list):
            raise RuntimeError_("append() 第一个参数必须是数组")
        args[0].append(args[1])
        return args[0]
    builtins["append"] = BuiltinFunc("append", _append)

    return builtins


# ============================================================
#  闭包
# ============================================================

class Closure:
    """闭包 —— 包装编译后的函数及其捕获的变量"""

    def __init__(self, func: CompiledFunc, captured=None):
        self.func = func
        self.captured = captured if captured is not None else {}

    @property
    def name(self): return self.func.name

    @property
    def params(self): return self.func.params

    @property
    def arity(self): return self.func.arity

    @property
    def chunk(self): return self.func.chunk

    def __repr__(self):
        return f"<closure {self.name}/{self.arity}>"


# ============================================================
#  调用栈帧
# ============================================================

class CallFrame:
    """一次函数调用的执行上下文"""

    def __init__(self, func=None, ip=0, locals_=None, captured=None, stack_base=0):
        self.func = func
        self.ip = ip
        self.locals = locals_ if locals_ is not None else {}
        self.captured = captured
        self.stack_base = stack_base


# ============================================================
#  栈式虚拟机
# ============================================================

class VM:
    """基于栈的虚拟机，执行编译器生成的字节码"""

    def __init__(self, builtins=None):
        self.stack: list = []
        self.frames: list[CallFrame] = []
        self.globals_: dict = {}
        self.builtins = builtins or {}
        self.output: list = []

    @property
    def frame(self) -> CallFrame:
        return self.frames[-1]

    def run(self, main_func: CompiledFunc):
        """执行主函数"""
        for name, func in self.builtins.items():
            self.globals_[name] = func

        main_closure = Closure(main_func, {})
        self.frames.append(CallFrame(
            func=main_closure, ip=0,
            locals_=self.globals_, stack_base=0))

        self._loop()

    def _loop(self):
        """主执行循环：取指-解码-执行"""
        while True:
            frame = self.frame
            chunk = frame.func.chunk if frame.func else None
            if chunk is None or frame.ip >= len(chunk.code):
                break

            op = chunk.code[frame.ip]; frame.ip += 1

            # ---- 常量加载 ----
            if op == Opcode.LOAD_CONST:
                idx = chunk.code[frame.ip]; frame.ip += 1
                self.stack.append(chunk.constants[idx])

            elif op == Opcode.LOAD_TRUE:
                self.stack.append(True)
            elif op == Opcode.LOAD_FALSE:
                self.stack.append(False)
            elif op == Opcode.LOAD_NONE:
                self.stack.append(None)

            # ---- 变量操作 ----
            elif op == Opcode.LOAD_VAR:
                ni = chunk.code[frame.ip]; frame.ip += 1
                name = chunk.constants[ni]
                self.stack.append(self._resolve(name, frame))

            elif op == Opcode.STORE_VAR:
                ni = chunk.code[frame.ip]; frame.ip += 1
                name = chunk.constants[ni]
                val = self.stack[-1]
                # 闭包自动捕获
                if isinstance(val, CompiledFunc):
                    cap = dict(frame.locals)
                    if frame.captured:
                        cap.update(frame.captured)
                    val = Closure(val, cap)
                    self.stack[-1] = val
                self._assign(name, val, frame)
                # 递归自引用
                if isinstance(val, Closure) and val.captured is not None:
                    val.captured[name] = val

            # ---- 算术运算 ----
            elif op == Opcode.ADD:
                b = self.stack.pop(); a = self.stack.pop()
                if isinstance(a, str) or isinstance(b, str):
                    self.stack.append(format_value(a) + format_value(b))
                else:
                    self.stack.append(a + b)

            elif op == Opcode.SUB:
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a - b)

            elif op == Opcode.MUL:
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a * b)

            elif op == Opcode.DIV:
                b = self.stack.pop(); a = self.stack.pop()
                if b == 0: raise RuntimeError_("除以零")
                self.stack.append(a // b if isinstance(a, int) and isinstance(b, int) else a / b)

            elif op == Opcode.MOD:
                b = self.stack.pop(); a = self.stack.pop()
                if b == 0: raise RuntimeError_("对零取模")
                self.stack.append(a % b)

            elif op == Opcode.NEGATE:
                self.stack.append(-self.stack.pop())

            # ---- 比较运算 ----
            elif op == Opcode.CMP_EQ:
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a == b)
            elif op == Opcode.CMP_NEQ:
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a != b)
            elif op == Opcode.CMP_LT:
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a < b)
            elif op == Opcode.CMP_GT:
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a > b)
            elif op == Opcode.CMP_LTE:
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a <= b)
            elif op == Opcode.CMP_GTE:
                b = self.stack.pop(); a = self.stack.pop()
                self.stack.append(a >= b)

            # ---- 逻辑运算 ----
            elif op == Opcode.NOT:
                self.stack.append(not self._truthy(self.stack.pop()))

            # ---- 栈操作 ----
            elif op == Opcode.POP:
                self.stack.pop()
            elif op == Opcode.DUP:
                self.stack.append(self.stack[-1])

            # ---- 跳转 ----
            elif op == Opcode.JUMP:
                frame.ip = chunk.code[frame.ip]

            elif op == Opcode.JUMP_IF_FALSE:
                target = chunk.code[frame.ip]; frame.ip += 1
                cond = self.stack.pop()
                if not self._truthy(cond):
                    frame.ip = target

            elif op == Opcode.JUMP_IF_TRUE:
                target = chunk.code[frame.ip]; frame.ip += 1
                cond = self.stack.pop()
                if self._truthy(cond):
                    frame.ip = target

            # ---- 函数调用 ----
            elif op == Opcode.CALL:
                argc = chunk.code[frame.ip]; frame.ip += 1
                args = [self.stack.pop() for _ in range(argc)]
                args.reverse()
                callee = self.stack.pop()
                self._call(callee, args)

            elif op == Opcode.RETURN:
                val = self.stack.pop()
                old_frame = self.frames.pop()
                del self.stack[old_frame.stack_base:]
                self.stack.append(val)

            # ---- 数组操作 ----
            elif op == Opcode.BUILD_ARRAY:
                count = chunk.code[frame.ip]; frame.ip += 1
                elems = [self.stack.pop() for _ in range(count)]
                elems.reverse()
                self.stack.append(elems)

            elif op == Opcode.GET_INDEX:
                idx = self.stack.pop(); arr = self.stack.pop()
                if not isinstance(arr, (list, str)):
                    raise RuntimeError_(f"无法索引 {type(arr).__name__}")
                i = int(idx)
                if i < 0 or i >= len(arr):
                    raise RuntimeError_(f"索引越界: {i}")
                self.stack.append(arr[i])

            elif op == Opcode.SET_INDEX:
                val = self.stack.pop(); idx = self.stack.pop(); arr = self.stack.pop()
                if not isinstance(arr, list):
                    raise RuntimeError_("只能对数组索引赋值")
                arr[int(idx)] = val
                self.stack.append(val)

            elif op == Opcode.GET_LEN:
                val = self.stack.pop()
                if isinstance(val, (list, str)):
                    self.stack.append(len(val))
                else:
                    raise RuntimeError_(f"len() 不支持 {type(val).__name__}")

            # ---- 停机 ----
            elif op == Opcode.HALT:
                break

            else:
                raise RuntimeError_(f"未知操作码: {op}")

    # ---- 变量解析 ----

    def _resolve(self, name, frame):
        if name in frame.locals: return frame.locals[name]
        if frame.captured is not None and name in frame.captured: return frame.captured[name]
        if name in self.globals_: return self.globals_[name]
        raise RuntimeError_(f"未定义的变量: '{name}'")

    def _assign(self, name, value, frame):
        if name in frame.locals:
            frame.locals[name] = value; return
        if frame.captured is not None and name in frame.captured:
            frame.captured[name] = value; return
        if name in self.globals_:
            self.globals_[name] = value; return
        frame.locals[name] = value

    # ---- 函数调用 ----

    def _call(self, callee, args):
        if isinstance(callee, BuiltinFunc):
            self.stack.append(callee.func(args))
            return
        if isinstance(callee, Closure):
            if len(args) != callee.arity:
                raise RuntimeError_(
                    f"函数 '{callee.name}' 需要 {callee.arity} 个参数，传入了 {len(args)} 个")
            locals_ = {}
            for i, p in enumerate(callee.params):
                locals_[p] = args[i]
            # args 已由 CALL 指令从栈中弹出，stack_base 就是当前栈顶
            self.frames.append(CallFrame(
                func=callee, ip=0, locals_=locals_,
                captured=callee.captured,
                stack_base=len(self.stack)))
            return
        if isinstance(callee, CompiledFunc):
            self._call(Closure(callee, self.globals_), args)
            return
        raise RuntimeError_(f"不可调用: {type(callee).__name__}")

    @staticmethod
    def _truthy(value) -> bool:
        if value is None: return False
        if isinstance(value, bool): return value
        if isinstance(value, (int, float)): return value != 0
        if isinstance(value, str): return len(value) > 0
        if isinstance(value, list): return len(value) > 0
        return True


# ============================================================
#  编译并执行的便捷函数
# ============================================================

def compile_and_run(source: str, output_list=None, show_dis=False):
    """编译源代码并用 VM 执行"""
    tokens = Lexer(source).tokenize()
    ast = Parser(tokens).parse()

    builtins = make_vm_builtins(output_list)
    compiler = Compiler(builtins)
    main_func = compiler.compile(ast)

    if show_dis:
        print(disassemble(main_func.chunk, main_func.name))
        return

    vm = VM(builtins)
    vm.run(main_func)


# ============================================================
#  REPL
# ============================================================

def repl():
    """交互式 REPL"""
    print("TinyLang 编译器 REPL (VM 模式)")
    print("输入 'exit' 或 'quit' 退出。")

    builtins = make_vm_builtins()
    compiler = Compiler(builtins)
    vm = VM(builtins)

    while True:
        try:
            lines = []
            depth = 0
            prompt = ">>> "
            while True:
                try:
                    line = input(prompt)
                except EOFError:
                    print()
                    return
                lines.append(line)
                depth += line.count("{") - line.count("}")
                if depth <= 0:
                    break
                prompt = "... "

            src = "\n".join(lines).strip()
            if not src:
                continue
            if src in ("exit", "quit"):
                print("再见！")
                break
            if not src.endswith("}") and not src.endswith(";"):
                src += ";"

            tokens = Lexer(src).tokenize()
            ast = Parser(tokens).parse()
            main_func = compiler.compile(ast)
            vm.run(main_func)

        except TinyLangError as e:
            print(f"错误: {e}")
        except Exception as e:
            print(f"内部错误: {e}")


# ============================================================
#  主函数
# ============================================================

def main():
    import sys
    args = sys.argv[1:]
    show_dis = "--dis" in args
    use_repl = "--repl" in args
    file_args = [a for a in args if not a.startswith("--")]

    if use_repl or not file_args:
        repl()
        return

    with open(file_args[0], "r", encoding="utf-8") as f:
        source = f.read()

    compile_and_run(source, show_dis=show_dis)


if __name__ == "__main__":
    main()
