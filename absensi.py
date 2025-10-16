import streamlit as st
import pandas as pd
from datetime import date
import requests 
import json
import time # Diperlukan untuk penundaan singkat (sleep)

# --- KONFIGURASI DAN INIITALISASI ---

# GANTI INI dengan URL Web App lengkap yang Anda dapatkan setelah Deploy Apps Script!
APPS_SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbxUaxNhx-U-2bSSpQDlutBekQa5VDTVLP0N1T5RWYvZJrXXzb-vRlJDLps_R4pcCsU1/exec' 

SHEET_KARYAWAN = 'Karyawan'
SHEET_ABSENSI = 'Absensi Harian'

STATUS_ABSENSI = ['hadir', 'sakit', 'alfa', 'resign', 'kosong']

# --- FUNGSI KOMUNIKASI API (Apps Script) ---

def get_data_from_sheets(sheet_name):
    """Membaca data dari Google Sheets melalui Apps Script API (GET)."""
    try:
        response = requests.get(APPS_SCRIPT_URL, params={'sheet': sheet_name}, timeout=10)
        response.raise_for_status() # Cek error HTTP (4xx atau 5xx)
        
        if not response.text.strip():
            st.error("Error: Respons dari Apps Script kosong. Mohon periksa URL dan status deployment Apps Script Anda.")
            return None
            
        result = response.json()
        
        if result['status'] == 200:
            return result['data']
        else:
            st.error(f"Error dari Apps Script (GET): {result['message']}")
            return None
    except requests.exceptions.Timeout:
        st.error("Gagal koneksi: Permintaan waktu tunggu (timeout) ke Apps Script.")
        return None
    except requests.exceptions.RequestException as e:
        st.error(f"Gagal koneksi ke Apps Script API. Pastikan URL benar: {e}")
        return None
    except json.JSONDecodeError as e:
        st.error(f"Gagal memproses respons (JSON Error). Apps Script mungkin mengembalikan HTML/Teks Error. Kesalahan: {e}")
        st.code(response.text, language='text', label="Raw Apps Script Response")
        return None
    except Exception as e:
        st.error(f"Terjadi kesalahan tak terduga: {e}")
        return None

def post_data_to_sheets(sheet_name, payload):
    """Menulis data ke Google Sheets melalui Apps Script API (POST)."""
    try:
        response = requests.post(APPS_SCRIPT_URL, params={'sheet': sheet_name}, json=payload, timeout=10)
        response.raise_for_status() # Cek error HTTP
        
        if not response.text.strip():
            st.error("Error POST: Respons dari Apps Script kosong. Mohon periksa status deployment.")
            return False

        result = response.json()
        
        if result['status'] == 200:
            return result['data'] if 'data' in result else True
            
        else:
            st.error(f"Error dari Apps Script (POST): {result['message']}")
            return False
            
    except requests.exceptions.Timeout:
        st.error("Gagal koneksi: Permintaan waktu tunggu (timeout) saat POST data.")
        return False
    except requests.exceptions.RequestException as e:
        st.error(f"Gagal koneksi ke Apps Script API. Pastikan URL benar: {e}")
        return False
    except json.JSONDecodeError as e:
        st.error(f"Gagal memproses respons POST (JSON Error). Apps Script mungkin mengembalikan HTML/Teks Error. Kesalahan: {e}")
        st.code(response.text, language='text', label="Raw Apps Script Response (POST)")
        return False
    except Exception as e:
        st.error(f"Terjadi kesalahan tak terduga saat POST: {e}")
        return False


# --- 1. SETUP DATA KARYAWAN (BACA DARI SHEETS) ---

# Fungsi karyawan tidak di-cache karena jarang dipanggil ulang
def load_karyawan():
    data = get_data_from_sheets(SHEET_KARYAWAN)
    if data:
        df = pd.DataFrame(data)
        if not df.empty:
            df['ID_Karyawan'] = df['ID_Karyawan'].astype(str).str.strip()
            df['ID_Karyawan'] = pd.to_numeric(df['ID_Karyawan'], errors='coerce').fillna(0).astype(int) 
            st.session_state.df_karyawan = df.set_index('ID_Karyawan')
        else:
            st.session_state.df_karyawan = pd.DataFrame(columns=['ID_Karyawan', 'Nama_Karyawan']).set_index('ID_Karyawan')
    else:
        st.session_state.df_karyawan = pd.DataFrame(columns=['ID_Karyawan', 'Nama_Karyawan']).set_index('ID_Karyawan')

