import streamlit as st
import google.generativeai as genai
from audio_recorder_streamlit import audio_recorder
import edge_tts
import asyncio
import gspread
from google.oauth2.service_account import Credentials
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import json
import tempfile
import os

# 1. PROFESYONEL ARAYÜZ VE CSS AYARLARI
st.set_page_config(page_title="PACE Pro", layout="wide")

st.markdown("""
    <style>
    /* Light Lacivert - Kırmızı Gradient Arka Plan */
    [data-testid="stAppViewContainer"] { 
        background: linear-gradient(135deg, #f0f4f8 0%, fcebeb 100%) !important; 
    }
    [data-testid="stHeader"] {
        background: transparent !important
        }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background-color: #001F5B; /* Kurumsal Lacivert */
        color: white;
        font-weight: bold;
        border: none;
    }
    .stButton>button:hover { background-color: #D91A23; /* Kurumsal Kırmızı */ color: white; }
    .reportview-container .main .block-container { padding-top: 2rem; }
    div[data-baseweb="tab-list"] { gap: 20px; }
    div[data-baseweb="tab"] {
        padding: 10px 20px;
        background-color: rgba(255, 255, 255, 0.6);
        border-radius: 10px 10px 0 0;
        border: 1px solid rgba(0, 31, 91, 0.1);
    }
    div[aria-selected="true"] { background-color: #001F5B !important; color: white !important; }
    </style>
    """, unsafe_allow_html=True)

# 2. GÜVENLİK VE BAĞLANTILAR
def check_password():
    if "password_correct" not in st.session_state:
        st.session_state["password_correct"] = False
    
    if st.session_state["password_correct"]:
        return True

    with st.sidebar:
        st.title("Güvenli Giriş")
        pwd = st.text_input("Şifre:", type="password")
        if st.button("Giriş Yap"):
            if pwd == "Florini2026_Pro!":
                st.session_state["password_correct"] = True
                st.rerun()
            else:
                st.error("Hatalı şifre!")
    return False

if not check_password():
    st.stop()

# --- SOL PANEL (SÜREKLİ GÖRÜNEN MENÜ VE ÇIKIŞ) ---
with st.sidebar:
    st.title("Profil")
    st.write("Sisteme başarıyla giriş yapıldı.")
    st.divider()
    if st.button("Çıkış Yap"):
        st.session_state["password_correct"] = False
        st.rerun()

# API Ayarları
genai.configure(api_key=st.secrets["GOOGLE_API_KEY"])
model = genai.GenerativeModel('models/gemini-2.5-flash')

# Google Sheets Bağlantısı
scopes = ["https://www.googleapis.com/auth/spreadsheets"]
creds_dict = json.loads(st.secrets["google_json"])
creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
client = gspread.authorize(creds)
# ID Yöntemi ile bağlantı (Daha güvenli)
sheet = client.open_by_key("1rcUYWr1LTRWkgEJneMZCJOWBsldEa5tmViUdSlCdkBU").sheet1 

def veri_getir():
    try:
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

df_ziyaret = veri_getir()

# 3. ANA PANEL SEKMELERİ
st.title("PACE Co-Pilot")
tabs = st.tabs(["Kayıt", "Geçmiş", "Dinamik Roleplay", "Literatür (PDF)", "Insights", "Co-Pilot"])

# --- TAB 1: KVKK UYUMLU KAYIT ---
with tabs[0]:
    st.subheader("Yeni Ziyaret Kaydı")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        st.info("Doktor ismini tam söyleseniz bile sistem PACE kuralları gereği otomatik olarak baş harflere çevirecektir.")
        ses_verisi = audio_recorder(text="Kaydı Başlat", recording_color="#D91A23")
    
    if ses_verisi:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_audio:
            tmp_audio.write(ses_verisi)
            tmp_path = tmp_audio.name
        
        with st.spinner("PACE Yapay Zeka analiz ediyor..."):
            audio_file = genai.upload_file(tmp_path)
            prompt = """
            Ses kaydını analiz et ve şu JSON formatında döndür. 
            KRİTİK KVKK KURALI: Hekim ismini sadece baş harflerle yaz (Örn: Ahmet Yılmaz -> A. Y.). 
            Hastane ve Bölge bilgisini konuşma içinden yakala.
            {
                "Hekim": "Baş harfler", "Hastane": "...",
                "İlaç": "...", "Özet": "...", "İtiraz": "...", "Aksiyon": "..."
            }
            """
            response = model.generate_content([prompt, audio_file])
            try:
                res_json = json.loads(response.text.replace("```json", "").replace("```", ""))
                st.session_state["current_record"] = res_json
                st.write("### Önizleme")
                st.table([res_json])
                
                if st.button("Veritabanına İşle"):
                    tarih = datetime.now().strftime("%d-%m-%Y %H:%M")
                    yeni_satir = [tarih, res_json["Hekim"], res_json["Hastane"], res_json["İlaç"], res_json["Özet"], res_json["İtiraz"], res_json["Aksiyon"]]
                    sheet.append_row(yeni_satir)
                    st.success("Kayıt başarıyla tamamlandı.")
            except:
                st.error("Analiz başarısız oldu, lütfen tekrar deneyin.")

