import os
import asyncio
import concurrent.futures
import requests
from fastapi import FastAPI
from io import BytesIO
from enkacard import encbanner
from fastapi.responses import JSONResponse
import enkacard
import starrailcard  # Import StarRailCard module
import enkanetwork
import uvicorn
from fastapi.staticfiles import StaticFiles

app = FastAPI()

# Directory where images will be saved
IMAGE_SAVE_PATH = "static/cards"

# Ensure the directory exists
os.makedirs(IMAGE_SAVE_PATH, exist_ok=True)

# Mount the static files directory to serve saved images
app.mount("/cards", StaticFiles(directory=IMAGE_SAVE_PATH), name="cards")

# Genshin Impact card creation
async def genshin_card(id, designtype):
    async with encbanner.ENC(uid=str(id)) as encard:
        return await encard.creat(akasha=True, template=(2 if str(designtype) == "2" else 1))

# Star Rail card creation
async def starrail_card(id, designtype):
    async with starrailcard.Card(seeleland=True, remove_logo=True, enka=True) as card:
        return await card.create(id, style=(2 if str(designtype) == "2" else 1))

# Star Rail profile creation
async def starrail_profile(id):
    async with starrailcard.Card(remove_logo=True, seeleland=True, enka=True) as card:
        return await card.create_profile(id, style=2)

# Helper function to save the image locally
def save_image(data, file_name):
    file_path = os.path.join(IMAGE_SAVE_PATH, file_name)
    with open(file_path, "wb") as file:
        file.write(data)
    return f"/cards/{file_name}"

# Process individual image card
def process_image(dt, user_id):
    file_name = f"{dt.id}_{user_id}.png"
    with BytesIO() as byte_io:
        dt.card.save(byte_io, "PNG")
        byte_io.seek(0)
        # Save the image locally
        image_url = save_image(byte_io.read(), file_name)
        return {
            "name": dt.name,
            "url": image_url
        }

# Process the profile image
def process_profile(profile_card, user_id):
    file_name = f"profile_{user_id}.png"
    with BytesIO() as byte_io:
        profile_card.card.save(byte_io, "PNG")
        byte_io.seek(0)
        # Save the profile image locally
        image_url = save_image(byte_io.read(), file_name)
        return {
            "name": profile_card.character_name,
            "url": image_url,
            "character_ids": profile_card.character_id
        }

# Process all the images returned
def process_images(result, user_id):
    characters = []
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = [executor.submit(process_image, dt, user_id) for dt in result.card]
        for future in concurrent.futures.as_completed(futures):
            try:
                characters.append(future.result())
            except Exception as e:
                print(f"Error processing image: {e}")
    return characters

# Route for Genshin Impact
@app.get("/genshin/{id}")
async def genshin_characters(id: int, design: str = "1"):
    try:
        result = await genshin_card(id, design)
        characters = process_images(result, id)
        return JSONResponse(content={'response': characters})

    except enkanetwork.exception.VaildateUIDError:
        return JSONResponse(content={'error': 'Invalid UID. Please check your UID.'}, status_code=400)

    except enkacard.enc_error.ENCardError:
        return JSONResponse(content={'error': 'Enable display of the showcase in the game or add characters there.'}, status_code=400)

    except Exception as e:
        return JSONResponse(content={'error': 'UNKNOWN ERR: ' + str(e)}, status_code=500)

# Route for Star Rail
@app.get("/starrail/{id}")
async def starrail_characters(id: int, design: str = "1"):
    try:
        result = await starrail_card(id, design)
        characters = process_images(result, id)
        return JSONResponse(content={'response': characters})

    except Exception as e:
        return JSONResponse(content={'error': 'UNKNOWN ERR: ' + str(e)}, status_code=500)

# Route for Star Rail profile
@app.get("/starrail/profile/{id}")
async def starrail_profile_route(id: int):
    try:
        result = await starrail_profile(id)
        profile_data = process_profile(result, id)
        return JSONResponse(content={'response': profile_data})

    except Exception as e:
        return JSONResponse(content={'error': 'UNKNOWN ERR: ' + str(e)}, status_code=500)

# Start the FastAPI server
if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=7860, workers=8, timeout_keep_alive=60000)
