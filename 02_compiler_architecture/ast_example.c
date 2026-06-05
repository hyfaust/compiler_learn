/* ============================================================
 * ast_example.c - AST节点定义和操作示例
 *
 * 本文件实现了编译器中抽象语法树(AST)的核心数据结构，包括:
 *   - 节点类型枚举（表达式、语句、声明）
 *   - 各类节点的创建函数
 *   - 带缩进的AST打印函数（可视化树结构）
 *   - 节点内存管理（创建和释放）
 *   - 完整示例：构建一个简单程序的AST并打印
 *
 * 编译: gcc -Wall -Wextra -o ast_example ast_example.c
 * 运行: ./ast_example
 *
 * AST是语法分析器的输出。与源代码相比，AST省略了
 * 括号、分号、逗号等语法糖，只保留语义相关的结构。
 * 后续的语义分析、中间代码生成都基于AST进行。
 * ============================================================ */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* ============================================================
 * 节点类型枚举
 * ============================================================ */

/* AST节点类型 */
typedef enum {
    /* ---- 表达式节点 ---- */
    NODE_INT_LITERAL,      /* 整数字面量: 42 */
    NODE_FLOAT_LITERAL,    /* 浮点字面量: 3.14 */
    NODE_STRING_LITERAL,   /* 字符串字面量: "hello" */
    NODE_BOOL_LITERAL,     /* 布尔字面量: true, false */
    NODE_IDENTIFIER,       /* 标识符引用: x, foo */

    NODE_BINARY_OP,        /* 二元运算: a + b, x * y */
    NODE_UNARY_OP,         /* 一元运算: -x, !flag */
    NODE_ASSIGN,           /* 赋值: x = expr */
    NODE_COMPOUND_ASSIGN,  /* 复合赋值: x += expr */
    NODE_FUNC_CALL,        /* 函数调用: foo(a, b) */
    NODE_ARRAY_ACCESS,     /* 数组访问: arr[i] */
    NODE_MEMBER_ACCESS,    /* 成员访问: obj.field */
    NODE_TERNARY,          /* 三元表达式: cond ? a : b */
    NODE_CAST,             /* 类型转换: (int)x */
    NODE_SIZEOF,           /* sizeof 表达式 */
    NODE_ADDR_OF,          /* 取地址: &x */
    NODE_DEREF,            /* 解引用: *ptr */

    /* ---- 语句节点 ---- */
    NODE_COMPOUND,         /* 复合语句(代码块): { stmts... } */
    NODE_IF,               /* if语句 */
    NODE_WHILE,            /* while循环 */
    NODE_FOR,              /* for循环 */
    NODE_DO_WHILE,         /* do-while循环 */
    NODE_RETURN,           /* return语句 */
    NODE_BREAK,            /* break语句 */
    NODE_CONTINUE,         /* continue语句 */
    NODE_EXPR_STMT,        /* 表达式语句: expr; */
    NODE_SWITCH,           /* switch语句 */

    /* ---- 声明节点 ---- */
    NODE_VAR_DECL,         /* 变量声明: int x = 5; */
    NODE_FUNC_DECL,        /* 函数声明/定义 */
    NODE_PARAM_DECL,       /* 函数参数声明 */
    NODE_STRUCT_DECL,      /* 结构体声明 */
    NODE_TYPEDEF_DECL,     /* typedef声明 */
    NODE_PROGRAM,          /* 程序根节点（翻译单元） */
} NodeType;

/* 运算符类型 */
typedef enum {
    OP_ADD, OP_SUB, OP_MUL, OP_DIV, OP_MOD,
    OP_EQ, OP_NE, OP_LT, OP_GT, OP_LE, OP_GE,
    OP_AND, OP_OR, OP_NOT,
    OP_BIT_AND, OP_BIT_OR, OP_BIT_XOR, OP_BIT_NOT,
    OP_SHIFT_LEFT, OP_SHIFT_RIGHT,
    OP_POSITIVE, OP_NEGATIVE, /* 一元 +, - */
    OP_PRE_INC, OP_PRE_DEC,   /* 前缀 ++, -- */
    OP_POST_INC, OP_POST_DEC, /* 后缀 ++, -- */
    OP_DEREF, OP_ADDR_OF,     /* *, & */
} Operator;

/* ============================================================
 * AST节点定义
 *
 * 使用联合体(union)来存储不同类型节点的特有数据。
 * 这种设计比使用继承更C风格，但同样清晰。
 * ============================================================ */

typedef struct ASTNode ASTNode;

/* AST节点基类 */
struct ASTNode {
    NodeType type;           /* 节点类型 */
    int line;                /* 源码行号 */
    int column;              /* 源码列号 */

    union {
        /* ---- 字面量 ---- */
        struct { long value; }                          int_lit;
        struct { double value; }                        float_lit;
        struct { char *value; }                         string_lit;
        struct { int value; }                           bool_lit;   /* 0=false, 1=true */
        struct { char *name; }                          ident;

        /* ---- 二元运算 ---- */
        struct {
            Operator op;
            ASTNode *left;
            ASTNode *right;
        } binary;

        /* ---- 一元运算 ---- */
        struct {
            Operator op;
            ASTNode *operand;
            int is_prefix;    /* 1=前缀, 0=后缀 */
        } unary;

        /* ---- 赋值 ---- */
        struct {
            ASTNode *target;
            ASTNode *value;
        } assign;

        /* ---- 复合赋值 ---- */
        struct {
            Operator op;      /* += 的OP_ADD, -= 的OP_SUB 等 */
            ASTNode *target;
            ASTNode *value;
        } compound_assign;

        /* ---- 函数调用 ---- */
        struct {
            char *func_name;
            ASTNode **args;   /* 参数列表 */
            int arg_count;
        } func_call;

        /* ---- 数组访问 ---- */
        struct {
            ASTNode *array;
            ASTNode *index;
        } array_access;

        /* ---- 成员访问 ---- */
        struct {
            ASTNode *object;
            char *member_name;
            int is_arrow;     /* 1=->, 0=. */
        } member_access;

        /* ---- 三元表达式 ---- */
        struct {
            ASTNode *condition;
            ASTNode *then_expr;
            ASTNode *else_expr;
        } ternary;

