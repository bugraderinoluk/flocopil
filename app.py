import streamlit as st
import google.generativeai as genai
from audio_recorder_streamlit import audio_recorder
import edge_tts
import asyncio
import json
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime, timedelta
from collections import defaultdict
import pandas as pd

# --- SAYFA AYARLARI ---
st.set_page_config(page_title="Florini Co-Pilot", page_icon="💊", layout="centered")

# --- GÜVENLİK ---
if 'giris_basarili' not in st.session_state:
    st.session_state['giris_basarili'] = False

def sifre_kontrol():
    if st.session_state['sifre_kutusu'] == "Florini2026_Pro!":
        st.session_state['giris_basarili'] = True
    else:
        st.error("❌ Hatalı şifre. Lütfen yetkili erişim şifresini giriniz.")

if not st.session_state['giris_basarili']:
    st.markdown("<h1 style='text-align: center; color: #1E1E1E;'>🔒 Florini Sistemine Giriş</h1>", unsafe_allow_html=True)
    st.text_input("Erişim Şifresi:", type="password", key="sifre_kutusu", on_change=sifre_kontrol)
    st.button("Giriş Yap", on_click=sifre_kontrol, use_container_width=True)
    st.stop()

# --- CSS (KIRMIZI-MAVİ GEÇİŞ) ---
st.markdown("""
    <style>
        .stApp { background: linear-gradient(135deg, #8B0000 0%, #00008B 100%) !important; }
        h1, h2, h3, h4, h5, h6, p, span, label, li, div[data-testid="stMarkdownContainer"] { color: #FAFAFA !important; }
        div[data-testid="stExpander"] { background-color: rgba(255, 255, 255, 0.1) !important; border: 1px solid rgba(255, 255, 255, 0.3) !important; border-radius: 10px; backdrop-filter: blur(10px); }
        div[data-testid="stExpander"] summary p { font-weight: bold; }
        div[data-testid="stExpander"] summary svg { fill: #FAFAFA !important; }
        button[data-baseweb="tab"] { background-color: rgba(255,255,255,0.1) !important; color: #FAFAFA !important; }
        button[aria-selected="true"] { background-color: rgba(255,255,255,0.3) !important; font-weight: bold; }
        .stTextInput>div>div>input, .stTextArea>div>div>textarea { background-color: rgba(255,255,255,0.9) !important; color: #000 !important; }
    </style>
""", unsafe_allow_html=True)

# --- API VE EXCEL ---
st.title("🎙️ Florini Co-Pilot")
api_key = st.secrets["GOOGLE_API_KEY"]
google_json_str = st.secrets["google_json"]
genai.configure(api_key=api_key.strip())
model = genai.GenerativeModel('models/gemini-2.5-flash')

@st.cache_resource
def google_sheets_baglan(json_str):
    creds_dict = json.loads(json_str)
    scopes = ["https://www.googleapis.com/auth/spreadsheets", "https://www.googleapis.com/auth/drive"]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    gc = gspread.authorize(creds)
    dosya = gc.open("Florini_Raporlar")
    return dosya

@st.cache_data(ttl=600)
def verileri_getir(json_str):
    dosya = google_sheets_baglan(json_str)
    ziyaretler = dosya.sheet1.get_all_records()
    try:
        satislar = dosya.worksheet("Satislar").get_all_records()
    except:
        satislar = [] # Eğer sayfa henüz açılmadıysa çökmesin
    return ziyaretler, satislar, dosya.url

ziyaret_verisi, satis_verisi, excel_url = verileri_getir(google_json_str)
dosya = google_sheets_baglan(google_json_str)
tablo = dosya.sheet1

# --- SES MOTORU (ERKEK/KADIN) ---
async def ses_olustur(metin, dosya_adi, cinsiyet="kadin"):
    ses_kodu = "tr-TR-EmelNeural" if cinsiyet == "kadin" else "tr-TR-AhmetNeural"
    communicate = edge_tts.Communicate(metin, ses_kodu, rate="+0%", pitch="+0Hz")
    await communicate.save(dosya_adi)

with st.sidebar:
    st.title("⚙️ Ayarlar")
    st.link_button("Excel Dosyasını Aç ↗", excel_url, use_container_width=True)
    if st.button("Çıkış Yap 🚪", use_container_width=True):
        st.session_state['giris_basarili'] = False
        st.rerun()

tab1, tab2, tab3, tab4, tab5 = st.tabs(["🎙️ Kayıt", "📅 Geçmiş", "🧬 Literatür", "🎭 Roleplay", "📊 Satış & Hedef"])

