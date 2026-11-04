"""Serve a preview build locally with GitHub Pages' clean-URL behaviour.

    python3 .github/preview/serve.py <site-dir> [--port 8000] [--bind 127.0.0.1]

Mapping (same as GitHub Pages for this site):
  /            -> index.html
  /about       -> about.html          (extensionless path -> .html file)
  /dir/        -> dir/index.html
  /styles.css  -> styles.css          (exact files)
  anything else -> 404.html with HTTP 404
Paths are resolved strictly under <site-dir>; dot-files and traversal are refused. Every
response carries `X-Robots-Tag: noindex`. Stdlib only; binds to localhost by default.
"""
import argparse
import mimetypes
import sys
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import unquote, urlsplit

mimetypes.add_type('text/plain; charset=utf-8', '.txt')
mimetypes.add_type('application/json; charset=utf-8', '.json')
mimetypes.add_type('image/svg+xml', '.svg')


def resolve(root, url_path):
    """Return (file_path, status) for a request path, or (None, 404)."""
    root = Path(root).resolve()
    path = unquote(urlsplit(url_path).path)
    if '\x00' in path or any(part.startswith('.') and part not in ('.well-known',) for part in path.split('/') if part):
        return None, 404
    rel = path.lstrip('/')
    candidates = []
    if rel == '' or rel.endswith('/'):
        candidates.append(rel + 'index.html')
    else:
        candidates.append(rel)
        if '.' not in rel.rsplit('/', 1)[-1]:
            candidates.append(rel + '.html')
            candidates.append(rel + '/index.html')
    for candidate in candidates:
        target = (root / candidate).resolve()
        if root not in target.parents or not target.is_file():
            continue
        return target, 200
    return None, 404


class PreviewHandler(SimpleHTTPRequestHandler):
    server_version = 'DemandRangePreview/1'

    def do_GET(self):
        self._serve(head=False)

    def do_HEAD(self):
        self._serve(head=True)

    def _serve(self, head):
        root = Path(self.directory)
        target, status = resolve(root, self.path)
        if target is None:
            fallback = root / '404.html'
            target = fallback if fallback.is_file() else None
        body = target.read_bytes() if target else b'404 Not Found\n'
        ctype = (mimetypes.guess_type(str(target))[0] if target else None) or 'application/octet-stream'
        if ctype.startswith('text/') and 'charset' not in ctype:
            ctype += '; charset=utf-8'
        self.send_response(status)
        self.send_header('Content-Type', ctype)
        self.send_header('Content-Length', str(len(body)))
        self.send_header('X-Robots-Tag', 'noindex, nofollow')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        if not head:
            self.wfile.write(body)

    def log_message(self, fmt, *args):
        sys.stderr.write('%s %s\n' % (self.address_string(), fmt % args))


def make_server(site_dir, bind='127.0.0.1', port=8000):
    site_dir = Path(site_dir).resolve()
    if not (site_dir / 'index.html').is_file():
        raise SystemExit(f'serve: no index.html under {site_dir}')
    handler = partial(PreviewHandler, directory=str(site_dir))
    return ThreadingHTTPServer((bind, port), handler)


def main(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('site_dir')
    parser.add_argument('--port', type=int, default=8000)
    parser.add_argument('--bind', default='127.0.0.1')
    args = parser.parse_args(argv[1:])
    server = make_server(args.site_dir, args.bind, args.port)
    host, port = server.server_address[:2]
    print(f'Preview of {Path(args.site_dir).resolve()} at http://{host}:{port}/  (Ctrl+C to stop)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
