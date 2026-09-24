import logging

from app.log_redaction import RedactTokenFilter


def render(*args) -> str:
    record = logging.LogRecord("uvicorn.access", logging.INFO, __file__, 1, '%s - "%s %s HTTP/%s" %d', args, None)
    assert RedactTokenFilter().filter(record)
    return record.getMessage()


def test_token_query_parameter_is_masked_in_access_log_lines():
    line = render("1.2.3.4:5", "POST", "/webhooks/telegram/bot?token=SECRETVALUE", "1.1", 200)
    assert "SECRETVALUE" not in line
    assert "/webhooks/telegram/bot?token=***" in line


def test_masks_token_anywhere_in_the_query_and_keeps_other_parameters():
    line = render("1.2.3.4:5", "GET", "/webhooks/whatsapp/a?hub.mode=subscribe&token=SECRETVALUE&x=1", "1.1", 200)
    assert "SECRETVALUE" not in line
    assert "hub.mode=subscribe" in line and "x=1" in line


def test_lines_without_a_token_are_untouched():
    assert render("1.2.3.4:5", "GET", "/tickets?status=new", "1.1", 200) == '1.2.3.4:5 - "GET /tickets?status=new HTTP/1.1" 200'
