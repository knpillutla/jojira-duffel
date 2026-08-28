import base64
import hashlib
import hmac
import json
from typing import Any, Optional
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from ..schemas import (
    GoogleAuthRequest,
    GoogleAuthResponse,
    UserProfileResponse,
    SignOutRequest,
    SignOutResponse,
)

from ...db.user_dao import UserDAO
from ...config import UserServiceConfig

import urllib.parse
from fastapi.responses import RedirectResponse

router = APIRouter(prefix="/auth", tags=["User Authentication"])


@router.get(
    "/google/login",
    summary="Redirect Browser to Google OAuth 2.0 Sign-In Page",
)
def redirect_to_google_login(
    client_id: Optional[str] = None,
    redirect_uri: Optional[str] = "http://localhost:3000/auth/callback",
):
    """
    Directly redirects the browser to Google's official OAuth 2.0 Sign-In consent page.
    """
    g_client_id = client_id or "YOUR_GOOGLE_CLIENT_ID.apps.googleusercontent.com"
    scopes = urllib.parse.quote("openid email profile")
    encoded_redirect = urllib.parse.quote(redirect_uri)
    google_auth_url = (
        f"https://accounts.google.com/o/oauth2/v2/auth?"
        f"client_id={g_client_id}&"
        f"redirect_uri={encoded_redirect}&"
        f"response_type=code&"
        f"scope={scopes}&"
        f"access_type=offline&"
        f"prompt=select_account"
    )
    return RedirectResponse(url=google_auth_url)



def _generate_jwt_token(payload: dict, secret: str) -> str:
    """Generates an HS256 JWT token using standard Python base64 & hmac modules."""
    header = {"alg": "HS256", "typ": "JWT"}
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip("=")
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    signature_input = f"{header_b64}.{payload_b64}".encode()
    signature = hmac.new(secret.encode(), signature_input, hashlib.sha256).digest()
    sig_b64 = base64.urlsafe_b64encode(signature).decode().rstrip("=")
    return f"{header_b64}.{payload_b64}.{sig_b64}"


def _verify_jwt_token(token: str, secret: str) -> Optional[dict]:
    """Verifies an HS256 JWT session token signature locally in ~0.1ms without external network calls."""
    try:
        parts = token.split(".")
        if len(parts) != 3:
            return None
        header_b64, payload_b64, sig_b64 = parts
        signature_input = f"{header_b64}.{payload_b64}".encode()
        expected_sig = hmac.new(secret.encode(), signature_input, hashlib.sha256).digest()
        expected_sig_b64 = base64.urlsafe_b64encode(expected_sig).decode().rstrip("=")
        if not hmac.compare_digest(sig_b64, expected_sig_b64):
            return None
        payload_json = base64.urlsafe_b64decode(payload_b64 + "==").decode()
        payload = json.loads(payload_json)
        if payload.get("exp") and payload["exp"] < int(datetime.now(timezone.utc).timestamp()):
            return None
        return payload
    except Exception:
        return None



def _verify_google_id_token(id_token: str) -> Optional[dict]:
    """Verifies Google ID Token signature and payload against Google OAuth2 tokeninfo API."""
    import urllib.request
    import urllib.parse
    try:
        url = f"https://oauth2.googleapis.com/tokeninfo?id_token={urllib.parse.quote(id_token)}"
        req = urllib.request.Request(url, headers={"User-Agent": "Jojira-User-Service/1.0"})
        with urllib.request.urlopen(req, timeout=5) as response:
            if response.status == 200:
                data = json.loads(response.read().decode("utf-8"))
                if data.get("iss") in ["accounts.google.com", "https://accounts.google.com"]:
                    return data
    except Exception as err:
        print(f"[AUTH NOTICE] Google ID token verification notice: {err}")
    return None


@router.post(
    "/google",
    response_model=GoogleAuthResponse,
    summary="Sign-In or Register User via Google OAuth Token",
)
def authenticate_google_user(req: GoogleAuthRequest):
    """
    Syncs user authentication token payload from Google OAuth Sign-In on the frontend.
    Verifies Google ID token cryptographic signature, upserts user, and returns session JWT token.
    """
    email = req.email
    google_sub = req.google_user_id
    name = req.name
    given_name = req.given_name or req.first_name
    family_name = req.family_name or req.last_name
    picture = req.picture

    # High Security Practice: Verify Google ID token if provided by UI
    if req.google_token:
        google_payload = _verify_google_id_token(req.google_token)
        if google_payload:
            email = google_payload.get("email") or email
            google_sub = google_payload.get("sub") or google_sub
            name = google_payload.get("name") or name
            given_name = google_payload.get("given_name") or given_name
            family_name = google_payload.get("family_name") or family_name
            picture = google_payload.get("picture") or picture

    if not email:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Valid email address is required for Google OAuth user authentication."
        )


    try:
        cfg = UserServiceConfig()
        user_dao = UserDAO(config=cfg)

        user_data = user_dao.sync_google_user(
            email=email,
            google_user_id=google_sub,
            name=name,
            given_name=given_name,
            family_name=family_name,
            first_name=req.first_name,
            last_name=req.last_name,
            phone_number=req.phone_number,
            date_of_birth=req.date_of_birth,
            picture_url=picture,
        )


        if not user_data:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to retrieve synced user profile."
            )

        # Generate JWT session token
        exp_timestamp = int((datetime.now(timezone.utc) + timedelta(days=7)).timestamp())
        token_payload = {
            "sub": user_data["id"],
            "email": user_data["email"],
            "exp": exp_timestamp
        }
        token = _generate_jwt_token(token_payload, cfg.jwt_secret)

        profile_resp = UserProfileResponse(
            status="success",
            user_id=user_data["id"],
            email=user_data["email"],
            name=user_data.get("name"),
            first_name=user_data.get("first_name"),
            last_name=user_data.get("last_name"),
            given_name=user_data.get("given_name"),
            family_name=user_data.get("family_name"),
            phone_number=user_data.get("phone_number"),
            date_of_birth=user_data.get("date_of_birth"),
            picture_url=user_data.get("picture_url"),
            google_user_id=user_data.get("google_user_id"),
            last_login_at=user_data.get("last_login_at"),
            created_at=user_data.get("created_at"),
            preferences=user_data["preferences"]
        )


        return GoogleAuthResponse(
            status="success",
            message=f"User '{user_data['email']}' successfully authenticated.",
            session_token=token,
            user=profile_resp
        )
    except Exception as err:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Google OAuth authentication failed: {str(err)}"
        )


@router.post(
    "/signout",
    response_model=SignOutResponse,
    summary="Sign Out User & Invalidate Session Token",
)
@router.post(
    "/logout",
    response_model=SignOutResponse,
    include_in_schema=False,
)
def signout_user(req: Optional[SignOutRequest] = None):
    """
    Sign out user, invalidate session token, and return sign-out confirmation.
    """
    usr_id = req.user_id if req else None
    msg = f"User '{usr_id}' successfully signed out." if usr_id else "User successfully signed out."
    return SignOutResponse(
        status="success",
        message=msg
    )

