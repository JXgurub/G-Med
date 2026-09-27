import os
from django.conf import settings
from django.shortcuts import get_object_or_404
from rest_framework import status, permissions
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.response import Response
from rest_framework.views import APIView
from .models import AnalysisResult
from .serializers import AnalysisUploadSerializer, AnalysisResultSerializer
from .tasks import analyze_image_task
from .services import analyze_lab_image_uzbek, NonAnalysisContentError

_EXT_TO_TYPE = {
    "jpg": "image", "jpeg": "image", "png": "image", "gif": "image",
    "webp": "image", "bmp": "image", "tiff": "image",
    "pdf": "pdf",
    "xlsx": "excel", "xls": "excel",
    "docx": "word", "doc": "word",
    "html": "html", "htm": "html",
}


class AnalysisUploadView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_analysis_upload'

    def post(self, request, *args, **kwargs):
        if not settings.GEMINI_API_KEY:
            return Response(
                {'detail': 'AI tahlil xizmati hozircha sozlanmagan.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        serializer = AnalysisUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        uploaded_file = serializer.validated_data["file"]
        session_key = serializer.validated_data.get("session_key", "")
        user = request.user if request.user.is_authenticated else None
        if not user and not session_key:
            return Response(
                {'detail': 'Mehmon tahlili uchun session key kerak.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        _, ext = os.path.splitext(uploaded_file.name)
        file_type = _EXT_TO_TYPE.get(ext.lower().lstrip("."), "image")

        analysis = AnalysisResult.objects.create(
            user=user,
            session_key=session_key,
            file=uploaded_file,
            file_type=file_type,
            status="pending",
            language="uz",
        )

        async_task = False
        job_id = None
        try:
            job = analyze_image_task.delay(str(analysis.id))
            job_id = job.id
            async_task = True
        except Exception:
            # Fallback to sync execution if Celery worker is unreachable
            try:
                with analysis.file.open("rb") as f:
                    file_bytes = f.read()
                result_text = analyze_lab_image_uzbek(file_bytes, analysis.file_type)
                analysis.result_text = result_text
                analysis.status = "completed"
                analysis.save(update_fields=["result_text", "status", "updated_at"])
            except NonAnalysisContentError as exc:
                analysis.result_text = str(exc)
                analysis.status = "failed"
                analysis.save(update_fields=["result_text", "status", "updated_at"])
            except Exception as exc:
                analysis.result_text = f"Tahlilda xatolik yuz berdi: {exc}"
                analysis.status = "failed"
                analysis.save(update_fields=["result_text", "status", "updated_at"])

        output = AnalysisResultSerializer(analysis, context={"request": request})
        return Response(
            {
                "job_id": job_id,
                "analysis": output.data,
                "async": async_task,
                "message": "Tahlil navbatga qo'yildi." if async_task else "Tahlil yakunlandi.",
            },
            status=status.HTTP_202_ACCEPTED if async_task else status.HTTP_200_OK,
        )


class AnalysisListView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_analysis_read'

    def get(self, request, *args, **kwargs):
        session_key = request.query_params.get("session_key", "")
        if request.user.is_authenticated:
            queryset = AnalysisResult.objects.filter(user=request.user)
        elif session_key:
            queryset = AnalysisResult.objects.filter(session_key=session_key)
        else:
            queryset = AnalysisResult.objects.none()

        queryset = queryset.order_by("-created_at")[:20]
        serializer = AnalysisResultSerializer(queryset, many=True, context={"request": request})
        return Response(serializer.data)


class AnalysisDetailView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = 'ai_analysis_read'

    def get(self, request, pk, *args, **kwargs):
        session_key = request.query_params.get("session_key", "")
        if request.user.is_authenticated:
            analysis = get_object_or_404(AnalysisResult, pk=pk, user=request.user)
        elif session_key:
            analysis = get_object_or_404(AnalysisResult, pk=pk, session_key=session_key)
        else:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        serializer = AnalysisResultSerializer(analysis, context={"request": request})
        return Response(serializer.data)

    def delete(self, request, pk, *args, **kwargs):
        session_key = request.query_params.get("session_key", "")
        if request.user.is_authenticated:
            analysis = get_object_or_404(AnalysisResult, pk=pk, user=request.user)
        elif session_key:
            analysis = get_object_or_404(AnalysisResult, pk=pk, session_key=session_key)
        else:
            return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)

        analysis.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
