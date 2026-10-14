import os
import sys
import time

import dropbox
import requests
from dotenv import load_dotenv

load_dotenv()

# Your Dropbox API access token
ACCESS_TOKEN = os.getenv("TOKEN")

if not ACCESS_TOKEN:
    print("You forgot to add your Dropbox credentials to the `.env` file! Add it and try again!")
    sys.exit(1)

# Initialize the Dropbox client
dbx = dropbox.Dropbox(ACCESS_TOKEN)

print(
    "Get your token at https://www.dropbox.com/developers/apps and ensure you have the necessary permissions ticked on!"
)


CHUNK_SIZE = 8 * 1024 * 1024
MAX_RETRIES = 5


def _with_retry(fn, *args):
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            return fn(*args)
        except (requests.exceptions.ConnectionError, requests.exceptions.SSLError, requests.exceptions.Timeout):
            if attempt == MAX_RETRIES:
                raise
            print(f"Connection dropped, retrying ({attempt}/{MAX_RETRIES - 1})...")
            time.sleep(2 * attempt)


def upload_file(file_path, dropbox_path):
    # Upload in chunks via an upload session; single-request uploads of large files get dropped
    # Dropbox drops large requests on auth/scope errors (shows up as SSLEOFError), so check with an empty one first
    try:
        dbx.files_upload_session_start(b"")
    except dropbox.exceptions.AuthError as e:
        print(f"Your Dropbox token was rejected: {e.error}")
        print("Enable 'files.content.write' and 'sharing.write' in your app's Permissions tab, then generate a new token.")
        sys.exit(1)

    file_size = os.path.getsize(file_path)
    with open(file_path, "rb") as f:
        chunk = f.read(CHUNK_SIZE)
        session = _with_retry(dbx.files_upload_session_start, chunk)
        cursor = dropbox.files.UploadSessionCursor(session_id=session.session_id, offset=len(chunk))
        commit = dropbox.files.CommitInfo(path=dropbox_path)

        while True:
            chunk = f.read(CHUNK_SIZE)
            if f.tell() >= file_size:
                _with_retry(dbx.files_upload_session_finish, chunk, cursor, commit)
                break
            _with_retry(dbx.files_upload_session_append_v2, chunk, cursor)
            cursor.offset += len(chunk)
            print(f"Uploaded {cursor.offset * 100 // file_size}%")

    print(f"File {file_path} uploaded to {dropbox_path} successfully.")

    # Generate a shared link
    shared_link_metadata = dbx.sharing_create_shared_link_with_settings(dropbox_path)

    return shared_link_metadata.url  # type: ignore


if __name__ == "__main__":
    upload_file("requirements.txt", "/requirements.txt")
