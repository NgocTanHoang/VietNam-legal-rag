import logging
from qdrant_client import QdrantClient
from app.core.config import settings

logging.basicConfig(level=logging.INFO)

def main():
    try:
        client = QdrantClient(
            url=settings.qdrant_connection_url,
            api_key=settings.QDRANT_API_KEY
        )
        collection_name = settings.QDRANT_COLLECTION
        print(f"Connecting to Qdrant at {settings.qdrant_connection_url}...")
        print(f"Collection name: {collection_name}")
        
        exists = client.collection_exists(collection_name=collection_name)
        print(f"Collection exists: {exists}")
        if exists:
            info = client.get_collection(collection_name=collection_name)
            print(f"Vector size: {info.config.params.vector_size if hasattr(info.config.params, 'vector_size') else info.config.params.vectors.size}")
            print(f"Points count: {info.points_count}")
    except Exception as e:
        print(f"Error inspecting Qdrant: {e}")

if __name__ == "__main__":
    main()
