from http.server import BaseHTTPRequestHandler
import json
import requests
from bs4 import BeautifulSoup
import os
import time
import re
import random
import logging
import urllib3

# Suppress InsecureRequestWarning for requests made with verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# User agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0'
]

class handler(BaseHTTPRequestHandler):
    def _set_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
    
    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()
        return

    def do_GET(self):
        try:
            if 'action=scrape_single' in self.path:
                self.handle_scrape_single()
            else:
                self.send_response(404)
                self._set_cors_headers()
                self.end_headers()
        except Exception as e:
            self.send_error_response(500, f"Server error: {str(e)}")

    def do_POST(self):
        try:
            if 'action=scrape_single' in self.path:
                self.handle_scrape_single()
            else:
                self.send_response(404)
                self._set_cors_headers()
                self.end_headers()
        except Exception as e:
            self.send_error_response(500, f"Server error: {str(e)}")

    def send_error_response(self, status_code, message):
        self.send_response(status_code)
        self._set_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        response = {'success': False, 'message': message}
        self.wfile.write(json.dumps(response).encode())

    def send_success_response(self, data):
        self.send_response(200)
        self._set_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def handle_scrape_single(self):
        """Handle single result scraping for CGPA calculator"""
        try:
            if self.command == 'GET':
                query_params = self.path.split('?')
                if len(query_params) > 1:
                    params = dict(param.split('=') for param in query_params[1].split('&'))
                    registration_number = params.get('registrationNumber')
                else:
                    self.send_error_response(400, 'No registration number provided')
                    return
            else: # POST
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data)
                registration_number = data.get('registrationNumber')
            
            if not registration_number:
                self.send_error_response(400, 'No registration number provided')
                return
            
            success, message, result_data = self.scrape_uaf_results(registration_number)
            response = {'success': success, 'message': message, 'resultData': result_data}
            self.send_success_response(response)
        except Exception as e:
            self.send_error_response(500, f"Error scraping single result: {str(e)}")

    def scrape_uaf_results(self, registration_number):
        """Main function to scrape UAF results"""
        try:
            session = requests.Session()
            session.headers.update({'User-Agent': random.choice(USER_AGENTS)})
            login_url = "https://lms.uaf.edu.pk/login/index.php"
            response = session.get(login_url, timeout=15, verify=False) # Often UAF LMS has cert issues
            if response.status_code != 200:
                return False, f"UAF LMS returned status code {response.status_code}. The server may be down.", None
            
            token = self.extract_js_token(response.text)
            if not token:
                soup = BeautifulSoup(response.text, 'html.parser')
                token_input = soup.find('input', {'id': 'token'})
                token = token_input.get('value') if token_input else None
            if not token:
                return False, "Could not extract security token from UAF LMS", None
            
            result_url = "https://lms.uaf.edu.pk/course/uaf_student_result.php"
            form_data = {'token': token, 'Register': registration_number}
            headers = {'Referer': login_url, 'Origin': 'https://lms.uaf.edu.pk'}
            response = session.post(result_url, data=form_data, headers=headers, timeout=20, verify=False)
            if response.status_code != 200:
                return False, f"UAF LMS returned status code {response.status_code}", None
            
            return self.parse_uaf_results(response.text, registration_number)
        except requests.exceptions.RequestException as e:
            return False, f"Network error: {str(e)}. UAF LMS may be unavailable.", None
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return False, f"Unexpected error: {str(e)}", None

    def extract_js_token(self, html_content):
        """Extract JavaScript-generated token from UAF LMS"""
        match = re.search(r"document\.getElementById\('token'\)\.value\s*=\s*'([^']+)'", html_content)
        return match.group(1) if match else None

    def parse_uaf_results(self, html_content, registration_number):
        """Parse UAF results"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            page_text = soup.get_text().lower()
            if any(text in page_text for text in ['blocked', 'access denied', 'not available']):
                return False, "Access blocked by UAF LMS", None
            if "no result" in page_text or "no records" in page_text:
                return False, f"No results found for registration number: {registration_number}", None
            
            student_info = {}
            info_tables = soup.find_all('table')
            if info_tables:
                for row in info_tables[0].find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) == 2:
                        key = cols[0].text.strip().replace(':', '').replace('#', '').replace(' ', '')
                        student_info[key] = cols[1].text.strip()
            
            student_results = []
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                if len(rows) > 5 and 'sr' in rows[0].get_text().lower():
                    for i in range(1, len(rows)):
                        cols = [col.text.strip() for col in rows[i].find_all('td')]
                        if len(cols) >= 5:
                            student_results.append({
                                'RegistrationNo': student_info.get('Registration', registration_number),
                                'StudentName': student_info.get('StudentFullName', student_info.get('StudentName', '')),
                                'SrNo': cols[0] if len(cols) > 0 else '', 'Semester': cols[1] if len(cols) > 1 else '',
                                'TeacherName': cols[2] if len(cols) > 2 else '', 'CourseCode': cols[3] if len(cols) > 3 else '',
                                'CourseTitle': cols[4] if len(cols) > 4 else '', 'CreditHours': cols[5] if len(cols) > 5 else '',
                                'Mid': cols[6] if len(cols) > 6 else '', 'Assignment': cols[7] if len(cols) > 7 else '',
                                'Final': cols[8] if len(cols) > 8 else '', 'Practical': cols[9] if len(cols) > 9 else '',
                                'Total': cols[10] if len(cols) > 10 else '', 'Grade': cols[11] if len(cols) > 11 else ''
                            })
            
            if student_results:
                return True, f"Successfully extracted {len(student_results)} records", student_results
            return False, f"No result data found for: {registration_number}", None
        except Exception as e:
            return False, f"Error parsing results: {str(e)}", None
