from http.server import BaseHTTPRequestHandler
import json
import requests
from bs4 import BeautifulSoup
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

# User agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
]

class handler(BaseHTTPRequestHandler):
    def _set_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()
        return

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

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

    def handle_request(self):
        try:
            registration_number = None
            if self.command == 'GET':
                parts = self.path.split('?')
                if len(parts) > 1:
                    params = dict(param.split('=') for param in parts[1].split('&'))
                    registration_number = params.get('registrationNumber')
            elif self.command == 'POST':
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data)
                registration_number = data.get('registrationNumber')
            
            if not registration_number:
                self.send_error_response(400, 'No registration number provided')
                return
            
            success, message, result_data = self.scrape_and_combine_results(registration_number)
            response = {'success': success, 'message': message, 'resultData': result_data}
            self.send_success_response(response)
        except Exception as e:
            logger.error(f"Request handling failed: {e}")
            self.send_error_response(500, f"A server error occurred: {e}")

    def scrape_and_combine_results(self, registration_number):
        logger.info(f"Starting robust parallel scrape for {registration_number}")

        # To prevent timeouts, fetch from both sites at the same time.
        with ThreadPoolExecutor(max_workers=2) as executor:
            future_lms = executor.submit(self.scrape_uaf_results, registration_number)
            future_att = executor.submit(self.scrape_attendance_system_results, registration_number)
            
            # Safely get results, preventing a crash if one scraper fails.
            try:
                lms_success, lms_message, lms_data = future_lms.result()
            except Exception as e:
                lms_success, lms_message, lms_data = False, f"LMS scraper function crashed: {e}", None

            try:
                att_success, att_message, att_data = future_att.result()
            except Exception as e:
                att_success, att_message, att_data = False, f"Attendance scraper function crashed: {e}", None

        messages = [f"LMS Status: {lms_message}", f"Attendance System Status: {att_message}"]

        # The UAF LMS data is the primary source. It is never modified.
        final_results = lms_data if lms_data else []
        student_name = final_results[0].get('StudentName', '') if final_results else ""
        processed_course_codes = {course['CourseCode'].upper().strip() for course in final_results}

        # Now, process the attendance data according to your rules.
        if att_success and att_data:
            unique_courses_added = 0
            for att_course in att_data:
                course_code = att_course.get('CourseCode', '').upper().strip()
                
                # Condition: Only add the course if it's NOT already in the primary LMS list.
                if course_code and course_code not in processed_course_codes:
                    att_course['StudentName'] = student_name
                    final_results.append(att_course)
                    processed_course_codes.add(course_code)
                    unique_courses_added += 1
            
            if unique_courses_added > 0:
                messages.append(f"Success: Merged {unique_courses_added} unique course(s) from attendance system.")

        if not final_results:
            return False, " | ".join(messages), None
            
        return True, " | ".join(messages), final_results

    def scrape_uaf_results(self, registration_number):
        try:
            session = requests.Session()
            session.headers.update({'User-Agent': random.choice(USER_AGENTS)})
            login_url = "https://lms.uaf.edu.pk/login/index.php"
            response = session.get(login_url, timeout=15, verify=False)
            response.raise_for_status()
            
            token_match = re.search(r"document\.getElementById\('token'\)\.value\s*=\s*'([^']+)'", response.text)
            if not token_match:
                return False, "Could not find security token.", None
            
            result_url = "https://lms.uaf.edu.pk/course/uaf_student_result.php"
            form_data = {'token': token_match.group(1), 'Register': registration_number}
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
            viewstate = soup.find('input', {'name': '__VIEWSTATE'})['value']
            viewstategenerator = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})['value']
            eventvalidation = soup.find('input', {'name': '__EVENTVALIDATION'})['value']
            
            form_data = {'__VIEWSTATE': viewstate, '__VIEWSTATEGENERATOR': viewstategenerator,
                         '__EVENTVALIDATION': eventvalidation, 'ctl00$Main$txtReg': registration_number,
                         'ctl00$Main$btnShow': 'Access To Student Information'}
            
            response = session.post(base_url, data=form_data, timeout=20)
            response.raise_for_status()

            if "StudentDetail.aspx" in response.url:
                return self.parse_attendance_system_results(response.content, registration_number)
            return False, "No results found.", None
        except Exception as e:
            return False, f"Attendance system request failed: {e}", None

    def parse_uaf_results(self, html_content, registration_number):
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            if "no result" in soup.get_text().lower():
                return False, "No result data found.", None
            
            student_info = {}
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
                    cols = [c.text.strip() for c in row.find_all('td')]
                    if len(cols) >= 12:
                        student_results.append({
                            'RegistrationNo': student_info.get('Registration', registration_number),
                            'StudentName': student_info.get('StudentFullName', ''), 'Semester': cols[1],
                            'TeacherName': cols[2], 'CourseCode': cols[3], 'CourseTitle': cols[4],
                            'CreditHours': cols[5], 'Mid': cols[6], 'Assignment': cols[7],
                            'Final': cols[8], 'Practical': cols[9], 'Total': cols[10], 'Grade': cols[11]
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
                cols = [c.text.strip() for c in row.find_all('td')]
                if len(cols) >= 16:
                    course_code = cols[5]
                    ch_match = re.search(r'-(\d)', course_code)
                    ch_val = ch_match.group(1) if ch_match else '3'
                    
                    student_results.append({
                        'RegistrationNo': registration_number, 'StudentName': "",
                        'Semester': 'Attendance based Courses', # Set semester name as requested
                        'TeacherName': cols[4], 'CourseCode': course_code, 'CourseTitle': cols[6],
                        'CreditHours': f"{ch_val}({ch_val}-0)", 'Mid': cols[8], 'Assignment': cols[9],
                        'Final': cols[10], 'Practical': cols[11], 'Total': cols[12], 'Grade': cols[13]
                    })
            return True, f"Extracted {len(student_results)} records.", student_results
        except Exception as e:
            return False, f"Error parsing attendance HTML.", None
