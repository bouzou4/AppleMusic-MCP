from fastapi import APIRouter, HTTPException, Depends, Query, Form
from fastapi.responses import RedirectResponse
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
from urllib.parse import urlencode
import uuid
import time
import jwt
import hashlib
import base64
import re
from datetime import datetime, timedelta

from app.core.database import get_db
from app.core.config import settings
from app.core.security import encrypt_token, decrypt_token
from app.models.oauth import OAuth2Client, AuthorizationRequest, AuthorizationCodeGrant, AccessToken

router = APIRouter()

# Pydantic models for OAuth requests/responses
class ClientRegistrationRequest(BaseModel):
    redirect_uris: List[str]
    client_name: Optional[str] = None
    grant_types: Optional[List[str]] = ["authorization_code", "refresh_token"]
    response_types: Optional[List[str]] = ["code"]
    scope: Optional[str] = None
    token_endpoint_auth_method: Optional[str] = "none"

class ClientRegistrationResponse(BaseModel):
    client_id: str
    client_id_issued_at: int
    redirect_uris: List[str]
    grant_types: List[str]
    response_types: List[str] 
    token_endpoint_auth_method: str
    client_name: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "Bearer"
    expires_in: int
    refresh_token: Optional[str] = None
    scope: Optional[str] = None

@router.get("/.well-known/oauth-authorization-server")
async def oauth_metadata():
    """
    OAuth 2.1 Authorization Server Metadata (RFC 8414)
    Claude uses this for automatic endpoint discovery
    """
    return {
        "issuer": settings.oauth_base_url,
        "authorization_endpoint": f"{settings.oauth_base_url}/oauth/authorize",
        "token_endpoint": f"{settings.oauth_base_url}/oauth/token",
        "registration_endpoint": f"{settings.oauth_base_url}/oauth/register",
        "revocation_endpoint": f"{settings.oauth_base_url}/oauth/revoke",
        "scopes_supported": [
            "library:read",
            "library:write", 
            "playlists:read",
            "playlists:write",
            "recently-played:read"
        ],
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["none"],
        "token_endpoint_auth_method": "none",
        "require_pushed_authorization_requests": False
    }

@router.post("/oauth/register", response_model=ClientRegistrationResponse)
async def dynamic_client_registration(
    request: ClientRegistrationRequest,
    db: AsyncSession = Depends(get_db)
):
    """
    Dynamic Client Registration (RFC 7591)
    Claude will call this to register itself as an OAuth client
    """
    
    # Generate unique client ID
    client_id = str(uuid.uuid4())
    client_issued_at = int(time.time())
    
    # Validate redirect URIs - Claude typically uses localhost ports or claude.ai domains
    allowed_patterns = [
        r"^http://localhost:\d+/.*$",
        r"^http://127\.0\.0\.1:\d+/.*$", 
        r"^https://claude\.ai/.*$",
        r"^https://.*\.claude\.ai/.*$"
    ]
    
    for uri in request.redirect_uris:
        if not any(re.match(pattern, uri) for pattern in allowed_patterns):
            raise HTTPException(400, f"Invalid redirect URI: {uri}")
    
    # Store client registration
    client = OAuth2Client(
        client_id=client_id,
        client_name=request.client_name or "Claude MCP Client",
        scope=request.scope,
        created_at=datetime.utcnow()
    )
    
    # Set list properties using the custom setters
    client.redirect_uris_list = request.redirect_uris
    client.grant_types_list = request.grant_types
    client.response_types_list = request.response_types
    
    db.add(client)
    await db.commit()
    
    return ClientRegistrationResponse(
        client_id=client_id,
        client_id_issued_at=client_issued_at,
        redirect_uris=request.redirect_uris,
        grant_types=request.grant_types,
        response_types=request.response_types,
        token_endpoint_auth_method="none",
        client_name=request.client_name
    )

