# SPDX-License-Identifier: MIT
from pathlib import Path
import json,hashlib
root=Path(__file__).resolve().parents[1]
manifest=json.loads((root/'SHARED_CODE.json').read_text(encoding='utf-8'))
for item in manifest['components']:
    path=(root/item['localPath']).resolve()
    if not path.is_relative_to(root) or not path.is_file():raise ValueError('shared path missing or outside repository')
    digest=hashlib.sha256(path.read_text(encoding='utf-8-sig').encode('utf-8')).hexdigest()
    if digest!=item['normalizedTextSha256']:raise ValueError('shared implementation changed; review canonical source/version and refresh manifest: '+item['localPath'])
print('Fixed shared implementation hashes checked; no sibling repository required')
