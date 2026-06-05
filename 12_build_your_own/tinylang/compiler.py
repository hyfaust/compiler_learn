"""
字节码编译器 (Bytecode Compiler)

将 AST 编译为字节码指令序列。编译器遍历 AST，为每个节点
生成对应的字节码指令，输出到 Chunk（字节码块）中。

编译器的核心职责：
- 将 AST 翻译为线性的字节码指令流
- 管理常量池（字面量和变量名）
- 处理控制流的跳转指令（需要回填 patch）
- 管理循环上下文（break/continue 的跳转目标）
- 为每个函数体编译独立的字节码块

设计决策：
- 变量通过常量池中的名称字符串引用（而非栈槽位索引）
- and/or 使用跳转指令实现短路求值
- for 循环使用临时变量管理迭代器和计数器
- 函数定义时创建独立的 Chunk，运行时包装为闭包
"""

from .ast_nodes import *
from .opcodes import Opcode, Chunk, CompiledFunction
from .builtins import BuiltinFunction
from .errors import CompileError


# ============================================================
#  循环上下文
# ============================================================

class LoopContext:
    """循环上下文 —— 跟踪 break/continue 的跳转目标

    Attributes:
        continue_addr: continue 应跳转到的地址（循环体开头或增量步骤）
        break_jumps:   需要回填的 break 跳转指令的操作数地址列表
    """

    def __init__(self, continue_addr: int = None):
        self.continue_addr = continue_addr
        self.break_jumps: list[int] = []


# ============================================================
#  字节码编译器
# ============================================================

