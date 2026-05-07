from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
import os
from dotenv import load_dotenv
import uuid
from pydantic import BaseModel
from typing import List
from typing import Dict

load_dotenv()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase接続
supabase = create_client(
    os.getenv("SUPABASE_URL"),
    os.getenv("SUPABASE_KEY")
)

@app.get("/")
def root():
    return {"message": "API OK"}

class CreateCollectionRequest(BaseModel):
    title: str
    content: str
    thumbnailUrl: str
    imageIds: List[str]
    aiTags: List[str]

class CreateSavedBoardRequest(BaseModel):
    title: str
    comment: str | None = None
    condition: dict
    offsets: Dict[str, dict]

# 🔥 保存API
@app.post("/save")
async def save_exhibit(
    file: UploadFile = File(...),
    text: str = Form(""),
    tags: str = Form(""),
    authorization: str = Header(None)
):
    try:
        # 🔐 Supabase Authのユーザー取得
        if not authorization:
            raise HTTPException(status_code=401, detail="No token")

        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)

        if not user:
            raise HTTPException(status_code=401, detail="Invalid user")

        user_id = user.user.id

        # 🖼 画像アップロード
        file_ext = file.filename.split(".")[-1]
        file_name = f"{uuid.uuid4()}.{file_ext}"

        file_bytes = await file.read()

        supabase.storage.from_("images").upload(
            file_name,
            file_bytes
        )

        image_url = supabase.storage.from_("images").get_public_url(file_name)

        # 📝 exhibitsに保存
        exhibit_res = supabase.table("exhibits").insert({
            "user_id": user_id,
            "image_url": image_url,
            "text": text
        }).execute()

        exhibit_id = exhibit_res.data[0]["id"]

        # 🏷 タグ処理
        tag_list = list(set([t.strip() for t in tags.split(",") if t.strip()]))

        for tag_name in tag_list:
            tag_res = supabase.table("tags").select("*").eq("name", tag_name).execute()

            if tag_res.data:
                tag_id = tag_res.data[0]["id"]
            else:
                new_tag = supabase.table("tags").insert({
                    "name": tag_name
                }).execute()
                tag_id = new_tag.data[0]["id"]

            supabase.table("exhibit_tags").insert({
                "exhibit_id": exhibit_id,
                "tag_id": tag_id
            }).execute()

        return {
            "message": "saved!",
            "exhibit_id": exhibit_id,
            "image_url": image_url
        }

    except Exception as e:
        return {"error": str(e)}


# 📚 作品一覧取得API
@app.get("/exhibits")
def get_exhibits():
    try:
        exhibits_res = supabase.table("exhibits") \
            .select("*") \
            .order("created_at", desc=True) \
            .execute()

        exhibits = exhibits_res.data
        result = []

        for exhibit in exhibits:
            exhibit_id = exhibit["id"]

            tag_links_res = supabase.table("exhibit_tags") \
                .select("tags(name)") \
                .eq("exhibit_id", exhibit_id) \
                .execute()

            tag_names = []

            for link in tag_links_res.data:
                if link.get("tags"):
                    tag_names.append(link["tags"]["name"])

            result.append({
                "id": exhibit["id"],
                "userId": exhibit["user_id"],
                "title": exhibit["text"] or "",
                "memo": exhibit["text"] or "",
                "tags": tag_names,
                "imageUrl": exhibit["image_url"],
                "createdAt": exhibit["created_at"],
            })

        return {
            "exhibits": result
        }

    except Exception as e:
        return {
            "error": str(e)
        }

# 🖼 フロント用：フォト一覧取得API
@app.get("/photos")
def get_photos():
    try:
        exhibits_res = supabase.table("exhibits") \
            .select("*") \
            .order("created_at", desc=True) \
            .execute()

        photos = []

        for exhibit in exhibits_res.data:
            exhibit_id = exhibit["id"]

            tag_links_res = supabase.table("exhibit_tags") \
                .select("tags(name)") \
                .eq("exhibit_id", exhibit_id) \
                .execute()

            tag_names = []

            for link in tag_links_res.data:
                if link.get("tags"):
                    tag_names.append(link["tags"]["name"])

            photos.append({
                "id": exhibit["id"],
                "userId": exhibit["user_id"],
                "title": exhibit["text"] or "",
                "memo": exhibit["text"] or "",
                "tags": tag_names,
                "aiTags": tag_names,
                "imageUrl": exhibit["image_url"],
                "createdAt": exhibit["created_at"],
            })

        return {
            "photos": photos
        }

    except Exception as e:
        return {"error": str(e)}

# 🧷 フロント用：保存済み図鑑ボード一覧取得API
@app.get("/saved-boards")
def get_saved_boards():
    return {
        "savedBoards": []
    }

