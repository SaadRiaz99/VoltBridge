"""Local simulated gateway matching the device HTTP contract. No hardware required."""
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, HTTPServer

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/devices/meter-1/measurements":
            self.send_error(404)
            return
        payload = json.dumps({"readings": [
            {"metric": "power", "value": 3.2, "unit": "kW",
             "timestamp": datetime.now(timezone.utc).isoformat(), "quality": "good", "simulated": True}
        ]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

if __name__ == "__main__":
    print("Simulated HTTP gateway on http://127.0.0.1:8090; Ctrl+C to stop")
    HTTPServer(("127.0.0.1", 8090), Handler).serve_forever()
