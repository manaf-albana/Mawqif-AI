"""
run_dashboard.py
----------------
ملف ومكتبة تشغيل الداش بورد تلقائياً في الخلفية وفتحه في المتصفح.
"""

import os
import sys
import time
import webbrowser
import http.server
import socketserver
import threading
from urllib.parse import urlencode

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

PORT = 8000
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))

if load_dotenv:
    load_dotenv(os.path.join(ROOT_DIR, ".env"))


class DashBoardHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=ROOT_DIR, **kwargs)

    def log_message(self, format, *args):
        pass


def start_dashboard_server():
    """
    تشغيل خادم الداش بورد في خيط خلفي (Background Thread) وفتح المتصفح آلياً.
    """
    dashboard_path = os.path.join(ROOT_DIR, "dashboard.html")
    channel_id = os.getenv("THINGSPEAK_CHANNEL_ID", "").strip()
    read_key = os.getenv("THINGSPEAK_READ_API_KEY", "").strip()
    query = ""
    if channel_id and not channel_id.startswith("YOUR_"):
        params = {"channel": channel_id}
        if read_key and not read_key.startswith("YOUR_"):
            params["key"] = read_key
        query = "?" + urlencode(params)
    url = f"http://localhost:{PORT}/dashboard.html{query}"

    try:
        socketserver.TCPServer.allow_reuse_address = True
        httpd = socketserver.TCPServer(("", PORT), DashBoardHandler)
        server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
        server_thread.start()
    except Exception:
        url = f"file:///{dashboard_path.replace(os.sep, '/')}{query}"

    time.sleep(0.3)
    webbrowser.open(url)
    return url


def run():
    url = start_dashboard_server()
    print("\n" + "=" * 60)
    print(" 🚀 تم تشغيل سيرفر الداش بورد بنجاح!")
    print(f" 🌐 الرابط المباشر: {url}")
    print(" 📱 تم فتح المتصفح تلقائياً...")
    print("=" * 60 + "\n")
    print("📌 اضغط Ctrl+C للإغلاق.\n")
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 تم الإغلاق.")


if __name__ == "__main__":
    run()
