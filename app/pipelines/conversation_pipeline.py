from urllib import request

from app.models.conversation import (
    ChatRequest, ChatResponse, MessageRole
)
from app.services.session_service import session_service
from app.services.conversation_service import conversation_service
from app.services.llm_service import llm_service
from app.core.exceptions import StorageCorruptionException, StorageException
from app.pipelines.context_builder import context_builder
from app.utils.arabic_normalizer import arabic_normalizer


class ConversationPipeline:
    """
    الـ pipeline الكامل للمحادثة.
    
    Flow:
    1. جيب أو اعمل session
    2. احفظ رسالة المستخدم
    3. ابني الـ context
    4. جنّر الرد
    5. احفظ الرد
    6. استخرج ذكريات
    7. رجّع الرد
    """

    def chat(self, request: ChatRequest) -> ChatResponse:
        """
        النقطة الرئيسية — بتاخد request وبترجع response.
        """
        print(f"\n محادثة جديدة: '{request.message[:50]}'")

        # ════════════════════════════════
        # Step 1: جيب أو اعمل Session
        # ════════════════════════════════
        if request.session_id:
            session = session_service.get_session(request.session_id)
        else:
            session = session_service.create_session()

        session_id = session.id
        print(f"    Session: {session_id}")

        # ════════════════════════════════
        # Step 2: Normalize + احفظ رسالة المستخدم
        # ════════════════════════════════
        normalized_query = arabic_normalizer.normalize_query(
            request.message
        )

        user_message = session_service.add_message(
            session_id=session_id,
            role=MessageRole.USER,
            content=request.message,
        )
        print(f"    رسالة المستخدم اتحفظت")
        # ════════════════════════════════
        # Step 2.5: كشف نية الحفظ الصريحة   ← هنا بالظبط
        # ════════════════════════════════
        save_intent = llm_service.detect_save_intent(request.message)
        saved_memory_id = None

        if save_intent.get("wants_to_save") and save_intent.get("confidence", 0) > 0.6:
            content = save_intent.get("content_to_save") or request.message
            try:
                saved_memory_id = conversation_service.save_as_memory(
                    session_id=session_id,
                    content=content,
                )
                print(f"    المستخدم طلب حفظ — اتحفظ في ChromaDB")
            except Exception:
                # Saving is optional: it must not turn a normal chat turn into a raw 500.
                print("    تعذر حفظ الذاكرة المطلوبة، نكمل المحادثة بشكل طبيعي")
        # ════════════════════════════════
        # Step 3: ابني الـ Context
        # ════════════════════════════════
        context_data = context_builder.build(
            session_id=session_id,
            user_query=normalized_query,
        )

        context       = context_data["context"]
        memory_ids    = context_data["memory_ids_used"]
        print(f"    Context جاهز")

        # ════════════════════════════════
        # Step 4: جنّر الرد
        # ════════════════════════════════
        print(" بيجنّر الرد...")
        system_prompt = context_builder.build_system_prompt()

        save_note = ""
        if saved_memory_id:
            save_note = "\n\n(لاحظ: المستخدم طلب حفظ معلومة، وتم حفظها بنجاح. أكّد له ذلك في ردك بشكل طبيعي.)"

        full_prompt = f"""{system_prompt}

        {context}{save_note}

        اكتب رد طبيعي ومفيد للمستخدم."""

        try:
            answer = llm_service._call(full_prompt, fast=False)
        except Exception as e:
            answer = f" حصل خطأ، جرب تاني: {str(e)}"

        print(f"    الرد جاهز")

        # ════════════════════════════════
        # Step 5: احفظ رد المساعد
        # ════════════════════════════════
        assistant_message = session_service.add_message(
            session_id=session_id,
            role=MessageRole.ASSISTANT,
            content=answer,
            memory_ids=memory_ids,
        )

        # ════════════════════════════════
        # Step 6: استخرج ذكريات
        # ════════════════════════════════
        print(" استخراج ذكريات...")
        try:
            extracted = conversation_service.process_and_extract(
                session_id=session_id,
                user_message=request.message,
                assistant_response=answer,
            )
        except (StorageCorruptionException, StorageException):
            # The assistant turn is already durable; keep a corrupt sidecar untouched and return the turn normally.
            print("    تعذر حفظ الذكريات المستخرجة، نكمل الرد بدون تعديل البيانات الحالية")
            extracted = []
        print(f"    {len(extracted)} ذكرى مستخرجة")

        # ════════════════════════════════
        # Step 7: Session Summary كل 20 رسالة
        # ════════════════════════════════
        if session.total_messages % 20 == 0:
            print(" بيعمل session summary...")
            conversation_service.summarize_session(session_id)

        # ════════════════════════════════
        # Step 8: رجّع الرد
        # ════════════════════════════════
        return ChatResponse(
            session_id=session_id,
            message_id=assistant_message.id,
            answer=answer,
            memories_used=memory_ids,
            new_memories=len(extracted) + (1 if saved_memory_id else 0),
)


# Singleton
conversation_pipeline = ConversationPipeline()
