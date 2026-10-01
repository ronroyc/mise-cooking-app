"""Recipe photo routes.

PUT    /api/recipes/{id}/photo   upload a photo: the request body is the image file itself
POST   /api/recipes/{id}/photo/from-url   download a photo from a website (for imported recipes)
DELETE /api/recipes/{id}/photo   remove it (the card goes back to a plain colored cover)
GET    /api/photos/{filename}    the image (a recipe's photo_url points here)

The upload sends the raw file instead of a multipart form, so no extra
package is needed to read it.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.recipes import get_recipe_or_404
from app.database.db import get_db
from app.schemas.recipe import PhotoFromUrlRequest, RecipeSummary
from app.services import photos, recipe_import

router = APIRouter(tags=["photos"])


@router.put("/recipes/{recipe_id}/photo", response_model=RecipeSummary)
async def upload_photo(recipe_id: int, request: Request, db: Session = Depends(get_db)):
    recipe = get_recipe_or_404(db, recipe_id)
    # Refuse a huge upload before reading it, when the browser says how big it is.
    if int(request.headers.get("content-length") or 0) > photos.MAX_BYTES:
        raise HTTPException(status_code=413, detail="The photo is too big. The limit is 15 MB.")
    try:
        return photos.save_photo(db, recipe, await request.body())
    except photos.InvalidPhotoError as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.post("/recipes/{recipe_id}/photo/from-url", response_model=RecipeSummary)
def photo_from_url(recipe_id: int, data: PhotoFromUrlRequest, db: Session = Depends(get_db)):
    recipe = get_recipe_or_404(db, recipe_id)
    try:
        return photos.save_photo(db, recipe, recipe_import.fetch(data.url, photos.MAX_BYTES))
    except (recipe_import.ImportFailed, photos.InvalidPhotoError) as error:
        raise HTTPException(status_code=422, detail=str(error))


@router.delete("/recipes/{recipe_id}/photo", response_model=RecipeSummary)
def delete_photo(recipe_id: int, db: Session = Depends(get_db)):
    return photos.remove_photo(db, get_recipe_or_404(db, recipe_id))


@router.get("/photos/{filename}")
def get_photo(filename: str):
    path = photos.path_for(filename)
    if path is None or not path.is_file():
        raise HTTPException(status_code=404, detail="Photo not found")
    extension = filename.rsplit(".", 1)[1]
    # Each upload gets a new file name, so a file never changes: browsers can keep it.
    return FileResponse(
        path, media_type=photos.MEDIA_TYPES[extension],
        headers={"Cache-Control": "private, max-age=31536000, immutable"},
    )
