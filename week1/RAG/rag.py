
from langchain_community.document_loaders import WebBaseLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS, Chroma
from langchain_openai import AzureChatOpenAI
from langchain_community.chat_models import ChatOllama
from langchain.prompts import PromptTemplate
from langchain.chains import RetrievalQA
import bs4
import requests
from urllib.parse import urljoin, urlparse

def load_web_content():
    """Load content from specific LangChain documentation pages"""
    print("Loading web content...")
    
    urls = [
        "https://docs.langchain.com/oss/python/langchain/overview",
        "https://docs.langchain.com/oss/python/langchain/philosophy", 
        "https://docs.langchain.com/oss/python/langchain/quickstart",
        "https://docs.langchain.com/oss/python/integrations/vectorstores",
        "https://docs.langchain.com/oss/python/integrations/retrievers",
        "https://docs.langchain.com/oss/python/integrations/chat_models",
        "https://docs.langchain.com/oss/python/integrations/llms",
        "https://docs.langchain.com/oss/python/core/agents",
        "https://docs.langchain.com/oss/python/core/chains",
        "https://docs.langchain.com/oss/python/core/prompts", 
        "https://docs.langchain.com/oss/python/core/memory",
        "https://docs.langchain.com/oss/python/core/tools",
        "https://docs.langchain.com/oss/python/core/chat_history",
        "https://docs.langchain.com/oss/python/core/streaming",
        "https://docs.langchain.com/oss/python/core/structured_output",
    ]
    
    def clean_html_content(html):
        soup = bs4.BeautifulSoup(html, "html.parser")
        
        for element in soup(["script", "style", "nav", "header", "footer", 
                           "aside", "button", ".navbar", ".sidebar"]):
            element.decompose()
        
        main_content = soup.find(['main', 'article', '[role="main"]', '.content'])
        if main_content:
            text = main_content.get_text()
        else:
            body = soup.find('body')
            text = body.get_text() if body else soup.get_text()
        
        lines = (line.strip() for line in text.splitlines())
        text = '\n'.join(line for line in lines if line and len(line) > 10)
        return text

    loader = WebBaseLoader(
        web_paths=urls,
        bs_kwargs={"parse_only": bs4.SoupStrainer(["main", "article", "div", "section", "p", "h1", "h2", "h3", "h4", "li"])},
        bs_get_text_kwargs={"strip": True}
    )
    
    try:
        webcontent = loader.load()
        print(f"Loaded {len(webcontent)} documents from specific URLs")
        
        filtered_content = []
        for doc in webcontent:
            content = doc.page_content.strip()
            if (len(content) > 200 and 
                not content.startswith(('function', 'var ', 'const ', '!function')) and
                'langchain' in content.lower()):
                filtered_content.append(doc)
        
        print(f"After filtering: {len(filtered_content)} meaningful documents")
        return filtered_content
        
    except Exception as e:
        print(f"Error loading web content: {e}")
        return []

def split_documents(webcontent):
    """Split documents into chunks for processing"""
    print("Splitting documents...")
    text_splitter = RecursiveCharacterTextSplitter(
        chunk_size=1500,
        chunk_overlap=300,
        separators=["\n\n", "\n", ". ", " ", ""]
    )
    doc = text_splitter.split_documents(webcontent)
    print(f"Split into {len(doc)} chunks")
    
    doc = [chunk for chunk in doc if len(chunk.page_content.strip()) > 50]
    print(f"After filtering short chunks: {len(doc)} meaningful chunks")
    return doc

def create_embeddings():
    """Create embeddings using HuggingFace model"""
    print("Creating embeddings...")
    embeddings = HuggingFaceEmbeddings(
        model_name="sentence-transformers/all-MiniLM-L6-v2"
    )
    return embeddings

def create_vector_stores(doc, embeddings):
    """Create both FAISS and Chroma vector stores"""
    print("Creating vector stores...")
    
    if not doc:
        print("No documents to create vector stores with!")
        return None, None
        
    print(f"Creating FAISS index with {len(doc)} documents...")
    db1 = FAISS.from_documents(
        documents=doc,
        embedding=embeddings
    )
    
    print(f"Creating Chroma index with {len(doc)} documents...")
    db2 = Chroma.from_documents(
        documents=doc,
        embedding=embeddings,
        persist_directory="./chroma_db"
    )
    db2.persist()
    
    print("Vector stores created successfully")
    return db1, db2

def create_retrievers(db1, db2):
    """Create retrievers from vector stores"""
    print("Creating retrievers...")
    
    retriever1 = db1.as_retriever(
        search_type="similarity",
        search_kwargs={
            "k": 6,
        }
    )
    
    retriever2 = db2.as_retriever(
        search_type="similarity", 
        search_kwargs={
            "k": 6,
        }
    )
    
    return retriever1, retriever2

