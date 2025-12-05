from http.server import BaseHTTPRequestHandler
import urllib.parse
import base64

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 1. Get the data sent from the website
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            
            # 2. Parse the Form Data
            fields = urllib.parse.parse_qs(post_data.decode('utf-8'))
            
            # Get filename and content (Handle lists returned by parse_qs)
            filename = fields.get('filename', ['download.bin'])[0]
            data_uri = fields.get('fileData', [''])[0]
            
            if not data_uri:
                self.send_error(400, "No file data provided")
                return

            # 3. Process Data URI (Format: data:mime/type;base64,.....)
            header, content = data_uri.split(',', 1)
            mime_type = header.split(':')[1].split(';')[0]
            
            # Decode the base64 content back to binary
            file_content = base64.b64decode(content)

            # 4. Send it back as a downloadable file
            self.send_response(200)
            self.send_header('Content-Type', mime_type)
            # This header forces the Android Download Manager to wake up
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', str(len(file_content)))
            self.end_headers()
            
            self.wfile.write(file_content)
            
        except Exception as e:
            self.send_response(500)
            self.end_headers()
            self.wfile.write(str(e).encode())
