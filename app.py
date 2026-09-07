import os
import datetime
import json
import re
import sqlite3
import hashlib
import urllib.request
import streamlit as st
from groq import Groq

# Türkiye Şehir Listesi
TURKEY_CITIES = [
    "Adana", "Adıyaman", "Afyonkarahisar", "Ağrı", "Aksaray", "Amasya", "Ankara", "Antalya", 
    "Ardahan", "Artvin", "Aydın", "Balıkesir", "Bartın", "Batman", "Bayburt", "Bilecik", 
    "Bingöl", "Bitlis", "Bolu", "Burdur", "Bursa", "Çanakkale", "Çankırı", "Çorum", 
    "Denizli", "Diyarbakır", "Düzce", "Edirne", "Elazığ", "Erzincan", "Erzurum", "Eskişehir", 
    "Gaziantep", "Giresun", "Gümüşhane", "Hakkari", "Hatay", "Iğdır", "Isparta", "İstanbul", 
    "İzmir", "Kahramanmaraş", "Karabük", "Karaman", "Kars", "Kastamonu", "Kayseri", "Kırıkkale", 
    "Kırklareli", "Kırşehir", "Kilis", "Kocaeli", "Konya", "Kütahya", "Malatya", "Manisa", 
    "Mardin", "Mersin", "Muğla", "Muş", "Nevşehir", "Niğde", "Ordu", "Osmaniye", "Rize", 
    "Sakarya", "Samsun", "Siirt", "Sinop", "Sivas", "Şanlıurfa", "Şırnak", "Tekirdağ", 
    "Tokat", "Trabzon", "Tunceli", "Uşak", "Van", "Yalova", "Yozgat", "Zonguldak"
]

# SQLite Veritabanı Yapılandırması
DB_FILE = "lunara.db"

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            email TEXT PRIMARY KEY,
            name TEXT,
            password TEXT,
            location TEXT,
            birth_date TEXT,
            birth_time TEXT,
            bio TEXT,
            email_notifications INTEGER,
            credits INTEGER,
            saved_readings TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS chat_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            email TEXT,
            role TEXT,
            content TEXT,
            timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

# --- YARDIMCI FONKSİYONLAR (KONUM & GÜVENLİK) ---

def get_auto_location():
    """Kullanıcının tarayıcı/istemci IP adresinden şehir ve ülke bilgisini tespit eder."""
    try:
        client_ip = ""
        # Streamlit HTTP istek başlıklarından gerçek istemci IP'sini alma (Sunucu IP'sini önlemek için)
        if hasattr(st, "context") and hasattr(st.context, "headers"):
            headers = st.context.headers
            if headers:
                for header_key in ["x-forwarded-for", "cf-connecting-ip", "x-real-ip"]:
                    for h_k, h_v in headers.items():
                        if h_k.lower() == header_key:
                            client_ip = h_v.split(",")[0].strip()
                            break
                    if client_ip:
                        break

        url = f"http://ip-api.com/json/{client_ip}" if client_ip else "http://ip-api.com/json/"
        req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=3) as response:
            data = json.loads(response.read().decode())
            if data.get("status") == "success":
                city = data.get("city", "")
                country = data.get("country", "")
                return f"{city}, {country}".strip(", ")
    except Exception:
        pass
    return ""

def hash_password(password: str) -> str:
    """Şifreyi SHA-256 algoritması ile hash'ler."""
    return hashlib.sha256(password.encode('utf-8')).hexdigest()

def verify_password(stored_password: str, provided_password: str) -> bool:
    """Hash'lenmiş veya eski açık metin şifreleri doğrular."""
    if len(stored_password) == 64 and all(c in '0123456789abcdefABCDEF' for c in stored_password):
        return stored_password == hash_password(provided_password)
    return stored_password == provided_password

