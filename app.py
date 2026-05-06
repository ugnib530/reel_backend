from flask import Flask, request, jsonify
import yt_dlp
import os
import tempfile

app = Flask(__name__)

API_KEY = os.environ.get("API_KEY", "bingu_secret_2025")

PRIVATE_KEYWORDS = ("login", "private", "not available", "sorry", "restricted", "requires")


# ─── YouTube via pytubefix ─────────────────────────────────────────────────

def _extract_youtube(url: str) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": (
            "bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[ext=mp4]+bestaudio[ext=m4a]"
            "/best[ext=mp4]/best"
        ),
        # Forces yt-dlp to use YouTube's Android client — no bot detection
        "extractor_args": {
            "youtube": {
                "player_client": ["android"]
            }
        },
    }

    with yt_dlp.YoutubeDL(opts) as ydl:
        info = ydl.extract_info(url, download=False)

    video_url, audio_url = _resolve_streams(info)
    if not video_url:
        raise Exception("No video URL found")

    return {
        "video_url": video_url,
        "audio_url": audio_url,
        "title":     info.get("title") or "YouTube Video",
        "thumbnail": info.get("thumbnail"),
        "uploader":  info.get("uploader") or info.get("channel"),
        "duration":  info.get("duration"),
        "width":     info.get("width"),
        "height":    info.get("height"),
    }



# ─── Instagram / Facebook via yt-dlp ──────────────────────────────────────

def _build_ydl_opts(cookie_file: str | None) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": (
            "bestvideo[vcodec^=avc1][ext=mp4]+bestaudio[ext=m4a]"
            "/bestvideo[ext=mp4]+bestaudio[ext=m4a]"
            "/best[ext=mp4]/best"
        ),
    }
    if cookie_file:
        opts["cookiefile"] = cookie_file
    return opts


def _write_cookie_file(sessionid: str) -> str:
    content = (
        "# Netscape HTTP Cookie File\n"
        f".instagram.com\tTRUE\t/\tTRUE\t2999999999\tsessionid\t{sessionid}\n"
    )
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(content)
        return f.name


def _resolve_streams(info: dict) -> tuple[str | None, str | None]:
    video_url = None
    audio_url = None

    requested = info.get("requested_formats") or []

    if len(requested) >= 2:
        for fmt in requested:
            vcodec = (fmt.get("vcodec") or "none").lower()
            acodec = (fmt.get("acodec") or "none").lower()
            if vcodec != "none" and acodec == "none":
                video_url = fmt.get("url")
            elif acodec != "none" and vcodec == "none":
                audio_url = fmt.get("url")

    if not video_url:
        video_url = info.get("url")
        audio_url = None

        if not video_url:
            formats = info.get("formats") or []
            mp4s = [f for f in formats if f.get("ext") == "mp4" and f.get("url")]
            if mp4s:
                video_url = mp4s[-1]["url"]

    return video_url, audio_url


def _extract_ytdlp(url: str, sessionid: str | None) -> dict:
    cookie_file = None
    if sessionid:
        cookie_file = _write_cookie_file(sessionid)

    try:
        opts = _build_ydl_opts(cookie_file)
        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        video_url, audio_url = _resolve_streams(info)
        if not video_url:
            raise Exception("No video URL found")

        return {
            "video_url": video_url,
            "audio_url": audio_url,
            "title":     info.get("title") or "Video",
            "thumbnail": info.get("thumbnail"),
            "uploader":  info.get("uploader") or info.get("channel"),
            "duration":  info.get("duration"),
            "width":     info.get("width"),
            "height":    info.get("height"),
        }
    finally:
        if cookie_file:
            try:
                os.unlink(cookie_file)
            except Exception:
                pass


# ─── Helpers ───────────────────────────────────────────────────────────────

def _is_youtube(url: str) -> bool:
    return "youtube.com" in url or "youtu.be" in url


# ─── Routes ────────────────────────────────────────────────────────────────

@app.route("/extract", methods=["GET"])
def extract():
    if request.args.get("key") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    sessionid = request.args.get("sessionid")

    try:
        if _is_youtube(url):
            data = _extract_youtube(url)
        else:
            data = _extract_ytdlp(url, sessionid)

        payload = {
            "video_url": data["video_url"],
            "title":     data["title"],
            "thumbnail": data["thumbnail"],
            "uploader":  data["uploader"],
            "duration":  data["duration"],
            "width":     data["width"],
            "height":    data["height"],
        }

        if data.get("audio_url"):
            payload["audio_url"] = data["audio_url"]

        return jsonify(payload), 200

    except yt_dlp.utils.DownloadError as e:
        if any(kw in str(e).lower() for kw in PRIVATE_KEYWORDS):
            return jsonify({"error": str(e), "requires_login": True}), 403
        return jsonify({"error": str(e)}), 400

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