# SEKME 1: YENİ KAYIT (Aynı Kaldı)
with tab1:
    st.info("📌 İlaçlar: Dolorix, Flexium, Cardioxen")
    ses_verisi = audio_recorder(text="Kayıt İçin Tıkla", recording_color="#e81e4d", neutral_color="#ffffff", icon_size="2x")
    if ses_verisi:
        with st.spinner("İşleniyor..."):
            audio_part = {"mime_type": "audio/wav", "data": ses_verisi}
            sistem_emri = """Sen Florini asistanısın. İlaçlar: Dolorix, Flexium, Cardioxen. Rapor çıkar ve sesli onay ver. {"raporlar": [{"hekim": "Ad", "ilac": "İlaç", "ozet": "Özet", "itiraz": "İtiraz", "aksiyon": "Adım"}], "sesli_onay": "Görüşme kaydedildi."}"""
            cevap = model.generate_content([sistem_emri, audio_part])
            veri = json.loads(cevap.text.replace('```json', '').replace('```', '').strip())
            for r in veri.get("raporlar", []):
                tablo.append_row([datetime.now().strftime("%d-%m-%Y %H:%M"), r.get("hekim", ""), r.get("ilac", ""), r.get("ozet", ""), r.get("itiraz", ""), r.get("aksiyon", "")])
            verileri_getir.clear()
            st.success("Kaydedildi.")
            asyncio.run(ses_olustur(veri.get("sesli_onay", "Kayıt tamam."), "onay.mp3", "kadin"))
            st.audio("onay.mp3", format="audio/mp3", autoplay=True)

# SEKME 2: GEÇMİŞ VE ÖZETLER
with tab2:
    st.markdown("### 📅 Veritabanı Geçmişi")
    if not ziyaret_verisi:
        st.info("Henüz kayıt bulunmamaktadır.")
    else:
        gunluk_kayitlar = defaultdict(list)
        for satir in ziyaret_verisi:
            tarih_saat = str(satir.get("Tarih", ""))
            if tarih_saat:
                gun = tarih_saat.split(" ")[0]
                gunluk_kayitlar[gun].append(satir)
        
        col_dun, col_yarin = st.columns(2)
        dunun_tarihi = (datetime.now() - timedelta(1)).strftime("%d-%m-%Y")
        
        with col_dun:
            if st.button("🔊 Dünün Özeti"):
                dun_verisi = gunluk_kayitlar.get(dunun_tarihi, [])
                if not dun_verisi:
                    st.warning("Düne ait kayıt bulunamadı.")
                else:
                    with st.spinner("Brifing hazırlanıyor..."):
                        prompt = f"""Şu veri dünkü ziyaretlerim: {str(dun_verisi)}. 
                        Bana detaylı ve profesyonel bir brifing ver. 
                        1. Kısaltmaları ASLA kullanma! 'Uzm. Dr.' yerine 'Uzman Doktor' yaz.
                        2. Unvanlardan sonra ASLA nokta (.) koyma.
                        3. İlaç isimlerini fonetik yaz (Doloriks, Fleksiyum, Kardiyoksen).
                        """
                        ozet_cevap = model.generate_content(prompt).text.strip()
                        asyncio.run(ses_olustur(ozet_cevap, "dun_ozet.mp3", "kadin"))
                        st.audio("dun_ozet.mp3", format="audio/mp3", autoplay=True)
                    
        with col_yarin:
            if st.button("📋 Yarının Planı"):
                with st.spinner("İş planı çıkarılıyor..."):
                    prompt = f"""Şu veriler tüm kayıtlarım: {str(ziyaret_verisi)}. 
                    Sadece 'Aksiyon' kısımlarına bak. Yarın yapmam gereken işleri bul.
                    Bana İKİ parçadan oluşan bir yanıt ver.
                    Parça 1 (Görsel Liste): Madde madde, çok net bir görsel liste hazırla.
                    Parça 2 (Sesli Brifing): 'SESLİ_METİN:' kelimesinden sonra bu listenin düz metin olarak halini yaz.
                    """
                    cevap = model.generate_content(prompt).text.strip()
                    
                    if "SESLİ_METİN:" in cevap:
                        gorsel_liste, sesli_metin = cevap.split("SESLİ_METİN:")
                    else:
                        gorsel_liste = cevap
                        sesli_metin = cevap
                    
                    st.markdown("### 📋 Yarının İş Listesi")
                    st.info(gorsel_liste.strip())
                    
                    asyncio.run(ses_olustur(sesli_metin.strip(), "yarin_plan.mp3", "kadin"))
                    st.audio("yarin_plan.mp3", format="audio/mp3", autoplay=True)

        for gun in sorted(gunluk_kayitlar.keys(), key=lambda d: datetime.strptime(d, "%d-%m-%Y"), reverse=True):
            with st.expander(f"📅 {gun} ({len(gunluk_kayitlar[gun])} Kayıt)"):
                for k in gunluk_kayitlar[gun]:
                    saat = k['Tarih'].split(' ')[1] if ' ' in k['Tarih'] else ""
                    st.markdown(f"**{saat} - {k.get('Hekim', '')} ({k.get('İlaç', '')})**")
                    st.write(f"- **Özet:** {k.get('Özet', '')}\n- **İtiraz:** {k.get('İtiraz', '')}\n- **Aksiyon:** {k.get('Aksiyon', '')}")
                    st.divider()
