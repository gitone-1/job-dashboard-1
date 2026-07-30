#!/usr/bin/env python3
"""将城市=上海 的岗位标记为"不匹配"，并同步到 user_status.json（云端）。
这样上海岗位从"有效岗位"消失，且下次更新不会因 restore_user_status 而回弹。
"""
import json
import re
import time
from datetime import datetime
from pathlib import Path

TODAY = datetime.now().strftime("%Y-%m-%d")


def load_json(p):
    p = Path(p)
    return json.load(open(p, 'r', encoding='utf-8')) if p.exists() else None


def save_json(p, data):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    json.dump(data, open(p, 'w', encoding='utf-8'), ensure_ascii=False, indent=2)


def main():
    jobs = load_json('jobs.json')
    status = load_json('user_status.json') or {}

    marked = []
    for j in jobs:
        if j.get('city') == '上海' and j.get('status') != '不匹配':
            j['status'] = '不匹配'
            key = j['company'] + '|' + j['title'] + '|' + j['city']
            status[key] = {'status': '不匹配', 'time': TODAY}
            marked.append(f"{j['company']} - {j['title']}")

    save_json('jobs.json', jobs)
    save_json('user_status.json', status)

    # 重新生成版本化数据文件（破 IE 缓存）
    versioned = f'jobs_v{int(time.time())}.json'
    save_json(versioned, jobs)
    html = Path('index.html').read_text(encoding='utf-8')
    new_html = re.sub(r"jobs_v\d+\.json", versioned, html)
    if new_html != html:
        Path('index.html').write_text(new_html, encoding='utf-8')

    total_sh = sum(1 for j in jobs if j['city'] == '上海')
    print(f"已将上海岗位标记为不匹配: {len(marked)} 个")
    for m in marked:
        print(f"  - {m}")
    print(f"当前上海岗位总数(均为不匹配): {total_sh}")
    print(f"版本文件: {versioned}")


if __name__ == '__main__':
    main()