# 📚 コレクション作成API
@app.post("/collections")
def create_collection(
    data: CreateCollectionRequest,
    authorization: str = Header(None)
):
    try:
        # 🔐 ユーザー認証
        if not authorization:
            raise HTTPException(status_code=401, detail="No token")

        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)

        if not user:
            raise HTTPException(status_code=401, detail="Invalid user")

        user_id = user.user.id

        # 📚 collections保存
        collection_res = supabase.table("collections").insert({
            "author_id": user_id,
            "title": data.title,
            "thumbnail_url": data.thumbnailUrl,
            "content": data.content,
            "ai_tags": data.aiTags
        }).execute()

        collection_id = collection_res.data[0]["id"]

        # 🔗 写真紐付け
        for exhibit_id in data.imageIds:
            supabase.table("collection_photos").insert({
                "collection_id": collection_id,
                "exhibit_id": exhibit_id
            }).execute()

        return {
            "message": "collection created!",
            "collectionId": collection_id
        }

    except Exception as e:
        return {
            "error": str(e)
        }

# 📚 コレクション一覧取得API
@app.get("/collections")
def get_collections():
    try:
        collections_res = supabase.table("collections") \
            .select("*") \
            .order("created_at", desc=True) \
            .execute()

        result = []

        for collection in collections_res.data:
            collection_id = collection["id"]

            # 🔗 紐付いた写真取得
            links_res = supabase.table("collection_photos") \
                .select("exhibits(image_url)") \
                .eq("collection_id", collection_id) \
                .execute()

            image_urls = []

            for link in links_res.data:
                if link.get("exhibits"):
                    image_urls.append(link["exhibits"]["image_url"])

            result.append({
                "id": collection["id"],
                "authorId": collection["author_id"],
                "title": collection["title"],
                "thumbnailUrl": collection["thumbnail_url"],
                "content": collection["content"],
                "imageUrls": image_urls,
                "aiTags": collection["ai_tags"],
                "createdAt": collection["created_at"]
            })

        return {
            "collections": result
        }

    except Exception as e:
        return {
            "error": str(e)
        }
    
# 📖 コレクション詳細取得API
@app.get("/collections/{collection_id}")
def get_collection_detail(collection_id: str):
    try:
        # ① コレクション本体を取得
        collection_res = supabase.table("collections") \
            .select("*") \
            .eq("id", collection_id) \
            .single() \
            .execute()

        collection = collection_res.data

        if not collection:
            raise HTTPException(status_code=404, detail="Collection not found")

        # ② 紐付いている写真を取得
        links_res = supabase.table("collection_photos") \
            .select("exhibits(id, user_id, image_url, text, created_at, view_count)") \
            .eq("collection_id", collection_id) \
            .execute()

        photos = []

        for link in links_res.data:
            exhibit = link.get("exhibits")

            if not exhibit:
                continue

            exhibit_id = exhibit["id"]

            # ③ 写真ごとのタグを取得
            tag_links_res = supabase.table("exhibit_tags") \
                .select("tags(name)") \
                .eq("exhibit_id", exhibit_id) \
                .execute()

            tag_names = []

            for tag_link in tag_links_res.data:
                if tag_link.get("tags"):
                    tag_names.append(tag_link["tags"]["name"])

            photos.append({
                "id": exhibit["id"],
                "userId": exhibit["user_id"],
                "title": exhibit["text"] or "",
                "memo": exhibit["text"] or "",
                "tags": tag_names,
                "aiTags": tag_names,
                "imageUrl": exhibit["image_url"],
                "createdAt": exhibit["created_at"],
            })

        return {
            "collection": {
                "id": collection["id"],
                "authorId": collection["author_id"],
                "title": collection["title"],
                "thumbnailUrl": collection["thumbnail_url"],
                "content": collection["content"],
                "imageUrls": [photo["imageUrl"] for photo in photos],
                "aiTags": collection["ai_tags"],
                "createdAt": collection["created_at"],
                "photos": photos
            }
        }

    except Exception as e:
        return {
            "error": str(e)
        }
    
# 🧷 保存済みボード作成API
@app.post("/saved-boards")
def create_saved_board(
    data: CreateSavedBoardRequest,
    authorization: str = Header(None)
):
    try:
        # 🔐 ユーザー認証
        if not authorization:
            raise HTTPException(status_code=401, detail="No token")

        token = authorization.replace("Bearer ", "")
        user = supabase.auth.get_user(token)

        if not user:
            raise HTTPException(status_code=401, detail="Invalid user")

        user_id = user.user.id

        # 🧷 保存
        board_res = supabase.table("saved_boards").insert({
            "user_id": user_id,
            "title": data.title,
            "comment": data.comment,
            "condition": data.condition,
            "offsets": data.offsets
        }).execute()

        board_id = board_res.data[0]["id"]

        return {
            "message": "saved board created!",
            "boardId": board_id
        }

    except Exception as e:
        return {
            "error": str(e)
        }