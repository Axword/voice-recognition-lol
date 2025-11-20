import logging, time

def now_str() -> str:
    return time.strftime("%H:%M:%S")

def make_logger(debug: bool = True):
    logger = logging.getLogger("LoLVoiceController")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s | %(message)s"))
    logger.handlers.clear()
    logger.addHandler(handler)
    logger.propagate = False
    return logger
