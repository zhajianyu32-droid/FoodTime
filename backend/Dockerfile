FROM python:3.12-slim

WORKDIR /app

# python:3.12-slim 默认 locale 是 C/POSIX，此时 open() 与 stdout 的默认编码不是 UTF-8。
# 本项目源码 / 日志 / prompt 大量中文，必须强制，否则启动即 UnicodeDecodeError。
ENV PYTHONUTF8=1 \
    PYTHONIOENCODING=utf-8


COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# 端口自适应：云平台（Railway/Render/Fly）会注入 $PORT，本地 docker 未注入时回退 8000
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}"]
