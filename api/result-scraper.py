from http.server import BaseHTTPRequestHandler
import json
import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from io import BytesIO
import os
import time
import re
import random
import logging
import uuid
from datetime import datetime, timedelta
import sqlite3
import hashlib
import urllib3

# Suppress InsecureRequestWarning for requests made with verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use /tmp directory for session storage
DATA_DIR = "/tmp/uaftools_data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Database path
DB_PATH = os.path.join(DATA_DIR, "saved_results.db")

# Initialize database
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # ADDED fileName column to store the user-defined name for the result
    c.execute('''
        CREATE TABLE IF NOT EXISTS saved_results (
            id TEXT PRIMARY KEY,
            registration_number TEXT NOT NULL,
            file_name TEXT NOT NULL,
            student_data TEXT NOT NULL,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_registration_number 
        ON saved_results (registration_number)
    ''')
    conn.commit()
    conn.close()

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
            if 'action=test' in self.path:
                self.handle_test_connection()
            elif 'action=check_session' in self.path:
                self.handle_check_session()
            elif 'action=scrape_single' in self.path:
                self.handle_scrape_single()
            elif 'action=load_result' in self.path or 'load_result' in self.path:
                self.handle_load_result()
            else:
                self.send_response(404)
                self._set_cors_headers()
                self.end_headers()
        except Exception as e:
            self.send_error_response(500, f"Server error: {str(e)}")

    def do_POST(self):
        try:
            if 'action=scrape' in self.path:
                self.handle_scrape()
            elif 'action=save' in self.path or 'save_result' in self.path:
                self.handle_save_result()
            elif 'action=clear_session' in self.path:
                self.handle_clear_session()
            elif 'action=scrape_single' in self.path:
                self.handle_scrape_single()
            else:
                self.send_response(404)
                self._set_cors_headers()
                self.end_headers()
        except Exception as e:
            self.send_error_response(500, f"Server error: {str(e)}")

    def do_DELETE(self):
        try:
            if 'action=save' in self.path or 'save_result' in self.path:
                self.handle_delete_saved_result()
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

    def handle_test_connection(self):
        """Test connection to UAF LMS - simplified version"""
        try:
            test_urls = [
                'https://lms.uaf.edu.pk/login/index.php',
                'https://lms.uaf.edu.pk/',
                'https://lms.uaf.edu.pk'
            ]
            
            success = False
            message = "UAF LMS is not responding"
            
            for test_url in test_urls:
                try:
                    # CORRECTED: Changed verify=True to verify=False to match the working scraper logic.
                    response = requests.get(test_url, timeout=10, headers={'User-Agent': random.choice(USER_AGENTS)}, verify=False)
                    if response.status_code < 500:
                        success = True
                        message = f"Connection to UAF LMS successful (Status: {response.status_code})"
                        break
                    else:
                        message = f"UAF LMS returned status code: {response.status_code}"
                except requests.exceptions.RequestException:
                    continue
            
            response_data = {'success': success, 'message': message}
            self.send_success_response(response_data)
        except Exception as e:
            self.send_success_response({'success': False, 'message': f'Connection test error: {str(e)}'})

    def handle_check_session(self):
        """Check if session exists and has data"""
        try:
            session_id = self.headers.get('Session-Id') or self.headers.get('session_id')
            if not session_id:
                self.send_error_response(400, 'No session ID provided')
                return
            session_data = self.load_from_session(session_id)
            has_data = bool(session_data)
            response_data = {
                'success': True, 
                'hasData': has_data,
                'recordCount': len(session_data) if has_data else 0,
                'message': f'Session has {len(session_data)} records' if has_data else 'Session has no data'
            }
            self.send_success_response(response_data)
        except Exception as e:
            self.send_error_response(500, f"Error checking session: {str(e)}")

    def handle_clear_session(self):
        """Manually clear a session"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            session_id = data.get('sessionId')
            if not session_id:
                self.send_error_response(400, 'No session ID provided')
                return
            self.delete_session(session_id)
            self.send_success_response({'success': True, 'message': 'Session cleared successfully'})
        except Exception as e:
            self.send_error_response(500, f"Error clearing session: {str(e)}")

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

    def handle_save_result(self):
        """Save result data to database"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            
            registration_number = data.get('registrationNumber')
            student_data = data.get('studentData')
            file_name = data.get('fileName')
            
            if not all([registration_number, student_data, file_name]):
                self.send_error_response(400, 'Missing required fields')
                return
            
            init_db()
            result_id = hashlib.md5(f"{registration_number}_{file_name}".encode()).hexdigest()
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            c.execute('SELECT id FROM saved_results WHERE id = ?', (result_id,))
            if c.fetchone():
                c.execute('UPDATE saved_results SET student_data = ?, timestamp = CURRENT_TIMESTAMP WHERE id = ?', (json.dumps(student_data), result_id))
            else:
                c.execute('INSERT INTO saved_results (id, registration_number, file_name, student_data) VALUES (?, ?, ?, ?)', (result_id, registration_number, file_name, json.dumps(student_data)))
            
            conn.commit()
            conn.close()
            self.send_success_response({'success': True, 'message': 'Result saved successfully', 'id': result_id})
        except Exception as e:
            self.send_error_response(500, f"Error saving result: {str(e)}")

    def handle_load_result(self):
        """Load saved results from database"""
        try:
            query_params = self.path.split('?')
            registration_number = None
            if len(query_params) > 1:
                params = dict(param.split('=') for param in query_params[1].split('&'))
                registration_number = params.get('registrationNumber')

            if not registration_number:
                self.send_error_response(400, 'No registration number provided')
                return
            
            init_db()
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('SELECT id, registration_number, file_name, student_data, timestamp FROM saved_results WHERE registration_number = ? ORDER BY timestamp DESC', (registration_number,))
            results = c.fetchall()
            conn.close()
            
            saved_results = [{'id': r[0], 'registration_number': r[1], 'fileName': r[2], 'student_data': json.loads(r[3]), 'timestamp': r[4]} for r in results]
            self.send_success_response({'success': True, 'message': 'Results loaded successfully', 'savedResults': saved_results})
        except Exception as e:
            self.send_error_response(500, f"Error loading results: {str(e)}")

    def handle_delete_saved_result(self):
        """Delete a saved result from database"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            result_id = data.get('id')
            if not result_id:
                self.send_error_response(400, 'No result ID provided')
                return
            
            init_db()
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            c.execute('DELETE FROM saved_results WHERE id = ?', (result_id,))
            conn.commit()
            conn.close()
            self.send_success_response({'success': True, 'message': 'Result deleted successfully'})
        except Exception as e:
            self.send_error_response(500, f"Error deleting result: {str(e)}")

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

    # UPDATED: Removed the 1-hour retention limit. Note that Vercel's /tmp is ephemeral.
    def load_from_session(self, session_id):
        try:
            session_file = os.path.join(DATA_DIR, f"session_{session_id}.json")
            if os.path.exists(session_file):
                with open(session_file, 'r') as f:
                    return json.load(f)
            return None
        except Exception as e:
            logger.error(f"Error loading from session {session_id}: {e}")
            return None

    def delete_session(self, session_id):
        try:
            session_file = os.path.join(DATA_DIR, f"session_{session_id}.json")
            if os.path.exists(session_file):
                os.remove(session_file)
                logger.info(f"Deleted session {session_id}")
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")

# Initialize database when module is loaded
init_db()
