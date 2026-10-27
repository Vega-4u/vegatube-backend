import os, re, json, urllib.parse, urllib.request, subprocess
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse
import requests
from mutagen.id3 import ID3, TIT2, TPE1, TALB, TPE2, TDRC, TCON, USLT, APIC

app = FastAPI()

def search_apple_catalog(query_str):
    storefronts = ["IN", "PK", "US", "KR", "SA", "AE", "GB", "NP", "JP", "CA"]
    q = urllib.parse.quote(query_str)
    for country in storefronts:
        try:
            url = f"https://itunes.apple.com/search?term={q}&entity=song&limit=3&country={country}"
            res = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=3).json()
            results = res.get("results", [])
            for item in results:
                cname = item.get("collectionName", "").lower()
                if any(bad in cname for bad in ["hits of", "best of", "top 20", "compilation"]):
                    continue
                return item
        except Exception:
            continue
    return None

def fetch_clean_lyrics(artist, title):
    try:
        url = "https://lrclib.net/api/get?" + urllib.parse.urlencode({"artist_name": artist, "track_name": title})
        res = requests.get(url, headers={"User-Agent": "Vegatube/2.0"}, timeout=3).json()
        lyrics = res.get("syncedLyrics") or res.get("plainLyrics") or ""
        if not lyrics:
            return ""
        lines = [re.sub(r"^\[[0-9:.]+\]\s*", "", l).strip() for l in lyrics.splitlines() if l.strip()]
        body = " ".join(lines)
        readable = sum(1 for c in body if c.isalnum() or c.isspace() or c in ",.!?'-")
        if (readable / len(body)) >= 0.85:
            return lyrics
        return ""
    except Exception:
        return ""

@app.get("/download")
def download_track(url: str = Query(...)):
    work_id = str(abs(hash(url)))[:8]
    raw_audio = f"/tmp/raw_{work_id}"
    out_mp3 = f"/tmp/out_{work_id}.mp3"
    thumb_path = f"/tmp/thumb_{work_id}"

    cmd_info = [
        "yt-dlp",
        "--extractor-args", "youtube:player_client=android",
        "--print", "%(title)s\n%(channel)s\n%(upload_date)s",
        url
    ]
    try:
        meta = subprocess.check_output(cmd_info).decode("utf-8").strip().splitlines()
        raw_title = meta[0] if len(meta) > 0 else "Song"
        raw_artist = meta[1] if len(meta) > 1 else "Unknown Artist"
        upload_year = meta[2][:4] if len(meta) > 2 and len(meta[2]) >= 4 else "2024"
    except Exception:
        raw_title, raw_artist, upload_year = "Song", "Unknown Artist", "2024"

    cmd_dl = [
        "yt-dlp",
        "--extractor-args", "youtube:player_client=android",
        "-f", "ba/b",
        "--write-thumbnail",
        "-o", raw_audio + ".%(ext)s",
        "-o", f"thumbnail:{thumb_path}.%(ext)s",
        url
    ]
    subprocess.run(cmd_dl)

    audio_files = [os.path.join("/tmp", f) for f in os.listdir("/tmp") if f.startswith(f"raw_{work_id}.") and not f.endswith((".jpg", ".webp", ".png"))]
    if not audio_files:
        raise HTTPException(status_code=500, detail="Download failed")

    subprocess.run(["ffmpeg", "-y", "-i", audio_files[0], "-vn", "-c:a", "libmp3lame", "-b:a", "96k", out_mp3])
    try:
        os.remove(audio_files[0])
    except Exception:
        pass

    clean = re.sub(r"(?i)\b(official|video|audio|full song|teaser|trailer|remix|hd|4k|lyric|lyrics|lyrical|visualizer|status)\b", "", raw_title)
    clean = re.sub(r"\s*[\(\[][^\)\]]*[\)\]]", " ", clean).strip()

    search_q = f"{clean} {raw_artist}" if raw_artist != "Unknown Artist" else clean
    itunes = search_apple_catalog(search_q) or search_apple_catalog(clean)

    song_title = clean
    artist_name = raw_artist
    album_name = clean
    release_year = upload_year
    category = "Music"
    cover_data = None

    if itunes:
        song_title = itunes.get("trackName", song_title)
        artist_name = itunes.get("artistName", artist_name)
        album_name = itunes.get("collectionName", album_name)
        rd = itunes.get("releaseDate", "")
        if rd:
            release_year = rd[:4]
        category = itunes.get("primaryGenreName", category)
        art_url = itunes.get("artworkUrl100", "").replace("100x100bb.jpg", "600x600bb.jpg")
        try:
            cover_data = requests.get(art_url, timeout=4).content
        except Exception:
            cover_data = None

    album_name = re.sub(r"(?i)\s*[\(\[][^\)\]]*(soundtrack|original)[^\)\]]*[\)\]]", "", album_name).strip()
    album_name = re.sub(r"(?i)\s*-\s*(single|ep|soundtrack).*$", "", album_name).strip()

    if not cover_data:
        raw_thumbs = [os.path.join("/tmp", f) for f in os.listdir("/tmp") if f.startswith(f"thumb_{work_id}.")]
        if raw_thumbs:
            jpg_thumb = f"/tmp/final_thumb_{work_id}.jpg"
            subprocess.run(["ffmpeg", "-y", "-i", raw_thumbs[0], jpg_thumb])
            if os.path.exists(jpg_thumb):
                with open(jpg_thumb, "rb") as img:
                    cover_data = img.read()
                try:
                    os.remove(jpg_thumb)
                except Exception:
                    pass
            try:
                os.remove(raw_thumbs[0])
            except Exception:
                pass

    lyrics_text = fetch_clean_lyrics(artist_name.split(",")[0].split("&")[0].strip(), song_title)

    try:
        id3 = ID3(out_mp3)
    except Exception:
        id3 = ID3()

    id3.delall("TIT2"); id3.delall("TPE1"); id3.delall("TALB"); id3.delall("TDRC"); id3.delall("TCON"); id3.delall("USLT"); id3.delall("APIC")
    id3.add(TIT2(encoding=3, text=song_title))
    id3.add(TPE1(encoding=3, text=artist_name))
    id3.add(TALB(encoding=3, text=album_name))
    id3.add(TDRC(encoding=3, text=release_year))
    id3.add(TCON(encoding=3, text=category))

    if lyrics_text:
        id3.add(USLT(encoding=3, lang="eng", desc="", text=lyrics_text))
    if cover_data:
        id3.add(APIC(encoding=3, mime="image/jpeg", type=3, desc="Cover", data=cover_data))

    id3.save(out_mp3)

    safe_name = re.sub(r'[/\\:*?"<>|]', "", f"{song_title} - {artist_name}").strip() + ".mp3"
    final_file = f"/tmp/{safe_name}"
    os.rename(out_mp3, final_file)

    return FileResponse(final_file, filename=safe_name, media_type="audio/mpeg")
