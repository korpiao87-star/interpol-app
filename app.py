import streamlit as st
import json  # 이 줄을 추가해야 합니다!
from google.oauth2 import service_account
from googleapiclient.discovery import build

# Secrets에 저장된 텍스트 블록을 파이썬이 이해할 수 있게(JSON) 변환해서 읽기
key_dict = json.loads(st.secrets["gcp_service_account"])
creds = service_account.Credentials.from_service_account_info(key_dict)

# 구글 드라이브 연결
service = build('drive', 'v3', credentials=creds)

# --- (이 아래로는 기존에 작업하시던 파일 읽어오기 코드 등을 그대로 쓰시면 됩니다) ---
import sqlite3
import pandas as pd
import os
import base64
import io
import html
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta
from pathlib import Path

# --- 0. 경로 설정 ---
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
DB_PATH = BASE_DIR / "users.db"
IMAGE_PATH = BASE_DIR / "blue_tiger.png"
NAV_IMAGE_PATH = BASE_DIR / "navibar.png"

UPLOAD_DIR.mkdir(exist_ok=True)

# --- 1. 기본 설정 ---
APP_TITLE = "서울경찰청 인터폴팀"
ADMIN_USERNAME = "admin"
INITIAL_ADMIN_PASSWORD = os.getenv("APP_ADMIN_PASSWORD", "1234") # 기본 초기 비밀번호
PASSWORD_SCHEME = "pbkdf2_sha256"
PBKDF2_ITERATIONS = 200_000
SESSION_TIMEOUT_MINUTES = 30
ALLOWED_FILE_TYPES = ['hwp', 'hwpx', 'pdf', 'docx', 'jpg', 'png', 'jpeg']

st.set_page_config(page_title=APP_TITLE, page_icon="🕵️", layout="wide")

# --- 2. 유틸 함수 ---
def get_base64_of_bin_file(bin_file: str) -> str:
    with open(bin_file, 'rb') as f:
        return base64.b64encode(f.read()).decode()

def escape_text(value) -> str:
    return html.escape(str(value if value is not None else ""))

def escape_text_with_br(value) -> str:
    return escape_text(value).replace("\n", "<br>")

def now_dt() -> datetime:
    return datetime.now()

def now_str() -> str:
    return now_dt().strftime("%Y-%m-%d %H:%M:%S")

def is_hashed_password(value: str) -> bool:
    return isinstance(value, str) and value.startswith(f"{PASSWORD_SCHEME}$")

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    derived = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return f"{PASSWORD_SCHEME}${PBKDF2_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(derived).decode()}"

def verify_password(password: str, stored_value: str) -> bool:
    if not stored_value:
        return False
    if is_hashed_password(stored_value):
        try:
            _, iter_str, salt_b64, hash_b64 = stored_value.split("$", 3)
            salt = base64.b64decode(salt_b64.encode())
            expected = base64.b64decode(hash_b64.encode())
            candidate = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, int(iter_str))
            return hmac.compare_digest(candidate, expected)
        except Exception:
            return False
    # 구버전 평문 비밀번호 호환
    return hmac.compare_digest(password, stored_value)

def make_storage_name(original_name: str) -> str:
    safe_name = Path(original_name).name
    suffix = Path(safe_name).suffix.lower()
    return f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{secrets.token_hex(8)}{suffix}"

def generate_temp_password(length: int = 12) -> str:
    alphabet = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789!@#$%"
    return "".join(secrets.choice(alphabet) for _ in range(length))

def is_admin() -> bool:
    return st.session_state.get("user_id") == ADMIN_USERNAME

# --- 3. 세션 및 초기화 관리 ---
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "user_id" not in st.session_state:
    st.session_state["user_id"] = ""
if "user_name" not in st.session_state:
    st.session_state["user_name"] = ""
if "nav_menu" not in st.session_state:
    st.session_state["nav_menu"] = "로그인"

def clear_auth_state():
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = ""
    st.session_state["user_name"] = ""
    st.session_state["nav_menu"] = "로그인"
    st.session_state.pop("last_activity", None)

def refresh_last_activity():
    st.session_state["last_activity"] = now_dt().isoformat()

# 타임아웃 검사
if st.session_state.get("logged_in"):
    last_activity_raw = st.session_state.get("last_activity")
    last_activity = None
    if last_activity_raw:
        try:
            last_activity = datetime.fromisoformat(last_activity_raw)
        except Exception:
            pass

    if last_activity and now_dt() - last_activity > timedelta(minutes=SESSION_TIMEOUT_MINUTES):
        clear_auth_state()
        st.session_state["timeout_notice"] = f"{SESSION_TIMEOUT_MINUTES}분 동안 활동이 없어 자동 로그아웃되었습니다."
        st.rerun()
    else:
        refresh_last_activity()

