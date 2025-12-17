from vanna import Agent
from vanna.core.registry import ToolRegistry
from vanna.tools import RunSqlTool, VisualizeDataTool
from vanna.integrations.anthropic import AnthropicLlmService
from vanna.integrations.mysql import MySQLRunner
from vanna.integrations.chromadb import ChromaAgentMemory
from database import User
import os

# Cache for user agents
user_agents = {}

def get_agent_for_user(user: User) -> Agent:
    """Get or create a Vanna agent for the user with role-based access"""
    cache_key = f"{user.id}_{user.role}"
    
    if cache_key in user_agents:
        return user_agents[cache_key]
    
    # Configure LLM
    llm = AnthropicLlmService(
        model="claude-sonnet-4-20250514",
        api_key=os.getenv("ANTHROPIC_API_KEY")
    )
    
    # Database connection with appropriate permissions
    # Use different credentials based on user role
    if user.role.startswith("admin"):
        # Admin connection - full access
        db_user = "vanna_admin"
        db_password = os.getenv("DB_ADMIN_PASSWORD", "admin_password")
    else:
        # Regular user connection - restricted access
        db_user = "vanna_user"
        db_password = os.getenv("DB_USER_PASSWORD", "user_password")
    
    db_tool = RunSqlTool(
        sql_runner=MySQLRunner(
            host="localhost",
            database="all_in_one",
            user=db_user,
            password=db_password,
            port=3306
        )
    )
    
    # Agent memory with user-specific collection
    agent_memory = ChromaAgentMemory(
        persist_directory=os.getenv("CHROMA_DIR", "/home/define/sql_chat"),
        collection_name=f"user_{user.id}"
    )
    
    # Create tools with role-based access
    tools = ToolRegistry()
    
    if user.role.startswith("admin"):
        # Admin gets full access
        tools.register_local_tool(db_tool, access_groups=['admin'])
        tools.register_local_tool(VisualizeDataTool(), access_groups=['admin'])
        
        # Add admin-specific business rules
        admin_rules = """
        Admin Access Rules:
        1. Full access to all database tables
        2. Can query sensitive data like user balances
        3. Can access admin audit logs
        4. Can view system performance metrics
        """
        agent_memory.save_text_memory(admin_rules, "admin_permissions")
        
    else:
        # Regular user gets restricted access
        tools.register_local_tool(db_tool, access_groups=['user'])
        tools.register_local_tool(VisualizeDataTool(), access_groups=['user'])
        
        # Add user-specific restrictions
        user_rules = f"""
        User Access Rules for User ID {user.id}:
        1. Only access non-sensitive data
        2. Cannot view other users' personal information
        3. Limited to own betting history
        4. Financial data is aggregated and anonymized
        """
        agent_memory.save_text_memory(user_rules, "user_restrictions")
    
    # Add common business rules
    common_rules = """
    Business Rules for Betting Analytics:
    1. Only settled bets (status = 'settled') should be used in analytics.
    2. Profit = coins_credited - stake.
    3. Exclude void or cancelled bets.
    4. coins_credited includes winnings plus stake return.
    """
    agent_memory.save_text_memory(common_rules, "business_logic")
    
    # Create agent
    agent = Agent(
        llm_service=llm,
        tool_registry=tools,
        agent_memory=agent_memory,
        config={"max_tool_iterations": 30, "stream_responses": True}
    )
    
    user_agents[cache_key] = agent
    return agent