        /* ---- 类型转换 ---- */
        struct {
            char *target_type;
            ASTNode *expr;
        } cast;

        /* ---- sizeof ---- */
        struct {
            ASTNode *expr;    /* sizeof(expr) */
            char *type_name;  /* sizeof(type) -- 二选一 */
        } sizeof_expr;

        /* ---- 复合语句(代码块) ---- */
        struct {
            ASTNode **stmts;
            int stmt_count;
            int stmt_capacity;
        } compound;

        /* ---- if语句 ---- */
        struct {
            ASTNode *condition;
            ASTNode *then_branch;
            ASTNode *else_branch;   /* 可为NULL */
        } if_stmt;

        /* ---- while循环 ---- */
        struct {
            ASTNode *condition;
            ASTNode *body;
        } while_stmt;

        /* ---- for循环 ---- */
        struct {
            ASTNode *init;       /* 初始化（可为NULL） */
            ASTNode *condition;  /* 条件（可为NULL） */
            ASTNode *update;     /* 更新（可为NULL） */
            ASTNode *body;
        } for_stmt;

        /* ---- do-while循环 ---- */
        struct {
            ASTNode *body;
            ASTNode *condition;
        } do_while_stmt;

        /* ---- return语句 ---- */
        struct {
            ASTNode *value;  /* 可为NULL (return;) */
        } return_stmt;

        /* ---- 表达式语句 ---- */
        struct {
            ASTNode *expr;   /* 可为NULL (空语句 ;) */
        } expr_stmt;

        /* ---- switch语句 ---- */
        struct {
            ASTNode *expr;
            ASTNode **cases;      /* case列表 */
            ASTNode **case_bodies; /* 对应的case体 */
            int case_count;
            ASTNode *default_body; /* default体（可为NULL） */
        } switch_stmt;

        /* ---- 变量声明 ---- */
        struct {
            char *type_name;   /* 类型名: "int", "char*", ... */
            char *var_name;    /* 变量名 */
            ASTNode *init;     /* 初始化表达式（可为NULL） */
            int is_const;      /* 是否为const */
            int is_static;     /* 是否为static */
        } var_decl;

        /* ---- 函数声明 ---- */
        struct {
            char *return_type;
            char *func_name;
            ASTNode **params;
            int param_count;
            ASTNode *body;     /* 函数体（可为NULL表示仅有声明） */
            int is_static;
        } func_decl;

        /* ---- 参数声明 ---- */
        struct {
            char *type_name;
            char *param_name;
        } param_decl;

        /* ---- 程序根节点 ---- */
        struct {
            ASTNode **declarations;
            int decl_count;
            int decl_capacity;
        } program;
    } as;
};

/* ============================================================
 * 运算符字符串表示
 * ============================================================ */

const char* op_to_string(Operator op) {
    switch (op) {
        case OP_ADD:        return "+";
        case OP_SUB:        return "-";
        case OP_MUL:        return "*";
        case OP_DIV:        return "/";
        case OP_MOD:        return "%";
        case OP_EQ:         return "==";
        case OP_NE:         return "!=";
        case OP_LT:         return "<";
        case OP_GT:         return ">";
        case OP_LE:         return "<=";
        case OP_GE:         return ">=";
        case OP_AND:        return "&&";
        case OP_OR:         return "||";
        case OP_NOT:        return "!";
        case OP_BIT_AND:    return "&";
        case OP_BIT_OR:     return "|";
        case OP_BIT_XOR:    return "^";
        case OP_BIT_NOT:    return "~";
        case OP_SHIFT_LEFT: return "<<";
        case OP_SHIFT_RIGHT:return ">>";
        case OP_POSITIVE:   return "+";
        case OP_NEGATIVE:   return "-";
        case OP_PRE_INC:    return "++";
        case OP_PRE_DEC:    return "--";
        case OP_POST_INC:   return "++";
        case OP_POST_DEC:   return "--";
        case OP_DEREF:      return "*";
        case OP_ADDR_OF:    return "&";
    }
    return "???";
}

/* ============================================================
 * 节点类型名称（用于调试输出）
 * ============================================================ */

const char* node_type_name(NodeType type) {
    switch (type) {
        case NODE_INT_LITERAL:      return "IntLiteral";
        case NODE_FLOAT_LITERAL:    return "FloatLiteral";
        case NODE_STRING_LITERAL:   return "StringLiteral";
        case NODE_BOOL_LITERAL:     return "BoolLiteral";
        case NODE_IDENTIFIER:       return "Identifier";
        case NODE_BINARY_OP:        return "BinaryOp";
        case NODE_UNARY_OP:         return "UnaryOp";
        case NODE_ASSIGN:           return "Assign";
        case NODE_COMPOUND_ASSIGN:  return "CompoundAssign";
        case NODE_FUNC_CALL:        return "FuncCall";
        case NODE_ARRAY_ACCESS:     return "ArrayAccess";
        case NODE_MEMBER_ACCESS:    return "MemberAccess";
        case NODE_TERNARY:          return "Ternary";
        case NODE_CAST:             return "Cast";
        case NODE_SIZEOF:           return "Sizeof";
        case NODE_ADDR_OF:          return "AddrOf";
        case NODE_DEREF:            return "Deref";
        case NODE_COMPOUND:         return "Compound";
        case NODE_IF:               return "If";
        case NODE_WHILE:            return "While";
        case NODE_FOR:              return "For";
        case NODE_DO_WHILE:         return "DoWhile";
        case NODE_RETURN:           return "Return";
        case NODE_BREAK:            return "Break";
        case NODE_CONTINUE:         return "Continue";
        case NODE_EXPR_STMT:        return "ExprStmt";
        case NODE_SWITCH:           return "Switch";
        case NODE_VAR_DECL:         return "VarDecl";
        case NODE_FUNC_DECL:        return "FuncDecl";
        case NODE_PARAM_DECL:       return "ParamDecl";
        case NODE_STRUCT_DECL:      return "StructDecl";
        case NODE_TYPEDEF_DECL:     return "TypedefDecl";
        case NODE_PROGRAM:          return "Program";
    }
    return "???";
}

/* ============================================================
 * 节点创建函数
 *
 * 每个 create_xxx 函数分配一个ASTNode，设置类型和行号，
 * 初始化特有字段，并返回指针。
 * ============================================================ */

