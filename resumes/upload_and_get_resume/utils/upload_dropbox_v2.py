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


# Sanatize File Name
def sanitize_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "", name)


# Get Unique Dropbox Path
def get_unique_dropbox_path(folder_path: str, base_name: str, extension: str):
    """
    Gets Unique path for Analysed resume report by checking if candidate's analysis with same name exists.
    Parameters:
    folder_path (str): Path to the Dropbox folder
    base_name (str): Name of the candidate
    extension (str): Extension of the file
    Returns:
    str: Unique Dropbox path
    file_name (str): Name of the file
    i (int): Version number
    """
    i = 0
    while True:
        file_name = f"{base_name}_{i}.{extension}"
        dropbox_path = f"/{folder_path}/{file_name}"

        try:
            dbx.files_get_metadata(dropbox_path)
            i += 1
        except dropbox.exceptions.ApiError as e:
            if (
                isinstance(e.error, dropbox.files.GetMetadataError)
                and e.error.is_path()
                and e.error.get_path().is_not_found()
            ):
                return dropbox_path, file_name, i
            else:
                raise e


# Save To Dropbox (Asybc)
async def save_to_dropbox(resume_path: str, candidate_name: str):
    """
    Saves the analysed resume to Dropbox
    Parameters:
    resume_path (str): Path to the resume file
    candidate_name (str): Name of the candidate
    Returns:
    dict: Contains the URL of the shared resume and version number
    """
    try:
        analysis_folder = "analysed_resumes"

        # Ensure sanitized name
        base_name = sanitize_filename(candidate_name)

        # Get unique Dropbox paths
        analysed_resume_dropbox_path, resume_filename, version = (
            get_unique_dropbox_path(analysis_folder, base_name, "pdf")
        )

        # Upload resume file
        with open(resume_path, "rb") as f:
            dbx.files_upload(
                f.read(), analysed_resume_dropbox_path, mode=WriteMode("add")
            )

        # Generate temporary shared links
        analysed_resume_shared = dbx.sharing_create_shared_link_with_settings(
            analysed_resume_dropbox_path
        )

        # Replace `?dl=0` with `?dl=1` for direct download
        analysed_resume_url = analysed_resume_shared.url.replace("?dl=0", "?dl=1")

        print(f"[INFO] Analysed Resume uploaded to Dropbox: {analysed_resume_url}")

        return {
            "analysed_resume_link": analysed_resume_url,
            "version": version,
        }

    except Exception as e:
        print(f"[ERROR] Failed to save to Dropbox: {e}")
        return None



