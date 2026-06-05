"""
TinyLang 错误类型定义

定义了编译流程中各阶段可能出现的错误类型，所有错误都包含
源代码位置信息（行号、列号），便于提供友好的错误提示。
"""


class TinyLangError(Exception):
    """TinyLang 所有错误的基类"""

    def __init__(self, message, line=None, column=None):
        self.message = message
        self.line = line
        self.column = column
        super().__init__(self.format_message())

    def format_message(self):
        if self.line is not None:
            if self.column is not None:
                return f"[行 {self.line}, 列 {self.column}] {self.message}"
            return f"[行 {self.line}] {self.message}"
        return self.message


class LexerError(TinyLangError):
    """词法分析阶段的错误

    当词法分析器遇到无法识别的字符、未终止的字符串等情况时抛出。
    """
    pass


class ParserError(TinyLangError):
    """语法分析阶段的错误

    当解析器遇到不符合语法规则的 token 序列时抛出。
    """
    pass


class RuntimeError_(TinyLangError):
    """运行时错误

    在解释器或虚拟机执行过程中，当出现类型错误、除零错误、
    未定义变量等情况时抛出。

    注意：名称末尾的下划线是为了避免与 Python 内置的
    RuntimeError 名称冲突。
    """
    pass


class CompileError(TinyLangError):
    """编译阶段的错误

    当字节码编译器遇到无法编译的 AST 结构时抛出，
    例如在循环外部使用 break/continue。
    """
    pass
