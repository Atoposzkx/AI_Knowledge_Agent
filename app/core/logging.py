"""V1 日志配置与学习说明。

一、日志用来做什么？
日志记录应用运行事件，帮助开发者判断发生了什么。
main.py 记录启动和关闭，llm_client.py 记录模型调用结果与耗时。
Router 目前只转换 HTTP 错误，不重复记录 Client 已经记录的同一次失败。
Uvicorn 的访问日志还可以记录请求路径和 HTTP 状态码。
logger.warning() 只记录消息，不抛异常、不返回 HTTP 响应，也不停止程序；
Client 中的 raise 才会把错误继续传给 Router。

二、三个文件的 logger 怎样联系？
本文件：logging.getLogger("app")，配置共同父级的输出器、格式和级别。
main.py：logging.getLogger(__name__)，名称为 app.main。
Client：logging.getLogger(__name__)，名称为 app.clients.llm_client。
__name__ 是当前模块名，用它命名 logger 可以标明日志来自哪个模块。

名称层级：
app
├── app.main
└── app.clients
    └── app.clients.llm_client

这几个 logger 是不同对象。变量都叫 logger，并不让它们成为同一个变量。
默认 propagate=True，子 logger 的记录会向父级传播；因此子模块发出记录，
可以由 app 上的输出器打印，输出中的来源仍是原来的子模块名称。
本文件叫 logging.py 不会自动建立父子关系；关系来自点分隔的 logger 名称。
如果这里用 __name__，得到 app.core.logging，它不是其他两个模块的父级。

三、Logger、Handler、Formatter 各负责什么？
Logger：接收日志调用并判断级别是否允许记录。
Handler：决定记录输出到哪里；StreamHandler 默认写到标准错误流，通常显示在终端。
Formatter：决定输出格式；这里采用“时间 级别 来源 消息”。
示例：2026-10-07 14:30:00,123 INFO app.main application_started

四、info() 与 setLevel() 的关系。
logger.info("application_started") 给这一条消息标记 INFO 级别。
logger.setLevel(logging.INFO) 设置 logger 的最低记录级别。
级别从低到高：DEBUG < INFO < WARNING < ERROR < CRITICAL。
本项目的子 logger 没有单独设置级别，默认 NOTSET，沿父级寻找有效级别，
因此继承 app 的 INFO 门槛：DEBUG 不记录，INFO/WARNING/ERROR 等可以记录。
若把 app 门槛改为 WARNING，子模块的 info() 调用就不会产生记录。
更精确地说，父级门槛通过“子级继承有效级别”影响这些调用；记录传播时，
不会再次按父 logger 的级别筛选。Handler 也可以设置自己的输出门槛，
但这里没有另设 Handler 级别，也没有给子 logger 单独设置级别。

五、Client 的日志消息怎样读？
llm_timeout：调用超时。
llm_connection_error：连接失败。
llm_provider_error：上游返回 HTTP 错误。
llm_empty_answer：模型返回空白或其他不可用的文本结果。
llm_success：模型调用成功。
这些名称和 elapsed_ms、status 都是我们自定义的文字，不是 Python 关键字。

计时方式：started = perf_counter() 记录开始计时值；
(perf_counter() - started) * 1000 得到经过的毫秒数，不是日期或钟表时间。
logger.warning("llm_connection_error elapsed_ms=%.0f", elapsed_ms)
会把 elapsed_ms 填入 %.0f，不保留小数；125.7 输出为 126。
logger.warning("llm_provider_error status=%s elapsed_ms=%.0f", status, elapsed_ms)
按顺序把 status 填入 %s，把 elapsed_ms 填入 %.0f。
例：llm_provider_error status=500 elapsed_ms=850。
这里只记录事件类别、状态码和耗时，不记录密钥、用户消息或上游响应原文。
"""

import logging


def configure_logging() -> None:
    # 应用启动时由 lifespan 调用，给 app 及其子模块准备公共输出通道。
    logger = logging.getLogger("app")
    # 多次进入 TestClient 会多次启动应用，避免重复添加输出器。
    # logger.handlers 是列表，保存直接添加到这个 logger 上的输出器。
    # 第一次配置时列表为空：[] 在条件判断中为 False，not [] 就是 True，
    # 因此会进入下面的代码，创建输出器并通过 addHandler 加入列表。
    # 添加后列表不为空，not logger.handlers 就是 False，不再重复添加。
    # 这里相当于判断 len(logger.handlers) == 0。
    # 同一进程中 getLogger("app") 会返回同一个 logger；应用关闭不会清空
    # 它的输出器。再次启动时若重复添加，同一条日志可能输出多遍。
    if not logger.handlers:
        # 输出目的地：默认标准错误流，运行应用时通常出现在终端。
        handler = logging.StreamHandler()
        # 四个字段：时间、级别、记录器名称（来源模块）、消息正文。
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        ))
        logger.addHandler(handler)  # 把配置好的输出器安装到 app logger。
    # 子模块默认继承这个级别；它们用 info/warning 等方法标记每条消息的级别。
    logger.setLevel(logging.INFO)
