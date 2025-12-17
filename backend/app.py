from fastapi import FastAPI, Depends, HTTPException, Request, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import json
import asyncio
from typing import AsyncGenerator
from pydantic import BaseModel
import uuid
import httpx
from datetime import datetime

from auth import AuthHandler
from database import authenticate_user, update_user_signin, get_user_permissions

app = FastAPI(title="Vanna AI Authentication Proxy")

# CORS configuration - UPDATED
origins = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
    "http://localhost:5500",
    "http://127.0.0.1:5500",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
    "http://localhost:8080",
    "http://127.0.0.1:8080",
    "http://localhost",
    "http://127.0.0.1",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS", "PATCH"],
    allow_headers=["*"],
    expose_headers=["*"],
    max_age=86400,
)

security = HTTPBearer()
auth_handler = AuthHandler()

# Vanna server URL
VANNA_SERVER = "http://localhost:8000"

class LoginRequestModel(BaseModel):
    email: str
    password: str
    user_type: str = "user"

class ChatRequest(BaseModel):
    message: str
    conversation_id: str = None

# CORS preflight endpoints
@app.options("/api/auth/login")
async def options_login():
    return JSONResponse(
        content={"message": "CORS preflight"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization",
        }
    )

@app.options("/api/vanna/v2/{path:path}")
async def options_vanna(path: str):
    return JSONResponse(
        content={"message": "CORS preflight"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "*",
        }
    )

@app.options("/api/auth/me")
async def options_me():
    return JSONResponse(
        content={"message": "CORS preflight"},
        headers={
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
            "Access-Control-Allow-Headers": "Authorization",
        }
    )

@app.post("/api/auth/login")
async def login(request: LoginRequestModel, req: Request):
    """
    Authenticate against existing MySQL admins/users tables
    """
    # Get client info
    client_host = req.client.host if req.client else "unknown"
    user_agent = req.headers.get("user-agent", "unknown")
    
    # Authenticate
    auth_result = auth_handler.authenticate_and_create_token(
        email=request.email,
        password=request.password,
        user_type=request.user_type,
        ip_address=client_host,
        user_agent=user_agent
    )
    
    if not auth_result:
        raise HTTPException(
            status_code=401,
            detail="Invalid credentials or account disabled"
        )
    
    return auth_result

@app.get("/api/auth/me")
async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Get current user info from token
    """
    token_data = auth_handler.decode_token(credentials.credentials)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    permissions = get_user_permissions(
        token_data["user_id"], 
        token_data["user_type"]
    )
    
    return {
        "id": token_data["user_id"],
        "email": token_data["email"],
        "type": token_data["user_type"],
        "permissions": permissions
    }

@app.post("/api/vanna/v2/chat_sse")
async def chat_sse_proxy(
    request: ChatRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Proxy to Vanna's SSE endpoint with authentication
    """
    token_data = auth_handler.decode_token(credentials.credentials)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Get user
    user_email = token_data["email"]
    user_type = token_data["user_type"]
    
    # Determine appropriate email for Vanna based on user type
    if user_type.startswith("admin"):
        vanna_cookie_email = "admin@example.com"
    else:
        vanna_cookie_email = user_email or "guest@example.com"
    
    conversation_id = request.conversation_id or f"{token_data['user_id']}_{uuid.uuid4()}"
    
    async def event_generator() -> AsyncGenerator[str, None]:
        # Create SSE connection to the actual Vanna server
        async with httpx.AsyncClient(timeout=60.0) as client:
            try:
                # Forward the request to Vanna server
                async with client.stream(
                    "POST",
                    f"{VANNA_SERVER}/api/vanna/v2/chat_sse",
                    json={
                        "message": request.message,
                        "conversation_id": conversation_id,
                        "metadata": {}
                    },
                    headers={
                        "Cookie": f"vanna_email={vanna_cookie_email}",
                        "Content-Type": "application/json"
                    }
                ) as response:
                    async for chunk in response.aiter_text():
                        yield chunk
                        
            except Exception as e:
                yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            'Cache-Control': 'no-cache',
            'Connection': 'keep-alive',
            'X-Accel-Buffering': 'no',
            'Access-Control-Allow-Origin': '*',
        }
    )

@app.post("/api/vanna/v2/chat_poll")
async def chat_poll_proxy(
    request: ChatRequest,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    """
    Proxy to Vanna's polling endpoint with authentication
    """
    token_data = auth_handler.decode_token(credentials.credentials)
    if not token_data:
        raise HTTPException(status_code=401, detail="Invalid token")
    
    # Get user
    user_email = token_data["email"]
    user_type = token_data["user_type"]
    
    # Determine appropriate email for Vanna
    if user_type.startswith("admin"):
        vanna_cookie_email = "admin@example.com"
    else:
        vanna_cookie_email = user_email or "guest@example.com"
    
    conversation_id = request.conversation_id or f"{token_data['user_id']}_{uuid.uuid4()}"
    
    async with httpx.AsyncClient() as client:
        try:
            # Forward to Vanna server
            response = await client.post(
                f"{VANNA_SERVER}/api/vanna/v2/chat_poll",
                json={
                    "message": request.message,
                    "conversation_id": conversation_id,
                    "metadata": {}
                },
                headers={
                    "Cookie": f"vanna_email={vanna_cookie_email}",
                    "Content-Type": "application/json"
                },
                timeout=30.0
            )
            
            if response.status_code != 200:
                raise HTTPException(
                    status_code=response.status_code,
                    detail=response.text
                )
            
            return response.json()
            
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Vanna server timeout")
        except httpx.RequestError as e:
            raise HTTPException(status_code=502, detail=f"Vanna server error: {str(e)}")

# Health check endpoints
@app.get("/")
async def root():
    return {"message": "Vanna AI Authentication Proxy"}

@app.get("/health")
async def health_check():
    # Also check if Vanna server is healthy
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{VANNA_SERVER}/health", timeout=5.0)
            vanna_status = response.status_code == 200
    except:
        vanna_status = False
    
    return {
        "status": "healthy",
        "vanna_server": "connected" if vanna_status else "disconnected",
        "timestamp": str(datetime.utcnow())
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=8001,
        # Optional: Add these for better CORS handling
        proxy_headers=True,
        forwarded_allow_ips="*"
    )