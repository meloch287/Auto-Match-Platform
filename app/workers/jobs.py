import logging
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from arq import ArqRedis
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.match import MatchStatusEnum

logger = logging.getLogger(__name__)


async def process_new_listing(
    ctx: dict[str, Any],
    listing_id: str,
) -> dict[str, Any]:
    logger.info(f"Processing new listing: {listing_id}")

    db: AsyncSession = ctx.get("db")
    if not db:
        logger.error("No database session in context")
        return {"listing_id": listing_id, "matches_created": 0, "error": "No DB session"}

    try:
        from app.models.listing import Listing, ListingStatusEnum
        from app.models.requirement import Requirement, RequirementStatusEnum
        from app.models.match import Match, MatchStatusEnum
        from app.services.matching.scorer import MatchScorer, ListingData

        result = await db.execute(
            select(Listing).where(Listing.id == UUID(listing_id))
        )
        listing = result.scalar_one_or_none()

        if not listing or listing.status != ListingStatusEnum.ACTIVE:
            return {"listing_id": listing_id, "matches_created": 0, "error": "Listing not active"}

        result = await db.execute(
            select(Requirement).where(
                and_(
                    Requirement.category_id == listing.category_id,
                    Requirement.status == RequirementStatusEnum.ACTIVE,
                )
            )
        )
        requirements = result.scalars().all()

        scorer = MatchScorer()
        matches_created = 0
        notifications_to_send = []
        listing_data = ListingData.from_model(listing)

        for requirement in requirements:
            existing = await db.execute(
                select(Match).where(
                    and_(
                        Match.listing_id == listing.id,
                        Match.requirement_id == requirement.id,
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue

            score = scorer.calculate_total_score(listing_data, requirement)

            if score >= 60:
                match = Match(
                    listing_id=listing.id,
                    requirement_id=requirement.id,
                    score=score,
                    status=MatchStatusEnum.NEW,
                )
                db.add(match)
                matches_created += 1

                notifications_to_send.append({
                    "match_id": str(match.id),
                    "user_id": str(requirement.user_id),
                    "is_buyer": True,
                })

        await db.commit()

        redis: ArqRedis = ctx.get("redis")
        if redis and notifications_to_send:
            for notif in notifications_to_send:
                await redis.enqueue_job(
                    "queue_match_notification_with_priority",
                    notif["match_id"],
                    notif["user_id"],
                    notif["is_buyer"],
                )

        logger.info(f"Created {matches_created} matches for listing {listing_id}")
        return {"listing_id": listing_id, "matches_created": matches_created}

    except Exception as e:
        logger.exception(f"Error processing listing {listing_id}: {e}")
        return {"listing_id": listing_id, "matches_created": 0, "error": str(e)}


async def process_new_requirement(
    ctx: dict[str, Any],
    requirement_id: str,
) -> dict[str, Any]:
    logger.info(f"Processing new requirement: {requirement_id}")

    db: AsyncSession = ctx.get("db")
    if not db:
        logger.error("No database session in context")
        return {"requirement_id": requirement_id, "matches_created": 0, "error": "No DB session"}

    try:
        from app.models.listing import Listing, ListingStatusEnum
        from app.models.requirement import Requirement, RequirementStatusEnum
        from app.models.match import Match, MatchStatusEnum
        from app.services.matching.scorer import MatchScorer, ListingData

        result = await db.execute(
            select(Requirement).where(Requirement.id == UUID(requirement_id))
        )
        requirement = result.scalar_one_or_none()

        if not requirement or requirement.status != RequirementStatusEnum.ACTIVE:
            return {"requirement_id": requirement_id, "matches_created": 0, "error": "Requirement not active"}

        result = await db.execute(
            select(Listing).where(
                and_(
                    Listing.category_id == requirement.category_id,
                    Listing.status == ListingStatusEnum.ACTIVE,
                )
            )
        )
        listings = result.scalars().all()

        scorer = MatchScorer()
        matches_created = 0
        notifications_to_send = []
        matches_to_create = []

        for listing in listings:
            existing = await db.execute(
                select(Match).where(
                    and_(
                        Match.listing_id == listing.id,
                        Match.requirement_id == requirement.id,
                    )
                )
            )
            if existing.scalar_one_or_none():
                continue

            listing_data = ListingData.from_model(listing)
            score = scorer.calculate_total_score(listing_data, requirement)

            if score >= 60:
                matches_to_create.append((listing, score))

        sorted_matches = MatchScorer.sort_matches_by_priority(matches_to_create)

        for listing, score in sorted_matches:
            match = Match(
                listing_id=listing.id,
                requirement_id=requirement.id,
                score=score,
                status=MatchStatusEnum.NEW,
            )
            db.add(match)
            matches_created += 1

            notifications_to_send.append({
                "match_id": str(match.id),
                "user_id": str(requirement.user_id),
                "is_buyer": True,
            })
            notifications_to_send.append({
                "match_id": str(match.id),
                "user_id": str(listing.user_id),
                "is_buyer": False,
            })

        await db.commit()

        redis: ArqRedis = ctx.get("redis")
        if redis and notifications_to_send:
            for notif in notifications_to_send:
                await redis.enqueue_job(
                    "queue_match_notification_with_priority",
                    notif["match_id"],
                    notif["user_id"],
                    notif["is_buyer"],
                )

        logger.info(f"Created {matches_created} matches for requirement {requirement_id}")
        return {"requirement_id": requirement_id, "matches_created": matches_created}

    except Exception as e:
        logger.exception(f"Error processing requirement {requirement_id}: {e}")
        return {"requirement_id": requirement_id, "matches_created": 0, "error": str(e)}


async def send_match_notification(
    ctx: dict[str, Any],
    match_id: str,
    user_id: str,
    is_buyer: bool,
) -> dict[str, Any]:
    logger.info(f"Sending match notification: match={match_id}, user={user_id}")

    db: AsyncSession = ctx.get("db")
    bot = ctx.get("bot")

    if not db or not bot:
        return {"match_id": match_id, "user_id": user_id, "sent": False, "error": "Missing context"}

    try:
        from app.models.user import User
        from app.models.match import Match
        from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

        result = await db.execute(
            select(User).where(User.id == UUID(user_id))
        )
        user = result.scalar_one_or_none()

        if not user or not user.telegram_id:
            return {"match_id": match_id, "user_id": user_id, "sent": False, "error": "User not found"}

        result = await db.execute(
            select(Match).where(Match.id == UUID(match_id))
        )
        match = result.scalar_one_or_none()

        if not match:
            return {"match_id": match_id, "user_id": user_id, "sent": False, "error": "Match not found"}

        message = f"🎯 New match found!\n\nMatch score: {match.score}%"

        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [
                InlineKeyboardButton(text="👁️ View", callback_data=f"match:view:{match_id}"),
                InlineKeyboardButton(text="💬 Contact", callback_data=f"match:contact:{match_id}"),
                InlineKeyboardButton(text="❌ Reject", callback_data=f"match:reject:{match_id}"),
            ]
        ])

        await bot.send_message(
            chat_id=user.telegram_id,
            text=message,
            reply_markup=keyboard,
        )

        return {"match_id": match_id, "user_id": user_id, "sent": True}

    except Exception as e:
        logger.exception(f"Failed to send notification: {e}")
        return {"match_id": match_id, "user_id": user_id, "sent": False, "error": str(e)}


async def queue_match_notification_with_priority(
    ctx: dict[str, Any],
    match_id: str,
    user_id: str,
    is_buyer: bool,
) -> dict[str, Any]:
    logger.info(f"Queueing match notification with priority: match={match_id}, user={user_id}")

    db: AsyncSession = ctx.get("db")
    redis: ArqRedis = ctx.get("redis")

    if not db:
        return {"match_id": match_id, "user_id": user_id, "queued": False, "error": "No DB session"}

    try:
        from app.services.notification import NotificationService

        notification_service = NotificationService(db)
        is_premium = await notification_service.is_user_premium(UUID(user_id))

        if is_premium:
            logger.info(f"Premium user {user_id}: sending immediate notification")
            if redis:
                await redis.enqueue_job(
                    "send_match_notification",
                    match_id,
                    user_id,
                    is_buyer,
                )
            return {
                "match_id": match_id,
                "user_id": user_id,
                "queued": True,
                "is_premium": True,
                "delay_seconds": 0,
            }
        else:
            delay_seconds = await notification_service.get_notification_delay_seconds(UUID(user_id))
            logger.info(f"Free user {user_id}: delaying notification by {delay_seconds} seconds")

            if redis:
                await redis.enqueue_job(
                    "send_delayed_match_notification",
                    match_id,
                    user_id,
                    is_buyer,
                    _defer_by=timedelta(seconds=delay_seconds),
                )
            return {
                "match_id": match_id,
                "user_id": user_id,
                "queued": True,
                "is_premium": False,
                "delay_seconds": delay_seconds,
            }

    except Exception as e:
        logger.exception(f"Failed to queue notification with priority: {e}")
        return {"match_id": match_id, "user_id": user_id, "queued": False, "error": str(e)}


async def send_delayed_match_notification(
    ctx: dict[str, Any],
    match_id: str,
    user_id: str,
    is_buyer: bool,
) -> dict[str, Any]:
    logger.info(f"Processing delayed match notification: match={match_id}, user={user_id}")

    db: AsyncSession = ctx.get("db")

    if not db:
        return {"match_id": match_id, "user_id": user_id, "sent": False, "error": "No DB session"}

    try:
        from app.models.user import User
        from app.models.match import Match

        result = await db.execute(
            select(User).where(User.id == UUID(user_id))
        )
        user = result.scalar_one_or_none()

        if not user:
            return {"match_id": match_id, "user_id": user_id, "sent": False, "error": "User not found"}

        result = await db.execute(
            select(Match).where(Match.id == UUID(match_id))
        )
        match = result.scalar_one_or_none()

        if not match:
            return {"match_id": match_id, "user_id": user_id, "sent": False, "error": "Match not found"}

        if match.status != MatchStatusEnum.NEW:
            logger.info(f"Match {match_id} status is {match.status}, skipping delayed notification")
            return {
                "match_id": match_id,
                "user_id": user_id,
                "sent": False,
                "skipped": True,
                "reason": f"Match status is {match.status}",
            }

        redis: ArqRedis = ctx.get("redis")
        if redis:
            await redis.enqueue_job(
                "send_match_notification",
                match_id,
                user_id,
                is_buyer,
            )

        return {"match_id": match_id, "user_id": user_id, "sent": True, "delayed": True}

    except Exception as e:
        logger.exception(f"Failed to send delayed notification: {e}")
        return {"match_id": match_id, "user_id": user_id, "sent": False, "error": str(e)}


async def send_batch_notifications(
    ctx: dict[str, Any],
    notifications: list[dict[str, Any]],
) -> dict[str, Any]:
    logger.info(f"Sending batch notifications: {len(notifications)} items")

    sent_count = 0
    redis: ArqRedis = ctx.get("redis")

    for notification in notifications:
        try:
            if redis:
                await redis.enqueue_job(
                    "send_match_notification",
                    notification.get("match_id"),
                    notification.get("user_id"),
                    notification.get("is_buyer", True),
                )
            sent_count += 1
        except Exception as e:
            logger.error(f"Failed to queue notification: {e}")

    return {"total": len(notifications), "sent": sent_count}


async def check_listing_renewals(ctx: dict[str, Any]) -> dict[str, Any]:
    logger.info("Checking listing renewals")

    db: AsyncSession = ctx.get("db")
    bot = ctx.get("bot")

    if not db:
        return {"checked": 0, "reminders_sent": 0, "error": "No DB session"}

    try:
        from app.models.listing import Listing, ListingStatusEnum
        from app.models.user import User

        threshold_date = datetime.utcnow() - timedelta(days=30)

        result = await db.execute(
            select(Listing).where(
                and_(
                    Listing.status == ListingStatusEnum.ACTIVE,
                    Listing.expires_at <= threshold_date + timedelta(days=15),
                    Listing.expires_at > threshold_date,
                )
            )
        )
        listings = result.scalars().all()

        reminders_sent = 0

        for listing in listings:
            try:
                result = await db.execute(
                    select(User).where(User.id == listing.user_id)
                )
                user = result.scalar_one_or_none()

                if user and user.telegram_id and bot:
                    days_left = (listing.expires_at - datetime.utcnow()).days
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"⏰ Your listing expires in {days_left} days.\n\nUse /my_listings to renew it.",
                    )
                    reminders_sent += 1
            except Exception as e:
                logger.error(f"Failed to send renewal reminder: {e}")

        return {"checked": len(listings), "reminders_sent": reminders_sent}

    except Exception as e:
        logger.exception(f"Error checking listing renewals: {e}")
        return {"checked": 0, "reminders_sent": 0, "error": str(e)}


