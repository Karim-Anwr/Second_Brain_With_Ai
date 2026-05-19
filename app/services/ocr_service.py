import pytesseract
import fitz  # PyMuPDF
from PIL import Image
from pathlib import Path

from app.core.exceptions import OCRFailedException, UnsupportedFileTypeException
from app.utils.text_cleaner import clean_text


class OCRService:
    """
    مسؤول عن استخراج النص من الصور والـ PDF.
    
    ليه class وماشيش functions عادية؟
    عشان لو عايزين نضيف إعدادات للـ OCR زي اللغة أو الدقة،
    نحطها في الـ __init__ مرة واحدة بدل ما نكررها في كل function.
    """

    def __init__(self, language: str = "ara+eng"):
        """
        language: اللغات اللي Tesseract هيتعرف عليها
        ara+eng = عربي وإنجليزي مع بعض
        """
        self.language = language



    def extract_text(self, file_path: str, file_type: str) -> str:
        """

        Args:
            file_path: مسار الملف على الـ disk
            file_type: "image" أو "pdf"
        
        Returns:
            النص المستخرج بعد التنظيف
        """
        path = Path(file_path)

        if not path.exists():
            raise OCRFailedException(f"الملف مش موجود: {file_path}")

        if file_type == "image":
            raw_text = self._extract_from_image(path)
        elif file_type == "pdf":
            raw_text = self._extract_from_pdf(path)
        else:
            raise UnsupportedFileTypeException(
                f"نوع الملف '{file_type}' مش مدعوم"
            )

        # نظف النص قبل ما ترجعه
        cleaned = clean_text(raw_text)

        if not cleaned:
            raise OCRFailedException(
                "الـ OCR اشتغل بس ما لقاش نص. "
                "ممكن الصورة تكون غير واضحة."
            )

        return cleaned

 

    def _extract_from_image(self, path: Path) -> str:
        """
        بيستخدم Tesseract عشان يقرأ الصورة.
        
        ليه _ في الأول؟
        عشان نقول للمبرمجين التانيين:
        "الـ method دي داخلية — متستخدمهاش من بره الـ class"
        """
        try:
            image = Image.open(path)

            # Tesseract بياخد الصورة ويرجع نص
            # config: بنقوله يشتغل بدقة عالية (oem=3, psm=3)
            text = pytesseract.image_to_string(
                image,
                lang=self.language,
                config="--oem 3 --psm 3"
            )
            return text

        except Exception as e:
            raise OCRFailedException(
                f"فشل في قراءة الصورة: {str(e)}"
            )

    def _extract_from_pdf(self, path: Path) -> str:
        """
        بيستخدم PyMuPDF عشان يقرأ الـ PDF.
        
        ليه PyMuPDF وماستخدمناش Tesseract للـ PDF؟
        لأن الـ PDF أحياناً بيكون فيه نص جاهز (مش صورة)،
        PyMuPDF بيقدر يجيبه مباشرة أسرع وأدق.
        
        لو الـ PDF كان صورة (scanned)،
        PyMuPDF مش هيلاقي نص — هنتعامل مع ده في Phase 2.
        """
        try:
            full_text = []

            # افتح الـ PDF
            doc = fitz.open(str(path))

            # اقرأ كل صفحة لوحدها
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    full_text.append(text)

            doc.close()

            return "\n".join(full_text)

        except Exception as e:
            raise OCRFailedException(
                f"فشل في قراءة الـ PDF: {str(e)}"
            )


# ============================================================
# Singleton — instance واحد بس للـ app كلها
# ============================================================
ocr_service = OCRService(language="ara+eng")