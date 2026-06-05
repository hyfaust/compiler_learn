/* ============================================================
 * symbol_table.c - 符号表的完整实现
 *
 * 本文件实现了一个用于编译器/解释器的符号表，包含:
 *   - FNV-1a哈希函数
 *   - 基于开链法的哈希表
 *   - 作用域链管理（进入/退出作用域）
 *   - 符号的插入、查找、更新
 *   - 类型信息
 *   - 未使用变量检测
 *
 * 编译: gcc -Wall -Wextra -o symbol_table symbol_table.c
 * 运行: ./symbol_table
 *
 * 符号表是编译器语义分析阶段的核心数据结构。
 * 它记录了程序中所有标识符的声明信息，包括:
 *   - 变量名、类型、作用域层级
 *   - 函数名、参数列表、返回类型
 *   - 类型定义信息
 *   - 是否已初始化、是否被使用
 * ============================================================ */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <ctype.h>

/* ============================================================
 * 配置常量
 * ============================================================ */

#define INITIAL_BUCKET_COUNT  64       /* 初始哈希桶数量 */
#define MAX_LOAD_FACTOR       0.75     /* 最大负载因子，超过则扩容 */
#define MAX_SCOPE_DEPTH       256      /* 最大嵌套作用域深度 */
#define MAX_SYMBOLS_PER_SCOPE 1024     /* 每个作用域最多符号数 */

/* ============================================================
 * 类型系统（简化版）
 *
 * 在真实编译器中，类型系统要复杂得多（支持结构体、
 * 联合体、函数类型、数组类型、指针类型的任意嵌套）。
 * 这里只展示基本类型以说明符号表的工作原理。
 * ============================================================ */

typedef enum {
    TYPE_VOID,
    TYPE_BOOL,
    TYPE_CHAR,
    TYPE_INT,
    TYPE_LONG,
    TYPE_FLOAT,
    TYPE_DOUBLE,
    TYPE_STRING,       /* char* (简化) */
    TYPE_ARRAY,        /* 数组类型 */
    TYPE_POINTER,      /* 指针类型 */
    TYPE_FUNCTION,     /* 函数类型 */
    TYPE_STRUCT,       /* 结构体类型 */
    TYPE_UNKNOWN,
} TypeKind;

/* 类型信息 */
typedef struct TypeInfo {
    TypeKind kind;
    int size;                  /* 类型大小（字节），-1表示未知 */
    struct TypeInfo *base;     /* 数组/指针的基类型 */
    int array_length;          /* 数组长度，-1表示未知 */
    const char *struct_name;   /* 结构体名称（仅TYPE_STRUCT） */
} TypeInfo;

/* 预定义类型实例 */
static TypeInfo type_void     = { TYPE_VOID,     0,  NULL, -1, NULL };
static TypeInfo type_bool     = { TYPE_BOOL,     1,  NULL, -1, NULL };
static TypeInfo type_char     = { TYPE_CHAR,     1,  NULL, -1, NULL };
static TypeInfo type_int      = { TYPE_INT,      4,  NULL, -1, NULL };
static TypeInfo type_long     = { TYPE_LONG,     8,  NULL, -1, NULL };
static TypeInfo type_float    = { TYPE_FLOAT,    4,  NULL, -1, NULL };
static TypeInfo type_double   = { TYPE_DOUBLE,   8,  NULL, -1, NULL };
static TypeInfo type_string   = { TYPE_STRING,   8,  NULL, -1, NULL }; /* sizeof(char*) */

/* 获取类型名称字符串 */
const char* type_kind_name(TypeKind kind) {
    switch (kind) {
        case TYPE_VOID:     return "void";
        case TYPE_BOOL:     return "bool";
        case TYPE_CHAR:     return "char";
        case TYPE_INT:      return "int";
        case TYPE_LONG:     return "long";
        case TYPE_FLOAT:    return "float";
        case TYPE_DOUBLE:   return "double";
        case TYPE_STRING:   return "string";
        case TYPE_ARRAY:    return "array";
        case TYPE_POINTER:  return "pointer";
        case TYPE_FUNCTION: return "function";
        case TYPE_STRUCT:   return "struct";
        case TYPE_UNKNOWN:  return "unknown";
    }
    return "???";
}

