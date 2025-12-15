from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import CurrentUser, DBSession
from app.api.responses import create_error_response, create_success_response
from app.repositories.listing import ListingRepository
from app.repositories.match import MatchRepository
from app.repositories.requirement import RequirementRepository
from app.schemas.chat import (
    ChatDetailResponse,
    ChatListResponse,
    ChatMessageCreate,
    ChatMessageResponse,
    ChatResponse,
    ChatRevealRequest,
    ChatRevealResponse,
)
from app.schemas.common import PaginationMeta, PaginationParams
from app.services.chat import ChatService

router = APIRouter(prefix="/chats", tags=["Chats"])

def get_pagination_params(
    page: int = Query(default=1, ge=1, description="Page number"),
    page_size: int = Query(default=20, ge=1, le=100, description="Items per page"),
) -> PaginationParams:
    """Dependency for pagination parameters."""
    return PaginationParams(page=page, page_size=page_size)

async def get_user_role_in_chat(
    chat_id: UUID,
    user_id: UUID,
    db,
) -> tuple[str | None, str | None, str | None]:
    """
    Determine user's role in a chat.
    
    Returns: (role, user_alias, other_alias) or (None, None, None) if not in chat
    """
    chat_service = ChatService(db)
    match_repo = MatchRepository(db)
    listing_repo = ListingRepository(db)
    requirement_repo = RequirementRepository(db)
    
    chat = await chat_service.get_chat(chat_id)
    if chat is None:
        return None, None, None
    
    match = await match_repo.get(chat.match_id)
    if match is None:
        return None, None, None
    
    listing = await listing_repo.get(match.listing_id)
    requirement = await requirement_repo.get(match.requirement_id)
    
    if listing is None or requirement is None:
        return None, None, None
    
    if user_id == requirement.user_id:
        return "buyer", chat.buyer_alias, chat.seller_alias
    elif user_id == listing.user_id:
        return "seller", chat.seller_alias, chat.buyer_alias
    
    return None, None, None

@router.get("")
async def list_chats(
    current_user: CurrentUser,
    db: DBSession,
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
) -> dict:
    """
    List current user's chats.
    
    Requirements: 13.7
    """
    chat_service = ChatService(db)
    
    chats = await chat_service.get_chats_for_user(
        user_id=current_user.id,
        skip=pagination.offset,
        limit=pagination.page_size,
    )
    
    all_chats = await chat_service.get_chats_for_user(
        user_id=current_user.id,
        limit=10000,
    )
    total_items = len(all_chats)
    total_pages = (total_items + pagination.page_size - 1) // pagination.page_size
    
    chat_responses = []
    for c in chats:
        role, user_alias, other_alias = await get_user_role_in_chat(
            c.id, current_user.id, db
        )
        
        messages = await chat_service.get_messages(c.id, limit=1)
        last_message_preview = None
        if messages:
            last_msg = messages[0]
            if last_msg.content:
                last_message_preview = last_msg.content[:50] + "..." if len(last_msg.content) > 50 else last_msg.content
        
        chat_responses.append(
            ChatListResponse(
                id=c.id,
                match_id=c.match_id,
                status=c.status,
                last_message_at=c.last_message_at,
                created_at=c.created_at,
                user_alias=user_alias or "",
                other_alias=other_alias or "",
                unread_count=0,
                last_message_preview=last_message_preview,
            ).model_dump()
        )
    
    pagination_meta = PaginationMeta(
        page=pagination.page,
        page_size=pagination.page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=pagination.page < total_pages,
        has_prev=pagination.page > 1,
    )
    
    return create_success_response(
        data=chat_responses,
        pagination=pagination_meta.model_dump(),
    )

