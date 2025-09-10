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
    c.execute('''
        CREATE TABLE IF NOT EXISTS saved_results (
            id TEXT PRIMARY KEY,
            registration_number TEXT NOT NULL,
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
            # Try multiple endpoints to test connection - updated to HTTPS
            test_urls = [
                'https://lms.uaf.edu.pk/login/index.php',
                'https://lms.uaf.edu.pk/',
                'https://lms.uaf.edu.pk'
            ]
            
            success = False
            message = "UAF LMS is not responding"
            
            for test_url in test_urls:
                try:
                    response = requests.get(test_url, timeout=10, headers={
                        'User-Agent': random.choice(USER_AGENTS),
                    }, verify=True)  # Enable SSL verification
                    
                    # If we get any response (even 500), the server is reachable
                    if response.status_code < 500:
                        success = True
                        message = f"Connection to UAF LMS successful (Status: {response.status_code})"
                        break
                    else:
                        message = f"UAF LMS returned status code: {response.status_code}"
                        
                except requests.exceptions.SSLError:
                    # Try without SSL verification if there's an SSL error
                    try:
                        response = requests.get(test_url, timeout=10, headers={
                            'User-Agent': random.choice(USER_AGENTS),
                        }, verify=False)
                        
                        if response.status_code < 500:
                            success = True
                            message = f"Connection to UAF LMS successful with SSL verification disabled (Status: {response.status_code})"
                            break
                        else:
                            message = f"UAF LMS returned status code: {response.status_code}"
                    except:
                        continue
                except requests.exceptions.RequestException as e:
                    # Continue to next URL if this one fails
                    continue
            
            response_data = {
                'success': success, 
                'message': message
            }
            self.send_success_response(response_data)
            
        except Exception as e:
            response_data = {
                'success': False, 
                'message': f'Connection test error: {str(e)}'
            }
            self.send_success_response(response_data)

    def handle_check_session(self):
        """Check if session exists and has data"""
        try:
            session_id = self.headers.get('Session-Id') or self.headers.get('session_id')
            if not session_id:
                self.send_error_response(400, 'No session ID provided')
                return
                
            session_data = self.load_from_session(session_id)
            if session_data:
                response_data = {
                    'success': True, 
                    'hasData': True,
                    'recordCount': len(session_data),
                    'message': f'Session has {len(session_data)} records'
                }
            else:
                response_data = {
                    'success': True, 
                    'hasData': False,
                    'recordCount': 0,
                    'message': 'Session has no data'
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
            response_data = {'success': True, 'message': 'Session cleared successfully'}
            self.send_success_response(response_data)
            
        except Exception as e:
            self.send_error_response(500, f"Error clearing session: {str(e)}")

    def handle_scrape_single(self):
        """Handle single result scraping for CGPA calculator"""
        try:
            if self.command == 'GET':
                # Handle GET request
                query_params = self.path.split('?')
                if len(query_params) > 1:
                    params = query_params[1].split('&')
                    registration_number = None
                    for param in params:
                        if param.startswith('registrationNumber='):
                            registration_number = param.split('=')[1]
                            break
                    
                    if not registration_number:
                        self.send_error_response(400, 'No registration number provided')
                        return
                    
                    # Scrape results
                    success, message, result_data = self.scrape_uaf_results(registration_number)
                    
                    if success and result_data:
                        response = {
                            'success': success, 
                            'message': message, 
                            'resultData': result_data
                        }
                    else:
                        response = {'success': success, 'message': message, 'resultData': result_data}
                    
                    self.send_success_response(response)
                else:
                    self.send_error_response(400, 'No registration number provided')
            else:
                # Handle POST request
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data)
                
                registration_number = data.get('registrationNumber')
                
                if not registration_number:
                    self.send_error_response(400, 'No registration number provided')
                    return
                
                # Scrape results
                success, message, result_data = self.scrape_uaf_results(registration_number)
                
                if success and result_data:
                    response = {
                        'success': success, 
                        'message': message, 
                        'resultData': result_data
                    }
                else:
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
            timestamp = data.get('timestamp')
            
            if not registration_number or not student_data:
                self.send_error_response(400, 'Missing required fields')
                return
            
            # Initialize database
            init_db()
            
            # Generate unique ID
            result_id = hashlib.md5(f"{registration_number}_{timestamp}".encode()).hexdigest()
            
            # Save to database
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            # Check if result already exists for this registration number and timestamp
            c.execute('''
                SELECT id FROM saved_results 
                WHERE registration_number = ? AND timestamp = ?
            ''', (registration_number, timestamp))
            
            existing_result = c.fetchone()
            
            if existing_result:
                # Update existing record
                c.execute('''
                    UPDATE saved_results 
                    SET student_data = ?
                    WHERE id = ?
                ''', (json.dumps(student_data), existing_result[0]))
            else:
                # Insert new record
                c.execute('''
                    INSERT INTO saved_results (id, registration_number, student_data, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (result_id, registration_number, json.dumps(student_data), timestamp))
            
            conn.commit()
            conn.close()
            
            response_data = {
                'success': True, 
                'message': 'Result saved successfully',
                'id': result_id
            }
            self.send_success_response(response_data)
            
        except Exception as e:
            self.send_error_response(500, f"Error saving result: {str(e)}")

    def handle_load_result(self):
        """Load saved results from database"""
        try:
            query_params = self.path.split('?')
            registration_number = None
            
            if len(query_params) > 1:
                params = query_params[1].split('&')
                for param in params:
                    if param.startswith('registrationNumber='):
                        registration_number = param.split('=')[1]
                        break
            
            if not registration_number:
                self.send_error_response(400, 'No registration number provided')
                return
            
            # Initialize database
            init_db()
            
            # Load from database
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            c.execute('''
                SELECT id, registration_number, student_data, timestamp
                FROM saved_results 
                WHERE registration_number = ?
                ORDER BY timestamp DESC
            ''', (registration_number,))
            
            results = c.fetchall()
            conn.close()
            
            saved_results = []
            for result in results:
                saved_results.append({
                    'id': result[0],
                    'registration_number': result[1],
                    'student_data': json.loads(result[2]),
                    'timestamp': result[3]
                })
            
            response_data = {
                'success': True, 
                'message': 'Results loaded successfully',
                'savedResults': saved_results
            }
            self.send_success_response(response_data)
            
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
            
            # Initialize database
            init_db()
            
            # Delete from database
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            c.execute('DELETE FROM saved_results WHERE id = ?', (result_id,))
            conn.commit()
            conn.close()
            
            response_data = {
                'success': True, 
                'message': 'Result deleted successfully'
            }
            self.send_success_response(response_data)
            
        except Exception as e:
            self.send_error_response(500, f"Error deleting result: {str(e)}")

    def handle_scrape(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)
        
        registration_number = data.get('registrationNumber')
        session_id = data.get('sessionId')
        
        if not registration_number:
            self.send_error_response(400, 'No registration number provided')
            return
            
        if not session_id:
            self.send_error_response(400, 'No session ID provided')
            return
        
        # Scrape results
        success, message, result_data = self.scrape_uaf_results(registration_number)
        
        # Save result to session file if successful
        if success and result_data:
            self.save_to_session(session_id, result_data)
            
        response = {'success': success, 'message': message, 'resultData': result_data}
        self.send_success_response(response)

    def handle_save(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)
        
        filename = data.get('filename', 'student_results')
        session_id = data.get('sessionId')
        
        if not session_id:
            self.send_error_response(400, 'No session ID provided')
            return
            
        # Load results from session file
        session_results = self.load_from_session(session_id)
        
        if session_results:
            # Create Excel file
            wb = Workbook()
            ws = wb.active
            ws.title = "Results"
            
            # Add headers if we have data
            if session_results:
                headers = list(session_results[0].keys())
                ws.append(headers)
                
                # Add data
                for result in session_results:
                    ws.append([result.get(header, '') for header in headers])
            
            # Save to bytes buffer
            output = BytesIO()
            wb.save(output)
            excel_data = output.getvalue()
            
            self.send_response(200)
            self._set_cors_headers()
            self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}.xlsx"')
            self.end_headers()
            
            self.wfile.write(excel_data)
            
            # DO NOT clean up session file - keep it for future downloads
            # Session will be automatically cleaned up after 1 hour
        else:
            self.send_error_response(400, 'No results to save')

    def scrape_uaf_results(self, registration_number):
        """Main function to scrape UAF results"""
        try:
            # Create session
            session = requests.Session()
            session.headers.update({
                'User-Agent': random.choice(USER_AGENTS),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            })
            
            # Step 1: Get login page to extract token - updated to HTTPS
            login_url = "https://lms.uaf.edu.pk/login/index.php"
            try:
                response = session.get(login_url, timeout=15, verify=True)
                
                if response.status_code != 200:
                    # Try without SSL verification if there's an SSL error
                    response = session.get(login_url, timeout=15, verify=False)
                    
                    if response.status_code != 200:
                        return False, f"UAF LMS returned status code {response.status_code}. The server may be down.", None
                    
            except requests.exceptions.SSLError:
                # Try without SSL verification
                try:
                    response = session.get(login_url, timeout=15, verify=False)
                    
                    if response.status_code != 200:
                        return False, f"UAF LMS returned status code {response.status_code}. The server may be down.", None
                        
                except requests.exceptions.RequestException as e:
                    return False, f"Network error: {str(e)}. UAF LMS may be unavailable.", None
            except requests.exceptions.RequestException as e:
                return False, f"Network error: {str(e)}. UAF LMS may be unavailable.", None
            
            # Step 2: Extract JavaScript-generated token
            token = self.extract_js_token(response.text)
            if not token:
                # Try alternative method - look for the hidden input field
                soup = BeautifulSoup(response.text, 'html.parser')
                token_input = soup.find('input', {'id': 'token'})
                if token_input and token_input.get('value'):
                    token = token_input.get('value')
                else:
                    return False, "Could not extract security token from UAF LMS", None
            
            # Step 3: Submit form with correct field names - updated to HTTPS
            result_url = "https://lms.uaf.edu.pk/course/uaf_student_result.php"
            form_data = {
                'token': token,
                'Register': registration_number
            }
            
            headers = {
                'Referer': login_url,
                'Origin': 'https://lms.uaf.edu.pk',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            try:
                response = session.post(result_url, data=form_data, headers=headers, timeout=20, verify=True)
                
                if response.status_code != 200:
                    # Try without SSL verification if there's an SSL error
                    response = session.post(result_url, data=form_data, headers=headers, timeout=20, verify=False)
                    
                    if response.status_code != 200:
                        return False, f"UAF LMS returned status code {response.status_code}", None
                    
            except requests.exceptions.SSLError:
                # Try without SSL verification
                try:
                    response = session.post(result_url, data=form_data, headers=headers, timeout=20, verify=False)
                    
                    if response.status_code != 200:
                        return False, f"UAF LMS returned status code {response.status_code}", None
                        
                except requests.exceptions.RequestException as e:
                    return False, f"Network error during result fetch: {str(e)}", None
            except requests.exceptions.RequestException as e:
                return False, f"Network error during result fetch: {str(e)}", None
            
            # Step 4: Parse results
            return self.parse_uaf_results(response.text, registration_number)
            
        except Exception as e:
            logger.error(f"Unexpected error: {str(e)}")
            return False, f"Unexpected error: {str(e)}", None

    def extract_js_token(self, html_content):
        """Extract JavaScript-generated token from UAF LMS"""
        try:
            # Look for the JavaScript that sets the token value
            js_pattern = r"document\.getElementById\('token'\)\.value\s*=\s*'([^']+)'"
            match = re.search(js_pattern, html_content)
            
            if match:
                return match.group(1)
            
            # Alternative patterns
            patterns = [
                r"token.*value.*=.*'([^']+)'",
                r"value.*=.*'([a-f0-9]{64})'",  # Look for 64-character hex values
                r"id=\"token\" value=\"([^\"]+)\"",  # Direct HTML attribute
            ]
            
            for pattern in patterns:
                match = re.search(pattern, html_content, re.IGNORECASE)
                if match:
                    return match.group(1)
            
            return None
            
        except Exception as e:
            logger.error(f"Token extraction error: {str(e)}")
            return None

    def parse_uaf_results(self, html_content, registration_number):
        """Parse UAF results"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Check if access is blocked or no results
            page_text = soup.get_text().lower()
            if any(blocked_text in page_text for blocked_text in ['blocked', 'access denied', 'not available', 'till result submission', 'suspended']):
                return False, "Access blocked by UAF LMS", None
            
            # Check if no results found
            if "no result" in page_text or "no records" in page_text:
                return False, f"No results found for registration number: {registration_number}", None
            
            # Extract student information
            student_info = {}
            
            # Look for student information in the first table
            info_tables = soup.find_all('table')
            if info_tables:
                # First table usually contains student info
                first_table = info_tables[0]
                rows = first_table.find_all('tr')
                
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) == 2:
                        key = cols[0].text.strip().replace(':', '').replace('#', '').replace(' ', '')
                        value = cols[1].text.strip()
                        student_info[key] = value
            
            # Set defaults
            if 'Registration' not in student_info:
                student_info['Registration'] = registration_number
            
            # Extract results from tables
            student_results = []
            
            # Look for result tables (usually the second or third table)
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                
                # Result tables have many rows and specific headers
                if len(rows) > 5:
                    # Check if first row contains result headers
                    header_row = rows[0]
                    header_text = header_row.get_text().lower()
                    
                    if any(term in header_text for term in ['sr', 'semester', 'course', 'teacher', 'credit', 'mid', 'assignment', 'final', 'practical', 'total', 'grade']):
                        # Process each data row (skip header)
                        for i in range(1, len(rows)):
                            row = rows[i]
                            cols = row.find_all('td')
                            
                            if len(cols) >= 5:  # At least 5 columns expected
                                result_data = {
                                    'RegistrationNo': student_info.get('Registration', registration_number),
                                    'StudentName': student_info.get('StudentFullName', student_info.get('StudentName', '')),
                                    'SrNo': cols[0].text.strip() if len(cols) > 0 else '',
                                    'Semester': cols[1].text.strip() if len(cols) > 1 else '',
                                    'TeacherName': cols[2].text.strip() if len(cols) > 2 else '',
                                    'CourseCode': cols[3].text.strip() if len(cols) > 3 else '',
                                    'CourseTitle': cols[4].text.strip() if len(cols) > 4 else '',
                                    'CreditHours': cols[5].text.strip() if len(cols) > 5 else '',
                                    'Mid': cols[6].text.strip() if len(cols) > 6 else '',
                                    'Assignment': cols[7].text.strip() if len(cols) > 7 else '',
                                    'Final': cols[8].text.strip() if len(cols) > 8 else '',
                                    'Practical': cols[9].text.strip() if len(cols) > 9 else '',
                                    'Total': cols[10].text.strip() if len(cols) > 10 else '',
                                    'Grade': cols[11].text.strip() if len(cols) > 11 else ''
                                }
                                
                                student_results.append(result_data)
            
            if student_results:
                return True, f"Successfully extracted {len(student_results)} records for {registration_number}", student_results
            else:
                # Check if we might have found the data but in a different format
                if "result award list" in page_text.lower():
                    # Try alternative parsing method
                    alt_results = self.alternative_parse(soup, registration_number, student_info)
                    if alt_results:
                        return True, f"Successfully extracted {len(alt_results)} records using alternative method", alt_results
                
                return False, f"No result data found for registration number: {registration_number}", None
                    
        except Exception as e:
            logger.error(f"Error parsing results: {str(e)}")
            return False, f"Error parsing results: {str(e)}", None

    def alternative_parse(self, soup, registration_number, student_info):
        """Alternative parsing method for different table structures"""
        try:
            student_results = []
            
            # Find all tables
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                
                # Look for rows with data (more than 2 columns)
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) >= 6:  # At least 6 columns for a result row
                        # Check if first column is a number (likely a serial number)
                        if cols[0].text.strip().isdigit():
                            result_data = {
                                'RegistrationNo': registration_number,
                                'StudentName': student_info.get('StudentFullName', student_info.get('StudentName', '')),
                                'SrNo': cols[0].text.strip(),
                                'Semester': cols[1].text.strip() if len(cols) > 1 else '',
                                'TeacherName': cols[2].text.strip() if len(cols) > 2 else '',
                                'CourseCode': cols[3].text.strip() if len(cols) > 3 else '',
                                'CourseTitle': cols[4].text.strip() if len(cols) > 4 else '',
                                'CreditHours': cols[5].text.strip() if len(cols) > 5 else '',
                                'Mid': cols[6].text.strip() if len(cols) > 6 else '',
                                'Assignment': cols[7].text.strip() if len(cols) > 7 else '',
                                'Final': cols[8].text.strip() if len(cols) > 8 else '',
                                'Practical': cols[9].text.strip() if len(cols) > 9 else '',
                                'Total': cols[10].text.strip() if len(cols) > 10 else '',
                                'Grade': cols[11].text.strip() if len(cols) > 11 else ''
                            }
                            
                            student_results.append(result_data)
            
            return student_results if student_results else None
            
        except Exception as e:
            logger.error(f"Error in alternative parsing: {str(e)}")
            return None

    def save_to_session(self, session_id, result_data):
        try:
            session_file = os.path.join(DATA_DIR, f"session_{session_id}.json")
            
            # Load existing data or create new array
            if os.path.exists(session_file):
                with open(session_file, 'r') as f:
                    existing_data = json.load(f)
            else:
                existing_data = []
            
            # Add metadata about when this data was added
            for result in result_data:
                result['_scrapedAt'] = datetime.now().isoformat()
            
            # Append new data to existing data
            existing_data.extend(result_data)
            
            # Save back to file
            with open(session_file, 'w') as f:
                json.dump(existing_data, f)
                
            logger.info(f"Saved {len(result_data)} records to session {session_id}, total records: {len(existing_data)}")
                
        except Exception as e:
            logger.error(f"Error saving to session {session_id}: {e}")

    def load_from_session(self, session_id):
        try:
            session_file = os.path.join(DATA_DIR, f"session_{session_id}.json")
            
            if os.path.exists(session_file):
                with open(session_file, 'r') as f:
                    data = json.load(f)
                    
                # Clean up old data (older than 1 hour)
                one_hour_ago = datetime.now() - timedelta(hours=1)
                filtered_data = [
                    item for item in data 
                    if '_scrapedAt' not in item or 
                    datetime.fromisoformat(item['_scrapedAt']) > one_hour_ago
                ]
                
                # If we filtered out data, save the cleaned version
                if len(filtered_data) != len(data):
                    with open(session_file, 'w') as f:
                        json.dump(filtered_data, f)
                    
                return filtered_data
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
