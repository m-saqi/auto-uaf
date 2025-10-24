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
from urllib.parse import urlparse, parse_qs

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
            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            action = query_params.get('action', [None])[0]
            registration_number = query_params.get('registrationNumber', [None])[0]

            if action == 'scrape_single':
                self.handle_scrape_single(registration_number)
            elif action == 'scrape_attendance':
                self.handle_scrape_attendance(registration_number)
            else:
                self.send_response(404)
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'message': 'Invalid action specified'}).encode())
        except Exception as e:
            logger.error(f"Server error during GET: {str(e)}", exc_info=True) # Log traceback
            self.send_error_response(500, f"Server error: {str(e)}")

    def do_POST(self):
        # Handle POST - expecting JSON body primarily
        try:
            content_length = int(self.headers['Content-Length'])
            post_data_bytes = self.rfile.read(content_length)
            post_data = json.loads(post_data_bytes.decode('utf-8'))

            parsed_path = urlparse(self.path)
            query_params = parse_qs(parsed_path.query)
            action = query_params.get('action', [None])[0]
            # Get registration number primarily from JSON body, fallback to query param
            registration_number = post_data.get('registrationNumber', query_params.get('registrationNumber', [None])[0])

            if action == 'scrape_single':
                self.handle_scrape_single(registration_number)
            elif action == 'scrape_attendance':
                self.handle_scrape_attendance(registration_number)
            else:
                self.send_response(404)
                self._set_cors_headers()
                self.end_headers()
                self.wfile.write(json.dumps({'success': False, 'message': 'Invalid action specified'}).encode())

        except json.JSONDecodeError:
            self.send_error_response(400, "Invalid JSON data received in POST request.")
        except Exception as e:
            logger.error(f"Server error during POST: {str(e)}", exc_info=True) # Log traceback
            self.send_error_response(500, f"Server error: {str(e)}")


    def send_error_response(self, status_code, message):
        try:
            self.send_response(status_code)
            self._set_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            response = {'success': False, 'message': message}
            self.wfile.write(json.dumps(response).encode())
        except Exception as e:
            # Fallback if headers already sent or other issue
            logger.error(f"Error sending error response itself: {e}")

    def send_success_response(self, data):
        try:
            self.send_response(200)
            self._set_cors_headers()
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
        except Exception as e:
            logger.error(f"Error sending success response: {e}")
            # Cannot easily send an error response here if headers are already sent

    def handle_scrape_single(self, registration_number):
        """Handle single result scraping for CGPA calculator (LMS)"""
        try:
            if not registration_number:
                self.send_error_response(400, 'No registration number provided')
                return

            success, message, result_data = self.scrape_uaf_results(registration_number)
            response = {'success': success, 'message': message, 'resultData': result_data}
            if success:
                self.send_success_response(response)
            else:
                # Determine appropriate status code based on message
                status_code = 404 if "No results found" in message or "incorrect" in message else 503 if "maintenance" in message else 500
                self.send_error_response(status_code, message)
        except Exception as e:
            logger.error(f"Error scraping single result: {str(e)}", exc_info=True)
            self.send_error_response(500, f"Error scraping LMS result: {str(e)}")

    def handle_scrape_attendance(self, registration_number):
        """Handle result scraping from the Attendance System"""
        try:
            if not registration_number:
                self.send_error_response(400, 'No registration number provided')
                return

            success, message, result_data = self.scrape_attendance_system(registration_number)
            response = {'success': success, 'message': message, 'resultData': result_data}
            if success:
                self.send_success_response(response)
            else:
                # Determine appropriate status code
                status_code = 404 if "No results found" in message or "not found" in message or "incorrect" in message else 503 if "timed out" in message or "down" in message else 500
                self.send_error_response(status_code, message)
        except Exception as e:
            logger.error(f"Error scraping attendance system: {str(e)}", exc_info=True)
            self.send_error_response(500, f"Error scraping attendance system: {str(e)}")

    def scrape_attendance_system(self, registration_number):
        """Scrapes results from the UAF Attendance System"""
        BASE_URL = "http://121.52.152.24/"
        DEFAULT_PAGE = "default.aspx"

        try:
            session = requests.Session()
            session.headers.update({'User-Agent': random.choice(USER_AGENTS)})

            # 1. GET the main page
            try:
                logger.info(f"Connecting to Attendance System at {BASE_URL}...")
                response = session.get(BASE_URL + DEFAULT_PAGE, timeout=25) # Increased timeout
                response.raise_for_status()
            except requests.exceptions.Timeout:
                 logger.error(f"Timeout connecting to Attendance System at {BASE_URL}")
                 return False, "Connection to UAF Attendance System timed out. Please try again later.", None
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to connect to Attendance System: {e}")
                return False, "Could not connect to UAF Attendance System. The server may be down or unavailable.", None

            soup = BeautifulSoup(response.text, 'html.parser')

            viewstate = soup.find('input', {'id': '__VIEWSTATE'})
            eventvalidation = soup.find('input', {'id': '__EVENTVALIDATION'})

            if not viewstate:
                logger.warning("Could not find __VIEWSTATE on attendance system page.")
                return False, "Could not parse the Attendance System page (VIEWSTATE missing). Structure might have changed.", None

            # Sometimes EVENTVALIDATION might be missing or empty, handle gracefully
            eventvalidation_value = eventvalidation.get('value', '') if eventvalidation else ''
            if not eventvalidation_value:
                 logger.warning("Could not find __EVENTVALIDATION on attendance system page. Proceeding without it.")


            form_data = {
                '__VIEWSTATE': viewstate.get('value', ''),
                '__EVENTVALIDATION': eventvalidation_value,
                'ctl00$Main$txtReg': registration_number,
                'ctl00$Main$btnShow': 'Access To Student Information' # Value from the button
            }

            # 2. POST the registration number
            try:
                logger.info(f"Submitting registration number {registration_number} to Attendance System...")
                headers = {'Referer': BASE_URL + DEFAULT_PAGE}
                post_response = session.post(BASE_URL + DEFAULT_PAGE, data=form_data, headers=headers, timeout=35) # Increased timeout
                post_response.raise_for_status()
            except requests.exceptions.Timeout:
                 logger.error(f"Timeout submitting form to Attendance System")
                 return False, "Request to Attendance System timed out while fetching results.", None
            except requests.exceptions.RequestException as e:
                logger.error(f"Failed to submit form to Attendance System: {e}")
                return False, f"Error while fetching results from Attendance System: {e}", None

            # 3. Parse the result page
            return self.parse_attendance_results(post_response.text, registration_number)

        except Exception as e:
            logger.error(f"Unexpected error during attendance scraping: {str(e)}", exc_info=True)
            return False, f"An unexpected error occurred during attendance scraping: {str(e)}", None

    def parse_attendance_results(self, html_content, registration_number):
        """Parses the result table from the Attendance System HTML"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')

            # More robust error checking using specific elements if available
            error_span = soup.find('span', {'id': 'ctl00_Main_lblmsg'}) # Specific error span
            if error_span and "not found" in error_span.text.lower():
                 logger.warning(f"Registration number {registration_number} not found on Attendance System.")
                 return False, f"Registration number {registration_number} not found on Attendance System.", None

            if "object moved to" in html_content.lower():
                 logger.warning(f"Redirect detected or 'object moved' error for {registration_number} on Attendance System.")
                 return False, f"Attendance system returned an unexpected page (Object Moved). Try again.", None

            result_table = soup.find('table', {'id': 'ctl00_Main_TabContainer1_tbResultInformation_gvResultInformation'})

            if not result_table:
                # Check if the login form input is still present, indicating failed POST
                login_input = soup.find('input', {'id': 'ctl00_Main_txtReg'})
                if login_input:
                    logger.warning(f"Result table not found, and login form present. Failed form submission for {registration_number}.")
                    return False, "Failed to submit registration to Attendance System. Double-check number or system might be busy.", None
                else:
                    # If no error span, no login form, and no table, it might genuinely be no results yet.
                    logger.warning(f"Could not find result table structure for {registration_number} on Attendance System. Assuming no results yet.")
                    # Return success with empty list
                    return True, "No results recorded in the Attendance System yet for this registration number.", []

            results = []
            header_skipped = False

            for row in result_table.find_all('tr'):
                # Skip header row (checking for 'th' tags is more reliable)
                if not header_skipped and row.find('th'):
                    header_skipped = True
                    continue
                # Also skip if it's the first row and looks like a header based on TD content
                if not header_skipped and 'registrationno' in row.get_text(strip=True, separator='|').lower():
                    header_skipped = True
                    continue

                cols = row.find_all('td')
                if len(cols) == 16:  # Expected number of columns
                    try:
                        # Clean up '&nbsp;' which might appear, resulting in '\xa0'
                        cleaned_cols_text = [col.text.strip().replace('\xa0', '') for col in cols]

                        # Handle empty strings, replace with 'N/A' for consistency, except for marks which should be 0
                        def clean_field(index, default='N/A', is_numeric=False):
                            val = cleaned_cols_text[index]
                            if not val:
                                return '0' if is_numeric else default
                            return val

                        course_data = {
                            'RegistrationNo': clean_field(0, registration_number), # Use input number if missing
                            'Year': clean_field(1),
                            'Sem': clean_field(2),
                            'Semester': clean_field(3), # Use 'semestername' (e.g., Winter20)
                            'TeacherName': clean_field(4),
                            'CourseCode': clean_field(5, 'UNKNOWN_CODE'),
                            'CourseName': clean_field(6),
                            'DegreeName': clean_field(7),
                            'Mid': clean_field(8, '0', is_numeric=True),
                            'Assignment': clean_field(9, '0', is_numeric=True), # Correct key
                            'Final': clean_field(10, '0', is_numeric=True),
                            'Practical': clean_field(11, '0', is_numeric=True),
                            'Total': clean_field(12, '0', is_numeric=True), # Use 'Total' key
                            'Grade': clean_field(13),
                            'Markinwords': clean_field(14),
                            'Status': clean_field(15)
                        }
                        # Add placeholders required by frontend logic
                        course_data['CreditHours'] = '?' # Needs user input
                        course_data['StudentName'] = 'N/A' # Will try to populate later

                        results.append(course_data)
                    except IndexError:
                        logger.error(f"Error parsing attendance row due to unexpected column count: {row}")
                    except Exception as e:
                        logger.error(f"Error processing attendance result row: {e} | Row: {row}", exc_info=True)
                elif len(cols) > 0: # Log rows that don't match expected structure but aren't empty
                    logger.warning(f"Skipping attendance row with unexpected column count ({len(cols)}): {row}")

            # Try to extract student name from the header section AFTER processing rows
            student_name = 'N/A'
            name_label = soup.find('span', {'id': 'ctl00_Main_lblName'})
            if name_label and name_label.text.strip():
                student_name = name_label.text.strip()
                logger.info(f"Extracted student name from attendance page: {student_name}")
                # Add/Update student name in all results
                for record in results:
                    record['StudentName'] = student_name

            if results:
                logger.info(f"Successfully extracted {len(results)} records from Attendance System for {registration_number}.")
                return True, f"Successfully extracted {len(results)} records", results
            else:
                 # Check again if login form is present, indicates failure post-parsing
                login_input = soup.find('input', {'id': 'ctl00_Main_txtReg'})
                if login_input:
                    logger.warning(f"Parsed 0 results, login form found. Failed submission for {registration_number}.")
                    return False, "Failed to retrieve results after submission. Check registration number.", None
                else:
                    logger.warning(f"Result table was found but no valid data rows could be parsed for {registration_number}.")
                    # Return success with empty list if table exists but parsing failed / table genuinely empty
                    return True, "Result table was empty or no valid rows found.", []

        except Exception as e:
            logger.exception(f"Critical error parsing attendance results for {registration_number}: {str(e)}") # Log traceback
            return False, f"Error parsing attendance results: {str(e)}", None


    def scrape_uaf_results(self, registration_number):
        """Main function to scrape UAF results (LMS) with HTTP/HTTPS fallback"""
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
                response = session.get(login_url, timeout=20, verify=False) # Slightly longer timeout
                response.raise_for_status()
                logger.info(f"Successfully connected via {scheme.upper()}.")
                break
            except requests.exceptions.Timeout:
                logger.warning(f"{scheme.upper()} LMS connection timed out.")
                response = None
            except requests.exceptions.RequestException as e:
                logger.warning(f"{scheme.upper()} LMS connection failed: {e}")
                response = None

        if not response:
            logger.error("Both HTTP and HTTPS connections failed to LMS.")
            return False, "Could not connect to UAF LMS. The server may be down or temporarily unavailable.", None

        try:
            # Check for maintenance message early
            if "under maintenance" in response.text.lower():
                 logger.warning("LMS appears to be under maintenance.")
                 return False, "UAF LMS is currently under maintenance. Please try again later.", None

            token = self.extract_js_token(response.text)
            if not token:
                soup = BeautifulSoup(response.text, 'html.parser')
                token_input = soup.find('input', {'id': 'token'})
                token = token_input.get('value') if token_input else None

            if not token:
                logger.error("Could not extract security token from UAF LMS.")
                return False, "Could not extract security token from UAF LMS. The site structure may have changed, or the site is down.", None

            result_url = f"{base_url}/course/uaf_student_result.php"
            form_data = {'token': token, 'Register': registration_number}
            headers = {'Referer': login_url, 'Origin': base_url}

            post_response = session.post(result_url, data=form_data, headers=headers, timeout=25, verify=False) # Increased timeout

            if post_response.status_code != 200:
                logger.error(f"LMS returned status code {post_response.status_code} for {registration_number}.")
                return False, f"UAF LMS returned status code {post_response.status_code}. It might be busy, under maintenance, or the request was blocked.", None

            return self.parse_uaf_results(post_response.text, registration_number)

        except requests.exceptions.Timeout:
            logger.error(f"Timeout during LMS scraping process for {registration_number}.")
            return False, "Request to UAF LMS timed out while fetching results.", None
        except requests.exceptions.RequestException as e:
             logger.error(f"Network error during LMS scraping for {registration_number}: {str(e)}")
             return False, f"Network error during LMS scraping: {str(e)}. UAF LMS may be unavailable.", None
        except Exception as e:
            logger.exception(f"Unexpected error during LMS scraping logic for {registration_number}: {str(e)}") # Log traceback
            return False, f"An unexpected error occurred during LMS scraping: {str(e)}", None


    def extract_js_token(self, html_content):
        """Extract JavaScript-generated token from UAF LMS"""
        match = re.search(r"document\.getElementById\('token'\)\.value\s*=\s*'([^']+)'", html_content)
        return match.group(1) if match else None

    def parse_uaf_results(self, html_content, registration_number):
        """Parse UAF results from LMS"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            page_text = soup.get_text(strip=True).lower() # Use stripped text

            # Check for specific error messages first
            # More specific checks
            if "no result for this number" in page_text or "registration number not found" in page_text or "no records found" in page_text:
                logger.warning(f"LMS reported 'no results found' for {registration_number}")
                return False, f"No results found for registration number: {registration_number}. Please double-check the number.", None
            if any(text in page_text for text in ['blocked', 'access denied', 'not available']):
                logger.warning(f"Access blocked by LMS for {registration_number}")
                return False, "Access blocked by UAF LMS, possibly due to too many requests. Try again later.", None
            if "under maintenance" in page_text:
                 logger.warning(f"LMS maintenance detected for {registration_number}")
                 return False, "UAF LMS appears to be under maintenance. Please try again later.", None

            student_info = {}
            # Find the first table which *usually* contains student info
            info_table = soup.find('table')
            student_name = 'N/A' # Default
            student_reg = registration_number # Default

            if info_table:
                rows = info_table.find_all('tr')
                for row in rows:
                     cols = row.find_all('td')
                     if len(cols) == 2:
                        key_raw = cols[0].text.strip().lower()
                        value = cols[1].text.strip()
                        if 'registration' in key_raw: student_reg = value
                        elif 'full name' in key_raw or 'student name' in key_raw: student_name = value
            else:
                 logger.warning(f"Could not find the student info table for {registration_number}")


            student_results = []
            result_tables = soup.find_all('table')

            # Start searching for the results table (usually not the first one)
            results_table_found = False
            if len(result_tables) > 0: # Check if there are tables at all
                for table in result_tables: # Check all tables
                    rows = table.find_all('tr')
                    header_row = rows[0] if rows else None
                    # More robust header check
                    if header_row and 'sr' in header_row.get_text(strip=True).lower() and ('grade' in header_row.get_text(strip=True).lower() or 'course code' in header_row.get_text(strip=True).lower()):
                        results_table_found = True
                        for i in range(1, len(rows)): # Skip header
                            cols = [col.text.strip().replace('\xa0', '') for col in rows[i].find_all('td')]
                            if len(cols) >= 12: # Expect at least 12 columns up to 'Grade'
                                try:
                                    result_item = {
                                        'RegistrationNo': student_reg, # Use extracted/default reg
                                        'StudentName': student_name, # Use extracted/default name
                                        'SrNo': cols[0],
                                        'Semester': cols[1], # Original Semester string from LMS
                                        'TeacherName': cols[2],
                                        'CourseCode': cols[3],
                                        'CourseTitle': cols[4],
                                        'CreditHours': cols[5], # Original CreditHours string e.g., "3(2-1)"
                                        'Mid': cols[6],
                                        'Assignment': cols[7],
                                        'Final': cols[8],
                                        'Practical': cols[9],
                                        'Total': cols[10],
                                        'Grade': cols[11]
                                    }
                                    student_results.append(result_item)
                                except IndexError:
                                    logger.error(f"Error parsing LMS result row due to index: {row}")
                                except Exception as e:
                                    logger.error(f"Error processing LMS result row: {e} | Row: {row}", exc_info=True)
                            elif len(cols) > 0: # Log rows that don't match expected structure but aren't empty
                                logger.warning(f"Skipping LMS row with unexpected column count ({len(cols)}): {row}")
                        # Found and processed the results table, break the loop over tables
                        break

            if student_results:
                 logger.info(f"Successfully extracted {len(student_results)} records from LMS for {registration_number}.")
                 return True, f"Successfully extracted {len(student_results)} records", student_results
            elif results_table_found: # Table header found, but no rows parsed
                 logger.warning(f"LMS Results table structure found for {registration_number}, but no data rows could be parsed.")
                 return False, f"Found results table, but failed to parse course data. Site structure might have changed.", None
            else:
                 # No error messages found, student info might be missing, no results table found
                 logger.error(f"Failed to find results table structure on LMS page for {registration_number}.")
                 return False, f"Could not find results table on LMS page. Registration incorrect, no results yet, or page structure changed.", None

        except Exception as e:
            logger.exception(f"Critical error parsing LMS results for {registration_number}: {str(e)}") # Log traceback
            return False, f"Error parsing LMS results: {str(e)}", None
