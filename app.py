from flask import Flask, request, jsonify
import yt_dlp
import os
import tempfile

app = Flask(__name__)

API_KEY = os.environ.get("API_KEY", "bingu_secret_2025")

PRIVATE_KEYWORDS = ("login", "private", "not available", "sorry", "restricted", "requires")


def _build_ydl_opts(sessionid: str | None, cookie_file: str | None) -> dict:
    opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        # Prefer H.264 video + m4a audio (widest device support)
        # Falls back gracefully if H.264 isn't available
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
    """
    Returns (video_url, audio_url).
    audio_url is non-None only when Instagram used DASH (separate streams).
    """
    video_url = None
    audio_url = None

    requested = info.get("requested_formats") or []

    if len(requested) >= 2:
        # DASH: yt-dlp matched a video+audio format pair
        for fmt in requested:
            vcodec = (fmt.get("vcodec") or "none").lower()
            acodec = (fmt.get("acodec") or "none").lower()
            if vcodec != "none" and acodec == "none":
                video_url = fmt.get("url")
            elif acodec != "none" and vcodec == "none":
                audio_url = fmt.get("url")
    
    if not video_url:
        # Progressive MP4 — single stream, audio is embedded
        video_url = info.get("url")
        audio_url = None

        # Last resort: pick the best mp4 from the formats list
        if not video_url:
            formats = info.get("formats") or []
            mp4s = [f for f in formats if f.get("ext") == "mp4" and f.get("url")]
            if mp4s:
                video_url = mp4s[-1]["url"]

    return video_url, audio_url


@app.route("/extract", methods=["GET"])
def extract():
    # ── Auth ──────────────────────────────────────────────────────────────────
    if request.args.get("key") != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    url = request.args.get("url", "").strip()
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    sessionid  = request.args.get("sessionid")
    cookie_file = None

    if sessionid:
        cookie_file = _write_cookie_file(sessionid)

    try:
        opts = _build_ydl_opts(sessionid, cookie_file)

        with yt_dlp.YoutubeDL(opts) as ydl:
            info = ydl.extract_info(url, download=False)

        video_url, audio_url = _resolve_streams(info)

        if not video_url:
            return jsonify({"error": "No video URL found"}), 404

        payload = {
            "video_url": video_url,
            "title":     info.get("title") or "Instagram Video",
            "thumbnail": info.get("thumbnail"),
            "uploader":  info.get("uploader") or info.get("channel"),
            "duration":  info.get("duration"),
            "width":     info.get("width"),
            "height":    info.get("height"),
        }

        # Only include audio_url when streams are separate (DASH)
        # Flutter will merge them locally with FFmpeg when this key is present
        if audio_url:
            payload["audio_url"] = audio_url

        return jsonify(payload), 200

    except yt_dlp.utils.DownloadError as e:
        if any(kw in str(e).lower() for kw in PRIVATE_KEYWORDS):
            return jsonify({"error": str(e), "requires_login": True}), 403
        return jsonify({"error": str(e)}), 400

    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500

    finally:
        if cookie_file:
            try:
                os.unlink(cookie_file)
            except Exception:
                pass


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
