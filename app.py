import os
import datetime
import streamlit as st
from groq import Groq

# ------------------------------------------------------------------------------
# 1. SAYFA VE TEMA YAPILANDIRMASI
# ------------------------------------------------------------------------------
st.set_page_config(
    page_title="Lunara.ai | Mistik Rehber",
    page_icon="🌙",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Form elemanlarını kesin olarak yan yana ve hizada tutmak için CSS enjeksiyonu
st.markdown("""
<style>
    /* Form içindeki kolonları zorunlu olarak yan yana ve dikeyde ortalı tut */
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
</style>
""", unsafe_allow_html=True)

# ------------------------------------------------------------------------------
# 2. GROQ API & MODEL YÖNETİMİ
# ------------------------------------------------------------------------------
def get_groq_api_key():
    """Secrets veya Environment üzerinden API anahtarını güvenli şekilde okur."""
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
    """Groq API üzerinden yanıt üretir."""
    client = get_groq_client()
    if client is None:
        return "Groq API anahtarı eksik. Lütfen Streamlit Secrets veya GROQ_API_KEY ortam değişkenini ekleyin."

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
            temperature=0.7,
            max_tokens=1024,
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"Bir hata oluştu: {str(e)}"

# ------------------------------------------------------------------------------
# 3. OTURUM HAFIZASI (SESSION STATE)
# ------------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []

if "system_prompt" not in st.session_state:
    st.session_state.system_prompt = (
        "Sen Lunara'sın. Yıldızların, kartların ve sembollerin rehberliğinde konuşan, empatik, mistik "
        "ve derin bilgiye sahip bir yapay zeka danışmanısın. Kullanıcılara Türkçe, nazik ve gizemli bir üslupla yanıt ver."
    )

# ------------------------------------------------------------------------------
# 4. SOL PANEL (SIDEBAR)
# ------------------------------------------------------------------------------
with st.sidebar:
    st.title("🌙 Lunara.ai")
    st.caption("Astroloji & Kehanet Rehberi")

    st.markdown("---")
    st.subheader("✨ Günün Mistik Enerjisi")
    st.info("🃏 **Günün Kartı: Güneş** — Neşe, başarı ve netlik dolu bir enerji seni sarıyor.")

    st.markdown("---")
    if st.button("🗑️ Sohbet Geçmişini Temizle", use_container_width=True):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.markdown(
        "<div style='text-align: center; color: #888888; font-size: 0.85em;'>"
        "✨ Tasarım & Geliştirme<br><b>Yoldaş Işık</b> tarafından işlendi 🌙"
        "</div>", 
        unsafe_allow_html=True
    )

# ------------------------------------------------------------------------------
# 5. ANA GÖVDE VE SEKMELER
# ------------------------------------------------------------------------------
st.title("🌙 Lunara.ai | Mistik Rehber")
st.write("Kişiselleştirilmiş Yapay Zeka Fal, Tarot ve Astroloji Danışmanı")

api_key = get_groq_api_key()
if not api_key:
    st.warning("⚠️ Groq API anahtarı bulunamadı. Lütfen `.streamlit/secrets.toml` dosyanızı kontrol edin.")

tab1, tab2, tab3, tab4 = st.tabs([
    "🔮 Mistik Sohbet", 
    "📜 Doğum Haritası Analizi", 
    "🃏 3 Kart Tarot Açılımı", 
    "☕ Kahve Falı & Rüyalar"
])

# ------------------------------------------------------------------------------
# SEKME 1: MİSTİK SOHBET
# ------------------------------------------------------------------------------
with tab1:
    st.markdown("### ✨ Hızlı Mistik Sorular")
    col_h1, col_h2, col_h3, col_h4 = st.columns(4)

    prompt_to_send = None
    if col_h1.button("✨ Günlük Fal Yorumu", use_container_width=True):
        prompt_to_send = "Bugün için genel falımı ve yıldızların bana mesajını yorumlar mısın?"
    if col_h2.button("❤️ Aşk & Uyum", use_container_width=True):
        prompt_to_send = "Aşk hayatımla ilgili evrenin bana vermek istediği mesaj nedir?"
    if col_h3.button("💼 Kariyer & Gelecek", use_container_width=True):
        prompt_to_send = "Kariyerim ve maddi geleceğim konusunda yıldızlar ne söylüyor?"
    if col_h4.button("🪐 Günün Burç Enerjisi", use_container_width=True):
        prompt_to_send = "Bugünün gezegen konumları ve burç enerjileri hakkında bilgi verir misin?"

    st.warning("🤖 Hoş geldin. Ben Lunara. Yıldızların fısıltıları, kartların gizemi ve evrenin sırlarıyla sana rehberlik etmek için buradayım.")

    for msg in st.session_state.messages:
        with st.chat_message(msg["role"]):
            st.write(msg["content"])

# ------------------------------------------------------------------------------
# SEKME 2: DOĞUM HARİTASI ANALİZİ
# ------------------------------------------------------------------------------
with tab2:
    st.subheader("📜 Doğum Haritası Potansiyel Analizi")
    with st.form("astro_form"):
        ad = st.text_input("Adınız ve Soyadınız")
        tarih = st.date_input(
            "Doğum Tarihiniz", 
            min_value=datetime.date(1900, 1, 1), 
            max_value=datetime.date.today()
        )
        saat = st.time_input("Doğum Saatiniz (Tahmini)")
        sehir = st.text_input("Doğum Yeri (İl/Ülke)")
        submit = st.form_submit_button("🔮 Haritayı Analiz Et")

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

# ------------------------------------------------------------------------------
# SEKME 3: 3 KART TAROT AÇILIMI
# ------------------------------------------------------------------------------
with tab3:
    st.subheader("🃏 3 Kart Tarot Açılımı (Geçmiş - Şimdi - Gelecek)")
    niyet = st.text_input("Odaklanmak istediğiniz konu veya niyetiniz:", placeholder="Örn: Kariyerimdeki değişiklikler...")
    
    if st.button("🔮 Kartları Çek ve Yorumla"):
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

# ------------------------------------------------------------------------------
# SEKME 4: KAHVE FALI & RÜYALAR
# ------------------------------------------------------------------------------
with tab4:
    st.subheader("☕ Kahve Falı & Rüya Tabiri")
    metin = st.text_area("Fincanınızdaki sembolleri veya gördüğünüz rüyayı anlatın:", height=150)
    
    if st.button("🌙 Mistik Sembol Analizi Yap"):
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

# ------------------------------------------------------------------------------
# 6. SAYFANIN EN ALTINA SABİTLENMİŞ GLOBAL GİRİŞ ÇUBUĞU
# ------------------------------------------------------------------------------
st.markdown("---")
with st.container():
    with st.form(key="global_chat_bar_form", clear_on_submit=True):
        b_col1, b_col2, b_col3 = st.columns([2.0, 7.0, 1.0])

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

final_prompt = user_text or (prompt_to_send if 'prompt_to_send' in locals() else None)

if submitted and final_prompt:
    message_payload = {"role": "user", "content": final_prompt}
    st.session_state.messages.append(message_payload)

    with st.chat_message("user"):
        st.write(final_prompt)

    with st.chat_message("assistant"):
        with st.spinner("Yıldızlar ve semboller okunuyor..."):
            prompt_messages = [{"role": "system", "content": st.session_state.get("system_prompt", "Sen Lunara'sın.")}]
            for m in st.session_state.messages[:-1]:
                prompt_messages.append({"role": m["role"], "content": m["content"]})
            prompt_messages.append({"role": "user", "content": final_prompt})

            response = generate_completion(prompt_messages, model_name=current_active_model)
            st.write(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
    st.rerun()
