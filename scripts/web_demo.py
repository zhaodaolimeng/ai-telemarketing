#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
催收机器人Web版Demo
"""
import asyncio
import uuid
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from flask import Flask, render_template, request, jsonify, session
from src.core.chatbot import CollectionChatBot

app = Flask(__name__)
app.secret_key = 'demo_secret_key_2026'

# 存储每个会话的机器人实例
bots = {}

def get_bot() -> CollectionChatBot:
    """获取当前会话的机器人实例"""
    # 生成唯一会话ID
    if 'session_id' not in session:
        session['session_id'] = str(uuid.uuid4())
    session_id = session['session_id']

    if session_id not in bots:
        # 初始化默认参数：H2阶段，逾期5天，欠款500k印尼盾
        bots[session_id] = CollectionChatBot(
            chat_group="H2",
            overdue_amount=500000,
            overdue_days=5
        )
    return bots[session_id]

@app.route('/')
def index():
    """首页"""
    bot = get_bot()
    # 获取机器人开场白
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    first_response, _ = loop.run_until_complete(bot.process())
    loop.close()

    return render_template('index.html', first_response=first_response)

@app.route('/send', methods=['POST'])
def send_message():
    """发送消息接口"""
    data = request.get_json()
    user_input = data.get('message', '').strip()

    if not user_input:
        return jsonify({'error': '消息不能为空'}), 400

    bot = get_bot()

    # 处理用户输入
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    response, _ = loop.run_until_complete(bot.process(user_input))
    loop.close()

    # 检查对话是否结束
    conversation_ended = bot.state in [bot.ChatState.CLOSE, bot.ChatState.FAILED]

    return jsonify({
        'response': response,
        'ended': conversation_ended
    })

@app.route('/reset', methods=['POST'])
def reset_chat():
    """重置对话"""
    if 'session_id' in session:
        session_id = session['session_id']
        if session_id in bots:
            del bots[session_id]
    # 清除会话ID，生成新的
    session.pop('session_id', None)

    # 获取新机器人的开场白
    bot = get_bot()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    first_response, _ = loop.run_until_complete(bot.process())
    loop.close()

    return jsonify({
        'response': first_response
    })

if __name__ == '__main__':
    print("=" * 60)
    print("🌐 印尼语智能催收机器人 Web Demo")
    print("=" * 60)
    print("📝 访问地址: http://localhost:8000")
    print("🚀 启动中...")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=8000)
