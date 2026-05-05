from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
import sys


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, format, *args):
        return


def main():
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 4177
    server = ThreadingHTTPServer(("127.0.0.1", port), QuietHandler)
    server.serve_forever()


if __name__ == "__main__":
    main()
