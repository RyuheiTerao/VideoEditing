import sys
import subprocess
import os
import whisper
import tempfile

if len(sys.argv) < 2:
    print("YouTubeのURLを指定してください。")
    sys.exit(1)

url = sys.argv[1]
workdir = "/app/work"
os.makedirs(workdir, exist_ok=True)

video_path = f"{workdir}/video.mp4"
sub_path = f"{workdir}/video.srt"
output_path = f"{workdir}/video_subtitled.mp4"

print("=== 1. 動画をダウンロード中... ===")
subprocess.run(["yt-dlp", "-f", "mp4", "-o", video_path, url], check=True)

print("=== 2. Whisperで日本語字幕を生成中... ===")
model = whisper.load_model("medium")
result = model.transcribe(video_path, language="ja")

with open(sub_path, "w", encoding="utf-8") as f:
    for i, segment in enumerate(result["segments"], start=1):
        start = segment["start"]
        end = segment["end"]
        text = segment["text"].strip()

        def format_time(t):
            h = int(t // 3600)
            m = int((t % 3600) // 60)
            s = int(t % 60)
            ms = int((t * 1000) % 1000)
            return f"{h:02}:{m:02}:{s:02},{ms:03}"

        f.write(f"{i}\n{format_time(start)} --> {format_time(end)}\n{text}\n\n")

print("=== 3. SRT → ASS形式に変換（字幕スタイル適用） ===")
ass_path = f"{workdir}/styled_subs.ass"
style_header = """[Script Info]
ScriptType: v4.00+
Collisions: Normal
PlayResX: 1920
PlayResY: 1080
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,Noto Sans CJK JP,60,&H00FFFFFF,&H000000FF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,4,0,2,60,60,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""

# SRT → ASS 変換
with open(sub_path, "r", encoding="utf-8") as srt, open(ass_path, "w", encoding="utf-8") as ass:
    ass.write(style_header)
    lines = srt.read().splitlines()
    i = 0
    while i < len(lines):
        if lines[i].isdigit():
            start_time = lines[i+1].split(" --> ")[0]
            end_time = lines[i+1].split(" --> ")[1]
            text = lines[i+2]
            # SRTの時間フォーマットをASS用に変換
            def srt_to_ass_time(t):
                h, m, s_ms = t.split(":")
                s, ms = s_ms.split(",")
                return f"{int(h)}:{int(m)}:{int(s)}.{int(ms)//10:02}"
            ass.write(f"Dialogue: 0,{srt_to_ass_time(start_time)},{srt_to_ass_time(end_time)},Default,,0,0,0,,{text}\n")
            i += 3
        else:
            i += 1

print("=== 4. 字幕を動画に埋め込み中（デザイン適用） ===")
subprocess.run([
    "ffmpeg", "-i", video_path, "-vf", f"ass={ass_path}",
    "-c:a", "copy", output_path
], check=True)

print("=== 完了！ ===")
print(f"日本語字幕付き動画: {output_path}")
