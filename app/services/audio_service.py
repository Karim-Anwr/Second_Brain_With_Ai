import os
import uuid
from pathlib import Path
import yt_dlp
from faster_whisper import WhisperModel
from app.core.exceptions import SecondBrainException


MAX_DURATION_SECONDS = 15 * 60  # حد أقصى 15 دقيقة


class AudioProcessingException(SecondBrainException):
    pass


class AudioService:
    """
    مسؤول عن تنزيل الصوت من لينكات الفيديو وتحويله لنص.
    
    بيحمل الصوت بس (مش الفيديو كامل) —
    """

    def __init__(self):
        self.temp_dir = Path("storage/temp_audio")
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        self.model = None  # lazy loading

    def _get_model(self) -> WhisperModel:
        if self.model is None:
            print("   🎙️  جاري تحميل موديل Whisper...")
            self.model = WhisperModel(
                "small",
                device="cpu",
                compute_type="int8",  # أخف وأسرع على CPU
            )
            print("    موديل Whisper جاهز")
        return self.model

    def check_duration(self, url: str) -> dict:
        """
        بيتأكد من مدة الفيديو قبل ما يحمله.
        لو طويل جداً، يرفض بدري قبل ما يضيع وقت.
        """
        try:
            opts = {"quiet": True, "no_warnings": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
                duration = info.get("duration", 0) or 0

            if duration > MAX_DURATION_SECONDS:
                return {
                    "allowed":  False,
                    "duration": duration,
                    "reason": (
                        f"الفيديو طويل ({duration // 60} دقيقة). "
                        f"الحد الأقصى المسموح {MAX_DURATION_SECONDS // 60} دقيقة."
                    ),
                }

            return {"allowed": True, "duration": duration}

        except Exception as e:
            return {
                "allowed":  False,
                "duration": 0,
                "reason":   f"مقدرناش نقرأ معلومات الفيديو: {e}",
            }

    def download_audio(self, url: str) -> str:
        """
        بيحمل الصوت بس من الفيديو (مش الفيديو كامل).
        بيرجع مسار ملف الصوت المؤقت.
        """
        file_id   = uuid.uuid4().hex[:10]
        out_path  = str(self.temp_dir / f"{file_id}.%(ext)s")

        opts = {
            "format": "bestaudio/best",
            "outtmpl": out_path,
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "mp3",
                "preferredquality": "128",
            }],
            "quiet": True,
            "no_warnings": True,
        }

        try:
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([url])

            final_path = str(self.temp_dir / f"{file_id}.mp3")
            if not os.path.exists(final_path):
                raise AudioProcessingException("فشل تحميل الصوت")

            return final_path

        except Exception as e:
            raise AudioProcessingException(f"فشل تحميل الصوت: {e}")

    def transcribe(self, audio_path: str) -> dict:
        """
        بيحول الصوت لنص باستخدام faster-whisper.
        """
        model = self._get_model()

        try:
            segments, info = model.transcribe(
                audio_path,
                beam_size=5,
                vad_filter=True,  # بيشيل فترات الصمت — أسرع وأدق
            )

            full_text = " ".join(seg.text.strip() for seg in segments)

            return {
                "text":     full_text.strip(),
                "language": info.language,
                "duration": info.duration,
            }

        except Exception as e:
            raise AudioProcessingException(f"فشل تحويل الصوت لنص: {e}")

    def process_video_audio(self, url: str) -> dict:
        """
        النقطة الرئيسية — من اللينك لحد النص الكامل.
        بتنضف ملف الصوت المؤقت في الآخر مهما حصل.
        """
        duration_check = self.check_duration(url)
        if not duration_check["allowed"]:
            raise AudioProcessingException(duration_check["reason"])

        audio_path = None
        try:
            print("   ⬇  تحميل الصوت...")
            audio_path = self.download_audio(url)

            print("     تحويل الصوت لنص...")
            result = self.transcribe(audio_path)
            print(f"    {len(result['text'].split())} كلمة مستخرجة")

            return result

        finally:
            if audio_path and os.path.exists(audio_path):
                os.remove(audio_path)


# Singleton
audio_service = AudioService()