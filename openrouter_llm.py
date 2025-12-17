import jwt
from fastapi import FastAPI, Request, Response, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# ---------------- Vanna imports ----------------
from vanna import Agent, AgentConfig
from vanna.core.registry import ToolRegistry
from vanna.core.user import UserResolver, RequestContext, User
from vanna.tools import RunSqlTool
from vanna.servers.fastapi import VannaFastAPIServer
from vanna.integrations.anthropic import AnthropicLlmService
from vanna.integrations.mysql import MySQLRunner
from vanna.integrations.chromadb import ChromaAgentMemory

# ---------------- CONFIG ----------------
JWT_SECRET = "CHANGE_ME_SECRET"
JWT_ALGO = "HS256"

# ---------------- AUTH ----------------
class JwtUserResolver(UserResolver):
    async def resolve_user(self, request_context: RequestContext) -> User:
        token = request_context.get_cookie("vanna_token")

        if not token:
            return User(id="anonymous", username="guest", group_memberships=[])

        try:
            payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGO])
            return User(
                id=payload["id"],
                email=payload["email"],
                group_memberships=payload["groups"]
            )
        except Exception:
            return User(id="anonymous", username="guest", group_memberships=[])

# ---------------- LLM ----------------
llm = AnthropicLlmService(
    model="claude-sonnet-4-20250514",
    api_key="YOUR_ANTHROPIC_KEY"
)

# ---------------- DATABASE ----------------
db_tool = RunSqlTool(
    sql_runner=MySQLRunner(
        host="localhost",
        database="all_in_one",
        user="vanna",
        password="12345678",
        port=3306
    )
)

# ---------------- MEMORY ----------------
agent_memory = ChromaAgentMemory(
    persist_directory="./chroma",
    collection_name="tool_memories"
)

# ---------------- TOOLS ----------------
tools = ToolRegistry()
tools.register_local_tool(db_tool, access_groups=["admin", "user"])

# ---------------- AGENT ----------------
agent = Agent(
    llm_service=llm,
    tool_registry=tools,
    user_resolver=JwtUserResolver(),
    agent_memory=agent_memory,
    config=AgentConfig(stream_responses=True)
)

# ---------------- FASTAPI ----------------
app = FastAPI()

# ---------------- LOGIN ----------------
class LoginRequest(BaseModel):
    email: str
    password: str

@app.post("/login")
def login(data: LoginRequest, response: Response):
    if data.email == "admin@example.com" and data.password == "admin123":
        groups = ["admin"]
    elif data.email == "user@example.com" and data.password == "user123":
        groups = ["user"]
    else:
        raise HTTPException(status_code=401, detail="Invalid login")

    token = jwt.encode(
        {"id": data.email, "email": data.email, "groups": groups},
        JWT_SECRET,
        algorithm=JWT_ALGO
    )

    response.set_cookie(
        key="vanna_token",
        value=token,
        httponly=True,
        samesite="lax"
    )

    return {"success": True}

# ---------------- UI (HTML + CSS + JS) ----------------
HTML_PAGE = """
<!DOCTYPE html>
<html>
<head>
<title>Vanna Chat</title>
<style>
body { font-family: Arial; background:#f4f4f4; }
.box { width:300px; margin:80px auto; background:#fff; padding:20px; border-radius:6px; }
#chat { width:600px; height:420px; margin:20px auto; background:#fff; overflow:auto; padding:10px; border-radius:6px; display:none; }
.user { text-align:right; margin:6px; }
.bot { text-align:left; margin:6px; color:#007bff; }
#input { width:600px; margin:auto; display:none; }
input, button { padding:10px; width:100%; margin-top:10px; }
</style>
</head>
<body>

<div class="box" id="loginBox">
  <h3>Login</h3>
  <input id="email" placeholder="Email">
  <input id="password" type="password" placeholder="Password">
  <button onclick="login()">Login</button>
</div>

<div id="chat"></div>

<div id="input">
  <input id="msg" placeholder="Ask something...">
  <button onclick="send()">Send</button>
</div>

<script>
async function login() {
  const res = await fetch("/login", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    body:JSON.stringify({
      email:email.value,
      password:password.value
    })
  });

  if(res.ok){
    loginBox.style.display="none";
    chat.style.display="block";
    input.style.display="flex";
  } else {
    alert("Invalid login");
  }
}

async function send(){
  const text = msg.value;
  msg.value="";
  chat.innerHTML += `<div class="user">${text}</div>`;

  const bot = document.createElement("div");
  bot.className="bot";
  chat.appendChild(bot);

  const res = await fetch("/api/chat", {
    method:"POST",
    headers:{ "Content-Type":"application/json" },
    credentials:"include",
    body:JSON.stringify({
      messages:[{role:"user", content:text}]
    })
  });

  const reader = res.body.getReader();
  const decoder = new TextDecoder();

  while(true){
    const {value, done} = await reader.read();
    if(done) break;
    decoder.decode(value).split("\\n").forEach(line=>{
      if(!line.trim()) return;
      const e = JSON.parse(line);
      if(e.type==="text"){
        bot.textContent += e.content;
        chat.scrollTop = chat.scrollHeight;
      }
    });
  }
}
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def ui():
    return HTML_PAGE

# ---------------- Vanna API ----------------
server = VannaFastAPIServer(agent)
server.run()

# ---------------- RUN ----------------
# uvicorn server:app --reload
