from rest_framework import serializers
from typing import Dict, List
import re


# Search Serializer Class
class SearchSerializer(serializers.Serializer):
    search_query = serializers.CharField(
        max_length=500,
        required=True,
        help_text="The search query string for finding relevant resumes",
    )

    from_experience = serializers.IntegerField(
        required=True, min_value=0, help_text="Minimum years of experience required"
    )

    to_experience = serializers.IntegerField(
        required=True, min_value=0, help_text="Maximum years of experience required"
    )

    similarity_threshold = serializers.FloatField(
        required=True,
        min_value=0.0,
        max_value=1.0,
        help_text="Similarity threshold for matching (between 0.0 and 1.0)",
    )

    # Validate
    def validate(self, data):
        """
        Check that from_experience is less than or equal to to_experience
        """
        if data["from_experience"] > data["to_experience"]:
            raise serializers.ValidationError(
                "from_experience must be less than or equal to to_experience"
            )
        return data

    # Validate Search Query
    def validate_search_query(self, value):
        """
        Validate that search_query is not empty or just whitespace
        """
        if not value.strip():
            raise serializers.ValidationError("Search query cannot be empty")
        return value.strip()

    # Parsed Search Query Improved
    def parse_search_query_improved(self, search_query: str) -> Dict[str, List[str]]:
        """
        Improved version of search query parser with better tag detection.

        Args:
            search_query (str): Input string like "skills python, C, C++, role software developer, location India"

        Returns:
            Dict[str, List[str]]: Parsed data like {"skills": ["python", "c", "c++"], "role": ["software developer"]}
        """
        # Define all possible tags
        valid_tags = [
            "name",
            "email",
            "phone number",
            "skills",
            "location",
            "education",
            "role",
        ]

        # Initialize result dictionary
        parsed_data = {}

        # Clean the input string
        search_query = search_query.strip()

        if not search_query:
            return parsed_data

        # Find all tag positions in the string
        tag_positions = []
        search_lower = search_query.lower()

        for tag in valid_tags:
            tag_lower = tag.lower()
            start = 0
            while True:
                pos = search_lower.find(tag_lower, start)
                if pos == -1:
                    break

                # Check if it's a whole word (not part of another word)
                if (pos == 0 or not search_lower[pos - 1].isalnum()) and (
                    pos + len(tag_lower) == len(search_lower)
                    or not search_lower[pos + len(tag_lower)].isalnum()
                ):
                    tag_positions.append((pos, tag_lower, len(tag_lower)))

                start = pos + 1

        # Sort by position
        tag_positions.sort()

        # Extract content for each tag
        for i, (pos, tag, tag_len) in enumerate(tag_positions):
            start_content = pos + tag_len

            # Find end of content (start of next tag or end of string)
            if i + 1 < len(tag_positions):
                end_content = tag_positions[i + 1][0]
            else:
                end_content = len(search_query)

            # Extract content
            content = search_query[start_content:end_content].strip()

            # Remove leading non-alphanumeric characters (like colons, commas)
            content = re.sub(r"^[^\w]+", "", content).strip()

            if content:
                # Split by commas and clean each value
                values = []
                for val in content.split(","):
                    val = val.strip()
                    if val:
                        # Remove any trailing punctuation
                        val = re.sub(r"[^\w\s]+$", "", val).strip()
                        if val:
                            values.append(val.lower())

                if values:
                    parsed_data[tag] = values
        # print(f"Parsed Search Query: {parsed_data}")
        return parsed_data


# Analyse Serializer Class
class AnalyseSerializer(serializers.Serializer):
    resume_path = serializers.CharField(
        max_length=500,
        required=True,
        help_text="The path to the resume file for analysis",
    )
    search_query = serializers.CharField(
        max_length=500,
        required=True,
        help_text="The search query string for finding relevant resumes",
    )

    # Validate Search Query
    def validate_search_query(self, value):
        """
        Validate that search_query is not empty or just whitespace
        """
        if not value.strip():
            raise serializers.ValidationError("Search query cannot be empty")
        return value.strip()

    # Validate Resume Path
    def validate_resumePath(self, value):
        """
        Validate that resumePath is not empty or just whitespace
        """
        if not value.strip():
            raise serializers.ValidationError("Resume path cannot be empty")
        if not value.startswith("https://www.dropbox.com"):
            raise serializers.ValidationError(
                "Only Dropbox shared links are supported."
            )
        return value.strip()
