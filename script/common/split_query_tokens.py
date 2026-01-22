import re


def split_query_tokens(sql: str):
    # 把「双字符运算符」一次性写出来，放在最前面，正则引擎会优先匹配
    DBL_OPS = (
        r'::|->>|->|#>>|#>|<->|@>|<@|\|\||&&|\?\&|\?\||'
        r'<<|>>|!=|<>|<=|>=|<->|==|\.\.|\.\*'
    )
    TOKEN_RE = re.compile(
        DBL_OPS +                          # 1. 双字符
        r'|\b\w+\b' +                      # 2. 单词
        r'|[^\w\s]',                       # 3. 剩余单字符
        re.IGNORECASE
    )
    # 清注释、去引号、压空白、去掉末尾分号
    sql = re.sub(r'/\*.*?\*/', ' ', sql, flags=re.S)        # 块注释
    sql = re.sub(r'--.*$', '', sql, flags=re.M)            # 行注释
    sql = re.sub(r'//.*$', '', sql, flags=re.M)            # AQL 也支持 // 行注释
    
    # 修改后的引号替换逻辑：只有引号内以$开头的 JSONPath 才保留，其余替换成 str (避免干扰 token 计数)
    # 匹配引号内容，分组捕获
    # group(1) 是单引号内容，group(2) 是双引号内容
    def repl_quote(m):
        single = m.group(1)
        double = m.group(2)
        content = single if single is not None else double
        if content.startswith('$'):
            return content
        return 'str'          
    
    sql = re.sub(r"""'([^']*)'|"([^"]*)\" """, repl_quote, sql)
    
    sql = ' '.join(sql.split())
    sql = sql.rstrip(';')
    return TOKEN_RE.findall(sql)