import streamlit as st
import sqlite3
import pandas as pd
import os
import base64
from datetime import datetime
from pathlib import Path
import io

# --- 0. 경로 설정 ---
BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = BASE_DIR / "uploads"
DB_PATH = BASE_DIR / "users.db"
IMAGE_PATH = BASE_DIR / "blue_tiger.png"

if not UPLOAD_DIR.exists():
    os.makedirs(UPLOAD_DIR)

# --- 1. 기본 화면 설정 ---
st.set_page_config(page_title="서울경찰청 인터폴팀", page_icon="🕵️", layout="wide")

# --- 2. 배경 이미지 설정 ---
def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

if IMAGE_PATH.exists():
    img_base64 = get_base64_of_bin_file(str(IMAGE_PATH))
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: linear-gradient(rgba(255,255,255,0.4), rgba(255,255,255,0.4)), url("data:image/png;base64,{img_base64}");
            background-size: cover; background-repeat: no-repeat; background-attachment: fixed; background-position: center;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

# --- 3. 앱 디자인(CSS) ---
st.markdown("""
<style>
    [data-testid="stSidebar"] { background-color: #002D56; }
    [data-testid="stSidebar"] * { color: white !important; }
    .stButton>button, .stFormSubmitButton>button { background-color: #00529B; color: white; border-radius: 10px; font-weight: bold; }
    .glass-box { background-color: rgba(255, 255, 255, 0.85); padding: 20px; border-radius: 15px; box-shadow: 0 4px 10px rgba(0,0,0,0.15); margin-bottom: 20px; color: #222; }
    .glass-box h4 { color: #002D56; border-bottom: 2px solid #00529B; padding-bottom: 8px; }
</style>
""", unsafe_allow_html=True)

# --- 4. 데이터베이스 초기화 ---
conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, name TEXT, department TEXT, status TEXT)')
c.execute('''CREATE TABLE IF NOT EXISTS org_chart_v2 
             (id INTEGER PRIMARY KEY AUTOINCREMENT, country TEXT, affiliation TEXT, name TEXT, 
              contact TEXT, category TEXT, purpose TEXT, position TEXT, manager TEXT)''')
# DB 스키마 충돌 방지를 위해 테이블 구조(열 5개)는 그대로 유지합니다.
c.execute('CREATE TABLE IF NOT EXISTS country_info (country_name TEXT PRIMARY KEY, features TEXT, treaty TEXT, contacts TEXT, tips TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS file_archive (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, filepath TEXT, upload_date TEXT)')
conn.commit()

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = ""

# --- 5. 사이드바 메뉴 ---
menu = ["로그인", "회원가입"]
if st.session_state["logged_in"]:
    if st.session_state.get("user_id") == "admin":
        menu = ["📊 연락망 및 대시보드", "🌍 국가별 공조 특징", "📁 공조 자료실", "⚙️ 데이터 관리", "로그아웃"]
    else:
        menu = ["📊 연락망 및 대시보드", "🌍 국가별 공조 특징", "📁 공조 자료실", "로그아웃"]

# 🌟 [수정된 부분] 버튼 클릭 시 메뉴 이동을 연동하기 위해 세션 상태(nav_menu)를 관리합니다.
if "nav_menu" not in st.session_state or st.session_state.nav_menu not in menu:
    st.session_state.nav_menu = menu[0]

choice = st.sidebar.selectbox("메뉴 선택", menu, key="nav_menu")

# --- 6. 기능별 화면 구현 ---
if choice == "로그아웃":
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = ""
    st.rerun()

elif choice == "로그인":
    st.markdown("<div style='text-align: center; margin-bottom: 20px;'><h2 style='color: #002D56; font-weight: 900;'>🔒 인터폴팀<br>업무 지원 시스템</h2></div>", unsafe_allow_html=True)
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        with st.form("login_form"):
            user_id = st.text_input("아이디")
            user_pw = st.text_input("비밀번호", type='password')
            submit_btn = st.form_submit_button("로그인", use_container_width=True)
            
            if submit_btn:
                if user_id == "admin" and user_pw == "1234":
                    st.session_state["logged_in"], st.session_state["user_name"], st.session_state["user_id"] = True, "관리자", "admin"
                    st.rerun()
                else:
                    c.execute('SELECT * FROM users WHERE username=? AND password=? AND status="approved"', (user_id, user_pw))
                    data = c.fetchone()
                    if data:
                        st.session_state["logged_in"], st.session_state["user_name"], st.session_state["user_id"] = True, data[2], data[0]
                        st.rerun()
                    else: 
                        st.error("승인 대기 중이거나 정보가 틀립니다.")
        
        # 🌟 [추가된 부분] 폼 바로 아래에 중앙 정렬된 작은 '회원가입' 버튼 추가
        st.markdown("<div style='height: 5px;'></div>", unsafe_allow_html=True)
        _, btn_col, _ = st.columns([1, 1.2, 1]) # 버튼 크기를 작게 만들기 위해 좌우 여백 확보
        with btn_col:
            if st.button("회원가입", use_container_width=True):
                st.session_state.nav_menu = "회원가입" # 사이드바 메뉴를 '회원가입'으로 자동 변경
                st.rerun()

