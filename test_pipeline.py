from app.pipelines.ingest_pipeline import ingest_pipeline

result = ingest_pipeline.process(
    file_path="/mnt/d/Second_Brain_App/test.jpg",
    file_name="test.jpg",
    file_type="image",
)

print("\n📊 النتيجة:")
print(f"Memory ID:  {result.memory_id}")
print(f"Summary:    {result.summary}")
print(f"Tags:       {result.tags}")
print(f"Category:   {result.category}")
print(f"Importance: {result.importance}")
print(f"Chunks:     {result.total_chunks}")
print(f"Status:     {result.status}")