choice = st.session_state.nav_menu

# --- 4. DB 연결 / 마이그레이션 ---
conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
conn.row_factory = sqlite3.Row
c = conn.cursor()

def column_exists(table_name: str, column_name: str) -> bool:
    c.execute(f"PRAGMA table_info({table_name})")
    return any(row["name"] == column_name for row in c.fetchall())

c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, name TEXT, department TEXT, status TEXT)')
c.execute('''CREATE TABLE IF NOT EXISTS org_chart_v2
             (id INTEGER PRIMARY KEY AUTOINCREMENT, country TEXT, affiliation TEXT, name TEXT,
             contact TEXT, category TEXT, purpose TEXT, position TEXT, manager TEXT)''')
c.execute('CREATE TABLE IF NOT EXISTS country_info (country_name TEXT PRIMARY KEY, features TEXT, treaty TEXT, contacts TEXT, tips TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS file_archive (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, filepath TEXT, upload_date TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS qna (id INTEGER PRIMARY KEY AUTOINCREMENT, author TEXT, question TEXT, date TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS qna_comments (id INTEGER PRIMARY KEY AUTOINCREMENT, qna_id INTEGER, author TEXT, comment TEXT, date TEXT, comment_type TEXT DEFAULT "comment")')
c.execute('CREATE TABLE IF NOT EXISTS audit_log (id INTEGER PRIMARY KEY AUTOINCREMENT, username TEXT, action TEXT, detail TEXT, created_at TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS app_config (config_key TEXT PRIMARY KEY, config_value TEXT)')

if not column_exists("file_archive", "uploader"):
    c.execute("ALTER TABLE file_archive ADD COLUMN uploader TEXT")
if not column_exists("users", "role"):
    c.execute("ALTER TABLE users ADD COLUMN role TEXT DEFAULT 'user'")
    c.execute("UPDATE users SET role='admin' WHERE username=?", (ADMIN_USERNAME,))

try:
    c.execute("SELECT id, filename, filepath, uploader FROM file_archive")
    for row in c.fetchall():
        if not row["filepath"]:
            c.execute("UPDATE file_archive SET filepath=? WHERE id=?", (row["filename"], row["id"]))
        if row["uploader"] is None:
            c.execute("UPDATE file_archive SET uploader=? WHERE id=?", ("알 수 없음", row["id"]))
except Exception:
    pass

c.execute("SELECT config_value FROM app_config WHERE config_key='admin_password_hash'")
if not c.fetchone():
    c.execute("INSERT OR REPLACE INTO app_config (config_key, config_value) VALUES (?, ?)", ("admin_password_hash", hash_password(INITIAL_ADMIN_PASSWORD)))
conn.commit()

# --- 5. 설정 / 로그 함수 ---
def get_config(key: str, default: str = "") -> str:
    c.execute("SELECT config_value FROM app_config WHERE config_key=?", (key,))
    row = c.fetchone()
    return row["config_value"] if row else default

def set_config(key: str, value: str):
    c.execute("INSERT OR REPLACE INTO app_config (config_key, config_value) VALUES (?, ?)", (key, value))
    conn.commit()

def log_event(username: str, action: str, detail: str = ""):
    try:
        c.execute("INSERT INTO audit_log (username, action, detail, created_at) VALUES (?, ?, ?, ?)",
                  ((username or "알 수 없음")[:100], action[:100], detail[:500], now_str()))
        conn.commit()
    except Exception:
        pass

def build_like_pattern(text: str) -> str:
    return f"%{text.strip()}%"

def fetch_distinct_values(table_name: str, column_name: str):
    c.execute(f"SELECT DISTINCT {column_name} AS value FROM {table_name} WHERE {column_name} IS NOT NULL AND TRIM({column_name}) <> '' ORDER BY {column_name} ASC")
    return [row["value"] for row in c.fetchall()]

def get_file_ext(filename: str) -> str:
    return Path(filename).suffix.lower().replace(".", "")

def get_file_kind(filename: str) -> str:
    ext = get_file_ext(filename)
    if ext in {"jpg", "jpeg", "png", "gif", "bmp", "webp"}: return "이미지"
    if ext == "pdf": return "PDF"
    return "문서"

def format_file_size(num_bytes: int) -> str:
    if num_bytes < 1024: return f"{num_bytes} B"
    if num_bytes < 1024 * 1024: return f"{num_bytes / 1024:.1f} KB"
    return f"{num_bytes / (1024 * 1024):.1f} MB"

