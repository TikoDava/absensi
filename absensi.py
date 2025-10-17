import streamlit as st
import pandas as pd
from datetime import date
import requests 
import json
import time 

# --- KONFIGURASI DAN INIITALISASI ---

# GANTI INI dengan URL Web App lengkap yang Anda dapatkan setelah Deploy Apps Script!
APPS_SCRIPT_URL = 'https://script.google.com/macros/s/AKfycbxUaxNhx-U-2bSSpQDlutBekQa5VDTVLP0N1T5RWYvZJrXXzb-vRlJDLps_R4pcCsU1/exec' 

SHEET_KARYAWAN = 'Karyawan'
SHEET_ABSENSI = 'Absensi Harian'

# DAFTAR STATUS LENGKAP
# FIX: 'setengah_hari' diubah menjadi '1/2 hari' agar konsisten dengan display
STATUS_ABSENSI = ['masuk', 'sakit', 'izin', 'alpha', '1/2 hari', 'resign', 'libur', 'kosong']

# Peta Status untuk tampilan Button/Radio dan Key (untuk disimpan ke Sheets)
STATUS_DISPLAY = {
    'masuk': '✅ Masuk',
    'sakit': '💊 Sakit',
    'izin': '📄 Izin', 
    'alpha': '❌ Alpha',
    '1/2 hari': '🌗 1/2 Hari',
    'resign': '🚪 Resign', 
    'libur': '🌴 Libur',      
    'kosong': '⚪ Kosong',    
}

# Mapping untuk warna tombol (Saat tombol TIDAK aktif/secondary)
STATUS_COLOR = {
    'masuk': 'primary', 
    'sakit': 'secondary',
    'izin': 'secondary',
    'alpha': 'primary', 
    '1/2 hari': 'secondary',
    'resign': 'primary', 
    'libur': 'secondary',      
    'kosong': 'secondary',    
}

# --- FUNGSI KOMUNIKASI API (Apps Script) ---
def get_data_from_sheets(sheet_name):
    """Membaca data dari Google Sheets melalui Apps Script API (GET)."""
    try:
        response = requests.get(APPS_SCRIPT_URL, params={'sheet': sheet_name}, timeout=10)
        response.raise_for_status() 
        if not response.text.strip():
            # FIX: Ganti st.error menjadi st.exception untuk error API
            st.exception("Error: Respons dari Apps Script kosong. Mohon periksa URL dan status deployment Apps Script Anda.")
            return None
        result = response.json()
        if result['status'] == 200:
            return result['data']
        else:
            st.exception(f"Error dari Apps Script (GET): {result['message']}")
            return None
    except requests.exceptions.Timeout:
        st.exception("Gagal koneksi: Permintaan waktu tunggu (timeout) ke Apps Script.")
        return None
    except requests.exceptions.RequestException as e:
        st.exception(f"Gagal koneksi ke Apps Script API. Pastikan URL benar: {e}")
        return None
    except json.JSONDecodeError as e:
        st.exception(f"Gagal memproses respons (JSON Error). Apps Script mungkin mengembalikan HTML/Teks Error. Kesalahan: {e}")
        st.code(response.text, language='text', label="Raw Apps Script Response")
        return None
    except Exception as e:
        st.exception(f"Terjadi kesalahan tak terduga: {e}")
        return None

def post_data_to_sheets(sheet_name, payload):
    """Menulis data ke Google Sheets melalui Apps Script API (POST)."""
    try:
        response = requests.post(APPS_SCRIPT_URL, params={'sheet': sheet_name}, json=payload, timeout=10)
        response.raise_for_status() 
        if not response.text.strip():
            st.exception("Error POST: Respons dari Apps Script kosong. Mohon periksa status deployment.")
            return False
        result = response.json()
        if result['status'] == 200:
            return result['data'] if 'data' in result else True
        else:
            # FIX: Ganti st.error menjadi st.exception
            st.exception(f"Error dari Apps Script (POST): {result['message']}")
            return False
    except requests.exceptions.Timeout:
        st.exception("Gagal koneksi: Permintaan waktu tunggu (timeout) saat POST data.")
        return False
    except requests.exceptions.RequestException as e:
        st.exception(f"Gagal koneksi ke Apps Script API. Pastikan URL benar: {e}")
        return False
    except json.JSONDecodeError as e:
        st.exception(f"Gagal memproses respons POST (JSON Error). Apps Script mungkin mengembalikan HTML/Teks Error. Kesalahan: {e}")
        st.code(response.text, language='text', label="Raw Apps Script Response (POST)")
        return False
    except Exception as e:
        st.exception(f"Terjadi kesalahan tak terduga saat POST: {e}")
        return False


