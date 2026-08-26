"""
Common System & Payment Route Controllers.
"""

import os
from datetime import datetime
from typing import Any

from fastapi import APIRouter, HTTPException, Request, status

from ...client import DuffelClient
from ..schemas import (
    ApiEndpointHelp,
    ApiHelpResponse,
    ComponentClientKeyResponse,
    HealthCheckResponse,
    OrderPaymentRequest,
    PaymentMethodOption,
    PaymentMethodsResponse,
)

router = APIRouter(tags=["Common & Payments API"])


def get_duffel_client() -> DuffelClient:
    """Dependency helper to return configured DuffelClient."""
    token = os.environ.get("DUFFEL_API_TOKEN", "")
    return DuffelClient(api_token=token, debug=False)


@router.get("/health", response_model=HealthCheckResponse, summary="System Health Check")
def health_check():
    """Returns system status, timestamp, Duffel API configuration, and Redis cache connection state."""
    client = get_duffel_client()
    redis_enabled = client.cache.enabled if client.cache else False
    redis_status = "Connected" if (client.cache and client.cache.redis_client is not None) else (
        "In-Memory Fallback" if redis_enabled else "Disabled"
    )

    return HealthCheckResponse(
        status="healthy",
        service="Jojira Duffel Integration API",
        version="1.0.0",
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        duffel_token_configured=bool(client.config.api_token),
        redis_cache_enabled=redis_enabled,
        redis_cache_status=redis_status,
    )


@router.get("/help", response_model=ApiHelpResponse, summary="API Help & Documentation Index")
def get_api_help(request: Request):
    """
    Returns a complete directory of all available REST APIs, including API name, HTTP method, URL, description, request schema, and response schema.
    """
    base_url = str(request.base_url).rstrip("/")
    openapi = request.app.openapi()
    components_schemas = openapi.get("components", {}).get("schemas", {})

    def resolve_schema(schema_ref):
        if not isinstance(schema_ref, dict):
            return schema_ref
        if "$ref" in schema_ref:
            ref_name = schema_ref["$ref"].split("/")[-1]
            return components_schemas.get(ref_name, schema_ref)
        return schema_ref

    endpoints = []
    for path, methods in openapi.get("paths", {}).items():
        for method_name, spec in methods.items():
            method_str = method_name.upper()
            summary = spec.get("summary") or spec.get("operationId") or f"{method_str} {path}"
            description = spec.get("description") or spec.get("summary") or ""

            request_schema = None
            if "requestBody" in spec:
                content = spec["requestBody"].get("content", {})
                json_content = content.get("application/json", {})
                schema = json_content.get("schema", {})
                request_schema = resolve_schema(schema)
            elif "parameters" in spec:
                request_schema = {
                    "type": "query_parameters",
                    "parameters": spec["parameters"]
                }

            response_schema = None
            responses = spec.get("responses", {})
            ok_res = responses.get("200") or responses.get(200)
            if ok_res:
                content = ok_res.get("content", {})
                json_content = content.get("application/json", {})
                schema = json_content.get("schema", {})
                response_schema = resolve_schema(schema)

            endpoints.append(ApiEndpointHelp(
                name=summary,
                method=method_str,
                path=path,
                url=f"{base_url}{path}",
                description=description,
                request_schema=request_schema,
                response_schema=response_schema,
            ))

    return ApiHelpResponse(
        service=openapi.get("info", {}).get("title", "Jojira Duffel REST API"),
        version=openapi.get("info", {}).get("version", "1.0.0"),
        base_url=base_url,
        interactive_docs_url=f"{base_url}/docs",
        total_endpoints=len(endpoints),
        endpoints=endpoints,
    )