# --- FUNGSI CACHE UNTUK DATA ABSENSI ---
@st.cache_data(show_spinner="Memuat data absensi terbaru...")
def get_absensi_data():
    """Mengambil semua data absensi dari sheets dengan caching."""
    return get_data_from_sheets(SHEET_ABSENSI)

# --- INIITALISASI AWAL ---
if 'df_karyawan' not in st.session_state:
    load_karyawan() 
    st.session_state.df_absensi_harian = pd.DataFrame(columns=['Tanggal', 'ID_Karyawan', 'Status_Kehadiran'])

# Inisialisasi state untuk Rekap Bulanan agar tidak kembali ke awal setelah rerun
if 'rekap_tahun' not in st.session_state:
    st.session_state.rekap_tahun = date.today().year
if 'rekap_bulan' not in st.session_state:
    st.session_state.rekap_bulan = date.today().month


# --- 2. FUNGSI INPUT KARYAWAN BARU (TULIS KE SHEETS) ---
def tambah_karyawan(nama_baru):
    """Menambahkan nama karyawan baru ke sheets dan memperbarui session state."""
    df_k = st.session_state.df_karyawan
    
    nama_baru_clean = nama_baru.strip()
    
    if not nama_baru_clean:
        st.warning("Nama karyawan tidak boleh kosong.")
        return
        
    if nama_baru_clean in df_k['Nama_Karyawan'].values:
        st.warning(f"Karyawan '{nama_baru_clean}' sudah ada dalam daftar.")
        return

    payload = {'nama_karyawan': nama_baru_clean}
    
    result = post_data_to_sheets(SHEET_KARYAWAN, payload)
    
    if result and 'id' in result:
        st.success(f"Karyawan '{nama_baru_clean}' (ID: {result['id']}) berhasil ditambahkan dan **diunggah**.")
        
        # Karena ini data karyawan, kita muat ulang tanpa cache
        load_karyawan() 
        st.rerun() 
        
    elif result is not False:
        st.error("Gagal mendapatkan ID baru atau menyimpan data dari Apps Script.")


# --- 3. FUNGSI INPUT ABSENSI HARIAN (TULIS KE SHEETS) ---
def input_absensi(tanggal, nama_karyawan, status, produksi):
    """Mencatat absensi harian dan menyimpannya di Google Sheets."""
    df_k = st.session_state.df_karyawan
    
    if df_k.empty:
        st.error("Daftar karyawan kosong. Tambahkan karyawan terlebih dahulu.")
        return

    try:
        karyawan_id = df_k[df_k['Nama_Karyawan'] == nama_karyawan].index[0]
    except IndexError:
        st.error(f"Karyawan '{nama_karyawan}' tidak ditemukan di master list.")
        return

    karyawan_id_std = int(karyawan_id) 
    
    payload = {
        'tanggal': tanggal.strftime('%Y-%m-%d'),
        'id_karyawan': karyawan_id_std,
        'status': status,
        'produksi': produksi 
    }
    
    if post_data_to_sheets(SHEET_ABSENSI, payload):
        st.success(f"Absensi untuk **{nama_karyawan}** pada {tanggal} ({status}) dengan produksi **{produksi}** berhasil dicatat dan **diunggah** ke Sheets!")
        
        # 1. Clear Cache Data Absensi untuk memaksa re-fetch data terbaru
        get_absensi_data.clear()
        
        # 2. Tambahkan penundaan singkat untuk memberi waktu Sheets commit data
        time.sleep(0.5) 
            
        st.rerun() # MEMAKSA RERUN AGAR REKAP BULANAN MENGAMBIL DATA TERBARU