# --- 1. SETUP DATA KARYAWAN (BACA DARI SHEETS) ---
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

if 'rekap_tahun' not in st.session_state:
    st.session_state.rekap_tahun = date.today().year
if 'rekap_bulan' not in st.session_state:
    st.session_state.rekap_bulan = date.today().month

# FIX: Inisialisasi awal tanggal input untuk tab cepat
if 'quick_input_date' not in st.session_state:
    st.session_state.quick_input_date = date.today()

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
        return False

    try:
        # Menggunakan .index[0] karena index adalah ID_Karyawan
        karyawan_id = df_k[df_k['Nama_Karyawan'] == nama_karyawan].index[0]
    except IndexError:
        st.error(f"Karyawan '{nama_karyawan}' tidak ditemukan di master list.")
        return False

    karyawan_id_std = int(karyawan_id) 
    
    payload = {
        'tanggal': tanggal.strftime('%Y-%m-%d'),
        'id_karyawan': karyawan_id_std,
        'status': status,
        'produksi': produksi 
    }
    
    # FIX: Memanggil post_data_to_sheets
    if post_data_to_sheets(SHEET_ABSENSI, payload):
        return True
    else:
        return False


# --- 4. FUNGSI REKAP BULANAN (BACA & PROSES DARI CACHE) ---
# ... (Fungsi rekap_bulanan tidak diubah, karena tidak ada bug yang terlihat di blok ini) ...
def rekap_bulanan(tahun, bulan):
    """Mengambil data dari cache dan menghitung rekap."""
    
    data_absensi = get_absensi_data()
    
    if not data_absensi or st.session_state.df_karyawan.empty:
        return pd.DataFrame()
        
    try:
        df_absensi = pd.DataFrame(data_absensi)
        
        if df_absensi.empty:
            df_rekap = st.session_state.df_karyawan.copy().reset_index()
            for status in STATUS_ABSENSI:
                df_rekap[status] = 0
            df_rekap['Total Produksi'] = 0 
            
            kolom_rekap = ['Nama_Karyawan', 'Total Produksi'] + STATUS_ABSENSI 
            return df_rekap[kolom_rekap].sort_values(by='Nama_Karyawan').reset_index(drop=True)

        # --- PEMROSESAN DATA ---
        
        df_absensi['Tanggal'] = pd.to_datetime(df_absensi['Tanggal'], errors='coerce', utc=True)
        df_absensi['Tanggal'] = df_absensi['Tanggal'].dt.tz_convert('Asia/Jakarta')
        df_absensi['Tanggal'] = df_absensi['Tanggal'].dt.normalize().dt.tz_localize(None)

        df_absensi['ID_Karyawan'] = pd.to_numeric(df_absensi['ID_Karyawan'], errors='coerce').fillna(0).astype(int)
        
        if 'Produksi' in df_absensi.columns:
            df_absensi['Produksi'] = pd.to_numeric(df_absensi['Produksi'], errors='coerce').fillna(0)
        else:
            df_absensi['Produksi'] = 0

        df_filtered = df_absensi[
            (df_absensi['Tanggal'].dt.year == tahun) & 
            (df_absensi['Tanggal'].dt.month == bulan)
        ].copy() # Gunakan .copy() untuk menghindari SettingWithCopyWarning

        # --- PERBAIKAN BUG 2X ABSENSI: Dapatkan STATUS dan PRODUKSI TERAKHIR per HARI ---
        # Sortir data berdasarkan waktu, lalu ambil baris terakhir per karyawan per tanggal (status final hari itu)
        df_final_daily = df_filtered.sort_values('Tanggal').groupby(
            ['ID_Karyawan', df_filtered['Tanggal'].dt.date] # Grouping berdasarkan ID dan Tanggal (hanya tanggal)
        ).last().reset_index() # Ambil entri TERAKHIR (terbaru) untuk hari itu
        
        # Kolom 'Tanggal' sekarang berisi objek date (dari .dt.date)
        df_final_daily['Tanggal'] = pd.to_datetime(df_final_daily['Tanggal'])

        # Hitung jumlah status berdasarkan STATUS FINAL harian
        df_counts = df_final_daily.groupby(['ID_Karyawan', 'Status_Kehadiran']).size().unstack(fill_value=0)
        
        # Hitung total produksi berdasarkan PRODUKSI FINAL harian
        df_produksi = df_final_daily.groupby('ID_Karyawan')['Produksi'].sum().reset_index()
        df_produksi = df_produksi.rename(columns={'Produksi': 'Total Produksi'})
        df_produksi = df_produksi.set_index('ID_Karyawan')

        df_rekap = st.session_state.df_karyawan.copy() 
        
        df_rekap = df_rekap.merge(
            df_counts, 
            left_index=True, 
            right_index=True,
            how='left' 
        )
        
        df_rekap = df_rekap.merge(
            df_produksi, 
            left_index=True, 
            right_index=True,
            how='left' 
        )
        
        # Inisialisasi kolom baru jika tidak ada data di Sheets (penting untuk status baru)
        for status in STATUS_ABSENSI:
            if status not in df_rekap.columns:
                df_rekap[status] = 0
                
        df_rekap = df_rekap.fillna(0)
        
        for status in STATUS_ABSENSI:
            df_rekap[status] = df_rekap[status].astype(int)
            
        df_rekap['Total Produksi'] = df_rekap['Total Produksi'].astype(int)
            
        df_rekap = df_rekap.reset_index() 

        # Pastikan kolom output sesuai dengan STATUS_ABSENSI yang baru
        kolom_rekap = ['Nama_Karyawan', 'Total Produksi'] + STATUS_ABSENSI 
        df_rekap = df_rekap[kolom_rekap]
        
        return df_rekap.sort_values(by='Nama_Karyawan').reset_index(drop=True)
            
    except Exception as e:
        st.error(f"Gagal memproses data rekap. Pastikan format kolom di Sheets sudah benar: {e}")
        return pd.DataFrame()