elif choice == "회원가입":
    st.markdown('<div class="glass-box"><h2 style="margin:0;">📝 계정 신청</h2></div>', unsafe_allow_html=True)
    with st.form("signup"):
        new_id, new_name, new_pw = st.text_input("아이디"), st.text_input("성명"), st.text_input("비밀번호", type='password')
        if st.form_submit_button("신청하기", use_container_width=True):
            try:
                c.execute('INSERT INTO users VALUES (?,?,?,?,?)', (new_id, new_pw, new_name, "인터폴", "pending"))
                conn.commit(); st.success("신청 완료!")
            except: st.error("이미 존재하는 아이디입니다.")

elif choice == "📊 연락망 및 대시보드":
    st.markdown(f'<div class="glass-box"><h2>👋 환영합니다, {st.session_state["user_name"]} 수사관님!</h2></div>', unsafe_allow_html=True)
    search = st.text_input("연락망 통합 검색", placeholder="국가, 성명, 구분 등 검색")
    query = "SELECT id as 연번, country as 국가, affiliation as 소속, name as 성명, contact as 연락처, category as 구분, purpose as 관리목적, position as 직책, manager as 관리주체 FROM org_chart_v2"
    if search: query += f" WHERE 국가 LIKE '%{search}%' OR 성명 LIKE '%{search}%' OR 소속 LIKE '%{search}%'"
    df = pd.read_sql_query(query, conn)
    st.dataframe(df, use_container_width=True, hide_index=True)

elif choice == "🌍 국가별 공조 특징":
    c.execute("SELECT country_name FROM country_info")
    countries = [r[0] for r in c.fetchall()]
    if countries:
        sel = st.selectbox("국가 선택", countries)
        c.execute("SELECT * FROM country_info WHERE country_name=?", (sel,))
        info = c.fetchone()
        
        for title, content in [("📌 특징", info[1]), ("📞 연락처", info[3]), ("💡 팁", info[4])]:
            st.markdown(f'<div class="glass-box"><h4>{title}</h4>{str(content).replace(chr(10), "<br>")}</div>', unsafe_allow_html=True)

