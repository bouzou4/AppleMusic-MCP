import jwt
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from app.core.config import settings

def generate_developer_token() -> str:
    """Generate Apple Music developer token (JWT)"""
    
    # Read private key
    private_key_path = Path(settings.apple_private_key_path)
    if not private_key_path.exists():
        raise FileNotFoundError(f"Private key not found at {settings.apple_private_key_path}")
    
    with open(private_key_path, 'r') as key_file:
        private_key = key_file.read()
    
    # Token payload
    now = datetime.utcnow()
    payload = {
        'iss': settings.apple_team_id,
        'iat': int(now.timestamp()),
        'exp': int((now + timedelta(hours=12)).timestamp()),  # 12 hour expiry
        'aud': 'appstoreconnect-v1'
    }
    
    # Generate JWT
    token = jwt.encode(
        payload,
        private_key,
        algorithm='ES256',
        headers={'kid': settings.apple_key_id}
    )
    
    return token

def validate_developer_token(token: str) -> bool:
    """Validate Apple Music developer token"""
    try:
        # For validation, we mainly check if it's not expired
        decoded = jwt.decode(token, options={"verify_signature": False})
        exp = decoded.get('exp', 0)
        return exp > time.time()
    except:
        return False