/* ============================================================
 * 符号条目
 *
 * 每个符号条目记录一个标识符的所有信息。
 * 使用开链法时，同一哈希桶中的符号通过 next 链接。
 * ============================================================ */

typedef enum {
    SYM_VARIABLE,      /* 局部/全局变量 */
    SYM_FUNCTION,      /* 函数 */
    SYM_PARAMETER,     /* 函数参数 */
    SYM_CONSTANT,      /* 常量（const变量、enum常量） */
    SYM_TYPE,          /* 类型定义（typedef） */
    SYM_LABEL,         /* goto标签 */
} SymbolKind;

typedef struct Symbol {
    char *name;                /* 符号名称（拥有所有权） */
    SymbolKind kind;           /* 符号种类 */
    TypeInfo *type;            /* 类型信息（不拥有所有权） */
    int scope_level;           /* 所在作用域层级 */
    int line_declared;         /* 声明所在行号 */
    int is_initialized;        /* 是否已初始化 */
    int is_used;               /* 是否被引用过 */
    int is_constant;           /* 是否为常量 */
    int param_index;           /* 参数序号（仅SYM_PARAMETER） */

    /* 函数特有信息 */
    int param_count;           /* 参数数量 */
    TypeInfo *return_type;     /* 返回类型 */

    /* 哈希链表 */
    struct Symbol *next;       /* 同一桶中的下一个符号 */
} Symbol;

/* 创建符号 */
Symbol* symbol_create(const char *name, SymbolKind kind, TypeInfo *type,
                      int scope_level, int line) {
    Symbol *sym = (Symbol*)calloc(1, sizeof(Symbol));
    if (!sym) {
        fprintf(stderr, "Error: out of memory\n");
        exit(1);
    }
    sym->name = strdup(name);
    sym->kind = kind;
    sym->type = type;
    sym->scope_level = scope_level;
    sym->line_declared = line;
    sym->is_initialized = 0;
    sym->is_used = 0;
    sym->is_constant = 0;
    sym->param_index = -1;
    sym->param_count = 0;
    sym->return_type = NULL;
    sym->next = NULL;
    return sym;
}

/* 释放符号 */
void symbol_destroy(Symbol *sym) {
    if (sym) {
        free(sym->name);
        free(sym);
    }
}

/* 获取符号种类名称 */
const char* symbol_kind_name(SymbolKind kind) {
    switch (kind) {
        case SYM_VARIABLE:  return "variable";
        case SYM_FUNCTION:  return "function";
        case SYM_PARAMETER: return "parameter";
        case SYM_CONSTANT:  return "constant";
        case SYM_TYPE:      return "type";
        case SYM_LABEL:     return "label";
    }
    return "???";
}

/* ============================================================
 * 作用域
 *
 * 每个作用域有自己的哈希表。作用域通过 parent 指针
 * 形成链表（作用域链），查找时从当前作用域逐层向上搜索。
 *
 * 作用域的典型场景:
 *   层级0: 全局作用域
 *   层级1: 函数作用域
 *   层级2: 函数内的代码块 { ... }
 *   层级3: 嵌套的代码块
 * ============================================================ */

typedef struct Scope {
    int level;                     /* 作用域层级 */
    const char *name;              /* 作用域名称（用于调试输出） */
    struct Scope *parent;          /* 父作用域 */

    /* 哈希表 */
    Symbol **buckets;              /* 哈希桶数组 */
    int bucket_count;              /* 桶数量 */
    int symbol_count;              /* 本作用域中的符号数量 */
} Scope;