async def check_requirement_renewals(ctx: dict[str, Any]) -> dict[str, Any]:
    logger.info("Checking requirement renewals")

    db: AsyncSession = ctx.get("db")
    bot = ctx.get("bot")

    if not db:
        return {"checked": 0, "reminders_sent": 0, "error": "No DB session"}

    try:
        from app.models.requirement import Requirement, RequirementStatusEnum
        from app.models.user import User

        threshold_date = datetime.utcnow() + timedelta(days=30)

        result = await db.execute(
            select(Requirement).where(
                and_(
                    Requirement.status == RequirementStatusEnum.ACTIVE,
                    Requirement.expires_at <= threshold_date,
                    Requirement.expires_at > datetime.utcnow(),
                )
            )
        )
        requirements = result.scalars().all()

        reminders_sent = 0

        for requirement in requirements:
            try:
                result = await db.execute(
                    select(User).where(User.id == requirement.user_id)
                )
                user = result.scalar_one_or_none()

                if user and user.telegram_id and bot:
                    days_left = (requirement.expires_at - datetime.utcnow()).days
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=f"⏰ Your requirement expires in {days_left} days.\n\nUse /my_requirements to renew it.",
                    )
                    reminders_sent += 1
            except Exception as e:
                logger.error(f"Failed to send renewal reminder: {e}")

        return {"checked": len(requirements), "reminders_sent": reminders_sent}

    except Exception as e:
        logger.exception(f"Error checking requirement renewals: {e}")
        return {"checked": 0, "reminders_sent": 0, "error": str(e)}