# --- 6. FUNGSI BARU UNTUK INPUT CEPAT (BERBASIS TOMBOL) ---

# Fungsi untuk memuat status dan produksi yang sudah tercatat
def get_current_status(tanggal_input):
    """Mengambil status dan produksi hari ini untuk semua karyawan."""
    
    df_k = st.session_state.df_karyawan
    if df_k.empty:
        return pd.DataFrame()

    data_absensi = get_absensi_data()
    df_absensi = pd.DataFrame(data_absensi) if data_absensi else pd.DataFrame(columns=['Tanggal', 'ID_Karyawan', 'Status_Kehadiran', 'Produksi'])

    if not df_absensi.empty:
        df_absensi['Tanggal'] = pd.to_datetime(df_absensi['Tanggal'], errors='coerce', utc=True)
        df_absensi['Tanggal'] = df_absensi['Tanggal'].dt.tz_convert('Asia/Jakarta').dt.normalize().dt.tz_localize(None)
        df_absensi['ID_Karyawan'] = pd.to_numeric(df_absensi['ID_Karyawan'], errors='coerce').fillna(0).astype(int)
        
        tanggal_str = tanggal_input.strftime('%Y-%m-%d')
        df_filtered = df_absensi[df_absensi['Tanggal'].dt.normalize() == pd.to_datetime(tanggal_str)]
        
        # FIX: Gunakan .last() setelah di-sort untuk memastikan status terakhir yang diambil
        df_current_status = df_filtered.sort_values(by='Tanggal').groupby('ID_Karyawan').agg(
            {'Status_Kehadiran': 'last', 'Produksi': 'last'}
        ).reset_index()
        
        df_current_status = df_current_status.rename(columns={'Status_Kehadiran': 'Status_Awal', 'Produksi': 'Produksi_Awal'})
        df_current_status['Status_Awal'] = df_current_status['Status_Awal'].str.lower()
        df_current_status['Produksi_Awal'] = pd.to_numeric(df_current_status['Produksi_Awal'], errors='coerce').fillna(0).astype(int)
    else:
        df_current_status = pd.DataFrame(columns=['ID_Karyawan', 'Status_Awal', 'Produksi_Awal'])
    
    # Gabungkan dengan master karyawan
    df_k_reset = df_k.copy().reset_index()
    df_merged = df_k_reset.merge(df_current_status, on='ID_Karyawan', how='left')
    
    # PERBAIKAN BUG KOSONG: Gunakan placeholder unik '__NEW_ENTRY__' untuk data yang benar-benar baru (NULL)
    df_merged['Status_Awal'] = df_merged['Status_Awal'].fillna('__NEW_ENTRY__').astype(str)
    df_merged['Produksi_Awal'] = df_merged['Produksi_Awal'].fillna(0).astype(int)
    
    # Siapkan session state untuk produksi (agar bisa di-edit)
    for index, row in df_merged.iterrows():
        # FIX: Gunakan key status dan prod yang unik per tanggal agar tidak konflik saat ganti tanggal
        key_status = f"status_{row['ID_Karyawan']}_{tanggal_input}"
        key_prod = f"prod_{row['ID_Karyawan']}_{tanggal_input}"
        
        # Inisialisasi session state untuk status
        initial_status_session = row['Status_Awal']
        if initial_status_session == '__NEW_ENTRY__':
            initial_status_session = 'kosong' # Tampilkan 'kosong' di UI untuk entri baru

        if key_status not in st.session_state:
            st.session_state[key_status] = initial_status_session
            
        # Inisialisasi session state untuk produksi
        if key_prod not in st.session_state:
            st.session_state[key_prod] = row['Produksi_Awal']
        
    return df_merged[['ID_Karyawan', 'Nama_Karyawan', 'Status_Awal', 'Produksi_Awal']]