/* 创建作用域 */
Scope* scope_create(int level, const char *name, Scope *parent) {
    Scope *scope = (Scope*)calloc(1, sizeof(Scope));
    if (!scope) {
        fprintf(stderr, "Error: out of memory\n");
        exit(1);
    }
    scope->level = level;
    scope->name = name ? strdup(name) : strdup("(anonymous)");
    scope->parent = parent;
    scope->bucket_count = INITIAL_BUCKET_COUNT;
    scope->symbol_count = 0;

    scope->buckets = (Symbol**)calloc(scope->bucket_count, sizeof(Symbol*));
    if (!scope->buckets) {
        fprintf(stderr, "Error: out of memory\n");
        exit(1);
    }
    return scope;
}

/* 释放作用域（递归释放所有符号） */
void scope_destroy(Scope *scope) {
    if (!scope) return;

    for (int i = 0; i < scope->bucket_count; i++) {
        Symbol *sym = scope->buckets[i];
        while (sym) {
            Symbol *next = sym->next;
            /* 检查未使用的变量 */
            if (sym->kind == SYM_VARIABLE && !sym->is_used) {
                printf("  [WARNING] Unused variable '%s' at line %d\n",
                       sym->name, sym->line_declared);
            }
            symbol_destroy(sym);
            sym = next;
        }
    }
    free(scope->buckets);
    free((void*)scope->name);
    free(scope);
}

/* ============================================================
 * FNV-1a 哈希函数
 *
 * FNV-1a是一个快速、高质量的非加密哈希函数。
 * 相比FNV-1（先乘后异或），FNV-1a先异或后乘，
 * 在雪崩效应上略好。
 *
 * 算法:
 *   hash = FNV_OFFSET_BASIS
 *   for each byte in data:
 *     hash = hash XOR byte
 *     hash = hash * FNV_PRIME
 * ============================================================ */

#define FNV_OFFSET_BASIS  2166136261u   /* 0x811c9dc5 */
#define FNV_PRIME         16777619u     /* 0x01000193 */

static unsigned int fnv1a_hash(const char *key) {
    unsigned int hash = FNV_OFFSET_BASIS;
    while (*key) {
        hash ^= (unsigned char)*key;
        hash *= FNV_PRIME;
        key++;
    }
    return hash;
}

/* ============================================================
 * 符号表
 *
 * 符号表管理作用域栈，提供以下核心操作:
 *   - push_scope:  进入新作用域
 *   - pop_scope:   退出当前作用域
 *   - insert:      在当前作用域插入符号
 *   - lookup:      从当前作用域向全局作用域逐层查找
 *   - lookup_local: 仅在当前作用域查找
 * ============================================================ */

typedef struct SymbolTable {
    Scope *current;            /* 当前（最内层）作用域 */
    int scope_depth;           /* 当前作用域深度 */
    int total_symbols;         /* 总共创建的符号数 */

    /* 错误统计 */
    int error_count;
    int warning_count;
} SymbolTable;

/* 创建符号表 */
SymbolTable* symbol_table_create(void) {
    SymbolTable *table = (SymbolTable*)calloc(1, sizeof(SymbolTable));
    if (!table) {
        fprintf(stderr, "Error: out of memory\n");
        exit(1);
    }
    /* 创建全局作用域 */
    table->current = scope_create(0, "global", NULL);
    table->scope_depth = 0;
    table->total_symbols = 0;
    table->error_count = 0;
    table->warning_count = 0;
    return table;
}

/* 释放符号表（释放所有作用域） */
void symbol_table_destroy(SymbolTable *table) {
    if (!table) return;

    /* 逐层弹出作用域 */
    while (table->current) {
        Scope *parent = table->current->parent;
        scope_destroy(table->current);
        table->current = parent;
    }
    free(table);
}

/* ============================================================
 * 作用域管理
 * ============================================================ */

