import sys
import os
import shutil
import time
import threading
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler

import pystray
from pystray import MenuItem as item
from PIL import Image, ImageDraw

import fitz  # PyMuPDF
import pytesseract

# ==========================================
# 1. KONFIGURASI TESSERACT BUNDLING
# ==========================================
def get_base_path() :
    
    is_frozen = getattr(sys, 'frozen', False)
    
    if is_frozen :
        return sys._MEIPASS
    else :
        return os.path.dirname(os.path.abspath(__file__))

base_path = get_base_path()

tesseract_dir = os.path.join(base_path, 'Tesseract-OCR')

tesseract_exe = os.path.join(tesseract_dir, 'tesseract.exe')

pytesseract.pytesseract.tesseract_cmd = tesseract_exe


# ==========================================
# 2. KONFIGURASI FOLDER (UNIVERSAL)
# ==========================================
USER_PATH = os.path.expanduser("~")

ONEDRIVE_PATH = os.path.join(USER_PATH, "OneDrive")

# Cerdas mendeteksi apakah laptop tujuan menggunakan OneDrive atau tidak
if os.path.exists(ONEDRIVE_PATH) :
    DIR_DOCS = os.path.join(ONEDRIVE_PATH, "Documents")
    DIR_PICS = os.path.join(ONEDRIVE_PATH, "Pictures")
    DIR_DESKTOP = os.path.join(ONEDRIVE_PATH, "Desktop")
else :
    DIR_DOCS = os.path.join(USER_PATH, "Documents")
    DIR_PICS = os.path.join(USER_PATH, "Pictures")
    DIR_DESKTOP = os.path.join(USER_PATH, "Desktop")

DIR_DOWN = os.path.join(USER_PATH, "Downloads")

DIR_MUSIC = os.path.join(USER_PATH, "Music")

DIR_VID = os.path.join(USER_PATH, "Videos")

SOURCES = \
[
    DIR_DESKTOP, 
    DIR_DOWN, 
    DIR_DOCS, 
    DIR_PICS, 
    DIR_MUSIC, 
    DIR_VID
]

IGNORE_EXTENSIONS = \
[
    '.py', 
    '.java', 
    '.cpp', 
    '.c', 
    '.h', 
    '.js', 
    '.html', 
    '.css', 
    '.php', 
    '.sql', 
    '.kt', 
    '.ini', 
    '.lnk'
]

AI_DESTINATIONS = \
{
    "Struk_dan_Keuangan": os.path.join(DIR_DOCS, "Keuangan_Paperless"),
    "Materi_Kuliah": os.path.join(DIR_DOCS, "Materi_dan_Tugas_Kuliah"),
    "Dokumen_Penting": os.path.join(DIR_DOCS, "Dokumen_Penting_Lainnya")
}


# ==========================================
# 3. MESIN AI PEMBACA ISI (PDF & GAMBAR)
# ==========================================
def extract_text_from_pdf(file_path) :
    
    try :
        doc = fitz.open(file_path)
        text = ""
        for page_num in range(min(2, doc.page_count)) :
            page = doc.load_page(page_num)
            text += page.get_text("text").lower()
        return text
    except Exception :
        return ""


def extract_text_from_image(file_path) :
    
    try :
        img = Image.open(file_path)
        text = pytesseract.image_to_string(img).lower()
        return text
    except Exception :
        return ""


def analyze_with_ai(file_path, file_name, ext) :
    
    extracted_text = ""
    
    if ext == '.pdf' :
        extracted_text = extract_text_from_pdf(file_path)
        
    elif ext in ['.jpg', '.jpeg', '.png'] :
        extracted_text = extract_text_from_image(file_path)

    # --- Logika Otak AI ---
    if any(keyword in extracted_text for keyword in ['total', 'rp', 'cash', 'kembali', 'struk', 'invoice']) :
        return AI_DESTINATIONS["Struk_dan_Keuangan"]
        
    if any(keyword in extracted_text for keyword in ['mahasiswa', 'dosen', 'tugas', 'matakuliah', 'algoritma', 'sistem', 'rekayasa']) :
        return AI_DESTINATIONS["Materi_Kuliah"]

    return None


