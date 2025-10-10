from http.server import BaseHTTPRequestHandler
import json
import requests
from bs4 import BeautifulSoup
import re
import random
import logging
import urllib3
from urllib.parse import urlparse, parse_qs

# Suppress InsecureRequestWarning for requests made with verify=False
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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

    def handle_request(self):
        try:
            parsed_path = urlparse(self.path)
            query = parse_qs(parsed_path.query)
            action = query.get('action', [None])[0]

            if action == 'scrape_single':
                self.handle_scrape_lms()
            elif action == 'scrape_attendance':
                self.handle_scrape_attendance()
            else:
                self.send_error_response(404, "Action not found.")
        except Exception as e:
            logger.error(f"Error handling request: {e}")
            self.send_error_response(500, f"Server error: {str(e)}")

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()
        
    def get_registration_number(self):
        """Extracts registration number from the request."""
        if self.command == 'GET':
            parsed_path = urlparse(self.path)
            query = parse_qs(parsed_path.query)
            return query.get('registrationNumber', [None])[0]
        elif self.command == 'POST':
            try:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                return json.loads(post_data).get('registrationNumber')
            except (json.JSONDecodeError, TypeError):
                return None
        return None

    def send_error_response(self, status_code, message):
        self.send_response(status_code)
        self._set_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps({'success': False, 'message': message}).encode())

    def send_success_response(self, data):
        self.send_response(200)
        self._set_cors_headers()
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    # --- UAF LMS SCRAPER ---
    def handle_scrape_lms(self):
        reg_no = self.get_registration_number()
        if not reg_no:
            self.send_error_response(400, 'Registration number not provided.')
            return
        success, message, data = self.scrape_uaf_results(reg_no)
        self.send_success_response({'success': success, 'message': message, 'resultData': data})

    # --- ATTENDANCE SYSTEM SCRAPER ---
    def handle_scrape_attendance(self):
        reg_no = self.get_registration_number()
        if not reg_no:
            self.send_error_response(400, 'Registration number not provided.')
            return
        success, message, data = self.scrape_student_attendance(reg_no)
        self.send_success_response({'success': success, 'message': message, 'resultData': data})

    # --- SCRAPING LOGIC ---
    def scrape_uaf_results(self, registration_number):
        session = requests.Session()
        session.headers.update({'User-Agent': random.choice(USER_AGENTS)})
        for scheme in ['http', 'https']:
            try:
                base_url = f"{scheme}://lms.uaf.edu.pk"
                login_url = f"{base_url}/login/index.php"
                response = session.get(login_url, timeout=15, verify=False)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.text, 'html.parser')
                token_input = soup.find('input', {'id': 'token'})
                token = token_input.get('value') if token_input else self.extract_js_token(response.text)

                if not token: continue

                result_url = f"{base_url}/course/uaf_student_result.php"
                post_response = session.post(result_url, data={'token': token, 'Register': registration_number}, headers={'Referer': login_url, 'Origin': base_url}, timeout=20, verify=False)
                if post_response.status_code == 200:
                    return self.parse_uaf_results(post_response.text, registration_number)
            except requests.exceptions.RequestException as e:
                logger.warning(f"LMS connection via {scheme} failed: {e}")
                continue
        return False, "Could not connect to UAF LMS. The server may be down or offline.", None

    def extract_js_token(self, html_content):
        match = re.search(r"document\.getElementById\('token'\)\.value\s*=\s*'([^']+)'", html_content)
        return match.group(1) if match else None

    def parse_uaf_results(self, html, reg_no):
        soup = BeautifulSoup(html, 'html.parser')
        if "no result" in soup.get_text().lower() or "no records" in soup.get_text().lower():
            return False, f"No results found for registration number: {reg_no}", None
        
        student_info = {}
        info_table = soup.find('table')
        if info_table:
            rows = info_table.find_all('tr')
            if len(rows) > 1:
                 student_info['StudentFullName'] = rows[1].find_all('td')[1].text.strip()

        results = []
        for table in soup.find_all('table'):
            if 'sr' in str(table.find('tr')).lower():
                for row in table.find_all('tr')[1:]:
                    cols = [c.text.strip() for c in row.find_all('td')]
                    if len(cols) >= 12:
                        results.append({
                            'RegistrationNo': reg_no, 'StudentName': student_info.get('StudentFullName', ''),
                            'Semester': cols[1], 'TeacherName': cols[2], 'CourseCode': cols[3], 'CourseTitle': cols[4],
                            'CreditHours': cols[5], 'Mid': cols[6], 'Assignment': cols[7], 'Final': cols[8],
                            'Practical': cols[9], 'Total': cols[10], 'Grade': cols[11]
                        })
        if not results:
             return False, "Result data found, but failed to parse courses.", None
        return True, f"Successfully extracted {len(results)} records.", results

    def scrape_student_attendance(self, registration_number):
        base_url = "http://121.52.152.24/"
        try:
            with requests.Session() as s:
                s.headers.update({'User-Agent': random.choice(USER_AGENTS)})
                r = s.get(base_url, timeout=10)
                soup = BeautifulSoup(r.content, 'html.parser')
                
                viewstate = soup.find('input', {'name': '__VIEWSTATE'})
                if not viewstate: return False, "Attendance website structure has changed (ViewState missing).", None

                form_data = {
                    '__VIEWSTATE': viewstate['value'],
                    '__VIEWSTATEGENERATOR': soup.find('input', {'name': '__VIEWSTATEGENERATOR'})['value'],
                    '__EVENTVALIDATION': soup.find('input', {'name': '__EVENTVALIDATION'})['value'],
                    'ctl00$Main$txtReg': registration_number,
                    'ctl00$Main$btnShow': 'Access To Student Information'
                }
                
                post_res = s.post(base_url, data=form_data, timeout=15, headers={'Referer': base_url})
                if base_url not in post_res.url:
                    return False, "Failed to access attendance details. Registration number may be incorrect.", None
                
                results_soup = BeautifulSoup(post_res.content, 'html.parser')
                attendance_table = results_soup.find('table', {'id': 'ctl00_Main_TabContainer1_tbAttendance_gvAttendance'})
                if not attendance_table:
                    return True, "No attendance records found for this student.", []

                attendance_data = []
                for row in attendance_table.find_all('tr')[1:]:
                    cols = [c.text.strip() for c in row.find_all('td')]
                    if len(cols) >= 6:
                        try:
                            attendance_data.append({
                                'CourseCode': cols[0], 'CourseName': cols[1], 'TeacherName': cols[2],
                                'TotalLectures': int(cols[3]), 'Attended': int(cols[4]), 'Status': cols[5]
                            })
                        except (ValueError, IndexError): continue
                
                return True, "Attendance data retrieved successfully.", attendance_data
        except requests.exceptions.RequestException as e:
            return False, f"Network error with attendance server: {e}", None
        except Exception as e:
            return False, f"An unexpected error occurred: {e}", None
