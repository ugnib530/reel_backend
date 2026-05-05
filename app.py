from flask import Flask, request, jsonify
import yt_dlp
import os

app = Flask(__name__)

# Simple secret key to prevent others from abusing your server
API_KEY = os.environ.get("API_KEY", "changeme123")

@app.route("/extract", methods=["GET"])
def extract():
    # Check API key
    key = request.args.get("key")
    if key != API_KEY:
        return jsonify({"error": "Unauthorized"}), 401

    url = request.args.get("url")
    if not url:
        return jsonify({"error": "No URL provided"}), 400

    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "format": "best[ext=mp4]/best",
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)

            # Get best video URL
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
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Server error: {str(e)}"}), 500


@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
