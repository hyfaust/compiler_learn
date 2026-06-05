"""
作用域环境 (Environment)

实现了变量的作用域管理，支持词法作用域（lexical scoping）。
Environment 是树遍历解释器的核心组件，用于管理变量的
定义、查找和修改。

作用域链的设计：
- 每个 Environment 持有一层作用域的变量
- 通过 parent 指针链接到外层作用域
- 变量查找沿作用域链向上搜索
- 变量修改找到最近的同名变量并更新
- 新变量总是定义在当前（最内层）作用域

这种设计自然支持：
- 块级作用域（if/while/for 创建新环境）
- 闭包（函数捕获定义时的环境）
"""


class Environment:
    """作用域环境 —— 管理变量的作用域链

    Attributes:
        vars:   当前作用域的变量字典
        parent: 外层作用域的 Environment（最外层为 None）

    使用示例：
        global_env = Environment()
        global_env.define("x", 42)

        local_env = Environment(global_env)
        local_env.define("y", 10)
        local_env.get("x")  # -> 42 (沿作用域链找到)
        local_env.get("y")  # -> 10 (在当前作用域找到)
    """

    def __init__(self, parent: "Environment" = None):
        self.vars: dict = {}
        self.parent: Environment | None = parent

    def define(self, name: str, value):
        """在当前作用域定义一个新变量

        如果同名变量已存在于当前作用域，会被覆盖。
        这是 let 声明语句使用的操作。

        Args:
            name:  变量名
            value: 变量的初始值
        """
        self.vars[name] = value

    def get(self, name: str):
        """查找变量的值（沿作用域链向上搜索）

        查找顺序：当前作用域 -> 父作用域 -> ... -> 最外层作用域
        如果找不到，抛出 RuntimeError_。

        Args:
            name: 变量名

        Returns:
            变量的值

        Raises:
            RuntimeError_: 变量未定义
        """
        if name in self.vars:
            return self.vars[name]
        if self.parent is not None:
            return self.parent.get(name)
        from .errors import RuntimeError_
        raise RuntimeError_(f"未定义的变量: '{name}'")

    def set(self, name: str, value):
        """修改一个已存在的变量（沿作用域链查找并更新）

        这是赋值语句（x = 5）使用的操作。
        如果变量不存在于任何作用域，抛出 RuntimeError_。

        注意：这与 define 不同 —— set 要求变量必须已存在，
        而 define 总是在当前作用域创建新变量。

        Args:
            name:  变量名
            value: 新值

        Raises:
            RuntimeError_: 变量未定义
        """
        if name in self.vars:
            self.vars[name] = value
            return
        if self.parent is not None:
            self.parent.set(name, value)
            return
        from .errors import RuntimeError_
        raise RuntimeError_(f"未定义的变量: '{name}'")

    def has(self, name: str) -> bool:
        """检查变量是否在作用域链中的任何位置定义"""
        if name in self.vars:
            return True
        if self.parent is not None:
            return self.parent.has(name)
        return False

    def __repr__(self):
        scope_depth = 0
        env = self
        while env.parent is not None:
            scope_depth += 1
            env = env.parent
        return f"Environment(depth={scope_depth}, vars={list(self.vars.keys())})"
