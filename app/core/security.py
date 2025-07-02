import jwt
import time
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from cryptography.fernet import Fernet

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

class TokenEncryption:
    """Encrypt/decrypt sensitive tokens for database storage"""
    
    def __init__(self):
        # Use the configured encryption key
        self.cipher = Fernet(settings.token_encryption_key.encode())
    
    def encrypt_token(self, token: str) -> str:
        """Encrypt sensitive token for storage"""
        return self.cipher.encrypt(token.encode()).decode()
    
    def decrypt_token(self, encrypted_token: str) -> str:
        """Decrypt token for use"""
        return self.cipher.decrypt(encrypted_token.encode()).decode()

# Utility functions for convenience
def encrypt_token(token: str) -> str:
    """Encrypt a token for database storage"""
    encryption = TokenEncryption()
    return encryption.encrypt_token(token)

def decrypt_token(encrypted_token: str) -> str:
    """Decrypt a token from database storage"""
    encryption = TokenEncryption()
    return encryption.decrypt_token(encrypted_token)