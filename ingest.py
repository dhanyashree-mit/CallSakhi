import os
from langchain_community.document_loaders import PyMuPDFLoader, DirectoryLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain_mongodb import MongoDBAtlasVectorSearch
from pymongo import MongoClient
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configuration
DATA_PATH = "knowledge_base/"
MONGODB_URI = os.getenv("MONGODB_URI")
DB_NAME = "callsakhi"
COLLECTION_NAME = "knowledge"
ATLAS_VECTOR_SEARCH_INDEX_NAME = "vector_index"

def normalize(text):
    return str(text).lower().strip().replace("&", "and")

def create_vector_db():
    print("--- [INGEST] Starting document ingestion for MongoDB Atlas ---")
    
    if not MONGODB_URI:
        print("--- [ERROR] MONGODB_URI not found in .env file ---")
        return

    # Load documents
    if not os.path.exists(DATA_PATH):
        print(f"--- [ERROR] Data path {DATA_PATH} does not exist ---")
        return

    print(f"--- [INGEST] Loading documents from {DATA_PATH} ---")
    loader = DirectoryLoader(DATA_PATH, glob='*.pdf', loader_cls=PyMuPDFLoader)
    documents = loader.load()
    
    if not documents:
        print("--- [ERROR] No PDF documents found in knowledge_base ---")
        return

    print(f"--- [INGEST] Loaded {len(documents)} pages ---")

    # Add normalized chapter metadata to each document
    for doc in documents:
        # Extract filename without extension as chapter name
        chapter_name = os.path.basename(doc.metadata.get('source', 'Unknown')).replace('.pdf', '')
        doc.metadata['chapter'] = normalize(chapter_name)

    # Split text
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
    texts = text_splitter.split_documents(documents)
    print(f"--- [INGEST] Created {len(texts)} text chunks with normalized chapter metadata ---")

    # Create embeddings
    print("--- [INGEST] Generating embeddings ---")
    embeddings = HuggingFaceEmbeddings(model_name='sentence-transformers/all-MiniLM-L6-v2',
                                       model_kwargs={'device': 'cpu'})

    # Connect to MongoDB
    print("--- [INGEST] Connecting to MongoDB Atlas ---")
    client = MongoClient(
        MONGODB_URI, 
        tls=True,
        tlsAllowInvalidCertificates=True, # Workaround for TLS handshake issues
        serverSelectionTimeoutMS=5000
    )
    # Check connection
    client.admin.command('ping')
    collection = client[DB_NAME][COLLECTION_NAME]

    # Insert into MongoDB Atlas Vector Search
    print("--- [INGEST] Uploading to MongoDB Atlas... ---")
    vector_search = MongoDBAtlasVectorSearch.from_documents(
        documents=texts,
        embedding=embeddings,
        collection=collection,
        index_name=ATLAS_VECTOR_SEARCH_INDEX_NAME
    )
    
    print(f"--- [SUCCESS] Uploaded to collection: {DB_NAME}.{COLLECTION_NAME} ---")
    print("--- [IMPORTANT] Now go to Atlas UI and create the Vector Search Index as per the guide. ---")

if __name__ == "__main__":
    create_vector_db()