@router.get("/{chat_id}/messages")
async def get_chat_messages(
    chat_id: UUID,
    current_user: CurrentUser,
    db: DBSession,
    pagination: Annotated[PaginationParams, Depends(get_pagination_params)],
) -> dict:
    """
    Get messages for a specific chat.
    
    Requirements: 13.7
    """
    chat_service = ChatService(db)
    match_repo = MatchRepository(db)
    listing_repo = ListingRepository(db)
    requirement_repo = RequirementRepository(db)
    
    is_in_chat = await chat_service.is_user_in_chat(chat_id, current_user.id)
    if not is_in_chat:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="FORBIDDEN",
                message="You don't have permission to view this chat",
            ),
        )
    
    chat = await chat_service.get_chat(chat_id)
    if chat is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=create_error_response(
                code="NOT_FOUND",
                message="Chat not found",
            ),
        )
    
    role, user_alias, other_alias = await get_user_role_in_chat(
        chat_id, current_user.id, db
    )
    
    match = await match_repo.get(chat.match_id)
    listing = await listing_repo.get(match.listing_id) if match else None
    requirement = await requirement_repo.get(match.requirement_id) if match else None
    
    buyer_id = requirement.user_id if requirement else None
    seller_id = listing.user_id if listing else None
    
    messages = await chat_service.get_messages(
        chat_id,
        skip=pagination.offset,
        limit=pagination.page_size,
    )
    
    all_messages = await chat_service.get_messages(chat_id, limit=10000)
    total_items = len(all_messages)
    total_pages = (total_items + pagination.page_size - 1) // pagination.page_size
    
    message_responses = []
    for m in messages:
        if m.sender_id == buyer_id:
            sender_alias = chat.buyer_alias
        elif m.sender_id == seller_id:
            sender_alias = chat.seller_alias
        else:
            sender_alias = "System"
        
        message_responses.append(
            ChatMessageResponse(
                id=m.id,
                chat_id=m.chat_id,
                sender_alias=sender_alias,
                message_type=m.message_type,
                content=m.content,
                media_url=m.media_url,
                created_at=m.created_at,
                updated_at=m.created_at,
                is_own_message=m.sender_id == current_user.id,
            ).model_dump()
        )
    
    pagination_meta = PaginationMeta(
        page=pagination.page,
        page_size=pagination.page_size,
        total_items=total_items,
        total_pages=total_pages,
        has_next=pagination.page < total_pages,
        has_prev=pagination.page > 1,
    )
    
    return create_success_response(
        data=message_responses,
        pagination=pagination_meta.model_dump(),
    )

@router.post("/{chat_id}/messages")
async def send_message(
    chat_id: UUID,
    message_data: ChatMessageCreate,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Send a message in a chat.
    
    Requirements: 13.7
    """
    chat_service = ChatService(db)
    
    is_in_chat = await chat_service.is_user_in_chat(chat_id, current_user.id)
    if not is_in_chat:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="FORBIDDEN",
                message="You don't have permission to send messages in this chat",
            ),
        )
    
    relayed_message = await chat_service.send_message(
        chat_id=chat_id,
        sender_id=current_user.id,
        content=message_data.content,
        message_type=message_data.message_type,
        media_url=message_data.media_url,
    )
    
    if relayed_message is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="MESSAGE_FAILED",
                message="Failed to send message",
            ),
        )
    
    return create_success_response(data={
        "message_id": str(relayed_message.message_id),
        "sender_alias": relayed_message.sender_alias,
        "message": "Message sent successfully",
    })

@router.post("/{chat_id}/reveal")
async def request_contact_reveal(
    chat_id: UUID,
    request: ChatRevealRequest,
    current_user: CurrentUser,
    db: DBSession,
) -> dict:
    """
    Request to reveal contact information.
    
    Both parties must consent for contacts to be revealed.
    
    Requirements: 13.7
    """
    chat_service = ChatService(db)
    
    is_in_chat = await chat_service.is_user_in_chat(chat_id, current_user.id)
    if not is_in_chat:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=create_error_response(
                code="FORBIDDEN",
                message="You don't have permission to request reveal in this chat",
            ),
        )
    
    result = await chat_service.request_reveal(chat_id, current_user.id)
    
    if not result.success:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=create_error_response(
                code="REVEAL_FAILED",
                message=result.message or "Failed to request contact reveal",
            ),
        )
    
    response = ChatRevealResponse(
        revealed=result.both_revealed,
        waiting_for_other=not result.both_revealed,
        contact_info={
            "buyer_contact": result.buyer_contact,
            "seller_contact": result.seller_contact,
        } if result.both_revealed else None,
    )
    
    return create_success_response(data=response.model_dump())
