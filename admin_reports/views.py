from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response

from quizzes.models import QuizReport
import csv, io
from django.http import HttpResponse

@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_reports(request):
    """
    GET /api/admin/reports/           -> JSON list of reports
    GET /api/admin/reports/?format=csv -> CSV export download
    """
    export_format = request.GET.get("format", "json")

    qs = (
        QuizReport.objects
        .select_related("quiz", "user")
        .all()
        .order_by("-created_at")
    )

    reports = [
        {
            "id": r.id,
            "quiz_title": r.quiz.title if r.quiz else "",
            "reported_by_email": r.user.email if r.user else "",
            "reason": r.reason,
            "created_at": r.created_at.isoformat(),
        }
        for r in qs
    ]

    if export_format == "csv":
        output = io.StringIO()
        fieldnames = ["id", "quiz_title", "reported_by_email", "reason", "created_at"]
        writer = csv.DictWriter(output, fieldnames=fieldnames)
        writer.writeheader()
        for row in reports:
            writer.writerow(row)

        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="reports.csv"'
        return response

    return Response(reports, status=status.HTTP_200_OK)
