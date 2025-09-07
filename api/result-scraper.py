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
import threading
import concurrent.futures
import asyncio
import aiohttp
import async_timeout
from urllib.parse import urljoin, urlparse
import brotli
import gzip
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Use /tmp directory for session storage
DATA_DIR = "/tmp/uaftools_data"
if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

# Database path
DB_PATH = os.path.join(DATA_DIR, "saved_results.db")

# Cache for tokens and sessions to avoid repeated extraction
TOKEN_CACHE = {}
SESSION_CACHE = {}
CACHE_LOCK = threading.Lock()

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
    c.execute('''
        CREATE TABLE IF NOT EXISTS cache (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            expiry DATETIME NOT NULL
        )
    ''')
    c.execute('''
        CREATE INDEX IF NOT EXISTS idx_cache_expiry 
        ON cache (expiry)
    ''')
    conn.commit()
    conn.close()

# User agents
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0'
]

# Create a session with retry strategy
def create_session():
    session = requests.Session()
    
    # Configure retry strategy
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["GET", "POST"]
    )
    
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=20)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    
    session.headers.update({
        'User-Agent': random.choice(USER_AGENTS),
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0',
    })
    
    return session

# Cache management functions
def get_cached_value(key):
    try:
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('SELECT value FROM cache WHERE key = ? AND expiry > datetime("now")', (key,))
        result = c.fetchone()
        conn.close()
        return json.loads(result[0]) if result else None
    except:
        return None

def set_cached_value(key, value, ttl_minutes=10):
    try:
        expiry = datetime.now() + timedelta(minutes=ttl_minutes)
        conn = sqlite3.connect(DB_PATH)
        c = conn.cursor()
        c.execute('''
            INSERT OR REPLACE INTO cache (key, value, expiry)
            VALUES (?, ?, ?)
        ''', (key, json.dumps(value), expiry))
        conn.commit()
        conn.close()
    except:
        pass