/* 进入新作用域 */
void symbol_table_push_scope(SymbolTable *table, const char *name) {
    table->scope_depth++;
    char scope_name[128];
    snprintf(scope_name, sizeof(scope_name), "%s (depth %d)",
             name ? name : "block", table->scope_depth);
    table->current = scope_create(table->scope_depth, scope_name, table->current);
    printf("  [SCOPE] Entered: %s\n", scope_name);
}

/* 退出当前作用域 */
void symbol_table_pop_scope(SymbolTable *table) {
    if (!table->current || table->current->level == 0) {
        fprintf(stderr, "Error: cannot pop global scope\n");
        return;
    }

    printf("  [SCOPE] Exiting: %s  (%d symbols)\n",
           table->current->name, table->current->symbol_count);

    Scope *old = table->current;
    table->current = old->parent;
    table->scope_depth--;
    scope_destroy(old);
}

/* ============================================================
 * 插入符号
 *
 * 在当前作用域插入一个新符号。
 * 如果同名符号已在当前作用域存在，报告重复定义错误。
 * （注意：不检查外层作用域的同名符号——这允许变量遮蔽）
 * ============================================================ */

int symbol_table_insert(SymbolTable *table, const char *name,
                        SymbolKind kind, TypeInfo *type, int line) {
    if (!table || !table->current || !name) return 0;

    /* 检查当前作用域是否已有同名符号 */
    unsigned int hash = fnv1a_hash(name);
    int bucket = hash % table->current->bucket_count;

    Symbol *existing = table->current->buckets[bucket];
    while (existing) {
        if (strcmp(existing->name, name) == 0) {
            fprintf(stderr, "  [ERROR] Redefinition of '%s' at line %d "
                    "(previously defined at line %d in scope '%s')\n",
                    name, line, existing->line_declared,
                    table->current->name);
            table->error_count++;
            return 0;
        }
        existing = existing->next;
    }

    /* 创建新符号并插入到哈希桶头部 */
    Symbol *sym = symbol_create(name, kind, type, table->current->level, line);
    sym->next = table->current->buckets[bucket];
    table->current->buckets[bucket] = sym;
    table->current->symbol_count++;
    table->total_symbols++;

    printf("  [INSERT] '%s' (%s, %s) at scope '%s' (level %d, line %d)\n",
           name, symbol_kind_name(kind), type_kind_name(type->kind),
           table->current->name, table->current->level, line);

    return 1;
}

/* ============================================================
 * 查找符号
 *
 * lookup: 从当前作用域逐层向全局作用域搜索。
 *         返回第一个找到的符号（内层作用域优先）。
 *
 * lookup_local: 仅在当前作用域中查找。
 *               用于检查重复定义等场景。
 * ============================================================ */

/* 在单个作用域中查找（辅助函数） */
static Symbol* scope_lookup(Scope *scope, const char *name) {
    unsigned int hash = fnv1a_hash(name);
    int bucket = hash % scope->bucket_count;

    Symbol *sym = scope->buckets[bucket];
    while (sym) {
        if (strcmp(sym->name, name) == 0) {
            return sym;
        }
        sym = sym->next;
    }
    return NULL;
}

/* 从当前作用域逐层查找 */
Symbol* symbol_table_lookup(SymbolTable *table, const char *name) {
    if (!table || !name) return NULL;

    Scope *scope = table->current;
    while (scope) {
        Symbol *sym = scope_lookup(scope, name);
        if (sym) {
            printf("  [LOOKUP] '%s' found at scope '%s' (level %d)\n",
                   name, scope->name, scope->level);
            sym->is_used = 1;  /* 标记为已使用 */
            return sym;
        }
        scope = scope->parent;
    }

    printf("  [LOOKUP] '%s' NOT FOUND\n", name);
    return NULL;
}

