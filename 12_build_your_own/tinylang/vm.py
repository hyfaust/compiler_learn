"""
基于栈的虚拟机 (Stack-Based Virtual Machine)

执行字节码编译器生成的指令序列。虚拟机使用一个操作数栈来
传递数据，通过 CallFrame 栈来管理函数调用。

栈式虚拟机的工作原理：
- 每条指令从栈上弹出操作数，将结果压回栈上
- 函数调用时压入新的 CallFrame，返回时弹出
- CallFrame 包含函数的局部变量、指令指针和捕获变量
- 全局变量存储在 VM 的 globals 字典中

变量解析链（Lookup Chain）：
    1. frame.locals   —— 当前函数的局部变量
    2. frame.captured —— 闭包捕获的变量
    3. vm.globals     —— 全局变量

设计决策：
- 闭包捕获的变量通过引用（dict）而非拷贝传递，支持跨调用共享状态
- 内置函数通过 BuiltinFunction 类型检测，直接调用 Python 函数
- 数组操作 GET_INDEX/SET_INDEX/GET_LEN 操作栈顶的值
"""

from .opcodes import Opcode, Chunk, CompiledFunction, disassemble
from .builtins import BuiltinFunction, format_value
from .errors import RuntimeError_


# ============================================================
#  闭包对象
# ============================================================

class Closure:
    """闭包 —— 包装编译后的函数及其捕获的变量

    在 TinyLang 中，每个函数在运行时都被包装为闭包。
    即使函数没有捕获任何自由变量，也使用 Closure 包装。

    Attributes:
        func:     编译后的函数对象 (CompiledFunction)
        captured: 捕获的变量字典（引用，非拷贝）
    """

    def __init__(self, func: CompiledFunction, captured: dict = None):
        self.func = func
        self.captured = captured if captured is not None else {}

    @property
    def name(self) -> str:
        return self.func.name

    @property
    def params(self) -> list:
        return self.func.params

    @property
    def arity(self) -> int:
        return self.func.arity

    @property
    def chunk(self) -> Chunk:
        return self.func.chunk

    def __repr__(self):
        return f"<closure {self.name}/{self.arity}>"


# ============================================================
#  调用栈帧
# ============================================================

class CallFrame:
    """调用栈帧 —— 一次函数调用的执行上下文

    每次函数调用都会创建一个新的 CallFrame，记录：
    - 当前执行到哪条指令（ip）
    - 函数的局部变量
    - 闭包捕获的变量（如果有）
    - 调用前的栈位置（用于返回时清理）

    Attributes:
        func:       闭包对象或 None（主函数时）
        ip:         指令指针（Instruction Pointer）
        locals:     局部变量字典
        captured:   闭包捕获的变量字典（可能为 None）
        stack_base: 该帧在 VM 栈上的起始位置
    """

    def __init__(self, func=None, ip: int = 0, locals_: dict = None,
                 captured: dict = None, stack_base: int = 0):
        self.func = func
        self.ip = ip
        self.locals = locals_ if locals_ is not None else {}
        self.captured = captured
        self.stack_base = stack_base


# ============================================================
#  虚拟机
# ============================================================

