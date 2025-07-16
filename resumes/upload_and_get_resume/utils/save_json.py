import json
import re

# Parse Response to Json
def parse_response_to_json(response_text):
    """
    Parse the structured response text and convert it to JSON format
    """
    try:
        # Initialize the JSON structure
        candidate_data = {
            "candidate_profile": {},
            "education": [],
            "skills": [],
            "languages": [],
            "projects": [],
            "achivements": [],
            "suitable_roles": [],
            "links": [],
            "detailed_analysis": {},
        }
        years_of_experience = ""
        # Split response by sections
        sections = response_text.split("=== ")

        for section in sections:
            if not section.strip():
                continue

            lines = section.strip().split("\n")
            section_title = lines[0].replace("===", "").strip().upper()

            if section_title == "CANDIDATE PROFILE":
                # Parse candidate profile
                for line in lines[1:]:
                    if ":" in line:
                        key, value = line.split(":", 1)
                        key = key.strip().lower().replace("/", "_").replace(" ", "_")

                        if key == "years_of_experience":
                            # years_of_experience = value
                            match = re.search(r'\d+(\.\d+)?', value)
                            years_of_experience = float(match.group()) if match else 0

                        value = value.strip()

                        candidate_data["candidate_profile"][key] = value

            elif section_title == "EDUCATION":
                # Parse education as list
                education_text = "\n".join(lines[1:]).strip()
                if education_text and education_text != "N/A":
                    candidate_data["education"] = [
                        edu.strip() for edu in education_text.split("\n") if edu.strip()
                    ]

            elif section_title == "SKILLS":
                # Parse skills as list and handle \n characters
                skills_text = "\n".join(lines[1:]).strip()
                if skills_text and skills_text != "N/A":
                    # Replace literal \n with actual newlines and split properly
                    skills_text = skills_text.replace("\\n", "\n")
                    # Split by newlines first, then by commas within each line
                    all_skills = []
                    for skill_line in skills_text.split("\n"):
                        if skill_line.strip():
                            # Check if line contains comma-separated skills
                            if "," in skill_line and not skill_line.startswith("-"):
                                # Split by comma
                                skills_in_line = [
                                    s.strip()
                                    for s in skill_line.split(",")
                                    if s.strip()
                                ]
                                all_skills.extend(skills_in_line)
                            else:
                                # Add as single skill
                                all_skills.append(skill_line.strip())
                    candidate_data["skills"] = all_skills

            elif section_title == "LANGUAGES":

                # Parse Languages as list and handle \n characters
                languages_text = "\n".join(lines[1:]).strip()
                if languages_text and languages_text != "N/A":
                    # Replace literal \n with actual newlines and split properly
                    languages_text = languages_text.replace("\\n", "\n")
                    # Split by newlines first, then by commas within each line
                    all_languages = []
                    for language_line in languages_text.split("\n"):
                        if language_line.strip():
                            # Check if line contains comma-separated languages
                            if "," in language_line and not language_line.startswith(
                                "-"
                            ):
                                # Split by comma
                                languages_in_line = [
                                    s.strip()
                                    for s in language_line.split(",")
                                    if s.strip()
                                ]
                                all_languages.extend(languages_in_line)
                            else:
                                # Add as single language
                                all_languages.append(language_line.strip())
                    candidate_data["languages"] = all_languages

            elif section_title == "PROJECTS":
                # Parse projects as list
                projects_text = "\n".join(lines[1:]).strip()
                if projects_text and projects_text != "N/A":
                    candidate_data["projects"] = [
                        project.strip()
                        for project in projects_text.split("\n")
                        if project.strip()
                    ]

            elif section_title == "ACHIVEMENTS":

                # Parse Achivements as list and handle \n characters
                achivements_text = "\n".join(lines[1:]).strip()
                if achivements_text and achivements_text != "N/A":
                    # Replace literal \n with actual newlines and split properly
                    achivements_text = achivements_text.replace("\\n", "\n")
                    # Split by newlines first, then by commas within each line
                    all_achivements = []
                    for achivement_line in achivements_text.split("\n"):
                        if achivement_line.strip():
                            # Check if line contains comma-separated achivement
                            if (
                                "," in achivement_line
                                and not achivement_line.startswith("-")
                            ):
                                # Split by comma
                                achivements_in_line = [
                                    s.strip()
                                    for s in achivement_line.split(",")
                                    if s.strip()
                                ]
                                all_achivements.extend(achivements_in_line)
                            else:
                                # Add as single achivements
                                all_achivements.append(achivement_line.strip())
                    candidate_data["achivements"] = all_achivements

            elif section_title == "SUITABLE ROLES":
                # Parse suitable roles as list
                roles_text = "\n".join(lines[1:]).strip()
                if roles_text and roles_text != "N/A":
                    if "," in roles_text:
                        candidate_data["suitable_roles"] = [
                            role.strip()
                            for role in roles_text.split(",")
                            if role.strip()
                        ]
                    else:
                        candidate_data["suitable_roles"] = [
                            role.strip()
                            for role in roles_text.split("\n")
                            if role.strip()
                        ]

            elif section_title == "LINKS":
                # Parse links as list of dictionaries
                links_text = "\n".join(lines[1:]).strip()
                if links_text and links_text != "N/A":
                    for link_line in links_text.split("\n"):
                        if ":" in link_line and link_line.strip():
                            title, url = link_line.split(":", 1)
                            candidate_data["links"].append(
                                {"title": title.strip(), "url": url.strip()}
                            )

            elif section_title == "DETAILED ANALYSIS":
                # Parse detailed analysis subsections and handle \n characters
                current_subsection = None
                current_content = []

                for line in lines[1:]:
                    if line.startswith("**") or line.endswith("**"):
                        # Save previous subsection if exists
                        if current_subsection:
                            content_text = "\n".join(current_content).strip()
                            # Replace literal \n with actual newlines
                            content_text = content_text.replace("\\n", "\n")
                            candidate_data["detailed_analysis"][
                                current_subsection
                            ] = content_text

                        # Start new subsection - remove colon from key name
                        subsection_name = (
                            line.replace("**", "")
                            .strip()
                            .lower()
                            .replace(" ", "_")
                            .replace("/", "_")
                        )
                        # Remove trailing colon if present
                        if subsection_name.endswith(":"):
                            subsection_name = subsection_name[:-1]
                        current_subsection = subsection_name
                        current_content = []
                    else:
                        current_content.append(line)

                # Save last subsection
                if current_subsection and current_content:
                    content_text = "\n".join(current_content).strip()
                    # Replace literal \n with actual newlines
                    content_text = content_text.replace("\\n", "\n")
                    candidate_data["detailed_analysis"][
                        current_subsection
                    ] = content_text

        return candidate_data, years_of_experience

    except Exception as e:
        print(f"[ERROR] Failed to parse response to JSON: {e}")
        return {
            "error": f"Failed to parse response: {str(e)}",
            "raw_response": response_text,
        }

