import re
import unicodedata


class ArabicNormalizer:
    """
    بينظف ويوحد النص العربي قبل الـ embedding.
    
    ليه مهم؟
    "مكتبة" و"مكتبه" و"مكتبةً" كلهم نفس الكلمة
    بس الـ embedding بيشوفهم مختلفين!
    الـ normalizer بيخليهم كلهم "مكتبه" واحدة.
    """

    # حروف التشكيل
    TASHKEEL = re.compile(r'[\u0610-\u061A\u064B-\u065F\u0670]')

    # التطويل
    TATWEEL = re.compile(r'\u0640+')

    # spaces متعددة
    MULTI_SPACE = re.compile(r'\s+')

    # OCR garbage — رموز مش منطقية
    OCR_GARBAGE = re.compile(
        r'[^\w\s\u0600-\u06FF\u0750-\u077F.,!?;:()\-\'\"/\\@#%&*+<>=\[\]{}]'
    )

    def normalize(self, text: str) -> str:
        """
        بيطبق كل التحسينات على النص.
        """
        if not text:
            return ""

        # 1. شيل التشكيل
        text = self.TASHKEEL.sub('', text)

        # 2. شيل التطويل
        text = self.TATWEEL.sub('', text)

        # 3. وحّد الألف
        text = re.sub(r'[إأآا]', 'ا', text)

        # 4. وحّد الياء
        text = re.sub(r'[يى]', 'ي', text)

        # 5. وحّد التاء المربوطة
        text = re.sub(r'ة', 'ه', text)

        # 6. وحّد الهمزة
        text = re.sub(r'[ؤئ]', 'ء', text)

        # 7. شيل OCR garbage
        text = self.OCR_GARBAGE.sub(' ', text)

        # 8. شيل spaces زيادة
        text = self.MULTI_SPACE.sub(' ', text)

        return text.strip()

    def normalize_query(self, query: str) -> str:
        """
        بينظف السؤال بتاع المستخدم.
        نفس الـ normalize بس بيحتفظ بعلامات الاستفهام.
        """
        return self.normalize(query)

    def is_arabic(self, text: str) -> bool:
        arabic = sum(1 for c in text if '\u0600' <= c <= '\u06FF')
        return arabic > len(text) * 0.3

    def clean_ocr_text(self, text: str) -> str:
        """
        تنظيف متخصص لنص الـ OCR.
        بيشيل الـ artifacts الشائعة.
        """
        # شيل أسطر فاضية كتير
        text = re.sub(r'\n{3,}', '\n\n', text)

        # شيل أحرف منفردة مش منطقية
        text = re.sub(r'\b[a-zA-Z]\b', '', text)

        # شيل أرقام الصفحات المنفردة
        text = re.sub(r'^\d+$', '', text, flags=re.MULTILINE)

        # normalize
        text = self.normalize(text)

        return text


# Singleton
arabic_normalizer = ArabicNormalizer()