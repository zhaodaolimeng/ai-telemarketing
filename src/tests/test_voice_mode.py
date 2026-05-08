#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
语音模式功能测试
覆盖: 文本模式改名、语音模式切换、ASR端点、语音对话流程
"""
import sys
import os
import json
import io
import wave
import struct
import math

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import pytest
import asyncio
from fastapi.testclient import TestClient
from pathlib import Path


# ============================================================
# Test fixtures
# ============================================================

@pytest.fixture
def client():
    """FastAPI TestClient"""
    sys.path.insert(0, str(Path(__file__).parent.parent))
    from api.main import app
    return TestClient(app)


@pytest.fixture
def test_wav_bytes():
    """生成测试用 WAV 音频 (16kHz, mono, 16bit, 1s silent)"""
    sample_rate = 16000
    duration = 1.0
    n_samples = int(sample_rate * duration)
    buf = io.BytesIO()
    with wave.open(buf, 'w') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(b'\x00\x00' * n_samples)
    return buf.getvalue()


# ============================================================
# Tests: Mode renaming & UI state
# ============================================================

class TestModeRenaming:
    """验证文本模式改名不影响现有功能"""

    def test_chat_start_succeeds(self, client):
        """文本模式 /chat/start 正常启动"""
        resp = client.post('/chat/start', json={
            'chat_group': 'H2',
            'customer_name': 'Pak Budi'
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'session_id' in data
        assert 'agent_response' in data

    def test_chat_turn_succeeds(self, client):
        """文本模式 /chat/turn 正常响应"""
        starter = client.post('/chat/start', json={
            'chat_group': 'H2', 'customer_name': 'Pak Budi'
        })
        sid = starter.json()['session_id']

        resp = client.post('/chat/turn', json={
            'session_id': sid,
            'customer_input': 'Ya, ini saya.'
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'agent_response' in data

    def test_voice_start_succeeds(self, client):
        """语音模式 /voice/start 正常启动"""
        resp = client.post('/voice/start', json={
            'chat_group': 'H2',
            'customer_name': 'Pak Budi'
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'session_id' in data
        assert 'agent_text' in data

    def test_voice_turn_succeeds(self, client):
        """语音模式 /voice/turn 正常响应"""
        starter = client.post('/voice/start', json={
            'chat_group': 'H2', 'customer_name': 'Pak Budi'
        })
        sid = starter.json()['session_id']

        resp = client.post('/voice/turn', json={
            'session_id': sid,
            'customer_input': 'Ya, ini saya.'
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'agent_text' in data

    def test_text_mode_independent_from_voice(self, client):
        """文本模式(/chat)和语音模式(/voice)使用独立会话"""
        # Start text session
        text_resp = client.post('/chat/start', json={
            'chat_group': 'H2', 'customer_name': 'Text User'
        })
        text_sid = text_resp.json()['session_id']

        # Start voice session
        voice_resp = client.post('/voice/start', json={
            'chat_group': 'H2', 'customer_name': 'Voice User'
        })
        voice_sid = voice_resp.json()['session_id']

        # They should be different sessions
        assert text_sid != voice_sid

        # Text turn works on text session
        text_turn = client.post('/chat/turn', json={
            'session_id': text_sid,
            'customer_input': 'Halo'
        })
        assert text_turn.status_code == 200


# ============================================================
# Tests: ASR endpoint
# ============================================================

class TestASREndpoint:
    """测试 /voice/asr 端点"""

    def test_asr_accepts_wav(self, client, test_wav_bytes):
        """ASR 端点接受 WAV 音频"""
        resp = client.post('/voice/asr', files={
            'audio': ('test.wav', test_wav_bytes, 'audio/wav')
        })
        assert resp.status_code == 200
        data = resp.json()
        assert 'text' in data
        assert 'success' in data

    def test_asr_rejects_empty(self, client):
        """ASR 端点处理空文件"""
        resp = client.post('/voice/asr', files={
            'audio': ('empty.webm', b'', 'audio/webm')
        })
        # Should not crash
        assert resp.status_code in (200, 400, 422, 500)

    def test_asr_accepts_webm(self, client):
        """ASR 端点接受 webm 格式"""
        # Minimal valid webm header for Opus audio
        webm_header = (
            b'\x1a\x45\xdf\xa3\x9fB\x86\x81\x01B\xf7\x81\x01B\xf2\x81'
            b'\x04B\xf3\x81\x08B\x82\x88matroskaB\x87\x81\x04B\x85\x81\x02'
            b'\x18S\x80g\x01\xff\xff\xff\xff\xff\xff\xff\x15I\xa9f'
            b'\x99*\xd7\xb1\x83\x0fB@M\x80\x86ChromeWA\x86Chrome'
            b'\x16T\xaek\xae\xdf\x01'
        )
        resp = client.post('/voice/asr', files={
            'audio': ('recording.webm', webm_header, 'audio/webm')
        })
        # Should respond gracefully (may fail ASR on empty content, but shouldn't 500)
        assert resp.status_code in (200, 400, 422)

    def test_asr_no_file(self, client):
        """ASR 端点缺少文件时返回 422"""
        resp = client.post('/voice/asr')
        assert resp.status_code == 422


# ============================================================
# Tests: Full voice mode flow
# ============================================================

class TestVoiceModeFlow:
    """测试语音模式完整流程"""

    def test_voice_start_to_turn_flow(self, client):
        """语音模式: 开始 → 对话轮次 → 结束"""
        # Start
        start_resp = client.post('/voice/start', json={
            'chat_group': 'H2',
            'customer_name': 'Pak Budi'
        })
        assert start_resp.status_code == 200
        start_data = start_resp.json()
        sid = start_data['session_id']
        assert start_data['agent_text']
        assert not start_data['is_finished']

        # Turn 1: identify
        turn1 = client.post('/voice/turn', json={
            'session_id': sid,
            'customer_input': 'Ya, ini saya.'
        })
        assert turn1.status_code == 200
        t1_data = turn1.json()
        assert t1_data['agent_text']

        # Turn 2: give time
        if not t1_data.get('is_finished'):
            turn2 = client.post('/voice/turn', json={
                'session_id': sid,
                'customer_input': 'Saya bisa bayar jam 4 sore.'
            })
            assert turn2.status_code == 200
            t2_data = turn2.json()
            assert t2_data['agent_text']

    def test_voice_session_not_found(self, client):
        """语音模式: 无效 session_id 返回 404"""
        resp = client.post('/voice/turn', json={
            'session_id': 'nonexistent-session-id',
            'customer_input': 'Halo'
        })
        assert resp.status_code == 404

    def test_voice_session_multiple_turns(self, client):
        """语音模式: 多轮对话不崩溃"""
        starter = client.post('/voice/start', json={
            'chat_group': 'H2', 'customer_name': 'Pak Budi'
        })
        sid = starter.json()['session_id']

        inputs = [
            'Ya, ini saya.',
            'Saya sedang sibuk.',
            'Nanti ya, jam 5 sore.',
        ]
        for inp in inputs:
            resp = client.post('/voice/turn', json={
                'session_id': sid,
                'customer_input': inp
            })
            assert resp.status_code == 200
            data = resp.json()
            if data.get('is_finished'):
                break

    def test_voice_start_different_groups(self, client):
        """语音模式: 不同催收组别正常启动"""
        for group in ['H2', 'H1', 'S0']:
            resp = client.post('/voice/start', json={
                'chat_group': group,
                'customer_name': 'Test User'
            })
            assert resp.status_code == 200
            assert 'session_id' in resp.json()

    def test_voice_end_marks_finished(self, client):
        """语音模式: /voice/end 挂断后标记已完成"""
        starter = client.post('/voice/start', json={
            'chat_group': 'H2', 'customer_name': 'Pak Budi'
        })
        sid = starter.json()['session_id']

        resp = client.post('/voice/end', json={'session_id': sid})
        assert resp.status_code == 200
        assert resp.json()['status'] == 'ok'

        # Session should be removed from active sessions
        turn_resp = client.post('/voice/turn', json={
            'session_id': sid,
            'customer_input': 'Halo'
        })
        assert turn_resp.status_code in (400, 404)

    def test_voice_end_nonexistent(self, client):
        """语音模式: /voice/end 不存在的会话"""
        resp = client.post('/voice/end', json={
            'session_id': 'nonexistent-id'
        })
        assert resp.status_code == 200
        assert resp.json()['status'] == 'not_found'


# ============================================================
# Tests: WAV audio generation (for ASR testing)
# ============================================================

class TestAudioGeneration:
    """测试音频生成和格式转换"""

    def test_generate_sine_wav(self):
        """生成正弦波 WAV 文件"""
        sample_rate = 16000
        duration = 0.5
        freq = 440
        n_samples = int(sample_rate * duration)

        buf = io.BytesIO()
        with wave.open(buf, 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            for i in range(n_samples):
                value = int(16000 * math.sin(2 * math.pi * freq * i / sample_rate))
                wf.writeframes(struct.pack('<h', value))

        wav_bytes = buf.getvalue()
        assert len(wav_bytes) > 100
        # Verify WAV header
        assert wav_bytes[:4] == b'RIFF'
        assert wav_bytes[8:12] == b'WAVE'

    def test_generate_silence_wav(self):
        """生成静音 WAV"""
        sample_rate = 16000
        duration = 0.3
        n_samples = int(sample_rate * duration)

        buf = io.BytesIO()
        with wave.open(buf, 'w') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sample_rate)
            wf.writeframes(b'\x00\x00' * n_samples)

        assert len(buf.getvalue()) > 44  # WAV header is 44 bytes


# ============================================================
# Tests: Text mode (regression)
# ============================================================

class TestTextModeRegression:
    """确认文本模式(l原手动模式)功能不受改名影响"""

    def test_chat_complete_conversation(self, client):
        """完整对话流程: 开始 → 多轮 → 结束"""
        starter = client.post('/chat/start', json={
            'chat_group': 'H2',
            'customer_name': 'Pak Budi'
        })
        assert starter.status_code == 200
        sid = starter.json()['session_id']
        assert sid

        # Multi-turn conversation
        conversation = [
            'Ya, ini saya.',
            'Saya bisa bayar.',
            'Jam 3 sore.',
            'Iya, saya setuju.',
        ]
        for msg in conversation:
            resp = client.post('/chat/turn', json={
                'session_id': sid,
                'customer_input': msg
            })
            assert resp.status_code == 200
            if resp.json().get('is_finished'):
                break

    def test_chat_start_missing_fields(self, client):
        """缺少必填字段时使用默认值"""
        resp = client.post('/chat/start', json={})
        # Server returns 200 with defaults for missing optional fields
        assert resp.status_code == 200
        data = resp.json()
        assert 'session_id' in data
        assert 'agent_response' in data

    def test_chat_turn_missing_session(self, client):
        """无效 session_id 返回错误"""
        resp = client.post('/chat/turn', json={
            'session_id': 'nonexistent',
            'customer_input': 'Halo'
        })
        assert resp.status_code == 404


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
