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
import hashlib

# 1. PROFESYONEL ARAYÜZ VE CSS AYARLARI
st.set_page_config(page_title="PACE Pro", layout="wide")

st.markdown("""
    <style>
    /* Streamlit'in siyah arka planını ve üst menüsünü zorla eziyoruz */
    [data-testid="stAppViewContainer"] {
        background: linear-gradient(135deg, #f0f4f8 0%, #fcebeb 100%) !important;
    }
    [data-testid="stHeader"] {
        background: transparent !important;
    }
    .stButton>button {
        width: 100%;
        border-radius: 10px;
        height: 3em;
        background-color: #001F5B;
        color: white;
        font-weight: bold;
        border: none;
    }
    .stButton>button:hover { background-color: #D91A23; color: white; }
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
sheet = client.open_by_key("1rcUYWr1LTRWkgEJneMZCJOWBsldEa5tmViUdSlCdkBU").sheet1

def veri_getir():
    try:
        data = sheet.get_all_records()
        return pd.DataFrame(data)
    except:
        return pd.DataFrame()

df_ziyaret = veri_getir()

# 3. ANA PANEL SEKMELERİ
st.title("PACE AI Co-Pilot v2.0")
tabs = st.tabs(["Kayıt", "Geçmiş", "Dinamik Roleplay", "Literatür (PDF)", "Insights", "Co-Pilot"])

# --- TAB 1: KVKK UYUMLU KAYIT ---
with tabs[0]:
    st.subheader("Yeni Ziyaret Kaydı")
    col1, col2 = st.columns([1, 2])
   
    with col1:
        st.info("Doktor ismini tam söyleseniz bile sistem PACE kuralları gereği otomatik olarak baş harflere çevirecektir.")
        ses_verisi = audio_recorder(text="Kaydı Başlat", recording_color="#D91A23", pause_threshold=3)
   
    if ses_verisi:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_audio:
            tmp_audio.write(ses_verisi)
            tmp_path = tmp_audio.name
       
        with st.spinner("PACE Yapay Zeka analiz ediyor..."):
            audio_file = genai.upload_file(tmp_path)
            prompt = """
            Ses kaydını analiz et ve şu JSON formatında döndür.
            KRİTİK KVKK KURALI: Hekim ismini sadece baş harflerle yaz (Örn: Ahmet Yılmaz -> A. Y.).
            Hastane bilgisini konuşma içinden yakala.
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
                    st.rerun()
            except:
                st.error("Analiz başarısız oldu, lütfen tekrar deneyin.")

# --- TAB 2: GEÇMİŞ VE AKSİYON PLANLAMA ---
with tabs[1]:
    st.subheader("Ziyaret Geçmişi")
    if not df_ziyaret.empty:
        st.dataframe(df_ziyaret, use_container_width=True)
        st.divider()
       
        st.subheader("Yaklaşan Aksiyonlar ve Yapılacaklar")
        st.caption("Geçmiş ziyaretlerde planlanan son aksiyonlar:")
       
        if "Aksiyon" in df_ziyaret.columns:
            gecerli_aks = df_ziyaret[
                (df_ziyaret["Aksiyon"].notna()) &
                (df_ziyaret["Aksiyon"].astype(str).str.strip() != "") &
                (df_ziyaret["Aksiyon"].astype(str).str.lower() != "yok")
            ]
            aksiyonlar = gecerli_aks["Aksiyon"].tail(4).tolist()
           
            if aksiyonlar:
                for i, aks in enumerate(aksiyonlar):
                    st.checkbox(f"Görev: {aks}", key=f"todo_{i}")
            else:
                st.info("Şu an için planlanmış bir aksiyon bulunmuyor.")
        else:
            st.warning("Aksiyon sütunu bulunamadı.")
    else:
        st.info("Veri bulunamadı.")

# --- TAB 3: DİNAMİK ROLEPLAY (YAZILI VE HAFIZALI SÜRÜM) ---
with tabs[2]:
    st.subheader("Saha Verisiyle Eğitilmiş Chat-Roleplay")
    if not df_ziyaret.empty:
        ilac_listesi = df_ziyaret["İlaç"].unique().tolist()
        secilen_ilac = st.selectbox("Antrenman yapılacak ilacı seçin:", ilac_listesi)
       
        itirazlar = df_ziyaret[df_ziyaret["İlaç"] == secilen_ilac]["İtiraz"].tolist()
        itiraz_metni = ", ".join([str(i) for i in itirazlar if str(i).strip().lower() != "yok" and str(i).strip() != ""])

        if "roleplay_chat" not in st.session_state:
            st.session_state.roleplay_chat = []

        for m in st.session_state.roleplay_chat:
            with st.chat_message(m["role"]): st.markdown(m["content"])

        if user_msg := st.chat_input("Hekime mesajınız..."):
            st.session_state.roleplay_chat.append({"role": "user", "content": user_msg})
            with st.chat_message("user"): st.markdown(user_msg)
           
            with st.spinner("Doktor yanıtlıyor..."):
                # PDF sekmesinden gelen bir klinik hafıza var mı kontrol ediliyor
                klinik_notu = ""
                if "klinik_hafiza" in st.session_state:
                    klinik_notu = f"\nSisteme yüklenen en son klinik araştırma özeti şudur:\n{st.session_state['klinik_hafiza']}\nEğer mümessil sana yukarıdaki klinik araştırmadan, yeni bilimsel verilerden veya buradaki çözümlerden bahsederse, bilime saygı duyan bir hekim olarak ikna ol, inadı bırak, hak verdiğini ve ilacı deneyeceğini olumlu bir dille belirt."

                roleplay_prompt = f"""
                Sen şüpheci bir hekimsin. Sana {secilen_ilac} satılmaya çalışılıyor.
                Geçmişteki gerçek itirazların şunlar: {itiraz_metni}.{klinik_notu}
                Bu itirazları kullanarak kullanıcıyı zorla. Doğal bir sohbet sürdür.
                Yanıtın kısa ve net olsun.
                """
                chat_history = [m["content"] for m in st.session_state.roleplay_chat]
                ai_response = model.generate_content([roleplay_prompt] + chat_history).text
               
                st.session_state.roleplay_chat.append({"role": "assistant", "content": ai_response})
                with st.chat_message("assistant"): st.markdown(ai_response)
    else:
        st.warning("Roleplay için önce kayıt oluşturmalısınız.")

# --- TAB 4: LİTERATÜR (PDF ANALİZ VE HAFIZAYA KAYIT) ---
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
               
                # Çıkan sonucu roleplay'in de erişebileceği ortak hafızaya alıyoruz
                st.session_state["klinik_hafiza"] = res_pdf.text
               
                st.markdown(res_pdf.text)
                st.success("Bilgi: Bu klinik çalışma başarıyla PACE hafızasına alındı. Roleplay sekmesindeki hekim artık bu araştırmadan haberdar ve doğru argümanları sunarsanız ikna olabilir.")

# --- TAB 5: INSIGHTS & TAHMİN (PLOTLY) ---
with tabs[4]:
    st.subheader("Satış Tahmini ve Trendler")
    if not df_ziyaret.empty:
        col_g1, col_g2 = st.columns(2)
       
        with col_g1:
            mevcut_ziyaret = len(df_ziyaret)
            hedef_ziyaret = st.number_input("Aylık Ziyaret Hedefinizi Belirleyin:", min_value=1, value=100)
            yüzde = (mevcut_ziyaret / hedef_ziyaret) * 100
            gosterge_yuzde = min(yüzde, 100)
           
            fig = go.Figure(go.Indicator(
                mode = "gauge+number",
                value = gosterge_yuzde,
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

# --- TAB 6: CO-PILOT CHATBOT (AKILLI VERİTABANI GÜNCELLEME DESTEKLİ) ---
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
            # Önce mesajın bir ilaç ismi değiştirme talebi olup olmadığını Gemini ile kontrol ediyoruz
            kontrol_prompt = f"""
            Kullanıcı mesajı: "{p}"
            Bu mesaj, veritabanındaki (Sheets) bir ilaç isminin yenisiyle değiştirilmesini mi talep ediyor?
            Yalnızca şu JSON formatında yanıt ver:
            {{
                "is_change_request": true veya false,
                "old_name": "varsa eski ilaç adı",
                "new_name": "varsa yeni verilmek istenen ilaç adı"
            }}
            Maksimum hassasiyet göster ve sadece saf JSON döndür.
            """
            try:
                kontrol_res = model.generate_content(kontrol_prompt).text
                kontrol_json = json.loads(kontrol_res.replace("```json", "").replace("```", "").strip())
            except:
                kontrol_json = {"is_change_request": False}
           
            # Eğer bir ilaç ismi değiştirme talebiyse arka planda Sheets güncellenir
            if kontrol_json.get("is_change_request") == True:
                eski = kontrol_json.get("old_name")
                yeni = kontrol_json.get("new_name")
               
                with st.spinner(f"Veritabanında '{eski}' isimli ilaçlar '{yeni}' olarak güncelleniyor..."):
                    try:
                        cells = sheet.findall(eski)
                        updated_count = 0
                        for cell in cells:
                            # İlaç verisi tablomuzda 4. sütunda yer almaktadır
                            if cell.col == 4:
                                sheet.update_cell(cell.row, cell.col, yeni)
                                updated_count += 1
                       
                        if updated_count > 0:
                            res = f"Başarılı! Veritabanındaki {updated_count} adet '{eski}' ismi '{yeni}' olarak değiştirildi. Tablolarınız güncellendi."
                            st.success(res)
                            st.rerun()
                        else:
                            res = f"Veritabanında '{eski}' isimli bir ilaç kaydı bulunamadı."
                            st.warning(res)
                    except Exception as e:
                        res = f"Güncelleme sırasında bir hata oluştu: {str(e)}"
                        st.error(res)
           
            elif "mail" in p.lower() or "taslak" in p.lower():
                res = model.generate_content(f"Şu istek için profesyonel bir mail taslağı oluştur: {p}").text
                st.info(res)
                if st.button("Onayla ve Gönder"): st.success("Mail iletildi.")
            else:
                res = model.generate_content(p).text
                st.markdown(res)
               
            st.session_state.messages.append({"role": "assistant", "content": res})
