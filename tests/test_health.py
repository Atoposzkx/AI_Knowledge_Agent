"""
健康检查测试。
"""

from fastapi.testclient import TestClient
from app.main import app

'''
TestClient(app)：创建一个测试客户端，可以在测试进程里向应用发送请求，不需要先启动 Uvicorn。
with ... as client：进入测试客户端的使用范围，结束时清理相关资源。
client.get("/health")：模拟发送 GET /health，取得响应。
两个 assert：分别检查状态码和返回内容。response.json() 把响应中的 JSON 解析成 Python 字典，再进行比较。
'''
#test_ 开头的函数名，让 pytest 能识别它是一个测试。
def test_health():
    with TestClient(app) as client:
        response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status":"ok"}