# streamlit_vanna_chinook.py
"""
Streamlit app: Vanna 2.x + OpenAI GPT-4o-mini + SQLite fallback.
- Attaches a User to RequestContext so tools with access_groups run.
- LocalFallbackRunner returns structured {'rows'|'error'|'traceback'} payloads.
- Displays streaming components and errors (including tracebacks) in UI.
"""

import os
import asyncio
import traceback as _tb
import streamlit as st
import pandas as pd
from sqlalchemy import create_engine, text

# -------------------------
# CONFIG - via environment where possible
# -------------------------
# Set your OpenAI API key in the environment:
# export OPENAI_API_KEY="sk-..."
OPENAI_API_KEY = "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"
OPENAI_MODEL = "gpt-4o-mini"

# Path to your Chinook DB (change or set env var SQLITE_DB_PATH)
SQLITE_DB_PATH = os.environ.get("SQLITE_DB_PATH", "/home/define/Downloads/chinook.db")
ENGINE_URL = f"sqlite:///{SQLITE_DB_PATH}"

# -------------------------
# Streamlit UI
# -------------------------
st.set_page_config(page_title="Chinook NL→SQL (Vanna + OpenAI)", layout="wide")
st.title("Chinook NL→SQL — Vanna + OpenAI (GPT-4o-mini)")
st.markdown("Ask natural language questions about the Chinook DB. Toggle Vanna to try the LLM-backed agent.")

if not os.path.exists(SQLITE_DB_PATH):
    st.error(f"SQLite DB not found at: {SQLITE_DB_PATH}")
    st.stop()

enable_vanna = st.checkbox("Enable Vanna/OpenAI LLM", value=True)
question = st.text_input("Ask (e.g. 'show all tables', 'show all artists', 'top 10 albums by sales')")

col1, col2 = st.columns([1, 3])
with col1:
    run_btn = st.button("Ask")
with col2:
    st.write("DB:", SQLITE_DB_PATH)
    st.write("Model:", OPENAI_MODEL)

engine = create_engine(ENGINE_URL, connect_args={"check_same_thread": False})

# -------------------------
# Helpers: safe execute, table mapping
# -------------------------
def safe_execute_select(sql_text):
    """
    Raise exceptions for anything unsafe or not a SELECT.
    Returns a pandas.DataFrame for valid SELECTs.
    """
    if not sql_text or not sql_text.strip():
        raise ValueError("Empty SQL.")
    upper = sql_text.upper()
    forbidden = [";", "DELETE", "UPDATE", "DROP", "INSERT", "ALTER", "CREATE"]
    if any(tok in upper for tok in forbidden):
        raise ValueError("Refusing to execute non-SELECT / multi-statement SQL for safety.")
    if not upper.strip().startswith("SELECT"):
        raise ValueError("Only SELECT statements are allowed.")
    return pd.read_sql_query(text(sql_text), engine)

def get_table_names_lower():
    try:
        df = pd.read_sql_query(text("SELECT name FROM sqlite_master WHERE type IN ('table','view') ORDER BY name;"), engine)
        return set([str(n).lower() for n in df["name"].tolist()])
    except Exception:
        return set()

# -------------------------
# Local fallback runner
# -------------------------
class LocalFallbackRunner:
    def __init__(self, engine):
        self.engine = engine

    def run(self, sql_text):
        """
        Return structure:
         - {"rows": [...]} on success
         - {"error": "message", "traceback": "full traceback"} on failure
        """
        try:
            df = safe_execute_select(sql_text)
            return {"rows": df.to_dict(orient="records")}
        except Exception as e:
            tb = _tb.format_exc()
            return {"error": str(e), "traceback": tb}