/* 辅助: 分配并初始化节点基类 */
static ASTNode* alloc_node(NodeType type, int line) {
    ASTNode *node = (ASTNode*)calloc(1, sizeof(ASTNode));
    if (!node) {
        fprintf(stderr, "Error: out of memory\n");
        exit(1);
    }
    node->type = type;
    node->line = line;
    return node;
}

/* 整数字面量 */
ASTNode* create_int_literal(long value, int line) {
    ASTNode *node = alloc_node(NODE_INT_LITERAL, line);
    node->as.int_lit.value = value;
    return node;
}

/* 浮点字面量 */
ASTNode* create_float_literal(double value, int line) {
    ASTNode *node = alloc_node(NODE_FLOAT_LITERAL, line);
    node->as.float_lit.value = value;
    return node;
}

/* 字符串字面量 */
ASTNode* create_string_literal(const char *value, int line) {
    ASTNode *node = alloc_node(NODE_STRING_LITERAL, line);
    node->as.string_lit.value = strdup(value);
    return node;
}

/* 布尔字面量 */
ASTNode* create_bool_literal(int value, int line) {
    ASTNode *node = alloc_node(NODE_BOOL_LITERAL, line);
    node->as.bool_lit.value = value;
    return node;
}

/* 标识符 */
ASTNode* create_identifier(const char *name, int line) {
    ASTNode *node = alloc_node(NODE_IDENTIFIER, line);
    node->as.ident.name = strdup(name);
    return node;
}

/* 二元运算 */
ASTNode* create_binary_op(Operator op, ASTNode *left, ASTNode *right, int line) {
    ASTNode *node = alloc_node(NODE_BINARY_OP, line);
    node->as.binary.op = op;
    node->as.binary.left = left;
    node->as.binary.right = right;
    return node;
}

/* 一元运算 */
ASTNode* create_unary_op(Operator op, ASTNode *operand, int is_prefix, int line) {
    ASTNode *node = alloc_node(NODE_UNARY_OP, line);
    node->as.unary.op = op;
    node->as.unary.operand = operand;
    node->as.unary.is_prefix = is_prefix;
    return node;
}

/* 赋值 */
ASTNode* create_assignment(ASTNode *target, ASTNode *value, int line) {
    ASTNode *node = alloc_node(NODE_ASSIGN, line);
    node->as.assign.target = target;
    node->as.assign.value = value;
    return node;
}

/* 函数调用 */
ASTNode* create_func_call(const char *name, ASTNode **args, int arg_count, int line) {
    ASTNode *node = alloc_node(NODE_FUNC_CALL, line);
    node->as.func_call.func_name = strdup(name);
    node->as.func_call.args = args;
    node->as.func_call.arg_count = arg_count;
    return node;
}

/* 数组访问 */
ASTNode* create_array_access(ASTNode *array, ASTNode *index, int line) {
    ASTNode *node = alloc_node(NODE_ARRAY_ACCESS, line);
    node->as.array_access.array = array;
    node->as.array_access.index = index;
    return node;
}

/* 成员访问 */
ASTNode* create_member_access(ASTNode *object, const char *member, int is_arrow, int line) {
    ASTNode *node = alloc_node(NODE_MEMBER_ACCESS, line);
    node->as.member_access.object = object;
    node->as.member_access.member_name = strdup(member);
    node->as.member_access.is_arrow = is_arrow;
    return node;
}

/* 三元表达式 */
ASTNode* create_ternary(ASTNode *cond, ASTNode *then_expr, ASTNode *else_expr, int line) {
    ASTNode *node = alloc_node(NODE_TERNARY, line);
    node->as.ternary.condition = cond;
    node->as.ternary.then_expr = then_expr;
    node->as.ternary.else_expr = else_expr;
    return node;
}

/* 类型转换 */
ASTNode* create_cast(const char *type_name, ASTNode *expr, int line) {
    ASTNode *node = alloc_node(NODE_CAST, line);
    node->as.cast.target_type = strdup(type_name);
    node->as.cast.expr = expr;
    return node;
}

/* 复合语句(代码块) */
ASTNode* create_compound_stmt(int line) {
    ASTNode *node = alloc_node(NODE_COMPOUND, line);
    node->as.compound.stmts = NULL;
    node->as.compound.stmt_count = 0;
    node->as.compound.stmt_capacity = 0;
    return node;
}

/* 向复合语句添加语句 */
void compound_add_stmt(ASTNode *compound, ASTNode *stmt) {
    if (compound->type != NODE_COMPOUND) return;

    /* 扩容 */
    if (compound->as.compound.stmt_count >= compound->as.compound.stmt_capacity) {
        int new_cap = compound->as.compound.stmt_capacity == 0
                      ? 4 : compound->as.compound.stmt_capacity * 2;
        compound->as.compound.stmts = (ASTNode**)realloc(
            compound->as.compound.stmts, new_cap * sizeof(ASTNode*));
        compound->as.compound.stmt_capacity = new_cap;
    }
    compound->as.compound.stmts[compound->as.compound.stmt_count++] = stmt;
}

/* if语句 */
ASTNode* create_if_stmt(ASTNode *condition, ASTNode *then_branch,
                        ASTNode *else_branch, int line) {
    ASTNode *node = alloc_node(NODE_IF, line);
    node->as.if_stmt.condition = condition;
    node->as.if_stmt.then_branch = then_branch;
    node->as.if_stmt.else_branch = else_branch;
    return node;
}

/* while循环 */
ASTNode* create_while_stmt(ASTNode *condition, ASTNode *body, int line) {
    ASTNode *node = alloc_node(NODE_WHILE, line);
    node->as.while_stmt.condition = condition;
    node->as.while_stmt.body = body;
    return node;
}

/* for循环 */
ASTNode* create_for_stmt(ASTNode *init, ASTNode *condition, ASTNode *update,
                         ASTNode *body, int line) {
    ASTNode *node = alloc_node(NODE_FOR, line);
    node->as.for_stmt.init = init;
    node->as.for_stmt.condition = condition;
    node->as.for_stmt.update = update;
    node->as.for_stmt.body = body;
    return node;
}