async def expire_old_listings(ctx: dict[str, Any]) -> dict[str, Any]:
    logger.info("Expiring old listings")

    db: AsyncSession = ctx.get("db")

    if not db:
        return {"expired": 0, "error": "No DB session"}

    try:
        from app.models.listing import Listing, ListingStatusEnum
        from sqlalchemy import update

        result = await db.execute(
            update(Listing)
            .where(
                and_(
                    Listing.status == ListingStatusEnum.ACTIVE,
                    Listing.expires_at < datetime.utcnow(),
                )
            )
            .values(status=ListingStatusEnum.EXPIRED)
            .returning(Listing.id)
        )

        expired_ids = result.scalars().all()
        await db.commit()

        logger.info(f"Expired {len(expired_ids)} listings")
        return {"expired": len(expired_ids)}

    except Exception as e:
        logger.exception(f"Error expiring listings: {e}")
        await db.rollback()
        return {"expired": 0, "error": str(e)}


async def expire_old_requirements(ctx: dict[str, Any]) -> dict[str, Any]:
    logger.info("Expiring old requirements")

    db: AsyncSession = ctx.get("db")

    if not db:
        return {"expired": 0, "error": "No DB session"}

    try:
        from app.models.requirement import Requirement, RequirementStatusEnum
        from sqlalchemy import update

        result = await db.execute(
            update(Requirement)
            .where(
                and_(
                    Requirement.status == RequirementStatusEnum.ACTIVE,
                    Requirement.expires_at < datetime.utcnow(),
                )
            )
            .values(status=RequirementStatusEnum.EXPIRED)
            .returning(Requirement.id)
        )

        expired_ids = result.scalars().all()
        await db.commit()

        logger.info(f"Expired {len(expired_ids)} requirements")
        return {"expired": len(expired_ids)}

    except Exception as e:
        logger.exception(f"Error expiring requirements: {e}")
        await db.rollback()
        return {"expired": 0, "error": str(e)}


