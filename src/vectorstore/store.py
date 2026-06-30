"""Vector store using pgvector for JD and skill embeddings."""

from openai import AsyncOpenAI
from sqlalchemy import text

from src.config import settings
from src.database import async_session


class VectorStore:
    """Manages embeddings for job descriptions and user skills using pgvector."""

    EMBEDDING_MODEL = "text-embedding-3-small"
    EMBEDDING_DIM = 1536

    def __init__(self):
        self.client = AsyncOpenAI(api_key=settings.openai_api_key)

    async def setup_pgvector(self):
        """Initialize pgvector extension and add vector column if needed."""
        async with async_session() as session:
            await session.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
            await session.execute(
                text(
                    f"""
                    ALTER TABLE jobs
                    ADD COLUMN IF NOT EXISTS embedding_vec vector({self.EMBEDDING_DIM})
                    """
                )
            )
            # Create index for fast similarity search
            await session.execute(
                text(
                    """
                    CREATE INDEX IF NOT EXISTS jobs_embedding_idx
                    ON jobs USING ivfflat (embedding_vec vector_cosine_ops)
                    WITH (lists = 100)
                    """
                )
            )
            await session.commit()

    async def generate_embedding(self, text_content: str) -> list[float]:
        """Generate embedding for text content."""
        response = await self.client.embeddings.create(
            model=self.EMBEDDING_MODEL,
            input=text_content[:8000],  # Token limit
        )
        return response.data[0].embedding

    async def store_job_embedding(self, job_id: str, description: str, skills: list[str]):
        """Generate and store embedding for a job."""
        # Combine description with skills for richer embedding
        combined_text = f"{description}\n\nKey Skills: {', '.join(skills)}"
        embedding = await self.generate_embedding(combined_text)

        async with async_session() as session:
            await session.execute(
                text(
                    """
                    UPDATE jobs SET embedding_vec = :embedding
                    WHERE id = :job_id
                    """
                ),
                {"embedding": str(embedding), "job_id": job_id},
            )
            await session.commit()

    async def store_user_profile_embedding(self, profile_text: str) -> list[float]:
        """Generate embedding for user's resume/profile."""
        return await self.generate_embedding(profile_text)

    async def find_similar_jobs(
        self, query_embedding: list[float], limit: int = 20, min_score: float = 0.6
    ) -> list[dict]:
        """Find jobs similar to the query embedding."""
        async with async_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT id, company, title, location, remote,
                           1 - (embedding_vec <=> :query_vec::vector) as similarity
                    FROM jobs
                    WHERE embedding_vec IS NOT NULL
                      AND status = 'new'
                    ORDER BY embedding_vec <=> :query_vec::vector
                    LIMIT :limit
                    """
                ),
                {"query_vec": str(query_embedding), "limit": limit},
            )
            rows = result.fetchall()

            return [
                {
                    "id": str(row.id),
                    "company": row.company,
                    "title": row.title,
                    "location": row.location,
                    "remote": row.remote,
                    "similarity": row.similarity,
                }
                for row in rows
                if row.similarity >= min_score
            ]

    async def find_jobs_matching_skills(
        self, skills: list[str], limit: int = 20
    ) -> list[dict]:
        """Find jobs matching a set of skills."""
        skills_text = ", ".join(skills)
        embedding = await self.generate_embedding(f"Required skills: {skills_text}")
        return await self.find_similar_jobs(embedding, limit=limit)
