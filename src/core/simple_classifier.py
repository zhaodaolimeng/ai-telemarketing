#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简易意图分类器 - 基于朴素贝叶斯的轻量级文本分类器
作为规则式IntentDetector的补充，提升unknown类别的识别率
"""
import json
import pickle
import re
from pathlib import Path
from typing import List, Dict, Tuple

# 可选依赖：scikit-learn
try:
    from sklearn.feature_extraction.text import CountVectorizer
    from sklearn.naive_bayes import MultinomialNB
    from sklearn.pipeline import Pipeline
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report
    SKLEARN_AVAILABLE = True
except ImportError:
    SKLEARN_AVAILABLE = False


class SimpleIntentClassifier:
    """简易意图分类器，使用词袋模型+朴素贝叶斯"""

    def __init__(self):
        if not SKLEARN_AVAILABLE:
            raise ImportError("需要安装scikit-learn才能使用本功能: pip install scikit-learn")

        self.pipeline = None
        self.intent_labels = set()
        self.is_trained = False

        # 印尼语常用停用词（精简版）
        self.stop_words = [
            'yang', 'dan', 'di', 'ke', 'dari', 'untuk', 'pada', 'dengan', 'adalah',
            'ini', 'itu', 'saya', 'anda', 'kita', 'kami', 'mereka', 'dia', 'nya',
            'ya', 'iya', 'tidak', 'bukan', 'sudah', 'belum', 'akan', 'bisa',
            'pagi', 'siang', 'sore', 'malam', 'selamat', 'halo', 'hai', 'pak', 'bu'
        ]

        # 预处理正则
        self.clean_pattern = re.compile(r'[^\w\s]')

    def _preprocess(self, text: str) -> str:
        """文本预处理：小写化、去标点、去停用词"""
        # 小写化
        text = text.lower()
        # 去标点
        text = self.clean_pattern.sub('', text)
        # 去停用词
        words = text.split()
        words = [w for w in words if w not in self.stop_words]
        return ' '.join(words)

    def load_training_data(self, data_dir: str = 'data/gold_dataset') -> Tuple[List[str], List[str]]:
        """从黄金数据集加载训练数据"""
        texts = []
        labels = []

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
                    if text and intent and intent != 'unknown':
                        texts.append(self._preprocess(text))
                        labels.append(intent)
                        self.intent_labels.add(intent)

        print(f"加载训练数据: {len(texts)} 条样本，共 {len(self.intent_labels)} 种意图")
        return texts, labels

    def train(self, data_dir: str = 'data/gold_dataset', test_size: float = 0.2) -> Dict:
        """训练分类器"""
        texts, labels = self.load_training_data(data_dir)

        if len(texts) < 100:
            print("警告：训练数据不足，可能影响分类效果")

        # 统计每个类别的样本数
        from collections import Counter
        label_counts = Counter(labels)
        min_count = min(label_counts.values())

        # 划分训练集测试集：最少的类别样本数>=2时才用分层抽样，否则用普通随机抽样
        if min_count >= 2:
            X_train, X_test, y_train, y_test = train_test_split(
                texts, labels, test_size=test_size, random_state=42, stratify=labels
            )
        else:
            print(f"警告：存在样本数<2的类别，禁用分层抽样，最少样本数: {min_count}")
            X_train, X_test, y_train, y_test = train_test_split(
                texts, labels, test_size=test_size, random_state=42
            )

        # 创建pipeline：词袋向量化 + 多项式朴素贝叶斯
        self.pipeline = Pipeline([
            ('vectorizer', CountVectorizer(ngram_range=(1, 2))),  # 1-gram和2-gram
            ('classifier', MultinomialNB(alpha=0.1))  # 拉普拉斯平滑
        ])

        # 训练
        self.pipeline.fit(X_train, y_train)
        self.is_trained = True

        # 评估
        y_pred = self.pipeline.predict(X_test)
        report = classification_report(y_test, y_pred, output_dict=True)

        print("\n训练完成！测试集评估结果：")
        print(f"整体准确率: {report['accuracy']:.4f}")
        print(f"宏平均F1: {report['macro avg']['f1-score']:.4f}")

        return report

    def predict(self, text: str, top_k: int = 3) -> List[Tuple[str, float]]:
        """预测意图，返回top k个结果和概率"""
        if not self.is_trained:
            raise ValueError("分类器尚未训练，请先调用train()方法")

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


def train_and_save_model():
    """训练并保存模型的快捷方法"""
    classifier = SimpleIntentClassifier()
    classifier.train()
    classifier.save_model()
    print("\n模型训练并保存完成！")

    # 测试样例
    test_cases = [
        "Saya akan bayar besok",
        "Saya tidak punya uang sekarang",
        "Ini bukan saya yang punya pinjaman",
        "Transfer kemana ya pak?",
        "Oke, saya transfer jam 3 nanti",
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
