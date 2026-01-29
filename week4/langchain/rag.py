import os
from langchain_openai import AzureChatOpenAI
from langchain_community.vectorstores import Chroma
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.document_loaders import PyPDFLoader
from langchain.agents import AgentExecutor, create_react_agent
from langchain.prompts import PromptTemplate
from langchain.tools import Tool
from langchain_community.tools import DuckDuckGoSearchRun

llm = AzureChatOpenAI(
    azure_deployment="gpt-4.1",
    api_version="2024-12-01-preview",
    temperature=0,
    azure_endpoint="https://ai-enablement.openai.azure.com/",
    api_key="key"
)

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

vectorstore_path = "./vectorstore"

def initialize_vectorstore(pdf_files=None):
    """Initialize or load the Chroma vectorstore."""
    if os.path.exists(vectorstore_path) and os.path.exists(os.path.join(vectorstore_path, "chroma.sqlite3")):
        try:
            print("Loading existing vectorstore...")
            db = Chroma(
                persist_directory=vectorstore_path,
                embedding_function=embeddings
            )
            print("Vectorstore loaded successfully")
            return db
        except Exception as e:
            print(f"Error loading existing vectorstore: {e}")
            if not pdf_files:
                raise ValueError("Cannot load existing vectorstore and no PDF files provided")
    
    if pdf_files:
        print("Creating new vectorstore from PDF files...")
        docs = []
        for file in pdf_files:
            if os.path.exists(file):
                print(f"Loading {file}...")
                loader = PyPDFLoader(file)
                docs.extend(loader.load())
        
        if docs:
            db = Chroma.from_documents(
                docs,
                embedding=embeddings,
                persist_directory=vectorstore_path
            )
            db.persist()
            print(f"Created vectorstore with {len(docs)} documents")
            return db
        else:
            raise ValueError("No documents found to load")
    else:
        raise ValueError("Vectorstore does not exist and no PDF files provided. Please provide PDF files to create the vectorstore.")

def hr_policy_search(query: str, db=None):
    """Search HR policy documents for information about policies, procedures, and guidelines."""
    if db is None:
        db = initialize_vectorstore()
    
    results = db.similarity_search(query, k=3)
    return "\n".join([r.page_content for r in results])

def create_hr_agent(db=None):
    """Create an agent with HR policy search and web search tools."""
    if db is None:
        db = initialize_vectorstore()
    
    web_search = DuckDuckGoSearchRun()
    
    tools = [
        Tool(
            name="HR_Policy_Search",
            func=lambda q: hr_policy_search(q, db),
            description="Search HR policy documents for information about policies, procedures, and guidelines. Use this to find information about company policies, hiring practices, employee benefits, and internal procedures."
        ),
        Tool(
            name="Web_Search",
            func=web_search.run,
            description="Fetch industry benchmarks, trends, and external information from the web. Use this to find industry standards, market trends, and comparative data."
        )
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
Thought:{agent_scratchpad}"""

    prompt = PromptTemplate.from_template(template)
    
    agent = create_react_agent(llm, tools, prompt)
    
    agent_executor = AgentExecutor(
        agent=agent,
        tools=tools,
        verbose=True,
        handle_parsing_errors=True,
        max_iterations=10
    )
    
    return agent_executor

if __name__ == "__main__":
    db = initialize_vectorstore()
    
    agent_executor = create_hr_agent(db)
    
    result = agent_executor.invoke({
        "input": "Compare our current hiring trend with industry benchmarks."
    })
    
    print("\n" + "="*70)
    print("Final Answer:")
    print("="*70)
    print(result["output"])
