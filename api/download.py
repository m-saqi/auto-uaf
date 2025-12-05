from http.server import BaseHTTPRequestHandler
import urllib.parse
import base64

class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        try:
            # 1. Read the length of the data sent
            content_length = int(self.headers.get('Content-Length', 0))
            if content_length == 0:
                self.send_error(400, "No data received")
                return

            # 2. Read the data
            post_data = self.rfile.read(content_length)
            
            # 3. Parse the data (Handle large data carefully)
            # We decode utf-8 and parse. 
            fields = urllib.parse.parse_qs(post_data.decode('utf-8'))
            
            filename = fields.get('filename', ['download.bin'])[0]
            data_uri = fields.get('fileData', [''])[0]
            
            if not data_uri or ',' not in data_uri:
                self.send_response(400)
                self.end_headers()
                self.wfile.write(b"Invalid File Data")
                return

            # 4. Extract Base64 content
            # Format is usually: "data:application/pdf;base64,JVBERi..."
            header, content = data_uri.split(',', 1)
            
            # Determine mime-type from the header (e.g., application/pdf)
            mime_type = "application/octet-stream"
            if ':' in header and ';' in header:
                mime_type = header.split(':')[1].split(';')[0]

            # 5. Decode File
            file_content = base64.b64decode(content)

            # 6. Send Response Headers (This triggers the Download Manager)
            self.send_response(200)
            self.send_header('Content-Type', mime_type)
            self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
            self.send_header('Content-Length', str(len(file_content)))
            self.end_headers()
            
            # 7. Write File
            self.wfile.write(file_content)
            
        except Exception as e:
            # If something fails, send a text file with the error so you can see it
            self.send_response(500)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            error_msg = f"Server Error: {str(e)}"
            self.wfile.write(error_msg.encode())