def handle_status_click(id_karyawan, tanggal_input, status_key):
    """Callback function saat tombol status diklik."""
    key_status = f"status_{id_karyawan}_{tanggal_input}"
    key_prod = f"prod_{id_karyawan}_{tanggal_input}"
    
    # Perbarui status di session state
    st.session_state[key_status] = status_key
    
    # FIX: Memastikan status non-produksi mereset produksi menjadi 0
    if status_key in ['alpha', 'sakit', 'izin', 'resign', 'libur', 'kosong', '1/2 hari']: # Tambahkan '1/2 hari'
        st.session_state[key_prod] = 0

def tampilkan_input_cepat_harian_button():
    """Menampilkan input cepat harian berbasis tombol dan memproses penyimpanan."""
    
    # FIX: Menggunakan st.session_state.quick_input_date yang sudah diperbarui di tab_input_cepat
    tanggal_input = st.session_state.quick_input_date 
    df_data = get_current_status(tanggal_input)
    
    if df_data.empty:
        st.warning("Tambahkan nama karyawan di tab 'Kelola Karyawan' terlebih dahulu.")
        return
        
    st.markdown("---")
    st.caption("Klik tombol status kehadiran untuk memperbarui. Status yang sedang aktif akan berwarna **biru** (primary).")
    
    # Tentukan lebar kolom: Nama Karyawan (2), Produksi (1), Status-status (1 per status)
    column_widths = [2, 1] + [1] * len(STATUS_ABSENSI) 
    
    # Header Tabel
    header_cols = st.columns(column_widths)
    header_cols[0].markdown('**Nama Karyawan**', help="Nama karyawan")
    header_cols[1].markdown('**Produksi**', help="Jumlah Produksi")
    for i, status_key in enumerate(STATUS_ABSENSI):
        # Tampilkan hanya label pendek (emoji/teks) di header
        # FIX: Gunakan split(" ")[0] untuk mengambil emoji/teks pertama
        header_cols[i+2].markdown(f'**{STATUS_DISPLAY[status_key].split(" ")[0]}**', help=STATUS_DISPLAY[status_key]) 
        
    st.markdown('***') # Garis pemisah Header
        
    updates_made = False
    
    # Tampilkan Data Karyawan
    for index, row in df_data.iterrows():
        id_karyawan = row['ID_Karyawan']
        nama_karyawan = row['Nama_Karyawan']
        
        # Ambil status dan produksi saat ini dari session state
        current_status_key = st.session_state[f"status_{id_karyawan}_{tanggal_input}"]
        current_prod = st.session_state[f"prod_{id_karyawan}_{tanggal_input}"]
        
        cols = st.columns(column_widths)
        
        # Kolom Nama
        cols[0].write(nama_karyawan)
        
        # Kolom Produksi (Number Input)
        st.session_state[f"prod_{id_karyawan}_{tanggal_input}"] = cols[1].number_input(
            "Produksi",
            min_value=0,
            # FIX: Gunakan current_prod, yang sudah dimuat dari sheets/session state
            value=current_prod, 
            step=1,
            # FIX: Gunakan key unik yang berbeda dari key session state (penting untuk number_input)
            key=f"prod_input_ui_{id_karyawan}_{tanggal_input}", 
            label_visibility="collapsed"
        )
        
        # Kolom Tombol Status
        for i, status_key in enumerate(STATUS_ABSENSI):
            is_active = (current_status_key == status_key)
            
            # FIX PEWARNAAN TOMBOL: Jika aktif, selalu 'primary' (biru)
            button_type = 'primary' if is_active else 'secondary'

            cols[i+2].button(
                STATUS_DISPLAY[status_key], # Teks tombol (Hanya Emoji/Teks Utama)
                on_click=handle_status_click,
                args=(id_karyawan, tanggal_input, status_key),
                key=f"btn_{id_karyawan}_{status_key}_{tanggal_input}",
                type=button_type, 
                use_container_width=True
            )

        # Logika Cek Perubahan: Status final != Status awal (dari sheets) ATAU Produksi berubah
        # Status awal yang digunakan untuk perbandingan adalah Status_Awal dari df_data 
        
        status_awal_ui = row['Status_Awal']
        produksi_awal_ui = row['Produksi_Awal']
        
        # Khusus: Jika status awal adalah '__NEW_ENTRY__', kita cek apakah status_final bukan 'kosong'
        # atau jika produksi final bukan 0. Jika new entry, kita anggap '__NEW_ENTRY__' sama dengan 'kosong'
        # untuk tujuan perbandingan, tetapi kita harus tetap upload entri 'kosong' pertama.
        
        is_new_entry = status_awal_ui == '__NEW_ENTRY__'
        
        # Jika ada perubahan status dari sheets ATAU ada perubahan produksi
        if current_status_key != status_awal_ui or current_prod != produksi_awal_ui:
            updates_made = True
            
        # FIX LOGIKA: Jika ini adalah entri baru (NEW_ENTRY) dan statusnya sekarang 'kosong'
        # kita harus tetap upload karena ini akan menjadi entri pertama (status: kosong, produksi: 0)
        # di Sheets, yang sebelumnya tidak ada.
        if is_new_entry and current_status_key == 'kosong':
            updates_made = True 


    st.markdown("---")

    # --- 3. LOGIKA PENYIMPANAN ---
    
    # Hanya tampilkan tombol simpan jika ada perubahan
    if st.button("💾 Simpan Perubahan Absensi Harian ke Google Sheets", disabled=not updates_made):
        
        rows_to_update = []
        success_count = 0
        
        for index, row in df_data.iterrows():
            id_karyawan = row['ID_Karyawan']
            
            status_awal = row['Status_Awal']
            produksi_awal = row['Produksi_Awal']
            
            # Nilai final diambil dari session state
            status_final = st.session_state[f"status_{id_karyawan}_{tanggal_input}"]
            produksi_final = st.session_state[f"prod_{id_karyawan}_{tanggal_input}"]

            # Logika Unggah yang Diperbaiki:
            should_update = False
            is_new_entry = status_awal == '__NEW_ENTRY__'
            
            # 1. Jika ada perubahan status ATAU produksi
            if status_final != status_awal or produksi_final != produksi_awal:
                should_update = True
                
            # 2. FIX: Jika ini adalah entri baru dan user klik 'kosong'
            # Kita harus upload status 'kosong' dengan produksi 0 untuk mencatat entry awal.
            if is_new_entry and status_final == 'kosong':
                should_update = True


            if should_update:
                rows_to_update.append({
                    'id_karyawan': id_karyawan,
                    'nama_karyawan': row['Nama_Karyawan'],
                    'status': status_final,
                    'produksi': produksi_final
                })

        if not rows_to_update:
            st.info("Tidak ada perubahan yang perlu disimpan.")
            return

        placeholder_msg = st.empty()
        placeholder_msg.info(f"Mengunggah **{len(rows_to_update)}** perubahan absensi ke Google Sheets...")
        
        # Gunakan list untuk mencatat yang gagal
        failed_updates = []

        for item in rows_to_update:
            try:
                # Kirim data satu per satu
                if input_absensi(tanggal_input, item['nama_karyawan'], item['status'], item['produksi']):
                    success_count += 1
                else:
                    # input_absensi akan menampilkan error Streamlit jika Apps Script gagal
                    failed_updates.append(item['nama_karyawan'])
            except Exception as e:
                st.exception(f"Error fatal saat mengirim data untuk {item['nama_karyawan']}: {e}")
                failed_updates.append(item['nama_karyawan'])
                
        # Logika pasca-update
        if success_count > 0:
            get_absensi_data.clear() # Hapus cache data absensi
            time.sleep(0.5)
            
            # Pesan sukses
            placeholder_msg.success(f"Absensi untuk **{success_count} karyawan** pada {tanggal_input} berhasil diperbarui dan **diunggah** ke Sheets!")
            
            # Pesan peringatan jika ada yang gagal
            if failed_updates:
                st.warning(f"{len(failed_updates)} karyawan gagal diperbarui (lihat detail error di atas): {', '.join(failed_updates)}. Silakan coba lagi.")
                
            # Bersihkan session state terkait input cepat untuk memuat ulang status baru
            for key in list(st.session_state.keys()):
                 # FIX: Hanya hapus key status dan prod yang terkait dengan tanggal yang sedang di-update
                 if key.startswith(f'status_') or key.startswith(f'prod_'):
                      if f'_{tanggal_input}' in key:
                         del st.session_state[key]
            
            st.rerun() # Muat ulang tampilan setelah berhasil
        else:
            placeholder_msg.error("Gagal mengunggah data. Periksa koneksi atau Apps Script URL Anda.")
            if failed_updates:
                 st.warning(f"Semua karyawan gagal diperbarui (lihat detail error di atas): {', '.join(failed_updates)}.")


