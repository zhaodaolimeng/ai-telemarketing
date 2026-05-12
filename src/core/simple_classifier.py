#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简易意图分类器 - 基于逻辑回归的优化版文本分类器
作为规则式IntentDetector的补充，提升unknown类别的识别率
"""
import json
import pickle
import re
from pathlib import Path
from typing import List, Dict, Tuple

# 可选依赖：scikit-learn
try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.linear_model import LogisticRegression
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report
    from sklearn.pipeline import Pipeline
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class SimpleIntentClassifier:
    """简易意图分类器，使用TF-IDF + Logistic Regression"""

    # P15-C01: 意图类别合并映射 — 将 LLM 细粒度标签合并到 chatbot 处理器粒度
    # 原则: (1) 同一 chatbot handler 的合并 (2) 语义等价合并 (3) 样本数<5的合并到最近父类
    INTENT_CONSOLIDATION = {
        # 同 handler 合并 (chatbot L1308: ask_extension 与 request_short_extension 同处理)
        "request_short_extension": "ask_extension",
        # 同 handler 合并 (chatbot L1367: deny_identity 与 third_party 同处理)
        # "third_party" → 保留，14 样本足够
        # 威胁/辱骂合并 (chatbot L1553: threaten 单独处理，user_abuse 无独立 handler)
        "user_abuse": "threaten",
        # 身份质疑合并 (chatbot L1597/L1601: question_identity 与 request_identity_verification 相邻)
        "request_identity_verification": "question_identity",
        # 费用/利息投诉合并 (chatbot L1605/L1613: 相邻处理)
        "complain_high_interest": "ask_fee",
        "request_interest_reduction": "ask_fee",
        # 暗示还款意愿 → agree_to_pay
        "borrowing_money": "agree_to_pay",
        "transfer_in_process": "agree_to_pay",
        # 沉默变体合并
        "silence_or_noise": "silence",
        # Gold dataset 旧标签合并
        "respond_to_greeting": "greeting",
        "acknowledge_debt": "agree_to_pay",
        "cannot_repay_now": "no_money",
        # 极稀类(<5样本)合并到最近父类，待后续 LLM 标注补充后拆分
        "request_payment_reminder": "ask_extension",   # 都是请求类
        "request_settlement_proof": "ask_fee",          # 行政管理类
        "app_uninstalled": "dont_know",                 # 无法继续表达
        "inquire_consequences": "ask_fee",              # 财务后果类
    }

    def __init__(self):
        if not SKLEARN_AVAILABLE:
            raise ImportError("需要安装scikit-learn才能使用本功能: pip install scikit-learn")

        self.pipeline = None
        self.intent_labels = set()
        self.is_trained = False

        # 印尼语常用停用词（精简版）
        self.stop_words = [
            "yang", "dan", "di", "ke", "dari", "untuk", "pada", "dengan", "adalah",
            "ini", "itu", "saya", "anda", "kita", "kami", "mereka", "dia", "nya",
            "ya", "iya", "tidak", "bukan", "sudah", "belum", "akan", "bisa",
            "pagi", "siang", "sore", "malam", "selamat", "halo", "hai", "pak", "bu"
        ]

        # 预处理正则
        self.clean_pattern = re.compile(r'[^\w\s]')

    @classmethod
    def consolidate_intent(cls, intent: str) -> str:
        """应用合并映射，返回合并后的意图标签"""
        return cls.INTENT_CONSOLIDATION.get(intent, intent)

    def _preprocess(self, text: str) -> str:
        """文本预处理：小写化、去标点"""
        # 小写化
        text = text.lower()
        # 去标点
        text = self.clean_pattern.sub('', text)
        return text

    def load_training_data(self, data_dir: str = 'data/raw/gold_dataset',
                            llm_labels_path: str = None,
                            apply_consolidation: bool = True) -> Tuple[List[str], List[str]]:
        """从黄金数据集加载训练数据，可选补充 LLM 精标注数据

        Args:
            apply_consolidation: 应用 INTENT_CONSOLIDATION 合并细粒度标签
        """
        texts = []
        labels = []
        consolidate_count = {}  # 统计合并数量

        gold_path = Path(data_dir)
        for file_path in gold_path.glob('*.json'):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
            except Exception as e:
                print(f"读取文件失败 {file_path}: {e}")
                continue

            dialogue = data.get('dialogue', [])
            for turn in dialogue:
                if turn.get('speaker') == 'customer':
                    text = turn.get('text', '').strip()
                    intent = turn.get('user_intent', '').strip()
                    if text and intent and intent != 'unknown' and intent != 'unknown_intent':
                        if apply_consolidation:
                            original = intent
                            intent = self.consolidate_intent(intent)
                            if original != intent:
                                consolidate_count[f"{original}→{intent}"] = \
                                    consolidate_count.get(f"{original}→{intent}", 0) + 1
                        texts.append(self._preprocess(text))
                        labels.append(intent)
                        self.intent_labels.add(intent)

        # 补充 LLM 精标注数据
        if llm_labels_path and Path(llm_labels_path).exists():
            with open(llm_labels_path, 'r', encoding='utf-8') as f:
                llm_data = json.load(f)
            llm_samples = llm_data.get('training_data', [])
            llm_added = 0
            for s in llm_samples:
                text = s.get('text', '').strip()
                intent = s.get('intent', 'unknown').strip()
                if text and intent and intent != 'unknown':
                    if apply_consolidation:
                        original = intent
                        intent = self.consolidate_intent(intent)
                        if original != intent:
                            consolidate_count[f"{original}→{intent}"] = \
                                consolidate_count.get(f"{original}→{intent}", 0) + 1
                    texts.append(self._preprocess(text))
                    labels.append(intent)
                    self.intent_labels.add(intent)
                    llm_added += 1
            print(f"补充 LLM 精标注数据: {llm_added} 条")

        if consolidate_count:
            print(f"意图合并统计 ({sum(consolidate_count.values())} 条被合并):")
            for mapping, count in sorted(consolidate_count.items(), key=lambda x: -x[1]):
                print(f"  {mapping}: {count}")

        print(f"加载训练数据: {len(texts)} 条样本，共 {len(self.intent_labels)} 种意图")
        return texts, labels

    def train(self, data_dir: str = 'data/raw/gold_dataset', test_size: float = 0.2,
              llm_labels_path: str = None,
              apply_consolidation: bool = True) -> Dict:
        """训练分类器，可选补充 LLM 精标注数据"""
        texts, labels = self.load_training_data(
            data_dir, llm_labels_path=llm_labels_path,
            apply_consolidation=apply_consolidation)

        if len(texts) < 100:
            print("警告：训练数据不足，可能影响分类效果")

        # 统计每个类别的样本数
        from collections import Counter
        label_counts = Counter(labels)
        print("各类别样本数:")
        for label, count in label_counts.most_common():
            print(f"  {label}: {count}")

        # 划分训练集测试集：最少的类别样本数>=2时才用分层抽样，否则用普通随机抽样
        min_count = min(label_counts.values())
        if min_count >= 2:
            X_train, X_test, y_train, y_test = train_test_split(
                texts, labels, test_size=test_size, random_state=42, stratify=labels
            )
        else:
            print(f"警告：存在样本数<2的类别，禁用分层抽样，最少样本数: {min_count}")
            X_train, X_test, y_train, y_test = train_test_split(
                texts, labels, test_size=test_size, random_state=42
            )

        # 创建pipeline：TF-IDF向量化 + Logistic Regression
        self.pipeline = Pipeline([
            ('tfidf', TfidfVectorizer(max_features=5000, ngram_range=(1, 2))),
            ('clf', LogisticRegression(C=10, class_weight='balanced', random_state=42, max_iter=500)),
        ])

        # 训练
        self.pipeline.fit(X_train, y_train)
        self.is_trained = True

        # 评估
        y_pred = self.pipeline.predict(X_test)
        report = classification_report(y_test, y_pred, output_dict=True, zero_division=0)

        print("\n训练完成！测试集评估结果：")
        print(f"整体准确率: {report['accuracy']:.4f}")
        print(f"宏平均F1: {report['macro avg']['f1-score']:.4f}")

        return report

    def predict(self, text: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """预测意图，返回top k个结果和概率"""
        if not self.is_trained:
            raise ValueError("分类器尚未训练，请先调用 train() 方法")

        processed_text = self._preprocess(text)
        probabilities = self.pipeline.predict_proba([processed_text])[0]

        # 排序返回top k
        intent_probs = list(zip(self.pipeline.classes_, probabilities))
        intent_probs.sort(key=lambda x: x[1], reverse=True)

        return intent_probs[:top_k]

    def save_model(self, path: str = 'models/simple_intent_classifier.pkl'):
        """保存模型到文件"""
        if not self.is_trained:
            raise ValueError("分类器尚未训练，无法保存")

        Path(path).parent.mkdir(exist_ok=True)
        with open(path, 'wb') as f:
            pickle.dump({
                'pipeline': self.pipeline,
                'intent_labels': self.intent_labels,
                'stop_words': self.stop_words
            }, f)
        print(f"模型已保存到: {path}")

    @classmethod
    def load_model(cls, path: str = 'models/simple_intent_classifier.pkl') -> 'SimpleIntentClassifier':
        """从文件加载模型"""
        if not Path(path).exists():
            raise FileNotFoundError(f"模型文件不存在: {path}")

        with open(path, 'rb') as f:
            data = pickle.load(f)

        classifier = cls()
        classifier.pipeline = data['pipeline']
        classifier.intent_labels = data['intent_labels']
        classifier.stop_words = data['stop_words']
        classifier.is_trained = True

        return classifier


def train_and_save_model(llm_labels_path: str = None, apply_consolidation: bool = True):
    """训练并保存模型的快捷方法"""
    classifier = SimpleIntentClassifier()
    classifier.train(llm_labels_path=llm_labels_path, apply_consolidation=apply_consolidation)
    classifier.save_model()
    print("\n模型训练并保存完成！")

    # 测试样例
    test_cases = [
        "Saya akan bayar besok",
        "Saya tidak punya uang sekarang",
        "Ini bukan saya yang punya pinjaman",
        "Transfer kemana ya pak?",
        "Oke saya transfer jam 3 nanti",
        "Saya sedang sibuk sekarang, nanti bicara ya"
    ]

    print("\n测试样例预测结果：")
    for test in test_cases:
        results = classifier.predict(test, top_k=2)
        print(f"\n输入: {test}")
        for intent, prob in results:
            print(f"  {intent}: {prob:.4f}")


if __name__ == "__main__":
    train_and_save_model()
