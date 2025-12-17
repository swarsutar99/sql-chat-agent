from typing import Optional
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from pydantic import BaseModel
import os
from datetime import datetime

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "mysql+pymysql://vanna:12345678@localhost/all_in_one"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

class User(BaseModel):
    id: int
    email: Optional[str] = None
    user_name: Optional[str] = None
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    role: str  # 'admin' or 'user'
    encrypted_password: str

def authenticate_user(email: str, password: str, user_type: str) -> Optional[User]:
    """
    SIMPLE AUTHENTICATION FOR DEVELOPMENT
    """
    db = SessionLocal()
    try:
        if user_type == "admin":
            # Get admin from database
            result = db.execute(
                text("""
                    SELECT id, email, encrypted_password, role_id, is_enabled
                    FROM admins 
                    WHERE email = :email AND is_enabled = 1
                    LIMIT 1
                """),
                {"email": email}
            ).fetchone()
            
            if result:
                user_id, user_email, encrypted_pw, role_id, is_enabled = result
                print(f"Found admin: {user_email}, Role ID: {role_id}")
                print(f"DB Password hash: {encrypted_pw}")
                print(f"User entered password: {password}")
                
                # DEVELOPMENT MODE: Allow common passwords
                common_passwords = [
                    "12345678",
                    "password",
                    "admin123", 
                    "admin",
                    "123456",
                    "test123",
                    "password123",
                    "admin@123"
                ]
                
                # Check if password is in common passwords list
                if password in common_passwords:
                    print(f"✅ DEVELOPMENT: Allowing common password '{password}' for admin {email}")
                    return User(
                        id=user_id,
                        email=user_email,
                        role=f"admin_role_{role_id}",
                        encrypted_password=encrypted_pw
                    )
                
                # Try to match with encrypted password (optional)
                if password == encrypted_pw:
                    print(f"✅ Password matches encrypted hash")
                    return User(
                        id=user_id,
                        email=user_email,
                        role=f"admin_role_{role_id}",
                        encrypted_password=encrypted_pw
                    )
                
                print(f"❌ Password '{password}' not in allowed list")
        
        elif user_type == "user":
            # Get user from database
            result = db.execute(
                text("""
                    SELECT id, user_name, encrypted_password, first_name, last_name
                    FROM users 
                    WHERE user_name = :username
                    LIMIT 1
                """),
                {"username": email}
            ).fetchone()
            
            if result:
                user_id, username, encrypted_pw, first_name, last_name = result
                print(f"Found user: {username}")
                
                # Same common passwords for users
                common_passwords = ["12345678", "password", "user123", "test123"]
                
                if password in common_passwords:
                    print(f"✅ Allowing common password for user {username}")
                    return User(
                        id=user_id,
                        email=username,
                        user_name=username,
                        first_name=first_name,
                        last_name=last_name,
                        role="user",
                        encrypted_password=encrypted_pw
                    )
        
        return None
    except Exception as e:
        print(f"Authentication error: {e}")
        return None
    finally:
        db.close()

def update_user_signin(user_id: int, user_type: str, ip_address: str, user_agent: str):
    """
    Update sign-in statistics
    """
    # Simplified - just log for now
    print(f"User {user_id} ({user_type}) signed in from {ip_address}")
    return True

def get_user_permissions(user_id: int, user_type: str) -> dict:
    """
    Get user permissions
    """
    if user_type.startswith("admin"):
        return {
            "role": "Administrator",
            "permissions": ["full_access", "manage_users", "view_reports"],
            "is_enabled": True
        }
    else:
        return {
            "role": "User",
            "permissions": ["query_data", "view_own_history"],
            "status": "active"
        }