/* 仅在当前作用域查找 */
Symbol* symbol_table_lookup_local(SymbolTable *table, const char *name) {
    if (!table || !table->current || !name) return NULL;
    return scope_lookup(table->current, name);
}

/* ============================================================
 * 辅助操作
 * ============================================================ */

/* 设置符号为已初始化 */
void symbol_table_mark_initialized(SymbolTable *table, const char *name) {
    Symbol *sym = symbol_table_lookup(table, name);
    if (sym) {
        sym->is_initialized = 1;
    }
}

/* 设置符号为常量 */
void symbol_table_mark_constant(SymbolTable *table, const char *name) {
    Symbol *sym = symbol_table_lookup(table, name);
    if (sym) {
        sym->is_constant = 1;
    }
}

/* ============================================================
 * 调试和打印
 * ============================================================ */

/* 打印单个符号的信息 */
static void print_symbol(const Symbol *sym) {
    printf("    %-15s  kind=%-10s  type=%-10s  scope=%-20s  level=%d  line=%d  "
           "init=%s  used=%s",
           sym->name,
           symbol_kind_name(sym->kind),
           type_kind_name(sym->type->kind),
           "",  /* scope name 在外层打印 */
           sym->scope_level,
           sym->line_declared,
           sym->is_initialized ? "yes" : "no",
           sym->is_used ? "yes" : "no");
    if (sym->is_constant) {
        printf("  [const]");
    }
    printf("\n");
}

/* 打印单个作用域的所有符号 */
static void print_scope(const Scope *scope) {
    printf("\n  === Scope: '%s' (level %d, %d symbols) ===\n",
           scope->name, scope->level, scope->symbol_count);

    for (int i = 0; i < scope->bucket_count; i++) {
        Symbol *sym = scope->buckets[i];
        while (sym) {
            print_symbol(sym);
            sym = sym->next;
        }
    }
}

/* 打印整个符号表（从全局到当前作用域） */
void symbol_table_dump(SymbolTable *table) {
    if (!table) return;

    printf("\n╔══════════════════════════════════════════════════════════════════╗\n");
    printf("║                    SYMBOL TABLE DUMP                            ║\n");
    printf("╠══════════════════════════════════════════════════════════════════╣\n");
    printf("║  Total symbols: %-5d  Scope depth: %-3d  Errors: %-3d  Warnings: %-3d ║\n",
           table->total_symbols, table->scope_depth,
           table->error_count, table->warning_count);
    printf("╚══════════════════════════════════════════════════════════════════╝\n");

    /* 收集所有作用域（从外到内） */
    Scope *scopes[MAX_SCOPE_DEPTH];
    int depth = 0;
    Scope *s = table->current;
    while (s && depth < MAX_SCOPE_DEPTH) {
        scopes[depth++] = s;
        s = s->parent;
    }

    /* 从全局作用域开始打印 */
    for (int i = depth - 1; i >= 0; i--) {
        print_scope(scopes[i]);
    }
    printf("\n");
}

/* ============================================================
 * 演示程序
 *
 * 模拟编译器处理以下伪代码时符号表的变化:
 *
 *   // 全局作用域
 *   int global_var = 10;
 *   void compute(int n) {
 *       double result = 0.0;
 *       for (int i = 0; i < n; i++) {
 *           result += i * 0.5;
 *       }
 *       if (result > 10.0) {
 *           int unused = 42;
 *       }
 *   }
 *   int main() {
 *       int x = 5;
 *       compute(x);
 *       return 0;
 *   }
 * ============================================================ */

