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
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
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

    def handle_request(self):
        try:
            query_params = self.path.split('?')
            action = ''
            if len(query_params) > 1:
                params = dict(param.split('=') for param in query_params[1].split('&'))
                action = params.get('action')

            if action == 'scrape_single':
                self.handle_scrape_single()
            elif action == 'scrape_attendance':
                self.handle_scrape_attendance()
            else:
                self.send_error_response(404, f"Action '{action}' not found.")
        except Exception as e:
            self.send_error_response(500, f"Server error: {str(e)}")

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

    def get_registration_number(self):
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
        return registration_number

    def handle_scrape_single(self):
        """Handle single result scraping for CGPA calculator"""
        try:
            registration_number = self.get_registration_number()
            if not registration_number:
                self.send_error_response(400, 'No registration number provided')
                return
            
            success, message, result_data = self.scrape_uaf_results(registration_number)
            response = {'success': success, 'message': message, 'resultData': result_data}
            self.send_success_response(response)
        except Exception as e:
            self.send_error_response(500, f"Error scraping single result: {str(e)}")

    def handle_scrape_attendance(self):
        """Handle attendance scraping"""
        try:
            registration_number = self.get_registration_number()
            if not registration_number:
                self.send_error_response(400, 'Registration number not provided.')
                return

            success, message, result_data = self.scrape_student_attendance(registration_number)
            self.send_success_response({'success': success, 'message': message, 'resultData': result_data})

        except json.JSONDecodeError:
            self.send_error_response(400, "Invalid JSON.")
        except Exception as e:
            self.send_error_response(500, f"An unexpected error occurred: {e}")

    def scrape_uaf_results(self, registration_number):
        """Main function to scrape UAF results with HTTP/HTTPS fallback"""
        session = requests.Session()
        session.headers.update({'User-Agent': random.choice(USER_AGENTS)})
        
        schemes = ['http', 'https']
        response = None
        base_url = ''
        
        for scheme in schemes:
            try:
                base_url = f"{scheme}://lms.uaf.edu.pk"
                login_url = f"{base_url}/login/index.php"
                logger.info(f"Attempting connection to UAF LMS via {scheme.upper()}...")
                response = session.get(login_url, timeout=15, verify=False)
                response.raise_for_status()
                logger.info(f"Successfully connected via {scheme.upper()}.")
                break 
            except requests.exceptions.RequestException as e:
                logger.warning(f"{scheme.upper()} connection failed: {e}")
                response = None 
        
        if not response:
            logger.error("Both HTTP and HTTPS connections failed.")
            return False, "Could not connect to UAF LMS. The server may be down or blocking requests.", None

        try:
            token = self.extract_js_token(response.text)
            if not token:
                soup = BeautifulSoup(response.text, 'html.parser')
                token_input = soup.find('input', {'id': 'token'})
                token = token_input.get('value') if token_input else None
            
            if not token:
                return False, "Could not extract security token from UAF LMS. The site structure may have changed.", None
            
            result_url = f"{base_url}/course/uaf_student_result.php"
            form_data = {'token': token, 'Register': registration_number}
            headers = {'Referer': login_url, 'Origin': base_url}
            
            post_response = session.post(result_url, data=form_data, headers=headers, timeout=20, verify=False)
            
            if post_response.status_code != 200:
                return False, f"UAF LMS returned status code {post_response.status_code} when fetching results.", None
            
            return self.parse_uaf_results(post_response.text, registration_number)
        except requests.exceptions.RequestException as e:
            return False, f"Network error during scraping: {str(e)}. UAF LMS may be unavailable.", None
        except Exception as e:
            logger.error(f"Unexpected error during scraping logic: {str(e)}")
            return False, f"An unexpected error occurred: {str(e)}", None


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

    def scrape_student_attendance(self, registration_number):
        base_url = "http://121.52.152.24/"
        results_url = "http://121.52.152.24/StudentDetail.aspx"
        try:
            with requests.Session() as session:
                session.headers.update({
                    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                })
                # Get initial page to extract form fields
                initial_res = session.get(base_url, timeout=10)
                initial_soup = BeautifulSoup(initial_res.content, 'html.parser')
                
                viewstate = initial_soup.find('input', {'name': '__VIEWSTATE'})
                viewstategenerator = initial_soup.find('input', {'name': '__VIEWSTATEGENERATOR'})
                eventvalidation = initial_soup.find('input', {'name': '__EVENTVALIDATION'})

                if not all([viewstate, viewstategenerator, eventvalidation]):
                    return False, "Could not find required form fields. The website may have changed.", None

                form_data = {
                    '__VIEWSTATE': viewstate['value'],
                    '__VIEWSTATEGENERATOR': viewstategenerator['value'],
                    '__EVENTVALIDATION': eventvalidation['value'],
                    'ctl00$Main$txtReg': registration_number,
                    'ctl00$Main$btnShow': 'Access To Student Information'
                }

                # Post data to get attendance details
                post_res = session.post(base_url, data=form_data, timeout=15, headers={'Referer': base_url})

                if post_res.url != results_url:
                    return False, "Failed to access student details. The registration number may be incorrect or the service is down.", None

                # Now parse the attendance table from the results page
                results_soup = BeautifulSoup(post_res.content, 'html.parser')
                attendance_table = results_soup.find('table', {'id': 'ctl00_Main_TabContainer1_tbAttendance_gvAttendance'})

                if not attendance_table:
                    return True, "No attendance records found for this student.", []

                rows = attendance_table.find_all('tr')[1:] # Skip header
                attendance_data = []
                for row in rows:
                    cols = [ele.text.strip() for ele in row.find_all('td')]
                    if len(cols) >= 6:
                        try:
                            total_lectures = int(cols[3])
                            attended_lectures = int(cols[4])
                            attendance_data.append({
                                'CourseCode': cols[0],
                                'CourseName': cols[1],
                                'TeacherName': cols[2],
                                'TotalLectures': total_lectures,
                                'Attended': attended_lectures,
                                'Status': cols[5]
                            })
                        except (ValueError, IndexError):
                            continue # Skip row if data is malformed
                
                return True, "Attendance data retrieved successfully.", attendance_data
        
        except requests.exceptions.RequestException as e:
            return False, f"A network error occurred: {e}", None
        except Exception as e:
            return False, f"An unexpected error occurred during scraping: {e}", None
