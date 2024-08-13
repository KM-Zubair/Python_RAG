from collections import OrderedDict
import logging
import os
import uuid
import shutil
import tempfile
import streamlit as st
import pandas as pd
from itertools import chain
from dotenv import load_dotenv
from ibm_watson_machine_learning.metanames import GenTextParamsMetaNames as GenParams
from ibm_watson_machine_learning.foundation_models.utils.enums import ModelTypes
from langchain_community.document_loaders import PyPDFLoader
from langchain_community.embeddings import HuggingFaceHubEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import Chroma
from langchain import PromptTemplate
from ibm_watson_machine_learning.foundation_models import Model
from mdb import delete_many_documents, get_many_documents, is_document_exist
from mongo_db_helper import get_questions, insert_questions, upload_file_cos
import httpx

# Set up logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

#logging.basicConfig(level=os.environ.get("LOGLEVEL", "DEBUG"))

st.set_page_config(
    page_title="DUDE",
    page_icon="🧊",
    layout="wide",
)

load_dotenv()

PROJECT_ID = os.getenv("PROJECT_ID", None)

MODEL_CREDENTIALS = {
    "url": os.getenv("IBM_CLOUD_URL", None),
    "apikey": os.getenv("IBM_MODEL_API_KEY", None)
}
# Check if API key is loaded correctly
if MODEL_CREDENTIALS["apikey"] is None:
    raise ValueError("The API key shouldn't be None. Please check your environment variables.")

# Initialize the HTTP clients
client = httpx.Client()
async_client = httpx.AsyncClient()

# Initialize HuggingFaceHubEmbeddings with the necessary arguments
embeddings = HuggingFaceHubEmbeddings(
    client=client,
    async_client=async_client,
    repo_id="sentence-transformers/all-MiniLM-L6-v2",
    huggingfacehub_api_token="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"
)

# Path to the directory where Chroma stores embeddings
persist_directory = "embeddings/"

# Delete the directory and its contents to reset Chroma
shutil.rmtree(persist_directory, ignore_errors=True)

# Optionally, recreate the directory
os.makedirs(persist_directory, exist_ok=True)

# Reinitialize Chroma with the cleared directory
chroma_db = Chroma(embedding_function=embeddings, persist_directory=persist_directory)

temp_dir = tempfile.mkdtemp()


with st.sidebar:
    uploaded_files = st.file_uploader(
        "Choose a PDF file", accept_multiple_files=True, label_visibility="collapsed")
    
    
    LLM_MAX_NEW_TOKENS = st.number_input(label='LLM Max New Tokens', value=4096)
    CHUNK_SIZE = st.number_input(label='Embeddings Chunk Size', value=2000)
    CHUNK_OVERLAP = st.number_input(label='Embeddings Chunk Overlap', value=400)
    K_TOP_CONTEXTS = st.number_input(label='K-TOP Contexts For Embeddings', value=3)

@st.cache_data
def process_pdf(uploaded_files, chunk_size=CHUNK_SIZE, chunk_overlap=CHUNK_OVERLAP):
    for uploaded_file in uploaded_files:
        file_name = uploaded_file.name
        file_id = uploaded_file.file_id
        file_type = uploaded_file.type
        file_size = uploaded_file.size

        logging.info(f"Processing file: {file_name}, ID: {file_id}, Type: {file_type}, Size: {file_size}")

        if is_document_exist(file_id):
            logging.info(f"File {file_name} already exists, skipping.")
            continue

        if (file_type not in ['application/pdf', 'application/json']):
            logging.error(f"Invalid file type: {file_type}")
            return st.error("Invalid file type")
        
        bytes_data = uploaded_file.read()
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as temp_file:
            temp_file.write(bytes_data)
            filepath = temp_file.name
            logging.info(f"Temporary file created: {filepath}")
            with st.spinner('Waiting for the file to upload'):
                if (file_type == 'application/pdf'):
                    logging.info("Processing PDF file")
                    loader = PyPDFLoader(filepath)
                    data = loader.load()
                    logging.info(f"PDF loaded, pages: {len(data)}")
                    text_splitter = RecursiveCharacterTextSplitter(
                        chunk_size=chunk_size, chunk_overlap=chunk_overlap)
                    docs = text_splitter.split_documents(data)
                    logging.info(f"Document split into {len(docs)} chunks")
                    chunk_ids = [str(uuid.uuid4()) for _ in range(len(docs))]
                    logging.info("Uploading file to COS")
                    upload_file_cos(filepath, file_name, file_id, file_size, chunk_ids)
                    logging.info("File uploaded to COS")
                    logging.info("Creating embeddings and storing in Chroma")
                    chroma_db.from_documents(ids=chunk_ids, documents=docs, embedding=embeddings, persist_directory="embeddings\\")
                    logging.info("Embeddings created and stored")
                elif (file_type == 'application/json'):
                    logging.info("Processing JSON file")
                    insert_questions(bytes_data)
                    logging.info("Questions inserted from JSON")

    logging.info("PDF processing completed")

