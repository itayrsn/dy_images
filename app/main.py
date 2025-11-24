import os
import requests
import streamlit as st
import qdrant_client

db = qdrant_client.QdrantClient(url="http://localhost:6333")
EMBEDDING_SERVICE_URL = os.getenv("EMBEDDING_SERVICE_URL", "http://localhost:8001")


# --- Service Functions ---
def search(query: str, top_k=15):
    # request post to embedding service
    response = requests.post(f"{EMBEDDING_SERVICE_URL}/embed", json={"string": query})
    embedding = response.json()["embedding"]
    return db.query_points(collection_name="images", query=embedding, with_payload=True, limit=top_k).points

# --- Page Config ---
st.set_page_config(
    page_title="DY Image Search",
    page_icon="🔍",
    layout="centered"
)

# --- Style & CSS ---
# This hides the default Streamlit menu and adds some custom styling for the images
st.markdown("""
<style>
    .stTextInput > div > div > input {
        font-size: 20px;
    }
    /* Normalize result image sizing */
    .stImage img {
        width: 100% !important;
        max-height: 250px;
        object-fit: cover;
        border-radius: 10px;
        transition: transform 0.3s ease;
    }
    .stImage img:hover {
        transform: scale(1.05);
    }
</style>
""", unsafe_allow_html=True)

# --- Interface ---
st.title("🔍 DY Image Search")
st.markdown("Search through your images using **natural language** descriptions")

query = st.text_input("What are you looking for?", placeholder="e.g., 'a man in a forest'")

if query:
    results = search(query, top_k=15)
    st.markdown("### Top Matches")
    
    # Display Results in a Grid
    cols = st.columns(3)
    for i, result in enumerate(results):
        with cols[i % 3]:
            st.image(result.payload['src_url'], width='stretch')
            st.caption(f"Similarity Score: {result.score:.4f}")
