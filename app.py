import os
import re
import urllib.parse
import requests
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from yt_dlp import YoutubeDL
from mutagen.easyid3 import EasyID3
from mutagen.id3 import ID3, APIC, USLT

app = FastAPI()

STOREFRONTS = ["in", "us", "gb", "pk", "ae", "sa", "ca", "au"]

def clean_query(title: str) -> str:
    patterns = [
        r"\(?official\s*(music\s*)?(video|audio|lyric|track)?\)?",
        r"\[?official\s*(music\s*)?(video|audio|lyric|track)?\]?",
        r"\(?lyrical\s*video\)?",
        r"\[?lyrical\s*video\]?",
        r"\(?full\s*(song|video|audio)\)?",
        r"\[?full\s*(song|video|audio)\]?",
        r"\(?remix\)?",
        r"\[?remix\]?",
        r"\(?4k(\s*uhd)?\)?",
        r"\[?4k(\s*uhd)?\]?",
        r"\|.*$",
        r"ft\..*$",
        r"feat\..*$"
    ]
    cleaned = title
    for p in patterns:
        cleaned = re.sub(p, "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned if len(cleaned) > 2 else title

def search_itunes(query: str):
    for sf in STOREFRONTS:
        try:
            url = f"https://itunes.apple.com/search?term={urllib.parse.quote(query)}&country={sf}&media=music&entity=song&limit=1"
            r = requests.get(url, timeout=4).json()
            if r.get("resultCount", 0) > 0:
                return r["results"][0]
        except Exception:
            continue
    return None

def fetch_lyrics(title: str, artist: str) -> str:
    try:
        url = f"https://lrclib.net/api/get?track_name={urllib.parse.quote(title)}&artist_name={urllib.parse.quote(artist)}"
        r = requests.get(url, timeout=3).json()
        return r.get("plainLyrics") or ""
    except Exception:
        return ""

@app.get("/download")
async def download_song(url: str):
    if not url:
        raise HTTPException(status_code=400, detail="Missing YouTube URL")

    out_tmpl = "/tmp/%(id)s.%(ext)s"
    ydl_opts = {
        'format': 'ba/b',
        'outtmpl': out_tmpl,
        'postprocessors': [{
            'key': 'FFmpegExtractAudio',
            'preferredcodec': 'mp3',
            'preferredquality': '96',
        }],
        'quiet': True,
        'no_warnings': True,
        'extractor_args': {
            'youtube': {
                'player_client': ['android', 'web']
            }
        }
    }

    try:
        with YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            video_id = info.get('id')
            raw_title = info.get('title', 'Song')
            yt_uploader = info.get('uploader', '')
            yt_thumbnail = info.get('thumbnail', '')

        mp3_path = f"/tmp/{video_id}.mp3"
        if not os.path.exists(mp3_path):
            raise HTTPException(status_code=500, detail="Audio extraction failed")

        cleaned = clean_query(raw_title)
        itunes_data = search_itunes(cleaned) or search_itunes(raw_title)

        if itunes_data:
            song_title = itunes_data.get("trackName", cleaned)
            artist_name = itunes_data.get("artistName", yt_uploader)
            album_name = itunes_data.get("collectionName", song_title)
            genre = itunes_data.get("primaryGenreName", "Pop")
            year = itunes_data.get("releaseDate", "")[:4]
            artwork_url = itunes_data.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
        else:
            song_title = cleaned
            artist_name = yt_uploader
            album_name = cleaned
            genre = "Soundtrack"
            year = ""
            artwork_url = yt_thumbnail

        # Write Basic Tags
        audio = EasyID3(mp3_path)
        audio['title'] = song_title
        audio['artist'] = artist_name
        audio['album'] = album_name
        audio['genre'] = genre
        if year:
            audio['date'] = year
        audio.save()

        # Cover Art & Lyrics
        id3 = ID3(mp3_path)
        if artwork_url:
            try:
                img_data = requests.get(artwork_url, timeout=5).content
                id3.add(APIC(encoding=3, mime='image/jpeg', type=3, desc='Cover', data=img_data))
            except Exception:
                pass

        lyrics = fetch_lyrics(song_title, artist_name)
        if lyrics:
            id3.add(USLT(encoding=3, lang='eng', desc='desc', text=lyrics))

        id3.save(v2_version=3)

        clean_filename = re.sub(r'[\\/*?:"<>|]', '', f"{song_title} - {artist_name}.mp3")
        return FileResponse(
            path=mp3_path,
            filename=clean_filename,
            media_type='audio/mpeg'
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
