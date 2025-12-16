"""
Payriff Payment Gateway Integration.

Payriff API documentation: https://payriff.com/docs
"""
import hashlib
import hmac
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, Optional

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class PayriffOrderStatus(str, Enum):
    """Payriff order statuses."""
    CREATED = "CREATED"
    APPROVED = "APPROVED"
    DECLINED = "DECLINED"
    CANCELED = "CANCELED"
    REFUNDED = "REFUNDED"


class PayriffConfig:
    """Payriff configuration."""
    
    def __init__(
        self,
        merchant_id: str,
        secret_key: str,
        base_url: str = "https://api.payriff.com/api/v2",
        callback_url: Optional[str] = None,
        result_url: Optional[str] = None,
    ):
        self.merchant_id = merchant_id
        self.secret_key = secret_key
        self.base_url = base_url
        self.callback_url = callback_url
        self.result_url = result_url


@dataclass
class PayriffOrder:
    """Payriff order data."""
    order_id: str
    session_id: str
    payment_url: str
    amount: Decimal
    currency: str
    status: PayriffOrderStatus
    created_at: datetime


class CreateOrderRequest(BaseModel):
    """Request to create Payriff order."""
    body: dict
    merchant: str


class PayriffService:
    """Service for Payriff payment gateway integration."""
    
    def __init__(self, config: PayriffConfig):
        self.config = config
        self.client = httpx.AsyncClient(timeout=30.0)
    
    async def create_order(
        self,
        amount: Decimal,
        currency: str = "AZN",
        description: str = "",
        language: str = "AZ",
        order_id: Optional[str] = None,
    ) -> Optional[PayriffOrder]:
        """
        Create a new payment order.
        
        Args:
            amount: Payment amount
            currency: Currency code (AZN, USD, EUR)
            description: Order description
            language: Interface language (AZ, EN, RU)
            order_id: Custom order ID (generated if not provided)
            
        Returns:
            PayriffOrder with payment URL or None on error
        """
        if not order_id:
            order_id = str(uuid.uuid4())
        
        # Amount in qəpik (cents) - multiply by 100
        amount_cents = int(amount * 100)
        
        payload = {
            "body": {
                "amount": amount_cents,
                "currencyType": currency,
                "description": description,
                "language": language.upper(),
                "approveURL": self.config.result_url or "",
                "cancelURL": self.config.result_url or "",
                "declineURL": self.config.result_url or "",
            },
            "merchant": self.config.merchant_id,
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.config.secret_key,
        }
        
        try:
            response = await self.client.post(
                f"{self.config.base_url}/createOrder",
                json=payload,
                headers=headers,
            )
            
            if response.status_code != 200:
                logger.error(f"Payriff API error: {response.status_code} - {response.text}")
                return None
            
            data = response.json()
            
            if data.get("code") != "00000":
                logger.error(f"Payriff error: {data.get('message')}")
                return None
            
            payload_data = data.get("payload", {})
            
            return PayriffOrder(
                order_id=payload_data.get("orderId", order_id),
                session_id=payload_data.get("sessionId", ""),
                payment_url=payload_data.get("paymentUrl", ""),
                amount=amount,
                currency=currency,
                status=PayriffOrderStatus.CREATED,
                created_at=datetime.utcnow(),
            )
            
        except Exception as e:
            logger.exception(f"Error creating Payriff order: {e}")
            return None
    
    async def get_order_status(self, session_id: str) -> Optional[dict]:
        """
        Get order status by session ID.
        
        Args:
            session_id: Payriff session ID
            
        Returns:
            Order status data or None on error
        """
        payload = {
            "body": {
                "sessionId": session_id,
            },
            "merchant": self.config.merchant_id,
        }
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": self.config.secret_key,
        }
        
        try:
            response = await self.client.post(
                f"{self.config.base_url}/getOrderInformation",
                json=payload,
                headers=headers,
            )
            
            if response.status_code != 200:
                logger.error(f"Payriff API error: {response.status_code}")
                return None
            
            data = response.json()
            
            if data.get("code") != "00000":
                logger.error(f"Payriff error: {data.get('message')}")
                return None
            
            return data.get("payload", {})
            
        except Exception as e:
            logger.exception(f"Error getting Payriff order status: {e}")
            return None
    
    def verify_callback(self, data: dict, signature: str) -> bool:
        """
        Verify callback signature from Payriff.
        
        Args:
            data: Callback data
            signature: Signature from X-Signature header
            
        Returns:
            True if signature is valid
        """
        # Create signature string from data
        sign_string = f"{data.get('orderId')}:{data.get('sessionId')}:{data.get('orderStatus')}"
        
        # Calculate HMAC-SHA256
        expected_signature = hmac.new(
            self.config.secret_key.encode(),
            sign_string.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature.lower(), signature.lower())
    
    async def close(self):
        """Close HTTP client."""
        await self.client.aclose()


def get_payriff_service() -> PayriffService:
    """Get Payriff service instance from settings."""
    import os
    
    config = PayriffConfig(
        merchant_id=os.getenv("PAYRIFF_MERCHANT_ID", ""),
        secret_key=os.getenv("PAYRIFF_SECRET_KEY", ""),
        callback_url=os.getenv("PAYRIFF_CALLBACK_URL", ""),
        result_url=os.getenv("PAYRIFF_RESULT_URL", ""),
    )
    
    return PayriffService(config)
