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
import concurrent.futures # Import this

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
            elif 'action=scrape_attendance' in self.path:
                self.handle_scrape_attendance()
            elif 'action=check_status' in self.path:
                self.handle_check_status()
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
            elif 'action=scrape_attendance' in self.path:
                self.handle_scrape_attendance()
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

    # --- MODIFIED FUNCTION ---
    def check_server_health(self, url, method='get', timeout=4): # <-- Reduced timeout to 4
        """
        Checks a single URL.
        Returns 'online' for 200-399 status.
        Returns 'error' for 500-599 status.
        Returns 'offline' for connection errors or timeouts.
        """
        try:
            with requests.Session() as s:
                s.headers.update({'User-Agent': random.choice(USER_AGENTS)})
                if method == 'head':
                    resp = s.head(url, timeout=timeout, verify=False, allow_redirects=True)
                else:
                    resp = s.get(url, timeout=timeout, verify=False, allow_redirects=True)
            
            if 200 <= resp.status_code < 400:
                return 'online' # Includes 200-OK, 301/302-Redirects
            elif 500 <= resp.status_code < 600:
                return 'error' # Server is up but broken (e.g., "Server Error in '/' Application")
            else:
                return 'offline' # Other client errors (404, 403)
        except requests.exceptions.RequestException as e:
            logger.warning(f"Health check for {url} failed: {str(e)}")
            # Try GET if HEAD failed, as some servers block HEAD
            if method == 'head':
                logger.info(f"Retrying {url} with GET...")
                # Call with 'get' but use the *same* short timeout
                return self.check_server_health(url, method='get', timeout=timeout)
            return 'offline' # Fails on GET or already was GET

    # --- MODIFIED FUNCTION ---
    def handle_check_status(self):
        """
        Handles the 'check_status' action by checking LMS and Attendance servers.
        """
        lms_status = 'offline'
        attnd_status = 'offline'

        with concurrent.futures.ThreadPoolExecutor() as executor:
            # Use 'head' for LMS (fast)
            future_lms_http = executor.submit(self.check_server_health, 'http://lms.uaf.edu.pk/login/index.php', method='head')
            future_lms_https = executor.submit(self.check_server_health, 'https://lms.uaf.edu.pk/login/index.php', method='head')
            # Use 'get' for Attendance (to catch the 500 error faster)
            future_attnd = executor.submit(self.check_server_health, 'http://121.52.152.24/default.aspx', method='get')

            # Process LMS results
            if future_lms_http.result() == 'online' or future_lms_https.result() == 'online':
                lms_status = 'online'
            
            # Process Attendance result
            attnd_status = future_attnd.result()

        response_data = {
            'success': True,
            'lms_status': lms_status,
            'attnd_status': attnd_status
        }
        self.send_success_response(response_data)

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

    def handle_scrape_attendance(self):
        """Handle result scraping from the Attendance System"""
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

            success, message, result_data = self.scrape_attendance_system(registration_number)
            response = {'success': success, 'message': message, 'resultData': result_data}
            self.send_success_response(response)
        except Exception as e:
            self.send_error_response(500, f"Error scraping attendance system: {str(e)}")

    def scrape_attendance_system(self, registration_number):
        """Scrapes results from the UAF Attendance System"""
        BASE_URL = "http://121.52.152.24/"
        DEFAULT_PAGE = "default.aspx"
        
        try:
            session = requests.Session()
            session.headers.update({'User-Agent': random.choice(USER_AGENTS)})

            # 1. GET the main page to retrieve VIEWSTATE and EVENTVALIDATION
            try:
                logger.info(f"Connecting to Attendance System at {BASE_URL}...")
                response = session.get(BASE_URL + DEFAULT_PAGE, timeout=20)
                response.raise_for_status()
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to connect to Attendance System: {e}")
                return False, "Could not connect to UAF Attendance System. The server may be down.", None

            soup = BeautifulSoup(response.text, 'html.parser')
            
            viewstate = soup.find('input', {'id': '__VIEWSTATE'})
            eventvalidation = soup.find('input', {'id': '__EVENTVALIDATION'})

            if not viewstate:
                logger.warning("Could not find __VIEWSTATE on attendance system page.")
                return False, "Could not parse the Attendance System page (VIEWSTATE missing).", None

            if not eventvalidation:
                logger.warning("Could not find __EVENTVALIDATION on attendance system page.")
                return False, "Could not parse the Attendance System page (EVENTVALIDATION missing).", None

            form_data = {
                '__VIEWSTATE': viewstate.get('value', ''),
                '__EVENTVALIDATION': eventvalidation.get('value', ''),
                'ctl00$Main$txtReg': registration_number,
                'ctl00$Main$btnShow': 'Access To Student Information'
            }

            # 2. POST the registration number
            try:
                logger.info(f"Submitting registration number {registration_number} to Attendance System...")
                post_response = session.post(BASE_URL + DEFAULT_PAGE, data=form_data, timeout=30)
                post_response.raise_for_status()
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to submit form to Attendance System: {e}")
                return False, "Error while fetching results from Attendance System.", None
            
            # 3. Parse the result page
            return self.parse_attendance_results(post_response.text, registration_number)
        
        except Exception as e:
            logger.error(f"Unexpected error during attendance scraping: {str(e)}")
            return False, f"An unexpected error occurred: {str(e)}", None

    def parse_attendance_results(self, html_content, registration_number):
        """Parses the result table from the Attendance System HTML"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Check for common errors first
            if "object moved to" in html_content.lower() or "student registration no. not found" in html_content.lower():
                logger.warning(f"No results found for {registration_number} on Attendance System.")
                return False, f"No results found for {registration_number} on Attendance System.", None
                
            result_table = soup.find('table', {'id': 'ctl00_Main_TabContainer1_tbResultInformation_gvResultInformation'})
            
            if not result_table:
                logger.warning(f"Could not find result table for {registration_number} on Attendance System.")
                return False, "Could not find result table on Attendance System page. The registration number may be incorrect.", None
                
            results = []
            header_rows = 1  # The first <tr> is the header
            
            for row in result_table.find_all('tr'):
                if header_rows > 0:
                    header_rows -= 1
                    continue
                
                cols = row.find_all('td')
                if len(cols) == 16:  # 16 columns as per the HTML structure
                    try:
                        course_data = {
                            'RegistrationNo': cols[0].text.strip(),
                            'Year': cols[1].text.strip(),
                            'Sem': cols[2].text.strip(),
                            'Semester': cols[3].text.strip(), # Using semestername
                            'TeacherName': cols[4].text.strip(),
                            'CourseCode': cols[5].text.strip(),
                            'CourseName': cols[6].text.strip(),
                            'DegreeName': cols[7].text.strip(),
                            'Mid': cols[8].text.strip(),
                            'Assigment': cols[9].text.strip(),
                            'Final': cols[10].text.strip(),
                            'Practical': cols[11].text.strip(),
                            'Totalmark': cols[12].text.strip(),
                            'Grade': cols[13].text.strip(),
                            'Markinwords': cols[14].text.strip(),
                            'Status': cols[15].text.strip()
                        }
                        results.append(course_data)
                    except Exception as e:
                        logger.error(f"Error parsing attendance result row: {e}")
                        
            if results:
                logger.info(f"Successfully extracted {len(results)} records from Attendance System for {registration_number}.")
                return True, f"Successfully extracted {len(results)} records", results
            else:
                logger.warning(f"Result table was found but no data rows could be parsed for {registration_number}.")
                return False, f"No result data found in table for: {registration_number}", None
                
        except Exception as e:
            logger.error(f"Error parsing attendance results: {str(e)}")
            return False, f"Error parsing results: {str(e)}", None


    def scrape_uaf_results(self, registration_number):
        """Main function to scrape UAF results with HTTP/HTTPS fallback"""
        session = requests.Session()
        session.headers.update({'User-Agent': random.choice(USER_AGENTS)})
        
        # Priority updated: HTTPS first, then HTTP
        schemes = ['https', 'http']
        response = None
        base_url = ''
        
        for scheme in schemes:
            try:
                base_url = f"{scheme}://lms.uaf.edu.pk"
                login_url = f"{base_url}/login/index.php"
                logger.info(f"Attempting connection to UAF LMS via {scheme.upper()}...")
                
                # Timeout updated to 3 seconds as requested
                response = session.get(login_url, timeout=3, verify=False)
                response.raise_for_status()
                logger.info(f"Successfully connected via {scheme.upper()}.")
                break 
            except requests.exceptions.RequestException as e:
                logger.warning(f"{scheme.upper()} connection failed: {e}")
                response = None 
        
        if not response:
            logger.error("Both HTTPS and HTTP connections failed.")
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
            
            # Keep a slightly longer timeout for the actual result fetch as it might take longer than the ping
            post_response = session.post(result_url, data=form_data, timeout=10, verify=False)
            
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

