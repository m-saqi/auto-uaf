from http.server import BaseHTTPRequestHandler
import json
import requests
from bs4 import BeautifulSoup
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
            # Determine action from URL query parameters
            query_params = self.path.split('?')
            action = ''
            if len(query_params) > 1:
                params = {k: v for k, v in [param.split('=') for param in query_params[1].split('&')]}
                action = params.get('action')

            if self.command == 'POST' or self.command == 'GET':
                if action == 'scrape_single':
                    self.handle_scrape_lms()
                elif action == 'scrape_attendance':
                    self.handle_scrape_attendance()
                else:
                    self.send_error_response(404, f"Action '{action}' not recognized.")
            else:
                self.send_error_response(405, "Method Not Allowed")
        except Exception as e:
            self.send_error_response(500, f"Server error: {str(e)}")

    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def get_registration_number(self):
        """Extracts registration number from GET or POST request."""
        if self.command == 'GET':
            query_params = self.path.split('?')
            if len(query_params) > 1:
                params = {k: v for k, v in [param.split('=') for param in query_params[1].split('&')]}
                return params.get('registrationNumber')
        elif self.command == 'POST':
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            return data.get('registrationNumber')
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
        try:
            reg_no = self.get_registration_number()
            if not reg_no:
                self.send_error_response(400, 'Registration number not provided.')
                return
            success, message, data = self.scrape_uaf_results(reg_no)
            self.send_success_response({'success': success, 'message': message, 'resultData': data})
        except Exception as e:
            self.send_error_response(500, f"Error during LMS scrape: {e}")

    # --- ATTENDANCE SYSTEM SCRAPER ---
    def handle_scrape_attendance(self):
        try:
            reg_no = self.get_registration_number()
            if not reg_no:
                self.send_error_response(400, 'Registration number not provided.')
                return
            success, message, data = self.scrape_student_attendance(reg_no)
            self.send_success_response({'success': success, 'message': message, 'resultData': data})
        except Exception as e:
            self.send_error_response(500, f"Error during attendance scrape: {e}")

    # --- LOGIC FOR UAF LMS ---
    def scrape_uaf_results(self, registration_number):
        session = requests.Session()
        session.headers.update({'User-Agent': random.choice(USER_AGENTS)})
        for scheme in ['http', 'https']:
            try:
                base_url = f"{scheme}://lms.uaf.edu.pk"
                login_url = f"{base_url}/login/index.php"
                response = session.get(login_url, timeout=15, verify=False)
                response.raise_for_status()
                
                token = self.extract_js_token(response.text) or BeautifulSoup(response.text, 'html.parser').find('input', {'id': 'token'}).get('value')
                if not token: continue

                result_url = f"{base_url}/course/uaf_student_result.php"
                post_response = session.post(result_url, data={'token': token, 'Register': registration_number}, headers={'Referer': login_url, 'Origin': base_url}, timeout=20, verify=False)
                if post_response.status_code == 200:
                    return self.parse_uaf_results(post_response.text, registration_number)
            except requests.exceptions.RequestException:
                continue
        return False, "Could not connect to UAF LMS. The server may be down.", None

    def extract_js_token(self, html_content):
        match = re.search(r"document\.getElementById\('token'\)\.value\s*=\s*'([^']+)'", html_content)
        return match.group(1) if match else None

    def parse_uaf_results(self, html, reg_no):
        soup = BeautifulSoup(html, 'html.parser')
        if "no result" in soup.get_text().lower():
            return False, f"No results found for: {reg_no}", None
        
        info_table = soup.find('table')
        student_info = {
            'Registration': reg_no,
            'StudentFullName': info_table.find_all('tr')[1].find_all('td')[1].text.strip() if info_table else ''
        }
        
        results = []
        for table in soup.find_all('table'):
            if 'sr' in str(table.find('tr')).lower():
                for row in table.find_all('tr')[1:]:
                    cols = [c.text.strip() for c in row.find_all('td')]
                    if len(cols) >= 12:
                        results.append({
                            'RegistrationNo': student_info.get('Registration'), 'StudentName': student_info.get('StudentFullName'),
                            'Semester': cols[1], 'TeacherName': cols[2], 'CourseCode': cols[3], 'CourseTitle': cols[4],
                            'CreditHours': cols[5], 'Mid': cols[6], 'Assignment': cols[7], 'Final': cols[8],
                            'Practical': cols[9], 'Total': cols[10], 'Grade': cols[11]
                        })
        return True, f"Found {len(results)} records.", results

    # --- LOGIC FOR ATTENDANCE SYSTEM ---
    def scrape_student_attendance(self, registration_number):
        base_url = "http://121.52.152.24/"
        results_url = f"{base_url}StudentDetail.aspx"
        try:
            with requests.Session() as s:
                s.headers.update({'User-Agent': random.choice(USER_AGENTS)})
                r = s.get(base_url, timeout=10)
                soup = BeautifulSoup(r.content, 'html.parser')
                
                form_data = {
                    '__VIEWSTATE': soup.find('input', {'name': '__VIEWSTATE'})['value'],
                    '__VIEWSTATEGENERATOR': soup.find('input', {'name': '__VIEWSTATEGENERATOR'})['value'],
                    '__EVENTVALIDATION': soup.find('input', {'name': '__EVENTVALIDATION'})['value'],
                    'ctl00$Main$txtReg': registration_number,
                    'ctl00$Main$btnShow': 'Access To Student Information'
                }
                
                post_res = s.post(base_url, data=form_data, timeout=15, headers={'Referer': base_url})
                if post_res.url != results_url:
                    return False, "Failed to access details. Check registration number.", None
                
                results_soup = BeautifulSoup(post_res.content, 'html.parser')
                attendance_table = results_soup.find('table', {'id': 'ctl00_Main_TabContainer1_tbAttendance_gvAttendance'})

                if not attendance_table:
                    return True, "No attendance records found.", []

                attendance_data = []
                for row in attendance_table.find_all('tr')[1:]:
                    cols = [c.text.strip() for c in row.find_all('td')]
                    if len(cols) >= 6:
                        try:
                            attendance_data.append({
                                'CourseCode': cols[0], 'CourseName': cols[1], 'TeacherName': cols[2],
                                'TotalLectures': int(cols[3]), 'Attended': int(cols[4]), 'Status': cols[5]
                            })
                        except (ValueError, IndexError):
                            continue
                return True, "Attendance retrieved.", attendance_data
        except requests.exceptions.RequestException as e:
            return False, f"Network error connecting to attendance server: {e}", None
        except Exception as e:
            return False, f"An error occurred during attendance scraping: {e}", None
