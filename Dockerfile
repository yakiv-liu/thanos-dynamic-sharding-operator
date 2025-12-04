FROM python:3.9-slim

WORKDIR /app

# 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制源代码
COPY src/ src/
COPY setup.py .

# 安装包
RUN pip install -e .

# 复制配置文件
COPY config/ config/

# 创建非root用户
RUN useradd -m -u 1000 operator && \
    chown -R operator:operator /app

USER operator

ENTRYPOINT ["python", "-m", "thanos_store_operator.operator"]
