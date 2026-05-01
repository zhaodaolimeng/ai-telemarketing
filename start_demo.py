#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
启动智能催收对话系统 Demo
"""
import uvicorn
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "src"))

print("=" * 70)
print("🤖 智能催收对话系统 - Demo")
print("=" * 70)
print()
print("正在启动服务...")
print()
print("📖 API文档将在以下地址可用:")
print("   Swagger UI: http://localhost:8000/docs")
print("   ReDoc:      http://localhost:8000/redoc")
print()
print("🌐 Demo网页将在以下地址可用:")
print("   主页:       http://localhost:8000/")
print()
print("按 Ctrl+C 停止服务")
print("=" * 70)
print()

if __name__ == "__main__":
    uvicorn.run(
        "api.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True
    )
