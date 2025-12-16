"""Payment API endpoints for Payriff integration."""
import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Header, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import DBSession, CurrentUser
from app.api.responses import create_success_response, create_error_response
from app.models.payment import Payment, PaymentStatusEnum, PaymentTypeEnum
from app.models.user import User
from app.services.payriff import get_payriff_service, PayriffOrderStatus
from app.services.subscription import SubscriptionService, get_subscription_plan

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/payments", tags=["Payments"])


class CreatePaymentRequest(BaseModel):
    """Request to create a payment."""
    payment_type: str  # subscription, vip, package_listings, package_requirements
    plan_id: Optional[str] = None  # for subscription
    amount: Optional[float] = None  # for custom amounts


class CreatePaymentResponse(BaseModel):
    """Response with payment URL."""
    payment_id: str
    payment_url: str
    amount: float
    currency: str


@router.post("/create", response_model=dict)
async def create_payment(
    request: CreatePaymentRequest,
    db: DBSession,
    current_user: CurrentUser,
) -> dict:
    """
    Create a new payment and get Payriff payment URL.
    
    Args:
        request: Payment request with type and plan
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Payment URL for redirect
    """
    # Determine amount based on payment type
    if request.payment_type == "subscription":
        if not request.plan_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=create_error_response(
                    code="PLAN_REQUIRED",
                    message="Plan ID is required for subscription payment",
                ),
            )
        
        plan = get_subscription_plan(request.plan_id)
        if not plan:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=create_error_response(
                    code="INVALID_PLAN",
                    message="Invalid subscription plan",
                ),
            )
        
        amount = plan.price
        description = f"Subscription: {plan.name_en}"
        payment_type = PaymentTypeEnum.SUBSCRIPTION
        
    elif request.payment_type == "package_listings":
        amount = Decimal("9.99")
        description = "Extra listings package (+5)"
        payment_type = PaymentTypeEnum.PACKAGE_LISTINGS
        
    elif request.payment_type == "package_requirements":
        amount = Decimal("4.99")
        description = "Extra requirements package (+10)"
        payment_type = PaymentTypeEnum.PACKAGE_REQUIREMENTS
        
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="INVALID_TYPE",
                message="Invalid payment type",
            ),
        )
    
    # Get user language for Payriff interface
    lang = current_user.language.value.upper() if current_user.language else "AZ"
    
    # Create Payriff order
    payriff = get_payriff_service()
    
    try:
        order = await payriff.create_order(
            amount=amount,
            currency="AZN",
            description=description,
            language=lang,
        )
        
        if not order:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=create_error_response(
                    code="PAYMENT_ERROR",
                    message="Failed to create payment order",
                ),
            )
        
        # Save payment to database
        payment = Payment(
            user_id=current_user.id,
            amount=amount,
            currency="AZN",
            payment_type=payment_type,
            plan_id=request.plan_id,
            payriff_order_id=order.order_id,
            payriff_session_id=order.session_id,
            payment_url=order.payment_url,
            status=PaymentStatusEnum.PENDING,
        )
        
        db.add(payment)
        await db.commit()
        await db.refresh(payment)
        
        logger.info(f"Created payment {payment.id} for user {current_user.id}")
        
        return create_success_response(
            data=CreatePaymentResponse(
                payment_id=str(payment.id),
                payment_url=order.payment_url,
                amount=float(amount),
                currency="AZN",
            ).model_dump()
        )
        
    finally:
        await payriff.close()


@router.post("/callback")
async def payment_callback(
    request: Request,
    db: DBSession,
    x_signature: Optional[str] = Header(None, alias="X-Signature"),
) -> dict:
    """
    Handle Payriff payment callback.
    
    This endpoint is called by Payriff when payment status changes.
    """
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")
    
    logger.info(f"Payriff callback received: {data}")
    
    session_id = data.get("sessionId")
    order_status = data.get("orderStatus")
    
    if not session_id:
        raise HTTPException(status_code=400, detail="Missing sessionId")
    
    # Find payment by session ID
    result = await db.execute(
        select(Payment).where(Payment.payriff_session_id == session_id)
    )
    payment = result.scalar_one_or_none()
    
    if not payment:
        logger.warning(f"Payment not found for session {session_id}")
        return {"status": "not_found"}
    
    # Update payment status
    old_status = payment.status
    
    if order_status == "APPROVED":
        payment.status = PaymentStatusEnum.APPROVED
        payment.paid_at = datetime.utcnow()
        
        # Activate subscription or add packages
        await _process_successful_payment(db, payment)
        
    elif order_status == "DECLINED":
        payment.status = PaymentStatusEnum.DECLINED
        
    elif order_status == "CANCELED":
        payment.status = PaymentStatusEnum.CANCELED
    
    await db.commit()
    
    logger.info(f"Payment {payment.id} status changed: {old_status} -> {payment.status}")
    
    return {"status": "ok"}


