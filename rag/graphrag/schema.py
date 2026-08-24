"""Neo4j schema — constraints, indexes, vector index."""

SCHEMA_QUERIES = [
    # Uniqueness constraints
    "CREATE CONSTRAINT topic_id IF NOT EXISTS FOR (t:Topic) REQUIRE t.id IS UNIQUE",
    "CREATE CONSTRAINT entity_id IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
    "CREATE CONSTRAINT source_id IF NOT EXISTS FOR (s:Source) REQUIRE s.id IS UNIQUE",
    "CREATE CONSTRAINT document_id IF NOT EXISTS FOR (d:Document) REQUIRE d.id IS UNIQUE",
    "CREATE CONSTRAINT digest_date IF NOT EXISTS FOR (d:DailyDigest) REQUIRE d.date IS UNIQUE",
    "CREATE CONSTRAINT observation_id IF NOT EXISTS FOR (o:Observation) REQUIRE o.id IS UNIQUE",
    "CREATE CONSTRAINT content_id IF NOT EXISTS FOR (c:Content) REQUIRE c.id IS UNIQUE",
    "CREATE CONSTRAINT category_id IF NOT EXISTS FOR (c:Category) REQUIRE c.id IS UNIQUE",

    # Full-text index for Entity hybrid search
    "CREATE FULLTEXT INDEX entity_search IF NOT EXISTS FOR (e:Entity) ON EACH [e.name, e.description]",

    # Full-text index for Topic name lookup (G-2: replaces toLower() CONTAINS pattern)
    "CREATE FULLTEXT INDEX topic_search IF NOT EXISTS FOR (t:Topic) ON EACH [t.name]",

    # Markdown reports are browse projections, not GraphRAG evidence. Remove
    # payloads left by pre-ATR versions while keeping navigation metadata.
    "MATCH (d:Document) REMOVE d.content",

    # Vector index for chunk embeddings (1536 dims for text-embedding-3-small)
    """CREATE VECTOR INDEX chunk_embeddings IF NOT EXISTS
       FOR (c:Chunk) ON (c.embedding)
       OPTIONS {indexConfig: {
         `vector.dimensions`: 1536,
         `vector.similarity_function`: 'cosine'
       }}""",
]


async def init_schema(driver) -> None:
    """Create all constraints and indexes. Safe to call multiple times."""
    for query in SCHEMA_QUERIES:
        try:
            await driver.execute_write(query)
        except Exception as e:
            if "already exists" not in str(e).lower():
                raise