/* do-while循环 */
ASTNode* create_do_while_stmt(ASTNode *body, ASTNode *condition, int line) {
    ASTNode *node = alloc_node(NODE_DO_WHILE, line);
    node->as.do_while_stmt.body = body;
    node->as.do_while_stmt.condition = condition;
    return node;
}

/* return语句 */
ASTNode* create_return_stmt(ASTNode *value, int line) {
    ASTNode *node = alloc_node(NODE_RETURN, line);
    node->as.return_stmt.value = value;
    return node;
}

/* break语句 */
ASTNode* create_break_stmt(int line) {
    return alloc_node(NODE_BREAK, line);
}

/* continue语句 */
ASTNode* create_continue_stmt(int line) {
    return alloc_node(NODE_CONTINUE, line);
}

/* 表达式语句 */
ASTNode* create_expr_stmt(ASTNode *expr, int line) {
    ASTNode *node = alloc_node(NODE_EXPR_STMT, line);
    node->as.expr_stmt.expr = expr;
    return node;
}

/* 变量声明 */
ASTNode* create_var_decl(const char *type_name, const char *var_name,
                         ASTNode *init, int line) {
    ASTNode *node = alloc_node(NODE_VAR_DECL, line);
    node->as.var_decl.type_name = strdup(type_name);
    node->as.var_decl.var_name = strdup(var_name);
    node->as.var_decl.init = init;
    return node;
}

/* 函数参数 */
ASTNode* create_param_decl(const char *type_name, const char *param_name, int line) {
    ASTNode *node = alloc_node(NODE_PARAM_DECL, line);
    node->as.param_decl.type_name = strdup(type_name);
    node->as.param_decl.param_name = strdup(param_name);
    return node;
}

/* 函数声明/定义 */
ASTNode* create_func_decl(const char *return_type, const char *func_name,
                          ASTNode **params, int param_count,
                          ASTNode *body, int line) {
    ASTNode *node = alloc_node(NODE_FUNC_DECL, line);
    node->as.func_decl.return_type = strdup(return_type);
    node->as.func_decl.func_name = strdup(func_name);
    node->as.func_decl.params = params;
    node->as.func_decl.param_count = param_count;
    node->as.func_decl.body = body;
    return node;
}

/* 程序根节点 */
ASTNode* create_program(int line) {
    ASTNode *node = alloc_node(NODE_PROGRAM, line);
    node->as.program.declarations = NULL;
    node->as.program.decl_count = 0;
    node->as.program.decl_capacity = 0;
    return node;
}

/* 向程序根节点添加声明 */
void program_add_decl(ASTNode *program, ASTNode *decl) {
    if (program->type != NODE_PROGRAM) return;

    if (program->as.program.decl_count >= program->as.program.decl_capacity) {
        int new_cap = program->as.program.decl_capacity == 0
                      ? 8 : program->as.program.decl_capacity * 2;
        program->as.program.declarations = (ASTNode**)realloc(
            program->as.program.declarations, new_cap * sizeof(ASTNode*));
        program->as.program.decl_capacity = new_cap;
    }
    program->as.program.declarations[program->as.program.decl_count++] = decl;
}

/* ============================================================
 * AST打印（带缩进的树形输出）
 *
 * 使用深度优先遍历，通过缩进来表示树的层级关系。
 * 每层缩进使用 │ 和 ├── / └── 前缀来显示树结构。
 * ============================================================ */

/* 打印缩进前缀 */
static void print_indent(const char *prefix, int is_last) {
    printf("%s%s", prefix, is_last ? "└── " : "├── ");
}

/* 生成子节点的前缀 */
static void make_child_prefix(const char *parent_prefix, int is_last,
                              char *child_prefix, int buf_size) {
    snprintf(child_prefix, buf_size, "%s%s",
             parent_prefix, is_last ? "    " : "│   ");
}

/* 前置声明 */
static void print_node(ASTNode *node, const char *prefix, int is_last);

/* 打印表达式（紧凑模式，不换行） */
static void print_expr_inline(ASTNode *node) {
    if (!node) {
        printf("(null)");
        return;
    }
    switch (node->type) {
        case NODE_INT_LITERAL:
            printf("%ld", node->as.int_lit.value);
            break;
        case NODE_FLOAT_LITERAL:
            printf("%g", node->as.float_lit.value);
            break;
        case NODE_STRING_LITERAL:
            printf("\"%s\"", node->as.string_lit.value);
            break;
        case NODE_BOOL_LITERAL:
            printf("%s", node->as.bool_lit.value ? "true" : "false");
            break;
        case NODE_IDENTIFIER:
            printf("%s", node->as.ident.name);
            break;
        case NODE_BINARY_OP:
            printf("(");
            print_expr_inline(node->as.binary.left);
            printf(" %s ", op_to_string(node->as.binary.op));
            print_expr_inline(node->as.binary.right);
            printf(")");
            break;
        case NODE_UNARY_OP:
            if (node->as.unary.is_prefix) {
                printf("%s", op_to_string(node->as.unary.op));
                print_expr_inline(node->as.unary.operand);
            } else {
                print_expr_inline(node->as.unary.operand);
                printf("%s", op_to_string(node->as.unary.op));
            }
            break;
        case NODE_FUNC_CALL:
            printf("%s(", node->as.func_call.func_name);
            for (int i = 0; i < node->as.func_call.arg_count; i++) {
                if (i > 0) printf(", ");
                print_expr_inline(node->as.func_call.args[i]);
            }
            printf(")");
            break;
        case NODE_ASSIGN:
            print_expr_inline(node->as.assign.target);
            printf(" = ");
            print_expr_inline(node->as.assign.value);
            break;
        case NODE_ARRAY_ACCESS:
            print_expr_inline(node->as.array_access.array);
            printf("[");
            print_expr_inline(node->as.array_access.index);
            printf("]");
            break;
        case NODE_TERNARY:
            printf("(");
            print_expr_inline(node->as.ternary.condition);
            printf(" ? ");
            print_expr_inline(node->as.ternary.then_expr);
            printf(" : ");
            print_expr_inline(node->as.ternary.else_expr);
            printf(")");
            break;
        case NODE_CAST:
            printf("((%s)", node->as.cast.target_type);
            print_expr_inline(node->as.cast.expr);
            printf(")");
            break;
        case NODE_MEMBER_ACCESS:
            print_expr_inline(node->as.member_access.object);
            printf("%s%s",
                   node->as.member_access.is_arrow ? "->" : ".",
                   node->as.member_access.member_name);
            break;
        default:
            printf("[%s]", node_type_name(node->type));
            break;
    }
}