# --- 4. FUNGSI REKAP BULANAN (BACA & PROSES DARI CACHE) ---
def rekap_bulanan(tahun, bulan):
    """Mengambil data dari cache dan menghitung rekap."""
    
    # Ambil data langsung dari fungsi cache
    data_absensi = get_absensi_data()
    
    if not data_absensi or st.session_state.df_karyawan.empty:
        return pd.DataFrame()
        
    try:
        df_absensi = pd.DataFrame(data_absensi)
        
        if df_absensi.empty:
            # Jika tidak ada data absensi sama sekali
            df_rekap = st.session_state.df_karyawan.copy().reset_index()
            for status in STATUS_ABSENSI:
                df_rekap[status] = 0
            df_rekap['Total Produksi'] = 0 # TAMBAHKAN KOLOM TOTAL PRODUKSI
            
            kolom_rekap = ['Nama_Karyawan', 'Total Produksi'] + STATUS_ABSENSI 
            return df_rekap[kolom_rekap].sort_values(by='Nama_Karyawan').reset_index(drop=True)


        # --- PEMROSESAN DATA ---
        
        # 1. Konversi Tanggal dan ZONA WAKTU (WIB)
        df_absensi['Tanggal'] = pd.to_datetime(df_absensi['Tanggal'], errors='coerce', utc=True)
        df_absensi['Tanggal'] = df_absensi['Tanggal'].dt.tz_convert('Asia/Jakarta')
        df_absensi['Tanggal'] = df_absensi['Tanggal'].dt.normalize().dt.tz_localize(None)

        # 2. Bersihkan ID Karyawan dan Produksi
        df_absensi['ID_Karyawan'] = df_absensi['ID_Karyawan'].astype(str).str.strip()
        df_absensi['ID_Karyawan'] = pd.to_numeric(df_absensi['ID_Karyawan'], errors='coerce').fillna(0).astype(int)
        
        # Pastikan kolom Produksi adalah numerik
        if 'Produksi' in df_absensi.columns:
            df_absensi['Produksi'] = pd.to_numeric(df_absensi['Produksi'], errors='coerce').fillna(0)
        else:
            df_absensi['Produksi'] = 0 # Jika kolom tidak ada, inisialisasi dengan 0

        # 3. Filter data absensi berdasarkan bulan dan tahun
        df_filtered = df_absensi[
            (df_absensi['Tanggal'].dt.year == tahun) & 
            (df_absensi['Tanggal'].dt.month == bulan)
        ]

        # 4. Hitung jumlah status kehadiran (df_counts)
        df_counts = df_filtered.groupby(['ID_Karyawan', 'Status_Kehadiran']).size().unstack(fill_value=0)
        
        # 5. Hitung total produksi (df_produksi)
        df_produksi = df_filtered.groupby('ID_Karyawan')['Produksi'].sum().reset_index()
        df_produksi = df_produksi.rename(columns={'Produksi': 'Total Produksi'})
        df_produksi = df_produksi.set_index('ID_Karyawan')


        # 6. Gabungkan dengan Master List Karyawan (LEFT JOIN)
        df_rekap = st.session_state.df_karyawan.copy() 
        
        # Gabung dengan count status
        df_rekap = df_rekap.merge(
            df_counts, 
            left_index=True, 
            right_index=True,
            how='left' 
        )
        
        # Gabung dengan total produksi
        df_rekap = df_rekap.merge(
            df_produksi, 
            left_index=True, 
            right_index=True,
            how='left' 
        )
        
        df_rekap = df_rekap.fillna(0)
        
        # Bersihkan dan konversi tipe data
        for status in STATUS_ABSENSI:
            if status not in df_rekap.columns:
                df_rekap[status] = 0
            df_rekap[status] = df_rekap[status].astype(int)
            
        df_rekap['Total Produksi'] = df_rekap['Total Produksi'].astype(int)
            
        df_rekap = df_rekap.reset_index() 

        # 7. URUTAN KOLOM REKAP (Total Produksi diletakkan setelah Nama_Karyawan)
        kolom_rekap = ['Nama_Karyawan', 'Total Produksi'] + STATUS_ABSENSI 
        df_rekap = df_rekap[kolom_rekap]
        
        return df_rekap.sort_values(by='Nama_Karyawan').reset_index(drop=True)
            
    except Exception as e:
        st.error(f"Gagal memproses data rekap. Pastikan format kolom di Sheets sudah benar: {e}")
        return pd.DataFrame()


# --- 5. TAMPILAN STREAMLIT (DASHBOARD) ---
st.set_page_config(layout="wide", page_title="Dashboard Absensi Karyawan")
st.title("Absensi Karyawan")

