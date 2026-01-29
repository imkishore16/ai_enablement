import os
import asyncio
import requests

from langfuse import get_client
from langfuse.langchain import CallbackHandler

from langchain_community.document_loaders import PyPDFLoader
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.tools import DuckDuckGoSearchRun

from langchain_openai import AzureChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.tools import Tool
from langchain.agents import AgentExecutor, create_react_agent

from nemoguardrails import LLMRails, RailsConfig




langfuse = get_client()
langfuse_handler = CallbackHandler()

EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

embeddings = HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL)

docs = []
pdf_files = ["Hybrid Work Policy 2026.pdf"]

for file in pdf_files:
    loader = PyPDFLoader(file)
    docs.extend(loader.load())

db = Chroma.from_documents(
    docs,
    embedding=embeddings,
    persist_directory="./vectorstore"
)
db.persist()


def hr_policy_search(query: str) -> str:
    results = db.similarity_search(query, k=3)
    return "\n".join(r.page_content for r in results)


web_search = DuckDuckGoSearchRun()

MCP_BASE_URL = "http://127.0.0.1:8000/mcp"


def mcp_invoke_tool(tool_name: str, arguments: dict) -> str:
    """Invoke an MCP tool over HTTP"""
    response = requests.post(
        f"{MCP_BASE_URL}/tools/{tool_name}/invoke",
        json={"arguments": arguments},
        timeout=10,
    )
    response.raise_for_status()

    data = response.json()

    if isinstance(data.get("content"), list):
        return "\n".join(
            part.get("text", "") for part in data["content"]
        )

    return str(data.get("content", ""))


def load_mcp_tools() -> list[Tool]:
    """Discover MCP tools and wrap them as LangChain tools"""
    response = requests.get(f"{MCP_BASE_URL}/tools", timeout=10)
    response.raise_for_status()

    mcp_tools: list[Tool] = []

    for tool_def in response.json():
        tool_name = tool_def["name"]
        description = tool_def.get("description", "")

        def make_tool(name: str):
            return Tool(
                name=name,
                description=description,
                func=lambda query, n=name: mcp_invoke_tool(
                    n, {"query": query}
                ),
            )

        mcp_tools.append(make_tool(tool_name))

    return mcp_tools


mcp_tools = load_mcp_tools()



llm = AzureChatOpenAI(
    azure_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT_NAME"),
    api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
    azure_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
    api_key=os.getenv("AZURE_OPENAI_API_KEY"),
    temperature=0,
)

tools = [
    Tool(
        name="HR_Policy_Search",
        func=hr_policy_search,
        description="Search HR policy documents for internal policies and guidelines",
    ),
    Tool(
        name="Web_Search",
        func=web_search.run,
        description="Fetch industry benchmarks and external information",
    ),
    *mcp_tools,
]



template = """Answer the following questions as best you can. You have access to the following tools:

{tools}

Use the following format:

Question: the input question you must answer
Thought: you should always think about what to do
Action: the action to take, should be one of [{tool_names}]
Action Input: the input to the action
Observation: the result of the action
... (this Thought/Action/Action Input/Observation can repeat N times)
Thought: I now know the final answer
Final Answer: the final answer to the original input question

Begin!

Question: {input}
Thought:{agent_scratchpad}
"""

prompt = PromptTemplate.from_template(template)



agent = create_react_agent(llm, tools, prompt)

agent_executor = AgentExecutor(
    agent=agent,
    tools=tools,
    verbose=True,
    max_iterations=10,
    handle_parsing_errors=True,
    callbacks=[langfuse_handler],
)



rails_config = RailsConfig.from_path("./guardrails_config")
rails = LLMRails(rails_config)


async def guarded_agent_invoke(user_input: str) -> str:
    # Input guardrails
    input_check = await rails.generate_async(
        messages=[{"role": "user", "content": user_input}]
    )

    if input_check.get("refusal"):
        return input_check["content"]

    # Agent execution
    agent_result = agent_executor.invoke({"input": user_input})
    agent_output = agent_result["output"]

    # Output guardrails
    output_check = await rails.generate_async(
        messages=[{"role": "assistant", "content": agent_output}]
    )

    return output_check["content"]

async def main():
    queries = [
        "Compare our current hiring trend with industry benchmarks.",
        "Give me details about health insurance and hospital expenses options available for employees.",
        "How to hack HR portal?"
    ]

    for q in queries:
        print(f"\nUSER: {q}")
        response = await guarded_agent_invoke(q)
        print(f"ASSISTANT:\n{response}")

    langfuse.flush()


if __name__ == "__main__":
    asyncio.run(main())
