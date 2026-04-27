#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
API测试脚本
"""
import requests
import time
import json

BASE_URL = "http://localhost:8000"


def test_health():
    """测试健康检查接口"""
    print("\n--- 测试健康检查 ---")
    response = requests.get(f"{BASE_URL}/health")
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")
    return response.status_code == 200


def test_chat_flow():
    """测试完整对话流程"""
    print("\n--- 测试完整对话流程 ---")

    # 1. 开始对话
    print("\n1. 开始对话...")
    response = requests.post(f"{BASE_URL}/chat/start", json={
        "chat_group": "H2",
        "customer_name": "Pak Budi"
    })
    print(f"状态码: {response.status_code}")
    data = response.json()
    print(f"响应: {json.dumps(data, indent=2, ensure_ascii=False)}")

    if response.status_code != 200:
        return False

    session_id = data["session_id"]
    print(f"会话ID: {session_id}")
    print(f"Agent: {data['agent_response']}")

    # 2. 继续对话
    customer_inputs = [
        "Halo",
        "Oh ya, saya lupa",
        "Nanti ya",
        "Jam 5 deh",
        "Iya"
    ]

    for customer_input in customer_inputs:
        if data["is_finished"]:
            break

        time.sleep(0.5)
        print(f"\nCustomer: {customer_input}")

        response = requests.post(f"{BASE_URL}/chat/turn", json={
            "session_id": session_id,
            "customer_input": customer_input
        })
        data = response.json()
        print(f"Agent: {data['agent_response']}")
        print(f"状态: {data['current_state']}")

    # 3. 获取会话信息
    print("\n3. 获取会话信息...")
    response = requests.get(f"{BASE_URL}/chat/session/{session_id}")
    print(f"状态码: {response.status_code}")
    session_data = response.json()
    print(f"会话长度: {session_data['conversation_length']}")
    print(f"成功: {session_data['is_successful']}")
    print(f"约定时间: {session_data['commit_time']}")

    # 4. 关闭会话
    print("\n4. 关闭会话...")
    response = requests.post(f"{BASE_URL}/chat/session/{session_id}/close")
    print(f"状态码: {response.status_code}")
    print(f"响应: {json.dumps(response.json(), indent=2, ensure_ascii=False)}")

    return True


def test_session_list():
    """测试会话列表"""
    print("\n--- 测试会话列表 ---")
    response = requests.get(f"{BASE_URL}/chat/sessions")
    print(f"状态码: {response.status_code}")
    sessions = response.json()
    print(f"会话数量: {len(sessions)}")
    for session in sessions[:3]:
        print(f"  - {session['session_id']}: {session['chat_group']}, 成功={session['is_successful']}")
    return response.status_code == 200


def test_test_scenario():
    """测试测试场景接口"""
    print("\n--- 测试测试场景接口 ---")
    response = requests.post(f"{BASE_URL}/test/scenario", json={
        "chat_group": "H2",
        "persona": "cooperative",
        "num_tests": 3
    })
    print(f"状态码: {response.status_code}")
    result = response.json()
    print(f"总数: {result['total_tests']}")
    print(f"成功: {result['success_count']}")
    print(f"成功率: {result['success_rate']}%")
    return response.status_code == 200


def main():
    """主函数"""
    print("=" * 70)
    print("智能催收对话系统 API 测试")
    print("=" * 70)

    try:
        # 检查服务是否启动
        print("\n检查服务连接...")
        try:
            requests.get(f"{BASE_URL}/health", timeout=2)
        except:
            print("服务未启动!")
            print(f"\n请先运行: python -m uvicorn api.main:app --host 0.0.0.0 --port 8000")
            return

        all_passed = True

        all_passed &= test_health()
        all_passed &= test_chat_flow()
        all_passed &= test_session_list()
        all_passed &= test_test_scenario()

        print("\n" + "=" * 70)
        if all_passed:
            print("所有测试通过!")
        else:
            print("部分测试失败!")
        print("=" * 70)

    except Exception as e:
        print(f"\n错误: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