def get_qna_status_class(status_text: str) -> str:
    return "status-done" if status_text == "답변완료" else "status-open"


# --- 6. 로그아웃 처리 ---
if choice == "로그아웃":
    if st.session_state.get("logged_in"):
        log_event(st.session_state.get("user_id", "미상"), "로그아웃", "사용자 로그아웃")
    clear_auth_state()
    st.rerun()

# --- 7. 로그인 전 화면 ---
elif not st.session_state.get("logged_in"):
    
    if IMAGE_PATH.exists():
        img_base64 = get_base64_of_bin_file(str(IMAGE_PATH))
        st.markdown(f'<style>.stApp {{ background-image: linear-gradient(rgba(255,255,255,0.40), rgba(255,255,255,0.40)), url("data:image/png;base64,{img_base64}"); background-size: cover; background-repeat: no-repeat; background-attachment: fixed; background-position: center; }}</style>', unsafe_allow_html=True)
    
    st.markdown("""
    <style>
        .stButton>button, .stFormSubmitButton>button { background-color: #00529B; color: white; border-radius: 10px; font-weight: bold; }
        .glass-box { background-color: rgba(255, 255, 255, 0.88); padding: 20px; border-radius: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.15); margin-bottom: 20px; color: #222; }
        .glass-box h4 { color: #002D56; border-bottom: 2px solid #00529B; padding-bottom: 8px; }
    </style>
    """, unsafe_allow_html=True)

    timeout_notice = st.session_state.pop("timeout_notice", None)
    if timeout_notice:
        st.warning(timeout_notice)

    if choice == "회원가입":
        st.markdown('<div class="glass-box"><h2 style="margin:0;">📝 계정 신청</h2></div>', unsafe_allow_html=True)
        with st.form("signup"):
            new_id = st.text_input("아이디")
            new_name = st.text_input("성명")
            new_pw = st.text_input("비밀번호", type='password')
            new_pw_confirm = st.text_input("비밀번호 재확인", type='password')

            if st.form_submit_button("신청하기", use_container_width=True):
                new_id = new_id.strip()
                new_name = new_name.strip()
                if not new_id or not new_name or not new_pw.strip():
                    st.error("아이디, 성명, 비밀번호를 모두 입력해주세요.")
                elif new_pw != new_pw_confirm:
                    st.error("비밀번호가 일치하지 않습니다. 다시 확인해주세요.")
                elif len(new_pw) < 8:
                    st.error("비밀번호는 최소 8자 이상으로 설정해주세요.")
                elif new_id.lower() == ADMIN_USERNAME:
                    st.error("사용할 수 없는 아이디입니다.")
                else:
                    try:
                        c.execute('INSERT INTO users (username, password, name, department, status, role) VALUES (?,?,?,?,?,?)',
                                  (new_id, hash_password(new_pw), new_name, "인터폴", "pending", "user"))
                        conn.commit()
                        log_event(new_id, "회원가입 신청", f"신청자: {new_name}")
                        st.success("신청 완료! 관리자 승인을 기다려주세요.")
                    except sqlite3.IntegrityError:
                        st.error("이미 존재하는 아이디입니다.")

        if st.button("로그인 화면으로 돌아가기", use_container_width=True):
            st.session_state.nav_menu = "로그인"
            st.rerun()

    else:
        st.markdown("<div style='text-align: center; margin-bottom: 20px;'><h2 style='color: #002D56; font-weight: 900;'>인터폴팀<br>업무 지원 시스템</h2></div>", unsafe_allow_html=True)
        _, col2, _ = st.columns([1, 2, 1])
        with col2:
            with st.form("login_form"):
                user_id = st.text_input("아이디")
                user_pw = st.text_input("비밀번호", type='password')
                submit_btn = st.form_submit_button("로그인", use_container_width=True)

                if submit_btn:
                    user_id = user_id.strip()
                    user_pw = user_pw.strip()

                    if user_id == ADMIN_USERNAME:
                        admin_hash = get_config("admin_password_hash", hash_password(INITIAL_ADMIN_PASSWORD))
                        if verify_password(user_pw, admin_hash):
                            st.session_state["logged_in"], st.session_state["user_name"], st.session_state["user_id"] = True, "관리자", ADMIN_USERNAME
                            refresh_last_activity()
                            log_event(ADMIN_USERNAME, "로그인 성공", "관리자 로그인")
                            st.session_state.nav_menu = "홈"
                            st.rerun()
                        else:
                            st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
                    else:
                        c.execute('SELECT username, password, name, status FROM users WHERE username=?', (user_id,))
                        data = c.fetchone()
                        if not data:
                            st.error("아이디 또는 비밀번호가 올바르지 않습니다.")
                        elif data["status"] != "approved":
                            st.error("승인 대기 중이거나 접근 권한이 없습니다.")
                        elif verify_password(user_pw, data["password"]):
                            if not is_hashed_password(data["password"]):
                                c.execute('UPDATE users SET password=? WHERE username=?', (hash_password(user_pw), user_id))
                                conn.commit()
                            st.session_state["logged_in"], st.session_state["user_name"], st.session_state["user_id"] = True, data["name"], data["username"]
                            refresh_last_activity()
                            log_event(user_id, "로그인 성공", "일반 사용자 로그인")
                            st.session_state.nav_menu = "홈"
                            st.rerun()
                        else:
                            st.error("아이디 또는 비밀번호가 올바르지 않습니다.")

            if st.button("회원가입", use_container_width=True):
                st.session_state.nav_menu = "회원가입"
                st.rerun()

