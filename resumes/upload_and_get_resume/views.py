# view.py
"""
REST APIs that handles Upload, Search and analysis of resumes.
"""
import tempfile
import os
import asyncio
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.parsers import MultiPartParser
from upload_and_get_resume.processes.extract_keys import extract_keys
from upload_and_get_resume.processes.search_resume import search_resume
from upload_and_get_resume.processes.analyse_resume import analyse_resume
from .serializer import SearchSerializer, AnalyseSerializer


# Upload PDF API view Class
class UploadPDFView(APIView):
    """
    Handles REST API post request to process and upload resumes to dropbox
    """

    parser_classes = [MultiPartParser]

    # POST request
    def post(self, request, *args, **kwargs):
        pdf_file = request.FILES.get("file")
        if not pdf_file:
            return Response(
                {"error": "No file provided"}, status=status.HTTP_400_BAD_REQUEST
            )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            for chunk in pdf_file.chunks():
                temp_file.write(chunk)
            print(f"Saved file to temporary path: {temp_file.name}")
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        response = loop.run_until_complete(extract_keys(temp_file.name))
        os.remove(temp_file.name)

        return Response(response, status=status.HTTP_200_OK)


# Search Resume API View Class
class SearchResumeView(APIView):
    """
    Handles REST APIs Post resquest to search resumes and gets relevent candidates based on the user's search.
    """

    # POST request
    def post(self, request, *args, **kwargs):
        try:
            data = request.data
            if not data:
                return Response(
                    {"error": "No data provided"}, status=status.HTTP_400_BAD_REQUEST
                )

            # print(f"Received data: {data}")

            # Serialise Data
            serializer = SearchSerializer(data=data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

            # Get validated data
            validated_data = serializer.validated_data
            search_query = validated_data["search_query"]
            
            search_query = serializer.parse_search_query_improved(search_query)
            from_experience = validated_data["from_experience"]
            to_experience = validated_data["to_experience"]
            similarity_threshold = validated_data["similarity_threshold"]
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            # Searches Resumes based on the User Input.
            response = loop.run_until_complete(
                search_resume(
                    search_query, from_experience, to_experience, similarity_threshold
                )
            )

            return Response(response, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Error occurred: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


# Analyse Resume API View
class AnalyseResumeView(APIView):
    """
    Handles REST APIs Post resquest to Analyse resumes and return analysed resume's Path(drop box URL) Shareable format.
    """

    # POST request
    def post(self, request, *args, **kwargs):
        try:
            # Call the analysis function with the resumePath
            data = request.data
            
            if not data:
                return Response(
                    {"error": "No data provided"}, status=status.HTTP_400_BAD_REQUEST
                )

            # Serialise data
            serializer = AnalyseSerializer(data=data)
            if not serializer.is_valid():
                return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
            validated_data = serializer.validated_data

            resume_path = validated_data["resume_path"]
            search_query = validated_data["search_query"]

            output_pdf_path = tempfile.NamedTemporaryFile(delete=False, suffix=".pdf")

            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            # Analyse Resume
            response = loop.run_until_complete(
                analyse_resume(resume_path, search_query, output_pdf_path.name)
            )

            response = {
                "analysed_resume_link": response,
            }
            return Response(response, status=status.HTTP_200_OK)

        except Exception as e:
            print(f"Error occurred: {e}")
            return Response(
                {"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
