# upload to dropbox
import re
import dropbox
from dropbox.files import WriteMode
import json
from dotenv import load_dotenv
import asyncio
import os
load_dotenv()


DROPBOX_ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN")
if not DROPBOX_ACCESS_TOKEN:
    raise ValueError("DROPBOX_ACCESS_TOKEN is not set in the environment variables.")
dbx = dropbox.Dropbox(DROPBOX_ACCESS_TOKEN)


# Sanitize Filename
def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)
        

# Get Unique Dropbox Path
def get_unique_dropbox_path(folder_path: str, base_name: str, extension: str):
    """
    Gets Unique path for Resume and Json file by checking if candidate with same name exists.
    """
    i = 0
    while True:
        file_name = f"{base_name}_{i}.{extension}"
        dropbox_path = f"/{folder_path}/{file_name}"

        try:
            dbx.files_get_metadata(dropbox_path)
            i += 1
        except dropbox.exceptions.ApiError as e:
            if isinstance(e.error, dropbox.files.GetMetadataError) and e.error.is_path() and e.error.get_path().is_not_found():
                return dropbox_path, file_name, i
            else:
                raise e
# Save To DropBox
async def save_to_dropbox(resume_path: str, json_data: dict, candidate_name: str):
    """
    Saves the resume and Json to Dropbox
    """
    try:
        resume_folder = "output_resumes"
        json_folder = "analysis_json"

        # Ensure sanitized name
        base_name = sanitize_filename(candidate_name)

        # Get unique Dropbox paths
        resume_dropbox_path, resume_filename, version = get_unique_dropbox_path(resume_folder, base_name, "pdf")
        json_dropbox_path, json_filename, _ = get_unique_dropbox_path(json_folder, base_name, "json")

        # Upload resume file
        with open(resume_path, "rb") as f:
            dbx.files_upload(f.read(), resume_dropbox_path, mode=WriteMode("add"))

        # Upload JSON content
        json_bytes = json.dumps(json_data, indent=4).encode("utf-8")
        dbx.files_upload(json_bytes, json_dropbox_path, mode=WriteMode("add"))

        # Generate temporary shared links
        resume_shared = dbx.sharing_create_shared_link_with_settings(resume_dropbox_path)
        json_shared = dbx.sharing_create_shared_link_with_settings(json_dropbox_path)

        # Replace `?dl=0` with `?dl=1` for direct download
        resume_url = resume_shared.url.replace("?dl=0", "?dl=1")
        json_url = json_shared.url.replace("?dl=0", "?dl=1")

        print(f"[INFO] Resume uploaded to Dropbox: {resume_url}")
        print(f"[INFO] JSON uploaded to Dropbox: {json_url}")

        return {
            "resume_link": resume_url,
            "json_link": json_url,
            "version": version,
        }

    except Exception as e:
        print(f"[ERROR] Failed to save to Dropbox: {e}")
        return None


