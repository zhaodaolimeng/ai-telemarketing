# 印尼智能催收系统 Docker 镜像
# 基于Python 3.10 slim版本，兼顾大小和功能
FROM python:3.10-slim-bookworm

# 环境变量配置
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
ENV ENV production
ENV TZ Asia/Jakarta

# 设置工作目录
WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    g++ \
    build-essential \
    curl \
    ffmpeg \  # 语音处理需要
    && rm -rf /var/lib/apt/lists/*

# 先复制requirements.txt，利用Docker缓存
COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# 复制项目代码
COPY . .

# 创建必要的目录
RUN mkdir -p /app/data /app/logs /app/tmp

# 健康检查
HEALTHCHECK --interval=30s --timeout=30s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

# 暴露端口
EXPOSE 8000

# 启动命令
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]
