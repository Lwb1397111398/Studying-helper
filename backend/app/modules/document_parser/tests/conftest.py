"""测试配置和fixtures"""

import pytest
from pathlib import Path


@pytest.fixture
def tmp_dir(tmp_path):
    """临时目录fixture"""
    return tmp_path


@pytest.fixture
def sample_txt_with_toc(tmp_path):
    """包含目录结构的测试TXT文件"""
    content = """目录

第一章 初识Python
第二章 数据类型
第三章 函数定义
第四章 面向对象
第五章 文件操作

第一章 初识Python

1.1 Python简介

Python是一种广泛使用的高级编程语言，由Guido van Rossum于1991年创建。

1.2 安装Python

访问Python官方网站下载安装包。

第二章 数据类型

2.1 数字类型

Python支持整数、浮点数和复数。

2.2 字符串类型

字符串是Python中最常用的数据类型之一。
"""
    file_path = tmp_path / "sample_with_toc.txt"
    file_path.write_text(content, encoding='utf-8')
    return file_path


@pytest.fixture
def sample_txt_without_toc(tmp_path):
    """无目录结构的测试TXT文件"""
    content = """这是一个简单的文本文件。

第一章 初识Python

Python是一种广泛使用的高级编程语言，由Guido van Rossum于1991年创建。
它具有简洁、易读的语法，适合初学者学习。

第二章 数据类型

Python支持多种数据类型，包括数字、字符串、列表、元组、字典等。
"""
    file_path = tmp_path / "sample_without_toc.txt"
    file_path.write_text(content, encoding='utf-8')
    return file_path


@pytest.fixture
def sample_txt_empty(tmp_path):
    """空的测试TXT文件"""
    file_path = tmp_path / "empty.txt"
    file_path.write_text("", encoding='utf-8')
    return file_path


@pytest.fixture
def sample_txt_gbk(tmp_path):
    """GBK编码的测试TXT文件（足够大的样本让chardet能正确检测）"""
    content = """第一章 测试章节

这是一个GBK编码的测试文件。本文件用于测试文档解析器是否能正确处理GBK编码的文本。
Python是一种广泛使用的高级编程语言，由Guido van Rossum于1991年创建。
它具有简洁、易读的语法，适合初学者学习。Python支持多种编程范式，
包括面向对象、命令式、函数式和过程式编程。

第二章 数据类型

Python支持多种数据类型，包括数字、字符串、列表、元组、字典等。
数字类型包括整数、浮点数和复数。字符串是Python中最常用的数据类型之一。
列表是一种有序的可变序列，元组是一种有序的不可变序列。

第三章 控制结构

Python提供了丰富的控制结构，包括条件语句、循环语句等。
条件语句使用if、elif、else关键字。循环语句包括for循环和while循环。
"""
    file_path = tmp_path / "sample_gbk.txt"
    file_path.write_bytes(content.encode('gbk'))
    return file_path