class Compiler:
    """字节码编译器

    将 AST 编译为 CompiledFunction（包含字节码的函数对象）。
    主程序被视为一个名为 "<main>"、参数为空的函数。

    使用方法：
        from tinylang.lexer import Lexer
        from tinylang.parser import Parser
        from tinylang.compiler import Compiler
        from tinylang.builtins import get_builtins

        tokens = Lexer(source).tokenize()
        ast = Parser(tokens).parse()

        compiler = Compiler(get_builtins())
        main_func = compiler.compile(ast)

    编译过程中的栈管理：
    - 编译表达式时，指令将值压入运行时栈
    - 消费值的指令从栈上弹出操作数
    - 编译完一条表达式语句后，POP 掉不需要的值
    """

    def __init__(self, builtins: dict = None):
        self.builtins = builtins or {}
        self._main_chunk = Chunk()
        self._chunk_stack: list[Chunk] = [self._main_chunk]
        self._loop_stack: list[LoopContext] = []
        self._temp_counter = 0

    @property
    def _chunk(self) -> Chunk:
        """获取当前正在编译的 Chunk"""
        return self._chunk_stack[-1]

    # ============================================================
    #  指令发射辅助方法
    # ============================================================

    def _emit(self, opcode: int, operand: int = None, line: int = 0):
        """向当前 Chunk 发射一条指令"""
        self._chunk.emit_op(opcode, operand, line)

    def _emit_const(self, value, line: int = 0) -> int:
        """向常量池添加值并发射 LOAD_CONST 指令

        Returns:
            常量在常量池中的索引
        """
        idx = self._chunk.add_constant(value)
        self._emit(Opcode.LOAD_CONST, idx, line)
        return idx

    def _emit_jump(self, opcode: int) -> int:
        """发射跳转指令，使用占位符目标地址

        Returns:
            操作数（目标地址）在 code 列表中的位置，用于后续回填
        """
        self._emit(opcode)
        pos = len(self._chunk.code)
        self._emit(0)  # 占位符
        return pos

    def _patch_jump(self, pos: int):
        """回填跳转指令的目标地址为当前位置"""
        self._chunk.code[pos] = len(self._chunk.code)

    def _new_temp(self, prefix: str) -> str:
        """生成唯一的临时变量名

        用于 for 循环的迭代器和计数器等内部变量。
        使用 __ 前缀和后缀避免与用户变量冲突。
        """
        name = f"__{prefix}_{self._temp_counter}__"
        self._temp_counter += 1
        return name

    def _add_name(self, name: str) -> int:
        """将变量名添加到常量池，返回索引"""
        return self._chunk.add_constant(name)

    # ============================================================
    #  循环上下文管理
    # ============================================================

    def _push_loop(self, continue_addr: int = None):
        """进入循环，压入新的循环上下文"""
        self._loop_stack.append(LoopContext(continue_addr))

    def _pop_loop(self):
        """退出循环，回填所有 break 跳转"""
        ctx = self._loop_stack.pop()
        for break_pos in ctx.break_jumps:
            self._patch_jump(break_pos)

    def _current_loop(self) -> LoopContext:
        """获取当前循环上下文"""
        if not self._loop_stack:
            return None
        return self._loop_stack[-1]

    # ============================================================
    #  主编译入口
    # ============================================================

    def compile(self, program: Program) -> CompiledFunction:
        """编译整个程序，返回主函数对象"""
        for stmt in program.statements:
            self._compile_stmt(stmt)

        # 程序末尾：确保有 HALT 指令
        self._emit(Opcode.HALT)

        return CompiledFunction("<main>", [], self._main_chunk)

    # ============================================================
    #  语句编译
    # ============================================================

    def _compile_stmt(self, node: Statement):
        """编译一条语句"""

        # let 声明
        if isinstance(node, LetStatement):
            self._compile_expr(node.value)
            self._emit(Opcode.STORE_VAR, self._add_name(node.name))
            return

        # 赋值
        if isinstance(node, AssignmentStatement):
            if isinstance(node.target, Identifier):
                self._compile_expr(node.value)
                self._emit(Opcode.STORE_VAR, self._add_name(node.target.name))
            elif isinstance(node.target, IndexExpression):
                self._compile_expr(node.target.array)
                self._compile_expr(node.target.index)
                self._compile_expr(node.value)
                self._emit(Opcode.SET_INDEX)
            return

        # 表达式语句（丢弃结果值）
        if isinstance(node, ExpressionStatement):
            self._compile_expr(node.expression)
            self._emit(Opcode.POP)
            return

        # if/elif/else
        if isinstance(node, IfStatement):
            self._compile_if(node)
            return

        # while 循环
        if isinstance(node, WhileStatement):
            self._compile_while(node)
            return

        # for-in 循环
        if isinstance(node, ForStatement):
            self._compile_for(node)
            return

        # 函数定义
        if isinstance(node, FunctionDef):
            self._compile_func_def(node)
            return

        # return
        if isinstance(node, ReturnStatement):
            if node.value is not None:
                self._compile_expr(node.value)
            else:
                self._emit(Opcode.LOAD_NONE)
            self._emit(Opcode.RETURN)
            return

        # break
        if isinstance(node, BreakStatement):
            loop = self._current_loop()
            if loop is None:
                raise CompileError("'break' 必须在循环内部使用")
            pos = self._emit_jump(Opcode.JUMP)
            loop.break_jumps.append(pos)
            return

        # continue
        if isinstance(node, ContinueStatement):
            loop = self._current_loop()
            if loop is None:
                raise CompileError("'continue' 必须在循环内部使用")
            if loop.continue_addr is None:
                raise CompileError("'continue' 在当前位置无效")
            self._emit(Opcode.JUMP)
            self._emit(loop.continue_addr)
            return

        raise CompileError(f"未知的语句类型: {type(node).__name__}")

    def _compile_stmts(self, statements: list):
        """编译一组语句"""
        for stmt in statements:
            self._compile_stmt(stmt)

    # ============================================================
    #  复合语句编译
    # ============================================================

    def _compile_if(self, node: IfStatement):
        """编译 if/elif/else 语句

        生成的字节码结构：
            <条件>               ; 压入条件值
            JUMP_IF_FALSE elif1  ; 为假则跳到下一个分支
            <then_body>
            JUMP end             ; 跳到末尾
        elif1:
            <条件>
            JUMP_IF_FALSE else1
            <elif_body>
            JUMP end
        else1:
            <else_body>
        end:
        """
        end_jumps = []

        # 主 if 分支
        self._compile_expr(node.condition)
        else_jump = self._emit_jump(Opcode.JUMP_IF_FALSE)
        self._compile_stmts(node.then_body)
        end_jumps.append(self._emit_jump(Opcode.JUMP))
        self._patch_jump(else_jump)

        # elif 分支
        for elif_cond, elif_body in node.elif_clauses:
            self._compile_expr(elif_cond)
            elif_jump = self._emit_jump(Opcode.JUMP_IF_FALSE)
            self._compile_stmts(elif_body)
            end_jumps.append(self._emit_jump(Opcode.JUMP))
            self._patch_jump(elif_jump)

        # else 分支
        if node.else_body is not None:
            self._compile_stmts(node.else_body)

        # 回填所有跳到末尾的指令
        for jump_pos in end_jumps:
            self._patch_jump(jump_pos)

    def _compile_while(self, node: WhileStatement):
        """编译 while 循环

        字节码结构：
        loop_start:
            <条件>
            JUMP_IF_FALSE loop_end
            <body>
            JUMP loop_start
        loop_end:
        """
        loop_start = len(self._chunk.code)
        self._push_loop(loop_start)  # continue 跳到条件检查

        self._compile_expr(node.condition)
        end_jump = self._emit_jump(Opcode.JUMP_IF_FALSE)

        self._compile_stmts(node.body)

        # 跳回循环开头
        self._emit(Opcode.JUMP)
        self._emit(loop_start)

        # 回填循环结束跳转
        self._patch_jump(end_jump)
        self._pop_loop()  # 回填 break 跳转

    def _compile_for(self, node: ForStatement):
        """编译 for-in 循环

        字节码结构：
            <iterable>              ; 求值可迭代对象
            STORE_VAR __iter_N__    ; 存储到临时变量
            LOAD_CONST 0
            STORE_VAR __idx_N__     ; 计数器初始化为 0
        loop_start:
            LOAD_VAR __idx_N__      ; 压入计数器
            LOAD_VAR __iter_N__     ; 压入可迭代对象
            GET_LEN                 ; 获取长度
            CMP_LT                  ; 比较: idx < len
            JUMP_IF_FALSE loop_end
            ; 获取元素
            LOAD_VAR __iter_N__
            LOAD_VAR __idx_N__
            GET_INDEX
            STORE_VAR var_name      ; 存储到循环变量
            <body>
        continue_target:
            ; 递增计数器
            LOAD_VAR __idx_N__
            LOAD_CONST 1
            ADD
            STORE_VAR __idx_N__
            JUMP loop_start
        loop_end:
        """
        # 生成临时变量名
        iter_name = self._new_temp("iter")
        idx_name = self._new_temp("idx")

        # 预先将名称添加到常量池
        iter_name_idx = self._add_name(iter_name)
        idx_name_idx = self._add_name(idx_name)
        var_name_idx = self._add_name(node.var_name)

        # 编译可迭代对象并存储
        self._compile_expr(node.iterable)
        self._emit(Opcode.STORE_VAR, iter_name_idx)

        # 初始化计数器为 0
        self._chunk.add_constant(0)
        self._emit(Opcode.LOAD_CONST, len(self._chunk.constants) - 1)
        self._emit(Opcode.STORE_VAR, idx_name_idx)

        # ---- 循环条件 ----
        loop_start = len(self._chunk.code)

        self._emit(Opcode.LOAD_VAR, idx_name_idx)
        self._emit(Opcode.LOAD_VAR, iter_name_idx)
        self._emit(Opcode.GET_LEN)
        self._emit(Opcode.CMP_LT)
        end_jump = self._emit_jump(Opcode.JUMP_IF_FALSE)

        # 压入循环上下文（continue 目标稍后设置）
        self._push_loop(None)

        # ---- 获取当前元素 ----
        self._emit(Opcode.LOAD_VAR, iter_name_idx)
        self._emit(Opcode.LOAD_VAR, idx_name_idx)
        self._emit(Opcode.GET_INDEX)
        self._emit(Opcode.STORE_VAR, var_name_idx)

        # ---- 循环体 ----
        self._compile_stmts(node.body)

        # ---- continue 目标：递增计数器 ----
        self._current_loop().continue_addr = len(self._chunk.code)

        self._emit(Opcode.LOAD_VAR, idx_name_idx)
        one_idx = self._chunk.add_constant(1)
        self._emit(Opcode.LOAD_CONST, one_idx)
        self._emit(Opcode.ADD)
        self._emit(Opcode.STORE_VAR, idx_name_idx)

        # 跳回循环条件
        self._emit(Opcode.JUMP)
        self._emit(loop_start)

        # ---- 循环结束 ----
        self._patch_jump(end_jump)
        self._pop_loop()  # 回填 break 跳转

    def _compile_func_def(self, node: FunctionDef):
        """编译函数定义

        编译流程：
        1. 创建新的 Chunk 用于函数体
        2. 切换到新 Chunk，编译函数体
        3. 在函数体末尾添加隐式 return none
        4. 切换回原来的 Chunk
        5. 将编译后的函数作为常量存入常量池
        6. 发射 STORE_VAR 将函数绑定到变量名
        """
        # 保存当前 Chunk，切换到函数的 Chunk
        func_chunk = Chunk()
        self._chunk_stack.append(func_chunk)

        # 编译函数体
        self._compile_stmts(node.body)

        # 隐式 return none（如果没有显式 return）
        self._emit(Opcode.LOAD_NONE)
        self._emit(Opcode.RETURN)

        # 恢复之前的 Chunk
        self._chunk_stack.pop()

        # 创建编译后的函数对象
        func = CompiledFunction(node.name or "<anonymous>", node.params, func_chunk)

        # 将函数作为常量存入父 Chunk
        const_idx = self._chunk.add_constant(func)
        self._emit(Opcode.LOAD_CONST, const_idx)

        # 绑定到变量名（匿名函数跳过）
        if node.name is not None:
            name_idx = self._add_name(node.name)
            self._emit(Opcode.STORE_VAR, name_idx)

    # ============================================================
    #  表达式编译
    # ============================================================

    def _compile_expr(self, node: Expression):
        """编译一个表达式，使其在运行时栈上产生一个值"""

        # ---- 字面量 ----
        if isinstance(node, IntegerLiteral):
            self._emit_const(node.value)
            return
        if isinstance(node, FloatLiteral):
            self._emit_const(node.value)
            return
        if isinstance(node, StringLiteral):
            self._emit_const(node.value)
            return
        if isinstance(node, BooleanLiteral):
            self._emit(Opcode.LOAD_TRUE if node.value else Opcode.LOAD_FALSE)
            return
        if isinstance(node, NoneLiteral):
            self._emit(Opcode.LOAD_NONE)
            return

        # ---- 标识符 ----
        if isinstance(node, Identifier):
            self._emit(Opcode.LOAD_VAR, self._add_name(node.name))
            return

        # ---- 数组字面量 ----
        if isinstance(node, ArrayLiteral):
            for elem in node.elements:
                self._compile_expr(elem)
            self._emit(Opcode.BUILD_ARRAY, len(node.elements))
            return

        # ---- 索引访问 ----
        if isinstance(node, IndexExpression):
            self._compile_expr(node.array)
            self._compile_expr(node.index)
            self._emit(Opcode.GET_INDEX)
            return

        # ---- 二元运算 ----
        if isinstance(node, BinaryOp):
            self._compile_binary(node)
            return

        # ---- 一元运算 ----
        if isinstance(node, UnaryOp):
            self._compile_unary(node)
            return

        # ---- 函数调用 ----
        if isinstance(node, CallExpression):
            self._compile_call(node)
            return

        # ---- 匿名函数 ----
        if isinstance(node, FunctionDef):
            self._compile_func_def(node)
            return

        raise CompileError(f"未知的表达式类型: {type(node).__name__}")

    def _compile_binary(self, node: BinaryOp):
        """编译二元运算表达式

        特殊处理 and/or：使用 DUP + 条件跳转实现短路求值。
        """
        # ---- 短路求值: a and b ----
        if node.op == "and":
            self._compile_expr(node.left)
            self._emit(Opcode.DUP)
            end_jump = self._emit_jump(Opcode.JUMP_IF_FALSE)
            self._emit(Opcode.POP)
            self._compile_expr(node.right)
            self._patch_jump(end_jump)
            return

        # ---- 短路求值: a or b ----
        if node.op == "or":
            self._compile_expr(node.left)
            self._emit(Opcode.DUP)
            end_jump = self._emit_jump(Opcode.JUMP_IF_TRUE)
            self._emit(Opcode.POP)
            self._compile_expr(node.right)
            self._patch_jump(end_jump)
            return

        # ---- 普通运算：先编译左右操作数 ----
        self._compile_expr(node.left)
        self._compile_expr(node.right)

        # 发射对应的运算指令
        op_map = {
            "+":  Opcode.ADD,
            "-":  Opcode.SUB,
            "*":  Opcode.MUL,
            "/":  Opcode.DIV,
            "%":  Opcode.MOD,
            "==": Opcode.CMP_EQ,
            "!=": Opcode.CMP_NEQ,
            "<":  Opcode.CMP_LT,
            ">":  Opcode.CMP_GT,
            "<=": Opcode.CMP_LTE,
            ">=": Opcode.CMP_GTE,
        }

        if node.op in op_map:
            self._emit(op_map[node.op])
        else:
            raise CompileError(f"未知的二元运算符: {node.op}")

    def _compile_unary(self, node: UnaryOp):
        """编译一元运算表达式"""
        self._compile_expr(node.operand)
        if node.op == "-":
            self._emit(Opcode.NEGATE)
        elif node.op == "not":
            self._emit(Opcode.NOT)
        else:
            raise CompileError(f"未知的一元运算符: {node.op}")

    def _compile_call(self, node: CallExpression):
        """编译函数调用

        字节码顺序：
        1. 编译被调用者（将其压入栈）
        2. 依次编译每个参数（压入栈）
        3. 发射 CALL 指令，参数为参数个数

        运行时，CALL 指令从栈上弹出参数和被调用者，执行函数，
        然后将返回值压入栈。
        """
        self._compile_expr(node.callee)
        for arg in node.args:
            self._compile_expr(arg)
        self._emit(Opcode.CALL, len(node.args))