# --- 5. TAMPILAN STREAMLIT (DASHBOARD) ---
st.set_page_config(layout="wide", page_title="Dashboard Absensi Karyawan")
st.title("Absensi Karyawan")

tab_input_cepat, tab_input, tab_rekap, tab_master, tab_harian = st.tabs([
    "⚡ Input Cepat Harian", 
    "✍️ Input Absensi Satuan", 
    "📈 Rekap Bulanan", 
    "👥 Kelola Karyawan", 
    "🔍 Tinjauan Harian"
])

# ----------------------------------------------------
# TAB INPUT CEPAT HARIAN (BERBASIS TOMBOL)
# ----------------------------------------------------
with tab_input_cepat:
    st.header("Input Absensi Cepat Harian (Tombol)")
    
    col1, col2 = st.columns([1, 4])
    with col1:
        # FIX: Panggil st.date_input dan simpan ke st.session_state.quick_input_date
        date_quick_input = st.date_input("Tanggal Absensi", value=st.session_state.quick_input_date, key='quick_input_date_tab_cepat')
        st.session_state.quick_input_date = date_quick_input
    
    tampilkan_input_cepat_harian_button()
    

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
        # --- FIX TAMPILAN: Menyesuaikan tinggi tabel secara dinamis ---
        jumlah_karyawan = len(st.session_state.df_karyawan)
        tinggi_tabel = (jumlah_karyawan * 35) + 30 
        
        st.dataframe(
            st.session_state.df_karyawan.reset_index(names='ID'), 
            use_container_width=True, 
            hide_index=True,
            height=int(tinggi_tabel) 
        )
    else:
        st.info("Silakan tambahkan karyawan pertama Anda.")