tab_input, tab_rekap, tab_master, tab_harian = st.tabs(["✍️ Input Absensi Harian", "📈 Rekap Bulanan", "👥 Kelola Karyawan", "🔍 Tinjauan Harian"])

# ----------------------------------------------------
# TAB 3: KELOLA KARYAWAN (MASTER LIST)
# ----------------------------------------------------
with tab_master:
    st.header("Kelola Data Karyawan")

    with st.form("form_karyawan_baru", clear_on_submit=True):
        nama_baru = st.text_input("Nama Karyawan Baru (Input Sekali Saja)")
        submitted_karyawan = st.form_submit_button("Tambah Karyawan & Simpan")
        if submitted_karyawan:
            tambah_karyawan(nama_baru)
    
    st.markdown("---")
    st.subheader("Daftar Karyawan Aktif")
    if not st.session_state.df_karyawan.empty:
        st.dataframe(
            st.session_state.df_karyawan.reset_index(names='ID'), 
            use_container_width=True, 
            hide_index=True
        )
    else:
        st.info("Silakan tambahkan karyawan pertama Anda.")

# ----------------------------------------------------
# TAB 1: INPUT ABSENSI HARIAN
# ----------------------------------------------------
with tab_input:
    st.header("Input Kehadiran Harian")
    
    if st.session_state.df_karyawan.empty:
        st.warning("Tambahkan nama karyawan di tab 'Kelola Karyawan' terlebih dahulu.")
    else:
        with st.form("form_absensi", clear_on_submit=True):
            col1, col2 = st.columns(2)
            
            with col1:
                tanggal_input = st.date_input("Tanggal", date.today())
            
            with col2:
                list_nama = st.session_state.df_karyawan['Nama_Karyawan'].tolist()
                nama_terpilih = st.selectbox("Nama Karyawan", options=list_nama)
            
            status_terpilih = st.radio(
                "Status Kehadiran",
                options=STATUS_ABSENSI,
                horizontal=True,
                index=0
            )
            
            produksi_input = st.number_input(
                "Jumlah Produksi (Cth: Unit, Kg, Item)",
                min_value=0,
                value=0,
                step=1
            )
            
            submitted = st.form_submit_button("Catat Absensi & Simpan ")
            
            if submitted:
                input_absensi(tanggal_input, nama_terpilih, status_terpilih, produksi_input)

# ----------------------------------------------------
# TAB 2: REKAP BULANAN
# ----------------------------------------------------
with tab_rekap:
    st.header("Rekapitulasi Absensi Per Bulan")
    
    col_tah, col_bul = st.columns(2)
    
    tahun_options = [date.today().year] + list(range(2023, date.today().year))
    tahun_options_sorted = sorted(list(set(tahun_options)), reverse=True)
    
    with col_tah:
        # Tentukan index default berdasarkan session state
        try:
            default_year_index = tahun_options_sorted.index(st.session_state.rekap_tahun)
        except ValueError:
            default_year_index = 0
            
        tahun_rekap = st.selectbox(
            "Pilih Tahun", 
            options=tahun_options_sorted,
            index=default_year_index,
            key='rekap_tahun' # Menggunakan key untuk persistensi
        )
    
    with col_bul:
        bulan_options = list(range(1, 13))
        # Tentukan index default berdasarkan session state
        try:
            default_month_index = bulan_options.index(st.session_state.rekap_bulan)
        except ValueError:
            default_month_index = 0
            
        bulan_rekap = st.selectbox(
            "Pilih Bulan", 
            options=bulan_options, 
            format_func=lambda x: date(2000, x, 1).strftime('%B'),
            index=default_month_index,
            key='rekap_bulan' # Menggunakan key untuk persistensi
        )
    
    # Panggil fungsi rekap, yang otomatis memanggil get_absensi_data() dari cache
    df_rekap = rekap_bulanan(tahun_rekap, bulan_rekap)
        
    if not df_rekap.empty:
        st.subheader(f"Ringkasan Absensi: {date(tahun_rekap, bulan_rekap, 1).strftime('%B %Y')}")
        
        # Styling untuk Total Produksi
        st.dataframe(
            df_rekap.style.format({'Total Produksi': '{:,}'}), 
            hide_index=True, 
            use_container_width=True
        )
            
        csv_export = df_rekap.to_csv(index=False).encode('utf-8')
        st.download_button(
            label="📥 Unduh Data Rekap (.csv)",
            data=csv_export,
            file_name=f'rekap_absensi_{tahun_rekap}_{bulan_rekap}.csv',
            mime='text/csv',
        )
    else:
        st.info(f"Tidak ada data absensi yang tercatat untuk bulan {bulan_rekap}/{tahun_rekap} atau data karyawan masih kosong.")
        
