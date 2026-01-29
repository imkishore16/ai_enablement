
import os
from typing import TypedDict, Annotated, Literal
from langchain_openai import AzureChatOpenAI
from langchain_community.tools import DuckDuckGoSearchRun
from langchain.tools import Tool
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

llm = AzureChatOpenAI(
    azure_deployment="gpt-4.1",
    api_version="2024-12-01-preview",
    temperature=0,
    azure_endpoint="https://ai-enablement.openai.azure.com/",
    api_key="api key"
)

web_search = DuckDuckGoSearchRun()

class AgentState(TypedDict):
    messages: Annotated[list, "messages"]
    next_agent: str

IT_DOCS_DIR = "./it_docs"
FINANCE_DOCS_DIR = "./finance_docs"


# TODO : file system MCp
def read_file_tool(directory: str):
    """Create a ReadFile tool for a specific directory."""
    def read_file(filename: str) -> str:
        """Read a file from the specified directory."""
        file_path = os.path.join(directory, filename)
        if not os.path.exists(file_path):
            return f"File '{filename}' not found in {directory} directory."
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            return f"Content of {filename}:\n\n{content}"
        except Exception as e:
            return f"Error reading file '{filename}': {str(e)}"
    
    return read_file

it_read_file = read_file_tool(IT_DOCS_DIR)
finance_read_file = read_file_tool(FINANCE_DOCS_DIR)

it_tools = [
    Tool(
        name="ReadFile",
        func=it_read_file,
        description="Read internal IT documentation files. Use this to find information about IT policies, procedures, approved software, VPN setup, hardware requests, etc. Provide the filename (e.g., 'vpn_setup.txt', 'approved_software.txt', 'laptop_request.txt')"
    ),
    Tool(
        name="WebSearch",
        func=web_search.run,
        description="Search the web for external IT information, technical documentation, software guides, troubleshooting steps, and industry best practices."
    )
]

finance_tools = [
    Tool(
        name="ReadFile",
        func=finance_read_file,
        description="Read internal finance documentation files. Use this to find information about reimbursement procedures, budget reports, payroll schedules, expense policies, etc. Provide the filename (e.g., 'reimbursement_policy.txt', 'budget_report.txt', 'payroll_schedule.txt')"
    ),
    Tool(
        name="WebSearch",
        func=web_search.run,
        description="Search the web for public finance data, industry benchmarks, financial regulations, and external financial information."
    )
]

it_llm = llm.bind_tools(it_tools)
finance_llm = llm.bind_tools(finance_tools)


def supervisor_agent(state: AgentState) -> AgentState:
    """Supervisor agent that classifies queries and routes to appropriate agent."""
    messages = state["messages"]
    
    user_query = ""
    for msg in messages:
        if isinstance(msg, HumanMessage):
            user_query = msg.content
            break
    
    classification_prompt = """You are a supervisor agent that classifies user queries into one of two categories: IT or Finance.

IT queries include:
- VPN setup, network issues, software installation
- Hardware requests (laptops, monitors, etc.)
- IT policies and approved software
- Technical support questions
- System access and permissions

Finance queries include:
- Reimbursements and expense claims
- Budget reports and financial data
- Payroll questions and schedules
- Financial policies and procedures
- Invoice and payment inquiries

User Query: {query}

Classify this query and respond with ONLY one word: either "IT" or "Finance".""".format(query=user_query)
    
    response = llm.invoke([HumanMessage(content=classification_prompt)])
    
    classification = response.content.strip().upper()
    
    if "IT" in classification:
        next_agent = "it_agent"
    elif "FINANCE" in classification:
        next_agent = "finance_agent"
    else:
        next_agent = "it_agent"
    
    return {
        "messages": messages,
        "next_agent": next_agent
    }

def it_agent(state: AgentState) -> AgentState:
    """IT agent that handles IT-related queries."""
    messages = state["messages"]
    
    system_message = SystemMessage(content="""You are an IT support agent. Your role is to help users with IT-related queries including:
- VPN setup and configuration
- Approved software and installation procedures
- Hardware requests (laptops, monitors, etc.)
- IT policies and procedures
- Technical troubleshooting

Use the ReadFile tool to access internal IT documentation and the WebSearch tool for external technical information.
Provide clear, step-by-step instructions when applicable.
If you cannot find the information, suggest contacting IT support directly.""")
    
    # Filter out supervisor routing messages
    filtered_messages = [msg for msg in messages if not (isinstance(msg, AIMessage) and "Routing to" in msg.content)]
    agent_messages = [system_message] + filtered_messages
    
    response = it_llm.invoke(agent_messages)
    
    return {
        "messages": [response],
        "next_agent": state.get("next_agent", "")
    }