/* 递归打印AST节点 */
static void print_node(ASTNode *node, const char *prefix, int is_last) {
    if (!node) return;

    print_indent(prefix, is_last);

    char child_prefix[512];
    make_child_prefix(prefix, is_last, child_prefix, sizeof(child_prefix));

    switch (node->type) {
        /* ---- 字面量和标识符 ---- */
        case NODE_INT_LITERAL:
            printf("IntLit %ld\n", node->as.int_lit.value);
            break;
        case NODE_FLOAT_LITERAL:
            printf("FloatLit %g\n", node->as.float_lit.value);
            break;
        case NODE_STRING_LITERAL:
            printf("StringLit \"%s\"\n", node->as.string_lit.value);
            break;
        case NODE_BOOL_LITERAL:
            printf("BoolLit %s\n", node->as.bool_lit.value ? "true" : "false");
            break;
        case NODE_IDENTIFIER:
            printf("Id '%s'\n", node->as.ident.name);
            break;

        /* ---- 二元运算 ---- */
        case NODE_BINARY_OP:
            printf("BinaryOp '%s' (line %d)\n",
                   op_to_string(node->as.binary.op), node->line);
            print_node(node->as.binary.left, child_prefix, 0);
            print_node(node->as.binary.right, child_prefix, 1);
            break;

        /* ---- 一元运算 ---- */
        case NODE_UNARY_OP:
            printf("UnaryOp '%s' %s (line %d)\n",
                   op_to_string(node->as.unary.op),
                   node->as.unary.is_prefix ? "prefix" : "postfix",
                   node->line);
            print_node(node->as.unary.operand, child_prefix, 1);
            break;

        /* ---- 赋值 ---- */
        case NODE_ASSIGN:
            printf("Assign (line %d)\n", node->line);
            print_node(node->as.assign.target, child_prefix, 0);
            print_node(node->as.assign.value, child_prefix, 1);
            break;

        /* ---- 函数调用 ---- */
        case NODE_FUNC_CALL:
            printf("FuncCall '%s' (%d args) (line %d)\n",
                   node->as.func_call.func_name,
                   node->as.func_call.arg_count,
                   node->line);
            for (int i = 0; i < node->as.func_call.arg_count; i++) {
                print_node(node->as.func_call.args[i], child_prefix,
                          i == node->as.func_call.arg_count - 1);
            }
            break;

        /* ---- 数组访问 ---- */
        case NODE_ARRAY_ACCESS:
            printf("ArrayAccess (line %d)\n", node->line);
            print_node(node->as.array_access.array, child_prefix, 0);
            print_node(node->as.array_access.index, child_prefix, 1);
            break;

        /* ---- 成员访问 ---- */
        case NODE_MEMBER_ACCESS:
            printf("MemberAccess '%s%s' (line %d)\n",
                   node->as.member_access.is_arrow ? "->" : ".",
                   node->as.member_access.member_name,
                   node->line);
            print_node(node->as.member_access.object, child_prefix, 1);
            break;

        /* ---- 三元表达式 ---- */
        case NODE_TERNARY:
            printf("Ternary '?:' (line %d)\n", node->line);
            print_node(node->as.ternary.condition, child_prefix, 0);
            print_node(node->as.ternary.then_expr, child_prefix, 0);
            print_node(node->as.ternary.else_expr, child_prefix, 1);
            break;

        /* ---- 类型转换 ---- */
        case NODE_CAST:
            printf("Cast -> '%s' (line %d)\n",
                   node->as.cast.target_type, node->line);
            print_node(node->as.cast.expr, child_prefix, 1);
            break;

        /* ---- 复合语句 ---- */
        case NODE_COMPOUND:
            printf("Compound (%d stmts) (line %d)\n",
                   node->as.compound.stmt_count, node->line);
            for (int i = 0; i < node->as.compound.stmt_count; i++) {
                print_node(node->as.compound.stmts[i], child_prefix,
                          i == node->as.compound.stmt_count - 1);
            }
            break;

        /* ---- if语句 ---- */
        case NODE_IF:
            printf("If (line %d)\n", node->line);
            print_node(node->as.if_stmt.condition, child_prefix, 0);
            print_node(node->as.if_stmt.then_branch, child_prefix,
                      node->as.if_stmt.else_branch ? 0 : 1);
            if (node->as.if_stmt.else_branch) {
                print_node(node->as.if_stmt.else_branch, child_prefix, 1);
            }
            break;

        /* ---- while循环 ---- */
        case NODE_WHILE:
            printf("While (line %d)\n", node->line);
            print_node(node->as.while_stmt.condition, child_prefix, 0);
            print_node(node->as.while_stmt.body, child_prefix, 1);
            break;

        /* ---- for循环 ---- */
        case NODE_FOR:
            printf("For (line %d)\n", node->line);
            if (node->as.for_stmt.init)
                print_node(node->as.for_stmt.init, child_prefix, 0);
            if (node->as.for_stmt.condition)
                print_node(node->as.for_stmt.condition, child_prefix, 0);
            if (node->as.for_stmt.update)
                print_node(node->as.for_stmt.update, child_prefix, 0);
            print_node(node->as.for_stmt.body, child_prefix, 1);
            break;

        /* ---- do-while循环 ---- */
        case NODE_DO_WHILE:
            printf("DoWhile (line %d)\n", node->line);
            print_node(node->as.do_while_stmt.body, child_prefix, 0);
            print_node(node->as.do_while_stmt.condition, child_prefix, 1);
            break;

        /* ---- return语句 ---- */
        case NODE_RETURN:
            printf("Return (line %d)", node->line);
            if (node->as.return_stmt.value) {
                printf("\n");
                print_node(node->as.return_stmt.value, child_prefix, 1);
            } else {
                printf(" (void)\n");
            }
            break;

        /* ---- break / continue ---- */
        case NODE_BREAK:
            printf("Break (line %d)\n", node->line);
            break;
        case NODE_CONTINUE:
            printf("Continue (line %d)\n", node->line);
            break;

        /* ---- 表达式语句 ---- */
        case NODE_EXPR_STMT:
            printf("ExprStmt (line %d)\n", node->line);
            if (node->as.expr_stmt.expr) {
                print_node(node->as.expr_stmt.expr, child_prefix, 1);
            }
            break;

        /* ---- 变量声明 ---- */
        case NODE_VAR_DECL:
            printf("VarDecl '%s %s' (line %d)\n",
                   node->as.var_decl.type_name,
                   node->as.var_decl.var_name,
                   node->line);
            if (node->as.var_decl.init) {
                print_node(node->as.var_decl.init, child_prefix, 1);
            }
            break;

        /* ---- 函数声明 ---- */
        case NODE_FUNC_DECL:
            printf("FuncDecl '%s %s' (%d params) (line %d)\n",
                   node->as.func_decl.return_type,
                   node->as.func_decl.func_name,
                   node->as.func_decl.param_count,
                   node->line);
            for (int i = 0; i < node->as.func_decl.param_count; i++) {
                print_node(node->as.func_decl.params[i], child_prefix, 0);
            }
            if (node->as.func_decl.body) {
                print_node(node->as.func_decl.body, child_prefix, 1);
            }
            break;

        /* ---- 参数声明 ---- */
        case NODE_PARAM_DECL:
            printf("Param '%s %s'\n",
                   node->as.param_decl.type_name,
                   node->as.param_decl.param_name);
            break;

        /* ---- 程序根节点 ---- */
        case NODE_PROGRAM:
            printf("Program (%d declarations) (line %d)\n",
                   node->as.program.decl_count, node->line);
            for (int i = 0; i < node->as.program.decl_count; i++) {
                print_node(node->as.program.declarations[i], child_prefix,
                          i == node->as.program.decl_count - 1);
            }
            break;

        default:
            printf("[Unknown node type %d]\n", node->type);
            break;
    }
}