# ----------------------------------------------------
# TAB 1: INPUT ABSENSI HARIAN (SATUAN)
# ----------------------------------------------------
with tab_input:
    st.header("Input Kehadiran Harian (Satuan)")
    
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
            
            # Status radio button menggunakan STATUS_DISPLAY agar tampilannya bagus
            status_terpilih_display = st.radio(
                "Status Kehadiran",
                options=list(STATUS_DISPLAY.values()),
                horizontal=True,
                index=0
            )
            # Konversi kembali ke status key untuk disimpan ke Sheets
            status_terpilih = next(key for key, value in STATUS_DISPLAY.items() if value == status_terpilih_display)

            
            produksi_input = st.number_input(
                "Jumlah Produksi (Cth: Unit, Kg, Item)",
                min_value=0,
                value=0,
                step=1
            )
            
            submitted = st.form_submit_button("Catat Absensi & Simpan ")
            
            if submitted:
                # FIX: Pastikan input_absensi dipanggil dengan nilai yang benar
                if input_absensi(tanggal_input, nama_terpilih, status_terpilih, produksi_input):
                    st.success(f"Absensi untuk **{nama_terpilih}** pada {tanggal_input} ({status_terpilih_display}) dengan produksi **{produksi_input}** berhasil dicatat dan **diunggah** ke Sheets!")
                    get_absensi_data.clear()
                    time.sleep(0.5)
                    st.rerun()

