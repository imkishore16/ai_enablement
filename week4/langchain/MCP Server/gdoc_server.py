from mcp.server.fastmcp import FastMCP
import os
import pickle
import io
import re
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from PyPDF2 import PdfReader

mcp = FastMCP("GoogleDocsMCP")

INSURANCE_DOCS_CONTENT = ""
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

def load_google_drive_docs():
    global INSURANCE_DOCS_CONTENT
    
    creds = None
    token_path = 'token.pickle'
    credentials_path = './credentials.json'
    
    if not os.path.exists(credentials_path):
        return False
    
    try:
        if os.path.exists(token_path):
            with open(token_path, 'rb') as token:
                creds = pickle.load(token)
        
        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    credentials_path, 
                    SCOPES,
                    redirect_uri='http://localhost:8080/'
                )
                creds = flow.run_local_server(
                    port=8080,
                    success_message='Authentication successful! You can close this window.',
                    open_browser=True
                )
            
            with open(token_path, 'wb') as token:
                pickle.dump(creds, token)
            
        service = build('drive', 'v3', credentials=creds)
        file_id = os.getenv("GOOGLE_DRIVE_FILE_ID")
        
        if not file_id:
            return False
        
        file_metadata = service.files().get(fileId=file_id, fields='name,mimeType,size').execute()
        mime_type = file_metadata.get('mimeType')
        
        if 'google-apps.document' in mime_type:
            request = service.files().export_media(fileId=file_id, mimeType='text/plain')
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_content.seek(0)
            INSURANCE_DOCS_CONTENT = file_content.read().decode('utf-8', errors='ignore')
            
        elif 'pdf' in mime_type.lower():
            request = service.files().get_media(fileId=file_id)
            pdf_content = io.BytesIO()
            downloader = MediaIoBaseDownload(pdf_content, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            pdf_content.seek(0)
            pdf_reader = PdfReader(pdf_content)
            
            text_content = []
            for page_num, page in enumerate(pdf_reader.pages, 1):
                page_text = page.extract_text()
                if page_text:
                    text_content.append(f"--- Page {page_num} ---\n{page_text}\n")
            
            INSURANCE_DOCS_CONTENT = "\n".join(text_content)
            
        else:
            request = service.files().get_media(fileId=file_id)
            file_content = io.BytesIO()
            downloader = MediaIoBaseDownload(file_content, request)
            
            done = False
            while not done:
                status, done = downloader.next_chunk()
            
            file_content.seek(0)
            INSURANCE_DOCS_CONTENT = file_content.read().decode('utf-8', errors='ignore')
        
        return True
        
    except Exception as e:
        print(f"Error loading docs: {e}")
        return False

@mcp.tool()
def search_insurance_docs(query: str) -> str:
    """Search insurance documents for relevant information based on a query."""
    if not INSURANCE_DOCS_CONTENT:
        return "No documents loaded. Please ensure Google Drive credentials are configured."
    
    query_lower = query.lower()
    sentences = re.split(r'[.!?\n]+', INSURANCE_DOCS_CONTENT)
    relevant_sentences = []
    
    for sentence in sentences:
        sentence = sentence.strip()
        if sentence and any(word in sentence.lower() for word in query_lower.split()):
            relevant_sentences.append(sentence)
    
    if relevant_sentences:
        result = "\n\n".join(relevant_sentences[:5])
        return f"Found in insurance documents:\n\n{result}"
    else:
        return "No relevant information found in the insurance documents for your query."

if __name__ == "__main__":
    load_google_drive_docs()
    mcp.run()