elif choice == "📁 공조 자료실":
    st.markdown('<div class="glass-box"><h2>📁 팀 공용 자료실</h2></div>', unsafe_allow_html=True)
    with st.expander("파일 업로드"):
        up_file = st.file_uploader("파일 선택", type=['hwp', 'hwpx', 'pdf', 'docx', 'jpg', 'png'])
        if st.button("저장") and up_file:
            with open(UPLOAD_DIR / up_file.name, "wb") as f: f.write(up_file.getbuffer())
            c.execute("INSERT INTO file_archive (filename, filepath, upload_date) VALUES (?,?,?)", (up_file.name, up_file.name, datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit(); st.rerun()
    
    c.execute("SELECT id, filename, upload_date FROM file_archive")
    for fid, fname, fdate in c.fetchall():
        st.markdown(f'<div class="glass-box"><b>{fname}</b> ({fdate})</div>', unsafe_allow_html=True)
        with open(UPLOAD_DIR / fname, "rb") as f: st.download_button("다운로드", f, file_name=fname, key=f"dl_{fid}")

elif choice == "⚙️ 데이터 관리":
    if st.session_state.get("user_id") != "admin": st.error("권한이 없습니다."); st.stop()
    tab1, tab2, tab3 = st.tabs(["👤 연락망 관리", "🌍 국가정보 관리", "👥 사용자 관리"])
    
    with tab1:
        st.subheader("📥 데이터 내보내기")
        c.execute("SELECT country, affiliation, name, contact, category, purpose, position, manager FROM org_chart_v2")
        all_data = c.fetchall()
        if all_data:
            df_download = pd.DataFrame(all_data, columns=['국가', '소속', '성명', '연락처', '구분', '관리목적', '직책', '관리주체'])
            df_download.insert(0, '연번', range(1, len(df_download) + 1))
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df_download.to_excel(writer, index=False, sheet_name='연락망')
            processed_data = output.getvalue()
            st.download_button(label="📥 현재 명단 엑셀 다운로드 (.xlsx)", data=processed_data, file_name=f"인터폴팀_연락망_{datetime.now().strftime('%Y%m%d')}.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", use_container_width=True)

        st.divider()
        st.subheader("📤 엑셀 일괄 업로드")
        uploaded_file = st.file_uploader("엑셀 파일 선택", type=['xlsx'])
        if uploaded_file and st.button("🚨 전체 덮어쓰기"):
            df_excel = pd.read_excel(uploaded_file).fillna("")
            c.execute('DELETE FROM org_chart_v2')
            for _, row in df_excel.iterrows():
                c.execute('INSERT INTO org_chart_v2 (country, affiliation, name, contact, category, purpose, position, manager) VALUES (?,?,?,?,?,?,?,?)', (str(row.iloc[1]), str(row.iloc[2]), str(row.iloc[3]), str(row.iloc[4]), str(row.iloc[5]), str(row.iloc[6]), str(row.iloc[7]), str(row.iloc[8])))
            conn.commit(); st.success("반영 완료!"); st.rerun()

        st.divider()
        st.subheader("✍️ 개별 관리")
        with st.form("new"):
            col1, col2 = st.columns(2)
            i1, i2, i3, i4 = col1.text_input("국가"), col1.text_input("소속"), col1.text_input("성명"), col1.text_input("연락처")
            i5, i6, i7, i8 = col2.text_input("구분"), col2.text_input("관리목적"), col2.text_input("직책"), col2.text_input("관리주체")
            if st.form_submit_button("저장"):
                c.execute('INSERT INTO org_chart_v2 (country, affiliation, name, contact, category, purpose, position, manager) VALUES (?,?,?,?,?,?,?,?)', (i1, i2, i3, i4, i5, i6, i7, i8))
                conn.commit(); st.rerun()

    with tab2:
        st.subheader("🌍 국가정보 등록 및 수정")
        
        c.execute("SELECT country_name FROM country_info ORDER BY country_name ASC")
        existing_countries = [r[0] for r in c.fetchall()]
        
        edit_choice = st.selectbox("수정할 국가 선택 (새로 추가하려면 '--- 신규 추가 ---' 선택)", ["--- 신규 추가 ---"] + existing_countries)
        
        default_name = ""
        default_feat = ""
        default_cont = ""
        default_tips = ""
        hidden_treaty = ""
        
        if edit_choice != "--- 신규 추가 ---":
            c.execute("SELECT * FROM country_info WHERE country_name = ?", (edit_choice,))
            target_data = c.fetchone()
            if target_data:
                default_name = target_data[0]
                default_feat = target_data[1]
                hidden_treaty = target_data[2]
                default_cont = target_data[3]
                default_tips = target_data[4]

        with st.form("country_form"):
            cn = st.text_input("국가명", value=default_name)
            cf = st.text_area("핵심 공조 특징", value=default_feat)
            cc = st.text_area("주요 연락 창구", value=default_cont)
            cp = st.text_area("실무 업무 팁 및 주의사항", value=default_tips)
            
            submit_label = "정보 수정 저장" if edit_choice != "--- 신규 추가 ---" else "신규 정보 저장"
            
            if st.form_submit_button(submit_label):
                if cn.strip() == "":
                    st.error("국가명을 입력해주세요.")
                else:
                    c.execute('INSERT OR REPLACE INTO country_info VALUES (?,?,?,?,?)', (cn, cf, hidden_treaty, cc, cp))
                    conn.commit()
                    st.success(f"{cn} 정보가 저장되었습니다.")
                    st.rerun()

    with tab3:
        c.execute('SELECT username, name, department, status FROM users WHERE username != "admin"')
        for u_id, u_name, u_dept, u_status in c.fetchall():
            with st.expander(f"{u_name} ({u_id}) [{u_status}]"):
                col1, col2, col3 = st.columns(3)
                if u_status == "pending":
                    if col1.button("승인", key=f"a_{u_id}"): c.execute('UPDATE users SET status="approved" WHERE username=?', (u_id,)); conn.commit(); st.rerun()
                else:
                    if col1.button("회수", key=f"r_{u_id}"): c.execute('UPDATE users SET status="pending" WHERE username=?', (u_id,)); conn.commit(); st.rerun()
                if col2.button("초기화", key=f"p_{u_id}"): c.execute('UPDATE users SET password="password123!" WHERE username=?', (u_id,)); conn.commit(); st.warning("password123!")
                if col3.button("삭제", key=f"d_{u_id}"): c.execute('DELETE FROM users WHERE username=?', (u_id,)); conn.commit(); st.rerun()