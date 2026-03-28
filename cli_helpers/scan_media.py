import os
import subprocess
import json
import csv
import sys

DIR = "/opt/music_videos"

def get_video_info(filepath):
    # Ask ffprobe to return pure JSON for the video stream and format
    cmd = [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        "-select_streams", "v:0", # Only look at the first video stream
        filepath
    ]
    
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        data = json.loads(result.stdout)

        stream = data.get("streams", [{}])[0]
        fmt = data.get("format", {})

        filename = os.path.basename(filepath)
        codec = stream.get("codec_name", "Unknown")
        
        # Resolution
        width = stream.get("width", 0)
        height = stream.get("height", 0)
        resolution = f"{width}x{height}" if width and height else "Unknown"

        # Bitrate (convert bps to kbps)
        bitrate_bps = fmt.get("bit_rate")
        bitrate = f"{int(bitrate_bps) // 1000} kbps" if bitrate_bps else "Unknown"

        # FPS (ffprobe returns fractions like '24000/1001')
        fps_raw = stream.get("r_frame_rate", "0/0")
        try:
            num, den = map(int, fps_raw.split('/'))
            fps = f"{num/den:.2f}" if den != 0 else "Unknown"
        except:
            fps = "Unknown"

        return [filename, bitrate, resolution, fps, codec]
        
    except Exception:
        return [os.path.basename(filepath), "Error", "Error", "Error", "Error"]

def main():
    # Write to standard output so we can pipe it to a file
    writer = csv.writer(sys.stdout)
    writer.writerow(["Filename", "Bitrate", "Resolution", "FPS", "Codec"])

    if not os.path.exists(DIR):
        print(f"Directory not found: {DIR}", file=sys.stderr)
        return

    for f in os.listdir(DIR):
        if f.lower().endswith(".mkv"):
            filepath = os.path.join(DIR, f)
            row = get_video_info(filepath)
            writer.writerow(row)

if __name__ == "__main__":
    main()