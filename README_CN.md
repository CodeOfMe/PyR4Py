# PyRlang

**R 风语法,跑在纯 Python 上。** 不需要 R 运行时,不编译,零依赖。

PyRlang 让你按 R 程序员真实的写法写代码——`x <- c(1, 2)`、`1:10`、`df$col`、`%>%`、
`%in%`、`y ~ x`——底下跑的就是普通 Python。同时它也把 R 风格的数据类型包装成
正常的 Python 库,可以直接在 `.py` 文件里用。

- **PyPI 发行名:** `pyr4py`
  (PyPI 比较项目名时会先剥掉 `-` 和 `_`,所以整个家族都被封了:`pyr` 是 2013 年的死 REPL,
  `pyrlang` 是一个仍在活跃开发的 BEAM 运行时,连带 `pyr-lang`/`PyRlang` 上传也被拒;
  `pyr4py`——"PyR for Python"——才是能通过的发行名)
- **import 名:** `PyRlang`(`import PyRlang`、`from PyRlang import *`)
- **协议:** GPL-3.0-or-later
- **Python:** >= 3.10

## 安装

```bash
pip install pyr4py            # 零依赖核心
pip install "pyr4py[all]"     # + NumPy 加速、matplotlib 绘图、pandas 互通
pip install "pyr4py[accel]"   # + 只装 NumPy
```

**速度:** 装了 NumPy 后,逐元素运算和统计自动走向量化路径(实测约 1.2–6 倍;
`PYRLANG_NO_NUMPY=1` 可强制回到纯 Python 路径)。

## 三种用法

### 1. R 风脚本(`.pyr` 文件)——完整语法

写 `hello.pyr`:

```r
x <- c(2, 4.5, 8, 1, 3.3, NA)
mean(x, na.rm = TRUE)
summary(x)

v <- 1:5
v[1]              # 从 1 开始数,v[1] 是第一个
v[-1]             # R 语义:负下标是"删掉这个元素"

df <- data.frame(
  name = c("ada", "bob"),
  age  = c(34, 47)
)
df$age
df[df$age > 35, ]
df$senior <- df$age > 40

df$age %>% mean() %>% round(2)
10 %in% c(4, 8, 10)
paste("R", "on", "Python", sep = "-") |> toupper()
f <- wage ~ age
```

像跑 R 脚本一样跑:

```bash
PyRlang hello.pyr          # 或:python -m PyRlang hello.pyr
```

顶层表达式会像 R 控制台一样自动回显结果,向量打印成 `[1] 2 4.5 8 1 3.3 NA`。

### 2. 交互式 REPL

```text
$ PyRlang
PyRlang 0.1.0 on Python 3.12 — R-style syntax, pure Python
Try: x <- c(1, 2, 3); mean(x).  exit() or Ctrl-D to quit.
>> x <- c(1, 2, 3)
>> mean(x)
[1] 2
>> 1:5 %>% sum()
[1] 15
```

### 3. 当普通 Python 库用

```python
from PyRlang import *

v = c(1, 2, 3)
v[1]  # 1 —— 从 1 开始
mean(v)  # 2.0
f = Formula("y ~ x")
df = data_frame(age=c(34, 47), wage=c(21.5, 33.0))
summary(df)  # R 风格的六数汇总
```

## 转换模式支持的语法

(`.pyr` 文件、REPL、`PyRlang -e`;普通 `.py` 文件永远不会被改写。)

| R 语法          | 转成                   | 说明                                                          |
|-----------------|------------------------|---------------------------------------------------------------|
| `x <- e`        | `x = e`                | `<` 和 `-` 相邻才认,和 R 解析器规则一致                       |
| `x < -e`        | 原样保留               | 中间有空格就是 Python 比较运算                                |
| `<<-`           | 不支持                 | 报清晰的错                                                    |
| `a:b`           | `seq(a, b)`            | 只在 `[]`/`{}` 之外;lambda 后、类型注解处、切片里都不转       |
| `x ^ y`         | `x ** y`               |                                                               |
| `x %% y`        | `x % y`                |                                                               |
| `a && b`        | `a and b`              | 相邻才认,对应 R 的标量逻辑运算                                |
| `a \|\| b`      | `a or b`               |                                                               |
| `!x`            | `PyRlang.not_(x)`          | 逐元素取反——对向量也成立                                      |
| `a %in% b`      | `PyRlang.isin(a, b)`       | 向量化的成员判断                                              |
| `a %>% f(b)`    | `PyRlang.pipe(a, f, b)`    | magrittr 管道;R 原生 `a \|> f(b)` 也支持                      |
| `y ~ x + z`     | `Formula('y ~ x + z')` | 放在函数实参里也认识:`lm(y ~ x, data = d)` 风格               |
| `df$col`        | `df.col`               |                                                               |
| `data.frame(…)` | `DataFrame(…)`         | 另外 `read.csv`、`write.csv`、`which.max`、`which.min`、`na.rm=`、`length.out=`、`names.arg=` |

## R 块语法

花括号转成缩进,R 在哪用花括号,这里就转哪里:

