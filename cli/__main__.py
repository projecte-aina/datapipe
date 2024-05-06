import sys

from cli.add_yt_channel import add_yt_channel
from cli.add_ccma_json import add_ccma_json
from cli.add_yt_video import add_yt_video
from cli.add_yt_playlist import add_yt_playlist


def main():
    if len(sys.argv) < 2:
        print("Expected at least one argument")
        exit()
    
    command = sys.argv[1]
    if command == "add-channel" and sys.argv[2]:
        add_yt_channel(sys.argv[2])
    if command == "add-ccma-json" and sys.argv[2]:
        add_ccma_json(sys.argv[2])
    if command == "add-yt-video" and sys.argv[2]:
        add_yt_video(sys.argv[2])
    if command == "add-yt-playlist" and sys.argv[2]:
        add_yt_playlist(sys.argv[2])

if __name__ == "__main__":
    main()
