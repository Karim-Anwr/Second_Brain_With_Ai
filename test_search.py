from app.pipelines.search_pipeline import search_pipeline

# ابحث عن حاجة
result = search_pipeline.search(
    query="كان فى حديث صوره لمحمد صلاح وهو شايل كاس",
    top_k=3,
)

print(f"\n🔍 نتائج البحث عن: '{result['query']}'")
print(f"عدد النتائج: {result['total']}")

for i, memory in enumerate(result["results"]):
    print(f"""
نتيجة {i+1}:
  الملف:      {memory.file_name}
  الملخص:     {memory.summary[:100]}...
  Tags:       {memory.tags}
  Score:      {memory.final_score}
  Semantic:   {memory.semantic_score}
  Recency:    {memory.recency_score}
  Importance: {memory.importance_score}
""")