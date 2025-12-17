import jwt
from datetime import datetime, timedelta
from typing import Optional
import os

from database import authenticate_user, get_user_permissions

SECRET_KEY = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 480

class AuthHandler:
    def encode_token(self, user_id: int, user_type: str, email: str) -> str:
        """
        Create JWT token with user info
        """
        payload = {
            "sub": str(user_id),
            "type": user_type,
            "email": email,
            "exp": datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
            "iat": datetime.utcnow()
        }
        return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
    
    def decode_token(self, token: str) -> Optional[dict]:
        """
        Decode and validate JWT token
        """
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            return {
                "user_id": int(payload.get("sub")),
                "user_type": payload.get("type"),
                "email": payload.get("email"),
                "expires": payload.get("exp")
            }
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
            return None
    
    def authenticate_and_create_token(
        self, 
        email: str, 
        password: str, 
        user_type: str,
        ip_address: str,
        user_agent: str
    ) -> Optional[dict]:
        """
        Authenticate user using ONLY database
        """
        print(f"Authenticating: {email} as {user_type}")
        
        # Get user from database
        user = authenticate_user(email, password, user_type)
        
        if not user:
            print(f"Authentication failed for {email}")
            return None
        
        print(f"User found: {user.id}, {user.email}")
        
        # Get user permissions
        permissions = get_user_permissions(user.id, user.role)
        
        # Create token
        token_email = user.email if user.email else user.user_name
        token = self.encode_token(user.id, user.role, token_email)
        
        return {
            "access_token": token,
            "token_type": "bearer",
            "user": {
                "id": user.id,
                "email": token_email,
                "username": user.user_name,
                "name": f"{user.first_name or ''} {user.last_name or ''}".strip(),
                "role": user.role,
                "permissions": permissions.get("permissions", []),
                "details": permissions
            }
        }