# Clean and formats Json
def clean_and_format_json(candidate_data):
    """
    Clean and format the JSON data for better readability
    """
    try:
        # Clean skills section
        if candidate_data.get("skills"):
            cleaned_skills = []
            for skill in candidate_data["skills"]:
                # Remove leading dashes and clean up
                skill = skill.strip()
                if skill.startswith("-"):
                    skill = skill[1:].strip()
                if skill:
                    cleaned_skills.append(skill)
            candidate_data["skills"] = cleaned_skills

        # Clean projects section
        if candidate_data.get("projects"):
            cleaned_projects = []
            for project in candidate_data["projects"]:
                # Remove leading dashes and clean up
                project = project.strip()
                if project.startswith("-"):
                    project = project[1:].strip()
                if project:
                    cleaned_projects.append(project)
            candidate_data["projects"] = cleaned_projects

        # Clean suitable roles section
        if candidate_data.get("suitable_roles"):
            cleaned_roles = []
            for role in candidate_data["suitable_roles"]:
                # Remove leading dashes and clean up
                role = role.strip()
                if role.startswith("-"):
                    role = role[1:].strip()
                if role:
                    cleaned_roles.append(role)
            candidate_data["suitable_roles"] = cleaned_roles

        # Clean education section
        if candidate_data.get("education"):
            cleaned_education = []
            for edu in candidate_data["education"]:
                # Remove leading dashes and clean up
                edu = edu.strip()
                if edu.startswith("-"):
                    edu = edu[1:].strip()
                if edu:
                    cleaned_education.append(edu)
            candidate_data["education"] = cleaned_education

        # Clean links section
        if candidate_data.get("links"):
            for link in candidate_data["links"]:
                if link.get("title") and link["title"].startswith("-"):
                    link["title"] = link["title"][1:].strip()

        # Clean detailed analysis section - remove extra colons from keys
        if candidate_data.get("detailed_analysis"):
            cleaned_analysis = {}
            for key, value in candidate_data["detailed_analysis"].items():
                # Remove trailing colon from key
                clean_key = key.rstrip(":")
                cleaned_analysis[clean_key] = value
            candidate_data["detailed_analysis"] = cleaned_analysis

        return candidate_data

    except Exception as e:
        print(f"[ERROR] Failed to clean JSON data: {e}")
        return candidate_data

# Save analysis to Json
def save_analysis_to_json(analysis_data, output_file_path):
    """
    Save the analysis data to a JSON file
    """
    try:
        # Clean the data before saving
        cleaned_data = clean_and_format_json(analysis_data)

        with open(output_file_path, "w", encoding="utf-8") as f:
            json.dump(cleaned_data, f, indent=2, ensure_ascii=False)
        print(f"[SUCCESS] Analysis saved to {output_file_path}")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to save JSON file: {e}")
        return False
