#!/usr/bin/env python3
"""
uaf_server.py
Complete single-file HTTP server for scraping UAF LMS results and managing sessions/saved results.

Usage:
    python uaf_server.py
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os
import re
import time
import random
import logging
import hashlib
import sqlite3
from io import BytesIO
from datetime import datetime, timedelta
from urllib.parse import urlparse, parse_qs, unquote_plus

import requests
import urllib3
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry
from bs4 import BeautifulSoup
from openpyxl import Workbook
from fake_useragent import UserAgent

# ------------------ CONFIG ------------------
HOST = "0.0.0.0"
PORT = 8080

DATA_DIR = "/tmp/uaftools_data"
DB_PATH = os.path.join(DATA_DIR, "saved_results.db")

BASE_URL = "http://lms.uaf.edu.pk"
LOGIN_URL = f"{BASE_URL}/login/index.php"
ALT_HOME_URL = f"{BASE_URL}/"
RESULT_URL = f"{BASE_URL}/course/uaf_student_result.php"

REQUEST_TIMEOUT = 15
MAX_RETRIES = 5
TOKEN_CACHE_TTL = 120  # seconds

# Ensure data dir exists
os.makedirs(DATA_DIR, exist_ok=True)

# ------------------ LOGGING ------------------
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("UAFTools")

# ------------------ USER-AGENT ------------------
try:
    ua = UserAgent()
except Exception:
    ua = None

def get_random_user_agent():
    if ua:
        try:
            return ua.random
        except Exception:
            pass
    fallback = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
    ]
    return random.choice(fallback)

# ------------------ DB ------------------
def init_db():
    with sqlite3.connect(DB_PATH) as conn:
        c = conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS saved_results (
                id TEXT PRIMARY KEY,
                registration_number TEXT NOT NULL,
                student_data TEXT NOT NULL,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        c.execute('CREATE INDEX IF NOT EXISTS idx_registration_number ON saved_results (registration_number)')
        conn.commit()

init_db()

# ------------------ TOKEN CACHE ------------------
_token_cache = {
    # "token": ("token_value", timestamp)
}

def cache_token(key, token_value):
    _token_cache[key] = (token_value, time.time())

def get_cached_token(key):
    val = _token_cache.get(key)
    if not val:
        return None
    token_value, ts = val
    if time.time() - ts > TOKEN_CACHE_TTL:
        del _token_cache[key]
        return None
    return token_value

# ------------------ HTTP SESSION WITH RETRIES ------------------
def create_session_with_retry():
    session = requests.Session()
    retry_strategy = Retry(
        total=MAX_RETRIES,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "POST"],
        respect_retry_after_header=True
    )
    adapter = HTTPAdapter(max_retries=retry_strategy, pool_connections=100, pool_maxsize=100)
    session.mount("http://", adapter)
    session.mount("https://", adapter)
    session.headers.update({
        "User-Agent": get_random_user_agent(),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
        "Connection": "keep-alive"
    })
    return session

# ------------------ UTIL ------------------
def json_response(handler, status_code, payload):
    handler.send_response(status_code)
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
    handler.send_header('Access-Control-Allow-Headers', 'Content-Type, Session-Id')
    handler.send_header('Content-Type', 'application/json')
    handler.end_headers()
    handler.wfile.write(json.dumps(payload, default=str).encode())

def parse_json_body(handler):
    length = int(handler.headers.get('Content-Length', '0') or 0)
    if length == 0:
        return {}
    raw = handler.rfile.read(length)
    try:
        return json.loads(raw.decode('utf-8'))
    except Exception:
        return {}

def parse_query_params(path):
    p = urlparse(path)
    return {k: v for k, v in ((kk, vv[0]) for kk, vv in parse_qs(p.query).items())}

# ------------------ SCRAPER & PARSERS ------------------
def extract_js_token(html_content):
    try:
        # common pattern: hidden input #token
        soup = BeautifulSoup(html_content, 'html.parser')
        token_input = soup.find('input', {'id': 'token'})
        if token_input and token_input.get('value'):
            return token_input.get('value')

        # javascript assignment
        script_pattern = r"document\.getElementById\(['\"]token['\"]\)\.value\s*=\s*['\"]([a-f0-9]{32,128})['\"]"
        m = re.search(script_pattern, html_content, re.IGNORECASE | re.DOTALL)
        if m:
            return m.group(1)

        # any 64 char hex-ish token
        token_pattern = r"\b[a-f0-9]{64}\b"
        m2 = re.search(token_pattern, html_content, re.IGNORECASE)
        if m2:
            return m2.group(0)

        # fallback: look for a shorter hex
        token_pattern2 = r"\b[a-f0-9]{32}\b"
        m3 = re.search(token_pattern2, html_content, re.IGNORECASE)
        if m3:
            return m3.group(0)

        return None
    except Exception as e:
        logger.exception("extract_js_token error")
        return None

def parse_uaf_results(html_content, registration_number):
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        page_text = soup.get_text().lower()

        # common blocking or no results phrases
        if any(term in page_text for term in ['blocked', 'access denied', 'not available', 'suspended', 'forbidden']):
            return False, "Access blocked by UAF LMS", None
        if any(term in page_text for term in ['no result', 'no records', 'no results found']):
            return False, f"No results found for registration number: {registration_number}", None

        # grab student meta from smaller info tables
        student_info = {}
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            for r in rows:
                cols = r.find_all('td')
                if len(cols) == 2:
                    k = cols[0].get_text(separator=' ', strip=True)
                    v = cols[1].get_text(separator=' ', strip=True)
                    if k and v:
                        student_info[k.replace(':', '').strip()] = v

        if 'Registration' not in student_info:
            student_info['Registration'] = registration_number

        results = []
        # Look for tables that look like results tables
        for table in soup.find_all('table'):
            rows = table.find_all('tr')
            if len(rows) < 3:
                continue

            header_text = rows[0].get_text(separator=' ', strip=True).lower()
            result_indicators = ['semester', 'course', 'grade', 'final', 'total', 'credit']
            if not any(ind in header_text for ind in result_indicators):
                continue

            # iterate rows after header
            for row in rows[1:]:
                cols = row.find_all(['td', 'th'])
                texts = [c.get_text(strip=True) for c in cols]
                if len(texts) < 2:
                    continue

                # build a flexible mapping depending on column count
                entry = {
                    'RegistrationNo': student_info.get('Registration', registration_number),
                    'StudentName': student_info.get('Student Name', student_info.get('StudentFullName', '')),
                    'SrNo': texts[0] if len(texts) > 0 else '',
                    'Semester': texts[1] if len(texts) > 1 else '',
                    'CourseCode': texts[3] if len(texts) > 3 else '',
                    'CourseTitle': texts[4] if len(texts) > 4 else '',
                    'CreditHours': texts[5] if len(texts) > 5 else '',
                    'Mid': texts[6] if len(texts) > 6 else '',
                    'Assignment': texts[7] if len(texts) > 7 else '',
                    'Final': texts[8] if len(texts) > 8 else '',
                    'Practical': texts[9] if len(texts) > 9 else '',
                    'Total': texts[10] if len(texts) > 10 else '',
                    'Grade': texts[11] if len(texts) > 11 else ''
                }

                if entry['CourseCode'] or entry['CourseTitle']:
                    results.append(entry)

        if results:
            return True, f"Successfully extracted {len(results)} records for {registration_number}", results

        # try alternative parsing if the above fails
        alt = alternative_parse(soup, registration_number, student_info)
        if alt:
            return True, f"Successfully extracted {len(alt)} records using alternative method", alt

        return False, f"No result data found for registration number: {registration_number}", None
    except Exception as e:
        logger.exception("parse_uaf_results error")
        return False, f"Error parsing results: {str(e)}", None

def alternative_parse(soup, registration_number, student_info):
    try:
        results = []
        tables = soup.find_all('table')
        for table in tables:
            rows = table.find_all('tr')
            if len(rows) < 2:
                continue
            for idx, row in enumerate(rows):
                if idx == 0:
                    continue
                cols = row.find_all('td')
                texts = [c.get_text(strip=True) for c in cols]
                if len(texts) >= 4:
                    entry = {
                        'RegistrationNo': registration_number,
                        'StudentName': student_info.get('StudentFullName', student_info.get('StudentName', '')),
                        'SrNo': texts[0] if len(texts) > 0 else '',
                        'Semester': texts[1] if len(texts) > 1 else '',
                        'CourseCode': texts[2] if len(texts) > 2 else '',
                        'CourseTitle': texts[3] if len(texts) > 3 else '',
                        'CreditHours': texts[4] if len(texts) > 4 else '',
                        'Mid': texts[5] if len(texts) > 5 else '',
                        'Final': texts[6] if len(texts) > 6 else '',
                        'Total': texts[7] if len(texts) > 7 else '',
                        'Grade': texts[8] if len(texts) > 8 else ''
                    }
                    if entry['CourseCode'] or entry['CourseTitle']:
                        results.append(entry)
        return results if results else None
    except Exception:
        logger.exception("alternative_parse error")
        return None

def scrape_uaf_results(registration_number):
    """High-level scraping function that tries multiple methods & caches token."""
    try:
        session = create_session_with_retry()

        # attempt to reuse cached token
        token = get_cached_token('login_token')
        if not token:
            # try main login url
            try:
                logger.info("Fetching login page for token...")
                resp = session.get(LOGIN_URL, timeout=REQUEST_TIMEOUT, verify=False)
                if resp.status_code == 200:
                    token = extract_js_token(resp.text)
                    if token:
                        cache_token('login_token', token)
                        logger.info("Token cached from login page")
            except Exception as e:
                logger.warning("Failed to fetch login page: %s", e)

        # try alternative home page
        if not token:
            try:
                logger.info("Trying alt home url for token...")
                resp = session.get(ALT_HOME_URL, timeout=REQUEST_TIMEOUT, verify=False)
                if resp.status_code == 200:
                    token = extract_js_token(resp.text)
                    if token:
                        cache_token('login_token', token)
                        logger.info("Token cached from alt home page")
            except Exception as e:
                logger.warning("Alt home fetch failed: %s", e)

        # if no token found, fallback to a static token (last resort)
        if not token:
            token = "7026cf7bcd105d50c715f01c4ccd8a2a665ea5fb2c76aaa5806d4103314fcf0f"
            logger.info("Using fallback static token (last resort)")

        # submit form
        form_data = {
            'token': token,
            'Register': registration_number
        }
        headers = {
            'Referer': LOGIN_URL,
            'Origin': BASE_URL,
            'Content-Type': 'application/x-www-form-urlencoded',
            'Host': urlparse(BASE_URL).netloc
        }

        try:
            logger.info(f"Submitting result request for {registration_number}")
            resp = session.post(RESULT_URL, data=form_data, headers=headers, timeout=20, verify=False)
        except requests.exceptions.RequestException as e:
            logger.exception("Network error during result fetch")
            return False, f"Network error during result fetch: {str(e)}", None

        if resp.status_code != 200:
            return False, f"UAF LMS returned status code {resp.status_code}", None

        return parse_uaf_results(resp.text, registration_number)

    except Exception as e:
        logger.exception("Unexpected error in scrape_uaf_results")
        return False, f"Unexpected error: {str(e)}", None

# ------------------ SESSION FILE MANAGEMENT ------------------
def session_file_path(session_id):
    return os.path.join(DATA_DIR, f"session_{session_id}.json")

def save_to_session(session_id, result_data):
    try:
        path = session_file_path(session_id)
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                existing = json.load(f)
        else:
            existing = []

        # Ensure we append timestamp to each record
        now = datetime.now().isoformat()
        for r in result_data:
            r['_scrapedAt'] = now

        existing.extend(result_data)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(existing, f, ensure_ascii=False, indent=0)
        logger.info("Saved %d records to session %s", len(result_data), session_id)
    except Exception:
        logger.exception("Error saving to session")

def load_from_session(session_id):
    try:
        path = session_file_path(session_id)
        if not os.path.exists(path):
            return None

        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # remove items older than 1 hour
        one_hour_ago = datetime.now() - timedelta(hours=1)
        filtered = []
        for item in data:
            if '_scrapedAt' not in item:
                filtered.append(item)
            else:
                try:
                    ts = datetime.fromisoformat(item['_scrapedAt'])
                    if ts > one_hour_ago:
                        filtered.append(item)
                except Exception:
                    filtered.append(item)

        if len(filtered) != len(data):
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(filtered, f, ensure_ascii=False, indent=0)

        return filtered
    except Exception:
        logger.exception("Error loading from session")
        return None

def delete_session(session_id):
    try:
        path = session_file_path(session_id)
        if os.path.exists(path):
            os.remove(path)
            logger.info("Deleted session %s", session_id)
    except Exception:
        logger.exception("Error deleting session")

# ------------------ DATABASE SAVES/LOADS ------------------
def save_result_to_db(registration_number, student_data, timestamp=None):
    try:
        if timestamp is None:
            timestamp = datetime.now().isoformat()
        result_id = hashlib.md5(f"{registration_number}_{timestamp}".encode()).hexdigest()
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            # Check if a record exists with same registration_number & timestamp
            c.execute("SELECT id FROM saved_results WHERE registration_number = ? AND timestamp = ?", (registration_number, timestamp))
            existing = c.fetchone()
            if existing:
                c.execute("UPDATE saved_results SET student_data = ? WHERE id = ?", (json.dumps(student_data), existing[0]))
                result_id = existing[0]
            else:
                c.execute("INSERT INTO saved_results (id, registration_number, student_data, timestamp) VALUES (?, ?, ?, ?)",
                          (result_id, registration_number, json.dumps(student_data), timestamp))
            conn.commit()
        return True, result_id
    except Exception as e:
        logger.exception("save_result_to_db error")
        return False, str(e)

def load_saved_results_from_db(registration_number):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("SELECT id, registration_number, student_data, timestamp FROM saved_results WHERE registration_number = ? ORDER BY timestamp DESC", (registration_number,))
            rows = c.fetchall()
        results = []
        for r in rows:
            results.append({
                'id': r[0],
                'registration_number': r[1],
                'student_data': json.loads(r[2]),
                'timestamp': r[3]
            })
        return True, results
    except Exception:
        logger.exception("load_saved_results_from_db error")
        return False, str(Exception)

def delete_saved_result_from_db(result_id):
    try:
        with sqlite3.connect(DB_PATH) as conn:
            c = conn.cursor()
            c.execute("DELETE FROM saved_results WHERE id = ?", (result_id,))
            conn.commit()
        return True, None
    except Exception as e:
        logger.exception("delete_saved_result_from_db error")
        return False, str(e)

# ------------------ HTTP REQUEST HANDLER ------------------
class handler(BaseHTTPRequestHandler):

    def _set_cors_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS, DELETE')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Session-Id')

    def do_OPTIONS(self):
        self.send_response(200)
        self._set_cors_headers()
        self.end_headers()

    def do_GET(self):
        try:
            q = parse_query_params(self.path)

            # Basic endpoints
            action = q.get('action') or q.get('a') or ''
            if 'test' == action or 'action=test' in self.path:
                return self.handle_test_connection()
            if 'check_session' == action:
                return self.handle_check_session()
            if 'scrape_single' == action:
                return self.handle_scrape_single_get(q)
            if 'load_result' == action or 'load_result' in self.path:
                return self.handle_load_result(q)

            # unknown
            json_response(self, 404, {'success': False, 'message': 'Unknown endpoint'})
        except Exception as e:
            logger.exception("do_GET error")
            json_response(self, 500, {'success': False, 'message': str(e)})

    def do_POST(self):
        try:
            path_q = parse_query_params(self.path)
            action = path_q.get('action') or ''

            if 'scrape' == action or 'action=scrape' in self.path:
                return self.handle_scrape()
            if 'save' == action or 'save_result' in self.path:
                return self.handle_save_result()
            if 'clear_session' == action:
                return self.handle_clear_session()
            if 'scrape_single' == action:
                return self.handle_scrape_single_post()
            if 'savefile' == action or 'action=savefile' in self.path:
                return self.handle_savefile_excel()
            # default
            json_response(self, 404, {'success': False, 'message': 'Unknown POST endpoint'})
        except Exception as e:
            logger.exception("do_POST error")
            json_response(self, 500, {'success': False, 'message': str(e)})

    def do_DELETE(self):
        try:
            path_q = parse_query_params(self.path)
            action = path_q.get('action') or ''
            if 'save' == action or 'save_result' in self.path:
                # treat as delete saved result
                return self.handle_delete_saved_result()
            json_response(self, 404, {'success': False, 'message': 'Unknown DELETE endpoint'})
        except Exception as e:
            logger.exception("do_DELETE error")
            json_response(self, 500, {'success': False, 'message': str(e)})

    # ---------- Handlers ----------
    def handle_test_connection(self):
        """Test connection to UAF LMS"""
        try:
            session = create_session_with_retry()
            message = "UAF LMS is not responding"
            success = False

            try:
                resp = session.get(LOGIN_URL, timeout=10, verify=False)
                if resp.status_code == 200:
                    success = True
                    message = f"Connection to UAF LMS successful (Status: {resp.status_code})"
                else:
                    message = f"UAF LMS returned status code: {resp.status_code}"
            except Exception as e:
                message = f"Connection failed: {str(e)}"

            json_response(self, 200, {'success': success, 'message': message})
        except Exception as e:
            logger.exception("handle_test_connection error")
            json_response(self, 500, {'success': False, 'message': str(e)})

    def handle_check_session(self):
        try:
            session_id = self.headers.get('Session-Id') or self.headers.get('session_id')
            if not session_id:
                json_response(self, 400, {'success': False, 'message': 'No session ID provided'})
                return
            data = load_from_session(session_id)
            if data:
                json_response(self, 200, {'success': True, 'hasData': True, 'recordCount': len(data), 'message': f'Session has {len(data)} records'})
            else:
                json_response(self, 200, {'success': True, 'hasData': False, 'recordCount': 0, 'message': 'Session has no data'})
        except Exception as e:
            logger.exception("handle_check_session error")
            json_response(self, 500, {'success': False, 'message': str(e)})

    def handle_clear_session(self):
        try:
            body = parse_json_body(self)
            session_id = body.get('sessionId')
            if not session_id:
                json_response(self, 400, {'success': False, 'message': 'No session ID provided'})
                return
            delete_session(session_id)
            json_response(self, 200, {'success': True, 'message': 'Session cleared successfully'})
        except Exception as e:
            logger.exception("handle_clear_session error")
            json_response(self, 500, {'success': False, 'message': str(e)})

    def handle_scrape_single_get(self, q):
        try:
            reg = q.get('registrationNumber') or q.get('registration_number')
            if not reg:
                json_response(self, 400, {'success': False, 'message': 'No registration number provided'})
                return
            success, message, data = scrape_uaf_results(unquote_plus(reg))
            json_response(self, 200, {'success': success, 'message': message, 'resultData': data})
        except Exception as e:
            logger.exception("handle_scrape_single_get error")
            json_response(self, 500, {'success': False, 'message': str(e)})

    def handle_scrape_single_post(self):
        try:
            body = parse_json_body(self)
            reg = body.get('registrationNumber') or body.get('registration_number')
            if not reg:
                json_response(self, 400, {'success': False, 'message': 'No registration number provided'})
                return
            success, message, data = scrape_uaf_results(reg)
            json_response(self, 200, {'success': success, 'message': message, 'resultData': data})
        except Exception as e:
            logger.exception("handle_scrape_single_post error")
            json_response(self, 500, {'success': False, 'message': str(e)})

    def handle_scrape(self):
        try:
            body = parse_json_body(self)
            registration_number = body.get('registrationNumber') or body.get('registration_number')
            session_id = body.get('sessionId') or body.get('session_id')

            if not registration_number:
                json_response(self, 400, {'success': False, 'message': 'No registration number provided'})
                return
            if not session_id:
                json_response(self, 400, {'success': False, 'message': 'No session ID provided'})
                return

            success, message, result_data = scrape_uaf_results(registration_number)
            if success and result_data:
                save_to_session(session_id, result_data)

            json_response(self, 200, {'success': success, 'message': message, 'resultData': result_data})
        except Exception as e:
            logger.exception("handle_scrape error")
            json_response(self, 500, {'success': False, 'message': str(e)})

    def handle_save_result(self):
        try:
            body = parse_json_body(self)
            registration_number = body.get('registrationNumber') or body.get('registration_number')
            student_data = body.get('studentData') or body.get('student_data')
            timestamp = body.get('timestamp') or datetime.now().isoformat()

            if not registration_number or not student_data:
                json_response(self, 400, {'success': False, 'message': 'Missing required fields'})
                return

            init_db()
            ok, result = save_result_to_db(registration_number, student_data, timestamp)
            if ok:
                json_response(self, 200, {'success': True, 'message': 'Result saved successfully', 'id': result})
            else:
                json_response(self, 500, {'success': False, 'message': f"DB error: {result}"})
        except Exception as e:
            logger.exception("handle_save_result error")
            json_response(self, 500, {'success': False, 'message': str(e)})

    def handle_load_result(self, q=None):
        try:
            if q is None:
                q = parse_query_params(self.path)
            reg = q.get('registrationNumber') or q.get('registration_number') or None
            if not reg:
                json_response(self, 400, {'success': False, 'message': 'No registration number provided'})
                return
            init_db()
            ok, results = load_saved_results_from_db(reg)
            if ok:
                json_response(self, 200, {'success': True, 'message': 'Results loaded successfully', 'savedResults': results})
            else:
                json_response(self, 500, {'success': False, 'message': 'Error loading results', 'error': results})
        except Exception as e:
            logger.exception("handle_load_result error")
            json_response(self, 500, {'success': False, 'message': str(e)})

    def handle_delete_saved_result(self):
        try:
            body = parse_json_body(self)
            result_id = body.get('id')
            if not result_id:
                json_response(self, 400, {'success': False, 'message': 'No result ID provided'})
                return
            ok, err = delete_saved_result_from_db(result_id)
            if ok:
                json_response(self, 200, {'success': True, 'message': 'Result deleted successfully'})
            else:
                json_response(self, 500, {'success': False, 'message': f"DB error: {err}"})
        except Exception as e:
            logger.exception("handle_delete_saved_result error")
            json_response(self, 500, {'success': False, 'message': str(e)})

    def handle_savefile_excel(self):
        """
        Export session data to an Excel file and return as attachment.
        Expects JSON with: sessionId and optional filename.
        """
        try:
            body = parse_json_body(self)
            session_id = body.get('sessionId') or body.get('session_id')
            filename = body.get('filename', 'student_results')

            if not session_id:
                json_response(self, 400, {'success': False, 'message': 'No session ID provided'})
                return

            session_results = load_from_session(session_id)
            if not session_results:
                json_response(self, 400, {'success': False, 'message': 'No results to save'})
                return

            wb = Workbook()
            ws = wb.active
            ws.title = "Results"

            # Flatten keys across all records to build headers
            headers = set()
            for rec in session_results:
                headers.update(rec.keys())
            headers = sorted(headers)

            ws.append(headers)
            for rec in session_results:
                row = [rec.get(h, '') for h in headers]
                ws.append(row)

            output = BytesIO()
            wb.save(output)
            excel_data = output.getvalue()

            self.send_response(200)
            self._set_cors_headers()
            self.send_header('Content-Type', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            self.send_header('Content-Disposition', f'attachment; filename="{filename}.xlsx"')
            self.send_header('Content-Length', str(len(excel_data)))
            self.end_headers()
            self.wfile.write(excel_data)
        except Exception as e:
            logger.exception("handle_savefile_excel error")
            json_response(self, 500, {'success': False, 'message': str(e)})

# ------------------ MAIN ------------------
def run_server(host=HOST, port=PORT):
    init_db()
    server = HTTPServer((host, port), handler)
    logger.info(f"UAFTools server running on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down server")
        server.server_close()

if __name__ == "__main__":
    run_server()
