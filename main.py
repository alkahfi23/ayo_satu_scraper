import requests
import time
import pandas as pd
from datetime import datetime
import os

# Konfigurasi
BASE_LIST_URL = "https://passport.ayosatu.id/api/tpgp/pengajuan"
DETAIL_URL = "https://passport.ayosatu.id/api/tpgp/pengajuan/{id}/detail"
TGP_ID = "3236c0b6-bbda-4029-85e3-ccb80e87995f"
SEKOLAH_ID = "4382"
LIMIT = 10

headers = {
    "Accept": "application/json",
    "Authorization": os.getenv("AUTH_TOKEN")  # Gunakan ENV variable di Railway
}

# Flatten JSON
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
            print(f"❌ Gagal ambil page {page}, status: {resp.status_code}")
            break

        items = resp.json().get("data", [])
        if not items:
            break

        all_ids.extend([item["id"] for item in items])
        print(f"✅ Page {page} - Ambil {len(items)} ID")
        page += 1
        time.sleep(0.3)
    return all_ids

def get_filtered_details(ids):
    results = []
    for id in ids:
        url = DETAIL_URL.format(id=id)
        resp = requests.get(url, headers=headers)
        if resp.status_code == 200:
            data = flatten_json(resp.json())
            status = data.get("data_status", "").lower()
            penghargaan = data.get("data_penghargaan_nama", "").lower()

            if status == "approved" and "pancawarsa" in penghargaan:
                results.append(data)
                print(f"✔ Approved & Pancawarsa: {id}")
            else:
                print(f"⚠️ Skip: {id} (status: {status}, penghargaan: {penghargaan})")
        else:
            print(f"❌ Gagal ambil detail ID {id}")
        time.sleep(0.3)
    return results

def save_filtered_to_files(data):
    selected_fields = [
        "data_nama",
        "data_status",
        "data_nta",
        "data_penghargaan_nama",
        "data_tempat_lahir",
        "data_tanggal_lahir",
        "data_jenis_kelamin",
        "data_jabatan_luar",
        "data_jabatan_dalam",
        "data_kwarda_nama",
        "data_kwarcab_nama",
        "data_penghargaans_0_penghargaan_name",
        "data_penghargaans_0_nomor_sk",
        "data_penghargaans_0_tanggal_terima"
    ]

    rename_map = {
        "data_nama": "Nama",
        "data_status": "Status",
        "data_nta": "NTA",
        "data_penghargaan_nama": "Penghargaan",
        "data_tempat_lahir": "Tempat Lahir",
        "data_tanggal_lahir": "Tanggal Lahir",
        "data_jenis_kelamin": "Jenis Kelamin",
        "data_jabatan_luar": "Jabatan Luar",
        "data_jabatan_dalam": "Jabatan Dalam",
        "data_kwarda_nama": "Kwarda",
        "data_kwarcab_nama": "Kwarcab",
        "data_penghargaans_0_penghargaan_name": "Nama Penghargaan",
        "data_penghargaans_0_nomor_sk": "Nomor SK",
        "data_penghargaans_0_tanggal_terima": "Tanggal Terima"
    }

    df = pd.DataFrame(data)
    if df.empty:
        print("⚠️ Tidak ada data yang sesuai ditemukan.")
        return

    nama_kwarcab = df.iloc[0].get("data_kwarcab_nama", "Unknown Kwarcab")
    nama_kwarcab = nama_kwarcab.strip().replace("/", "-").replace(":", "-")

    csv_filename = f"pancawarsa_{nama_kwarcab}.csv"
    xlsx_filename = f"Pancawarsa - {nama_kwarcab}.xlsx"

    # Filter dan rename kolom
    available_fields = [col for col in selected_fields if col in df.columns]
    df_filtered = df[available_fields].rename(columns=rename_map)

    # Format tanggal dan umur
    today = pd.to_datetime(datetime.today().date())
    if "Tanggal Lahir" in df_filtered.columns:
        df_filtered["Tanggal Lahir"] = pd.to_datetime(df_filtered["Tanggal Lahir"], errors='coerce')
        df_filtered["Umur"] = df_filtered["Tanggal Lahir"].apply(
            lambda dob: today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            if pd.notnull(dob) else None
        )

    # Simpan ke CSV
    df_filtered.to_csv(csv_filename, index=False)
    print(f"📁 CSV disimpan: {csv_filename}")

    # Simpan ke Excel
    try:
        df_filtered.to_excel(xlsx_filename, index=False, engine='openpyxl')
        print(f"✅ Excel berhasil disimpan: {xlsx_filename}")
    except Exception as e:
        print(f"❌ Gagal simpan Excel: {e}")

# Eksekusi
if __name__ == "__main__":
    all_ids = get_all_ids()
    print(f"🔢 Total ID ditemukan: {len(all_ids)}")
    data = get_filtered_details(all_ids)
    print(f"✅ Data valid: {len(data)}")
    save_filtered_to_files(data)