/* 公开的打印函数 */
void ast_print(ASTNode *root) {
    if (!root) {
        printf("(empty AST)\n");
        return;
    }
    printf("\n");
    print_node(root, "", 1);
    printf("\n");
}

/* ============================================================
 * 内存管理：释放AST
 *
 * 深度优先遍历释放所有节点及其字符串成员。
 * ============================================================ */

void ast_free(ASTNode *node) {
    if (!node) return;

    switch (node->type) {
        case NODE_STRING_LITERAL:
            free(node->as.string_lit.value);
            break;
        case NODE_IDENTIFIER:
            free(node->as.ident.name);
            break;
        case NODE_BINARY_OP:
            ast_free(node->as.binary.left);
            ast_free(node->as.binary.right);
            break;
        case NODE_UNARY_OP:
            ast_free(node->as.unary.operand);
            break;
        case NODE_ASSIGN:
            ast_free(node->as.assign.target);
            ast_free(node->as.assign.value);
            break;
        case NODE_FUNC_CALL:
            free(node->as.func_call.func_name);
            for (int i = 0; i < node->as.func_call.arg_count; i++) {
                ast_free(node->as.func_call.args[i]);
            }
            free(node->as.func_call.args);
            break;
        case NODE_ARRAY_ACCESS:
            ast_free(node->as.array_access.array);
            ast_free(node->as.array_access.index);
            break;
        case NODE_MEMBER_ACCESS:
            ast_free(node->as.member_access.object);
            free(node->as.member_access.member_name);
            break;
        case NODE_TERNARY:
            ast_free(node->as.ternary.condition);
            ast_free(node->as.ternary.then_expr);
            ast_free(node->as.ternary.else_expr);
            break;
        case NODE_CAST:
            free(node->as.cast.target_type);
            ast_free(node->as.cast.expr);
            break;
        case NODE_COMPOUND:
            for (int i = 0; i < node->as.compound.stmt_count; i++) {
                ast_free(node->as.compound.stmts[i]);
            }
            free(node->as.compound.stmts);
            break;
        case NODE_IF:
            ast_free(node->as.if_stmt.condition);
            ast_free(node->as.if_stmt.then_branch);
            ast_free(node->as.if_stmt.else_branch);
            break;
        case NODE_WHILE:
            ast_free(node->as.while_stmt.condition);
            ast_free(node->as.while_stmt.body);
            break;
        case NODE_FOR:
            ast_free(node->as.for_stmt.init);
            ast_free(node->as.for_stmt.condition);
            ast_free(node->as.for_stmt.update);
            ast_free(node->as.for_stmt.body);
            break;
        case NODE_DO_WHILE:
            ast_free(node->as.do_while_stmt.body);
            ast_free(node->as.do_while_stmt.condition);
            break;
        case NODE_RETURN:
            ast_free(node->as.return_stmt.value);
            break;
        case NODE_EXPR_STMT:
            ast_free(node->as.expr_stmt.expr);
            break;
        case NODE_VAR_DECL:
            free(node->as.var_decl.type_name);
            free(node->as.var_decl.var_name);
            ast_free(node->as.var_decl.init);
            break;
        case NODE_FUNC_DECL:
            free(node->as.func_decl.return_type);
            free(node->as.func_decl.func_name);
            for (int i = 0; i < node->as.func_decl.param_count; i++) {
                ast_free(node->as.func_decl.params[i]);
            }
            free(node->as.func_decl.params);
            ast_free(node->as.func_decl.body);
            break;
        case NODE_PARAM_DECL:
            free(node->as.param_decl.type_name);
            free(node->as.param_decl.param_name);
            break;
        case NODE_PROGRAM:
            for (int i = 0; i < node->as.program.decl_count; i++) {
                ast_free(node->as.program.declarations[i]);
            }
            free(node->as.program.declarations);
            break;
        default:
            break;
    }
    free(node);
}

/* ============================================================
 * 示例：构建AST
 *
 * 为以下C程序构建AST:
 *
 *   int factorial(int n) {
 *       if (n <= 1) return 1;
 *       return n * factorial(n - 1);
 *   }
 *
 *   int main() {
 *       int result = factorial(10);
 *       printf("factorial(10) = %d\n", result);
 *       return 0;
 *   }
 * ============================================================ */