void demo_basic_operations(void) {
    printf("============================================================\n");
    printf("  Demo 1: Basic Symbol Table Operations\n");
    printf("============================================================\n");

    SymbolTable *table = symbol_table_create();

    /* --- 全局作用域 --- */
    printf("\n--- Inserting global symbols ---\n");
    symbol_table_insert(table, "global_var", SYM_VARIABLE, &type_int, 1);
    symbol_table_mark_initialized(table, "global_var");

    symbol_table_insert(table, "MAX_SIZE", SYM_CONSTANT, &type_int, 2);
    symbol_table_mark_constant(table, "MAX_SIZE");
    symbol_table_mark_initialized(table, "MAX_SIZE");

    symbol_table_insert(table, "compute", SYM_FUNCTION, &type_void, 3);

    symbol_table_insert(table, "main", SYM_FUNCTION, &type_int, 10);

    /* --- 进入 compute 函数 --- */
    printf("\n--- Entering function: compute ---\n");
    symbol_table_push_scope(table, "compute");

    symbol_table_insert(table, "n", SYM_PARAMETER, &type_int, 3);
    symbol_table_mark_initialized(table, "n");

    symbol_table_insert(table, "result", SYM_VARIABLE, &type_double, 4);
    symbol_table_mark_initialized(table, "result");

    /* --- 进入 for 循环体 --- */
    printf("\n--- Entering for-loop body ---\n");
    symbol_table_push_scope(table, "for-loop");

    symbol_table_insert(table, "i", SYM_VARIABLE, &type_int, 5);
    symbol_table_mark_initialized(table, "i");

    /* 查找: i 在当前作用域，n 在外层作用域 */
    printf("\n--- Looking up symbols from inside for-loop ---\n");
    Symbol *sym_i = symbol_table_lookup(table, "i");
    Symbol *sym_n = symbol_table_lookup(table, "n");
    Symbol *sym_result = symbol_table_lookup(table, "result");
    Symbol *sym_unknown = symbol_table_lookup(table, "nonexistent");

    (void)sym_i; (void)sym_n; (void)sym_result; (void)sym_unknown;

    /* 退出 for 循环 */
    printf("\n--- Exiting for-loop ---\n");
    symbol_table_pop_scope(table);

    /* --- 进入 if 代码块 --- */
    printf("\n--- Entering if-block ---\n");
    symbol_table_push_scope(table, "if-block");

    symbol_table_insert(table, "unused", SYM_VARIABLE, &type_int, 8);
    /* 注意: unused 没有被标记为 is_used，退出时会产生警告 */

    /* 在 if 块中可以访问外层的 result */
    printf("\n--- Looking up 'result' from inside if-block ---\n");
    symbol_table_lookup(table, "result");

    printf("\n--- Exiting if-block ---\n");
    symbol_table_pop_scope(table);

    printf("\n--- Exiting function: compute ---\n");
    symbol_table_pop_scope(table);

    /* --- 进入 main 函数 --- */
    printf("\n--- Entering function: main ---\n");
    symbol_table_push_scope(table, "main");

    symbol_table_insert(table, "x", SYM_VARIABLE, &type_int, 11);
    symbol_table_mark_initialized(table, "x");

    /* 尝试重复定义 */
    printf("\n--- Testing redefinition error ---\n");
    symbol_table_insert(table, "x", SYM_VARIABLE, &type_double, 12);

    /* 查找全局符号 */
    printf("\n--- Looking up global symbols from main ---\n");
    symbol_table_lookup(table, "global_var");
    symbol_table_lookup(table, "compute");

    printf("\n--- Exiting function: main ---\n");
    symbol_table_pop_scope(table);

    /* 打印最终状态 */
    symbol_table_dump(table);

    symbol_table_destroy(table);
}

/* ============================================================
 * 演示: 变量遮蔽 (Shadowing)
 *
 * 内层作用域的变量可以遮蔽外层同名变量。
 * 查找时，内层的定义优先。
 * ============================================================ */