async def archive_inactive_chats(ctx: dict[str, Any]) -> dict[str, Any]:
    logger.info("Archiving inactive chats")

    db: AsyncSession = ctx.get("db")

    if not db:
        return {"archived": 0, "error": "No DB session"}

    try:
        from app.models.chat import Chat, ChatStatusEnum
        from sqlalchemy import update

        threshold = datetime.utcnow() - timedelta(days=30)

        result = await db.execute(
            update(Chat)
            .where(
                and_(
                    Chat.status == ChatStatusEnum.ACTIVE,
                    Chat.updated_at < threshold,
                )
            )
            .values(status=ChatStatusEnum.ARCHIVED)
            .returning(Chat.id)
        )

        archived_ids = result.scalars().all()
        await db.commit()

        logger.info(f"Archived {len(archived_ids)} chats")
        return {"archived": len(archived_ids)}

    except Exception as e:
        logger.exception(f"Error archiving chats: {e}")
        await db.rollback()
        return {"archived": 0, "error": str(e)}


async def expire_vip_listings(ctx: dict[str, Any]) -> dict[str, Any]:
    logger.info("Expiring VIP listings")

    db: AsyncSession = ctx.get("db")

    if not db:
        return {"expired": 0, "error": "No DB session"}

    try:
        from app.models.listing import Listing
        from sqlalchemy import update

        now = datetime.utcnow()

        result = await db.execute(
            update(Listing)
            .where(
                and_(
                    Listing.is_vip == True,
                    Listing.vip_expires_at.isnot(None),
                    Listing.vip_expires_at <= now,
                )
            )
            .values(
                is_vip=False,
                vip_expires_at=None,
                priority_score=0,
            )
            .returning(Listing.id)
        )

        expired_ids = result.scalars().all()
        await db.commit()

        logger.info(f"Expired VIP status for {len(expired_ids)} listings")
        return {"expired": len(expired_ids)}

    except Exception as e:
        logger.exception(f"Error expiring VIP listings: {e}")
        await db.rollback()
        return {"expired": 0, "error": str(e)}