# Finance Agent
def finance_agent(state: AgentState) -> AgentState:
    """Finance agent that handles Finance-related queries."""
    messages = state["messages"]
    
    system_message = SystemMessage(content="""You are a Finance support agent. Your role is to help users with Finance-related queries including:
- Reimbursement procedures and filing
- Budget reports and financial data
- Payroll schedules and processing
- Expense policies and procedures
- Invoice and payment inquiries

Use the ReadFile tool to access internal finance documentation and the WebSearch tool for public finance data and industry benchmarks.
Provide clear, accurate information with relevant dates and procedures.
If you cannot find the information, suggest contacting the Finance department directly.""")
    
    # Filter out supervisor routing messages
    filtered_messages = [msg for msg in messages if not (isinstance(msg, AIMessage) and "Routing to" in msg.content)]
    agent_messages = [system_message] + filtered_messages
    
    response = finance_llm.invoke(agent_messages)
    
    return {
        "messages": [response],
        "next_agent": state.get("next_agent", "")
    }

# Router function for supervisor
def supervisor_router(state: AgentState) -> Literal["it_agent", "finance_agent"]:
    """Route to the appropriate agent based on supervisor decision."""
    next_agent = state.get("next_agent", "it_agent")
    
    if next_agent == "it_agent":
        return "it_agent"
    elif next_agent == "finance_agent":
        return "finance_agent"
    else:
        return "it_agent"


# Router function for IT agent
def it_agent_router(state: AgentState) -> Literal["it_tools", "end"]:
    """Route IT agent to tools or end."""
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, AIMessage) and hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "it_tools"
    return "end"

# Router function for Finance agent
def finance_agent_router(state: AgentState) -> Literal["finance_tools", "end"]:
    """Route Finance agent to tools or end."""
    messages = state["messages"]
    last_message = messages[-1] if messages else None
    
    if isinstance(last_message, AIMessage) and hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        return "finance_tools"
    return "end"

# Create tool nodes
it_tool_node = ToolNode(it_tools)
finance_tool_node = ToolNode(finance_tools)

# Build the graph
workflow = StateGraph(AgentState)

# Add nodes
workflow.add_node("supervisor", supervisor_agent)
workflow.add_node("it_agent", it_agent)
workflow.add_node("finance_agent", finance_agent)
workflow.add_node("it_tools", it_tool_node)
workflow.add_node("finance_tools", finance_tool_node)

# Set entry point
workflow.set_entry_point("supervisor")

# Add edges
workflow.add_conditional_edges(
    "supervisor",
    supervisor_router,
    {
        "it_agent": "it_agent",
        "finance_agent": "finance_agent"
    }
)

# IT agent routes to tools if tool calls exist, otherwise ends
workflow.add_conditional_edges(
    "it_agent",
    it_agent_router,    
    {
        "it_tools": "it_tools",
        "end": END
    }
)

# Finance agent routes to tools if tool calls exist, otherwise ends
workflow.add_conditional_edges(
    "finance_agent",
    finance_agent_router,
    {
        "finance_tools": "finance_tools",
        "end": END
    }
)


workflow.add_edge("it_tools", "it_agent")
workflow.add_edge("finance_tools", "finance_agent")


app = workflow.compile()

def run_query(query: str):
    """Run a query through the multi-agent system."""
    initial_state = {
        "messages": [HumanMessage(content=query)],
        "next_agent": ""
    }
    
    result = app.invoke(initial_state)
    
    final_messages = result["messages"]
    for msg in reversed(final_messages):
        if isinstance(msg, AIMessage):
            if not hasattr(msg, 'tool_calls') or not msg.tool_calls:
                return msg.content
    
    return "No response generated."

if __name__ == "__main__":
    os.makedirs(IT_DOCS_DIR, exist_ok=True)
    os.makedirs(FINANCE_DOCS_DIR, exist_ok=True)
    
    test_queries = [
        "How to set up VPN?",
        "What software is approved for use?",
        "How to file a reimbursement?",
        "When is payroll processed?",
    ]
    
    print("=" * 70)
    print("Multi-Agent Support System")
    print("=" * 70)
    
    for query in test_queries:
        print(f"\nQuery: {query}")
        print("-" * 70)
        response = run_query(query)
        print(f"Response: {response}")
        print("=" * 70)
