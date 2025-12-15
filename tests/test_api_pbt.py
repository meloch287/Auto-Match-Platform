"""
Property-based tests for API endpoints.

This module contains property-based tests for API response format consistency
and other API-related properties.

**Feature: auto-match-platform, Property 17: API Response Format Consistency**
**Validates: Requirements 13.9**
"""

from typing import Any

from hypothesis import given, settings, strategies as st

from app.api.responses import create_error_response, create_success_response


# Strategies for generating test data
json_primitives = st.one_of(
    st.none(),
    st.booleans(),
    st.integers(),
    st.floats(allow_nan=False, allow_infinity=False),
    st.text(max_size=100),
)

# Recursive strategy for JSON-like data
json_data = st.recursive(
    json_primitives,
    lambda children: st.one_of(
        st.lists(children, max_size=5),
        st.dictionaries(st.text(min_size=1, max_size=20), children, max_size=5),
    ),
    max_leaves=10,
)


class TestAPIResponseFormatConsistency:
    """
    Property tests for API response format consistency.
    
    **Feature: auto-match-platform, Property 17: API Response Format Consistency**
    **Validates: Requirements 13.9**
    
    Property: *For any* API response (success or error), the response format
    should always contain the required fields: success, data, error.
    """

    @given(data=json_data)
    @settings(max_examples=100)
    def test_success_response_has_required_fields(self, data: Any) -> None:
        """
        Property: Success responses always have success=True, data field, and error=None.
        
        **Feature: auto-match-platform, Property 17: API Response Format Consistency**
        **Validates: Requirements 13.9**
        """
        response = create_success_response(data=data)
        
        # Required fields must exist
        assert "success" in response
        assert "data" in response
        assert "error" in response
        
        # Success response properties
        assert response["success"] is True
        assert response["error"] is None
        assert response["data"] == data

    @given(data=json_data, pagination=st.one_of(st.none(), st.fixed_dictionaries({
        "page": st.integers(min_value=1, max_value=1000),
        "page_size": st.integers(min_value=1, max_value=100),
        "total_items": st.integers(min_value=0, max_value=100000),
        "total_pages": st.integers(min_value=0, max_value=10000),
        "has_next": st.booleans(),
        "has_prev": st.booleans(),
    })))
    @settings(max_examples=100)
    def test_success_response_with_pagination(
        self, data: Any, pagination: dict | None
    ) -> None:
        """
        Property: Success responses with pagination include pagination metadata.
        
        **Feature: auto-match-platform, Property 17: API Response Format Consistency**
        **Validates: Requirements 13.9**
        """
        response = create_success_response(data=data, pagination=pagination)
        
        # Required fields must exist
        assert "success" in response
        assert "data" in response
        assert "error" in response
        
        # Success response properties
        assert response["success"] is True
        assert response["error"] is None
        
        # Pagination field
        if pagination is not None:
            assert "pagination" in response
            assert response["pagination"] == pagination
        else:
            # Pagination key should not be present if not provided
            assert "pagination" not in response or response.get("pagination") is None

    @given(
        code=st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="_"
        )),
        message=st.text(min_size=1, max_size=500),
    )
    @settings(max_examples=100)
    def test_error_response_has_required_fields(
        self, code: str, message: str
    ) -> None:
        """
        Property: Error responses always have success=False, data=None, and error object.
        
        **Feature: auto-match-platform, Property 17: API Response Format Consistency**
        **Validates: Requirements 13.9**
        """
        response = create_error_response(code=code, message=message)
        
        # Required fields must exist
        assert "success" in response
        assert "data" in response
        assert "error" in response
        
        # Error response properties
        assert response["success"] is False
        assert response["data"] is None
        assert response["error"] is not None
        
        # Error object structure
        assert "code" in response["error"]
        assert "message" in response["error"]
        assert response["error"]["code"] == code
        assert response["error"]["message"] == message

    @given(
        code=st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="_"
        )),
        message=st.text(min_size=1, max_size=500),
        details=st.lists(
            st.fixed_dictionaries({
                "field": st.text(min_size=1, max_size=50),
                "message": st.text(min_size=1, max_size=200),
            }),
            min_size=1,  # Ensure at least one detail to test non-empty case
            max_size=5,
        ),
    )
    @settings(max_examples=100)
    def test_error_response_with_details(
        self, code: str, message: str, details: list[dict]
    ) -> None:
        """
        Property: Error responses with non-empty details include the details array.
        
        **Feature: auto-match-platform, Property 17: API Response Format Consistency**
        **Validates: Requirements 13.9**
        """
        response = create_error_response(code=code, message=message, details=details)
        
        # Required fields must exist
        assert "success" in response
        assert "data" in response
        assert "error" in response
        
        # Error response properties
        assert response["success"] is False
        assert response["data"] is None
        assert response["error"] is not None
        
        # Error object structure with details
        assert "code" in response["error"]
        assert "message" in response["error"]
        assert "details" in response["error"]
        assert response["error"]["details"] == details

    @given(
        code=st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="_"
        )),
        message=st.text(min_size=1, max_size=500),
    )
    @settings(max_examples=50)
    def test_error_response_without_details(
        self, code: str, message: str
    ) -> None:
        """
        Property: Error responses without details (None or empty) don't include details field.
        
        **Feature: auto-match-platform, Property 17: API Response Format Consistency**
        **Validates: Requirements 13.9**
        """
        # Test with None
        response_none = create_error_response(code=code, message=message, details=None)
        assert "details" not in response_none["error"]
        
        # Test with empty list
        response_empty = create_error_response(code=code, message=message, details=[])
        assert "details" not in response_empty["error"]

    @given(data=json_data)
    @settings(max_examples=100)
    def test_success_and_error_responses_are_mutually_exclusive(
        self, data: Any
    ) -> None:
        """
        Property: A response is either a success (success=True, error=None)
        or an error (success=False, data=None), never both.
        
        **Feature: auto-match-platform, Property 17: API Response Format Consistency**
        **Validates: Requirements 13.9**
        """
        success_response = create_success_response(data=data)
        error_response = create_error_response(code="TEST", message="Test error")
        
        # Success response: success=True, error=None
        assert success_response["success"] is True
        assert success_response["error"] is None
        
        # Error response: success=False, data=None
        assert error_response["success"] is False
        assert error_response["data"] is None
        
        # They are mutually exclusive
        assert success_response["success"] != error_response["success"]

    @given(
        data1=json_data,
        data2=json_data,
    )
    @settings(max_examples=50)
    def test_response_format_is_consistent_across_different_data(
        self, data1: Any, data2: Any
    ) -> None:
        """
        Property: Response format structure is consistent regardless of data content.
        
        **Feature: auto-match-platform, Property 17: API Response Format Consistency**
        **Validates: Requirements 13.9**
        """
        response1 = create_success_response(data=data1)
        response2 = create_success_response(data=data2)
        
        # Both responses have the same structure (same keys)
        assert set(response1.keys()) == set(response2.keys())
        
        # Both have the same success value
        assert response1["success"] == response2["success"]
        
        # Both have error=None
        assert response1["error"] == response2["error"]

    @given(
        code1=st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="_"
        )),
        code2=st.text(min_size=1, max_size=50, alphabet=st.characters(
            whitelist_categories=("Lu", "Ll", "Nd"),
            whitelist_characters="_"
        )),
        message1=st.text(min_size=1, max_size=500),
        message2=st.text(min_size=1, max_size=500),
    )
    @settings(max_examples=50)
    def test_error_response_format_is_consistent(
        self, code1: str, code2: str, message1: str, message2: str
    ) -> None:
        """
        Property: Error response format structure is consistent regardless of error content.
        
        **Feature: auto-match-platform, Property 17: API Response Format Consistency**
        **Validates: Requirements 13.9**
        """
        response1 = create_error_response(code=code1, message=message1)
        response2 = create_error_response(code=code2, message=message2)
        
        # Both responses have the same structure (same keys)
        assert set(response1.keys()) == set(response2.keys())
        
        # Both have the same success value
        assert response1["success"] == response2["success"]
        
        # Both have data=None
        assert response1["data"] == response2["data"]
        
        # Both error objects have the same structure
        assert set(response1["error"].keys()) == set(response2["error"].keys())
