from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from quizzes.models import QuizReport
import csv, io, json
from django.http import HttpResponse

@api_view(["GET"])
@permission_classes([IsAdminUser])
def admin_reports(request):
    export_format = request.GET.get("format", "json")

    reports = QuizReport.objects.all().values("id", "quiz__title", "reported_by__email", "reason", "created_at")

    if export_format == "csv":
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=reports[0].keys())
        writer.writeheader()
        writer.writerows(reports)
        response = HttpResponse(output.getvalue(), content_type="text/csv")
        response["Content-Disposition"] = 'attachment; filename="reports.csv"'
        return response

    return Response(list(reports))