async def _process_successful_payment(db: AsyncSession, payment: Payment) -> None:
    """Process successful payment - activate subscription or add packages."""
    
    # Get user
    result = await db.execute(
        select(User).where(User.id == payment.user_id)
    )
    user = result.scalar_one_or_none()
    
    if not user:
        logger.error(f"User not found for payment {payment.id}")
        return
    
    if payment.payment_type == PaymentTypeEnum.SUBSCRIPTION:
        # Activate subscription
        subscription_service = SubscriptionService(db)
        await subscription_service.purchase(user.id, payment.plan_id)
        logger.info(f"Activated subscription {payment.plan_id} for user {user.id}")
        
    elif payment.payment_type == PaymentTypeEnum.PACKAGE_LISTINGS:
        # Add extra listings
        if user.free_listings_limit is None:
            user.free_listings_limit = 2 + 5  # default + extra
        else:
            user.free_listings_limit += 5
        logger.info(f"Added 5 extra listings for user {user.id}")
        
    elif payment.payment_type == PaymentTypeEnum.PACKAGE_REQUIREMENTS:
        # Add extra requirements
        if user.free_requirements_limit is None:
            user.free_requirements_limit = 2 + 10  # default + extra
        else:
            user.free_requirements_limit += 10
        logger.info(f"Added 10 extra requirements for user {user.id}")


@router.get("/status/{payment_id}", response_model=dict)
async def get_payment_status(
    payment_id: UUID,
    db: DBSession,
    current_user: CurrentUser,
) -> dict:
    """
    Get payment status.
    
    Args:
        payment_id: Payment UUID
        db: Database session
        current_user: Authenticated user
        
    Returns:
        Payment status
    """
    result = await db.execute(
        select(Payment).where(
            Payment.id == payment_id,
            Payment.user_id == current_user.id,
        )
    )
    payment = result.scalar_one_or_none()
    
    if not payment:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Payment not found",
            ),
        )
    
    return create_success_response(
        data={
            "payment_id": str(payment.id),
            "status": payment.status.value,
            "amount": float(payment.amount),
            "currency": payment.currency,
            "payment_type": payment.payment_type.value,
            "created_at": payment.created_at.isoformat(),
            "paid_at": payment.paid_at.isoformat() if payment.paid_at else None,
        }
    )


@router.get("/check/{session_id}", response_model=dict)
async def check_payment_by_session(
    session_id: str,
    db: DBSession,
) -> dict:
    """
    Check payment status by Payriff session ID.
    Used for redirect after payment.
    """
    result = await db.execute(
        select(Payment).where(Payment.payriff_session_id == session_id)
    )
    payment = result.scalar_one_or_none()
    
    if not payment:
        return create_success_response(
            data={"status": "not_found"}
        )
    
    # If still pending, check with Payriff
    if payment.status == PaymentStatusEnum.PENDING:
        payriff = get_payriff_service()
        try:
            order_info = await payriff.get_order_status(session_id)
            if order_info:
                order_status = order_info.get("orderStatus")
                if order_status == "APPROVED":
                    payment.status = PaymentStatusEnum.APPROVED
                    payment.paid_at = datetime.utcnow()
                    await _process_successful_payment(db, payment)
                    await db.commit()
                elif order_status == "DECLINED":
                    payment.status = PaymentStatusEnum.DECLINED
                    await db.commit()
                elif order_status == "CANCELED":
                    payment.status = PaymentStatusEnum.CANCELED
                    await db.commit()
        finally:
            await payriff.close()
    
    return create_success_response(
        data={
            "status": payment.status.value,
            "payment_type": payment.payment_type.value,
        }
    )
