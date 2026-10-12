import logging
import time
from functools import lru_cache
from typing import List, Optional
from google import genai
from google.genai import types

from app.core.config import get_settings
from app.rag.chunker import ChunkPayload

logger = logging.getLogger(__name__)


class GeminiEmbeddingService:
    """
    Embedding service using Google Gemini Embedding 2 (gemini-embedding-2).
    Utilizes Matryoshka Representation Learning (MRL) configured to output 1536 dimensions
    to match PostgreSQL Vector(1536) in ai.document_chunks.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        dimension: Optional[int] = None,
    ):
        settings = get_settings()
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.EMBEDDING_MODEL
        self.dimension = dimension or settings.EMBEDDING_DIMENSION

        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not configured! Embedding calls will fail.")

        self.client = genai.Client(api_key=self.api_key)
        logger.info(
            "Initialized GeminiEmbeddingService with model='%s', dimension=%d",
            self.model,
            self.dimension,
        )

    def embed_query(self, query: str, max_retries: int = 3) -> List[float]:
        """
        Embed a single text query (e.g. for user search query in RAG retrieval).
        """
        query_text = query.strip()
        if not query_text:
            raise ValueError("Cannot embed empty query")

        config = types.EmbedContentConfig(output_dimensionality=self.dimension)

        for attempt in range(1, max_retries + 1):
            try:
                response = self.client.models.embed_content(
                    model=self.model,
                    contents=query_text,
                    config=config,
                )
                if not response.embeddings or not response.embeddings[0].values:
                    raise RuntimeError("No embedding values returned from Gemini API")

                embedding_values = list(response.embeddings[0].values)
                if len(embedding_values) != self.dimension:
                    raise ValueError(
                        f"Expected embedding dimension {self.dimension}, got {len(embedding_values)}"
                    )
                return embedding_values
            except Exception as e:
                logger.warning(
                    "Gemini embed_query failed (attempt %d/%d): %s",
                    attempt,
                    max_retries,
                    e,
                )
                if attempt == max_retries:
                    raise
                time.sleep(2 ** attempt)

        raise RuntimeError("Failed to embed query after retries")

    def embed_documents(
        self,
        texts: List[str],
        batch_size: int = 20,
        max_retries: int = 3,
    ) -> List[List[float]]:
        """
        Embed a batch of document texts in chunks.
        Sends multi-content batch requests to optimize network roundtrips and API quota.
        """
        if not texts:
            return []

        all_embeddings: List[List[float]] = []
        config = types.EmbedContentConfig(output_dimensionality=self.dimension)

        # Process in batches
        for i in range(0, len(texts), batch_size):
            batch = texts[i : i + batch_size]
            # Format multi-content request
            contents_payload = [{"parts": [{"text": text}]} for text in batch]

            success = False
            for attempt in range(1, max_retries + 1):
                try:
                    response = self.client.models.embed_content(
                        model=self.model,
                        contents=contents_payload,
                        config=config,
                    )
                    if not response.embeddings or len(response.embeddings) != len(batch):
                        raise RuntimeError(
                            f"Mismatch in returned embeddings count: expected {len(batch)}, got {len(response.embeddings) if response.embeddings else 0}"
                        )

                    for emb in response.embeddings:
                        values = list(emb.values)
                        if len(values) != self.dimension:
                            raise ValueError(
                                f"Expected dimension {self.dimension}, got {len(values)}"
                            )
                        all_embeddings.append(values)

                    success = True
                    break
                except Exception as e:
                    logger.warning(
                        "Batch embedding error for batch [%d:%d] (attempt %d/%d): %s",
                        i,
                        i + len(batch),
                        attempt,
                        max_retries,
                        e,
                    )
                    if attempt == max_retries:
                        raise
                    time.sleep(2 ** attempt)

            if not success:
                raise RuntimeError(f"Failed to embed batch starting at index {i}")

        return all_embeddings

    def embed_chunks(
        self,
        chunks: List[ChunkPayload],
        batch_size: int = 20,
    ) -> List[List[float]]:
        """Convenience method to embed a list of ChunkPayload objects."""
        texts = [c.content for c in chunks]
        return self.embed_documents(texts=texts, batch_size=batch_size)


@lru_cache
def get_embedding_service() -> GeminiEmbeddingService:
    """Singleton cached factory for GeminiEmbeddingService."""
    return GeminiEmbeddingService()
