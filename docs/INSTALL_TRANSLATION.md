# 翻译功能安装指南

## 🎯 推荐：本地翻译模型（无需联网）

### 安装本地翻译库
```bash
pip install transformers torch sentencepiece
```

这会安装：
- **Hugging Face Transformers** - 模型框架
- **PyTorch** - 深度学习引擎
- **SentencePiece** - 分词器

### 使用本地模型
首次运行时会自动下载模型（约300MB）：
- Helsinki-NLP/opus-mt-id-en (印尼文→英文)
- Helsinki-NLP/opus-mt-en-id (英文→印尼文)

## 🌐 备选：在线翻译服务

### 方案1: deep-translator
```bash
pip install deep-translator
```

### 方案2: translators 库
```bash
pip install translators
```

### 方案3: 两者都安装
```bash
pip install deep-translator translators
```

## ✅ 验证安装

运行测试：
```bash
python src/core/translator.py
```

你会看到翻译测试结果，显示使用的翻译服务。

## 🚀 使用说明

安装后，重启后端服务：
```bash
python start_demo.py
```

刷新浏览器页面，翻译功能现在会使用本地模型！

## 🔧 支持的翻译服务（优先级排序）

1. **Local MarianMT** - 离线、快速、免费、优先使用
2. **Google Translate** (通过 deep-translator) - 最准确
3. **MyMemory** (通过 deep-translator) - 备选
4. **translators 库** - 多个服务支持
5. **回退翻译** - 单词映射（当所有其他服务不可用时）

## 💡 提示

- 本地模型首次加载需要下载（约300MB），之后可以离线使用
- 如果不需要联网翻译，只安装本地模型即可：`pip install transformers torch sentencepiece`
- 翻译结果会缓存，提高速度

## 📦 完整安装（本地+在线）

```bash
pip install transformers torch sentencepiece deep-translator translators
```
