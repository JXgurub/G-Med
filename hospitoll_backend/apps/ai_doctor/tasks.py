from celery import shared_task
import logging
from .models import AnalysisResult
from .services import NonAnalysisContentError, analyze_lab_image_uzbek

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=2)
def analyze_image_task(self, analysis_id: str):
    analysis = AnalysisResult.objects.filter(id=analysis_id).first()
    if not analysis:
        return {"status": "not_found", "analysis_id": str(analysis_id)}

    try:
        analysis.status = "pending"
        analysis.save(update_fields=["status", "updated_at"])

        with analysis.file.open("rb") as f:
            file_bytes = f.read()

        result_text = analyze_lab_image_uzbek(file_bytes, analysis.file_type)
        analysis.result_text = result_text
        analysis.status = "completed"
        analysis.save(update_fields=["result_text", "status", "updated_at"])
        return {"status": "completed", "analysis_id": str(analysis.id)}
    except NonAnalysisContentError as exc:
        analysis.result_text = str(exc)
        analysis.status = "failed"
        analysis.save(update_fields=["result_text", "status", "updated_at"])
        return {"status": "failed", "analysis_id": str(analysis.id), "reason": "not_analysis"}
    except Exception as exc:
        logger.exception("Error analyzing image for %s: %s", analysis_id, exc)
        if self.request.retries < self.max_retries:
            raise self.retry(exc=exc, countdown=2 ** self.request.retries)

        analysis.result_text = f"Tahlilda xatolik yuz berdi: {exc}"
        analysis.status = "failed"
        analysis.save(update_fields=["result_text", "status", "updated_at"])
        return {"status": "failed", "analysis_id": str(analysis.id)}