process_pdf(uploaded_files)


MODEL_TYPE = ModelTypes.FLAN_UL2
PROMPT_TEMPLATE = '''You are an AI assistant tasked with answering questions based solely on the provided context. Do not use any external knowledge:
Here's the document: \n"{context}"\n
Here is the Question:{question}

Instructions:
1. Carefully analyze the context and the question.
2. If the context contains information directly relevant to the question, provide a concise and accurate answer based only on that information.
3. If the answer cannot be fully determined from the context, but there is related information, provide that information and explain why a complete answer isn't possible.
4. If the context does not contain any information related to the question, respond with exactly "Answer not found in the provided context."
5. Do not make assumptions or provide information not present in the given context.

Answer:
'''


GEN_PARAMETERS = {
    GenParams.DECODING_METHOD: 'greedy',
    GenParams.MAX_NEW_TOKENS: LLM_MAX_NEW_TOKENS,
}

PRE_PROMPT_TEMPLATE = '''Generate answers of the question based on the following document:
Here's the document: \n"{context}"\n
Here is the Question:{question}'''

llm_model = Model(MODEL_TYPE, MODEL_CREDENTIALS, GEN_PARAMETERS, PROJECT_ID)

def create_prompt(question, context=""):
    prompt_template = PromptTemplate(
        template=PRE_PROMPT_TEMPLATE, input_variables=['question', 'context'])
    prompt = prompt_template.format(question=question, context=context)
    return prompt

def top_k_context(contexts, k=K_TOP_CONTEXTS):
    context = ""
    for i in range(k):
        context += contexts[i].page_content + "\n\n"
    return context

def extract(query, top_contexts):
    prompt = create_prompt(query, top_contexts)
    output = llm_model.generate_text(prompt)
    return output

def process_question(user_question):
    logging.info(f"Processing question: {user_question}")
    contexts = []

    mmr_retriever = chroma_db.as_retriever(search_kwargs={"k": K_TOP_CONTEXTS, "include_metadata": True})
    try:
        logging.info("Retrieving relevant documents")
        contexts = mmr_retriever.get_relevant_documents(user_question)
        logging.info(f"Retrieved {len(contexts)} relevant documents")
    except Exception as e:
        logging.error(f"Error retrieving documents: {str(e)}")
        contexts = []

    top_contexts = top_k_context(contexts) if len(contexts) > 0 else ''
    logging.info("Extracting answer")
    response = extract(user_question, top_contexts)
    logging.info("Answer extracted")
    return response, contexts, top_contexts

tab1, tab2 = st.tabs(["Virtual Assistant", "Document Manager"])

if user_question := st.chat_input("Ask a question"):
    st.session_state.clear()
    st.session_state['user_question'] = user_question
    
    response, contexts, top_contexts = process_question(user_question)

    st.session_state['assistant_answer'] = response
    if len(contexts) > 0:
        st.session_state['extra_details'] = top_contexts

if 'user_question' in st.session_state:
    with tab1.chat_message("user"):
            st.markdown(st.session_state['user_question'])

if 'assistant_answer' in st.session_state:
    with tab1.chat_message("assistant"):
        st.markdown(st.session_state['assistant_answer'])
        st.divider()
        if 'extra_details' in st.session_state:
            with st.expander("Reference paragraphs from the document"):
                st.write(st.session_state['extra_details'])

shutil.rmtree(temp_dir)

documents = get_many_documents()

updated_docs = []
for obj in documents:
    updated_obj = OrderedDict([("is_selected", False)] + list(obj.items()))
    obj.clear() 
    obj.update(updated_obj) 
    updated_docs.append(obj)

df = pd.DataFrame(updated_docs)
edited_df = tab2.data_editor(df)

if tab2.button("Delete selected", type="primary"):
    ids_to_delete = []
    chunk_ids_to_delete =[]
    ids = edited_df.loc[edited_df["is_selected"]]["_id"]
    chunk_ids = edited_df.loc[edited_df["is_selected"]]["chunk_ids"]

    for id in ids:
        ids_to_delete.append(id)

    for chunk_id in chunk_ids:
        chunk_ids_to_delete.append(chunk_id)

    flattened_chunk_ids_to_delete = list(chain(*chunk_ids_to_delete))

    delete_many_documents(ids_to_delete)
    
    chroma_db.delete(flattened_chunk_ids_to_delete)
    st.rerun()