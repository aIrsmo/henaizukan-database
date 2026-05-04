from fastapi import FastAPI, UploadFile, File, Form, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client
import os
from dotenv import load_dotenv
import uuid

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