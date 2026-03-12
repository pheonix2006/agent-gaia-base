#!/usr/bin/env python
"""AI Agent 服务启动脚本

自动检测端口占用，启动服务并打开浏览器。
"""
import os
import sys
import socket
import webbrowser
import time
from pathlib import Path

# 添加项目根目录到 Python 路径
sys.path.insert(0, str(Path(__file__).parent.parent))
sys.path.insert(0, str(Path(__file__).parent / "src"))


def find_free_port(start_port: int = 8000, max_attempts: int = 10) -> int:
    """从 start_port 开始查找可用端口"""
    for port in range(start_port, start_port + max_attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            try:
                s.bind(("", port))
                return port
            except OSError:
                continue
    raise RuntimeError(f"无法在 {start_port}-{start_port + max_attempts} 范围内找到可用端口")


def main():
    """启动服务并打开浏览器"""
    import uvicorn
    from ai_agent.api.main import app

    # 查找可用端口
    port = find_free_port(8000)
    host = "127.0.0.1"

    print("=" * 50)
    print("🚀 AI Agent 服务启动中...")
    print(f"📍 地址: http://{host}:{port}")
    print(f"📖 API 文档: http://{host}:{port}/docs")
    print("=" * 50)
    print()

    if port != 8000:
        print(f"⚠️  端口 8000 被占用，使用端口 {port}")
        print()

    # 自动打开浏览器（延迟一点让服务先启动）
    def open_browser():
        time.sleep(1.5)
        webbrowser.open(f"http://{host}:{port}/docs")

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    # 启动服务
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
