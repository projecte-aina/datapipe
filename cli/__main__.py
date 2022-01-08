import sys

from cli.add_yt_channel import add_yt_channel

def main():
    if len(sys.argv) < 2:
        print("Expected at least one argument")
        exit()
    
    command = sys.argv[1]
    if command == "add-channel" and sys.argv[2]:
        add_yt_channel(sys.argv[2])

if __name__ == "__main__":
    main()
