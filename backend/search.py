"""Semble搜索包装器 - 自动配置代理和离线模式"""

import os
import sys

# 配置环境
os.environ['HF_HUB_OFFLINE'] = '1'
os.environ['HTTPS_PROXY'] = os.environ.get('HTTPS_PROXY', 'http://127.0.0.1:7890')
os.environ['HTTP_PROXY'] = os.environ.get('HTTP_PROXY', 'http://127.0.0.1:7890')

from semble import SembleIndex


def search(query: str, path: str = '.', top_k: int = 5):
    """搜索代码库"""
    index = SembleIndex.from_path(path, include_text_files=False)
    results = index.search(query, top_k=top_k)

    for i, r in enumerate(results, 1):
        chunk = r.chunk
        print(f"\n[{i}] {chunk.file_path}:{chunk.start_line}-{chunk.end_line}")
        print(f"    Score: {r.score:.4f}")
        print(f"    {chunk.content[:200]}...")
    return results


if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("用法: python search.py <查询> [路径] [结果数]")
        print("示例: python search.py 'document parser' . 5")
        sys.exit(1)

    query = sys.argv[1]
    path = sys.argv[2] if len(sys.argv) > 2 else '.'
    top_k = int(sys.argv[3]) if len(sys.argv) > 3 else 5

    search(query, path, top_k)