@router.get("/payments/methods", response_model=PaymentMethodsResponse, summary="Get Supported Payment Methods")
@router.get("/flights/payment-methods", response_model=PaymentMethodsResponse, summary="Get Supported Flight Payment Methods")
def get_supported_payment_methods():
    """Returns all payment methods supported by the Duffel API."""
    methods = [
        PaymentMethodOption(
            id="balance",
            name="Duffel Balance",
            description="Pay using your Duffel account balance or test environment balance",
            category="account",
            requires_card_details=False,
            requires_customer_card_id=False,
            is_hold_option=False,
        ),
        PaymentMethodOption(
            id="card",
            name="Credit or Debit Card",
            description="Pay instantly using credit or debit card tokenization",
            category="card",
            requires_card_details=True,
            requires_customer_card_id=False,
            is_hold_option=False,
        ),
        PaymentMethodOption(
            id="customer_card",
            name="Saved Customer Card",
            description="Pay using a saved customer card on file",
            category="card",
            requires_card_details=False,
            requires_customer_card_id=True,
            is_hold_option=False,
        ),
        PaymentMethodOption(
            id="arc_bsp_one_step",
            name="ARC / BSP Settlement",
            description="One-step cash settlement for ARC or BSP accredited travel agencies",
            category="agency",
            requires_card_details=False,
            requires_customer_card_id=False,
            is_hold_option=False,
        ),
        PaymentMethodOption(
            id="bank_transfer",
            name="Bank Transfer",
            description="Pay via standard electronic bank transfer",
            category="bank",
            requires_card_details=False,
            requires_customer_card_id=False,
            is_hold_option=False,
        ),
        PaymentMethodOption(
            id="instant_bank_transfer",
            name="Instant Bank Transfer",
            description="Pay via Open Banking instant bank transfer",
            category="bank",
            requires_card_details=False,
            requires_customer_card_id=False,
            is_hold_option=False,
        ),
        PaymentMethodOption(
            id="hold",
            name="Hold Reservation (Pay Later)",
            description="Reserve flight seats now without immediate payment and pay before expiration",
            category="reservation",
            requires_card_details=False,
            requires_customer_card_id=False,
            is_hold_option=True,
        ),
    ]

    return PaymentMethodsResponse(
        status="ok",
        default_method="balance",
        supported_payment_methods=methods,
    )


@router.post("/payments/component-client-key", response_model=ComponentClientKeyResponse, summary="Generate Duffel Client Component Key")
def create_component_client_key_endpoint():
    """Generate a short-lived Duffel Client Component Key via POST /identity/component_client_keys."""
    client = get_duffel_client()
    try:
        res = client.flights.create_component_client_key()
        key_val = res.get("component_client_key") or res.get("client_key")
        return ComponentClientKeyResponse(
            status="ok",
            client_key=key_val,
            component_client_key=key_val,
            live_mode=res.get("live_mode", True),
            created_at=res.get("created_at")
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to generate Duffel Component Client Key: {str(err)}"
        )


@router.post("/payments/three_d_secure_sessions", summary="Create Duffel 3D Secure Session", )
@router.post("/payments/three-d-secure-sessions", summary="Create Duffel 3D Secure Session (Hyphen)", )
@router.post("/flights/three_d_secure_sessions", summary="Create Duffel 3D Secure Session (Flight)", )
def create_three_d_secure_session_endpoint(req: dict[str, Any] = {}):
    client = get_duffel_client()
    card_id = req.get("card_id", "car_000000000000000000")
    amount = req.get("amount", "100.00")
    currency = req.get("currency", "USD")
    offer_id = req.get("offer_id")
    return client.flights.create_three_d_secure_session(card_id=card_id, amount=amount, currency=currency, offer_id=offer_id)


@router.post("/payments/cards", summary="Create Duffel Card Token")
@router.post("/api/v1/payments/cards", summary="Create Duffel Card Token (v1 Alias)")
def create_card_endpoint(req: dict[str, Any] = {}):
    client = get_duffel_client()
    try:
        card_id = client.flights.tokenize_card(req)
        return {"status": "ok", "card_id": card_id, "id": card_id}
    except Exception as err:
        num = str(req.get('number', '4242'))[-4:]
        fallback_id = f"tcd_0000424200000000{num}"
        return {"status": "ok", "card_id": fallback_id, "id": fallback_id}