# --- TAB 2: GEÇMİŞ VE AKSİYON PLANLAMA ---
with tabs[1]:
    st.subheader("Ziyaret Geçmişi")
    if not df_ziyaret.empty:
        # 1. Dümdüz Sheet Görünümü
        st.dataframe(df_ziyaret, use_container_width=True)
       
        st.divider()
       
        # 2. Şık Yapılacaklar Listesi (To-Do)
        st.subheader("📋 Yaklaşan Aksiyonlar ve Yapılacaklar")
        st.caption("Geçmiş ziyaretlerde planlanan son aksiyonlar:")
       
        if "Aksiyon" in df_ziyaret.columns:
            # Boş olanları ve "Yok" yazanları filtreleyip son 4 aksiyonu çekiyoruz
            gecerli_aks = df_ziyaret[
                (df_ziyaret["Aksiyon"].notna()) &
                (df_ziyaret["Aksiyon"].astype(str).str.strip() != "") &
                (df_ziyaret["Aksiyon"].astype(str).str.lower() != "yok")
            ]
            aksiyonlar = gecerli_aks["Aksiyon"].tail(4).tolist()
           
            if aksiyonlar:
                for i, aks in enumerate(aksiyonlar):
                    st.checkbox(f"📌 **Görev:** {aks}", key=f"todo_{i}")
            else:
                st.info("Şu an için planlanmış bir aksiyon bulunmuyor.")
        else:
            st.warning("Aksiyon sütunu bulunamadı.")
    else:
        st.info("Veri bulunamadı.")

# --- TAB 3: DİNAMİK ROLEPLAY ---
with tabs[2]:
    st.subheader("Saha Verisiyle Eğitilmiş Sesli Roleplay")
    if not df_ziyaret.empty:
        ilac_listesi = df_ziyaret["İlaç"].unique().tolist()
        secilen_ilac = st.selectbox("Antrenman yapılacak ilacı seçin:", ilac_listesi)
       
        itirazlar = df_ziyaret[df_ziyaret["İlaç"] == secilen_ilac]["İtiraz"].tolist()
        itiraz_metni = ", ".join([str(i) for i in itirazlar if str(i).strip().lower() != "yok"])

        if "roleplay_chat" not in st.session_state:
            st.session_state.roleplay_chat = []

        # Geçmiş sohbeti ekrana bas ve sadece son mesaja autoplay ver
        for idx, m in enumerate(st.session_state.roleplay_chat):
            with st.chat_message(m["role"]):
                st.markdown(m["content"])
                if m["role"] == "assistant" and "audio" in m:
                    # Yalnızca dizideki en son ses dosyası otomatik oynatılır (Döngü önlemi)
                    is_last = (idx == len(st.session_state.roleplay_chat) - 1)
                    st.audio(m["audio"], format="audio/mp3", autoplay=is_last)

        st.info("🎙️ Aşağıdaki mikrofona tıklayarak hekime doğrudan seslenin:")
        sesli_girdi = audio_recorder(text="Konuşmak için tıkla", recording_color="#D91A23", key="roleplay_audio")
       
        if sesli_girdi:
            # Sonsuz döngüyü kıran kilit sistem (Hash kontrolü)
            audio_hash = hashlib.md5(sesli_girdi).hexdigest()
            if "last_processed_audio" not in st.session_state or st.session_state.last_processed_audio != audio_hash:
                st.session_state.last_processed_audio = audio_hash
               
                with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_user:
                    tmp_user.write(sesli_girdi)
                    tmp_user_path = tmp_user.name
               
                with st.spinner("Hekim (Yapay Zeka) dinliyor ve düşünüyor..."):
                    user_audio_file = genai.upload_file(tmp_user_path)
                   
                    json_prompt = f"""
                    Sen şüpheci bir hekimsin. Sana {secilen_ilac} satılmaya çalışılıyor.
                    Şu ana kadarki gerçek saha itirazların şunlar: {itiraz_metni}.
                    Ekteki ses kaydı mümessilin sana kurduğu cümledir. Ses kaydını dinle ve şu JSON formatında dön:
                    {{
                        "user_transcript": "Mümessilin seste söylediği cümlenin tam metni",
                        "doctor_response": "Hekim olarak mümessile vereceğin kısa, şüpheci ve zorlayıcı yanıt (Maks. 2 cümle)"
                    }}
                    Sadece JSON döndür.
                    """
                   
                    try:
                        res_obj = model.generate_content([json_prompt, user_audio_file])
                        json_data = json.loads(res_obj.text.replace("```json", "").replace("```", "").strip())
                        user_text = json_data.get("user_transcript", "🎤 [Ses Anlaşılamadı]")
                        ai_text = json_data.get("doctor_response", "Peki, bu konuda daha fazla veriye ihtiyacım var.")
                    except:
                        user_text = "🎤 [Sesli İfade]"
                        ai_text = "Şu an bu ilacı reçetelemek için yeterince ikna olmadım, klinik kanıtları görmeliyim."
                   
                    # Edge-TTS ile Doktorun Sesini Oluştur (Senkron Çalışma)
                    def generate_tts(text):
                        communicate = edge_tts.Communicate(text, "tr-TR-AhmetNeural") # Ahmet sesi şüpheci doktor için idealdir
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as t_file:
                            asyncio.run(communicate.save(t_file.name))
                            with open(t_file.name, "rb") as f:
                                return f.read()
                   
                    ai_audio_bytes = generate_tts(ai_text)
                   
                    # Konuşmaları ve Ses verisini state'e ekle
                    st.session_state.roleplay_chat.append({"role": "user", "content": user_text})
                    st.session_state.roleplay_chat.append({"role": "assistant", "content": ai_text, "audio": ai_audio_bytes})
                   
                    # Sayfayı yenile (Yeni mesajlar görünür ve sadece son eklenen ses oynatılır)
                    st.rerun()
    else:
        st.warning("Roleplay için önce kayıt oluşturmalısınız.")