# ----------------------------------------------------
# TAB 2: REKAP BULANAN
# ----------------------------------------------------
with tab_rekap:
    st.header("Rekapitulasi Absensi Per Bulan")
    
    col_tah, col_bul = st.columns(2)
    
    tahun_options = [date.today().year] + list(range(2023, date.today().year))
    tahun_options_sorted = sorted(list(set(tahun_options)), reverse=True)
    
    with col_tah:
        try:
            default_year_index = tahun_options_sorted.index(st.session_state.rekap_tahun)
        except ValueError:
            default_year_index = 0
            
        tahun_rekap = st.selectbox(
            "Pilih Tahun", 
            options=tahun_options_sorted,
            index=default_year_index,
            key='rekap_tahun_tab' 
        )
    
    with col_bul:
        bulan_options = list(range(1, 13))
        try:
            default_month_index = bulan_options.index(st.session_state.rekap_bulan)
        except ValueError:
            default_month_index = 0
            
        bulan_rekap = st.selectbox(
            "Pilih Bulan", 
            options=bulan_options, 
            format_func=lambda x: date(2000, x, 1).strftime('%B'),
            index=default_month_index,
            key='rekap_bulan_tab' 
        )
    
    df_rekap = rekap_bulanan(tahun_rekap, bulan_rekap)
        
    if not df_rekap.empty:
        st.subheader(f"Ringkasan Absensi: {date(tahun_rekap, bulan_rekap, 1).strftime('%B %Y')}")
        
        # Ganti nama kolom sesuai STATUS_DISPLAY yang baru
        kolom_ganti_nama = {k: STATUS_DISPLAY.get(k, k.capitalize()) for k in STATUS_ABSENSI}
        df_rekap_display = df_rekap.rename(columns=kolom_ganti_nama)
        
        st.dataframe(
            df_rekap_display.style.format({'Total Produksi': '{:,}'}), 
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
    
    data_absensi = get_absensi_data()
    
    if not data_absensi or st.session_state.df_karyawan.empty:
        st.warning("Tidak ada data absensi yang ditemukan atau daftar karyawan kosong.")
    else:
        df_absensi = pd.DataFrame(data_absensi)
        
        df_absensi['Tanggal'] = pd.to_datetime(df_absensi['Tanggal'], errors='coerce', utc=True)
        df_absensi['Tanggal'] = df_absensi['Tanggal'].dt.tz_convert('Asia/Jakarta')
        df_absensi['Tanggal'] = df_absensi['Tanggal'].dt.normalize().dt.tz_localize(None)

        df_absensi['ID_Karyawan'] = pd.to_numeric(df_absensi['ID_Karyawan'], errors='coerce').fillna(0).astype(int)
        if 'Produksi' in df_absensi.columns:
            df_absensi['Produksi'] = pd.to_numeric(df_absensi['Produksi'], errors='coerce').fillna(0)

        df_display = df_absensi.merge(
            st.session_state.df_karyawan.reset_index()[['ID_Karyawan', 'Nama_Karyawan']],
            on='ID_Karyawan',
            how='left'
        )
        
        df_display = df_display.sort_values(by='Tanggal', ascending=False)
        
        if not df_display.empty and pd.notna(df_display['Tanggal'].min()):
            min_date = df_display['Tanggal'].min().date()
            max_date = df_display['Tanggal'].max().date()
        else:
            min_date = date.today()
            max_date = date.today()
        
        col_start, col_end = st.columns(2)
        with col_start:
            start_date = st.date_input("Tanggal Mulai", value=min_date, min_value=min_date, max_value=max_date, key='log_start_date')
        with col_end:
            end_date = st.date_input("Tanggal Akhir", value=max_date, min_value=min_date, max_value=max_date, key='log_end_date')
            
        df_filtered = df_display[
            (df_display['Tanggal'].dt.date >= start_date) & 
            (df_display['Tanggal'].dt.date <= end_date)
        ]

        st.subheader(f"Log Harian ({start_date} hingga {end_date})")
        
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
                file_name=f'log_absensi_harian_{start_date}_to_{end_date}.csv',
                mime='text/csv',
            )
