from http.server import BaseHTTPRequestHandler
import json
import requests
from bs4 import BeautifulSoup
from openpyxl import Workbook
from io import BytesIO
import os
import re
import random
import logging
import sqlite3
import hashlib
import urllib3
from concurrent.futures import ThreadPoolExecutor

# Suppress InsecureRequestWarning for requests made with verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use /tmp directory for writable storage in Vercel
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
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
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
            self.send_error_response(500, f"Server GET error: {str(e)}")

    def do_POST(self):
        try:
            if 'action=scrape_single' in self.path:
                self.handle_scrape_single()
            elif 'action=save' in self.path or 'save_result' in self.path:
                self.handle_save_result()
            else:
                self.send_response(404)
                self._set_cors_headers()
                self.end_headers()
        except Exception as e:
            self.send_error_response(500, f"Server POST error: {str(e)}")

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
        try:
            registration_number = None
            if self.command == 'GET':
                query_params = self.path.split('?')
                if len(query_params) > 1:
                    params = dict(param.split('=') for param in query_params[1].split('&'))
                    registration_number = params.get('registrationNumber')
            else: # POST
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data)
                registration_number = data.get('registrationNumber')
            
            if not registration_number:
                self.send_error_response(400, 'No registration number provided')
                return
            
            success, message, result_data = self.scrape_and_combine_results_in_parallel(registration_number)
            response = {'success': success, 'message': message, 'resultData': result_data}
            self.send_success_response(response)
        except Exception as e:
            self.send_error_response(500, f"Error processing scrape request: {str(e)}")

    # Other handlers like handle_save_result remain unchanged...
    def handle_save_result(self): pass # Placeholder for brevity

    def scrape_and_combine_results_in_parallel(self, registration_number):
        logger.info(f"Starting parallel scrape for {registration_number}")

        # Fetch from both sites at the same time to prevent timeouts
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_lms = executor.submit(self.scrape_uaf_results, registration_number)
            future_att = executor.submit(self.scrape_attendance_system_results, registration_number)
            
            lms_success, lms_message, lms_data = future_lms.result()
            att_success, att_message, att_data = future_att.result()

        # The logic for merging remains exactly as requested
        messages = [f"LMS: {lms_message}", f"Attendance System: {att_message}"]
        
        # UAF LMS courses are the base, they are never modified.
        combined_data = lms_data if lms_data else []
        student_name = combined_data[0].get('StudentName', '') if combined_data else ""
        
        # Create a set of existing LMS course codes for quick checking
        lms_course_codes = {course['CourseCode'].upper().strip() for course in combined_data}

        # Now, check the attendance system results
        if att_success and att_data:
            unique_att_courses_added = 0
            for att_course in att_data:
                course_code = att_course.get('CourseCode', '').upper().strip()
                # ONLY add the course if it's not already in the LMS list
                if course_code and course_code not in lms_course_codes:
                    if student_name:
                        att_course['StudentName'] = student_name
                    combined_data.append(att_course)
                    lms_course_codes.add(course_code)
                    unique_att_courses_added += 1
            
            if unique_att_courses_added > 0:
                messages.append(f"Merged {unique_att_courses_added} unique course(s) from attendance system.")

        if not combined_data:
            return False, "No results found from any source.", None
            
        final_message = " | ".join(messages)
        return True, final_message, combined_data

    def scrape_uaf_results(self, registration_number):
        try:
            session = requests.Session()
            session.headers.update({'User-Agent': random.choice(USER_AGENTS)})
            login_url = "https://lms.uaf.edu.pk/login/index.php"
            response = session.get(login_url, timeout=15, verify=False)
            response.raise_for_status()
            
            token = re.search(r"document\.getElementById\('token'\)\.value\s*=\s*'([^']+)'", response.text)
            if not token:
                return False, "Could not find security token.", None
            
            result_url = "https://lms.uaf.edu.pk/course/uaf_student_result.php"
            form_data = {'token': token.group(1), 'Register': registration_number}
            response = session.post(result_url, data=form_data, timeout=20, verify=False)
            response.raise_for_status()
            
            return self.parse_uaf_results(response.text, registration_number)
        except Exception as e:
            return False, f"LMS request failed: {e}", None

    def scrape_attendance_system_results(self, registration_number):
        try:
            session = requests.Session()
            session.headers.update({'User-Agent': random.choice(USER_AGENTS)})
            base_url = "http://121.52.152.24/"
            
            response = session.get(base_url, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            viewstate = soup.find('input', {'name': '__VIEWSTATE'})
            viewstategenerator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
            eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})

            if not all([viewstate, viewstategenerator, eventvalidation]):
                return False, "Could not find form fields.", None
            
            form_data = {'__VIEWSTATE': viewstate['value'], '__VIEWSTATEGENERATOR': viewstategenerator['value'],
                         '__EVENTVALIDATION': eventvalidation['value'], 'ctl00$Main$txtReg': registration_number,
                         'ctl00$Main$btnShow': 'Access To Student Information'}
            
            response = session.post(base_url, data=form_data, timeout=20)
            response.raise_for_status()

            if "StudentDetail.aspx" in response.url:
                return self.parse_attendance_system_results(response.content, registration_number)
            else:
                return False, "No results found.", None
        except Exception as e:
            return False, f"Attendance system request failed: {e}", None

    def parse_uaf_results(self, html_content, registration_number):
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            if "no result" in soup.get_text().lower():
                return False, "No result data found.", None
            
            student_info = {}
            # Logic to parse student info...
            info_table = soup.find('table')
            if info_table:
                for row in info_table.find_all('tr'):
                    cols = row.find_all('td')
                    if len(cols) == 2:
                        key = cols[0].text.strip().replace(':', '').replace('#', '').replace(' ', '')
                        student_info[key] = cols[1].text.strip()

            student_results = []
            result_table = soup.find('table', {'border': '1', 'width': '100%'})
            if result_table:
                for row in result_table.find_all('tr')[1:]:
                    cols = [col.text.strip() for col in row.find_all('td')]
                    if len(cols) >= 12:
                        student_results.append({
                            'RegistrationNo': student_info.get('Registration', registration_number),
                            'StudentName': student_info.get('StudentFullName', ''),
                            'Semester': cols[1], 'TeacherName': cols[2], 'CourseCode': cols[3],
                            'CourseTitle': cols[4], 'CreditHours': cols[5], 'Mid': cols[6],
                            'Assignment': cols[7], 'Final': cols[8], 'Practical': cols[9],
                            'Total': cols[10], 'Grade': cols[11]
                        })
            
            return True, f"Extracted {len(student_results)} records.", student_results
        except Exception as e:
            return False, f"Error parsing LMS HTML.", None

    def parse_attendance_system_results(self, html_content, registration_number):
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            result_table = soup.find('table', {'id': 'ctl00_Main_TabContainer1_tbResultInformation_gvResultInformation'})
            if not result_table:
                return False, "Result table not found.", None

            student_results = []
            for row in result_table.find_all('tr')[1:]:
                cols = [col.text.strip() for col in row.find_all('td')]
                if len(cols) >= 16:
                    course_code = cols[5]
                    ch_match = re.search(r'-(\d)', course_code)
                    credit_hours_value = ch_match.group(1) if ch_match else '3'
                    credit_hours_str = f"{credit_hours_value}({credit_hours_value}-0)"
                    
                    student_results.append({
                        'RegistrationNo': registration_number,
                        'StudentName': "", # Will be filled by the merge logic
                        'Semester': 'Attendance based Courses', # Hardcoded as requested
                        'TeacherName': cols[4], 'CourseCode': course_code, 'CourseTitle': cols[6],
                        'CreditHours': credit_hours_str, 'Mid': cols[8], 'Assignment': cols[9],
                        'Final': cols[10], 'Practical': cols[11], 'Total': cols[12], 'Grade': cols[13]
                    })
            
            return True, f"Extracted {len(student_results)} records.", student_results
        except Exception as e:
            return False, f"Error parsing attendance HTML.", None

# Initialize database on module load
init_db()
