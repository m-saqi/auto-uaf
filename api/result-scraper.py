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
import urllib3
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver.chrome.service import Service

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
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

    def setup_selenium_driver(self):
        """Setup Chrome driver with anti-detection settings"""
        try:
            chrome_options = Options()
            chrome_options.add_argument('--headless=new')
            chrome_options.add_argument('--no-sandbox')
            chrome_options.add_argument('--disable-dev-shm-usage')
            chrome_options.add_argument('--disable-gpu')
            chrome_options.add_argument('--window-size=1920,1080')
            chrome_options.add_argument('--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')
            chrome_options.add_argument('--accept-language=en-US,en;q=0.9')
            chrome_options.add_argument('--disable-blink-features=AutomationControlled')
            chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
            chrome_options.add_experimental_option('useAutomationExtension', False)
            
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Execute CDP commands to prevent detection
            driver.execute_cdp_cmd('Page.addScriptToEvaluateOnNewDocument', {
                'source': '''
                    Object.defineProperty(navigator, 'webdriver', {
                        get: () => undefined
                    })
                '''
            })
            
            return driver
        except Exception as e:
            logger.error(f"Failed to setup Selenium driver: {e}")
            return None

    def handle_test_connection(self):
        """Test connection to UAF LMS using Selenium"""
        try:
            driver = self.setup_selenium_driver()
            if not driver:
                response_data = {
                    'success': False, 
                    'message': 'Failed to initialize browser'
                }
                self.send_success_response(response_data)
                return
                
            try:
                driver.get('http://lms.uaf.edu.pk/login/index.php')
                
                # Wait for page to load
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "body"))
                )
                
                if "Learning Management System" in driver.title:
                    response_data = {
                        'success': True, 
                        'message': f'Connection to UAF LMS successful. Page title: {driver.title}'
                    }
                else:
                    response_data = {
                        'success': False, 
                        'message': f'Connected but unexpected page title: {driver.title}'
                    }
                    
            except TimeoutException:
                response_data = {
                    'success': False, 
                    'message': 'Connection timeout - page took too long to load'
                }
            except Exception as e:
                response_data = {
                    'success': False, 
                    'message': f'Connection failed: {str(e)}'
                }
            finally:
                driver.quit()
            
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

    def handle_scrape_single(self):
        """Handle single result scraping using Selenium"""
        try:
            if self.command == 'GET':
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
                    
                    success, message, result_data = self.scrape_with_selenium(registration_number)
                    response = {'success': success, 'message': message, 'resultData': result_data}
                    self.send_success_response(response)
                else:
                    self.send_error_response(400, 'No registration number provided')
            else:
                content_length = int(self.headers['Content-Length'])
                post_data = self.rfile.read(content_length)
                data = json.loads(post_data)
                
                registration_number = data.get('registrationNumber')
                if not registration_number:
                    self.send_error_response(400, 'No registration number provided')
                    return
                
                success, message, result_data = self.scrape_with_selenium(registration_number)
                response = {'success': success, 'message': message, 'resultData': result_data}
                self.send_success_response(response)
                
        except Exception as e:
            self.send_error_response(500, f"Error scraping single result: {str(e)}")

    def scrape_with_selenium(self, registration_number):
        """Scrape results using Selenium to mimic real browser behavior"""
        driver = None
        try:
            driver = self.setup_selenium_driver()
            if not driver:
                return False, "Failed to initialize browser", None
            
            # Navigate to login page
            driver.get('http://lms.uaf.edu.pk/login/index.php')
            
            # Wait for page to load completely
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.TAG_NAME, "body"))
            )
            
            # Wait a bit to mimic human behavior
            time.sleep(2)
            
            # Find the registration input field and submit button
            try:
                reg_input = WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "REG"))
                )
                submit_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//input[@type='submit' and @value='Result']"))
                )
                
                # Enter registration number and submit
                reg_input.clear()
                reg_input.send_keys(registration_number)
                time.sleep(1)  # Mimic human typing delay
                submit_button.click()
                
                # Wait for results to load
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.TAG_NAME, "table"))
                )
                
                # Get page source and parse results
                page_source = driver.page_source
                success, message, result_data = self.parse_uaf_results(page_source, registration_number)
                
                return success, message, result_data
                
            except TimeoutException:
                return False, "Timeout waiting for page elements to load", None
            except Exception as e:
                return False, f"Error interacting with page: {str(e)}", None
                
        except Exception as e:
            logger.error(f"Selenium scraping error: {str(e)}")
            return False, f"Scraping error: {str(e)}", None
        finally:
            if driver:
                driver.quit()

    def parse_uaf_results(self, html_content, registration_number):
        """Parse UAF results from HTML content"""
        try:
            soup = BeautifulSoup(html_content, 'html.parser')
            
            # Check for error messages
            page_text = soup.get_text().lower()
            if any(msg in page_text for msg in ['blocked', 'access denied', 'not available', 'no result', 'no records']):
                return False, "No results found or access denied", None
            
            # Extract student information
            student_info = {}
            info_tables = soup.find_all('table')
            
            for table in info_tables:
                rows = table.find_all('tr')
                for row in rows:
                    cols = row.find_all('td')
                    if len(cols) == 2:
                        key = cols[0].text.strip().replace(':', '').replace('#', '').replace(' ', '')
                        value = cols[1].text.strip()
                        if key and value:
                            student_info[key] = value
            
            student_info['Registration'] = registration_number
            
            # Extract results from tables
            student_results = []
            
            for table in soup.find_all('table'):
                rows = table.find_all('tr')
                
                if len(rows) > 3:
                    header_row = rows[0]
                    header_text = header_row.get_text().lower()
                    
                    result_indicators = ['sr', 'semester', 'course', 'teacher', 'credit', 'mid', 'assignment', 'final', 'practical', 'total', 'grade']
                    
                    if any(indicator in header_text for indicator in result_indicators):
                        for i in range(1, len(rows)):
                            row = rows[i]
                            cols = row.find_all('td')
                            
                            if len(cols) >= 8:
                                result_data = {
                                    'RegistrationNo': student_info.get('Registration', registration_number),
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
                                
                                if result_data['CourseCode'] or result_data['CourseTitle']:
                                    student_results.append(result_data)
            
            if student_results:
                return True, f"Successfully extracted {len(student_results)} records", student_results
            else:
                return False, "No result data found in the page", None
                    
        except Exception as e:
            logger.error(f"Error parsing results: {str(e)}")
            return False, f"Error parsing results: {str(e)}", None

    # [Keep all the other methods unchanged - handle_save_result, handle_load_result, etc.]
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
            
            init_db()
            result_id = hashlib.md5(f"{registration_number}_{timestamp}".encode()).hexdigest()
            
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            c.execute('SELECT id FROM saved_results WHERE registration_number = ? AND timestamp = ?', 
                     (registration_number, timestamp))
            existing_result = c.fetchone()
            
            if existing_result:
                c.execute('UPDATE saved_results SET student_data = ? WHERE id = ?', 
                         (json.dumps(student_data), existing_result[0]))
            else:
                c.execute('INSERT INTO saved_results (id, registration_number, student_data, timestamp) VALUES (?, ?, ?, ?)',
                         (result_id, registration_number, json.dumps(student_data), timestamp))
            
            conn.commit()
            conn.close()
            
            response_data = {'success': True, 'message': 'Result saved successfully', 'id': result_id}
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
            
            init_db()
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            c.execute('SELECT id, registration_number, student_data, timestamp FROM saved_results WHERE registration_number = ? ORDER BY timestamp DESC', 
                     (registration_number,))
            
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
            
            response_data = {'success': True, 'message': 'Results loaded successfully', 'savedResults': saved_results}
            self.send_success_response(response_data)
            
        except Exception as e:
            self.send_error_response(500, f"Error loading results: {str(e)}")

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
        
        success, message, result_data = self.scrape_with_selenium(registration_number)
        
        if success and result_data:
            self.save_to_session(session_id, result_data)
            
        response = {'success': success, 'message': message, 'resultData': result_data}
        self.send_success_response(response)

    def save_to_session(self, session_id, result_data):
        try:
            session_file = os.path.join(DATA_DIR, f"session_{session_id}.json")
            
            if os.path.exists(session_file):
                with open(session_file, 'r') as f:
                    existing_data = json.load(f)
            else:
                existing_data = []
            
            for result in result_data:
                result['_scrapedAt'] = datetime.now().isoformat()
            
            existing_data.extend(result_data)
            
            with open(session_file, 'w') as f:
                json.dump(existing_data, f)
                
        except Exception as e:
            logger.error(f"Error saving to session {session_id}: {e}")

    def load_from_session(self, session_id):
        try:
            session_file = os.path.join(DATA_DIR, f"session_{session_id}.json")
            
            if os.path.exists(session_file):
                with open(session_file, 'r') as f:
                    data = json.load(f)
                
                one_hour_ago = datetime.now() - timedelta(hours=1)
                filtered_data = [
                    item for item in data 
                    if '_scrapedAt' not in item or 
                    datetime.fromisoformat(item['_scrapedAt']) > one_hour_ago
                ]
                
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
        except Exception as e:
            logger.error(f"Error deleting session {session_id}: {e}")

# Initialize database when module is loaded
init_db()