# SEKME 3: LİTERATÜR
with tab3:
    arama_sorgusu = st.text_area("İtiraz / Araştırma Konusu:", placeholder="Örn: Diyabetik hastalarda böbreği yorar mı?")
    if st.button("Tıbbi Literatür Bul"):
        with st.spinner("PubMed ve The Lancet taranıyor..."):
            prompt = f"Şu konuyu GERÇEK LİTERATÜR (PubMed) ile cevapla. Referans ver. Mümessilin söyleyeceği kısa bir yanıt yaz: {arama_sorgusu}"
            st.markdown(model.generate_content(prompt).text)

# SEKME 4: SESLİ DOKTOR ROLEPLAY SİMÜLATÖRÜ
with tab4:
    st.markdown("### 🗣️ Canlı Simülasyon (Roleplay)")
    if ziyaret_verisi:
        hekimler = list(set([s["Hekim"] for s in ziyaret_verisi if s.get("Hekim")]))
        secilen_hekim = st.selectbox("Simüle Edilecek Hekim:", ["Seçiniz..."] + hekimler)
        
        if secilen_hekim != "Seçiniz...":
            # Cinsiyet Tahmini
            kadin_isimleri = ["ayşe", "fatma", "canan", "elif", "zeynep", "hanım", "dr. ayşe", "dr. canan"]
            is_kadin = any(isim in secilen_hekim.lower() for isim in kadin_isimleri)
            cinsiyet_kodu = "kadin" if is_kadin else "erkek"
            
            st.info(f"🎭 **{secilen_hekim}** karakteri yüklendi. Mikrofona konuşarak simülasyonu başlatın.")
            rp_ses = audio_recorder(text="Doktora Konuş", key="rp_recorder")
            
            if rp_ses:
                with st.spinner("Doktor düşünüyor..."):
                    hekim_gecmisi = [s for s in ziyaret_verisi if s["Hekim"] == secilen_hekim]
                    rp_prompt = f"""
                    Senin adın {secilen_hekim}. Sen bir doktorsun. Karşında Florini firmasının mümessili var.
                    İşte senin bu mümessille geçmişte konuştuğun konular ve itirazların: {hekim_gecmisi}.
                    Senin psikolojik profilin: Bu geçmişe bakarak itiraz eden, meşgul, bazen huysuz ama mantıklı bir doktor ol.
                    
                    GÖREV: Sana birazdan gönderilen sesi dinle ve bana DOKTOR KARAKTERİNDEN ÇIKMADAN SADECE 1-2 CÜMLELİK DOĞAL BİR CEVAP VER. Merhaba falan deme, direkt konuya/itiraza gir.
                    """
                    audio_part = {"mime_type": "audio/wav", "data": rp_ses}
                    doktorun_cevabi = model.generate_content([rp_prompt, audio_part]).text.strip()
                    
                    st.chat_message("user").write("🎙️ *Sizin ses kaydınız*")
                    st.chat_message("assistant").write(f"👨‍⚕️ **{secilen_hekim}:** {doktorun_cevabi}")
                    
                    # Sesi oluştur ve çal
                    asyncio.run(ses_olustur(doktorun_cevabi, "doktor_sesi.mp3", cinsiyet_kodu))
                    st.audio("doktor_sesi.mp3", format="audio/mp3", autoplay=True)
    else:
        st.warning("Veri yok.")

# SEKME 5: SATIŞ VE HEDEFLER
with tab5:
    st.markdown("### 📊 Ziyaret ve Satış Performansı")
    if satis_verisi:
        df_satis = pd.DataFrame(satis_verisi)
        # Verileri sayısala çevir
        df_satis['Satilan_Kutu'] = pd.to_numeric(df_satis['Satilan_Kutu'], errors='coerce').fillna(0)
        df_satis['Hedef_Kutu'] = pd.to_numeric(df_satis['Hedef_Kutu'], errors='coerce').fillna(0)
        
        toplam_satis = df_satis['Satilan_Kutu'].sum()
        toplam_hedef = df_satis['Hedef_Kutu'].sum()
        
        col1, col2, col3 = st.columns(3)
        col1.metric("Toplam Kutu Hedefi", f"{toplam_hedef}")
        col2.metric("Gerçekleşen Satış", f"{toplam_satis}", f"{toplam_satis - toplam_hedef} Fark")
        col3.metric("Hedef Ulaşım %", f"%{int((toplam_satis/toplam_hedef)*100)}" if toplam_hedef else "%0")
        
        st.divider()
        st.markdown("#### 📈 İlaç Bazlı Satış Performansı")
        ilac_bazli = df_satis.groupby('İlaç')[['Satilan_Kutu', 'Hedef_Kutu']].sum()
        st.bar_chart(ilac_bazli)
    else:

        st.warning("Henüz Excel'de 'Satislar' sayfası oluşturulmamış veya boş.")
