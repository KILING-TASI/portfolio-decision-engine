# SPDX-License-Identifier: MIT
"""Validate the frozen local inventory without other repositories or network."""
from pathlib import Path
import json
import hashlib


def check(root):
    root = root.resolve()
    manifest = json.loads((root / 'SHARED_CODE.json').read_text(encoding='utf-8'))
    if manifest['schemaVersion'] != 'fixed-shared-components/1':
        raise ValueError('不支持的共享清单版本')
    paths = set()
    for item in manifest['components']:
        if item['localPath'] in paths:
            raise ValueError('共享路径重复登记：' + item['localPath'])
        paths.add(item['localPath'])
        path = (root / item['localPath']).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError('共享文件缺失或路径越界：' + item['localPath'])
        for field in ('canonicalRepository', 'canonicalPath', 'syncPolicy', 'licenseScope'):
            if not item.get(field):
                raise ValueError('共享清单缺少字段：' + field)
        sha = hashlib.sha256(path.read_text(encoding='utf-8-sig').encode('utf-8')).hexdigest()
        if sha != item['normalizedTextSha256']:
            raise ValueError('共享实现已改变，请复核固定版本后更新清单：' + item['localPath'])
    return len(paths)


if __name__ == '__main__':
    import sys
    if hasattr(sys.stdout, 'reconfigure'): sys.stdout.reconfigure(encoding='utf-8')
    print(f'共享组件检查通过：{check(Path(__file__).resolve().parents[1])} 项；无需其他仓库或联网')
