#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
初始化数据库
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from api.database import init_db, init_script_library, get_db

print("正在初始化数据库...")
init_db()
print("数据库表创建完成!")

print("\n正在初始化脚本库...")
db = next(get_db())
init_script_library(db)
print("脚本库初始化完成!")

print("\n数据库初始化成功!")