async def check_expiring_subscriptions(ctx: dict[str, Any]) -> dict[str, Any]:
    logger.info("Checking expiring subscriptions")

    db: AsyncSession = ctx.get("db")
    bot = ctx.get("bot")

    if not db:
        return {"checked": 0, "notifications_sent": 0, "error": "No DB session"}

    try:
        from app.services.subscription import SubscriptionService

        subscription_service = SubscriptionService(db)
        expiring_users = await subscription_service.check_expiring(days_ahead=3)

        notifications_sent = 0

        for user in expiring_users:
            try:
                if user.telegram_id and bot and user.subscription_expires_at:
                    days_left = (user.subscription_expires_at - datetime.utcnow()).days

                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=(
                            f"⚠️ Your premium subscription expires in {days_left} days.\n\n"
                            f"Use /subscription to renew and keep your premium features!"
                        ),
                    )
                    notifications_sent += 1
            except Exception as e:
                logger.error(f"Failed to send subscription expiry warning to user {user.id}: {e}")

        logger.info(f"Sent {notifications_sent} subscription expiry warnings")
        return {"checked": len(expiring_users), "notifications_sent": notifications_sent}

    except Exception as e:
        logger.exception(f"Error checking expiring subscriptions: {e}")
        return {"checked": 0, "notifications_sent": 0, "error": str(e)}


async def expire_subscriptions(ctx: dict[str, Any]) -> dict[str, Any]:
    logger.info("Expiring subscriptions")

    db: AsyncSession = ctx.get("db")
    bot = ctx.get("bot")

    if not db:
        return {"expired": 0, "error": "No DB session"}

    try:
        from app.services.subscription import SubscriptionService
        from app.models.user import User, SubscriptionTypeEnum

        now = datetime.utcnow()
        result = await db.execute(
            select(User).where(
                and_(
                    User.subscription_type == SubscriptionTypeEnum.PREMIUM,
                    User.subscription_expires_at.isnot(None),
                    User.subscription_expires_at <= now,
                )
            )
        )
        expired_users = result.scalars().all()

        subscription_service = SubscriptionService(db)
        expired_count = await subscription_service.expire_subscriptions()

        notifications_sent = 0
        for user in expired_users:
            try:
                if user.telegram_id and bot:
                    await bot.send_message(
                        chat_id=user.telegram_id,
                        text=(
                            "📋 Your premium subscription has expired.\n\n"
                            "You've been downgraded to the free tier.\n"
                            "Use /subscription to renew your premium features!"
                        ),
                    )
                    notifications_sent += 1
            except Exception as e:
                logger.error(f"Failed to send subscription expiry notification to user {user.id}: {e}")

        logger.info(f"Expired {expired_count} subscriptions, sent {notifications_sent} notifications")
        return {"expired": expired_count, "notifications_sent": notifications_sent}

    except Exception as e:
        logger.exception(f"Error expiring subscriptions: {e}")
        return {"expired": 0, "error": str(e)}


async def process_pending_delayed_notifications(ctx: dict[str, Any]) -> dict[str, Any]:
    logger.info("Processing pending delayed notifications")
    return {"processed": 0, "status": "ok"}


async def startup(ctx: dict[str, Any]) -> None:
    logger.info("Worker starting up...")

    from app.core.database import async_session_factory
    from app.bot.config import create_bot

    ctx["db"] = async_session_factory()

    try:
        ctx["bot"] = create_bot()
    except Exception as e:
        logger.warning(f"Could not create bot: {e}")
        ctx["bot"] = None

    logger.info("Worker started")


async def shutdown(ctx: dict[str, Any]) -> None:
    logger.info("Worker shutting down...")

    if ctx.get("db"):
        await ctx["db"].close()

    if ctx.get("bot"):
        await ctx["bot"].session.close()

    logger.info("Worker stopped")