@router.get("/oauth/authorize")
async def oauth_authorize(
    response_type: str = Query(...),
    client_id: str = Query(...),
    redirect_uri: str = Query(...),
    scope: str = Query(default="library:read"),
    state: Optional[str] = Query(default=None),
    code_challenge: str = Query(...),
    code_challenge_method: str = Query(default="S256"),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth Authorization Endpoint
    Redirects user to Apple Music OAuth for authentication
    """
    
    # Validate client_id
    result = await db.execute(
        select(OAuth2Client).where(OAuth2Client.client_id == client_id)
    )
    client = result.scalar_one_or_none()
    if not client:
        raise HTTPException(400, "Invalid client_id")
    
    # Validate redirect_uri
    if redirect_uri not in client.redirect_uris_list:
        raise HTTPException(400, "Invalid redirect_uri")
    
    # Validate PKCE
    if code_challenge_method != "S256":
        raise HTTPException(400, "Only S256 code_challenge_method supported")
    
    # Store authorization request temporarily
    auth_request_id = str(uuid.uuid4())
    auth_request = AuthorizationRequest(
        id=auth_request_id,
        client_id=client_id,
        redirect_uri=redirect_uri,
        scope=scope,
        state=state or auth_request_id,  # Use auth_request_id if no state provided
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        expires_at=datetime.utcnow() + timedelta(minutes=10)
    )
    
    db.add(auth_request)
    await db.commit()
    
    # Generate developer token for MusicKit
    from app.core.security import generate_developer_token
    developer_token = generate_developer_token()
    
    # Redirect to our MusicKit authentication page
    musickit_auth_url = f"{settings.oauth_base_url}/static/musickit-auth.html?auth_request_id={auth_request_id}&developer_token={developer_token}"
    
    return RedirectResponse(url=musickit_auth_url, status_code=302)

@router.post("/oauth/musickit/callback")
async def musickit_callback(
    request: Dict[str, Any],
    db: AsyncSession = Depends(get_db)
):
    """
    Handle MusicKit user token from JavaScript
    This replaces the Apple OAuth callback in our hybrid approach
    """
    
    auth_request_id = request.get("auth_request_id")
    user_token = request.get("user_token")
    
    if not auth_request_id or not user_token:
        raise HTTPException(400, "Missing auth_request_id or user_token")
    
    # Retrieve stored authorization request
    result = await db.execute(
        select(AuthorizationRequest).where(
            AuthorizationRequest.id == auth_request_id,
            AuthorizationRequest.expires_at > datetime.utcnow()
        )
    )
    auth_request = result.scalar_one_or_none()
    
    if not auth_request:
        raise HTTPException(400, "Invalid or expired authorization request")
    
    try:
        # Generate our own authorization code for Claude
        our_auth_code = str(uuid.uuid4())
        
        # Store the authorization code mapping with MusicKit user token
        code_grant = AuthorizationCodeGrant(
            code=our_auth_code,
            client_id=auth_request.client_id,
            redirect_uri=auth_request.redirect_uri,
            scope=auth_request.scope,
            code_challenge=auth_request.code_challenge,
            code_challenge_method=auth_request.code_challenge_method,
            apple_user_token=user_token,  # This is the MusicKit user token
            apple_refresh_token=None,  # MusicKit doesn't provide refresh tokens
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        
        db.add(code_grant)
        await db.commit()
        
        # Return redirect URL for JavaScript to handle
        claude_callback_params = {
            "code": our_auth_code,
            "state": auth_request.state
        }
        
        redirect_url = f"{auth_request.redirect_uri}?" + urlencode(claude_callback_params)
        
        return {"redirect_url": redirect_url, "status": "success"}
        
    except Exception as e:
        # Return error for JavaScript to handle
        error_params = {
            "error": "server_error",
            "error_description": "Failed to process MusicKit authentication",
            "state": auth_request.state
        }
        
        error_url = f"{auth_request.redirect_uri}?" + urlencode(error_params)
        return {"redirect_url": error_url, "status": "error", "message": str(e)}

@router.get("/oauth/apple/callback")
async def apple_oauth_callback(
    code: str = Query(...),
    state: str = Query(...),  # This is our auth_request_id
    db: AsyncSession = Depends(get_db)
):
    """
    Handle callback from Apple Music OAuth
    Exchange Apple code for user token, then redirect back to Claude
    """
    
    # Retrieve stored authorization request
    result = await db.execute(
        select(AuthorizationRequest).where(
            AuthorizationRequest.id == state,
            AuthorizationRequest.expires_at > datetime.utcnow()
        )
    )
    auth_request = result.scalar_one_or_none()
    
    if not auth_request:
        raise HTTPException(400, "Invalid or expired authorization request")
    
    try:
        # Exchange Apple authorization code for user token
        apple_token_response = await exchange_apple_authorization_code(code)
        
        # Generate our own authorization code for Claude
        our_auth_code = str(uuid.uuid4())
        
        # Store the authorization code mapping
        code_grant = AuthorizationCodeGrant(
            code=our_auth_code,
            client_id=auth_request.client_id,
            redirect_uri=auth_request.redirect_uri,
            scope=auth_request.scope,
            code_challenge=auth_request.code_challenge,
            code_challenge_method=auth_request.code_challenge_method,
            apple_user_token=apple_token_response["access_token"],
            apple_refresh_token=apple_token_response.get("refresh_token"),
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )
        
        db.add(code_grant)
        await db.commit()
        
        # Redirect back to Claude with our authorization code
        claude_callback_params = {
            "code": our_auth_code,
            "state": auth_request.state
        }
        
        claude_callback_url = (
            f"{auth_request.redirect_uri}?" + urlencode(claude_callback_params)
        )
        
        return RedirectResponse(url=claude_callback_url, status_code=302)
        
    except Exception as e:
        # Redirect to Claude with error
        error_params = {
            "error": "server_error",
            "error_description": "Failed to authenticate with Apple Music",
            "state": auth_request.state
        }
        
        error_url = f"{auth_request.redirect_uri}?" + urlencode(error_params)
        return RedirectResponse(url=error_url, status_code=302)

async def exchange_apple_authorization_code(code: str) -> Dict[str, Any]:
    """Exchange Apple authorization code for user token"""
    import httpx
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://appleid.apple.com/auth/token",
            data={
                "client_id": settings.apple_client_id,
                "client_secret": settings.apple_client_secret,
                "code": code,
                "grant_type": "authorization_code",
                "redirect_uri": f"{settings.oauth_base_url}/oauth/apple/callback"
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"}
        )
        
        if response.status_code != 200:
            raise Exception(f"Apple OAuth failed: {response.text}")
        
        return response.json()

@router.post("/oauth/token", response_model=TokenResponse)
async def oauth_token(
    grant_type: str = Form(...),
    code: Optional[str] = Form(None),
    refresh_token: Optional[str] = Form(None),
    client_id: str = Form(...),
    code_verifier: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db)
):
    """
    OAuth Token Endpoint
    Exchange authorization code or refresh token for access token
    """
    
    if grant_type == "authorization_code":
        return await handle_authorization_code_grant(
            code, client_id, code_verifier, db
        )
    elif grant_type == "refresh_token":
        return await handle_refresh_token_grant(
            refresh_token, client_id, db
        )
    else:
        raise HTTPException(400, "Unsupported grant_type")

async def handle_authorization_code_grant(
    code: str, 
    client_id: str, 
    code_verifier: str, 
    db: AsyncSession
) -> TokenResponse:
    """Handle authorization_code grant type"""
    
    # Retrieve and validate authorization code
    result = await db.execute(
        select(AuthorizationCodeGrant).where(
            AuthorizationCodeGrant.code == code,
            AuthorizationCodeGrant.client_id == client_id,
            AuthorizationCodeGrant.expires_at > datetime.utcnow()
        )
    )
    code_grant = result.scalar_one_or_none()
    
    if not code_grant:
        raise HTTPException(400, "Invalid or expired authorization code")
    
    # Verify PKCE code_verifier
    expected_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip('=')
    
    if expected_challenge != code_grant.code_challenge:
        raise HTTPException(400, "Invalid code_verifier")
    
    # Generate access token with encrypted Apple token
    access_token_payload = {
        "sub": client_id,
        "apple_user_token": encrypt_token(code_grant.apple_user_token),
        "apple_refresh_token": encrypt_token(code_grant.apple_refresh_token) if code_grant.apple_refresh_token else None,
        "scope": code_grant.scope,
        "iat": int(time.time()),
        "exp": int(time.time()) + settings.access_token_lifetime,
        "token_type": "Bearer"
    }
    
    access_token = jwt.encode(
        access_token_payload, 
        settings.jwt_secret_key, 
        algorithm="HS256"
    )
    
    # Generate refresh token
    refresh_token = str(uuid.uuid4())
    
    # Store tokens
    token_record = AccessToken(
        access_token_jti=str(uuid.uuid4()),
        refresh_token=refresh_token,
        client_id=client_id,
        scope=code_grant.scope,
        apple_user_token=code_grant.apple_user_token,
        apple_refresh_token=code_grant.apple_refresh_token,
        expires_at=datetime.utcnow() + timedelta(seconds=settings.access_token_lifetime)
    )
    
    db.add(token_record)
    
    # Clean up authorization code
    await db.delete(code_grant)
    await db.commit()
    
    return TokenResponse(
        access_token=access_token,
        token_type="Bearer",
        expires_in=settings.access_token_lifetime,
        refresh_token=refresh_token,
        scope=code_grant.scope
    )

async def handle_refresh_token_grant(
    refresh_token: str,
    client_id: str,
    db: AsyncSession
) -> TokenResponse:
    """Handle refresh_token grant type"""
    
    # Find the refresh token
    result = await db.execute(
        select(AccessToken).where(
            AccessToken.refresh_token == refresh_token,
            AccessToken.client_id == client_id
        )
    )
    token_record = result.scalar_one_or_none()
    
    if not token_record:
        raise HTTPException(400, "Invalid refresh token")
    
    # TODO: Refresh Apple Music token if needed
    # For now, reuse existing Apple token
    
    # Generate new access token
    access_token_payload = {
        "sub": client_id,
        "apple_user_token": encrypt_token(token_record.apple_user_token),
        "apple_refresh_token": encrypt_token(token_record.apple_refresh_token) if token_record.apple_refresh_token else None,
        "scope": token_record.scope,
        "iat": int(time.time()),
        "exp": int(time.time()) + settings.access_token_lifetime,
        "token_type": "Bearer"
    }
    
    new_access_token = jwt.encode(
        access_token_payload, 
        settings.jwt_secret_key, 
        algorithm="HS256"
    )
    
    # Update token record
    token_record.expires_at = datetime.utcnow() + timedelta(seconds=settings.access_token_lifetime)
    await db.commit()
    
    return TokenResponse(
        access_token=new_access_token,
        token_type="Bearer",
        expires_in=settings.access_token_lifetime,
        refresh_token=refresh_token,  # Reuse same refresh token
        scope=token_record.scope
    )