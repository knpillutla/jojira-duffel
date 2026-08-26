"""
Common & Payment Pydantic schemas and Data Transfer Objects for Duffel REST API.
"""

from typing import Any, Optional
from pydantic import BaseModel, Field


class PassengerInput(BaseModel):
    """Passenger details for flight search and order booking as expected by Duffel API."""
    id: Optional[str] = Field(None, description="Passenger ID from offer (e.g. 'pas_00001')")
    type: str = Field("adult", description="Passenger type: adult, child, infant_without_seat")
    given_name: Optional[str] = Field(None, description="Given / First Name")
    first_name: Optional[str] = Field(None, description="Alias for given_name")
    family_name: Optional[str] = Field(None, description="Family / Last Name")
    last_name: Optional[str] = Field(None, description="Alias for family_name")
    email: Optional[str] = Field(None, description="Contact Email Address")
    phone_number: Optional[str] = Field(None, description="Phone Number with country code")
    born_on: Optional[str] = Field(None, description="Date of birth in YYYY-MM-DD format")
    title: Optional[str] = Field("mr", description="Title: mr, ms, mrs, dr")
    gender: Optional[str] = Field("m", description="Gender: m, f")


class PaymentInput(BaseModel):
    """Payment details for Duffel order creation supporting all Duffel payment methods."""
    type: str = Field("balance", description="Payment method: balance, card, arc_bsp_one_step, customer_card, bank_transfer, instant_bank_transfer")
    currency: Optional[str] = Field("USD", description="Payment currency code e.g. USD")
    amount: Optional[str] = Field(None, description="Total payment amount string e.g. '613.33'")
    card_token: Optional[str] = Field(None, description="Card token if paying via credit card")
    token: Optional[str] = Field(None, description="Alias for card_token or Duffel Payments token")
    card_id: Optional[str] = Field(None, description="Saved Card ID for card payment")
    customer_card_id: Optional[str] = Field(None, description="Saved customer card ID on file")
    payment_method_id: Optional[str] = Field(None, description="Generic payment method ID or token")


class OrderPaymentRequest(BaseModel):
    """Request payload to pay for a hold order (POST /air/orders/{order_id}/payments)."""
    payment: Optional[PaymentInput] = Field(None, description="Payment details object (type: 'balance', 'card', etc.)")
    payments: Optional[list[PaymentInput]] = Field(None, description="List of payment objects")


class HealthCheckResponse(BaseModel):
    """System health check response status."""
    status: str
    service: str = Field("Jojira Duffel Integration API", description="Service name")
    version: str
    timestamp: str = Field(..., description="Current system timestamp")
    duffel_token_configured: bool
    redis_cache_enabled: bool
    redis_cache_status: str


class PaymentMethodOption(BaseModel):
    """Supported Duffel payment method option item."""
    id: str = Field(..., description="Payment method identifier e.g. 'balance', 'card', 'hold'")
    name: str = Field(..., description="Human-readable payment method display name")
    description: str = Field(..., description="Explanation of payment method")
    category: str = Field(..., description="Category: account, card, agency, bank, reservation")
    requires_card_details: bool = Field(False, description="Whether card token or credit card details are required")
    requires_customer_card_id: bool = Field(False, description="Whether customer card ID is required")
    is_hold_option: bool = Field(False, description="Whether this option reserves seats without immediate payment")


class PaymentMethodsResponse(BaseModel):
    """List of all Duffel-supported payment methods response."""
    status: str = Field("ok", description="Response status")
    default_method: str = Field("balance", description="Default recommended payment method")
    supported_payment_methods: list[PaymentMethodOption] = Field(..., description="Array of supported payment methods")


class ComponentClientKeyResponse(BaseModel):
    """Response payload containing generated Duffel Client Component Key for front-end Card Form."""
    status: str = Field("ok", description="Response status")
    client_key: str = Field(..., description="Short-lived Duffel Component Client Key JWT token")
    component_client_key: Optional[str] = Field(None, description="Alias for client_key")
    live_mode: bool = Field(True, description="Whether key is in live mode vs test mode")
    created_at: Optional[str] = Field(None, description="ISO timestamp of key creation")


class ApiEndpointHelp(BaseModel):
    """Help metadata for an API endpoint."""
    name: str = Field(..., description="API endpoint name / summary")
    method: str = Field(..., description="HTTP Method e.g. GET, POST")
    path: str = Field(..., description="API endpoint path")
    url: str = Field(..., description="Full API endpoint URL e.g. http://localhost:8000/api/v1/flights/search")
    description: str = Field(..., description="Description of endpoint functionality")
    request_schema: Optional[Any] = Field(None, description="Input request JSON schema or query parameters")
    response_schema: Optional[Any] = Field(None, description="Output response JSON schema")


class ApiHelpResponse(BaseModel):
    """Complete API help directory response."""
    service: str = Field(..., description="Service title")
    version: str = Field(..., description="API version")
    base_url: str = Field(..., description="Server base URL e.g. http://localhost:8000")
    interactive_docs_url: str = Field(..., description="Interactive OpenAPI docs URL")
    total_endpoints: int = Field(..., description="Total number of registered endpoints")
    endpoints: list[ApiEndpointHelp] = Field(..., description="List of all API endpoint specifications")
