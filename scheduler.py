from apscheduler.schedulers.background import BackgroundScheduler
import logging
from airtable_utils import check_and_notify

def start_scheduler():
    scheduler = BackgroundScheduler()
    scheduler.add_job(check_and_notify, 'interval', minutes=1)
    scheduler.start()

    logging.info("APScheduler started with 1-minute interval.")