# -------------------------
# Run button action
# -------------------------
if run_btn:
    if not question or not question.strip():
        st.warning("Please enter a question before asking.")
    else:
        debug_lines = []

        # Try Vanna imports
        use_vanna = False
        agent = None
        user_resolver = None

        if enable_vanna:
            if not OPENAI_API_KEY:
                st.error("OPENAI_API_KEY not set. Set environment variable OPENAI_API_KEY and re-run.")
            else:
                try:
                    # Vanna imports
                    from vanna import Agent as VannaAgentClass
                    from vanna.tools import RunSqlTool, VisualizeDataTool
                    from vanna.core.registry import ToolRegistry
                    from vanna.integrations.openai import OpenAILlmService
                    from vanna.core.user import RequestContext, UserResolver, User
                    from vanna.integrations.local.agent_memory import DemoAgentMemory
                    from vanna.tools.agent_memory import SaveQuestionToolArgsTool, SearchSavedCorrectToolUsesTool, SaveTextMemoryTool

                    debug_lines.append("Vanna imports successful.")

                    # LLM service
                    llm_service = OpenAILlmService(
                        api_key=OPENAI_API_KEY,
                        model=OPENAI_MODEL,
                    )
                    debug_lines.append("OpenAILlmService created.")

                    # Agent memory
                    agent_memory = DemoAgentMemory(max_items=1000)
                    debug_lines.append("DemoAgentMemory initialized.")

                    # User resolver
                    class SimpleUserResolver(UserResolver):
                        async def resolve_user(self, request_context: RequestContext) -> User:
                            # lightweight guest user that has 'user' group
                            return User(id="guest", email="guest@example.com", group_memberships=["user"])
                    user_resolver = SimpleUserResolver()

                    # Tools & registry
                    tool_registry = ToolRegistry()
                    run_sql_tool = RunSqlTool(sql_runner=LocalFallbackRunner(engine))
                    viz_tool = VisualizeDataTool()
                    tool_registry.register_local_tool(run_sql_tool, access_groups=['user','admin'])
                    tool_registry.register_local_tool(viz_tool, access_groups=['user','admin'])
                    tool_registry.register_local_tool(SaveQuestionToolArgsTool(), access_groups=['admin'])
                    tool_registry.register_local_tool(SearchSavedCorrectToolUsesTool(), access_groups=['admin','user'])
                    tool_registry.register_local_tool(SaveTextMemoryTool(), access_groups=['admin','user'])

                    # Construct agent
                    agent = VannaAgentClass(
                        llm_service=llm_service,
                        tool_registry=tool_registry,
                        user_resolver=user_resolver,
                        agent_memory=agent_memory
                    )
                    use_vanna = True
                    debug_lines.append("Agent constructed successfully.")
                except Exception as e:
                    debug_lines.append(f"Vanna agent setup failed: {e}")
                    use_vanna = False

        # Show debug lines
        if debug_lines:
            st.subheader("Vanna debug:")
            for ln in debug_lines:
                st.text(ln)

        # Run agent
        if use_vanna and agent is not None:
            st.info("Using Vanna agent (OpenAI LLM) — streaming output below.")
            outpl = st.empty()
            tool_error_box = st.empty()

            async def run_agent():
                # start with no user, then resolve and attach
                request_context = RequestContext(user=None, metadata={})
                try:
                    resolved_user = await user_resolver.resolve_user(request_context)
                    request_context.user = resolved_user
                    outpl.write(f"Resolved user: id={resolved_user.id}, groups={getattr(resolved_user, 'group_memberships', None)}")
                except Exception as e:
                    outpl.write(f"Warning: failed to resolve user: {e}")

                captured = None
                try:
                    async for comp in agent.send_message(request_context=request_context, message=question):
                        # 1) If tool returned a dict (our LocalFallbackRunner structured responses)
                        if isinstance(comp, dict):
                            if 'rows' in comp:
                                captured = comp['rows']
                                outpl.write("Tool returned rows.")
                            elif 'error' in comp:
                                # display short error and full traceback if present
                                tool_error_box.error(f"Tool error: {comp.get('error')}")
                                if comp.get('traceback'):
                                    outpl.write("Tool traceback (detailed):")
                                    st.code(comp.get('traceback'))
                            else:
                                outpl.write(repr(comp))
                            continue

                        # 2) If Vanna returned a rich component (task tracker / status etc.)
                        rich = getattr(comp, "rich_component", None)
                        simple = getattr(comp, "simple_component", None)
                        if rich is not None:
                            try:
                                comp_type = getattr(rich, "type", None)
                                status = getattr(rich, "status", None)
                                detail = getattr(rich, "detail", None)
                                task_id = getattr(rich, "task_id", None)
                                outpl.write(f"Component: type={comp_type}, status={status}, task_id={task_id}")
                                if detail:
                                    # show task detail; if it mentions 'error' highlight it
                                    if "error" in str(detail).lower():
                                        tool_error_box.error(f"Task detail: {detail}")
                                    else:
                                        outpl.write(f"Detail: {detail}")
                            except Exception:
                                outpl.write(repr(rich))
                            continue

                        # 3) fallback text/content shapes
                        if hasattr(comp, 'text') and getattr(comp, 'text'):
                            outpl.write(comp.text)
                        elif hasattr(comp, 'content') and getattr(comp, 'content'):
                            outpl.write(comp.content)
                        else:
                            outpl.write(repr(comp))

                    # show rows if captured
                    if captured is not None:
                        st.subheader("Tool result")
                        st.dataframe(pd.DataFrame(captured))
                    else:
                        st.info("Agent finished with no tool rows. Check any tool error messages above.")
                except Exception as e:
                    st.error(f"Agent runtime error: {e}")
                    st.code(_tb.format_exc())

            # run the async agent safely within Streamlit
            try:
                asyncio.run(run_agent())
            except RuntimeError:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(run_agent())
                loop.close()

        # Fallback if Vanna not used or failed
        if not use_vanna:
            st.info("Fallback mode (no LLM). Showing sample tables/results.")
            try:
                existing = get_table_names_lower()
                for t in ["albums","artists","tracks","invoices","customers"]:
                    if t in existing:
                        df = pd.read_sql_query(f"SELECT * FROM {t} LIMIT 5", engine)
                        st.subheader(t)
                        st.dataframe(df)
            except Exception as e:
                st.error(f"Fallback SQL error: {e}")
                st.code(_tb.format_exc())