```r
if (total > 10) {
  msg <- "big"
} else if (total == 10) {
  msg <- "ten"
} else {
  msg <- "small"
}

for (i in 1:5) {
  total <- total + i
}

repeat {
  guard <- guard + 3
  if (guard >= 9) {
    break
  }
}
```

`next` 也支持,R 花括号**之外**的行保持逐字节原样,所以 `.pyr` 里混写的
纯 Python 代码不会被改排。不支持:R 的 `function(x) {...}` 定义(请写
Python `def`)和单行 `if (x) y <- 2` 形式。

## R 终端(REPL)

不带参数运行 `PyRlang`,就是一个仿 R 控制台的终端,像 IPython 那样架在
Python 上:TAB 补全、历史存于 `~/.pyr_history`、`_` 保存上一个结果、
`q()` 退出、`source("file.pyr")` 现场跑脚本:

```text
>> x <- c(2, 4.5, 8, 1, 3.3, NA)
>> mean(x, na.rm = TRUE)
[1] 3.76
>> _
[1] 3.76
```

## 绘图(可选)

装了 `matplotlib`(`pip install "pyr4py[graphics]"`)后可用:

```r
plot(x, y, col = "steelblue")      # 散点(type = "l" 是折线)
hist(x, breaks = 20)
barplot(heights, names.arg = c("a", "b"))
```

图会存成 `plot_01.png`、`hist_01.png`… 并打印路径,脚本与 REPL 都不会阻塞。

## pandas 互通(可选)

```python
from PyRlang import data_frame, to_pandas, from_pandas

pdf = to_pandas(data_frame(age=c(34, 47)))  # pandas DataFrame(NA -> NaN)
df = from_pandas(pdf)  # 回到 PyRlang(NaN -> NA)
```

## 有意为之的语义

- **下标从 1 开始。** `v[1]` 是第一个元素;下标 0 报 R 风格的错误。
  `v[2:4]` 返回第 2、3、4 个元素(闭区间,同 R);越界切片用 `NA` 补齐。
- **负下标是"删除"。** `v[-1]` 是去掉第一个元素(和 Python 的负数索引不同,这是故意的)。
- **循环复用。** `c(1, 2) + c(1, 2, 3, 4)` 会循环复用短向量,同 R。
- **NA 无处不在。** 真正的 `NA` 单例:`NA + 1` 是 `NA`,`mean(c(1, NA))` 是 `NA`,
  除非写 `na.rm = TRUE`;`if (NA)` 会报 R 的那条错。
- **R 风打印。** 向量打印为 `[1] 1 2 3`,字符串带引号,逻辑值是 `TRUE`/`FALSE`,
  六数汇总按 R 的版式排。
- **除零是 `Inf`/`NaN`**,不抛异常——同 R。

## 库里有什么

- 构造与检查:`c`、`seq`、`rep`、`length`、`unique`、`sort`、`rev`、
  `head`、`tail`、`which`、`which.max`、`which.min`、`table`
- 统计:`mean`、`median`、`sd`、`var`、`min`、`max`、`sum`、`prod`、
  `summary`、`sqrt`、`exp`、`log`,全部支持 `na.rm` 语义
- 字符串:`paste`、`paste0`、`sprintf`、`nchar`、`toupper`、`tolower`、
  `substr`、`substring`、`cat`
- 数据:`data.frame`、`$`、R 式行列子集、`nrow`、`ncol`、`names`、
  `read.csv`、`write.csv`
- 逻辑:`ifelse`、`%in%`、逐元素 `&`、`|`、`!`、向量化比较

## 诚实说明(v0.1.2 的限制)

- R 块语法有边界:`function(x) {...}` 定义不转换(请写 Python `def`);
  单行 `if (x) y <- 2` 形式不支持。
- `->`(右赋值)还没转。
- `lm`、`glm`、`ggplot` 等建模栈还不存在;`Formula` 目前只是数据结构,绘图只覆盖
  `plot`、`hist`、`barplot`。
- 没有包/命名空间系统;要用的 Python 库直接 `import`。
- `.pyr` 文件里不要写 Python 类型注解(R 模式下 `n:m` 会被当成数列)。
- 只支持 Python >= 3.10。

## 版本号策略

发布只允许**修改版本号最后一位**(`0.1.1` → `0.1.2` → …),`0.1` 前缀在本
开发线内固定不动。

## 开发

```bash
pip install -e ".[dev]"
pytest
ruff format . && ruff check .
python -m build
twine check dist/*
```

跑示例:

```bash
python -m PyRlang examples/basics.pyr
python -m PyRlang examples/dataframe.pyr
PyRlang
```

## 发布到 PyPI

本项目在 PyPI 上的发行名是 **`pyr4py`**(占名说明见开头)。

```bash
python -m build
twine check dist/*
twine upload dist/pyr4py-0.1.0*
```

先用 `--repository testpypi` 到 TestPyPI 彩排,或配置 API token:

```ini
# ~/.pypirc
[pypi]
username = __token__
password = pypi-xxxxxxxx
```

## 协议

GPL-3.0-or-later,见 [LICENSE](LICENSE)。