class handler(BaseHTTPRequestHandler):
    def _set_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Session-Id, session_id')
    
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
            elif 'action=bulk_status' in self.path:
                self.handle_bulk_status()
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
            elif 'action=scrape_bulk' in self.path:
                self.handle_scrape_bulk()
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

    def handle_test_connection(self):
        """Test connection to UAF LMS - simplified version"""
        try:
            # Try multiple endpoints to test connection - updated to HTTPS
            test_urls = [
                'https://lms.uaf.edu.pk/login/index.php',
                'https://lms.uaf.edu.pk/',
                'https://lms.uaf.edu.pk'
            ]
            
            success = False
            message = "UAF LMS is not responding"
            response_time = None
            
            for test_url in test_urls:
                try:
                    start_time = time.time()
                    response = requests.get(test_url, timeout=10, headers={
                        'User-Agent': random.choice(USER_AGENTS),
                    }, verify=True)
                    response_time = time.time() - start_time
                    
                    # If we get any response (even 500), the server is reachable
                    if response.status_code < 500:
                        success = True
                        message = f"Connection to UAF LMS successful (Status: {response.status_code}, Response Time: {response_time:.2f}s)"
                        break
                    else:
                        message = f"UAF LMS returned status code: {response.status_code}"
                        
                except requests.exceptions.SSLError:
                    # Try without SSL verification if there's an SSL error
                    try:
                        start_time = time.time()
                        response = requests.get(test_url, timeout=10, headers={
                            'User-Agent': random.choice(USER_AGENTS),
                        }, verify=False)
                        response_time = time.time() - start_time
                        
                        if response.status_code < 500:
                            success = True
                            message = f"Connection to UAF LMS successful with SSL verification disabled (Status: {response.status_code}, Response Time: {response_time:.2f}s)"
                            break
                        else:
                            message = f"UAF LMS returned status code: {response.status_code}"
                    except:
                        continue
                except requests.exceptions.RequestException as e:
                    # Continue to next URL if this one fails
                    continue
            
            response_data = {
                'success': success, 
                'message': message,
                'responseTime': response_time
            }
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
        """Handle single result scraping for CGPA calculator"""
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
                    
                    # Check cache first
                    cache_key = f"result_{registration_number}"
                    cached_result = get_cached_value(cache_key)
                    
                    if cached_result:
                        response = {
                            'success': True, 
                            'message': 'Result loaded from cache', 
                            'resultData': cached_result,
                            'cached': True
                        }
                        self.send_success_response(response)
                        return
                    
                    # Scrape results
                    success, message, result_data = self.scrape_uaf_results(registration_number)
                    
                    if success and result_data:
                        # Cache the result for 10 minutes
                        set_cached_value(cache_key, result_data, 10)
                        response = {
                            'success': success, 
                            'message': message, 
                            'resultData': result_data,
                            'cached': False
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
                
                # Check cache first
                cache_key = f"result_{registration_number}"
                cached_result = get_cached_value(cache_key)
                
                if cached_result:
                    response = {
                        'success': True, 
                        'message': 'Result loaded from cache', 
                        'resultData': cached_result,
                        'cached': True
                    }
                    self.send_success_response(response)
                    return
                
                # Scrape results
                success, message, result_data = self.scrape_uaf_results(registration_number)
                
                if success and result_data:
                    # Cache the result for 10 minutes
                    set_cached_value(cache_key, result_data, 10)
                    response = {
                        'success': success, 
                        'message': message, 
                        'resultData': result_data,
                        'cached': False
                    }
                else:
                    response = {'success': success, 'message': message, 'resultData': result_data}
                
                self.send_success_response(response)
                
        except Exception as e:
            self.send_error_response(500, f"Error scraping single result: {str(e)}")

    def handle_scrape_bulk(self):
        """Handle bulk scraping of multiple registration numbers"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            
            registration_numbers = data.get('registrationNumbers', [])
            session_id = data.get('sessionId')
            
            if not registration_numbers:
                self.send_error_response(400, 'No registration numbers provided')
                return
                
            if not session_id:
                self.send_error_response(400, 'No session ID provided')
                return
            
            # Start bulk scraping in background thread
            thread = threading.Thread(
                target=self.bulk_scrape_worker,
                args=(registration_numbers, session_id)
            )
            thread.daemon = True
            thread.start()
            
            response_data = {
                'success': True, 
                'message': f'Bulk scraping started for {len(registration_numbers)} registration numbers',
                'total': len(registration_numbers)
            }
            self.send_success_response(response_data)
            
        except Exception as e:
            self.send_error_response(500, f"Error starting bulk scrape: {str(e)}")

    def bulk_scrape_worker(self, registration_numbers, session_id):
        """Worker function for bulk scraping"""
        try:
            # Create progress tracking file
            progress_file = os.path.join(DATA_DIR, f"progress_{session_id}.json")
            progress_data = {
                'total': len(registration_numbers),
                'completed': 0,
                'successful': 0,
                'failed': 0,
                'results': [],
                'startTime': datetime.now().isoformat(),
                'status': 'running'
            }
            
            with open(progress_file, 'w') as f:
                json.dump(progress_data, f)
            
            # Use ThreadPoolExecutor for concurrent scraping
            with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
                # Map registration numbers to executor
                future_to_reg = {
                    executor.submit(self.scrape_uaf_results, reg): reg 
                    for reg in registration_numbers
                }
                
                for future in concurrent.futures.as_completed(future_to_reg):
                    reg = future_to_reg[future]
                    try:
                        success, message, result_data = future.result()
                        
                        # Update progress
                        with open(progress_file, 'r') as f:
                            progress_data = json.load(f)
                        
                        progress_data['completed'] += 1
                        
                        if success and result_data:
                            progress_data['successful'] += 1
                            # Save to session
                            self.save_to_session(session_id, result_data)
                            progress_data['results'].append({
                                'registrationNumber': reg,
                                'success': True,
                                'count': len(result_data)
                            })
                        else:
                            progress_data['failed'] += 1
                            progress_data['results'].append({
                                'registrationNumber': reg,
                                'success': False,
                                'error': message
                            })
                        
                        # Save progress
                        with open(progress_file, 'w') as f:
                            json.dump(progress_data, f)
                            
                    except Exception as e:
                        # Update progress on error
                        with open(progress_file, 'r') as f:
                            progress_data = json.load(f)
                        
                        progress_data['completed'] += 1
                        progress_data['failed'] += 1
                        progress_data['results'].append({
                            'registrationNumber': reg,
                            'success': False,
                            'error': str(e)
                        })
                        
                        # Save progress
                        with open(progress_file, 'w') as f:
                            json.dump(progress_data, f)
            
            # Mark as completed
            with open(progress_file, 'r') as f:
                progress_data = json.load(f)
            
            progress_data['status'] = 'completed'
            progress_data['endTime'] = datetime.now().isoformat()
            
            with open(progress_file, 'w') as f:
                json.dump(progress_data, f)
                
        except Exception as e:
            logger.error(f"Error in bulk scrape worker: {str(e)}")

    def handle_bulk_status(self):
        """Get status of bulk scraping operation"""
        try:
            session_id = self.headers.get('Session-Id') or self.headers.get('session_id')
            if not session_id:
                self.send_error_response(400, 'No session ID provided')
                return
                
            progress_file = os.path.join(DATA_DIR, f"progress_{session_id}.json")
            
            if os.path.exists(progress_file):
                with open(progress_file, 'r') as f:
                    progress_data = json.load(f)
                
                response_data = {
                    'success': True,
                    'progress': progress_data
                }
            else:
                response_data = {
                    'success': False,
                    'message': 'No bulk operation found for this session'
                }
                
            self.send_success_response(response_data)
            
        except Exception as e:
            self.send_error_response(500, f"Error getting bulk status: {str(e)}")

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
            
            # Initialize database
            init_db()
            
            # Generate unique ID
            result_id = hashlib.md5(f"{registration_number}_{timestamp}".encode()).hexdigest()
            
            # Save to database
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            # Check if result already exists for this registration number and timestamp
            c.execute('''
                SELECT id FROM saved_results 
                WHERE registration_number = ? AND timestamp = ?
            ''', (registration_number, timestamp))
            
            existing_result = c.fetchone()
            
            if existing_result:
                # Update existing record
                c.execute('''
                    UPDATE saved_results 
                    SET student_data = ?
                    WHERE id = ?
                ''', (json.dumps(student_data), existing_result[0]))
            else:
                # Insert new record
                c.execute('''
                    INSERT INTO saved_results (id, registration_number, student_data, timestamp)
                    VALUES (?, ?, ?, ?)
                ''', (result_id, registration_number, json.dumps(student_data), timestamp))
            
            conn.commit()
            conn.close()
            
            response_data = {
                'success': True, 
                'message': 'Result saved successfully',
                'id': result_id
            }
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
            
            # Initialize database
            init_db()
            
            # Load from database
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            c.execute('''
                SELECT id, registration_number, student_data, timestamp
                FROM saved_results 
                WHERE registration_number = ?
                ORDER BY timestamp DESC
            ''', (registration_number,))
            
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
            
            response_data = {
                'success': True, 
                'message': 'Results loaded successfully',
                'savedResults': saved_results
            }
            self.send_success_response(response_data)
            
        except Exception as e:
            self.send_error_response(500, f"Error loading results: {str(e)}")

    def handle_delete_saved_result(self):
        """Delete a saved result from database"""
        try:
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length)
            data = json.loads(post_data)
            
            result_id = data.get('id')
            
            if not result_id:
                self.send_error_response(400, 'No result ID provided')
                return
            
            # Initialize database
            init_db()
            
            # Delete from database
            conn = sqlite3.connect(DB_PATH)
            c = conn.cursor()
            
            c.execute('DELETE FROM saved_results WHERE id = ?', (result_id,))
            conn.commit()
            conn.close()
            
            response_data = {
                'success': True, 
                'message': 'Result deleted successfully'
            }
            self.send_success_response(response_data)
            
        except Exception as e:
            self.send_error_response(500, f"Error deleting result: {str(e)}")

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
        
        # Check cache first
        cache_key = f"result_{registration_number}"
        cached_result = get_cached_value(cache_key)
        
        if cached_result:
            # Save cached result to session
            self.save_to_session(session_id, cached_result)
            response = {
                'success': True, 
                'message': 'Result loaded from cache', 
                'resultData': cached_result,
                'cached': True
            }
            self.send_success_response(response)
            return
        
        # Scrape results
        success, message, result_data = self.scrape_uaf_results(registration_number)
        
        # Save result to session file if successful
        if success and result_data:
            self.save_to_session(session_id, result_data)
            # Cache the result
            set_cached_value(cache_key, result_data, 10)
            
        response = {
            'success': success, 
            'message': message, 
            'resultData': result_data,
            'cached': False
        }
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

    def scrape_uaf_results(self, registration_number):
        """Main function to scrape UAF results"""
        try:
            # Check if we have a cached token and session
            cache_key = f"token_session_{hashlib.md5(registration_number.encode()).hexdigest()}"
            cached_data = get_cached_value(cache_key)
            
            if cached_data and 'token' in cached_data and 'session' in cached_data:
                # Use cached token and session
                token = cached_data['token']
                session = cached_data['session']
                logger.info(f"Using cached token and session for {registration_number}")
            else:
                # Create new session and extract token
                session = create_session()
                
                # Step 1: Get login page to extract token - updated to HTTPS
                login_url = "https://lms.uaf.edu.pk/login/index.php"
                try:
                    response = session.get(login_url, timeout=15, verify=True)
                    
                    if response.status_code != 200:
                        # Try without SSL verification if there's an SSL error
                        response = session.get(login_url, timeout=15, verify=False)
                        
                        if response.status_code != 200:
                            return False, f"UAF LMS returned status code {response.status_code}. The server may be down.", None
                        
                except requests.exceptions.SSLError:
                    # Try without SSL verification
                    try:
                        response = session.get(login_url, timeout=15, verify=False)
                        
                        if response.status_code != 200:
                            return False, f"UAF LMS returned status code {response.status_code}. The server may be down.", None
                            
                    except requests.exceptions.RequestException as e:
                        return False, f"Network error: {str(e)}. UAF LMS may be unavailable.", None
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
                
                # Cache the token and session for future use
                set_cached_value(cache_key, {
                    'token': token,
                    'session': session.cookies.get_dict()
                }, 5)  # Cache for 5 minutes
            
            # Step 3: Submit form with correct field names - updated to HTTPS
            result_url = "https://lms.uaf.edu.pk/course/uaf_student_result.php"
            form_data = {
                'token': token,
                'Register': registration_number
            }
            
            headers = {
                'Referer': 'https://lms.uaf.edu.pk/login/index.php',
                'Origin': 'https://lms.uaf.edu.pk',
                'Content-Type': 'application/x-www-form-urlencoded'
            }
            
            try:
                # If we have a cached session, restore cookies
                if cached_data and 'session' in cached_data:
                    session.cookies.update(cached_data['session'])
                
                response = session.post(result_url, data=form_data, headers=headers, timeout=20, verify=True)
                
                if response.status_code != 200:
                    # Try without SSL verification if there's an SSL error
                    response = session.post(result_url, data=form_data, headers=headers, timeout=20, verify=False)
                    
                    if response.status_code != 200:
                        return False, f"UAF LMS returned status code {response.status_code}", None
                    
            except requests.exceptions.SSLError:
                # Try without SSL verification
                try:
                    response = session.post(result_url, data=form_data, headers=headers, timeout=20, verify=False)
                    
                    if response.status_code != 200:
                        return False, f"UAF LMS returned status code {response.status_code}", None
                        
                except requests.exceptions.RequestException as e:
                    return False, f"Network error during result fetch: {str(e)}", None
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

# Initialize database when module is loaded
init_db()
