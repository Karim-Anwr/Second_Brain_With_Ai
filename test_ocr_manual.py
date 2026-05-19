from app.services.ocr_service import ocr_service

result = ocr_service.extract_text(
    file_path="/mnt/d/Second_Brain_App/test.jpg",
    file_type="image"
)
print("النص المستخرج:")
print(result)
print(f"\nعدد الكلمات: {len(result.split())}")