void demo_variable_shadowing(void) {
    printf("\n============================================================\n");
    printf("  Demo 2: Variable Shadowing\n");
    printf("============================================================\n");

    SymbolTable *table = symbol_table_create();

    /* 全局作用域 */
    symbol_table_insert(table, "x", SYM_VARIABLE, &type_int, 1);
    symbol_table_mark_initialized(table, "x");

    printf("\n--- Lookup 'x' in global scope ---\n");
    symbol_table_lookup(table, "x");

    /* 进入函数 */
    symbol_table_push_scope(table, "foo");

    /* 函数作用域中的 x 遮蔽全局的 x */
    symbol_table_insert(table, "x", SYM_VARIABLE, &type_double, 5);
    symbol_table_mark_initialized(table, "x");

    printf("\n--- Lookup 'x' in function scope (shadows global) ---\n");
    Symbol *sym = symbol_table_lookup(table, "x");
    if (sym) {
        printf("  Found: x is %s at level %d\n",
               type_kind_name(sym->type->kind), sym->scope_level);
    }

    /* 进入内层代码块 */
    symbol_table_push_scope(table, "inner-block");

    /* 再次遮蔽 */
    symbol_table_insert(table, "x", SYM_VARIABLE, &type_char, 8);
    symbol_table_mark_initialized(table, "x");

    printf("\n--- Lookup 'x' in inner block (shadows function x) ---\n");
    sym = symbol_table_lookup(table, "x");
    if (sym) {
        printf("  Found: x is %s at level %d\n",
               type_kind_name(sym->type->kind), sym->scope_level);
    }

    /* 退出内层 */
    symbol_table_pop_scope(table);

    printf("\n--- Lookup 'x' after exiting inner block ---\n");
    sym = symbol_table_lookup(table, "x");
    if (sym) {
        printf("  Found: x is %s at level %d (back to function scope)\n",
               type_kind_name(sym->type->kind), sym->scope_level);
    }

    /* 退出函数 */
    symbol_table_pop_scope(table);

    printf("\n--- Lookup 'x' after exiting function ---\n");
    sym = symbol_table_lookup(table, "x");
    if (sym) {
        printf("  Found: x is %s at level %d (global scope)\n",
               type_kind_name(sym->type->kind), sym->scope_level);
    }

    symbol_table_dump(table);
    symbol_table_destroy(table);
}

/* ============================================================
 * 演示: 哈希冲突处理
 *
 * 通过插入多个名字不同但哈希值相同（模桶数）的符号，
 * 验证开链法的正确性。
 * ============================================================ */

void demo_hash_collision(void) {
    printf("\n============================================================\n");
    printf("  Demo 3: Hash Collision Handling\n");
    printf("============================================================\n");

    SymbolTable *table = symbol_table_create();

    /* 插入多个符号 */
    const char *names[] = {
        "alpha", "bravo", "charlie", "delta", "echo",
        "foxtrot", "golf", "hotel", "india", "juliet",
        "kilo", "lima", "mike", "november", "oscar",
        "papa", "quebec", "romeo", "sierra", "tango",
    };
    int name_count = sizeof(names) / sizeof(names[0]);

    printf("\n--- Inserting %d symbols ---\n", name_count);
    for (int i = 0; i < name_count; i++) {
        symbol_table_insert(table, names[i], SYM_VARIABLE, &type_int, i + 1);
    }

    /* 验证所有符号都能正确查找 */
    printf("\n--- Verifying all symbols can be looked up ---\n");
    int found_count = 0;
    for (int i = 0; i < name_count; i++) {
        Symbol *sym = symbol_table_lookup(table, names[i]);
        if (sym) {
            found_count++;
        }
    }
    printf("  Found %d / %d symbols\n", found_count, name_count);

    /* 打印哈希值分布 */
    printf("\n--- Hash distribution (%d buckets) ---\n",
           table->current->bucket_count);
    int max_chain = 0;
    int empty_buckets = 0;
    for (int i = 0; i < table->current->bucket_count; i++) {
        int chain_len = 0;
        Symbol *sym = table->current->buckets[i];
        while (sym) {
            chain_len++;
            sym = sym->next;
        }
        if (chain_len == 0) empty_buckets++;
        if (chain_len > max_chain) max_chain = chain_len;
    }
    printf("  Max chain length: %d\n", max_chain);
    printf("  Empty buckets: %d / %d\n", empty_buckets, table->current->bucket_count);
    printf("  Load factor: %.2f\n",
           (double)table->current->symbol_count / table->current->bucket_count);

    symbol_table_destroy(table);
}

