import os
import json
import time
import logging
from logging.handlers import RotatingFileHandler
from typing import Dict

from flask import Flask, Response, jsonify, render_template_string, request

import db
from analytics import compute_summary, compute_worktime
from templates import HTML
from utils import now_str

# ===== PATHS / WORKDIR =====
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(BASE_DIR)

# ===== LOGGING =====
LOG_DIR = os.path.join(BASE_DIR, "logs")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(LOG_DIR, "log.txt")

logger = logging.getLogger("ivms")
logger.setLevel(logging.INFO)

_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s")

# file (rotating)
_file_handler = RotatingFileHandler(
    LOG_FILE,
    maxBytes=5 * 1024 * 1024,  # 5 MB
    backupCount=5,
    encoding="utf-8",
)
_file_handler.setFormatter(_formatter)
logger.addHandler(_file_handler)

# console (useful for manual запуск)
_console = logging.StreamHandler()
_console.setFormatter(_formatter)
logger.addHandler(_console)

logger.info("=== iVMS access log service starting ===")

# ===== FLASK =====
app = Flask(__name__)

DB_CONN_STR = (
    "DRIVER={SQL Server Native Client 11.0};"
    "SERVER=127.0.0.1;"
    "DATABASE=thirdparty;"
    "UID=sa;"
    "PWD=YOUR_PASSWORD;"
    "TrustServerCertificate=yes;"
)

TABLE_NAME = "dbo.attlog"

MAX_PAGE_ROWS = 300
MAX_SSE_BATCH = 50
SSE_POLL_SECONDS = 1.0


@app.errorhandler(Exception)
def handle_exception(e):
    # ВАЖНО: это даст полный stacktrace в logs/log.txt
    logger.exception("Unhandled exception: %s", e)
    return jsonify({"ok": False, "error": "Internal Server Error"}), 500


@app.route("/")
def index():
    return render_template_string(HTML)


@app.route("/api/doors")
def api_doors():
    # get_doors(db_conn_str, table_name)
    return jsonify(db.get_doors(DB_CONN_STR, TABLE_NAME))


@app.route("/api/log")
def api_log():
    filters: Dict[str, str] = dict(request.args)
    data = db.get_log(DB_CONN_STR, TABLE_NAME, filters, limit=MAX_PAGE_ROWS)
    return jsonify(data)


@app.route("/api/summary")
def api_summary():
    filters: Dict[str, str] = dict(request.args)
    events = db.get_log(DB_CONN_STR, TABLE_NAME, filters, limit=2000)
    return jsonify(compute_summary(events))


@app.route("/api/worktime")
def api_worktime():
    filters: Dict[str, str] = dict(request.args)
    events = db.get_log(DB_CONN_STR, TABLE_NAME, filters, limit=10000)
    return jsonify(compute_worktime(events))


@app.route("/sse")
def sse():
    last_serial = db.get_max_serialno(DB_CONN_STR, TABLE_NAME)

    def gen():
        yield "data: " + json.dumps(
            {"type": "hello", "ts": now_str(), "lastSerial": last_serial},
            ensure_ascii=False
        ) + "\n\n"

        cur_last = last_serial

        while True:
            try:
                rows = db.get_log_after_serial(DB_CONN_STR, TABLE_NAME, cur_last, limit=MAX_SSE_BATCH)
                if rows:
                    cur_last = int(rows[-1].get("serialNo", cur_last))
                    payload = {"type": "batch", "ts": now_str(), "rows": rows}
                    yield "data: " + json.dumps(payload, ensure_ascii=False) + "\n\n"
                else:
                    yield "data: " + json.dumps({"type": "ping", "ts": now_str()}, ensure_ascii=False) + "\n\n"

                time.sleep(SSE_POLL_SECONDS)

            except GeneratorExit:
                break
            except Exception as e:
                logger.exception("SSE error: %s", e)
                yield "data: " + json.dumps(
                    {"type": "error", "ts": now_str(), "error": str(e)},
                    ensure_ascii=False
                ) + "\n\n"
                time.sleep(2.0)

    return Response(gen(), mimetype="text/event-stream")


def main():
    host = os.getenv("IVMS_HOST", "0.0.0.0")
    port = int(os.getenv("IVMS_PORT", "8099"))
    debug = os.getenv("IVMS_DEBUG", "0") == "1"

    # Для службы reloader НЕЛЬЗЯ
    logger.info("Starting Flask server on %s:%s (debug=%s)", host, port, debug)
    app.run(host=host, port=port, debug=debug, use_reloader=False, threaded=True)


if __name__ == "__main__":
    main()
