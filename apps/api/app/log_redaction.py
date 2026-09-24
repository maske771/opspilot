import logging
import re

_TOKEN_PARAM = re.compile(r"([?&]token=)[^&\s\"]+")


class RedactTokenFilter(logging.Filter):
    """Webhook URLs carry a secret `?token=`; keep it out of access logs."""

    def filter(self, record: logging.LogRecord) -> bool:
        if isinstance(record.args, tuple):
            record.args = tuple(_TOKEN_PARAM.sub(r"\1***", arg) if isinstance(arg, str) else arg for arg in record.args)
        if isinstance(record.msg, str):
            record.msg = _TOKEN_PARAM.sub(r"\1***", record.msg)
        return True