ASTNode* build_factorial_ast(void) {
    /* ---- 函数体: factorial ---- */

    /* 条件: n <= 1 */
    ASTNode *cond = create_binary_op(OP_LE,
        create_identifier("n", 2),
        create_int_literal(1, 2),
        2
    );

    /* then分支: return 1 */
    ASTNode *then_branch = create_return_stmt(
        create_int_literal(1, 2), 2
    );

    /* else分支: return n * factorial(n - 1) */
    ASTNode *n_minus_1 = create_binary_op(OP_SUB,
        create_identifier("n", 3),
        create_int_literal(1, 3),
        3
    );

    ASTNode **call_args = (ASTNode**)malloc(sizeof(ASTNode*));
    call_args[0] = n_minus_1;

    ASTNode *recursive_call = create_func_call("factorial", call_args, 1, 3);

    ASTNode *mul_expr = create_binary_op(OP_MUL,
        create_identifier("n", 3),
        recursive_call,
        3
    );

    ASTNode *else_branch = create_return_stmt(mul_expr, 3);

    /* if语句 */
    ASTNode *if_stmt = create_if_stmt(cond, then_branch, else_branch, 2);

    /* 函数体 */
    ASTNode *factorial_body = create_compound_stmt(1);
    compound_add_stmt(factorial_body, if_stmt);

    /* 函数参数: int n */
    ASTNode **factorial_params = (ASTNode**)malloc(sizeof(ASTNode*));
    factorial_params[0] = create_param_decl("int", "n", 1);

    /* 函数声明 */
    ASTNode *factorial_decl = create_func_decl(
        "int", "factorial",
        factorial_params, 1,
        factorial_body, 1
    );

    /* ---- 函数体: main ---- */

    /* 变量声明: int result = factorial(10) */
    ASTNode **fac_args = (ASTNode**)malloc(sizeof(ASTNode*));
    fac_args[0] = create_int_literal(10, 8);

    ASTNode *fac_call = create_func_call("factorial", fac_args, 1, 8);

    ASTNode *result_decl = create_var_decl("int", "result", fac_call, 8);

    /* printf调用 */
    ASTNode **printf_args = (ASTNode**)malloc(2 * sizeof(ASTNode*));
    printf_args[0] = create_string_literal("factorial(10) = %d\\n", 9);
    printf_args[1] = create_identifier("result", 9);

    ASTNode *printf_call = create_func_call("printf", printf_args, 2, 9);

    /* return 0 */
    ASTNode *return_0 = create_return_stmt(create_int_literal(0, 10), 10);

    /* main函数体 */
    ASTNode *main_body = create_compound_stmt(7);
    compound_add_stmt(main_body, result_decl);
    compound_add_stmt(main_body, create_expr_stmt(printf_call, 9));
    compound_add_stmt(main_body, return_0);

    /* main函数声明 */
    ASTNode **main_params = NULL;  /* main() 无参数 */
    ASTNode *main_decl = create_func_decl(
        "int", "main",
        main_params, 0,
        main_body, 7
    );

    /* ---- 程序根节点 ---- */
    ASTNode *program = create_program(1);
    program_add_decl(program, factorial_decl);
    program_add_decl(program, main_decl);

    return program;
}

/* ============================================================
 * 示例2：构建更复杂的AST
 *
 *   int fibonacci(int n) {
 *       int a = 0, b = 1;
 *       for (int i = 0; i < n; i++) {
 *           int temp = a + b;
 *           a = b;
 *           b = temp;
 *       }
 *       return a;
 *   }
 *
 * （简化版，不包含多变量声明，用单独声明表示）
 * ============================================================ */

ASTNode* build_fibonacci_ast(void) {
    /* 函数体 */
    ASTNode *body = create_compound_stmt(1);

    /* int a = 0; */
    compound_add_stmt(body, create_var_decl("int", "a",
        create_int_literal(0, 2), 2));

    /* int b = 1; */
    compound_add_stmt(body, create_var_decl("int", "b",
        create_int_literal(1, 2), 2));

    /* for循环体: int temp = a + b; a = b; b = temp; */
    ASTNode *loop_body = create_compound_stmt(3);

    /* temp = a + b */
    compound_add_stmt(loop_body, create_var_decl("int", "temp",
        create_binary_op(OP_ADD,
            create_identifier("a", 4),
            create_identifier("b", 4),
            4),
        4));

    /* a = b */
    compound_add_stmt(loop_body, create_expr_stmt(
        create_assignment(
            create_identifier("a", 5),
            create_identifier("b", 5),
            5),
        5));

    /* b = temp */
    compound_add_stmt(loop_body, create_expr_stmt(
        create_assignment(
            create_identifier("b", 6),
            create_identifier("temp", 6),
            6),
        6));

    /* for循环 */
    ASTNode *for_loop = create_for_stmt(
        /* init: int i = 0 */
        create_var_decl("int", "i", create_int_literal(0, 3), 3),
        /* condition: i < n */
        create_binary_op(OP_LT,
            create_identifier("i", 3),
            create_identifier("n", 3),
            3),
        /* update: i++ */
        create_unary_op(OP_POST_INC,
            create_identifier("i", 3), 0, 3),
        /* body */
        loop_body,
        3
    );

    compound_add_stmt(body, for_loop);

    /* return a; */
    compound_add_stmt(body, create_return_stmt(
        create_identifier("a", 8), 8));

    /* 函数声明 */
    ASTNode **params = (ASTNode**)malloc(sizeof(ASTNode*));
    params[0] = create_param_decl("int", "n", 1);

    return create_func_decl("int", "fibonacci", params, 1, body, 1);
}

/* ============================================================
 * 示例3：展示各种表达式节点
 * ============================================================ */