class VM:
    """基于栈的虚拟机

    执行 CompiledFunction 对象中的字节码。主程序被视为一个
    参数为空的特殊函数。

    使用方法：
        from tinylang.lexer import Lexer
        from tinylang.parser import Parser
        from tinylang.compiler import Compiler
        from tinylang.builtins import get_builtins
        from tinylang.vm import VM

        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()

        compiler = Compiler(get_builtins())
        main_func = compiler.compile(ast)

        vm = VM(get_builtins())
        vm.run(main_func)

    运行时栈的使用约定：
    - LOAD_* 指令将值压入栈
    - 算术/比较指令弹出操作数，压入结果
    - CALL 指令：栈上是 [callee, arg1, arg2, ..., argN]
      弹出参数和 callee，压入返回值
    - RETURN 指令：弹出返回值，恢复调用者的栈状态，压入返回值
    """

    def __init__(self, builtins: dict = None):
        self.stack: list = []          # 操作数栈
        self.frames: list[CallFrame] = []  # 调用栈
        self.globals_: dict = {}       # 全局变量
        self.builtins = builtins or {} # 内置函数
        self.output: list = []         # 输出捕获

    @property
    def current_frame(self) -> CallFrame:
        """获取当前调用栈帧"""
        return self.frames[-1]

    # ============================================================
    #  程序入口
    # ============================================================

    def run(self, main_func: CompiledFunction):
        """执行主函数

        将内置函数注册到全局变量，创建主函数的调用栈帧，
        然后进入主循环执行字节码。

        Args:
            main_func: 编译器生成的主函数对象
        """
        # 将内置函数注册到全局作用域
        for name, func in self.builtins.items():
            self.globals_[name] = func

        # 创建主函数的闭包和调用栈帧
        main_closure = Closure(main_func, {})
        frame = CallFrame(
            func=main_closure,
            ip=0,
            locals_=self.globals_,  # 主函数的"局部变量"就是全局变量
            captured=None,
            stack_base=0,
        )
        self.frames.append(frame)

        # 进入主执行循环
        self._run_loop()

    # ============================================================
    #  主执行循环
    # ============================================================

    def _run_loop(self):
        """主执行循环 —— 取指-解码-执行循环

        这是虚拟机的核心。每次迭代：
        1. 从当前帧的字节码中取出一条指令
        2. 指令指针前进
        3. 根据操作码执行对应的操作
        """
        while True:
            frame = self.current_frame
            chunk = frame.func.chunk if frame.func else None

            # 安全检查：如果当前没有有效的代码块，退出
            if chunk is None:
                break

            # 取指令
            if frame.ip >= len(chunk.code):
                break

            opcode = chunk.code[frame.ip]
            frame.ip += 1

            # ============================================================
            #  常量加载
            # ============================================================

            if opcode == Opcode.LOAD_CONST:
                idx = chunk.code[frame.ip]
                frame.ip += 1
                self.stack.append(chunk.constants[idx])

            elif opcode == Opcode.LOAD_TRUE:
                self.stack.append(True)

            elif opcode == Opcode.LOAD_FALSE:
                self.stack.append(False)

            elif opcode == Opcode.LOAD_NONE:
                self.stack.append(None)

            # ============================================================
            #  变量操作
            # ============================================================

            elif opcode == Opcode.LOAD_VAR:
                name_idx = chunk.code[frame.ip]
                frame.ip += 1
                name = chunk.constants[name_idx]
                value = self._resolve_var(name, frame)
                self.stack.append(value)

            elif opcode == Opcode.STORE_VAR:
                name_idx = chunk.code[frame.ip]
                frame.ip += 1
                name = chunk.constants[name_idx]
                value = self.stack[-1]  # STORE 不弹出值（保留在栈上）

                # 闭包自动捕获：函数定义在另一个函数内部时，
                # 自动将外层函数的局部变量作为闭包捕获变量
                if isinstance(value, CompiledFunction):
                    captured = dict(frame.locals)
                    if frame.captured:
                        captured.update(frame.captured)
                    value = Closure(value, captured)
                    self.stack[-1] = value  # 替换栈上的值

                self._assign_var(name, value, frame)

                # 闭包自引用：将函数自身加入捕获字典，支持递归调用
                if isinstance(value, Closure):
                    if value.captured is not None:
                        value.captured[name] = value

            # ============================================================
            #  算术运算
            # ============================================================

            elif opcode == Opcode.ADD:
                b = self.stack.pop()
                a = self.stack.pop()
                # 字符串拼接
                if isinstance(a, str) or isinstance(b, str):
                    self.stack.append(format_value(a) + format_value(b))
                else:
                    self.stack.append(a + b)

            elif opcode == Opcode.SUB:
                b = self.stack.pop()
                a = self.stack.pop()
                if not isinstance(a, (int, float)) or not isinstance(b, (int, float)):
                    raise RuntimeError_(f"运算符 '-' 不支持 {type(a).__name__} 和 {type(b).__name__}")
                self.stack.append(a - b)

            elif opcode == Opcode.MUL:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a * b)

            elif opcode == Opcode.DIV:
                b = self.stack.pop()
                a = self.stack.pop()
                if b == 0:
                    raise RuntimeError_("除以零")
                if isinstance(a, int) and isinstance(b, int):
                    self.stack.append(a // b)
                else:
                    self.stack.append(a / b)

            elif opcode == Opcode.MOD:
                b = self.stack.pop()
                a = self.stack.pop()
                if b == 0:
                    raise RuntimeError_("对零取模")
                self.stack.append(a % b)

            elif opcode == Opcode.NEGATE:
                a = self.stack.pop()
                self.stack.append(-a)

            # ============================================================
            #  比较运算
            # ============================================================

            elif opcode == Opcode.CMP_EQ:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a == b)

            elif opcode == Opcode.CMP_NEQ:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a != b)

            elif opcode == Opcode.CMP_LT:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a < b)

            elif opcode == Opcode.CMP_GT:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a > b)

            elif opcode == Opcode.CMP_LTE:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a <= b)

            elif opcode == Opcode.CMP_GTE:
                b = self.stack.pop()
                a = self.stack.pop()
                self.stack.append(a >= b)

            # ============================================================
            #  逻辑运算
            # ============================================================

            elif opcode == Opcode.AND:
                # 短路求值已在编译器中处理，这里做备选处理
                b = self.stack.pop()
                a = self.stack.pop()
                if self._is_truthy(a):
                    self.stack.append(b)
                else:
                    self.stack.append(a)

            elif opcode == Opcode.OR:
                b = self.stack.pop()
                a = self.stack.pop()
                if self._is_truthy(a):
                    self.stack.append(a)
                else:
                    self.stack.append(b)

            elif opcode == Opcode.NOT:
                a = self.stack.pop()
                self.stack.append(not self._is_truthy(a))

            # ============================================================
            #  栈操作
            # ============================================================

            elif opcode == Opcode.POP:
                self.stack.pop()

            elif opcode == Opcode.DUP:
                self.stack.append(self.stack[-1])

            # ============================================================
            #  跳转指令
            # ============================================================

            elif opcode == Opcode.JUMP:
                target = chunk.code[frame.ip]
                frame.ip = target  # 无条件跳转

            elif opcode == Opcode.JUMP_IF_FALSE:
                target = chunk.code[frame.ip]
                frame.ip += 1
                condition = self.stack.pop()  # 始终弹出条件值
                if not self._is_truthy(condition):
                    frame.ip = target

            elif opcode == Opcode.JUMP_IF_TRUE:
                target = chunk.code[frame.ip]
                frame.ip += 1
                condition = self.stack.pop()  # 始终弹出条件值
                if self._is_truthy(condition):
                    frame.ip = target

            # ============================================================
            #  函数调用和返回
            # ============================================================

            elif opcode == Opcode.CALL:
                arg_count = chunk.code[frame.ip]
                frame.ip += 1

                # 从栈上弹出参数（注意顺序：参数在被调用者之上）
                args = []
                for _ in range(arg_count):
                    args.append(self.stack.pop())
                args.reverse()  # 恢复正确顺序

                callee = self.stack.pop()

                self._setup_call(callee, args)

            elif opcode == Opcode.RETURN:
                value = self.stack.pop()
                self._do_return(value)

            # ============================================================
            #  数组操作
            # ============================================================

            elif opcode == Opcode.BUILD_ARRAY:
                count = chunk.code[frame.ip]
                frame.ip += 1
                elements = []
                for _ in range(count):
                    elements.append(self.stack.pop())
                elements.reverse()
                self.stack.append(elements)

            elif opcode == Opcode.GET_INDEX:
                index = self.stack.pop()
                array = self.stack.pop()
                if not isinstance(array, (list, str)):
                    raise RuntimeError_(
                        f"无法对 {type(array).__name__} 类型进行索引访问"
                    )
                idx = int(index)
                if idx < 0 or idx >= len(array):
                    raise RuntimeError_(
                        f"索引越界: {idx} (长度为 {len(array)})"
                    )
                self.stack.append(array[idx])

            elif opcode == Opcode.SET_INDEX:
                value = self.stack.pop()
                index = self.stack.pop()
                array = self.stack.pop()
                if not isinstance(array, list):
                    raise RuntimeError_("只能对数组进行索引赋值")
                array[int(index)] = value
                self.stack.append(value)

            elif opcode == Opcode.GET_LEN:
                val = self.stack.pop()
                if isinstance(val, (list, str)):
                    self.stack.append(len(val))
                else:
                    raise RuntimeError_(
                        f"len() 不支持 {type(val).__name__} 类型"
                    )

            # ============================================================
            #  停机
            # ============================================================

            elif opcode == Opcode.HALT:
                break

            else:
                raise RuntimeError_(f"未知的操作码: {opcode}")

    # ============================================================
    #  变量解析
    # ============================================================

    def _resolve_var(self, name: str, frame: CallFrame):
        """解析变量值

        按以下顺序查找：
        1. 当前帧的局部变量
        2. 闭包捕获的变量
        3. 全局变量

        Args:
            name:  变量名
            frame: 当前调用栈帧

        Returns:
            变量的值

        Raises:
            RuntimeError_: 变量未定义
        """
        # 1. 局部变量
        if name in frame.locals:
            return frame.locals[name]

        # 2. 闭包捕获的变量
        if frame.captured is not None and name in frame.captured:
            return frame.captured[name]

        # 3. 全局变量
        if name in self.globals_:
            return self.globals_[name]

        raise RuntimeError_(f"未定义的变量: '{name}'")

    def _assign_var(self, name: str, value, frame: CallFrame):
        """赋值变量

        按以下顺序查找并更新已存在的变量：
        1. 当前帧的局部变量（存在则更新）
        2. 闭包捕获的变量（存在则更新）
        3. 全局变量（存在则更新）
        4. 都不存在时，在当前帧的局部变量中新建

        Args:
            name:  变量名
            value: 新值
            frame: 当前调用栈帧
        """
        # 局部变量
        if name in frame.locals:
            frame.locals[name] = value
            return

        # 闭包捕获的变量
        if frame.captured is not None and name in frame.captured:
            frame.captured[name] = value
            return

        # 全局变量
        if name in self.globals_:
            self.globals_[name] = value
            return

        # 新变量默认存入局部变量
        frame.locals[name] = value

    # ============================================================
    #  函数调用管理
    # ============================================================

    def _setup_call(self, callee, args: list):
        """设置函数调用

        处理三种可调用对象：
        1. BuiltinFunction —— 直接调用 Python 函数，将返回值压入栈
        2. Closure —— 创建新的 CallFrame，压入调用栈
        3. CompiledFunction —— 包装为 Closure 后创建 CallFrame

        Args:
            callee: 被调用的对象
            args:   参数列表
        """
        # 内置函数：直接调用
        if isinstance(callee, BuiltinFunction):
            result = callee.func(args)
            self.stack.append(result)
            return

        # 闭包：创建新帧
        if isinstance(callee, Closure):
            if len(args) != callee.arity:
                raise RuntimeError_(
                    f"函数 '{callee.name}' 需要 {callee.arity} 个参数，"
                    f"但传入了 {len(args)} 个"
                )
            # 将参数绑定到新帧的局部变量
            locals_ = {}
            for i, param in enumerate(callee.params):
                locals_[param] = args[i]

            frame = CallFrame(
                func=callee,
                ip=0,
                locals_=locals_,
                captured=callee.captured,
                stack_base=len(self.stack),
            )
            self.frames.append(frame)
            return

        # 编译后的函数：包装为闭包
        if isinstance(callee, CompiledFunction):
            closure = Closure(callee, self.globals_)
            self._setup_call(closure, args)
            return

        raise RuntimeError_(f"不可调用的类型: {type(callee).__name__}")

    def _do_return(self, value):
        """处理函数返回

        1. 弹出当前调用栈帧
        2. 清理栈到调用前的位置
        3. 将返回值压入栈

        Args:
            value: 返回值
        """
        frame = self.frames.pop()
        # 清理栈：移除该帧使用的所有栈空间
        del self.stack[frame.stack_base:]
        # 压入返回值
        self.stack.append(value)

    # ============================================================
    #  辅助方法
    # ============================================================

    @staticmethod
    def _is_truthy(value) -> bool:
        """判断一个 TinyLang 值的真值

        与解释器中的 is_truthy 保持一致。
        """
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        if isinstance(value, str):
            return len(value) > 0
        if isinstance(value, list):
            return len(value) > 0
        return True