/* ============================================================
 * 演示: 复杂的嵌套作用域场景
 *
 * 模拟编译以下代码:
 *
 *   int counter = 0;
 *
 *   void process() {
 *       int data[10];
 *       for (int i = 0; i < 10; i++) {
 *           data[i] = i * counter;
 *           if (data[i] > 50) {
 *               int threshold = data[i];
 *               printf("%d\n", threshold);
 *           }
 *       }
 *       int unused_var = 99;
 *   }
 *
 *   int main() {
 *       process();
 *       return 0;
 *   }
 * ============================================================ */

void demo_complex_nesting(void) {
    printf("\n============================================================\n");
    printf("  Demo 4: Complex Nested Scopes\n");
    printf("============================================================\n");

    SymbolTable *table = symbol_table_create();

    /* 全局 */
    symbol_table_insert(table, "counter", SYM_VARIABLE, &type_int, 1);
    symbol_table_mark_initialized(table, "counter");

    symbol_table_insert(table, "process", SYM_FUNCTION, &type_void, 3);
    symbol_table_insert(table, "main", SYM_FUNCTION, &type_int, 15);

    /* process 函数 */
    symbol_table_push_scope(table, "process");

    symbol_table_insert(table, "data", SYM_VARIABLE, &type_int, 4);
    symbol_table_mark_initialized(table, "data");

    /* for 循环 */
    symbol_table_push_scope(table, "for-loop");

    symbol_table_insert(table, "i", SYM_VARIABLE, &type_int, 5);
    symbol_table_mark_initialized(table, "i");

    /* if 代码块 */
    symbol_table_push_scope(table, "if-block");

    symbol_table_insert(table, "threshold", SYM_VARIABLE, &type_int, 7);
    symbol_table_mark_initialized(table, "threshold");
    symbol_table_mark_initialized(table, "threshold"); /* 再次标记，无影响 */

    /* 从 if 块内部查找 */
    printf("\n--- Lookup chain from deepest scope ---\n");
    symbol_table_lookup(table, "threshold");  /* 当前作用域 */
    symbol_table_lookup(table, "i");          /* for-loop 作用域 */
    symbol_table_lookup(table, "data");       /* process 作用域 */
    symbol_table_lookup(table, "counter");    /* 全局作用域 */

    symbol_table_pop_scope(table); /* 退出 if */
    symbol_table_pop_scope(table); /* 退出 for */

    /* process 函数中的另一个变量 */
    symbol_table_insert(table, "unused_var", SYM_VARIABLE, &type_int, 10);

    symbol_table_pop_scope(table); /* 退出 process */

    /* main 函数 */
    symbol_table_push_scope(table, "main");
    symbol_table_insert(table, "result", SYM_VARIABLE, &type_int, 16);
    symbol_table_pop_scope(table); /* 退出 main */

    /* 最终状态 */
    symbol_table_dump(table);

    symbol_table_destroy(table);
}

/* ============================================================
 * 主函数
 * ============================================================ */

int main(void) {
    printf("╔══════════════════════════════════════════════════════════╗\n");
    printf("║        Symbol Table Implementation - Demo               ║\n");
    printf("║  Features: Hash table, Scope chain, Type system         ║\n");
    printf("╚══════════════════════════════════════════════════════════╝\n\n");

    demo_basic_operations();
    demo_variable_shadowing();
    demo_hash_collision();
    demo_complex_nesting();

    printf("\n============================================================\n");
    printf("  All demos completed.\n");
    printf("============================================================\n");

    return 0;
}
