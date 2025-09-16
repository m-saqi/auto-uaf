from http.server import BaseHTTPRequestHandler
import json
import requests
from bs4 import BeautifulSoup
import re
import random
import logging
import urllib3

# --- Basic Setup ---
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

    def send_json_response(self, status_code, data):
        self.send_response(status_code)
        self._set_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def handle_request(self):
        logger.info(f"--- Handling new request ---")
        try:
            registration_number = None
            if 'registrationNumber' in self.path:
                params = dict(p.split('=') for p in self.path.split('?')[1].split('&'))
                registration_number = params.get('registrationNumber')
            else: # POST
                content_length = int(self.headers.get('Content-Length', 0))
                if content_length > 0:
                    body = self.rfile.read(content_length)
                    data = json.loads(body)
                    registration_number = data.get('registrationNumber')
            
            if not registration_number:
                self.send_json_response(400, {'success': False, 'message': 'Registration number is required.'})
                return

            success, message, result_data = self.scrape_and_combine(registration_number)
            response_data = {'success': success, 'message': message, 'resultData': result_data}
            self.send_json_response(200, response_data)

        except Exception as e:
            logger.error(f"CRITICAL ERROR in handle_request: {e}", exc_info=True)
            self.send_json_response(500, {'success': False, 'message': f'A fatal server error occurred: {e}'})

    def scrape_and_combine(self, registration_number):
        logger.info(f"--- 1. Starting scrape for {registration_number} ---")

        # --- STEP 1: Fetch from UAF LMS (Primary Source) ---
        logger.info("--- 2. Fetching from UAF LMS... ---")
        lms_success, lms_message, lms_data = self.scrape_uaf_lms(registration_number)
        logger.info(f"--- 3. UAF LMS Result: Success={lms_success}, Courses Found={len(lms_data) if lms_data else 0} ---")

        # --- STEP 2: Fetch from Attendance System (Secondary Source) ---
        logger.info("--- 4. Fetching from Attendance System... ---")
        att_success, att_message, att_data = self.scrape_attendance_system(registration_number)
        logger.info(f"--- 5. Attendance System Result: Success={att_success}, Courses Found={len(att_data) if att_data else 0} ---")

        # --- STEP 3: Combine the results according to your logic ---
        logger.info("--- 6. Combining results... ---")
        
        # The LMS data is the base. It is not changed.
        final_results = lms_data if lms_data else []
        student_name = final_results[0].get('StudentName', '') if final_results else ""
        
        # Create a set of course codes from the LMS data for easy checking.
        lms_course_codes = {course['CourseCode'].upper().strip() for course in final_results}

        # Check attendance data against the LMS data.
        if att_success and att_data:
            unique_courses_added = 0
            for att_course in att_data:
                course_code = att_course.get('CourseCode', '').upper().strip()
                
                # The crucial condition: Add only if the course is not in the LMS list.
                if course_code and course_code not in lms_course_codes:
                    att_course['StudentName'] = student_name
                    final_results.append(att_course)
                    unique_courses_added += 1
            
            logger.info(f"--- 7. Added {unique_courses_added} unique courses from the attendance system. ---")

        if not final_results:
            return False, "Failed to fetch results from any source.", None
        
        return True, "Scraping complete.", final_results

    def scrape_uaf_lms(self, registration_number):
        try:
            # This function contains the logic from your original result-scraper.py
            session = requests.Session()
            session.headers.update({'User-Agent': random.choice(USER_AGENTS)})
            login_url = "https://lms.uaf.edu.pk/login/index.php"
            response = session.get(login_url, timeout=15, verify=False)
            response.raise_for_status()
            
            token_match = re.search(r"document\.getElementById\('token'\)\.value\s*=\s*'([^']+)'", response.text)
            if not token_match: return False, "LMS token not found.", None
            
            result_url = "https://lms.uaf.edu.pk/course/uaf_student_result.php"
            form_data = {'token': token_match.group(1), 'Register': registration_number}
            response = session.post(result_url, data=form_data, timeout=20, verify=False)
            response.raise_for_status()
            
            # Parsing logic for LMS
            soup = BeautifulSoup(response.text, 'html.parser')
            if "no result" in soup.get_text().lower(): return False, "No results found on LMS.", []
            
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
            return True, "LMS scrape successful.", student_results
        except Exception as e:
            logger.error(f"LMS Scraper Failed: {e}")
            return False, f"LMS scrape failed: {e}", None

    def scrape_attendance_system(self, registration_number):
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

            if "StudentDetail.aspx" not in response.url:
                return False, "No results found on attendance system.", []

            # Parsing logic for Attendance System
            soup = BeautifulSoup(response.content, 'html.parser')
            result_table = soup.find('table', {'id': 'ctl00_Main_TabContainer1_tbResultInformation_gvResultInformation'})
            if not result_table: return False, "Result table not found.", []

            student_results = []
            for row in result_table.find_all('tr')[1:]:
                cols = [c.text.strip() for c in row.find_all('td')]
                if len(cols) >= 16:
                    course_code = cols[5]
                    ch_match = re.search(r'-(\d)', course_code)
                    ch_val = ch_match.group(1) if ch_match else '3'
                    
                    student_results.append({
                        'RegistrationNo': registration_number, 'StudentName': "",
                        'Semester': 'Attendance based Courses', # This creates the separate section
                        'TeacherName': cols[4], 'CourseCode': course_code, 'CourseTitle': cols[6],
                        'CreditHours': f"{ch_val}({ch_val}-0)", 'Mid': cols[8], 'Assignment': cols[9],
                        'Final': cols[10], 'Practical': cols[11], 'Total': cols[12], 'Grade': cols[13]
                    })
            return True, "Attendance system scrape successful.", student_results
        except Exception as e:
            logger.error(f"Attendance System Scraper Failed: {e}")
            return False, f"Attendance system scrape failed: {e}", None
