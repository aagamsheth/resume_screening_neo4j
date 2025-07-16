from django.urls import path
from .views import UploadPDFView , SearchResumeView , AnalyseResumeView

urlpatterns = [
    path('upload/', UploadPDFView.as_view(), name='upload-pdf'),
    path('search/', SearchResumeView.as_view(), name='search-resume'),
    path('analyse/', AnalyseResumeView.as_view(), name='analyse-resume'),
]