def test_retrievers(retriever1, retriever2):
    """Test the retrievers with a sample query"""
    print("Testing retrievers...")
    query = "What is LangChain?"
    
    try:
        retrieved_docs1 = retriever1.invoke(query)
        context1 = "\n\n".join(doc.page_content for doc in retrieved_docs1)
        print(f"FAISS retriever found {len(retrieved_docs1)} documents, context length: {len(context1)}")
        if retrieved_docs1:
            print(f"Sample FAISS content preview: {retrieved_docs1[0].page_content[:200]}...")
    except Exception as e:
        print(f"FAISS retriever error: {e}")
    
    try:
        retrieved_docs2 = retriever2.invoke(query)
        context2 = "\n\n".join(doc.page_content for doc in retrieved_docs2)
        print(f"Chroma retriever found {len(retrieved_docs2)} documents, context length: {len(context2)}")
        if retrieved_docs2:
            print(f"Sample Chroma content preview: {retrieved_docs2[0].page_content[:200]}...")
    except Exception as e:
        print(f"Chroma retriever error: {e}")

def create_azure_llm():
    """Create Azure OpenAI LLM"""
    print("Setting up Azure OpenAI LLM...")
    llm = AzureChatOpenAI(
        azure_deployment="gpt-4.1",  
        api_version="2024-12-01-preview",
        temperature=0,
        azure_endpoint="https://openai-101.openai.azure.com/",
        api_key=""
    )
    return llm

def create_ollama_llm():
    """Create Ollama LLM"""
    print("Setting up Ollama LLM...")
    llm = ChatOllama(
        model="llama3",
        temperature=0
    )
    return llm

def create_rag_prompt():
    """Create the RAG prompt template"""
    rag_prompt = PromptTemplate(
        input_variables=["context", "question"],
        template="""You are a helpful assistant that answers questions about LangChain and related technologies using the provided context.

Use the following context to answer the question. If you can find relevant information in the context, provide a comprehensive answer. If the information is not available in the context, then say "I don't know based on the provided context."

Context:
{context}

Question: {question}

Answer: Let me analyze the provided context to answer your question.

"""
    )
    return rag_prompt

def create_qa_chains(llm, retriever1, retriever2, rag_prompt):
    """Create QA chains for both retrievers"""
    print("Creating QA chains...")
    
    qa_chain1 = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever1,
        chain_type="stuff",
        chain_type_kwargs={"prompt": rag_prompt},
        return_source_documents=True
    )
    
    qa_chain2 = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever2,
        chain_type="stuff",
        chain_type_kwargs={"prompt": rag_prompt},
        return_source_documents=True
    )
    
    return qa_chain1, qa_chain2

def test_qa_chains(qa_chain1, qa_chain2, llm_name):
    """Test the QA chains with sample queries"""
    print(f"\n=== Testing {llm_name} QA Chains ===")
    
    queries = [
        "How do you create a vector store in LangChain?",
        "What are the main components of LangChain?"     
    ]
    
    for query in queries:
        print(f"\nQuery: {query}")
        
        print("FAISS Retriever Result:")
        result1 = qa_chain1(query)
        print("Answer:", result1["result"])
        
        print("Chroma Retriever Result:")
        result2 = qa_chain2(query)
        print("Answer:", result2["result"])

def main():
    print("Starting RAG Pipeline...")
    
    webcontent = load_web_content()
    doc = split_documents(webcontent)
    
    embeddings = create_embeddings()
    db1, db2 = create_vector_stores(doc, embeddings)
    
    retriever1, retriever2 = create_retrievers(db1, db2)
    
    test_retrievers(retriever1, retriever2)
    
    rag_prompt = create_rag_prompt()
    
    print("\n" + "="*50)
    print("TESTING WITH AZURE OPENAI")
    print("="*50)
    
    azure_llm = create_azure_llm()
    azure_qa_chain1, azure_qa_chain2 = create_qa_chains(azure_llm, retriever1, retriever2, rag_prompt)
    test_qa_chains(azure_qa_chain1, azure_qa_chain2, "Azure OpenAI")
    
    print("\n" + "="*50)
    print("TESTING WITH OLLAMA")
    print("="*50)
    
    ollama_llm = create_ollama_llm()
    ollama_qa_chain1, ollama_qa_chain2 = create_qa_chains(ollama_llm, retriever1, retriever2, rag_prompt)
    test_qa_chains(ollama_qa_chain1, ollama_qa_chain2, "Ollama")
    print("\nRAG Pipeline completed successfully!")

if __name__ == "__main__":
    main()