# --- 8. 로그인 후 메인 화면 ---
else:
    # 🌟 사이드바 네비게이션 메뉴 🌟
    with st.sidebar:
        st.markdown(f"### 🕵️ 인터폴팀 시스템\n**{escape_text(st.session_state['user_name'])}** 수사관님")
        st.divider()
        if st.button("🏠 홈", use_container_width=True): st.session_state.nav_menu = "홈"; st.rerun()
        if st.button("📊 연락망", use_container_width=True): st.session_state.nav_menu = "연락망"; st.rerun()
        if st.button("🌍 국가별 공조 특징", use_container_width=True): st.session_state.nav_menu = "국가별지원"; st.rerun()
        if st.button("📁 팀 공용 자료실", use_container_width=True): st.session_state.nav_menu = "자료실"; st.rerun()
        if st.button("🧠 지식 네트워크 (Obsidian)", use_container_width=True): st.session_state.nav_menu = "지식네트워크"; st.rerun()
        
        if is_admin():
            st.divider()
            if st.button("⚙️ 데이터 관리", use_container_width=True): st.session_state.nav_menu = "데이터 관리"; st.rerun()
            
        st.divider()
        if st.button("⚙️ 개인설정", use_container_width=True): st.session_state.nav_menu = "설정"; st.rerun()
        if st.button("🚪 로그아웃", use_container_width=True): st.session_state.nav_menu = "로그아웃"; st.rerun()


    # 메인 화면 CSS 및 배경
    if IMAGE_PATH.exists():
        img_base64 = get_base64_of_bin_file(str(IMAGE_PATH))
        st.markdown(f'<style>.stApp {{ background-image: linear-gradient(rgba(255,255,255,0.40), rgba(255,255,255,0.40)), url("data:image/png;base64,{img_base64}"); background-size: cover; background-repeat: no-repeat; background-attachment: fixed; background-position: center; }}</style>', unsafe_allow_html=True)

    st.markdown(f"""
    <style>
        .stButton>button, .stFormSubmitButton>button {{ background-color: #00529B; color: white; border-radius: 10px; font-weight: bold; }}
        .glass-box {{ background-color: rgba(255, 255, 255, 0.88); padding: 20px; border-radius: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.15); margin-bottom: 20px; color: #222; }}
        .glass-box h4 {{ color: #002D56; border-bottom: 2px solid #00529B; padding-bottom: 8px; }}
        
        .contact-card, .file-card, .comment-card {{ background: rgba(255,255,255,0.92); border: 1px solid rgba(0,45,86,0.10); border-radius: 14px; padding: 14px 16px; margin-bottom: 12px; }}
        .answer-card {{ background: rgba(232,244,255,0.96); border: 1px solid rgba(0,82,155,0.25); border-radius: 14px; padding: 14px 16px; margin-bottom: 12px; }}
        .contact-meta, .file-meta, .comment-meta {{ color: #55616F; font-size: 0.9rem; margin-bottom: 6px; }}
        .question-wrap {{ background-color: rgba(255,255,255,0.90); border-radius: 16px; border: 1px solid rgba(0,45,86,0.10); padding: 16px; margin-bottom: 18px; }}
        .status-pill {{ display: inline-block; padding: 4px 10px; border-radius: 999px; font-size: 0.82rem; font-weight: 700; margin-left: 8px; }}
        .status-open {{ background: rgba(255, 193, 7, 0.16); color: #8A5A00; border: 1px solid rgba(255, 193, 7, 0.35); }}
        .status-done {{ background: rgba(40, 167, 69, 0.14); color: #1D6A33; border: 1px solid rgba(40, 167, 69, 0.28); }}
        .preview-wrap {{ background: rgba(255,255,255,0.96); border: 1px solid rgba(0,45,86,0.10); border-radius: 14px; padding: 12px; margin-top: 10px; margin-bottom: 8px; }}
    </style>
    """, unsafe_allow_html=True)

    # 🌟 1) 홈 화면
    if choice == "홈":
        st.markdown(f'<div class="glass-box"><h2>👋 환영합니다, {escape_text(st.session_state["user_name"])} 수사관님!</h2><p>좌측 사이드바 메뉴를 선택하여 이동하세요.</p></div>', unsafe_allow_html=True)

        stat1, stat2, stat3, stat4 = st.columns(4)
        c.execute("SELECT COUNT(*) AS cnt FROM org_chart_v2")
        stat1.metric("연락망", c.fetchone()["cnt"])
        c.execute("SELECT COUNT(*) AS cnt FROM country_info")
        stat2.metric("국가정보", c.fetchone()["cnt"])
        c.execute("SELECT COUNT(*) AS cnt FROM file_archive")
        stat3.metric("자료실", c.fetchone()["cnt"])
        stat4.metric("지식망", "연결됨")

        col1, col2 = st.columns(2)
        if col1.button("📊 연락망", use_container_width=True, key="h1"):
            st.session_state.nav_menu = "연락망"
            st.rerun()
        if col2.button("🌍 국가별 공조 특징", use_container_width=True, key="h2"):
            st.session_state.nav_menu = "국가별지원"
            st.rerun()

        col3, col4 = st.columns(2)
        if col3.button("📁 공조 자료실", use_container_width=True, key="h3"):
            st.session_state.nav_menu = "자료실"
            st.rerun()
        if col4.button("🧠 지식 네트워크", use_container_width=True, key="h4"):
            st.session_state.nav_menu = "지식네트워크"
            st.rerun()

    # 🌟 2) 설정 화면 (개인정보 수정)
    elif choice == "설정":
        st.markdown('<div class="glass-box"><h2>⚙️ 개인정보 설정</h2><p>이름과 비밀번호를 수정할 수 있습니다.</p></div>', unsafe_allow_html=True)

        if is_admin():
            with st.form("admin_settings_form"):
                current_pw = st.text_input("현재 관리자 비밀번호", type="password")
                new_pw = st.text_input("새 관리자 비밀번호", type="password")
                new_pw_confirm = st.text_input("새 관리자 비밀번호 확인", type="password")
                if st.form_submit_button("관리자 비밀번호 변경", use_container_width=True):
                    admin_hash = get_config("admin_password_hash", hash_password(INITIAL_ADMIN_PASSWORD))
                    if not verify_password(current_pw, admin_hash):
                        st.error("현재 비밀번호가 올바르지 않습니다.")
                    elif len(new_pw.strip()) < 8:
                        st.error("새 비밀번호는 최소 8자 이상이어야 합니다.")
                    elif new_pw != new_pw_confirm:
                        st.error("새 비밀번호가 일치하지 않습니다.")
                    else:
                        set_config("admin_password_hash", hash_password(new_pw.strip()))
                        log_event(st.session_state["user_id"], "관리자 비밀번호 변경", "설정 화면에서 변경")
                        st.success("관리자 비밀번호가 변경되었습니다.")
        else:
            c.execute('SELECT name, password FROM users WHERE username=?', (st.session_state["user_id"],))
            user_info = c.fetchone()
            if user_info:
                with st.form("settings_form"):
                    edit_name = st.text_input("성명 (이름)", value=user_info["name"])
                    old_pw = st.text_input("현재 비밀번호", type="password")
                    st.markdown("<small>비밀번호를 바꾸지 않으려면 새 비밀번호 칸을 비워두세요.</small>", unsafe_allow_html=True)
                    edit_pw = st.text_input("새로운 비밀번호", type="password")
                    edit_pw_confirm = st.text_input("새로운 비밀번호 확인", type="password")
                    if st.form_submit_button("정보 수정 저장", use_container_width=True):
                        if not verify_password(old_pw, user_info["password"]):
                            st.error("현재 비밀번호가 올바르지 않습니다.")
                        elif not edit_name.strip():
                            st.error("성명을 입력해주세요.")
                        elif edit_pw.strip() and len(edit_pw.strip()) < 8:
                            st.error("새 비밀번호는 최소 8자 이상이어야 합니다.")
                        elif edit_pw.strip() and edit_pw != edit_pw_confirm:
                            st.error("새로운 비밀번호가 일치하지 않습니다.")
                        else:
                            new_pw_hash = hash_password(edit_pw.strip()) if edit_pw.strip() else user_info["password"]
                            c.execute('UPDATE users SET name=?, password=? WHERE username=?', (edit_name.strip(), new_pw_hash, st.session_state["user_id"]))
                            conn.commit()
                            st.session_state["user_name"] = edit_name.strip()
                            log_event(st.session_state["user_id"], "개인정보 수정", "이름/비밀번호 변경")
                            st.success("개인정보가 성공적으로 수정되었습니다.")

    # 🌟 3) 연락망 화면
    elif choice == "연락망":
        st.markdown('<div class="glass-box"><h2>📊 연락망</h2></div>', unsafe_allow_html=True)

        # 복잡한 필터 제거 후 '통합 검색' 및 '검색' 버튼만 남김
        fcol1, fcol2 = st.columns([4, 1])
        with fcol1:
            search = st.text_input("통합 검색", placeholder="검색어를 입력하세요", key="contact_search", label_visibility="collapsed")
        with fcol2:
            st.button("검색", use_container_width=True)

        base_query = "SELECT id as 연번, country as 국가, affiliation as 소속, name as 성명, contact as 연락처, category as 구분, purpose as 관리목적, position as 직책, manager as 관리주체 FROM org_chart_v2"
        where_clauses, params = [], []

        if search.strip():
            like_v = build_like_pattern(search)
            where_clauses.append("(country LIKE ? OR name LIKE ? OR affiliation LIKE ? OR contact LIKE ? OR category LIKE ? OR purpose LIKE ? OR position LIKE ? OR manager LIKE ?)")
            params.extend([like_v] * 8)

        if where_clauses: base_query += " WHERE " + " AND ".join(where_clauses)
        base_query += " ORDER BY country ASC, affiliation ASC, name ASC"

        df = pd.read_sql_query(base_query, conn, params=params)
        
        # 메트릭스(검색 결과 수 등) 제거하고 바로 데이터프레임 표시
        st.dataframe(df, use_container_width=True, hide_index=True)

        if not df.empty:
            out = io.BytesIO()
            with pd.ExcelWriter(out, engine='openpyxl') as writer: df.to_excel(writer, index=False, sheet_name='연락망검색결과')
            st.download_button("📥 검색 결과 엑셀 다운로드", data=out.getvalue(), file_name=f"연락망_검색_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)
            
        if is_admin() and not df.empty:
            st.divider()
            contact_options = [f"{int(row['연번'])} | {row['국가']} | {row['성명']} | {row['소속']}" for _, row in df.iterrows()]
            selected_label = st.selectbox("🛠️ 수정/삭제할 항목 선택", contact_options)
            selected_id = int(selected_label.split("|")[0].strip())
            c.execute("SELECT * FROM org_chart_v2 WHERE id=?", (selected_id,))
            target = c.fetchone()
            if target:
                with st.form(f"edit_{selected_id}"):
                    col1, col2 = st.columns(2)
                    e1 = col1.text_input("국가", value=target["country"] or "")
                    e2 = col1.text_input("소속", value=target["affiliation"] or "")
                    e3 = col1.text_input("성명", value=target["name"] or "")
                    e4 = col1.text_input("연락처", value=target["contact"] or "")
                    e5 = col2.text_input("구분", value=target["category"] or "")
                    e6 = col2.text_input("관리목적", value=target["purpose"] or "")
                    e7 = col2.text_input("직책", value=target["position"] or "")
                    e8 = col2.text_input("관리주체", value=target["manager"] or "")
                    if st.form_submit_button("수정 저장", use_container_width=True):
                        c.execute("UPDATE org_chart_v2 SET country=?, affiliation=?, name=?, contact=?, category=?, purpose=?, position=?, manager=? WHERE id=?", (e1, e2, e3, e4, e5, e6, e7, e8, selected_id))
                        conn.commit()
                        st.success("수정되었습니다.")
                        st.rerun()

                if st.button("🗑️ 선택한 연락망 삭제", use_container_width=True):
                    c.execute("DELETE FROM org_chart_v2 WHERE id=?", (selected_id,))
                    conn.commit()
                    st.success("삭제되었습니다.")
                    st.rerun()

    # 🌟 4) 국가별 공조 특징
    elif choice == "국가별지원":
        st.markdown('<div class="glass-box"><h2>🌍 국가별 공조 특징</h2></div>', unsafe_allow_html=True)
        c.execute("SELECT country_name FROM country_info ORDER BY country_name ASC")
        countries = [r[0] for r in c.fetchall()]
        if countries:
            sel = st.selectbox("국가 선택", countries)
            c.execute("SELECT * FROM country_info WHERE country_name=?", (sel,))
            info = c.fetchone()
            if info:
                for title, content in [("📌 공조 특징", info["features"]), ("📞 연락·문의처", info["contacts"]), ("💡 공조 팁", info["tips"])]:
                    st.markdown(f'<div class="glass-box"><h4>{title}</h4>{escape_text_with_br(content)}</div>', unsafe_allow_html=True)
        else:
            st.info("등록된 국가 정보가 없습니다.")

    # 🌟 5) 자료실
    elif choice == "자료실":
        st.markdown('<div class="glass-box"><h2>📁 팀 공용 자료실</h2></div>', unsafe_allow_html=True)

        with st.expander("파일 업로드"):
            up_file = st.file_uploader("파일 선택", type=ALLOWED_FILE_TYPES)
            if st.button("저장") and up_file:
                original_name = Path(up_file.name).name
                if Path(original_name).suffix.lower().replace(".", "") in ALLOWED_FILE_TYPES:
                    storage_name = make_storage_name(original_name)
                    with open(UPLOAD_DIR / storage_name, "wb") as f: f.write(up_file.getbuffer())
                    c.execute("INSERT INTO file_archive (filename, filepath, upload_date, uploader) VALUES (?,?,?,?)", (original_name, storage_name, datetime.now().strftime("%Y-%m-%d %H:%M"), st.session_state["user_name"]))
                    conn.commit()
                    st.success("저장되었습니다.")
                    st.rerun()
                else: st.error("허용되지 않은 형식입니다.")

        c.execute("SELECT * FROM file_archive ORDER BY id DESC")
        files = c.fetchall()
        for row in files:
            full_path = UPLOAD_DIR / (row["filepath"] or row["filename"])
            st.markdown(f"""
            <div class="file-card">
                <div style="font-weight:700;">📄 {escape_text(row['filename'])}</div>
                <div class="file-meta">업로드: {escape_text(row['upload_date'])} | 업로더: {escape_text(row['uploader'])}</div>
            </div>
            """, unsafe_allow_html=True)
            
            a1, a2, a3 = st.columns([1.1, 1.1, 1])
            with a1:
                if full_path.exists():
                    with open(full_path, "rb") as f: st.download_button("⬇️ 다운로드", f, file_name=row["filename"], key=f"dl_{row['id']}", use_container_width=True)
                else: st.error("서버에 파일이 없습니다.")
            with a2:
                if get_file_kind(row["filename"]) in {"이미지", "PDF"} and full_path.exists():
                    if st.toggle("미리보기", key=f"pv_{row['id']}"):
                        ext = get_file_ext(row["filename"])
                        if ext in {"jpg", "jpeg", "png", "gif", "bmp", "webp"}: st.image(str(full_path))
                        elif ext == "pdf": st.markdown(f'<iframe src="data:application/pdf;base64,{base64.b64encode(full_path.read_bytes()).decode("utf-8")}" width="100%" height="720"></iframe>', unsafe_allow_html=True)
            with a3:
                if is_admin():
                    if st.button("🗑️ 삭제", key=f"del_{row['id']}", use_container_width=True):
                        if full_path.exists(): full_path.unlink(missing_ok=True)
                        c.execute("DELETE FROM file_archive WHERE id=?", (row["id"],))
                        conn.commit()
                        st.rerun()

    # 🌟 6) 지식 네트워크 (Obsidian 이식)
    elif choice == "지식네트워크":
        st.markdown('<div class="glass-box"><h2>🧠 지식 네트워크 (Obsidian)</h2><p>사건 분석, 지식 연결, 복잡한 데이터 정리는 옵시디언을 활용합니다.</p></div>', unsafe_allow_html=True)
        
        st.info("💡 모바일에서 이용 시 옵시디언(Obsidian) 앱이 설치되어 있어야 하며, 공유 폴더가 동기화된 상태여야 합니다.")
        
        # 딥링크 버튼
        obsidian_url = "obsidian://open?vault=Interpol_Vault"
        st.markdown(f"""
            <a href="{obsidian_url}" target="_blank" style="text-decoration: none;">
                <div style="background-color: #7b61ff; color: white; text-align: center; padding: 25px; border-radius: 15px; font-size: 20px; font-weight: bold; box-shadow: 0 4px 15px rgba(123,97,255,0.4);">
                    🟣 옵시디언 앱 실행 및 지식망 연결
                </div>
            </a>
            """, unsafe_allow_html=True)
        
        st.markdown("<br>", unsafe_allow_html=True)
        with st.expander("❓ 이용 가이드"):
            st.write("1. **처음 사용:** 휴대폰 앱스토어에서 Obsidian 앱을 먼저 설치하세요.")
            st.write("2. **폴더 동기화:** Remotely Save 또는 Obsidian Sync를 통해 'Interpol_Vault' 폴더를 동기화하세요.")
            st.write("3. **연결성:** 문서 본문에 `[[문서제목]]`을 입력하여 사건과 인물을 연결하세요.")

    # 🌟 7) 데이터 관리 (관리자)
    elif choice == "데이터 관리":
        if not is_admin():
            st.error("관리자만 접근할 수 있습니다.")
            st.stop()
            
        tab1, tab2, tab3, tab4 = st.tabs(["👤 연락망", "🌍 국가정보", "👥 사용자", "🕘 로그"])

        with tab1:
            st.subheader("📥 엑셀 내보내기/업로드")
            c.execute("SELECT country, affiliation, name, contact, category, purpose, position, manager FROM org_chart_v2")
            all_data = c.fetchall()
            if all_data:
                df_download = pd.DataFrame(all_data, columns=['국가', '소속', '성명', '연락처', '구분', '관리목적', '직책', '관리주체'])
                df_download.insert(0, '연번', range(1, len(df_download) + 1))
                out = io.BytesIO()
                with pd.ExcelWriter(out, engine='openpyxl') as writer: df_download.to_excel(writer, index=False, sheet_name='연락망')
                st.download_button("📥 엑셀 다운로드", data=out.getvalue(), file_name=f"연락망_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
            
            upload_option = st.radio("업로드 방식:", ["🚨 전체 덮어쓰기 (기존 삭제)", "➕ 기존 데이터에 추가"])
            uploaded_file = st.file_uploader("엑셀 파일 선택", type=['xlsx'])
            if uploaded_file and st.button("적용하기", use_container_width=True):
                df_ex = pd.read_excel(uploaded_file).fillna("")
                if "덮어쓰기" in upload_option: c.execute('DELETE FROM org_chart_v2')
                for _, row in df_ex.iterrows(): c.execute('INSERT INTO org_chart_v2 (country, affiliation, name, contact, category, purpose, position, manager) VALUES (?,?,?,?,?,?,?,?)', (str(row.iloc[1]), str(row.iloc[2]), str(row.iloc[3]), str(row.iloc[4]), str(row.iloc[5]), str(row.iloc[6]), str(row.iloc[7]), str(row.iloc[8])))
                conn.commit(); st.success("반영 완료!"); st.rerun()

        with tab2:
            c.execute("SELECT country_name FROM country_info ORDER BY country_name ASC")
            edit_choice = st.selectbox("국가 선택", ["--- 신규 추가 ---"] + [r["country_name"] for r in c.fetchall()])
            target = {"country_name": "", "features": "", "contacts": "", "tips": ""}
            if edit_choice != "--- 신규 추가 ---":
                c.execute("SELECT * FROM country_info WHERE country_name = ?", (edit_choice,))
                target = c.fetchone()
            with st.form("country_form"):
                cn = st.text_input("국가명", value=target["country_name"])
                cf = st.text_area("공조 특징", value=target["features"])
                cc = st.text_area("연락처", value=target["contacts"])
                cp = st.text_area("팁", value=target["tips"])
                if st.form_submit_button("저장") and cn.strip():
                    c.execute('INSERT OR REPLACE INTO country_info VALUES (?,?,?,?,?)', (cn.strip(), cf, "", cc, cp))
                    conn.commit(); st.success("저장되었습니다."); st.rerun()

        with tab3:
            c.execute('SELECT username, name, department, status, role FROM users WHERE username != ? ORDER BY username ASC', (ADMIN_USERNAME,))
            for row in c.fetchall():
                u_id = row["username"]
                with st.expander(f"{escape_text(row['name'])} ({escape_text(u_id)}) [{escape_text(row['status'])}]"):
                    col1, col2 = st.columns(2)
                    if row["status"] == "pending" and col1.button("승인", key=f"a_{u_id}"): c.execute('UPDATE users SET status="approved" WHERE username=?', (u_id,)); conn.commit(); st.rerun()
                    elif row["status"] == "approved" and col1.button("승인회수", key=f"r_{u_id}"): c.execute('UPDATE users SET status="pending" WHERE username=?', (u_id,)); conn.commit(); st.rerun()
                    if col2.button("삭제", key=f"d_{u_id}"): c.execute('DELETE FROM users WHERE username=?', (u_id,)); conn.commit(); st.rerun()

        with tab4:
            st.subheader("🕘 최근 접속 및 주요 작업 로그")
            c.execute("SELECT created_at as 시각, username as 사용자, action as 동작, detail as 상세 FROM audit_log ORDER BY id DESC LIMIT 300")
            log_rows = c.fetchall()
            if log_rows:
                df_logs = pd.DataFrame(log_rows, columns=["시각", "사용자", "동작", "상세"])
                st.dataframe(df_logs, use_container_width=True, hide_index=True)
                