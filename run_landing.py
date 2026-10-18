import http.server
import socketserver
import webbrowser
import os
from pathlib import Path

PORT = 8080
# الانتقال إلى مجلد صفحة الهبوط
os.chdir(Path(__file__).resolve().parent / "landing_page")

Handler = http.server.SimpleHTTPRequestHandler
with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"✅ Landing Page is live at: http://localhost:{PORT}")
    webbrowser.open(f"http://localhost:{PORT}")
    httpd.serve_forever()