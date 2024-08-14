import os
import git
import time
import shutil
from fastapi import FastAPI, HTTPException, Request, UploadFile
from pydantic import BaseModel
from fastapi.responses import JSONResponse

app = FastAPI()


class YamlRequest(BaseModel):
    input_yaml_path: str


VERSIONING_DIR = ".\\versioning_directory"


@app.get("/")
async def version_yaml():
    return JSONResponse(content={"message": "Hi there"}, status_code=200)


@app.post("/version-yaml")
async def version_yaml(file: UploadFile):
    # Save the uploaded YAML file to a temporary location
    input_yaml_path = f".\\tmp\\{file.filename}"
    with open(input_yaml_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    filename = os.path.basename(input_yaml_path)
    target_yaml_path = os.path.join(VERSIONING_DIR, filename)

    if not os.path.exists(target_yaml_path):
        raise HTTPException(status_code=404, detail="Target YAML file does not exist in versioning directory")

    # Initialize repository
    repo = git.Repo(VERSIONING_DIR)
    # Record the original commit on the master branch
    original_commit = repo.head.commit
    # Create a new branch named after the current timestamp and filename
    branch_name = f"{time.strftime('%Y%m%d-%H%M%S')}-{filename}"
    merge_success = False
    try:
        new_branch = repo.create_head(branch_name)
        new_branch.checkout()

        # Copy content from input YAML to target YAML in the new branch
        shutil.copy(input_yaml_path, target_yaml_path)

        target_yaml_relative2repo_path = filename # TODO can also be path inside VERSIONING_DIR (not only filename)
        # Stage and commit the changes
        repo.git.add(target_yaml_relative2repo_path)
        commit_message = f"Updated {filename} from {input_yaml_path}"
        repo.git.commit('-m', commit_message)

        # Attempt to merge the changes into the master branch
        repo.git.checkout('master')
        try:
            repo.git.merge(branch_name)
            merge_success = True
            return JSONResponse(content={"message": "Merge successful", "branch": branch_name}, status_code=200)
        except git.exc.GitCommandError as e:
            conflict_output = str(e)
            return JSONResponse(content={"error": "Merge conflict", "details": conflict_output}, status_code=409)

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        # Cleanup: delete the branch and checkout the master branch
        if branch_name and not merge_success:
            repo.git.checkout('master')
            repo.git.branch('-D', branch_name)  # Delete the branch
        # Clean up temporary file
        if os.path.exists(input_yaml_path):
            os.remove(input_yaml_path)
        if not merge_success:
            # Reset the repository to the original commit
            repo.git.reset('--hard', original_commit.hexsha)


if __name__ == '__main__':
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8888)
