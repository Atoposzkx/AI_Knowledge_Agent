"""V1 日志：应用自己的日志输出到终端，避免开启第三方 SDK 调试日志。"""

import logging


def configure_logging() -> None:
    logger = logging.getLogger("app")
    # 多次进入 TestClient 会多次启动应用，避免重复添加输出器。
    if not logger.handlers:
        handler = logging.StreamHandler()
        handler.setFormatter(logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        ))
        logger.addHandler(handler)
    logger.setLevel(logging.INFO)