# ==========================================
# 4. LOGIKA SORTIR UTAMA
# ==========================================
def get_destination_folder(file_path, name) :
    
    ext = os.path.splitext(name)[1].lower()

    ai_decision = analyze_with_ai(file_path, name, ext)
    
    if ai_decision is not None :
        return ai_decision

    if ext in ['.pdf', '.docx', '.xlsx', '.pptx', '.txt'] :
        return os.path.join(DIR_DOCS, "Dokumen_Umum")
        
    if ext in ['.jpg', '.jpeg', '.png', '.svg', '.webp'] :
        return os.path.join(DIR_PICS, "Gambar_Tersortir")
        
    if ext in ['.mp4', '.mkv', '.mp3', '.wav'] :
        return os.path.join(DIR_VID, "Media_Tersortir")
        
    if ext in ['.exe', '.msi', '.zip', '.rar'] :
        return os.path.join(DIR_DOWN, "Aplikasi_dan_Arsip")

    return os.path.join(DIR_DOWN, "Lain_lain")


# ==========================================
# 5. CORE ENGINE (PEMINDAH FILE)
# ==========================================
def move_file(file_path, name) :
    
    ext = os.path.splitext(name)[1].lower()
    
    if ext in IGNORE_EXTENSIONS or ext in ['.crdownload', '.part', '.tmp'] or name.startswith('.') :
        return

    time.sleep(1) 

    dest_folder = get_destination_folder(file_path, name)
    
    if os.path.dirname(file_path) == dest_folder :
        return

    if not os.path.exists(dest_folder) :
        os.makedirs(dest_folder)

    filename, extension = os.path.splitext(name)
    
    counter = 1
    
    unique_name = name
    
    while os.path.exists(os.path.join(dest_folder, unique_name)) :
        unique_name = f"{filename}({counter}){extension}"
        counter += 1
        
    dest_path = os.path.join(dest_folder, unique_name)

    try :
        shutil.move(file_path, dest_path)
        print(f"✅ AI Tersortir: [{name}] -> [{os.path.basename(dest_folder)}]")
    except Exception as e :
        pass


# ==========================================
# 6. WATCHDOG & SYSTEM TRAY
# ==========================================
class MoverHandler(FileSystemEventHandler) :
    
    def on_modified(self, event) :
        if not event.is_directory :
            move_file(event.src_path, os.path.basename(event.src_path))
            
    def on_created(self, event) :
        if not event.is_directory :
            move_file(event.src_path, os.path.basename(event.src_path))


observer = None

def start_background_watcher() :
    
    global observer
    
    event_handler = MoverHandler()
    
    observer = Observer()
    
    for path in SOURCES :
        if os.path.exists(path) :
            observer.schedule(event_handler, path, recursive=False)
            
    observer.start()
    
    try :
        while observer.is_alive() :
            time.sleep(1)
    except Exception :
        pass


def create_image() :
    
    image = Image.new('RGB', (64, 64), color = (41, 128, 185))
    
    draw = ImageDraw.Draw(image)
    
    draw.ellipse((16, 16, 48, 48), fill=(255, 255, 255))
    
    return image


def quit_action(icon, item) :
    
    global observer
    
    print("Mematikan sistem...")
    
    if observer :
        observer.stop()
        observer.join()
        
    icon.stop()


def setup_tray() :
    
    menu = pystray.Menu(
        item('Sistem Organiser Aktif', lambda: None),
        pystray.Menu.SEPARATOR,
        item('Matikan Sistem (Quit)', quit_action)
    )
    
    icon = pystray.Icon("FileOrganizer", create_image(), "Smart AI Organizer", menu)
    
    icon.run()


if __name__ == "__main__" :
    
    print("🚀 Sistem AI Organizer berjalan di latar belakang! (Mode Universal)")
    
    watcher_thread = threading.Thread(target=start_background_watcher, daemon=True)
    
    watcher_thread.start()
    
    setup_tray()