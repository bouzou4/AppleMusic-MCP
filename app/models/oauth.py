from sqlalchemy import Column, String, DateTime, Text, ForeignKey, Integer
from sqlalchemy.sql import func
from datetime import datetime
import json

from app.core.database import Base

class OAuth2Client(Base):
    __tablename__ = "oauth2_clients"
    
    client_id = Column(String, primary_key=True)
    client_name = Column(String)
    redirect_uris = Column(Text)  # JSON serialized list
    grant_types = Column(Text)    # JSON serialized list
    response_types = Column(Text) # JSON serialized list
    scope = Column(String)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())
    
    @property
    def redirect_uris_list(self):
        return json.loads(self.redirect_uris) if self.redirect_uris else []
    
    @redirect_uris_list.setter
    def redirect_uris_list(self, value):
        self.redirect_uris = json.dumps(value)
    
    @property
    def grant_types_list(self):
        return json.loads(self.grant_types) if self.grant_types else []
    
    @grant_types_list.setter
    def grant_types_list(self, value):
        self.grant_types = json.dumps(value)
    
    @property
    def response_types_list(self):
        return json.loads(self.response_types) if self.response_types else []
    
    @response_types_list.setter
    def response_types_list(self, value):
        self.response_types = json.dumps(value)

class AuthorizationRequest(Base):
    __tablename__ = "authorization_requests"
    
    id = Column(String, primary_key=True)
    client_id = Column(String, ForeignKey("oauth2_clients.client_id"))
    redirect_uri = Column(String)
    scope = Column(String)
    state = Column(String)
    code_challenge = Column(String)
    code_challenge_method = Column(String)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())

class AuthorizationCodeGrant(Base):
    __tablename__ = "authorization_code_grants"
    
    code = Column(String, primary_key=True)
    client_id = Column(String, ForeignKey("oauth2_clients.client_id"))
    redirect_uri = Column(String)
    scope = Column(String)
    code_challenge = Column(String)
    code_challenge_method = Column(String)
    apple_user_token = Column(Text)
    apple_refresh_token = Column(Text)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())

class AccessToken(Base):
    __tablename__ = "access_tokens"
    
    access_token_jti = Column(String, primary_key=True)
    refresh_token = Column(String, unique=True)
    client_id = Column(String, ForeignKey("oauth2_clients.client_id"))
    scope = Column(String)
    apple_user_token = Column(Text)
    apple_refresh_token = Column(Text)
    expires_at = Column(DateTime)
    created_at = Column(DateTime, default=func.now())