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
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import cloudscraper
from fp.fp import FreeProxy

# Disable SSL warnings
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# Set up logging
logging.basicConfig(level=logging.INFO)
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

# User agents - updated with more realistic ones
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/92.0.4515.107 Safari/537.36'
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

    def create_session_with_retry(self):
        """Create a requests session with retry logic"""
        session = requests.Session()
        
        # Configure retry strategy
        retry_strategy = Retry(
            total=3,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["GET", "POST"]
        )
        
        adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=10, pool_maxsize=10)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        
        return session

    def create_cloudscraper_session(self):
        """Create a cloudscraper session to bypass Cloudflare protection"""
        try:
            scraper = cloudscraper.create_scraper()
            return scraper
        except Exception as e:
            logger.error(f"Error creating cloudscraper session: {str(e)}")
            return self.create_session_with_retry()

    def get_proxy(self):
        """Get a free proxy server"""
        try:
            proxy = FreeProxy(rand=True, timeout=1).get()
            return {'http': proxy, 'https': proxy}
        except:
            return None

    def handle_test_connection(self):
        """Test connection to UAF LMS - improved version"""
        try:
            test_url = 'http://lms.uaf.edu.pk/login/index.php'
            
            # Try multiple approaches
            approaches = [
                self.test_direct_connection,
                self.test_with_cloudscraper,
                self.test_with_proxy
            ]
            
            success = False
            message = "All connection attempts failed"
            
            for approach in approaches:
                try:
                    success, message = approach(test_url)
                    if success:
                        break
                except Exception as e:
                    logger.error(f"Connection test approach failed: {str(e)}")
                    continue
            
            response_data = {
                'success': success, 
                'message': message
            }
            self.send_success_response(response_data)
            
        except Exception as e:
            response_data = {
                'success': False, 
                'message': f'Connection test error: {str(e)}'
            }
            self.send_success_response(response_data)

    def test_direct_connection(self, test_url):
        """Test direct connection"""
        session = self.create_session_with_retry()
        session.headers.update({
            'User-Agent': random.choice(USER_AGENTS),
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1',
        })
        
        try:
            response = session.get(test_url, timeout=15, verify=False)
            
            if response.status_code == 200:
                return True, f"Direct connection successful (Status: {response.status_code})"
            else:
                return False, f"UAF LMS returned status code: {response.status_code}"
                
        except requests.exceptions.RequestException as e:
            return False, f"Direct connection failed: {str(e)}"

    def test_with_cloudscraper(self, test_url):
        """Test connection using cloudscraper"""
        try:
            scraper = self.create_cloudscraper_session()
            response = scraper.get(test_url, timeout=15)
            
            if response.status_code == 200:
                return True, f"Cloudscraper connection successful (Status: {response.status_code})"
            else:
                return False, f"Cloudscraper connection failed with status: {response.status_code}"
                
        except Exception as e:
            return False, f"Cloudscraper connection failed: {str(e)}"

    def test_with_proxy(self, test_url):
        """Test connection using proxy"""
        try:
            proxy = self.get_proxy()
            if not proxy:
                return False, "No available proxies"
                
            session = self.create_session_with_retry()
            session.headers.update({
                'User-Agent': random.choice(USER_AGENTS),
            })
            
            response = session.get(test_url, proxies=proxy, timeout=15, verify=False)
            
            if response.status_code == 200:
                return True, f"Proxy connection successful (Status: {response.status_code})"
            else:
                return False, f"Proxy connection failed with status: {response.status_code}"
                
        except Exception as e:
            return False, f"Proxy connection failed: {str(e)}"

    # [Keep all other methods the same until the scrape_uaf_results method]

    def scrape_uaf_results(self, registration_number):
        """Main function to scrape UAF results with multiple fallback approaches"""
        approaches = [
            self.scrape_direct_method,
            self.scrape_with_cloudscraper,
            self.scrape_with_proxy
        ]
        
        for approach in approaches:
            try:
                success, message, result_data = approach(registration_number)
                if success:
                    return success, message, result_data
            except Exception as e:
                logger.error(f"Scraping approach failed: {str(e)}")
                continue
        
        # If all approaches fail, try the cached approach
        try:
            return self.scrape_from_cache(registration_number)
        except Exception as e:
            logger.error(f"Cached approach also failed: {str(e)}")
            return False, "All scraping methods failed. The UAF LMS may be down or blocking requests.", None

    def scrape_direct_method(self, registration_number):
        """Original scraping method"""
        try:
            session = self.create_session_with_retry()
            
            # Set realistic browser headers
            session.headers.update({
                'User-Agent': random.choice(USER_AGENTS),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Cache-Control': 'max-age=0',
                'Origin': 'http://lms.uaf.edu.pk',
                'Referer': 'http://lms.uaf.edu.pk/login/index.php'
            })
            
            # Step 1: Get login page to extract token
            login_url = "http://lms.uaf.edu.pk/login/index.php"
            try:
                logger.info(f"Fetching login page: {login_url}")
                response = session.get(login_url, timeout=15, verify=False)
                
                if response.status_code != 200:
                    return False, f"UAF LMS returned status code {response.status_code}. The server may be down.", None
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error fetching login page: {str(e)}")
                return False, f"Network error: {str(e)}. UAF LMS may be unavailable.", None
            
            # Step 2: Extract token from JavaScript
            token = self.extract_js_token(response.text)
            logger.info(f"Extracted token: {token}")
            
            if not token:
                # Try to find token in the HTML directly
                soup = BeautifulSoup(response.text, 'html.parser')
                token_input = soup.find('input', {'id': 'token'})
                if token_input and token_input.get('value'):
                    token = token_input.get('value')
                    logger.info(f"Found token in HTML: {token}")
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
                'Content-Type': 'application/x-www-form-urlencoded',
                'Host': 'lms.uaf.edu.pk'
            }
            
            try:
                logger.info(f"Submitting form to: {result_url}")
                response = session.post(result_url, data=form_data, headers=headers, timeout=20, verify=False)
                
                if response.status_code != 200:
                    return False, f"UAF LMS returned status code {response.status_code}", None
                    
                logger.info(f"Successfully received response from result page")
                    
            except requests.exceptions.RequestException as e:
                logger.error(f"Network error during result fetch: {str(e)}")
                return False, f"Network error during result fetch: {str(e)}", None
            
            # Step 4: Parse results
            success, message, result_data = self.parse_uaf_results(response.text, registration_number)
            
            # Cache successful results
            if success:
                self.cache_results(registration_number, result_data)
                
            return success, message, result_data
            
        except Exception as e:
            logger.error(f"Unexpected error in scrape_direct_method: {str(e)}")
            return False, f"Unexpected error: {str(e)}", None

    def scrape_with_cloudscraper(self, registration_number):
        """Scraping using cloudscraper to bypass protections"""
        try:
            scraper = self.create_cloudscraper_session()
            
            # Get login page
            login_url = "http://lms.uaf.edu.pk/login/index.php"
            response = scraper.get(login_url, timeout=15)
            
            if response.status_code != 200:
                return False, f"Cloudscraper failed with status {response.status_code}", None
            
            # Extract token
            token = self.extract_js_token(response.text)
            if not token:
                soup = BeautifulSoup(response.text, 'html.parser')
                token_input = soup.find('input', {'id': 'token'})
                if token_input and token_input.get('value'):
                    token = token_input.get('value')
                else:
                    return False, "Could not extract security token with cloudscraper", None
            
            # Submit form
            result_url = "http://lms.uaf.edu.pk/course/uaf_student_result.php"
            form_data = {
                'token': token,
                'Register': registration_number
            }
            
            response = scraper.post(result_url, data=form_data, timeout=20)
            
            if response.status_code != 200:
                return False, f"Cloudscraper form submission failed with status {response.status_code}", None
            
            # Parse results
            success, message, result_data = self.parse_uaf_results(response.text, registration_number)
            
            # Cache successful results
            if success:
                self.cache_results(registration_number, result_data)
                
            return success, message, result_data
            
        except Exception as e:
            logger.error(f"Error in scrape_with_cloudscraper: {str(e)}")
            return False, f"Cloudscraper error: {str(e)}", None

    def scrape_with_proxy(self, registration_number):
        """Scraping using proxy server"""
        try:
            proxy = self.get_proxy()
            if not proxy:
                return False, "No proxies available", None
                
            session = self.create_session_with_retry()
            session.headers.update({
                'User-Agent': random.choice(USER_AGENTS),
            })
            
            # Get login page
            login_url = "http://lms.uaf.edu.pk/login/index.php"
            response = session.get(login_url, proxies=proxy, timeout=15, verify=False)
            
            if response.status_code != 200:
                return False, f"Proxy connection failed with status {response.status_code}", None
            
            # Extract token
            token = self.extract_js_token(response.text)
            if not token:
                soup = BeautifulSoup(response.text, 'html.parser')
                token_input = soup.find('input', {'id': 'token'})
                if token_input and token_input.get('value'):
                    token = token_input.get('value')
                else:
                    return False, "Could not extract security token with proxy", None
            
            # Submit form
            result_url = "http://lms.uaf.edu.pk/course/uaf_student_result.php"
            form_data = {
                'token': token,
                'Register': registration_number
            }
            
            headers = {
                'Referer': login_url,
                'Origin': 'http://lms.uaf.edu.pk',
                'Content-Type': 'application/x-www-form-urlencoded',
            }
            
            response = session.post(result_url, data=form_data, headers=headers, 
                                  proxies=proxy, timeout=20, verify=False)
            
            if response.status_code != 200:
                return False, f"Proxy form submission failed with status {response.status_code}", None
            
            # Parse results
            success, message, result_data = self.parse_uaf_results(response.text, registration_number)
            
            # Cache successful results
            if success:
                self.cache_results(registration_number, result_data)
                
            return success, message, result_data
            
        except Exception as e:
            logger.error(f"Error in scrape_with_proxy: {str(e)}")
            return False, f"Proxy error: {str(e)}", None

    def scrape_from_cache(self, registration_number):
        """Try to get results from cache if direct scraping fails"""
        cache_file = os.path.join(DATA_DIR, f"cache_{registration_number}.json")
        
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    cached_data = json.load(f)
                
                # Check if cache is still valid (less than 24 hours old)
                cache_time = datetime.fromisoformat(cached_data.get('timestamp', ''))
                if datetime.now() - cache_time < timedelta(hours=24):
                    return True, "Results retrieved from cache", cached_data['result_data']
            except Exception as e:
                logger.error(f"Error reading cache: {str(e)}")
        
        return False, "No valid cache available", None

    def cache_results(self, registration_number, result_data):
        """Cache results for future use"""
        try:
            cache_file = os.path.join(DATA_DIR, f"cache_{registration_number}.json")
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'result_data': result_data
            }
            
            with open(cache_file, 'w') as f:
                json.dump(cache_data, f)
                
            logger.info(f"Results cached for {registration_number}")
        except Exception as e:
            logger.error(f"Error caching results: {str(e)}")

    # [Keep all other methods the same]

# Initialize database when module is loaded
init_db()