def check_password_strength(password: str):
    """Şifre gücünü ve eksik kriterleri kontrol eder."""
    score = 0
    feedback = []
    
    if len(password) >= 8:
        score += 1
    else:
        feedback.append("En az 8 karakter olmalı.")
        
    if re.search(r"[A-Z]", password):
        score += 1
    else:
        feedback.append("En az 1 büyük harf (A-Z) içermeli.")
        
    if re.search(r"[a-z]", password):
        score += 1
    else:
        feedback.append("En az 1 küçük harf (a-z) içermeli.")
        
    if re.search(r"[0-9]", password):
        score += 1
    else:
        feedback.append("En az 1 rakam (0-9) içermeli.")
        
    if re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        score += 1
    else:
        feedback.append("En az 1 özel karakter (!@#$%^&* vb.) içermeli.")
        
    return score, feedback

# --- VERİTABANI İŞLEMLERİ ---

def db_get_user(email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("SELECT name, password, location, birth_date, birth_time, bio, email_notifications, credits, saved_readings FROM users WHERE email = ?", (email,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return {
            "name": row[0],
            "password": row[1],
            "location": row[2],
            "birth_date": datetime.date.fromisoformat(row[3]) if row[3] else None,
            "birth_time": datetime.datetime.strptime(row[4], "%H:%M:%S").time() if row[4] else None,
            "bio": row[5],
            "email_notifications": bool(row[6]),
            "credits": row[7],
            "saved_readings": json.loads(row[8]) if row[8] else []
        }
    return None

def db_save_user(email, data):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    b_date_str = data["birth_date"].isoformat() if data.get("birth_date") else None
    b_time_str = data["birth_time"].strftime("%H:%M:%S") if data.get("birth_time") else None
    saved_readings_str = json.dumps(data.get("saved_readings", []), ensure_ascii=False)
    
    cursor.execute('''
        INSERT OR REPLACE INTO users (email, name, password, location, birth_date, birth_time, bio, email_notifications, credits, saved_readings)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', (
        email,
        data.get("name"),
        data.get("password"),
        data.get("location"),
        b_date_str,
        b_time_str,
        data.get("bio"),
        1 if data.get("email_notifications", True) else 0,
        data.get("credits", 20),
        saved_readings_str
    ))
    conn.commit()
    conn.close()

def db_save_chat_message(email, role, content):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO chat_history (email, role, content)
        VALUES (?, ?, ?)
    ''', (email, role, content))
    conn.commit()
    conn.close()

def db_get_chat_history(email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT role, content FROM chat_history
        WHERE email = ?
        ORDER BY timestamp ASC
    ''', (email,))
    rows = cursor.fetchall()
    conn.close()
    return [{"role": row[0], "content": row[1]} for row in rows]

def db_clear_chat_history(email):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM chat_history WHERE email = ?", (email,))
    conn.commit()
    conn.close()

# Sayfa Yapılandırması
st.set_page_config(page_title="Lunara.ai | Mistik Rehber", page_icon="🌙", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
    [data-testid="stForm"] [data-testid="stHorizontalBlock"] {
        display: flex !important;
        align-items: center !important;
        flex-direction: row !important;
    }
    [data-testid="stForm"] [data-testid="column"] {
        width: auto !important;
        flex: 1 1 0% !important;
        min-width: 0px !important;
    }
    form:has(input[placeholder*="Fal, tarot veya burçlar"]) {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        z-index: 999999 !important;
        background-color: var(--background-color, #0e1117) !important;
        padding: 12px 24px !important;
        box-shadow: 0 -4px 25px rgba(0, 0, 0, 0.4) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.1) !important;
        width: 100% !important;
        box-sizing: border-box !important;
    }
    .main .block-container {
        padding-bottom: 140px !important;
    }
</style>
""", unsafe_allow_html=True)

# MODEL TANIMLARI
MODEL_OPTIONS = {
    "🧠 Gelişmiş (Llama 3.3 70B)": "llama-3.3-70b-versatile",
    "⚡ Hızlı (Llama 3.1 8B)": "llama-3.1-8b-instant",
    "🔮 Dengeli (Mixtral 8x7B)": "mixtral-8x7b-32768"
}

def get_groq_api_key():
    try:
        key = st.secrets.get("GROQ_API_KEY")
    except Exception:
        key = None
    if not key:
        key = os.environ.get("GROQ_API_KEY")
    return key

def get_groq_client():
    api_key = get_groq_api_key()
    if not api_key:
        return None
    return Groq(api_key=api_key)

@st.cache_data(ttl=300)
def get_groq_models_list():
    client = get_groq_client()
    if not client:
        return []
    try:
        models_data = client.models.list()
        valid_models = []
        for m in models_data.data:
            m_id = getattr(m, 'id', '')
            if m_id and not any(x in m_id.lower() for x in ['whisper', 'audio', 'embed', 'guard', 'vision', 'safetensors']):
                valid_models.append(m_id)
        return valid_models
    except Exception:
        return []

def generate_completion(messages, preferred_model=None):
    client = get_groq_client()
    if client is None:
        return "Groq API anahtarı bulunamadı. Lütfen st.secrets veya ortam değişkenlerini kontrol edin."

    candidate_models = []
    if preferred_model:
        candidate_models.append(preferred_model)
    
    candidate_models.extend(list(MODEL_OPTIONS.values()))
    
    active_models = get_groq_models_list()
    candidate_models.extend(active_models)

    fallback_models = ["gemma2-9b-it", "llama3-8b-8192"]
    candidate_models.extend(fallback_models)

    models_to_try = []
    for m in candidate_models:
        if m and m not in models_to_try:
            models_to_try.append(m)

    last_error = ""
    for current_model in models_to_try:
        try:
            response = client.chat.completions.create(
                model=current_model,
                messages=messages,
                temperature=0.4,
                max_tokens=1500,
            )
            if response and response.choices:
                content = response.choices[0].message.content
                clean_content = re.sub(r'<think>[\s\S]*?</think>', '', content).strip()
                return clean_content
        except Exception as e:
            last_error = str(e)
            continue
            
    return f"Yıldızlardan şu an yanıt alınamadı. (Detay: {last_error})"

# Oturum Yönetimi
if "messages" not in st.session_state: st.session_state.messages = []
if "recent_queries" not in st.session_state: st.session_state.recent_queries = []
if "auth_mode" not in st.session_state: st.session_state.auth_mode = None
if "logged_in_user" not in st.session_state: st.session_state.logged_in_user = None
if "logged_in_email" not in st.session_state: st.session_state.logged_in_email = None
if "guest_credits" not in st.session_state: st.session_state.guest_credits = 10
if "astro_result" not in st.session_state: st.session_state.astro_result = ""
if "tarot_result" not in st.session_state: st.session_state.tarot_result = ""
if "kahve_result" not in st.session_state: st.session_state.kahve_result = ""

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = (
        "Sen Lunara'sın. Profesyonel, empatik ve mistik bir astroloji ve fal danışmanısın. "
        "DİL KURALI: Cevaplarının TAMAMI YALNIZCA KUSURSUZ VE AKICI TÜRKÇE OLMALIDIR. "
        "Asla İngilizce cümle veya düşünce süreci (<think>) yazma. "
        "KESİN KURAL: Hiçbir zaman 'Bu bilgiler ışığında...', 'Gökyüzünün o anki dansını inceleyerek...', 'Sizin için hazırladım' gibi "
        "giriş, açıklama veya sunuş cümleleri yazma. Doğrudan ve net bir şekilde doğrudan analizin/yorumun kendisine başla."
    )

MODEL_CREDIT_COSTS = {
    "llama-3.1-8b-instant": 1,
    "llama-3.3-70b-versatile": 2,
    "mixtral-8x7b-32768": 2,
    "gemma2-9b-it": 1
}

def deduct_credits(model_id):
    required_cost = MODEL_CREDIT_COSTS.get(model_id, 1)
    if st.session_state.logged_in_email:
        u_email = st.session_state.logged_in_email
        user_data = db_get_user(u_email)
        if user_data:
            current_credits = user_data.get("credits", 0)
            if current_credits < required_cost:
                st.error(f"⚠️ Yetersiz kredi! Bu işlem {required_cost} kredi gerektiriyor. Mevcut krediniz: {current_credits}.")
                return False
            user_data["credits"] -= required_cost
            db_save_user(u_email, user_data)
    else:
        if st.session_state.guest_credits < required_cost:
            st.error(f"⚠️ Yetersiz misafir kredisi! Bu işlem {required_cost} kredi gerektiriyor. Lütfen üye olun.")
            return False
        st.session_state.guest_credits -= required_cost
    return True

# --- MODALLAR VE DİYALOGLAR ---

@st.dialog("✨ Lunara.ai - Giriş Yap")
def login_dialog():
    l_email = st.text_input("E-posta Adresi")
    l_pass = st.text_input("Şifre", type="password")
    
    col1, col2 = st.columns(2)
    if col1.button("Giriş Yap", use_container_width=True):
        user_data = db_get_user(l_email)
        if user_data and verify_password(user_data["password"], l_pass):
            if user_data["password"] == l_pass:
                user_data["password"] = hash_password(l_pass)
                db_save_user(l_email, user_data)
                
            st.session_state.logged_in_email = l_email
            st.session_state.logged_in_user = user_data["name"]
            st.session_state.messages = db_get_chat_history(l_email)
            st.session_state.auth_mode = None
            st.rerun()
        else:
            st.error("Hatalı e-posta veya şifre!")
            
    if col2.button("İptal", use_container_width=True):
        st.session_state.auth_mode = None
        st.rerun()

    st.markdown("---")
    if st.button("🔑 Şifremi Unuttum", use_container_width=True):
        st.session_state.auth_mode = "forgot_pass"
        st.rerun()

@st.dialog("✨ Lunara.ai - Üye Ol")
def signup_dialog():
    s_name = st.text_input("Ad Soyad")
    s_email = st.text_input("E-posta Adresi")
    s_pass = st.text_input("Şifre", type="password")
    
    if s_pass:
        score, feedback = check_password_strength(s_pass)
        progress_val = min(score / 5.0, 1.0)
        st.caption(f"Şifre Gücü: **%{int(progress_val * 100)}**")
        st.progress(progress_val)
        if feedback:
            for fb in feedback:
                st.caption(f"⚠️ {fb}")
    
    st.markdown("---")
    
    with st.expander("📜 KVKK Aydınlatma Metni & Kullanım Koşulları"):
        st.write("""
        **1. Kişisel Verilerin Korunması:** Lunara.ai, kişisel verilerinizi 6698 sayılı KVKK gereğince yalnızca yapay zeka tabanlı astroloji/fal hizmeti sunmak ve üyelik işlemlerini yürütmek amacıyla işler.
        **2. Veri Güvenliği:** Şifreleriniz kriptografik yöntemlerle şifrelenerek saklanır.
        **3. Hizmet Şartları:** Üretilen içerikler eğlence ve kişisel gelişim amaçlıdır.
        """)
        
    kvkk_check = st.checkbox("KVKK Aydınlatma Metni'ni ve Kullanım Koşulları'nı okudum, kabul ediyorum.")
    
    col1, col2 = st.columns(2)
    if col1.button("Kayıt Ol", use_container_width=True):
        if not s_name or not s_email or not s_pass:
            st.error("⚠️ Lütfen tüm alanları doldurun.")
        elif not kvkk_check:
            st.warning("⚠️ Devam etmek için KVKK ve Kullanım Koşulları'nı onaylamalısınız.")
        else:
            score, _ = check_password_strength(s_pass)
            if score < 3:
                st.error("⚠️ Lütfen daha güçlü bir şifre seçin (En az 8 karakter, harf ve rakam içermelidir).")
            elif db_get_user(s_email):
                st.warning("⚠️ Bu e-posta zaten kullanımda.")
            else:
                hashed_pass = hash_password(s_pass)
                db_save_user(s_email, {"name": s_name, "password": hashed_pass, "credits": 20})
                st.session_state.logged_in_email = s_email
                st.session_state.logged_in_user = s_name
                st.session_state.messages = []
                st.session_state.auth_mode = None
                st.rerun()

    if col2.button("İptal", use_container_width=True):
        st.session_state.auth_mode = None
        st.rerun()

@st.dialog("🔑 Şifremi Unuttum")
def forgot_password_dialog():
    f_email = st.text_input("Kayıtlı E-posta Adresiniz")
    new_pass = st.text_input("Yeni Şifre", type="password")
    confirm_pass = st.text_input("Yeni Şifre (Tekrar)", type="password")
    
    if new_pass:
        score, feedback = check_password_strength(new_pass)
        progress_val = min(score / 5.0, 1.0)
        st.caption(f"Şifre Gücü: **%{int(progress_val * 100)}**")
        st.progress(progress_val)
        if feedback:
            for fb in feedback:
                st.caption(f"⚠️ {fb}")

    col1, col2 = st.columns(2)
    if col1.button("Şifreyi Güncelle", use_container_width=True):
        user_data = db_get_user(f_email)
        if not user_data:
            st.error("⚠️ Bu e-posta adresiyle kayıtlı bir kullanıcı bulunamadı.")
        elif new_pass != confirm_pass:
            st.error("⚠️ Girilen şifreler eşleşmiyor!")
        else:
            score, _ = check_password_strength(new_pass)
            if score < 3:
                st.error("⚠️ Lütfen daha güçlü bir şifre belirleyin.")
            else:
                user_data["password"] = hash_password(new_pass)
                db_save_user(f_email, user_data)
                st.success("✅ Şifreniz başarıyla güncellendi! Giriş yapabilirsiniz.")
                st.session_state.auth_mode = "login"
                st.rerun()

    if col2.button("İptal", use_container_width=True):
        st.session_state.auth_mode = None
        st.rerun()

@st.dialog("⚙️ Gelişmiş Profil")
def profile_dialog():
    email = st.session_state.logged_in_email
    user_data = db_get_user(email)
    
    st.info(f"🪙 **Mevcut Kredi:** {user_data.get('credits', 0)}")
    if st.button("✨ 50 Kredi Yükle"):
        user_data["credits"] += 50
        db_save_user(email, user_data)
        st.rerun()
    
    new_name = st.text_input("Ad Soyad", value=user_data.get("name", ""))
    
    # --- KONUM SEÇİMİ VE OTOMATİK BULMA ---
    st.write("**Konum Bilgisi:**")
    
    # Türkiye Şehirleri Açılır Listesi
    selected_tr_city = st.selectbox(
        "🇹🇷 Türkiye'den Şehir Seçin (İsteğe Bağlı):",
        options=["-- Seçiniz veya Elle Giriniz --"] + [f"{city}, Türkiye" for city in TURKEY_CITIES]
    )
    
    current_loc = st.session_state.get("temp_location", user_data.get("location", ""))
    if selected_tr_city != "-- Seçiniz veya Elle Giriniz --":
        current_loc = selected_tr_city

    col_loc1, col_loc2 = st.columns([3, 1])
    with col_loc1:
        new_loc = st.text_input("Konum (İl/Ülke veya Özel Konum)", value=current_loc, label_visibility="collapsed")
    with col_loc2:
        if st.button("📍 Otomatik Bul", use_container_width=True):
            auto_loc = get_auto_location()
            if auto_loc:
                st.session_state["temp_location"] = auto_loc
                st.toast(f"📍 Güncel konumunuz tespit edildi: {auto_loc}")
                st.rerun()
            else:
                st.error("Konumunuz tespit edilemedi.")

    # --- BİLDİRİM ABONELİĞİ ---
    email_notif = st.checkbox(
        "🔔 E-posta bildirimlerine ve günlük burç bültenine abone ol",
        value=user_data.get("email_notifications", True)
    )
    
    st.markdown("---")
    
    # --- ŞİFRE DEĞİŞTİRME (ESKİ ŞİFRE SORULMAZ) ---
    st.write("🔒 **Şifre Değiştirme** (Şifrenizi değiştirmek istemiyorsanız alanları boş bırakın)")
    new_pass = st.text_input("Yeni Şifreniz", type="password", key="p_new")
    confirm_new_pass = st.text_input("Yeni Şifreniz (Tekrar)", type="password", key="p_conf")
    
    if new_pass:
        score, feedback = check_password_strength(new_pass)
        progress_val = min(score / 5.0, 1.0)
        st.caption(f"Yeni Şifre Gücü: **%{int(progress_val * 100)}**")
        st.progress(progress_val)
        if feedback:
            for fb in feedback:
                st.caption(f"⚠️ {fb}")
    
    col1, col2 = st.columns(2)
    if col1.button("Kaydet", use_container_width=True):
        # Şifre Değişikliği İsteği
        if new_pass or confirm_new_pass:
            if not new_pass:
                st.error("⚠️ Lütfen yeni bir şifre girin!")
                return
            if new_pass != confirm_new_pass:
                st.error("⚠️ Yeni şifreleriniz birbiriyle eşleşmiyor!")
                return
            
            score, _ = check_password_strength(new_pass)
            if score < 3:
                st.error("⚠️ Yeni şifreniz yeterince güçlü değil.")
                return
                
            user_data["password"] = hash_password(new_pass)

        # Temp Konum Temizliği & Profil Güncelleme
        final_loc = new_loc
        if "temp_location" in st.session_state:
            del st.session_state["temp_location"]

        user_data.update({
            "name": new_name,
            "location": final_loc,
            "email_notifications": email_notif
        })
        
        db_save_user(email, user_data)
        st.session_state.logged_in_user = new_name
        st.session_state.auth_mode = None
        st.toast("✅ Profiliniz başarıyla güncellendi!")
        st.rerun()

    if col2.button("İptal", use_container_width=True):
        if "temp_location" in st.session_state:
            del st.session_state["temp_location"]
        st.session_state.auth_mode = None
        st.rerun()

if st.session_state.auth_mode == "login": login_dialog()
elif st.session_state.auth_mode == "signup": signup_dialog()
elif st.session_state.auth_mode == "forgot_pass": forgot_password_dialog()
elif st.session_state.auth_mode == "profile": profile_dialog()

# Yan Panel
with st.sidebar:
    st.title("🌙 Lunara.ai")
    st.markdown("---")
    
    if st.session_state.logged_in_email:
        u_record = db_get_user(st.session_state.logged_in_email)
        st.markdown(f"✨ **{st.session_state.logged_in_user}**")
        st.caption(f"🪙 Kredi Bakiyesi: **{u_record.get('credits', 0)}**")
        
        col1, col2 = st.columns(2)
        if col1.button("⚙️ Profil", use_container_width=True):
            st.session_state.auth_mode = "profile"
            st.rerun()
        if col2.button("Çıkış", use_container_width=True):
            st.session_state.logged_in_email = None
            st.session_state.logged_in_user = None
            st.session_state.messages = []
            st.rerun()
    else:
        st.caption(f"🪙 Misafir Kredisi: **{st.session_state.guest_credits}**")
        col1, col2 = st.columns(2)
        if col1.button("Giriş Yap", use_container_width=True):
            st.session_state.auth_mode = "login"
            st.rerun()
        if col2.button("Üye Ol", use_container_width=True):
            st.session_state.auth_mode = "signup"
            st.rerun()

    st.markdown("---")
    if st.button("🗑️ Sohbet Geçmişini Temizle", use_container_width=True):
        if st.session_state.logged_in_email:
            db_clear_chat_history(st.session_state.logged_in_email)
        st.session_state.messages = []
        st.rerun()

def process_chat_request(prompt_text, model_id=None):
    if not deduct_credits(model_id or "llama-3.3-70b-versatile"):
        return False

    st.session_state.messages.append({"role": "user", "content": prompt_text})
    if st.session_state.logged_in_email:
        db_save_chat_message(st.session_state.logged_in_email, "user", prompt_text)
    
    with st.spinner("Yıldızlar okunuyor..."):
        prompt_messages = [{"role": "system", "content": st.session_state.get("system_prompt")}]
        history = st.session_state.messages[-10:] if len(st.session_state.messages) > 10 else st.session_state.messages
        for m in history[:-1]: prompt_messages.append({"role": m["role"], "content": m["content"]})
        prompt_messages.append({"role": "user", "content": prompt_text})

        response = generate_completion(prompt_messages, preferred_model=model_id)
        
        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.logged_in_email:
            db_save_chat_message(st.session_state.logged_in_email, "assistant", response)
    return True

st.title("🌙 Lunara.ai | Mistik Rehber")

# Sekmelerin tanımlanması
tab1, tab2, tab3, tab4 = st.tabs(["💬 Mistik Sohbet", "🪐 Doğum Haritası Analizi", "🃏 3 Kart Tarot", "☕ Kahve Falı"])

# --- TAB 1: MİSTİK SOHBET ---
with tab1:
    st.markdown("### ✨ Hızlı Sorular")
    c1, c2, c3, c4 = st.columns(4)
    q_prompt = None
    if c1.button("☕ Günlük Fal Yorumu", use_container_width=True): q_prompt = "Bugün için günlük falımı yorumlar mısın?"
    if c2.button("💖 Aşk & Uyum", use_container_width=True): q_prompt = "Aşk hayatımla ilgili mesajı yorumlar mısın?"
    if c3.button("💼 Kariyer & Gelecek", use_container_width=True): q_prompt = "Kariyerimle ilgili yıldızların mesajı nedir?"
    if c4.button("🃏 Tarot Çek", use_container_width=True): q_prompt = "Benim için bir tarot kartı çek ve yorumla."

    if q_prompt:
        if process_chat_request(q_prompt): st.rerun()

    for msg in reversed(st.session_state.messages):
        with st.chat_message(msg["role"], avatar="👤" if msg["role"] == "user" else "🌙"):
            st.write(msg["content"])

# --- TAB 2: DOĞUM HARİTASI ANALİZİ ---
with tab2:
    st.subheader("🪐 Doğum Haritası Potansiyel Analizi")
    
    if st.session_state.get("astro_result"):
        st.markdown(st.session_state.astro_result)
        st.markdown("---")

    default_ad = ""
    default_tarih = datetime.date(1995, 1, 1)
    default_saat = datetime.time(12, 0)
    default_sehir = ""

    if st.session_state.logged_in_email:
        u_data = db_get_user(st.session_state.logged_in_email)
        if u_data:
            default_ad = u_data.get("name", "")
            default_sehir = u_data.get("location", "")
            if u_data.get("birth_date"):
                default_tarih = u_data.get("birth_date")
            if u_data.get("birth_time"):
                default_saat = u_data.get("birth_time")

    with st.form("astro_form"):
        ad = st.text_input("Adınız ve Soyadınız", value=default_ad)
        
        st.write("**Doğum Tarihiniz:**")
        col_d, col_m, col_y = st.columns(3)
        with col_d:
            sel_day = st.selectbox("Gün", list(range(1, 32)), index=default_tarih.day - 1)
        with col_m:
            sel_month = st.selectbox("Ay", list(range(1, 13)), index=default_tarih.month - 1)
        with col_y:
            current_year = datetime.date.today().year
            years_list = list(range(current_year, 1919, -1))
            default_year_idx = years_list.index(default_tarih.year) if default_tarih.year in years_list else 0
            sel_year = st.selectbox("Yıl", years_list, index=default_year_idx)
            
        saat = st.time_input("Doğum Saatiniz", value=default_saat)
        sehir = st.text_input("Doğum Yeri (İl/Ülke)", value=default_sehir)
        submit = st.form_submit_button("🪐 Haritayı Analiz Et")

    if submit:
        try:
            tarih = datetime.date(sel_year, sel_month, sel_day)
            valid_date = True
        except ValueError:
            st.error("⚠️ Seçtiğiniz tarih geçersiz (Örn: Şubat ayında 30-31. gün seçimi). Lütfen tarihi kontrol edin.")
            valid_date = False

        if valid_date:
            if not ad or not sehir:
                st.warning("⚠️ Lütfen adınızı ve doğum yerini eksiksiz doldurun.")
            else:
                if deduct_credits("llama-3.3-70b-versatile"):
                    with st.spinner("Gezegen konumları ve doğum haritası hesaplanıyor..."):
                        prompt = (
                            f"Kullanıcı Bilgileri:\n"
                            f"- İsim: {ad}\n"
                            f"- Doğum Tarihi: {tarih}\n"
                            f"- Doğum Saati: {saat}\n"
                            f"- Doğum Yeri: {sehir}\n\n"
                            "Giriş veya sunuş cümlesi yazmadan DOĞRUDAN 1. maddeden başlayarak şu başlıklar altında analizi sun:\n"
                            "1. **Güneş Burcu ve Öz Kimlik:**\n"
                            "2. **Yükselen Burcu ve Dış Dünya:**\n"
                            "3. **Ay Burcu ve İç Dünya:**\n"
                            "4. **Ruhsal Yolculuk ve Önemli Tavsiyeler:**"
                        )
                        res = generate_completion([{"role": "user", "content": prompt}], preferred_model="llama-3.3-70b-versatile")
                        if res:
                            st.session_state.astro_result = res
                            st.rerun()
                        else:
                            st.session_state.astro_result = "Yıldızlardan şu an yanıt alınamadı, lütfen tekrar deneyin."

# --- TAB 3: 3 KART TAROT ---
with tab3:
    if st.session_state.tarot_result: 
        st.write(st.session_state.tarot_result)
        st.markdown("---")

    niyet = st.text_input("Niyetiniz:")
    if st.button("Kartları Çek"):
        if deduct_credits("llama-3.3-70b-versatile"):
            with st.spinner("Karıştırılıyor..."):
                res = generate_completion([{"role": "user", "content": f"Giriş cümlesi yazmadan doğrudan {niyet} niyetine 3 tarot kartı çek ve yorumla."}], preferred_model="llama-3.3-70b-versatile")
                st.session_state.tarot_result = res
                st.rerun()

# --- TAB 4: KAHVE FALI ---
with tab4:
    if st.session_state.kahve_result: 
        st.write(st.session_state.kahve_result)
        st.markdown("---")

    metin = st.text_area("Sembolleri anlatın:")
    if st.button("Analiz Yap"):
        if metin and deduct_credits("llama-3.3-70b-versatile"):
            with st.spinner("Çözümleniyor..."):
                res = generate_completion([{"role": "user", "content": f"Giriş/sunuş cümlesi yazmadan doğrudan şu sembolleri yorumla: {metin}"}], preferred_model="llama-3.3-70b-versatile")
                st.session_state.kahve_result = res
                st.rerun()

# Alt Sohbet Çubuğu
with st.container():
    with st.form(key="global_chat_bar_form", clear_on_submit=True):
        b1, b2, b3 = st.columns([2.5, 6.5, 1.0])
        with b1:
            selected_label = st.selectbox(
                "Model",
                options=list(MODEL_OPTIONS.keys()),
                label_visibility="collapsed"
            )
            active_model_id = MODEL_OPTIONS[selected_label]
        with b2: user_text = st.text_input("Mesaj", label_visibility="collapsed", placeholder="Fal, tarot veya burçlar hakkında bir şey sor...")
        with b3: submitted = st.form_submit_button("➤")

if submitted and user_text:
    if process_chat_request(user_text, active_model_id):
        st.rerun()
