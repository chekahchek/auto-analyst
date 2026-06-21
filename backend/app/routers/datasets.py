from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, UploadFile, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.dependencies import get_storage_service
from app.models.dataset import Dataset
from app.services.exceptions import InvalidFileError, MalformedCSVError, StorageError
from app.services.storage import DatasetStorageService
from app.services.profiling import update_dataset_profile

router = APIRouter(prefix="/datasets", tags=["datasets"])


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_dataset(
    file: UploadFile,
    background_tasks: BackgroundTasks,
    request: Request,
    db: Annotated[AsyncSession, Depends(get_db)],
    storage_service: Annotated[DatasetStorageService, Depends(get_storage_service)],
):
    DatasetStorageService.validate_extension(file.filename)

    # Store dataset in database to get ID
    dataset = Dataset(
        filename=Path(file.filename).name,
        original_filename=file.filename,
        storage_path="",
        user_id=None,
    )
    db.add(dataset)
    await db.commit()
    await db.refresh(dataset)

    # Save the dataset file to storage and validate it
    try:
        path = await storage_service.save(file, dataset.id)
    except (InvalidFileError, MalformedCSVError) as exc:
        await db.delete(dataset)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
    except StorageError as exc:
        await db.delete(dataset)
        await db.commit()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(exc)
        ) from exc

    dataset.storage_path = str(path)
    await db.commit()

    # Run a background task to profile the dataset and update database
    background_tasks.add_task(
        update_dataset_profile,
        dataset_id=dataset.id,
        storage_path=str(path),
        graph=request.app.state.profiler_graph,
        max_llm_calls=request.app.state.settings.max_profile_llm_calls,
    )

    return {
        "dataset_id": str(dataset.id),
        "filename": dataset.filename,
        "original_filename": dataset.original_filename,
        "storage_path": dataset.storage_path,
    }
