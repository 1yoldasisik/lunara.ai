import os
import datetime
import streamlit as st
from groq import Groq

# Sayfa ve Tema Yapılandırması
st.set_page_config(
    page_title="Lunara.ai | Mistik Rehber",
    page_icon="🌙",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Sohbet çubuğunu Gemini gibi sabitleyen ve model seçimini sol tarafa hizalayan CSS
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
    
    /* Sohbet çubuğunu en alta sabitleme (Gemini tarzı) */
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

    /* Sayfa içeriğinin sabit çubuğun altında kalmaması için alt boşluk */
    .main .block-container {
        padding-bottom: 140px !important;
    }
</style>
""", unsafe_allow_html=True)

# Groq API ve Model Yönetimi
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


def generate_completion(messages, model_name=None):
    client = get_groq_client()
    if client is None:
        return "Groq API anahtarı eksik. Lütfen yapılandırma dosyasını veya ortam değişkenini kontrol edin."

    try:
        models_response = client.models.list()
        available_models = [
            m.id for m in models_response.data 
            if not any(x in m.id.lower() for x in ["guard", "whisper", "embed"])
        ]
        
        if model_name and model_name in available_models:
            chosen_model = model_name
        elif available_models:
            preferred = ["llama-3.3-70b-versatile", "llama-3.1-70b-versatile", "llama-3.1-8b-instant", "llama3-70b-8192", "mixtral-8x7b-32768"]
            chosen_model = next((m for m in preferred if m in available_models), available_models[0])
        else:
            chosen_model = "llama-3.3-70b-versatile"

        response = client.chat.completions.create(
            model=chosen_model,
            messages=messages,
            temperature=0.4,
            max_tokens=2048,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Bir hata oluştu: {str(e)}"

# Oturum ve Kullanıcı Belleği Yönetimi
if "messages" not in st.session_state:
    st.session_state.messages = []

if "recent_queries" not in st.session_state:
    st.session_state.recent_queries = []

if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = None

if "users" not in st.session_state:
    st.session_state.users = {}

if "logged_in_user" not in st.session_state:
    st.session_state.logged_in_user = None

if "logged_in_email" not in st.session_state:
    st.session_state.logged_in_email = None

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = (
        "Sen Lunara'sın. Profesyonel, empatik ve mistik bir astroloji ve fal danışmanısın. "
        "Kullanıcılara her zaman akıcı, gramer açısından kusursuz, anlamlı ve edebi bir Türkçe ile yanıt ver. "
        "Asla anlamsız, kopuk, rüya benzeri veya saçma cümleler kurma; her zaman mantıklı bir bütünlük içinde konuş."
    )

# Giriş, Üye Ol ve Profil Modalları (Dialogs)
@st.dialog("✨ Lunara.ai - Giriş Yap")
def login_dialog():
    st.write("Yıldızların rehberliğine tekrar hoş geldin.")
    l_email = st.text_input("E-posta Adresi", key="l_email")
    l_pass = st.text_input("Şifre", type="password", key="l_pass")
    col_l1, col_l2 = st.columns(2)
    with col_l1:
        if st.button("Giriş Yap", use_container_width=True, key="submit_login"):
            if l_email and l_pass:
                if l_email in st.session_state.users and st.session_state.users[l_email]["password"] == l_pass:
                    st.session_state.logged_in_email = l_email
                    st.session_state.logged_in_user = st.session_state.users[l_email]["name"]
                    st.success(f"Hoş geldin, {st.session_state.logged_in_user}! Yıldızlar seninle.")
                    st.session_state.auth_mode = None
                    st.rerun()
                else:
                    st.error("E-posta veya şifre hatalı!")
            else:
                st.warning("Lütfen tüm alanları doldurun.")
    with col_l2:
        if st.button("İptal", use_container_width=True, key="cancel_login"):
            st.session_state.auth_mode = None
            st.rerun()

@st.dialog("✨ Lunara.ai - Üye Ol")
def signup_dialog():
    st.write("Mistik yolculuğa ilk adımını at ve ruhsal profilini oluştur.")
    s_name = st.text_input("Ad Soyad", key="s_name")
    s_email = st.text_input("E-posta Adresi", key="s_email")
    s_pass = st.text_input("Şifre", type="password", key="s_pass")
    col_s1, col_s2 = st.columns(2)
    with col_s1:
        if st.button("Kayıt Ol", use_container_width=True, key="submit_signup"):
            if s_name and s_email and s_pass:
                if s_email in st.session_state.users:
                    st.warning("Bu e-posta adresi ile zaten bir hesap mevcut.")
                else:
                    st.session_state.users[s_email] = {
                        "name": s_name, 
                        "password": s_pass, 
                        "email_notifications": True
                    }
                    st.session_state.logged_in_email = s_email
                    st.session_state.logged_in_user = s_name
                    st.success("Üyeliğiniz başarıyla oluşturuldu ve giriş yapıldı! Hoş geldin.")
                    st.session_state.auth_mode = None
                    st.rerun()
            else:
                st.warning("Lütfen tüm alanları doldurun.")
    with col_s2:
        if st.button("İptal", use_container_width=True, key="cancel_signup"):
            st.session_state.auth_mode = None
            st.rerun()

@st.dialog("⚙️ Profil Ayarları ve Bildirimler")
def profile_dialog():
    email = st.session_state.logged_in_email
    if not email or email not in st.session_state.users:
        st.warning("Oturum bilgisi bulunamadı.")
        if st.button("Kapat", key="close_prof_err"):
            st.session_state.auth_mode = None
            st.rerun()
        return

    user_data = st.session_state.users[email]
    st.write("Kişisel bilgilerinizi düzenleyebilir ve bildirim tercihlerinizi yönetebilirsiniz.")

    new_name = st.text_input("Ad Soyad", value=user_data["name"], key="prof_name")
    st.text_input("E-posta Adresi (Değiştirilemez)", value=email, disabled=True, key="prof_email")
    new_pass = st.text_input("Şifre", type="password", value=user_data["password"], key="prof_pass")
    
    email_notif = st.checkbox(
        "E-posta bildirimleri al (Günlük fal, özel tarot ve burç uyarıları)", 
        value=user_data.get("email_notifications", True),
        key="prof_notif"
    )

    col_p1, col_p2 = st.columns(2)
    with col_p1:
        if st.button("Değişiklikleri Kaydet", use_container_width=True, key="save_profile"):
            st.session_state.users[email]["name"] = new_name
            st.session_state.users[email]["password"] = new_pass
            st.session_state.users[email]["email_notifications"] = email_notif
            st.session_state.logged_in_user = new_name
            st.success("Profil ayarlarınız başarıyla güncellendi!")
            st.session_state.auth_mode = None
            st.rerun()
    with col_p2:
        if st.button("İptal", use_container_width=True, key="cancel_profile"):
            st.session_state.auth_mode = None
            st.rerun()

if st.session_state.auth_mode == "login":
    login_dialog()
elif st.session_state.auth_mode == "signup":
    signup_dialog()
elif st.session_state.auth_mode == "profile":
    profile_dialog()

# Yan Panel
with st.sidebar:
    st.title("🌙 Lunara.ai")
    st.caption("Astroloji & Kehanet Rehberi")

    st.markdown("---")
    st.subheader("✨ Günün Mistik Enerjisi")
    st.info("🃏 **Günün Kartı: Güneş** — Neşe, başarı ve netlik dolu bir enerji seni sarıyor.")

    st.markdown("---")
    st.subheader("🕒 Son Kullanılanlar")
    
    recent_selected_prompt = None
    if not st.session_state.get("recent_queries"):
        st.caption("Henüz geçmiş işlem bulunmuyor.")
    else:
        for idx, q in enumerate(reversed(st.session_state.recent_queries[-5:])):
            short_q = (q[:22] + "...") if len(q) > 22 else q
            if st.button(f"🔹 {short_q}", key=f"recent_btn_{idx}", use_container_width=True):
                recent_selected_prompt = q

    st.markdown("---")
    if st.button("🗑️ Sohbet Geçmişini Temizle", use_container_width=True):
        st.session_state.messages = []
        st.session_state.recent_queries = []
        st.rerun()

    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #888888; font-size: 0.85em;'>"
        "✨ Tasarım & Geliştirme<br><b>Yoldaş Işık</b> tarafından işlendi 🌙"
        "</div>", 
        unsafe_allow_html=True
    )

# Sidebar'daki "Son Kullanılanlar" butonuna basıldığında tetiklenecek mekanizma
if recent_selected_prompt:
    st.session_state.messages.append({"role": "user", "content": recent_selected_prompt})
    with st.spinner("Yıldızlar ve semboller okunuyor..."):
        prompt_messages = [{"role": "system", "content": st.session_state.get("system_prompt", "Sen Lunara'sın.")}]
        for m in st.session_state.messages[:-1]:
            prompt_messages.append({"role": m["role"], "content": m["content"]})
        prompt_messages.append({"role": "user", "content": recent_selected_prompt})

        # Varsayılan model ile tetikle
        response = generate_completion(prompt_messages, model_name="llama-3.3-70b-versatile")
        st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()

# En Üst Sağ Köşe: Giriş Yap / Üye Ol veya Profil/Çıkış Alanı
top_space_col1, top_space_col2 = st.columns([7, 4])
with top_space_col2:
    if st.session_state.logged_in_email:
        u_c1, u_c2, u_c3 = st.columns([2, 1.2, 1])
        with u_c1:
            st.markdown(f"<div style='text-align: right; padding-top: 8px; font-size: 0.85em;'>✨ <b>{st.session_state.logged_in_user}</b></div>", unsafe_allow_html=True)
        with u_c2:
            if st.button("⚙️ Profil", key="profile_btn", use_container_width=True):
                st.session_state.auth_mode = "profile"
                st.rerun()
        with u_c3:
            if st.button("Çıkış", key="logout_btn", use_container_width=True):
                st.session_state.logged_in_email = None
                st.session_state.logged_in_user = None
                st.session_state.auth_mode = None
                st.rerun()
    else:
        auth_c1, auth_c2 = st.columns(2)
        with auth_c1:
            if st.button("Giriş Yap", key="top_login_btn", use_container_width=True):
                st.session_state.auth_mode = "login"
                st.rerun()
        with auth_c2:
            if st.button("Üye Ol", key="top_signup_btn", use_container_width=True):
                st.session_state.auth_mode = "signup"
                st.rerun()

# Ana Başlık Alanı
st.title("🌙 Lunara.ai | Mistik Rehber")
st.write("Kişiselleştirilmiş Yapay Zeka Fal, Tarot ve Astroloji Danışmanı")

api_key = get_groq_api_key()
if not api_key:
    st.warning("⚠️ Groq API anahtarı bulunamadı. Lütfen `.streamlit/secrets.toml` dosyanızı kontrol edin.")

tab1, tab2, tab3, tab4 = st.tabs([
    "💬 Mistik Sohbet", 
    "🪐 Doğum Haritası Analizi", 
    "🃏 3 Kart Tarot Açılımı", 
    "☕ Kahve Falı & Rüyalar"
])

# Sekme 1: Mistik Sohbet
with tab1:
    st.markdown("### ✨ Hızlı Mistik Sorular")
    col_h1, col_h2, col_h3, col_h4 = st.columns(4)

    quick_prompt_to_send = None
    if col_h1.button("☕ Günlük Fal Yorumu", use_container_width=True):
        quick_prompt_to_send = "Bugün için genel falımı ve yıldızların bana mesajını yorumlar mısın?"
    if col_h2.button("💖 Aşk & Uyum", use_container_width=True):
        quick_prompt_to_send = "Aşk hayatımla ilgili evrenin bana vermek istediği mesaj nedir?"
    if col_h3.button("💼 Kariyer & Gelecek", use_container_width=True):
        quick_prompt_to_send = "Kariyerim ve maddi geleceğim konusunda yıldızlar ne söylüyor?"
    if col_h4.button("🃏 Tarot & Kader", use_container_width=True):
        quick_prompt_to_send = "Geleceğime ışık tutacak bir kart çekerek bana rehberlik eder misin?"

    # Hızlı butonlara tıklandığında doğrudan mesajı ekle ve yanıt üret
    if quick_prompt_to_send:
        if quick_prompt_to_send not in st.session_state.recent_queries:
            st.session_state.recent_queries.append(quick_prompt_to_send)
            if len(st.session_state.recent_queries) > 10:
                st.session_state.recent_queries.pop(0)

        st.session_state.messages.append({"role": "user", "content": quick_prompt_to_send})
        with st.spinner("Yıldızlar ve semboller okunuyor..."):
            prompt_messages = [{"role": "system", "content": st.session_state.get("system_prompt", "Sen Lunara'sın.")}]
            for m in st.session_state.messages[:-1]:
                prompt_messages.append({"role": m["role"], "content": m["content"]})
            prompt_messages.append({"role": "user", "content": quick_prompt_to_send})

            response = generate_completion(prompt_messages, model_name="llama-3.3-70b-versatile")
            st.session_state.messages.append({"role": "assistant", "content": response})
        st.rerun()

    st.warning("🤖 Hoş geldin. Ben Lunara. Yıldızların fısıltıları, kartların gizemi ve evrenin sırlarıyla sana rehberlik etmek için buradayım.")

    for msg in st.session_state.messages:
        avatar_icon = "👤" if msg["role"] == "user" else "🌙"
        with st.chat_message(msg["role"], avatar=avatar_icon):
            st.write(msg["content"])

# Sekme 2: Doğum Haritası Analizi
with tab2:
    st.subheader("🪐 Doğum Haritası Potansiyel Analizi")
    with st.form("astro_form"):
        ad = st.text_input("Adınız ve Soyadınız")
        tarih = st.date_input(
            "Doğum Tarihiniz", 
            min_value=datetime.date(1900, 1, 1), 
            max_value=datetime.date.today()
        )
        saat = st.time_input("Doğum Saatiniz (Tahmini)")
        sehir = st.text_input("Doğum Yeri (İl/Ülke)")
        submit = st.form_submit_button("🪐 Haritayı Analiz Et")

    if submit and ad and sehir:
        with st.spinner("Gezegen konumları hesaplanıyor ve yıldızlar okunuyor..."):
            prompt = (
                f"Kullanıcı Bilgileri:\n"
                f"- İsim: {ad}\n"
                f"- Doğum Tarihi: {tarih}\n"
                f"- Doğum Saati: {saat}\n"
                f"- Doğum Yeri: {sehir}\n\n"
                "Bu bilgilere dayanarak profesyonel bir astrolog ve mistik rehber gibi akıcı, kusursuz ve edebi bir Türkçe ile şu başlıklar altında detaylı bir analiz sun:\n"
                "1. **Güneş Burcu ve Öz Kimlik:** (Kişinin temel karakterini, yaşam enerjisini ve potansiyelini açıkla)\n"
                "2. **Yükselen Burcu ve Dış Dünya:** (Verilen saate göre dışarıdan nasıl algılandığını ve maskesini açıkla)\n"
                "3. **Ay Burcu ve İç Dünya:** (Duygusal dünyasını, iç sığınağını ve bilinçaltı dinamiklerini açıkla)\n"
                "4. **Ruhsal Yolculuk ve Önemli Tavsiyeler:** (Kişinin bu hayattaki kadersel yönelimini mistik bir dille özetle)\n\n"
                "Asla anlamsız kelime tekrarları yapma, yapılandırılmış ve akıcı paragraflar kullan."
            )
            temp_messages = [
                {"role": "system", "content": "Sen dünyanın en iyi, en akıcı ve edebi dili kullanan uzman bir astrolog ve mistik rehberisin. Kesinlikle kelime tekrarı yapmazsın."},
                {"role": "user", "content": prompt}
            ]
            result = generate_completion(temp_messages, model_name="llama-3.3-70b-versatile")
            st.markdown("---")
            st.markdown(result)

# Sekme 3: 3 Kart Tarot Açılımı
with tab3:
    st.subheader("🃏 3 Kart Tarot Açılımı (Geçmiş - Şimdi - Gelecek)")
    niyet = st.text_input("Odaklanmak istediğiniz konu veya niyetiniz:", placeholder="Örn: Kariyerimdeki değişiklikler...")
    
    if st.button("🃏 Kartları Çek ve Yorumla"):
        with st.spinner("Kartlar karıştırılıyor ve çekiliyor..."):
            prompt = (
                f"Kullanıcının Niyeti/Sorusu: '{niyet if niyet else 'Genel Hayat Akışı'}'. "
                "Rastgele 3 Tarot kartı seç (Geçmiş, Şimdi ve Gelecek pozisyonları için). "
                "Her kartın adını, düz/ters durumunu ve bu 3 kartın birbiriyle olan mistik bağını niyet doğrultusunda detaylıca yorumla."
            )
            temp_messages = [
                {"role": "system", "content": "Sen sezgileri güçlü profesyonel bir Tarot okuyucususun."},
                {"role": "user", "content": prompt}
            ]
            tarot_result = generate_completion(temp_messages, model_name="llama-3.3-70b-versatile")
            st.markdown("---")
            st.markdown(tarot_result)

# Sekme 4: Kahve Falı ve Rüyalar
with tab4:
    st.subheader("☕ Kahve Falı & Rüya Tabiri")
    metin = st.text_area("Fincanınızdaki sembolleri veya gördüğünüz rüyayı anlatın:", height=150)
    
    if st.button("☕ Mistik Sembol Analizi Yap"):
        if metin:
            with st.spinner("Semboller çözümleniyor..."):
                prompt = (
                    f"Kullanıcı Metni: '{metin}'. "
                    "Bu metindeki sembolleri, objeleri ve hisleri hem mistik geleneğe hem de bilincin derinliklerine dayanarak "
                    "detaylı, anlamlı ve yol gösterici bir biçimde yorumla."
                )
                temp_messages = [
                    {"role": "system", "content": "Sen sembol bilimi ve mistik rüya/fincan yorumlama konusunda uzman bir rehbersin."},
                    {"role": "user", "content": prompt}
                ]
                symbol_result = generate_completion(temp_messages, model_name="llama-3.3-70b-versatile")
                st.markdown("---")
                st.markdown(symbol_result)
        else:
            st.warning("Lütfen analiz edilecek bir metin yazın.")

# Alt Kısma Sabitlenmiş Global Giriş Çubuğu (Model Seçim Menüsü Eski Konumunda / Alt Bar İçinde)
with st.container():
    with st.form(key="global_chat_bar_form", clear_on_submit=True):
        b_col1, b_col2, b_col3 = st.columns([1.2, 7.8, 1.0])

        with b_col1:
            bar_model_choice = st.selectbox(
                "Model",
                options=["Pro (70B)", "Flash (8B)", "Beta"],
                label_visibility="collapsed"
            )
            bar_model_map = {
                "Pro (70B)": "llama-3.3-70b-versatile",
                "Flash (8B)": "llama-3.1-8b-instant",
                "Beta": "llama-3.2-90b-vision-preview"
            }
            current_active_model = bar_model_map[bar_model_choice]

        with b_col2:
            user_text = st.text_input("Mesaj", placeholder="Fal, tarot veya burçlar hakkında bir şey yazın...", label_visibility="collapsed")

        with b_col3:
            submitted = st.form_submit_button("➤", help="Gönder")

if submitted and user_text:
    final_prompt = user_text
    if final_prompt not in st.session_state.recent_queries:
        st.session_state.recent_queries.append(final_prompt)
        if len(st.session_state.recent_queries) > 10:
            st.session_state.recent_queries.pop(0)

    message_payload = {"role": "user", "content": final_prompt}
    st.session_state.messages.append(message_payload)

    with st.chat_message("user", avatar="👤"):
        st.write(final_prompt)

    with st.chat_message("assistant", avatar="🌙"):
        with st.spinner("Yıldızlar ve semboller okunuyor..."):
            prompt_messages = [{"role": "system", "content": st.session_state.get("system_prompt", "Sen Lunara'sın.")}]
            for m in st.session_state.messages[:-1]:
                prompt_messages.append({"role": m["role"], "content": m["content"]})
            prompt_messages.append({"role": "user", "content": final_prompt})

            response = generate_completion(prompt_messages, model_name=current_active_model)
            st.write(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()
