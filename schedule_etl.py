import schedule
import time
import subprocess
import sys
import os
import logging
from datetime import datetime

ETL_SCRIPT = os.path.join(os.path.dirname(__file__), "etl_to_timescaledb.py")
PYTHON_EXEC = sys.executable  # Use the current Python interpreter

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(levelname)s: %(message)s",
    handlers=[logging.StreamHandler()]
)

def job():
    logging.info("Running ETL job: etl_to_timescaledb.py")
    try:
        result = subprocess.run([PYTHON_EXEC, ETL_SCRIPT], capture_output=True, text=True, timeout=300)
        if result.stdout:
            logging.info("[ETL STDOUT] %s", result.stdout.strip())
        if result.stderr:
            logging.error("[ETL STDERR] %s", result.stderr.strip())
        if result.returncode != 0:
            logging.error(f"ETL script exited with code {result.returncode}")
    except subprocess.TimeoutExpired:
        logging.error("ETL job timed out.")
    except Exception as e:
        logging.exception(f"Unexpected error running ETL job: {e}")

schedule.every(1).minutes.do(job)

logging.info("Scheduler started. ETL job will run every 1 minute.")
job()  # Run once at startup
while True:
    schedule.run_pending()
    time.sleep(1)
