import streamlit as st
import sqlite3
import pandas as pd
import os
import base64
from datetime import datetime

# --- 0. 기본 화면 설정 ---
st.set_page_config(page_title="서울경찰청 인터폴팀", page_icon="🕵️", layout="centered")

# --- 1. 배경 이미지 설정 (투명도 0.4) ---
def get_base64_of_bin_file(bin_file):
    with open(bin_file, 'rb') as f:
        data = f.read()
    return base64.b64encode(data).decode()

image_path = 'blue_tiger.png'

if os.path.exists(image_path):
    img_base64 = get_base64_of_bin_file(image_path)
    st.markdown(
        f"""
        <style>
        .stApp {{
            background-image: linear-gradient(rgba(255,255,255,0.4), rgba(255,255,255,0.4)), url("data:image/png;base64,{img_base64}");
            background-size: cover;
            background-repeat: no-repeat;
            background-attachment: fixed;
            background-position: center;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )
else:
    st.warning("배경 이미지(blue_tiger.png)를 찾을 수 없습니다.")

# --- 2. 앱 전체 디자인(CSS) ---
st.markdown("""
<style>
    [data-testid="stSidebar"] {
        background-color: #002D56;
    }
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    
    .stButton>button {
        background-color: #00529B;
        color: white;
        border-radius: 10px;
        border: none;
        padding: 10px 20px;
        font-weight: bold;
        transition: all 0.3s ease;
    }
    .stButton>button:hover {
        background-color: #003B73;
        transform: scale(1.02);
    }
    
    .stTextInput>div>div>input, .stTextArea>div>div>textarea {
        border-radius: 8px;
        border: 1px solid #ccc;
    }
    [data-testid="stDataFrame"] {
        background-color: rgba(255, 255, 255, 0.9);
        border-radius: 10px;
        overflow: hidden;
        box-shadow: 0 4px 6px rgba(0,0,0,0.1);
    }

    .glass-box {
        background-color: rgba(255, 255, 255, 0.85);
        padding: 20px;
        border-radius: 15px;
        box-shadow: 0 4px 10px rgba(0,0,0,0.15);
        margin-bottom: 20px;
        color: #222;
        line-height: 1.6;
    }
    .glass-box h4 {
        color: #002D56;
        margin-top: 0;
        margin-bottom: 12px;
        border-bottom: 2px solid #00529B;
        padding-bottom: 8px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. 데이터베이스 및 폴더 초기화 ---
conn = sqlite3.connect('users.db', check_same_thread=False)
c = conn.cursor()

c.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, password TEXT, name TEXT, department TEXT, status TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS org_chart (id INTEGER PRIMARY KEY AUTOINCREMENT, dept TEXT, name TEXT, contact TEXT, task TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS country_info (country_name TEXT PRIMARY KEY, features TEXT, treaty TEXT, contacts TEXT, tips TEXT)')
c.execute('CREATE TABLE IF NOT EXISTS file_archive (id INTEGER PRIMARY KEY AUTOINCREMENT, filename TEXT, filepath TEXT, upload_date TEXT)')

if not os.path.exists("uploads"):
    os.makedirs("uploads")
conn.commit()

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = ""

# --- 4. 사이드바 메뉴 (관리자 권한 분리) ---
menu = ["로그인", "회원가입"]
if st.session_state["logged_in"]:
    # 🌟 [핵심 수정] admin 계정이면 모든 메뉴를 보여주고, 일반 계정이면 데이터 관리를 숨깁니다.
    if st.session_state.get("user_id") == "admin":
        menu = ["📊 대시보드 및 조직도", "🌍 국가별 공조 특징", "📁 공조 자료실", "⚙️ 데이터 관리", "로그아웃"]
    else:
        menu = ["📊 대시보드 및 조직도", "🌍 국가별 공조 특징", "📁 공조 자료실", "로그아웃"]

st.sidebar.title("🕵️ 서울청 인터폴팀")
st.sidebar.markdown("---")
choice = st.sidebar.selectbox("메뉴 선택", menu)

# --- 5. 기능별 화면 구현 ---

if choice == "로그아웃":
    st.session_state["logged_in"] = False
    st.session_state["user_id"] = ""
    st.rerun()

elif choice == "로그인":
    st.markdown("""
    <div style="text-align: center; margin-bottom: 20px;">
        <h2 style='color: #002D56; margin-top: 0; text-shadow: 2px 2px 4px rgba(255,255,255,0.8); font-weight: 900;'>🔒 인터폴팀 업무 지원 시스템</h2>
        <p style='color: #333; font-weight: bold;'>허가된 인원만 접근 가능합니다.</p>
    </div>
    """, unsafe_allow_html=True)
    
    _, col2, _ = st.columns([1, 2, 1])
    with col2:
        user_id = st.text_input("아이디")
        user_pw = st.text_input("비밀번호", type='password')
        if st.button("로그인", use_container_width=True):
            if user_id == "admin" and user_pw == "1234":
                st.session_state["logged_in"] = True
                st.session_state["user_name"] = "관리자"
                st.session_state["user_id"] = "admin"
                st.rerun()
            else:
                c.execute('SELECT * FROM users WHERE username=? AND password=? AND status="approved"', (user_id, user_pw))
                data = c.fetchone()
                if data:
                    st.session_state["logged_in"] = True
                    st.session_state["user_name"] = data[2]
                    st.session_state["user_id"] = data[0]
                    st.rerun()
                else:
                    st.error("로그인 실패: 정보를 확인하거나 승인 여부를 문의하세요.")

elif choice == "회원가입":
    st.markdown('<div class="glass-box"><h2 style="margin:0;">📝 계정 신청</h2><p>신청 후 관리자의 승인이 필요합니다.</p></div>', unsafe_allow_html=True)
    with st.form("signup_form"):
        new_id = st.text_input("아이디")
        new_name = st.text_input("성명")
        new_pw = st.text_input("비밀번호", type='password')
        if st.form_submit_button("신청하기", use_container_width=True):
            try:
                c.execute('INSERT INTO users VALUES (?,?,?,?,?)', (new_id, new_pw, new_name, "인터폴", "pending"))
                conn.commit()
                st.success("신청 완료!")
            except:
                st.error("이미 존재하는 아이디입니다.")

elif choice == "📊 대시보드 및 조직도":
    st.markdown(f'<div class="glass-box"><h2 style="margin:0;">👋 환영합니다, {st.session_state["user_name"]} 수사관님!</h2></div>', unsafe_allow_html=True)
    
    c.execute("SELECT COUNT(*) FROM org_chart")
    total_staff = c.fetchone()[0]
    c.execute("SELECT COUNT(*) FROM file_archive")
    total_files = c.fetchone()[0]
    
    col1, col2 = st.columns(2)
    with col1:
        st.markdown(f'<div class="glass-box" style="text-align:center;"><h4>👥 등록된 인적 네트워크</h4><h2 style="margin:0;">{total_staff} 명</h2></div>', unsafe_allow_html=True)
    with col2:
        st.markdown(f'<div class="glass-box" style="text-align:center;"><h4>📁 공조 자료실 파일</h4><h2 style="margin:0;">{total_files} 건</h2></div>', unsafe_allow_html=True)

    st.markdown('<div class="glass-box" style="padding-bottom: 5px;"><h4 style="border:none; margin:0;">🔍 조직도 및 연락처</h4></div>', unsafe_allow_html=True)
    search = st.text_input("검색어 입력", placeholder="이름, 부서, 업무 등", label_visibility="collapsed")
    query = "SELECT dept, name, contact, task FROM org_chart"
    if search:
        query += f" WHERE name LIKE '%{search}%' OR task LIKE '%{search}%' OR dept LIKE '%{search}%'"
    c.execute(query)
    df = pd.DataFrame(c.fetchall(), columns=['부서', '성명', '연락처', '담당업무'])
    st.dataframe(df, use_container_width=True, hide_index=True)

elif choice == "🌍 국가별 공조 특징":
    st.markdown('<div class="glass-box"><h2 style="margin:0;">🌍 국가별 공조 정보</h2></div>', unsafe_allow_html=True)
    c.execute("SELECT country_name FROM country_info")
    countries = [r[0] for r in c.fetchall()]
    if countries:
        sel = st.selectbox("조회할 국가를 선택하세요", countries)
        c.execute("SELECT * FROM country_info WHERE country_name=?", (sel,))
        info = c.fetchone()
        
        sections = [("📌 핵심 공조 특징", info[1]), ("📜 인도조약 / 사법공조 여부", info[2]), 
                    ("📞 주요 연락 창구", info[3]), ("💡 실무 업무 팁 및 주의사항", info[4])]
        
        for title, content in sections:
            formatted_content = str(content).replace('\n', '<br>') if content else "내용 없음"
            st.markdown(f'<div class="glass-box"><h4>{title}</h4>{formatted_content}</div>', unsafe_allow_html=True)
    else:
        st.info("등록된 국가 정보가 없습니다.")

elif choice == "📁 공조 자료실":
    st.markdown('<div class="glass-box"><h2 style="margin:0;">📁 팀 공통 자료실</h2></div>', unsafe_allow_html=True)
    
    with st.expander("➕ 새 파일 업로드하기", expanded=False):
        up_file = st.file_uploader(
            "문서 및 이미지 파일을 선택하세요", 
            type=['hwp', 'hwpx', 'pdf', 'docx', 'doc', 'xlsx', 'jpg', 'jpeg', 'png']
        )
        if st.button("서버에 저장", use_container_width=True) and up_file:
            path = os.path.join("uploads", up_file.name)
            with open(path, "wb") as f:
                f.write(up_file.getbuffer())
            c.execute("INSERT INTO file_archive (filename, filepath, upload_date) VALUES (?,?,?)",
                      (up_file.name, path, datetime.now().strftime("%Y-%m-%d %H:%M")))
            conn.commit()
            st.success(f"'{up_file.name}' 업로드 성공!")
            st.rerun()

    f_search = st.text_input("파일명 검색", placeholder="검색어를 입력하세요")
    f_query = "SELECT id, filename, filepath, upload_date FROM file_archive"
    if f_search:
        f_query += f" WHERE filename LIKE '%{f_search}%'"
    
    c.execute(f_query)
    files = c.fetchall()
    
    if not files:
        st.markdown('<div class="glass-box">등록된 자료가 없습니다.</div>', unsafe_allow_html=True)
    else:
        for f_id, f_name, f_path, f_date in files:
            st.markdown(f"""
            <div class="glass-box" style="margin-bottom: 10px; padding: 15px;">
                <h5 style="margin:0; color:#002D56;">{f_name}</h5>
                <p style="margin:0; font-size: 12px; color: gray;">업로드: {f_date}</p>
            </div>
            """, unsafe_allow_html=True)
            
            col1, col2 = st.columns(2)
            with open(f_path, "rb") as f:
                col1.download_button("⬇️ 다운로드", f, file_name=f_name, key=f"dl_{f_id}", use_container_width=True)
            if col2.button("🗑️ 파일 삭제", key=f"del_{f_id}", use_container_width=True):
                if os.path.exists(f_path): os.remove(f_path)
                c.execute("DELETE FROM file_archive WHERE id=?", (f_id,))
                conn.commit()
                st.rerun()

elif choice == "⚙️ 데이터 관리":
    # 🌟 [이중 보안] 만약 비정상적인 방법으로 접근하더라도 차단되도록 방어막 설정
    if st.session_state.get("user_id") != "admin":
        st.error("🚫 최고 관리자 전용 메뉴입니다. 접근 권한이 없습니다.")
        st.stop()
        
    st.markdown('<div class="glass-box"><h2 style="margin:0;">⚙️ 시스템 관리</h2></div>', unsafe_allow_html=True)
    tab1, tab2, tab3 = st.tabs(["👤 조직도 관리", "🌍 국가정보 관리", "✅ 승인대기"])
    
    with tab1:
        st.subheader("신규 팀원 등록")
        with st.form("org_new"):
            d, n, c_no, t = st.text_input("부서"), st.text_input("성명"), st.text_input("연락처"), st.text_input("업무")
            if st.form_submit_button("신규 저장", use_container_width=True):
                c.execute('INSERT INTO org_chart (dept, name, contact, task) VALUES (?,?,?,?)', (d, n, c_no, t))
                conn.commit()
                st.success("등록 완료!")
                st.rerun()

        st.divider()
        st.subheader("기존 팀원 수정/삭제")
        c.execute("SELECT id, dept, name, contact, task FROM org_chart")
        org_rows = c.fetchall()
        for rid, rdept, rname, rcontact, rtask in org_rows:
            with st.expander(f"👤 {rname} ({rdept})"):
                with st.form(f"edit_org_{rid}"):
                    edit_dept = st.text_input("부서", value=rdept)
                    edit_name = st.text_input("성명", value=rname)
                    edit_contact = st.text_input("연락처", value=rcontact)
                    edit_task = st.text_input("업무", value=rtask)
                    
                    col1, col2 = st.columns(2)
                    if col1.form_submit_button("💾 정보 수정", use_container_width=True):
                        c.execute("UPDATE org_chart SET dept=?, name=?, contact=?, task=? WHERE id=?", 
                                  (edit_dept, edit_name, edit_contact, edit_task, rid))
                        conn.commit()
                        st.success("수정되었습니다.")
                        st.rerun()
                    if col2.form_submit_button("🗑️ 팀원 삭제", use_container_width=True):
                        c.execute("DELETE FROM org_chart WHERE id=?", (rid,))
                        conn.commit()
                        st.warning("삭제되었습니다.")
                        st.rerun()

    with tab2:
        st.subheader("국가 정보 등록 및 수정")
        st.info("국가명을 입력하고 정보를 넣으면 자동으로 등록되거나 기존 정보가 수정됩니다.")
        with st.form("country_manage"):
            cn = st.text_input("국가명 (예: 중국, 베트남)")
            cf = st.text_area("핵심 공조 특징")
            ct = st.text_input("범죄인 인도조약 / 사법공조 여부")
            cc = st.text_area("주요 연락 창구")
            cp = st.text_area("실무 업무 팁 및 주의사항")
            if st.form_submit_button("💾 정보 저장/수정", use_container_width=True):
                c.execute('INSERT OR REPLACE INTO country_info VALUES (?,?,?,?,?)', (cn, cf, ct, cc, cp))
                conn.commit()
                st.success(f"{cn} 정보가 처리되었습니다.")
                st.rerun()
        
        st.divider()
        st.subheader("기존 국가 정보 관리 (수정/삭제)")
        c.execute("SELECT country_name, features, treaty, contacts, tips FROM country_info")
        country_data = c.fetchall()
        
        if not country_data:
            st.write("등록된 국가가 없습니다.")
        else:
            for cname, cfeat, ctreaty, ccont, ctips in country_data:
                with st.expander(f"🌍 {cname} 정보 상세보기/관리"):
                    with st.form(f"edit_country_{cname}"):
                        e_feat = st.text_area("핵심 공조 특징", value=cfeat)
                        e_treaty = st.text_input("인도조약/사법공조", value=ctreaty)
                        e_cont = st.text_area("주요 연락 창구", value=ccont)
                        e_tips = st.text_area("업무 팁", value=ctips)
                        
                        col1, col2 = st.columns(2)
                        if col1.form_submit_button(f"💾 {cname} 수정", use_container_width=True):
                            c.execute("UPDATE country_info SET features=?, treaty=?, contacts=?, tips=? WHERE country_name=?", 
                                      (e_feat, e_treaty, e_cont, e_tips, cname))
                            conn.commit()
                            st.success(f"{cname} 정보가 수정되었습니다.")
                            st.rerun()
                        if col2.form_submit_button(f"🗑️ {cname} 삭제", use_container_width=True):
                            c.execute("DELETE FROM country_info WHERE country_name=?", (cname,))
                            conn.commit()
                            st.warning(f"{cname} 정보가 완전히 삭제되었습니다.")
                            st.rerun()

    with tab3:
        c.execute('SELECT username, name FROM users WHERE status="pending"')
        users = c.fetchall()
        if not users: st.info("대기 중인 계정이 없습니다.")
        for u in users:
            st.markdown(f'<div class="glass-box" style="padding:15px; margin-bottom:10px;"><b>{u[1]}</b> ({u[0]})</div>', unsafe_allow_html=True)
            if st.button("승인하기", key=f"app_{u[0]}", use_container_width=True):
                c.execute('UPDATE users SET status="approved" WHERE username=?', (u[0],))
                conn.commit()
                st.rerun()
                