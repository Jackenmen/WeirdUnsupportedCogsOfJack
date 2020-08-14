"""Script that sends data through socket connection to the bot.

Script requires JSON payload from GitHub's `push` webhook event
to be passed in first argument.

See link below for more info:
https://developer.github.com/webhooks/event-payloads/#push

Note:
This script does not handle webhook requests itself,
it's up to server administrator to choose how to pass data to this script.
I recommend using https://github.com/adnanh/webhook
"""

import json
import socket
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print("This script requires exactly one argument with JSON payload.")
        return 1

    payload = json.loads(sys.argv[1])
    authors = {
        commit_data["author"]["username"]: commit_data["author"]
        for commit_data in payload["commits"]
    }

    with socket.socket() as sock:
        sock.connect(("127.0.0.1", 8888))
        sock.send(json.dumps(authors).encode())

    return 0


if __name__ == "__main__":
    sys.exit(main())
