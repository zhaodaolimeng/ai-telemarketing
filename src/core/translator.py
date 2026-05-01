#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
印尼文-英文翻译模块
支持多种翻译方案：
1. 本地Transformers模型 (MarianMT) - 优先
2. deep-translator (Google/MyMemory)
3. translators 库
4. 回退的单词映射
"""

import time
from typing import Optional
from dataclasses import dataclass
from functools import lru_cache


@dataclass
class TranslationResult:
    original_text: str
    translated_text: str
    source_lang: str
    target_lang: str
    success: bool
    service_used: str = ""


class Translator:
    """多方案翻译器 - 优先本地模型"""

    def __init__(self, prefer_local: bool = True):
        self.services = []
        self._translation_cache = {}
        self._local_model = None
        self._local_tokenizer = None
        self._local_available = False
        self._prefer_local = prefer_local
        self._init_services()

    def _init_services(self):
        """初始化可用的翻译服务 - 先尝试本地模型"""
        # 1. 优先：本地翻译模型 (MarianMT)
        try:
            self._init_local_model()
            if self._local_available:
                self.services.append(("local", "local"))
                print("✅ Local MarianMT model available")
        except Exception as e:
            print(f"⚠️ Local model not available: {e}")

        # 2. 尝试 deep-translator
        try:
            from deep_translator import GoogleTranslator, MyMemoryTranslator
            self.services.append(("google", GoogleTranslator))
            self.services.append(("mymemory", MyMemoryTranslator))
            print("✅ deep-translator available")
        except ImportError:
            print("⚠️ deep-translator not available")

        # 3. 尝试 translators 库
        try:
            import translators as ts
            self.services.append(("translators", ts))
            print("✅ translators library available")
        except ImportError:
            print("⚠️ translators library not available")

    def _init_local_model(self):
        """初始化本地MarianMT翻译模型"""
        try:
            from transformers import MarianMTModel, MarianTokenizer
            import torch

            # 印尼文->英文 模型
            model_name = "Helsinki-NLP/opus-mt-id-en"

            print(f"Loading local translation model: {model_name}")
            self._local_tokenizer = MarianTokenizer.from_pretrained(model_name)
            self._local_model = MarianMTModel.from_pretrained(model_name)

            # 也加载英文->印尼文 模型
            self._local_tokenizer_en_id = MarianTokenizer.from_pretrained("Helsinki-NLP/opus-mt-en-id")
            self._local_model_en_id = MarianMTModel.from_pretrained("Helsinki-NLP/opus-mt-en-id")

            self._local_available = True
            print("✅ Local translation models loaded successfully!")
        except ImportError as e:
            print(f"⚠️ transformers not installed: {e}")
            print("   Run: pip install transformers torch sentencepiece")
        except Exception as e:
            print(f"⚠️ Could not load local model: {e}")

    def _translate_local(self, text: str, source_lang: str, target_lang: str) -> str:
        """使用本地模型翻译"""
        if not self._local_available:
            raise Exception("Local model not available")

        try:
            import torch

            if source_lang == "id" and target_lang == "en":
                tokenizer = self._local_tokenizer
                model = self._local_model
            elif source_lang == "en" and target_lang == "id":
                tokenizer = self._local_tokenizer_en_id
                model = self._local_model_en_id
            else:
                raise Exception(f"Unsupported language pair: {source_lang}->{target_lang}")

            # Tokenize
            inputs = tokenizer(text, return_tensors="pt", padding=True, truncation=True, max_length=512)

            # Generate translation
            with torch.no_grad():
                translated = model.generate(**inputs, max_new_tokens=100)

            # Decode
            result = tokenizer.decode(translated[0], skip_special_tokens=True)
            return result

        except Exception as e:
            print(f"Local translation failed: {e}")
            raise

    def translate(
        self,
        text: str,
        source_lang: str = "id",
        target_lang: str = "en",
        timeout: float = 10.0
    ) -> TranslationResult:
        """
        翻译文本

        Args:
            text: 原文
            source_lang: 源语言 (id/en/zh)
            target_lang: 目标语言 (en/id/zh)
            timeout: 超时时间（秒）

        Returns:
            翻译结果
        """
        text = text.strip()
        if not text:
            return TranslationResult(text, text, source_lang, target_lang, True, "empty")

        if source_lang == target_lang:
            return TranslationResult(text, text, source_lang, target_lang, True, "same")

        # 检查缓存
        cache_key = (text, source_lang, target_lang)
        if cache_key in self._translation_cache:
            return self._translation_cache[cache_key]

        # 优先尝试本地模型
        if self._local_available and self._prefer_local:
            try:
                start_time = time.time()
                result = self._translate_local(text, source_lang, target_lang)
                if result and time.time() - start_time < timeout:
                    trans_result = TranslationResult(text, result, source_lang, target_lang, True, "local")
                    self._translation_cache[cache_key] = trans_result
                    return trans_result
            except Exception as e:
                print(f"Local translation failed: {e}")

        # 尝试其他翻译服务
        for service_name, service in self.services:
            if service_name == "local":
                continue  # 已经试过了

            try:
                start_time = time.time()

                if service_name == "google":
                    from deep_translator import GoogleTranslator
                    translator = GoogleTranslator(source=source_lang, target=target_lang)
                    result = translator.translate(text)
                    if time.time() - start_time < timeout:
                        trans_result = TranslationResult(text, result, source_lang, target_lang, True, "google")
                        self._translation_cache[cache_key] = trans_result
                        return trans_result

                elif service_name == "mymemory":
                    from deep_translator import MyMemoryTranslator
                    translator = MyMemoryTranslator(source=source_lang, target=target_lang)
                    result = translator.translate(text)
                    if time.time() - start_time < timeout:
                        trans_result = TranslationResult(text, result, source_lang, target_lang, True, "mymemory")
                        self._translation_cache[cache_key] = trans_result
                        return trans_result

                elif service_name == "translators":
                    import translators as ts
                    result = ts.translate_text(text, from_language=source_lang, to_language=target_lang)
                    if time.time() - start_time < timeout:
                        trans_result = TranslationResult(text, result, source_lang, target_lang, True, "translators")
                        self._translation_cache[cache_key] = trans_result
                        return trans_result

            except Exception as e:
                print(f"Service {service_name} failed: {e}")
                continue

        # 所有服务都失败或超时，使用回退方案
        result = self._fallback_translate(text, source_lang, target_lang)
        trans_result = TranslationResult(text, result, source_lang, target_lang, True, "fallback")
        self._translation_cache[cache_key] = trans_result
        return trans_result

    @lru_cache(maxsize=1000)
    def _fallback_translate(self, text: str, source_lang: str, target_lang: str) -> str:
        """回退翻译方案 - 单词级映射"""
        # 印尼文到英文
        id_to_en = {
            "Halo": "Hello",
            "Selamat pagi": "Good morning",
            "Selamat siang": "Good afternoon",
            "Selamat sore": "Good evening",
            "Selamat malam": "Good night",
            "Terima kasih": "Thank you",
            "Ya": "Yes",
            "Tidak": "No",
            "Maaf": "Sorry",
            "Bagaimana kabar Anda": "How are you",
            "Kapan": "When",
            "Berapa": "How much",
            "Saya": "I",
            "Anda": "You",
            "Kami": "We",
            "Mereka": "They",
            "Ini": "This",
            "Itu": "That",
            "Pak": "Mr",
            "Bu": "Mrs",
            "aplikasi": "application",
            "dari": "from",
            "pinjaman": "loan",
            "bayar": "pay",
            "waktu": "time",
            "hari": "day",
            "besok": "tomorrow",
            "hari ini": "today",
            "jam": "o'clock",
            "janji": "promise",
            "ingat": "remember",
            "lupa": "forget",
            "sibuk": "busy",
            "kesulitan": "difficulty",
            "Extra": "Extra"
        }

        # 英文到印尼文
        en_to_id = {v: k for k, v in id_to_en.items()}

        if source_lang == "id" and target_lang == "en":
            # 完整短语匹配
            if text in id_to_en:
                return id_to_en[text]
            # 单词级替换
            result = text
            for id_word, en_word in id_to_en.items():
                if len(id_word.split()) == 1:
                    result = result.replace(id_word, en_word)
            return result
        elif source_lang == "en" and target_lang == "id":
            if text in en_to_id:
                return en_to_id[text]
            result = text
            for en_word, id_word in en_to_id.items():
                if len(en_word.split()) == 1:
                    result = result.replace(en_word, id_word)
            return result

        return text


# 全局翻译器实例
_translator_instance = None


def get_translator() -> Translator:
    """获取全局翻译器实例"""
    global _translator_instance
    if _translator_instance is None:
        _translator_instance = Translator()
    return _translator_instance


def translate_text(
    text: str,
    source_lang: str = "id",
    target_lang: str = "en"
) -> TranslationResult:
    """便捷翻译函数"""
    translator = get_translator()
    return translator.translate(text, source_lang, target_lang)


# 测试
if __name__ == "__main__":
    print("=" * 70)
    print("印尼文-英文翻译测试")
    print("=" * 70)

    test_texts = [
        ("Halo, selamat siang Pak Budi. Saya dari aplikasi Extra.", "id", "en"),
        ("Hello, good afternoon Mr. Budi. I'm from the Extra application.", "en", "id"),
        ("Terima kasih, saya ingat.", "id", "en"),
        ("Kapan Anda bisa bayar?", "id", "en"),
    ]

    translator = get_translator()

    for text, src, tgt in test_texts:
        print(f"\n原文 ({src}): {text}")
        result = translator.translate(text, src, tgt)
        print(f"译文 ({tgt}): {result.translated_text}")
        print(f"服务: {result.service_used}")
