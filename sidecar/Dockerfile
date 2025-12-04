FROM python:3.9-slim

WORKDIR /app

# 安装依赖
RUN pip install --no-cache-dir pyyaml

# 复制sidecar脚本
COPY sidecar.py .

# 创建非root用户
RUN useradd -m -u 1001 sidecar && \
    chown -R sidecar:sidecar /app

USER sidecar

ENTRYPOINT ["python", "sidecar.py"]
