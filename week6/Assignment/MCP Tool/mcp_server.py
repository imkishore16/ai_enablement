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
SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]

def load_google_drive_docs():
    global INSURANCE_DOCS_CONTENT

    creds = None
    token_path = "token.pickle"
    credentials_path = "./credentials.json"

    if not os.path.exists(credentials_path):
        raise RuntimeError("Missing credentials.json")

    if os.path.exists(token_path):
        with open(token_path, "rb") as f:
            creds = pickle.load(f)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                credentials_path, SCOPES
            )
            creds = flow.run_local_server(port=8080)

        with open(token_path, "wb") as f:
            pickle.dump(creds, f)

    service = build("drive", "v3", credentials=creds)

    file_id = os.getenv("GOOGLE_DRIVE_FILE_ID")
    if not file_id:
        raise RuntimeError("GOOGLE_DRIVE_FILE_ID not set")

    meta = service.files().get(
        fileId=file_id,
        fields="mimeType",
    ).execute()

    mime_type = meta["mimeType"]

    if "google-apps.document" in mime_type:
        request = service.files().export_media(
            fileId=file_id,
            mimeType="text/plain",
        )
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        INSURANCE_DOCS_CONTENT = buf.getvalue().decode("utf-8", errors="ignore")

    elif "pdf" in mime_type.lower():
        request = service.files().get_media(fileId=file_id)
        buf = io.BytesIO()
        downloader = MediaIoBaseDownload(buf, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()

        reader = PdfReader(buf)
        pages = []
        for i, page in enumerate(reader.pages, 1):
            text = page.extract_text()
            if text:
                pages.append(text)
        INSURANCE_DOCS_CONTENT = "\n".join(pages)

    else:
        raise RuntimeError("Unsupported file type")


@mcp.tool()
def search_insurance_docs(query: str) -> str:
    """Search insurance documents from Google Drive."""
    if not INSURANCE_DOCS_CONTENT:
        return "No documents loaded."

    words = query.lower().split()
    sentences = re.split(r"[.!?\n]+", INSURANCE_DOCS_CONTENT)

    matches = [
        s.strip()
        for s in sentences
        if s.strip() and any(w in s.lower() for w in words)
    ]

    if not matches:
        return "No relevant information found."

    return "\n\n".join(matches[:5])


if __name__ == "__main__":
    load_google_drive_docs()
    mcp.run(host="127.0.0.1", port=8000)
