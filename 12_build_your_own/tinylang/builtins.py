"""
内置函数定义

定义了 TinyLang 提供的所有内置函数。内置函数是语言自带的
功能，不需要用户定义即可使用。

内置函数列表：
- print(...)   打印值到标准输出
- len(x)       获取数组或字符串的长度
- type(x)      获取值的类型名称
- str(x)       将值转换为字符串
- int(x)       将值转换为整数
- float(x)     将值转换为浮点数
- range(...)   生成整数序列
- append(arr, val)  向数组追加元素

设计说明：
- 内置函数使用 BuiltinFunction 包装，使其可以像用户定义函数一样调用
- 所有内置函数接受一个参数列表（list），返回一个值
- 输出可以通过 output_list 参数捕获，便于测试
"""

from .errors import RuntimeError_


class BuiltinFunction:
    """内置函数包装类

    将一个 Python 函数包装为 TinyLang 的可调用对象。
    这样内置函数可以和用户定义的函数使用相同的调用机制。

    Attributes:
        name: 函数名
        func: 底层的 Python 函数
    """

    def __init__(self, name: str, func):
        self.name = name
        self.func = func

    def __repr__(self):
        return f"<builtin: {self.name}>"

    def __call__(self, args):
        return self.func(args)


def format_value(value) -> str:
    """将 TinyLang 值格式化为显示用的字符串

    格式化规则：
    - true/false -> "true"/"false"
    - none -> "none"
    - 数组 -> "[1, 2, 3]"
    - 其他 -> Python 的 str() 转换
    """
    if value is True:
        return "true"
    elif value is False:
        return "false"
    elif value is None:
        return "none"
    elif isinstance(value, list):
        return "[" + ", ".join(format_value(v) for v in value) + "]"
    else:
        return str(value)


def get_builtins(output_list: list = None) -> dict:
    """获取所有内置函数的字典

    Args:
        output_list: 可选的输出捕获列表。
                     如果提供，print 函数的输出会同时追加到此列表中。
                     这主要用于测试。

    Returns:
        字典，键为函数名，值为 BuiltinFunction 对象
    """
    builtins = {}

    # ---- print(...): 打印值 ----
    def _print(args):
        parts = [format_value(arg) for arg in args]
        text = " ".join(parts)
        if output_list is not None:
            output_list.append(text)
        print(text)
        return None

    builtins["print"] = BuiltinFunction("print", _print)

    # ---- len(x): 获取长度 ----
    def _len(args):
        if len(args) != 1:
            raise RuntimeError_("len() 需要恰好 1 个参数")
        val = args[0]
        if isinstance(val, (list, str)):
            return len(val)
        raise RuntimeError_(f"len() 不支持 {type(val).__name__} 类型")

    builtins["len"] = BuiltinFunction("len", _len)

    # ---- type(x): 获取类型名 ----
    def _type(args):
        if len(args) != 1:
            raise RuntimeError_("type() 需要恰好 1 个参数")
        val = args[0]
        if isinstance(val, bool):
            return "boolean"
        elif isinstance(val, int):
            return "integer"
        elif isinstance(val, float):
            return "float"
        elif isinstance(val, str):
            return "string"
        elif isinstance(val, list):
            return "array"
        elif val is None:
            return "none"
        elif isinstance(val, BuiltinFunction):
            return "builtin_function"
        else:
            return "unknown"

    builtins["type"] = BuiltinFunction("type", _type)

    # ---- str(x): 转换为字符串 ----
    def _str(args):
        if len(args) != 1:
            raise RuntimeError_("str() 需要恰好 1 个参数")
        return format_value(args[0])

    builtins["str"] = BuiltinFunction("str", _str)

    # ---- int(x): 转换为整数 ----
    def _int(args):
        if len(args) != 1:
            raise RuntimeError_("int() 需要恰好 1 个参数")
        val = args[0]
        if isinstance(val, bool):
            return 1 if val else 0
        if isinstance(val, (int, float)):
            return int(val)
        if isinstance(val, str):
            try:
                return int(val)
            except ValueError:
                try:
                    return int(float(val))
                except ValueError:
                    raise RuntimeError_(f"无法将 '{val}' 转换为整数")
        raise RuntimeError_(f"无法将 {type(val).__name__} 转换为整数")

    builtins["int"] = BuiltinFunction("int", _int)

    # ---- float(x): 转换为浮点数 ----
    def _float(args):
        if len(args) != 1:
            raise RuntimeError_("float() 需要恰好 1 个参数")
        val = args[0]
        if isinstance(val, bool):
            return 1.0 if val else 0.0
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val)
            except ValueError:
                raise RuntimeError_(f"无法将 '{val}' 转换为浮点数")
        raise RuntimeError_(f"无法将 {type(val).__name__} 转换为浮点数")

    builtins["float"] = BuiltinFunction("float", _float)

    # ---- range(...): 生成整数序列 ----
    # 用法：range(stop) 或 range(start, stop) 或 range(start, stop, step)
    def _range(args):
        if len(args) == 1:
            return list(range(int(args[0])))
        elif len(args) == 2:
            return list(range(int(args[0]), int(args[1])))
        elif len(args) == 3:
            return list(range(int(args[0]), int(args[1]), int(args[2])))
        else:
            raise RuntimeError_("range() 需要 1-3 个参数")

    builtins["range"] = BuiltinFunction("range", _range)

    # ---- append(arr, val): 向数组追加元素 ----
    def _append(args):
        if len(args) != 2:
            raise RuntimeError_("append() 需要恰好 2 个参数")
        if not isinstance(args[0], list):
            raise RuntimeError_("append() 的第一个参数必须是数组")
        args[0].append(args[1])
        return args[0]

    builtins["append"] = BuiltinFunction("append", _append)

    return builtins
