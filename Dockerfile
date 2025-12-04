FROM python:3.11-slim

WORKDIR /app

# 1. 复制依赖声明并安装
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 2. 复制项目代码
COPY src/ ./src/
COPY config/ ./config/
COPY setup.py .

# 3. 以开发模式安装当前包，便于导入
RUN pip install -e .

# 4. 设置默认启动命令
ENTRYPOINT ["python", "-m", "thanos_store_operator.operator"]