# ----------------------------------------------------
# TAB 4: TINJAUAN HARIAN (REKAP PRODUKSI HARIAN)
# ----------------------------------------------------
with tab_harian:
    st.header("Rekap Data Harian (Termasuk Produksi)")
    
    # Ambil data Absensi Harian mentah dari fungsi cache
    data_absensi = get_absensi_data()
    
    if not data_absensi or st.session_state.df_karyawan.empty:
        st.warning("Tidak ada data absensi yang ditemukan atau daftar karyawan kosong.")
    else:
        df_absensi = pd.DataFrame(data_absensi)
        
        # --- PEMROSESAN DATA ---
        
        # 1. Konversi Tanggal dan ZONA WAKTU (WIB)
        df_absensi['Tanggal'] = pd.to_datetime(df_absensi['Tanggal'], errors='coerce', utc=True)
        df_absensi['Tanggal'] = df_absensi['Tanggal'].dt.tz_convert('Asia/Jakarta')
        df_absensi['Tanggal'] = df_absensi['Tanggal'].dt.normalize().dt.tz_localize(None)

        df_absensi['ID_Karyawan'] = pd.to_numeric(df_absensi['ID_Karyawan'], errors='coerce').fillna(0).astype(int)
        if 'Produksi' in df_absensi.columns:
            df_absensi['Produksi'] = pd.to_numeric(df_absensi['Produksi'], errors='coerce').fillna(0)

        # 2. Gabungkan dengan Nama Karyawan
        df_display = df_absensi.merge(
            st.session_state.df_karyawan.reset_index()[['ID_Karyawan', 'Nama_Karyawan']],
            on='ID_Karyawan',
            how='left'
        )
        
        df_display = df_display.sort_values(by='Tanggal', ascending=False)
        
        # 3. Kontrol Filter Tanggal
        if not df_display.empty and pd.notna(df_display['Tanggal'].min()):
            min_date = df_display['Tanggal'].min().date()
            max_date = df_display['Tanggal'].max().date()
        else:
            min_date = date.today()
            max_date = date.today()
        
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input("Tanggal Mulai", value=min_date, min_value=min_date, max_value=max_date)
        with col_end:
            end_date = st.date_input("Tanggal Akhir", value=max_date, min_value=min_date, max_value=max_date)
            
        # 4. Filter data berdasarkan tanggal yang dipilih
        df_filtered = df_display[
            (df_display['Tanggal'].dt.date >= start_date) & 
            (df_display['Tanggal'].dt.date <= end_date)
        ]

        st.subheader(f"Log Harian ({start_date} hingga {end_date})")
        
        # 5. Pilih dan ganti nama kolom untuk tampilan
        if not df_filtered.empty:
            
            df_filtered['Tanggal'] = df_filtered['Tanggal'].dt.date
            
            df_final = df_filtered[[
                'Tanggal', 
                'Nama_Karyawan', 
                'Status_Kehadiran', 
                'Produksi'
            ]].rename(columns={
                'Tanggal': 'Tanggal Absensi/Produksi', 
                'Status_Kehadiran': 'Status',
                'Nama_Karyawan': 'Karyawan',
                'Produksi': 'Jumlah Produksi'
            })
            
            st.dataframe(df_final.style.format({'Jumlah Produksi': '{:,}'}), hide_index=True, use_container_width=True)

            csv_export = df_final.to_csv(index=False).encode('utf-8')
            st.download_button(
                label="📥 Unduh Log Harian (.csv)",
                data=csv_export,
                file_name=f'log_harian_produksi_{start_date}_to_{end_date}.csv',
                mime='text/csv',
            )
        else:
            st.info("Tidak ada data harian untuk rentang tanggal yang dipilih.")


