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

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Use /tmp directory for session storage
DATA_DIR = "/tmp/uaftools_data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

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
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
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
            elif 'action=save' in self.path:
                self.handle_save()
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
        try:
            # Test connection to UAF LMS
            test_url = 'http://lms.uaf.edu.pk/login/index.php'
            
            try:
                response = requests.get(test_url, timeout=10, headers={
                    'User-Agent': random.choice(USER_AGENTS),
                })
                
                if response.status_code == 200:
                    response_data = {'success': True, 'message': 'Connection to UAF LMS successful'}
                    self.send_success_response(response_data)
                    return
                else:
                    response_data = {'success': False, 'message': f'UAF LMS returned status code: {response.status_code}'}
                    self.send_success_response(response_data)
                    return
                    
            except Exception as e:
                response_data = {'success': False, 'message': f'Connection error: {str(e)}'}
                self.send_success_response(response_data)
                return
            
        except Exception as e:
            response_data = {'success': False, 'message': f'Connection test error: {str(e)}'}
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
        """Handle single result scraping for GPA calculator"""
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
                    
                    # Calculate GPA if successful
                    if success and result_data:
                        gpa_data = self.calculate_gpa_cgpa(result_data)
                        response = {
                            'success': success, 
                            'message': message, 
                            'resultData': result_data,
                            'gpaData': gpa_data
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
                
                # Calculate GPA if successful
                if success and result_data:
                    gpa_data = self.calculate_gpa_cgpa(result_data)
                    response = {
                        'success': success, 
                        'message': message, 
                        'resultData': result_data,
                        'gpaData': gpa_data
                    }
                else:
                    response = {'success': success, 'message': message, 'resultData': result_data}
                
                self.send_success_response(response)
                
        except Exception as e:
            self.send_error_response(500, f"Error scraping single result: {str(e)}")

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

    def calculate_quality_points(self, marks, credit_hours):
        """Calculate quality points based on UAF grading system"""
        try:
            marks = float(marks)
            credit_hours = int(credit_hours)
            
            # Handle F grade cases first
            if credit_hours == 5 and marks < 40:
                return 0.0
            elif credit_hours == 4 and marks < 32:
                return 0.0
            elif credit_hours == 3 and marks < 24:
                return 0.0
            elif credit_hours == 2 and marks < 16:
                return 0.0
            elif credit_hours == 1 and marks < 8:
                return 0.0
            
            # Calculate quality points for passing grades
            if credit_hours == 5:
                if marks >= 80:
                    return 20.0
                elif marks >= 50:
                    return 20.0 - ((80.0 - marks) * 0.33333)
                else:  # marks between 40-50
                    return 10.0 - ((50.0 - marks) * 0.5)
            
            elif credit_hours == 4:
                if marks >= 64:
                    return 16.0
                elif marks >= 40:
                    return 16.0 - ((64.0 - marks) * 0.33333)
                else:  # marks between 32-40
                    return 8.0 - ((40.0 - marks) * 0.5)
            
            elif credit_hours == 3:
                if marks >= 48:
                    return 12.0
                elif marks >= 30:
                    return 12.0 - ((48.0 - marks) * 0.33333)
                else:  # marks between 24-30
                    return 6.0 - ((30.0 - marks) * 0.5)
            
            elif credit_hours == 2:
                if marks >= 32:
                    return 8.0
                elif marks >= 20:
                    return 8.0 - ((32.0 - marks) * 0.33333)
                else:  # marks between 16-20
                    return 4.0 - ((20.0 - marks) * 0.5)
            
            elif credit_hours == 1:
                if marks >= 16:
                    return 4.0
                elif marks >= 10:
                    return 4.0 - ((16.0 - marks) * 0.33333)
                else:  # marks between 8-10
                    return 2.0 - ((10.0 - marks) * 0.5)
            
            return 0.0
            
        except (ValueError, TypeError):
            return 0.0

    def get_grade(self, marks, credit_hours):
        """Get letter grade based on marks and credit hours"""
        try:
            marks = float(marks)
            
            # Determine passing marks threshold based on credit hours
            if credit_hours == 5:
                passing_marks = 40
            elif credit_hours == 4:
                passing_marks = 32
            elif credit_hours == 3:
                passing_marks = 24
            elif credit_hours == 2:
                passing_marks = 16
            elif credit_hours == 1:
                passing_marks = 8
            else:
                passing_marks = 50  # Default
            
            if marks < passing_marks:
                return "F"
            
            # Grade ranges (approximate based on UAF system)
            if marks >= 80:
                return "A"
            elif marks >= 70:
                return "B"
            elif marks >= 60:
                return "C"
            elif marks >= 50:
                return "D"
            else:
                return "F"
                
        except (ValueError, TypeError):
            return "F"

    def calculate_gpa_cgpa(self, result_data):
        """Calculate GPA and CGPA from result data"""
        try:
            # Organize by semester
            semesters = {}
            student_info = {}
            
            for result in result_data:
                # Extract student info from first record
                if not student_info:
                    student_info = {
                        'name': result.get('StudentName', ''),
                        'registration': result.get('RegistrationNo', '')
                    }
                
                # Extract semester information
                semester = result.get('Semester', 'Unknown')
                if semester not in semesters:
                    semesters[semester] = []
                
                # Extract course details
                course_code = result.get('CourseCode', '')
                course_title = result.get('CourseTitle', '')
                credit_hours_str = result.get('CreditHours', '0')
                marks_str = result.get('Total', '0')
                
                # Parse credit hours (handle formats like "3(3-0)")
                credit_hours = 0
                if credit_hours_str:
                    # Extract numbers from string
                    numbers = re.findall(r'\d+', credit_hours_str)
                    if numbers:
                        credit_hours = int(numbers[0])
                
                # Parse marks
                marks = 0
                try:
                    marks = float(marks_str) if marks_str else 0
                except (ValueError, TypeError):
                    marks = 0
                
                # Calculate quality points and grade
                quality_points = self.calculate_quality_points(marks, credit_hours)
                grade = self.get_grade(marks, credit_hours)
                
                # Add to semester data
                semesters[semester].append({
                    'courseCode': course_code,
                    'courseTitle': course_title,
                    'creditHours': credit_hours,
                    'marks': marks,
                    'qualityPoints': round(quality_points, 2),
                    'grade': grade
                })
            
            # Calculate GPA for each semester and overall CGPA
            semester_gpa = {}
            total_quality_points = 0
            total_credit_hours = 0
            
            for semester, courses in semesters.items():
                semester_quality_points = 0
                semester_credit_hours = 0
                
                for course in courses:
                    semester_quality_points += course['qualityPoints']
                    semester_credit_hours += course['creditHours']
                
                if semester_credit_hours > 0:
                    semester_gpa[semester] = {
                        'gpa': round(semester_quality_points / semester_credit_hours, 4),
                        'percentage': round((semester_quality_points / semester_credit_hours) * 25, 2),
                        'courses': courses
                    }
                    
                    total_quality_points += semester_quality_points
                    total_credit_hours += semester_credit_hours
            
            # Calculate overall CGPA
            cgpa = 0
            cgpa_percentage = 0
            if total_credit_hours > 0:
                cgpa = round(total_quality_points / total_credit_hours, 4)
                cgpa_percentage = round((total_quality_points / total_credit_hours) * 25, 2)
            
            return {
                'studentInfo': student_info,
                'cgpa': cgpa,
                'cgpaPercentage': cgpa_percentage,
                'semesters': semester_gpa,
                'totalQualityPoints': total_quality_points,
                'totalCreditHours': total_credit_hours
            }
            
        except Exception as e:
            logger.error(f"Error calculating GPA: {str(e)}")
            return {
                'studentInfo': {'name': '', 'registration': ''},
                'cgpa': 0,
                'cgpaPercentage': 0,
                'semesters': {},
                'totalQualityPoints': 0,
                'totalCreditHours': 0
            }

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
            
            # Step 1: Get login page to extract token
            login_url = "http://lms.uaf.edu.pk/login/index.php"
            try:
                response = session.get(login_url, timeout=15)
                
                if response.status_code != 200:
                    return False, f"UAF LMS returned status code {response.status_code}. The server may be down.", None
                    
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
            
            # Step 3: Submit form with correct field names
            result_url = "http://lms.uaf.edu.pk/course/uaf_student_result.php"
            form_data = {
                'token': token,
                'Register': registration_number
            }
            
            headers = {
                'Referer': login_url,
                'Origin': 'http://lms.uaf.edu.pk',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            try:
                response = session.post(result_url, data=form_data, headers=headers, timeout=20)
                
                if response.status_code != 200:
                    return False, f"UAF LMS returned status code {response.status_code}", None
                    
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
