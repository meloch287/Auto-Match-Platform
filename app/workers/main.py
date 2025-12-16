from arq.connections import RedisSettings
from arq import cron

from app.core.config import get_settings
from app.workers.jobs import (
    process_new_listing,
    process_new_requirement,
    process_new_auto_listing,
    send_match_notification,
    send_auto_match_notification,
    queue_match_notification_with_priority,
    queue_auto_match_notification_with_priority,
    send_delayed_match_notification,
    process_pending_delayed_notifications,
    send_batch_notifications,
    check_listing_renewals,
    check_requirement_renewals,
    expire_old_listings,
    expire_old_requirements,
    archive_inactive_chats,
    expire_vip_listings,
    check_expiring_subscriptions,
    expire_subscriptions,
    startup,
    shutdown,
)

settings = get_settings()


def get_redis_settings() -> RedisSettings:
    redis_url = str(settings.redis_url)
    if redis_url.startswith("redis://"):
        redis_url = redis_url[8:]

    if "/" in redis_url:
        host_port, db = redis_url.rsplit("/", 1)
        db = int(db) if db else 0
    else:
        host_port = redis_url
        db = 0

    if ":" in host_port:
        host, port = host_port.split(":")
        port = int(port)
    else:
        host = host_port
        port = 6379

    return RedisSettings(host=host, port=port, database=db)


class WorkerSettings:
    redis_settings = get_redis_settings()

    functions = [
        process_new_listing,
        process_new_requirement,
        process_new_auto_listing,
        send_match_notification,
        send_auto_match_notification,
        queue_match_notification_with_priority,
        queue_auto_match_notification_with_priority,
        send_delayed_match_notification,
        process_pending_delayed_notifications,
        send_batch_notifications,
        check_listing_renewals,
        check_requirement_renewals,
        expire_old_listings,
        expire_old_requirements,
        archive_inactive_chats,
        expire_vip_listings,
        check_expiring_subscriptions,
        expire_subscriptions,
    ]

    cron_jobs = [
        cron(check_listing_renewals, hour=3, minute=0),
        cron(check_requirement_renewals, hour=3, minute=30),
        cron(expire_old_listings, hour=4, minute=0),
        cron(expire_old_requirements, hour=4, minute=30),
        cron(archive_inactive_chats, hour=5, minute=0),
        cron(expire_vip_listings, hour=2, minute=0),
        cron(check_expiring_subscriptions, hour=1, minute=0),
        cron(expire_subscriptions, hour=1, minute=30),
        cron(process_pending_delayed_notifications, minute=30),
    ]

    on_startup = startup
    on_shutdown = shutdown

    max_jobs = 10
    job_timeout = 300
    keep_result = 3600
    retry_jobs = True
    max_tries = 3
