from flask import Flask, request, jsonify
import yt_dlp
import os
import tempfile

app = Flask(__name__)

API_KEY = os.environ.get("API_KEY", "changeme123")

@app.route("/extract", methods=["GET"])
def extract():
    key = request.args.get("key")
    if key != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    url = request.args.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    sessionid = request.args.get("sessionid")

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "best[ext=mp4]/best",
    }

    cookie_file = None

    if sessionid:
        cookie_content = (
            "# Netscape HTTP Cookie File\n"
            f".instagram.com\tTRUE\t/\tTRUE\t2999999999\tsessionid\t{sessionid}\n"
        )
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
            f.write(cookie_content)
            cookie_file = f.name
        ydl_opts["cookiefile"] = cookie_file

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            video_url = info.get("url")
            if not video_url:
                formats = info.get("formats", [])
                mp4_formats = [f for f in formats if f.get("ext") == "mp4" and f.get("url")]
                if mp4_formats:
                    video_url = mp4_formats[-1]["url"]

            if not video_url:
                return jsonify({"error": "No video URL found"}), 404

            return jsonify({
                "video_url": video_url,
                "title": info.get("title", "Instagram Video"),
                "thumbnail": info.get("thumbnail"),
                "uploader": info.get("uploader"),
                "duration": info.get("duration"),
            })

    except yt_dlp.utils.DownloadError as e:
        error_lower = str(e).lower()
        if any(kw in error_lower for kw in ["login", "private", "not available", "sorry", "restricted"]):
            return jsonify({"error": "private_post", "requires_login": True}), 403
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
