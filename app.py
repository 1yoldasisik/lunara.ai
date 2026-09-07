import os
import datetime
import json
import re
import sqlite3
import bcrypt
import streamlit as st
import streamlit.components.v1 as components
from groq import Groq

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

# --- ŞİFRE GÜVENLİĞİ YARDIMCI FONKSİYONLARI ---

def hash_password(plain_password):
    """Düz metin şifreyi bcrypt ile hash'ler."""
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

def verify_password(plain_password, stored_hash):
    """Girilen şifreyi veritabanındaki bcrypt hash'i ile karşılaştırır.
    Eski (hash'lenmemiş) kayıtlarla geriye dönük uyumluluk için,
    stored_hash geçerli bir bcrypt hash'i değilse düz metin karşılaştırmasına düşer."""
    if not stored_hash or not plain_password:
        return False
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), stored_hash.encode("utf-8"))
    except (ValueError, TypeError):
        # Muhtemelen eski, hash'lenmemiş bir kayıt
        return stored_hash == plain_password

def is_bcrypt_hash(value):
    return bool(value) and (value.startswith("$2b$") or value.startswith("$2a$") or value.startswith("$2y$"))

# --- VERİTABANI YARDIMCI FONKSİYONLARI ---

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

# Sayfa ve Tema Yapılandırması
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
    div[data-testid="stForm"]:has(input[placeholder*="Fal, tarot veya burçlar"]) {
        position: fixed !important;
        bottom: 0 !important;
        left: 0 !important;
        right: 0 !important;
        z-index: 999999 !important;
        background-color: var(--background-color, #0e1117) !important;
        padding: 22px 24px !important;
        min-height: 92px !important;
        box-shadow: 0 -4px 25px rgba(0, 0, 0, 0.4) !important;
        border-top: 1px solid rgba(255, 255, 255, 0.1) !important;
        width: 100% !important;
        box-sizing: border-box !important;
        margin: 0 !important;
    }
    /* Model seçme sütununu küçült */
    div[data-testid="stForm"]:has(input[placeholder*="Fal, tarot veya burçlar"]) [data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child {
        flex: 0 0 150px !important;
        max-width: 150px !important;
    }
    div[data-testid="stForm"]:has(input[placeholder*="Fal, tarot veya burçlar"]) [data-testid="stHorizontalBlock"] > div[data-testid="column"]:first-child [data-baseweb="select"] {
        font-size: 0.82rem !important;
    }
    .main .block-container {
        padding-bottom: 170px !important;
    }
</style>
""", unsafe_allow_html=True)

# EN UYGUN 3 MODEL TANIMI VE ETİKETLERİ
# NOT: mixtral-8x7b-32768, llama-3.1-8b-instant ve llama-3.3-70b-versatile
# Groq tarafından deprecate/decommission edildi (Haziran-Ağustos 2026).
# Güncel, aktif olan modellerle değiştirildi.
MODEL_OPTIONS = {
    "🧠 Gelişmiş (GPT-OSS 120B)": "openai/gpt-oss-120b",
    "⚡ Hızlı (GPT-OSS 20B)": "openai/gpt-oss-20b",
    "🔮 Dengeli (Qwen3.6 27B)": "qwen/qwen3.6-27b"
}

DEFAULT_MODEL_ID = "openai/gpt-oss-120b"

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
    """Groq API'den aktif tüm modelleri sorgular."""
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

    # 1. Denenecek modeller sırasını oluştur (Önce seçilen model, sonra alternatifler)
    candidate_models = []
    if preferred_model:
        candidate_models.append(preferred_model)

    # 3 Ana model yedeği
    candidate_models.extend(list(MODEL_OPTIONS.values()))

    # Hesaptaki diğer dinamik modeller
    active_models = get_groq_models_list()
    candidate_models.extend(active_models)

    # Yinelenen modelleri sırasını koruyarak temizle
    models_to_try = []
    for m in candidate_models:
        if m and m not in models_to_try:
            models_to_try.append(m)

    last_error = ""
    # Arka planda çalışan ilk modeli bulana kadar otomatik dene
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
            # Seçilen model çalışmazsa sessizce sonraki yedek modele geç
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
        "Asla İngilizce cümle veya düşünce süreci (<think>) yazma. Edebi bir bütünlük içinde konuş."
    )

MODEL_CREDIT_COSTS = {
    "openai/gpt-oss-20b": 1,
    "openai/gpt-oss-120b": 2,
    "qwen/qwen3.6-27b": 2,
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

def refund_credits(model_id):
    """generate_completion tüm modellerde başarısız olursa krediyi iade eder."""
    required_cost = MODEL_CREDIT_COSTS.get(model_id, 1)
    if st.session_state.logged_in_email:
        u_email = st.session_state.logged_in_email
        user_data = db_get_user(u_email)
        if user_data:
            user_data["credits"] = user_data.get("credits", 0) + required_cost
            db_save_user(u_email, user_data)
    else:
        st.session_state.guest_credits += required_cost

def generation_failed(response_text):
    return isinstance(response_text, str) and response_text.startswith("Yıldızlardan şu an yanıt alınamadı")

def scroll_to_latest_message():
    """Sohbet listesinin en altına, yani en son alınan yoruma otomatik kaydırır."""
    st.markdown('<div id="lunara-son-mesaj"></div>', unsafe_allow_html=True)
    components.html(
        """
        <script>
            const targetDoc = window.parent.document;
            const anchor = targetDoc.getElementById("lunara-son-mesaj");
            if (anchor) {
                anchor.scrollIntoView({behavior: "smooth", block: "end"});
            }
        </script>
        """,
        height=0,
    )

def pin_chat_bar_to_bottom():
    """Alt sohbet çubuğunu gerçek ekran viewport'una sabitler.
    NOT: Elemanı doğrudan <body>'ye taşımak (reparent) React'in olay
    yönetimini (tıklama, yazma) bozabileceği için DOM yapısı korunuyor;
    bunun yerine çubuğun sabitlenmesini engelleyen 'transform' özelliği
    taşıyan üst kapsayıcılar (Streamlit'in kaydırma animasyonları için
    kullandığı) tespit edilip nötrlüyor, çünkü position:fixed bir
    transform'lu üst elemana denk geldiğinde viewport yerine o elemana
    göre konumlanıyor ve sayfa kaydırılınca kayıyor. Bir MutationObserver
    + periyodik kontrol ile bu durum sürekli korunuyor."""
    components.html(
        """
        <script>
            try {
                const doc = window.parent.document;

                function neutralizeAncestorTransforms(el) {
                    let node = el.parentElement;
                    while (node && node !== doc.body) {
                        const cs = getComputedStyle(node);
                        if (cs.transform && cs.transform !== "none") {
                            node.style.setProperty("transform", "none", "important");
                        }
                        if (cs.filter && cs.filter !== "none") {
                            node.style.setProperty("filter", "none", "important");
                        }
                        node = node.parentElement;
                    }
                }

                function pinLunaraChatBar() {
                    const inputs = doc.querySelectorAll('input[placeholder*="Fal, tarot veya bur"]');
                    inputs.forEach((inp) => {
                        const bar = inp.closest('div[data-testid="stForm"]');
                        if (!bar) return;

                        neutralizeAncestorTransforms(bar);

                        const styleProps = {
                            "position": "fixed",
                            "bottom": "0px",
                            "left": "0px",
                            "right": "0px",
                            "width": "100%",
                            "z-index": "999999",
                            "padding": "22px 24px",
                            "min-height": "92px",
                            "box-sizing": "border-box",
                            "margin": "0px",
                            "box-shadow": "0 -4px 25px rgba(0, 0, 0, 0.4)",
                            "border-top": "1px solid rgba(255, 255, 255, 0.1)"
                        };
                        for (const [prop, val] of Object.entries(styleProps)) {
                            bar.style.setProperty(prop, val, "important");
                        }
                        if (!bar.style.backgroundColor) {
                            const bg = getComputedStyle(doc.body).backgroundColor || "#0e1117";
                            bar.style.setProperty("background-color", bg, "important");
                        }
                    });
                }

                pinLunaraChatBar();
                const lunaraObserver = new MutationObserver(pinLunaraChatBar);
                lunaraObserver.observe(doc.body, {childList: true, subtree: true});
                // Ek güvence: bazı yeniden çizimler mutation observer'ı kaçırabiliyor
                setInterval(pinLunaraChatBar, 800);
            } catch (e) {
                console.warn("Lunara chat bar pin failed:", e);
            }
        </script>
        """,
        height=0,
    )

# Modallar
@st.dialog("✨ Lunara.ai - Giriş Yap")
def login_dialog():
    l_email = st.text_input("E-posta Adresi")
    l_pass = st.text_input("Şifre", type="password")
    col1, col2 = st.columns(2)
    if col1.button("Giriş Yap", use_container_width=True):
        user_data = db_get_user(l_email)
        if user_data and verify_password(l_pass, user_data["password"]):
            # Eski (hash'lenmemiş) kayıtları ilk başarılı girişte otomatik hash'le
            if not is_bcrypt_hash(user_data["password"]):
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

@st.dialog("✨ Lunara.ai - Üye Ol")
def signup_dialog():
    s_name = st.text_input("Ad Soyad")
    s_email = st.text_input("E-posta Adresi")
    s_pass = st.text_input("Şifre", type="password")
    col1, col2 = st.columns(2)
    if col1.button("Kayıt Ol", use_container_width=True):
        if s_name and s_email and s_pass:
            if db_get_user(s_email):
                st.warning("Bu e-posta zaten kullanımda.")
            else:
                db_save_user(s_email, {"name": s_name, "password": hash_password(s_pass), "credits": 20})
                st.session_state.logged_in_email = s_email
                st.session_state.logged_in_user = s_name
                st.session_state.messages = []
                st.session_state.auth_mode = None
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
    new_pass = st.text_input(
        "Yeni Şifre (değiştirmek istemiyorsanız boş bırakın)",
        type="password",
        value=""
    )
    new_loc = st.text_input("Konum", value=user_data.get("location", ""))

    col1, col2 = st.columns(2)
    if col1.button("Kaydet", use_container_width=True):
        update = {"name": new_name, "location": new_loc}
        if new_pass:
            update["password"] = hash_password(new_pass)
        user_data.update(update)
        db_save_user(email, user_data)
        st.session_state.logged_in_user = new_name
        st.session_state.auth_mode = None
        st.rerun()
    if col2.button("İptal", use_container_width=True):
        st.session_state.auth_mode = None
        st.rerun()

if st.session_state.auth_mode == "login": login_dialog()
elif st.session_state.auth_mode == "signup": signup_dialog()
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
    model_id = model_id or DEFAULT_MODEL_ID
    if not deduct_credits(model_id):
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

        if generation_failed(response):
            refund_credits(model_id)
            st.error("⚠️ Yanıt alınamadı, krediniz iade edildi. Lütfen tekrar deneyin.")

        st.session_state.messages.append({"role": "assistant", "content": response})
        if st.session_state.logged_in_email:
            db_save_chat_message(st.session_state.logged_in_email, "assistant", response)
    return True

st.title("🌙 Lunara.ai | Mistik Rehber")

tab1, tab2, tab3, tab4 = st.tabs(["💬 Mistik Sohbet", "🪐 Doğum Haritası Analizi", "🃏 3 Kart Tarot", "☕ Kahve Falı"])

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

    for idx, msg in enumerate(st.session_state.messages):
        with st.chat_message(msg["role"], avatar="👤" if msg["role"] == "user" else "🌙"):
            st.write(msg["content"])

    if st.session_state.messages:
        scroll_to_latest_message()

with tab2:
    st.subheader("🪐 Doğum Haritası Potansiyel Analizi")

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

        # --- DÜZELTİLEN TARİH SEÇİM ALANI ---
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
        # ------------------------------------

        saat = st.time_input("Doğum Saatiniz", value=default_saat)
        sehir = st.text_input("Doğum Yeri (İl/Ülke)", value=default_sehir)
        submit = st.form_submit_button("🪐 Haritayı Analiz Et")

    if submit:
        # --- TARİH GEÇERLİLİK KONTROLÜ ---
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
                if deduct_credits(DEFAULT_MODEL_ID):
                    with st.spinner("Gezegen konumları ve doğum haritası hesaplanıyor..."):
                        prompt = (
                            f"Kullanıcı Bilgileri:\n"
                            f"- İsim: {ad}\n"
                            f"- Doğum Tarihi: {tarih}\n"
                            f"- Doğum Saati: {saat}\n"
                            f"- Doğum Yeri: {sehir}\n\n"
                            "Bu bilgilere dayanarak profesyonel bir astrolog gibi TAMAMEN TÜRKÇE, akıcı ve edebi bir dille şu başlıklar altında detaylı bir analiz sun:\n"
                            "1. **Güneş Burcu ve Öz Kimlik:**\n"
                            "2. **Yükselen Burcu ve Dış Dünya:**\n"
                            "3. **Ay Burcu ve İç Dünya:**\n"
                            "4. **Ruhsal Yolculuk ve Önemli Tavsiyeler:**"
                        )
                        res = generate_completion([{"role": "user", "content": prompt}], preferred_model=DEFAULT_MODEL_ID)
                        if res and not generation_failed(res):
                            st.session_state.astro_result = res
                        else:
                            refund_credits(DEFAULT_MODEL_ID)
                            st.session_state.astro_result = "Yıldızlardan şu an yanıt alınamadı, krediniz iade edildi. Lütfen tekrar deneyin."
    if st.session_state.get("astro_result"):
        st.markdown("---")
        st.markdown(st.session_state.astro_result)

with tab3:
    niyet = st.text_input("Niyetiniz:")
    if st.button("Kartları Çek"):
        if deduct_credits(DEFAULT_MODEL_ID):
            with st.spinner("Karıştırılıyor..."):
                res = generate_completion([{"role": "user", "content": f"{niyet} niyetine 3 tarot kartı çek ve yorumla."}], preferred_model=DEFAULT_MODEL_ID)
                if generation_failed(res):
                    refund_credits(DEFAULT_MODEL_ID)
                st.session_state.tarot_result = res
                st.rerun()
    if st.session_state.tarot_result: st.write(st.session_state.tarot_result)

with tab4:
    metin = st.text_area("Sembolleri anlatın:")
    if st.button("Analiz Yap"):
        if metin and deduct_credits(DEFAULT_MODEL_ID):
            with st.spinner("Çözümleniyor..."):
                res = generate_completion([{"role": "user", "content": f"{metin} sembollerini yorumla."}], preferred_model=DEFAULT_MODEL_ID)
                if generation_failed(res):
                    refund_credits(DEFAULT_MODEL_ID)
                st.session_state.kahve_result = res
                st.rerun()
    if st.session_state.kahve_result: st.write(st.session_state.kahve_result)

# Alt Sohbet Çubuğu
with st.container():
    with st.form(key="global_chat_bar_form", clear_on_submit=True):
        b1, b2, b3 = st.columns([1.5, 7.5, 1.0])
        with b1:
            selected_label = st.selectbox(
                "Model",
                options=list(MODEL_OPTIONS.keys()),
                label_visibility="collapsed"
            )
            active_model_id = MODEL_OPTIONS[selected_label]
        with b2: user_text = st.text_input("Mesaj", label_visibility="collapsed", placeholder="Fal, tarot veya burçlar hakkında bir şey sor...")
        with b3: submitted = st.form_submit_button("➤")

pin_chat_bar_to_bottom()

if submitted and user_text:
    if process_chat_request(user_text, active_model_id):
        st.rerun()