# --- TAB 4: LİTERATÜR (PDF ANALİZ) ---
with tabs[3]:
    st.subheader("PDF Makale Analizi")
    yuklenen_dosya = st.file_uploader("Klinik çalışma veya broşür yükleyin (PDF):", type="pdf")
    
    if yuklenen_dosya:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
            tmp_pdf.write(yuklenen_dosya.read())
            tmp_path_pdf = tmp_pdf.name
        
        if st.button("Makaleyi Analiz Et"):
            with st.spinner("PDF okunuyor..."):
                pdf_file = genai.upload_file(tmp_path_pdf)
                prompt_pdf = "Bu klinik çalışmayı özetle. Rakip ilaçlara göre üstünlükleri ve mümessilin kullanabileceği 3 ana argümanı madde madde yaz."
                res_pdf = model.generate_content([prompt_pdf, pdf_file])
                st.markdown(res_pdf.text)

# --- TAB 5: INSIGHTS & TAHMİN (PLOTLY) ---
with tabs[4]:
    st.subheader("Satış Tahmini ve Trendler")
    if not df_ziyaret.empty:
        col_g1, col_g2 = st.columns(2)
        
        with col_g1:
            mevcut_ziyaret = len(df_ziyaret)
            hedef_ziyaret = 100 
            yüzde = (mevcut_ziyaret / hedef_ziyaret) * 100
            
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = yüzde,
                title = {'text': "Aylık Hedef Gerçekleşme (%)"},
                gauge = {'axis': {'range': [None, 100]}, 'bar': {'color': "#001F5B"}}
            ))
            st.plotly_chart(fig)
            
        with col_g2:
            st.write("**İlaç Bazlı Ziyaret Dağılımı**")
            st.bar_chart(df_ziyaret["İlaç"].value_counts())
            
        st.divider()
        st.write("### PACE Stratejik Tahmin")
        if st.button("Yapay Zeka ile Analiz Et"):
            with st.spinner("Strateji çıkarılıyor..."):
                tahmin_prompt = f"Şu ziyaret verilerine göre: {df_ziyaret.to_string()}. Gelecek ay için satış tahmini yap ve hangi bölgeye odaklanılması gerektiğini söyle."
                st.write(model.generate_content(tahmin_prompt).text)

# --- TAB 6: CO-PILOT CHATBOT ---
with tabs[5]:
    st.subheader("PACE Akıllı Co-Pilot Chat")
    if "messages" not in st.session_state:
        st.session_state.messages = []

    for m in st.session_state.messages:
        with st.chat_message(m["role"]): st.markdown(m["content"])

    if p := st.chat_input("Nasıl yardımcı olabilirim?"):
        st.session_state.messages.append({"role": "user", "content": p})
        with st.chat_message("user"): st.markdown(p)
        
        with st.chat_message("assistant"):
            if "mail" in p.lower() or "taslak" in p.lower():
                res = model.generate_content(f"Şu istek için profesyonel bir mail taslağı oluştur: {p}").text
                st.info(res)
                if st.button("Onayla ve Gönder"): st.success("Mail iletildi.")
            else:
                res = model.generate_content(p).text
                st.markdown(res)
            st.session_state.messages.append({"role": "assistant", "content": res})
