from typing import Any

def create_success_response(data: Any = None, pagination: dict | None = None) -> dict:

    response = {
        "success": True,
        "data": data,
        "error": None,
    }
    if pagination:
        response["pagination"] = pagination
    return response

def create_error_response(
    code: str,
    message: str,
    details: list[dict] | None = None,
) -> dict:
    """
    Create a standardized error response.
    
    Args:
        code: Error code (e.g., "VALIDATION_ERROR", "NOT_FOUND")
        message: Human-readable error message
        details: Optional list of detailed error information
        
    Returns:
        Standardized error response dictionary
        
    Requirements: 13.9 (Property 17: API Response Format Consistency)
    """
    error_obj: dict[str, Any] = {
        "code": code,
        "message": message,
    }
    if details:
        error_obj["details"] = details
    
    return {
        "success": False,
        "data": None,
        "error": error_obj,
    }
