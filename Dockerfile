# BUILD STAGE
FROM python:3.14.4-slim-bookworm AS builder

# Copy UV binary from official image
COPY --from=ghcr.io/astral-sh/uv:0.11.6 /uv /uvx /bin/

# 在容器里设置工作字典
WORKDIR /app 

# UV Docker optimizations. UV配置项
ENV UV_COMPILE_BYTECODE=1
ENV UV_LINK_MODE=copy
ENV UV_PYTHON_DOWNLOADS=0
# UV_PYTHON_DOWNLOADS=0: 告诉UV使用从base image使用python而不是下载本身

# Install dependencies first (cached if unchanged)
COPY pyproject.toml uv.lock ./
RUN uv sync --locked --no-install-project --no-dev
# locked 代表从lock文件里使用确切的版本

# 在复制app代码前安装依赖
# Dockerfile 里“先装依赖，再复制代码”: 假设：
# COPY . .
# RUN uv sync

# 你修改了：
# print("Hello")

# Docker 可能需要重新执行下面的依赖安装步骤。

# 但作者采用：
# COPY pyproject.toml uv.lock ./
# RUN uv sync --locked --no-dev
# COPY . .

# 那么：
# pyproject.toml 没变化
# uv.lock 没变化
#         ↓
# 依赖层可以使用缓存
#         ↓
# 只重新处理代码

# 所以：依赖变化少，代码变化多，因此让 Docker 更早缓存依赖层。
# Docker在每一步缓存作为一层,之前的缓存可以复用而不用重构

# Copy app code and install project
COPY . ./
RUN uv sync --locked --no-dev
# 这次Run速度很快因为所有依赖已经缓存

# 第二阶段
# PRODUCTION STAGE
FROM python:3.14.4-slim-bookworm

WORKDIR /app

# Run as non-root user for security
RUN useradd -m appuser && chown -R appuser:appuser /app
USER appuser

# Copy app and dependencies from builder stage
COPY --from=builder --chown=appuser:appuser /app /app
# --from=builder: 从构建阶段直接复制过来而不是从本地
# Docker如何知道构建阶段在哪结束并在这结束: 
# 所有Dockerfile里的指令都开始的一个新的阶段.
# 最开始的build stage会赋予一个我们后面可以参考的名字
# 生产阶段最终会生成一个Image


ENV PATH="/app/.venv/bin:$PATH"
ENV PYTHONUNBUFFERED=1
ENV PORT=8080
# PYTHONUNBUFFERED: 使得python输出立马在日志(log)里出现
# 没有这个,输出和日志不会出现直到buffer填满,这在云端运行时debug会造成麻烦

# exec replaces shell so fastapi receives SIGTERM for clean shutdown
# 运行指令和停止指令
# -c表示告诉shell下一个参数是一个要执行的指令
CMD ["/bin/sh", "-c", "exec fastapi run --host 0.0.0.0 --port \"$PORT\" --proxy-headers --forwarded-allow-ips '*'"]