ASTNode* build_expression_demo_ast(void) {
    ASTNode *body = create_compound_stmt(1);

    /* int x = (a + b) * (c - d);   -- 嵌套二元运算 */
    compound_add_stmt(body, create_var_decl("int", "x",
        create_binary_op(OP_MUL,
            create_binary_op(OP_ADD,
                create_identifier("a", 2),
                create_identifier("b", 2), 2),
            create_binary_op(OP_SUB,
                create_identifier("c", 2),
                create_identifier("d", 2), 2),
            2),
        2));

    /* int y = -x + 3;   -- 一元运算 */
    compound_add_stmt(body, create_var_decl("int", "y",
        create_binary_op(OP_ADD,
            create_unary_op(OP_NEGATIVE, create_identifier("x", 3), 1, 3),
            create_int_literal(3, 3),
            3),
        3));

    /* arr[i + 1] = x * 2;   -- 数组访问 + 赋值 */
    compound_add_stmt(body, create_expr_stmt(
        create_assignment(
            create_array_access(
                create_identifier("arr", 4),
                create_binary_op(OP_ADD,
                    create_identifier("i", 4),
                    create_int_literal(1, 4), 4),
                4),
            create_binary_op(OP_MUL,
                create_identifier("x", 4),
                create_int_literal(2, 4), 4),
            4),
        4));

    /* ptr->field = x > 0 ? x : -x;   -- 成员访问 + 三元表达式 */
    compound_add_stmt(body, create_expr_stmt(
        create_assignment(
            create_member_access(
                create_identifier("ptr", 5),
                "field", 1, 5),
            create_ternary(
                create_binary_op(OP_GT,
                    create_identifier("x", 5),
                    create_int_literal(0, 5), 5),
                create_identifier("x", 5),
                create_unary_op(OP_NEGATIVE,
                    create_identifier("x", 5), 1, 5),
                5),
            5),
        5));

    /* double d = (double)x / 3;   -- 类型转换 */
    compound_add_stmt(body, create_var_decl("double", "d",
        create_binary_op(OP_DIV,
            create_cast("double", create_identifier("x", 6), 6),
            create_int_literal(3, 6),
            6),
        6));

    ASTNode **params = NULL;
    return create_func_decl("void", "expression_demo", params, 0, body, 1);
}

/* ============================================================
 * 主函数
 * ============================================================ */

int main(void) {
    printf("╔══════════════════════════════════════════════════════════╗\n");
    printf("║         AST (Abstract Syntax Tree) Demo                 ║\n");
    printf("║  Building and visualizing AST for C programs            ║\n");
    printf("╚══════════════════════════════════════════════════════════╝\n");

    /* ---- 示例1: factorial + main ---- */
    printf("\n============================================================\n");
    printf("  Example 1: factorial & main\n");
    printf("  Source:\n");
    printf("    int factorial(int n) {\n");
    printf("        if (n <= 1) return 1;\n");
    printf("        return n * factorial(n - 1);\n");
    printf("    }\n");
    printf("    int main() {\n");
    printf("        int result = factorial(10);\n");
    printf("        printf(\"factorial(10) = %%d\\n\", result);\n");
    printf("        return 0;\n");
    printf("    }\n");
    printf("============================================================\n");

    ASTNode *prog1 = build_factorial_ast();
    ast_print(prog1);
    ast_free(prog1);

    /* ---- 示例2: fibonacci ---- */
    printf("\n============================================================\n");
    printf("  Example 2: fibonacci (iterative)\n");
    printf("  Source:\n");
    printf("    int fibonacci(int n) {\n");
    printf("        int a = 0, b = 1;\n");
    printf("        for (int i = 0; i < n; i++) {\n");
    printf("            int temp = a + b;\n");
    printf("            a = b;\n");
    printf("            b = temp;\n");
    printf("        }\n");
    printf("        return a;\n");
    printf("    }\n");
    printf("============================================================\n");

    ASTNode *prog2 = build_fibonacci_ast();
    ast_print(prog2);
    ast_free(prog2);

    /* ---- 示例3: 各种表达式 ---- */
    printf("\n============================================================\n");
    printf("  Example 3: Expression types showcase\n");
    printf("  Source:\n");
    printf("    void expression_demo() {\n");
    printf("        int x = (a + b) * (c - d);\n");
    printf("        int y = -x + 3;\n");
    printf("        arr[i + 1] = x * 2;\n");
    printf("        ptr->field = x > 0 ? x : -x;\n");
    printf("        double d = (double)x / 3;\n");
    printf("    }\n");
    printf("============================================================\n");

    ASTNode *prog3 = build_expression_demo_ast();
    ast_print(prog3);
    ast_free(prog3);

    /* ---- 内联表达式打印示例 ---- */
    printf("\n============================================================\n");
    printf("  Inline Expression Printing\n");
    printf("============================================================\n\n");

    /* (a + b) * c - d / e */
    ASTNode *expr = create_binary_op(OP_SUB,
        create_binary_op(OP_MUL,
            create_binary_op(OP_ADD,
                create_identifier("a", 0),
                create_identifier("b", 0), 0),
            create_identifier("c", 0), 0),
        create_binary_op(OP_DIV,
            create_identifier("d", 0),
            create_identifier("e", 0), 0),
        0
    );
    printf("  Expression: ");
    print_expr_inline(expr);
    printf("\n");
    ast_free(expr);

    /* x++ + ++y */
    expr = create_binary_op(OP_ADD,
        create_unary_op(OP_POST_INC, create_identifier("x", 0), 0, 0),
        create_unary_op(OP_PRE_INC, create_identifier("y", 0), 1, 0),
        0
    );
    printf("  Expression: ");
    print_expr_inline(expr);
    printf("\n");
    ast_free(expr);

    /* foo(bar(x + 1), baz()) */
    ASTNode **args1 = (ASTNode**)malloc(2 * sizeof(ASTNode*));
    args1[0] = create_func_call("bar",
        (ASTNode*[]){ create_binary_op(OP_ADD,
            create_identifier("x", 0),
            create_int_literal(1, 0), 0) },
        1, 0);
    args1[1] = create_func_call("baz", NULL, 0, 0);

    expr = create_func_call("foo", args1, 2, 0);
    printf("  Expression: ");
    print_expr_inline(expr);
    printf("\n");

    /* 需要手动释放 args1 数组（ast_free会释放其中的节点） */
    ast_free(args1[0]);
    ast_free(args1[1]);
    free(args1);
    free(expr->as.func_call.func_name);
    free(expr->as.func_call.args);
    free(expr);

    printf("\n============================================================\n");
    printf("  AST demo complete.\n");
    printf("============================================================\n");

    return 0;
}
