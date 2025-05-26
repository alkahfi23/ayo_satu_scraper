import requests
import pandas as pd
from datetime import datetime
import os
from io import BytesIO

# --- Konfigurasi dari environment variable ---
BASE_LIST_URL = "https://passport.ayosatu.id/api/tpgp/pengajuan"
DETAIL_URL = "https://passport.ayosatu.id/api/tpgp/pengajuan/{id}/detail"
TGP_ID = "3236c0b6-bbda-4029-85e3-ccb80e87995f"
SEKOLAH_ID = os.getenv("SEKOLAH_ID")
LIMIT = 10

TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")
BEARER_TOKEN = os.getenv("BEARER_TOKEN")

headers = {
    "Accept": "application/json",
    "Authorization": f"Bearer {BEARER_TOKEN}"
}

def flatten_json(y):
    out = {}
    def flatten(x, name=''):
        if isinstance(x, dict):
            for a in x:
                flatten(x[a], f'{name}{a}_')
        elif isinstance(x, list):
            for i, a in enumerate(x):
                flatten(a, f'{name}{i}_')
        else:
            out[name[:-1]] = x
    flatten(y)
    return out

def get_all_ids():
    print("🔍 Mengambil semua ID dari API...")
    page = 1
    all_ids = []
    while True:
        params = {
            "search": "",
            "limit": LIMIT,
            "page": page,
            "tpgp_id": TGP_ID,
            "sekolah_id": SEKOLAH_ID
        }
        resp = requests.get(BASE_LIST_URL, headers=headers, params=params)
        if resp.status_code != 200:
            print(f"❌ Gagal ambil data list, status code: {resp.status_code}")
            print(f"Response: {resp.text}")
            break

        items = resp.json().get("data", [])
        if not items:
            print("ℹ️ Tidak ada data lagi di halaman ini.")
            break

        all_ids.extend([item["id"] for item in items])
        print(f"➡️ Halaman {page}, ditemukan {len(items)} ID.")
        page += 1
    print(f"✅ Total ID terkumpul: {len(all_ids)}")
    return all_ids

def get_filtered_details(ids):
    print("🔍 Mengambil detail tiap ID dan filter data...")
    results = []
    for idx, id in enumerate(ids, start=1):
        url = DETAIL_URL.format(id=id)
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = flatten_json(resp.json())
            status = data.get("data_status", "").lower()
            penghargaan = data.get("data_penghargaan_nama", "").lower()
            if status == "approved" and "pancawarsa" in penghargaan:
                results.append(data)
                print(f"  ✅ ID {idx}/{len(ids)}: memenuhi syarat")
            else:
                print(f"  ⚠️ ID {idx}/{len(ids)}: tidak memenuhi syarat")
        else:
            print(f"  ❌ Gagal ambil detail ID {id}, status code: {resp.status_code}")
    print(f"✅ Total data yang lolos filter: {len(results)}")
    return results

def generate_excel(data):
    print("📥 Menghasilkan file Excel dalam memori...")
    selected_fields = [
        "data_nama", "data_status", "data_nta", "data_penghargaan_nama",
        "data_tempat_lahir", "data_tanggal_lahir", "data_jenis_kelamin",
        "data_jabatan_luar", "data_jabatan_dalam", "data_kwarda_nama",
        "data_kwarcab_nama", "data_penghargaans_0_penghargaan_name",
        "data_penghargaans_0_nomor_sk", "data_penghargaans_0_tanggal_terima"
    ]
    rename_map = {
        "data_nama": "Nama", "data_status": "Status", "data_nta": "NTA",
        "data_penghargaan_nama": "Penghargaan", "data_tempat_lahir": "Tempat Lahir",
        "data_tanggal_lahir": "Tanggal Lahir", "data_jenis_kelamin": "Jenis Kelamin",
        "data_jabatan_luar": "Jabatan Luar", "data_jabatan_dalam": "Jabatan Dalam",
        "data_kwarda_nama": "Kwarda", "data_kwarcab_nama": "Kwarcab",
        "data_penghargaans_0_penghargaan_name": "Nama Penghargaan",
        "data_penghargaans_0_nomor_sk": "Nomor SK",
        "data_penghargaans_0_tanggal_terima": "Tanggal Terima"
    }

    df = pd.DataFrame(data)
    if df.empty:
        print("⚠️ Data kosong, tidak dapat buat Excel.")
        return None, None

    df_filtered = df[[col for col in selected_fields if col in df.columns]].copy()

    # Format tanggal
    for col in df_filtered.columns:
        if "tanggal" in col.lower():
            df_filtered[col] = pd.to_datetime(df_filtered[col], errors='coerce', utc=True)
            df_filtered[col] = df_filtered[col].dt.tz_localize(None).dt.strftime('%Y-%m-%d')

    # Rename kolom
    df_filtered.rename(columns=rename_map, inplace=True)

    # Hitung umur
    today = pd.to_datetime(datetime.today().date())
    if "Tanggal Lahir" in df_filtered.columns:
        df_filtered["Umur"] = pd.to_datetime(df_filtered["Tanggal Lahir"], errors='coerce').apply(
            lambda dob: today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day)) if pd.notnull(dob) else None
        )

    # Simpan ke buffer (memory)
    buffer = BytesIO()
    df_filtered.to_excel(buffer, index=False, engine='openpyxl')
    buffer.seek(0)

    nama_kwarcab = df.iloc[0].get("data_kwarcab_nama", "Unknown").replace("/", "-")
    filename = f"Pancawarsa - {nama_kwarcab}.xlsx"

    print(f"✅ File Excel '{filename}' berhasil dibuat di memori.")
    return buffer, filename

def send_to_telegram(file_buffer, filename):
    print(f"📤 Mengirim file '{filename}' ke Telegram...")
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendDocument"
    files = {"document": (filename, file_buffer)}
    data = {"chat_id": TELEGRAM_CHAT_ID, "caption": f"📄 Data Pancawarsa dari {filename}"}
    resp = requests.post(url, data=data, files=files)
    if resp.ok:
        print(f"✅ File '{filename}' berhasil dikirim ke Telegram.")
    else:
        print(f"❌ Gagal kirim Telegram, status code: {resp.status_code}")
        print(f"Response: {resp.text}")

if __name__ == "__main__":
    try:
        ids = get_all_ids()
        if not ids:
            print("⚠️ Tidak ada ID yang ditemukan, proses dihentikan.")
            exit(1)

        data = get_filtered_details(ids)
        if not data:
            print("⚠️ Tidak ada data yang memenuhi kriteria filter, proses dihentikan.")
            exit(1)

        file_buffer, filename = generate_excel(data)
        if file_buffer and filename:
            send_to_telegram(file_buffer, filename)
        else:
            print("⚠️ Gagal membuat file Excel, proses dihentikan.")
            exit(1)
    except Exception as e:
        print(f"❌ Terjadi error: {e}")
        exit(1)
