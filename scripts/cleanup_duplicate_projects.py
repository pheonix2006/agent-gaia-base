#!/usr/bin/env python3
"""清理错误的项目注册"""

import json
from pathlib import Path

config_file = Path.home() / ".agents" / "projects.json"

print(f"读取配置文件: {config_file}")
with open(config_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"\n当前项目列表 ({len(data['projects'])} 个):")
for i, project in enumerate(data['projects'], 1):
    print(f"{i}. {project['slug']}")
    print(f"   名称: {project['name']}")
    print(f"   路径: {project['path']}")
    print(f"   活跃会话: {project['active_session']}")

# 保留正确的项目 (ai-agent)，删除错误的项目 (ai-agent-2)
print("\n清理策略：")
print("- 保留 'ai-agent' (E:\\Project\\ai agent) - 正确路径，有数据")
print("- 删除 'ai-agent-2' (E:\\Project) - 错误路径，无数据")

data['projects'] = [p for p in data['projects'] if p['slug'] == 'ai-agent']

print(f"\n清理后的项目列表 ({len(data['projects'])} 个):")
for project in data['projects']:
    print(f"- {project['slug']} ({project['path']})")

# 备份原文件
backup_file = config_file.with_suffix('.json.backup')
print(f"\n备份原文件到: {backup_file}")
with open(backup_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

# 保存清理后的配置
print(f"保存清理后的配置到: {config_file}")
with open(config_file, 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2, ensure_ascii=False)

print("\n[OK] 清理完成！")
print("\n下一步：重启服务")
print("  uv run python main.py")
