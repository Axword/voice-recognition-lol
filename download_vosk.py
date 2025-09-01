#!/usr/bin/env python3
"""
Vosk Model Downloader for LoL Voice Controller
Automatically downloads and sets up speech recognition models
"""

import os
import zipfile
import requests
import sys

def download_file(url, filename):
    """Download file with progress bar"""
    try:
        response = requests.get(url, stream=True)
        total_size = int(response.headers.get('content-length', 0))
        
        print(f"📥 Downloading {filename}...")
        print(f"📊 Size: {total_size / (1024*1024):.1f} MB")
        
        with open(filename, 'wb') as file:
            downloaded = 0
            for data in response.iter_content(chunk_size=8192):
                size = file.write(data)
                downloaded += size
                
                # Progress bar
                if total_size > 0:
                    percent = (downloaded / total_size) * 100
                    bar_length = 30
                    filled_length = int(bar_length * downloaded // total_size)
                    bar = '█' * filled_length + '-' * (bar_length - filled_length)
                    print(f"\r[{bar}] {percent:.1f}%", end='', flush=True)
        
        print("\n✅ Download completed!")
        return True
        
    except Exception as e:
        print(f"\n❌ Download failed: {e}")
        return False

def main():
    print("🎯 Vosk Model Downloader for LoL Voice Controller")
    print("=" * 60)
    
    # Model URLs (small models for faster download)
    models = {
        'polish': {
            'url': 'https://alphacephei.com/vosk/models/vosk-model-small-pl-0.22.zip',
            'filename': 'vosk-model-small-pl-0.22.zip',
            'extract_to': 'vosk-model-small-pl-0.22',
            'size': '~42 MB'
        },
        'english': {
            'url': 'https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip',
            'filename': 'vosk-model-small-en-us-0.15.zip',
            'extract_to': 'vosk-model-small-en-us-0.15',
            'size': '~39 MB'
        }
    }
    
    print("Available models:")
    for i, (lang, model) in enumerate(models.items(), 1):
        print(f"{i}. {lang.title()} - {model['extract_to']} ({model['size']})")
    
    try:
        choice = input("\nSelect model to download (1-2) or press Enter for Polish: ").strip()
        if not choice:
            choice = "1"
        
        choice = int(choice)
        if choice == 1:
            selected_model = models['polish']
        elif choice == 2:
            selected_model = models['english']
        else:
            print("❌ Invalid choice")
            return
            
    except ValueError:
        print("❌ Invalid input")
        return
    
    # Check if model already exists
    if os.path.exists(selected_model['extract_to']):
        print(f"✅ Model {selected_model['extract_to']} already exists!")
        return
    
    # Download model
    print(f"\n🎯 Selected: {selected_model['extract_to']}")
    print(f"🌐 URL: {selected_model['url']}")
    
    if download_file(selected_model['url'], selected_model['filename']):
        # Extract model
        print(f"📦 Extracting {selected_model['filename']}...")
        try:
            with zipfile.ZipFile(selected_model['filename'], 'r') as zip_ref:
                zip_ref.extractall('.')
            print("✅ Extraction completed!")
            
            # Clean up zip file
            os.remove(selected_model['filename'])
            print("🗑️  Cleaned up zip file")
            
            # Verify
            if os.path.exists(selected_model['extract_to']):
                print(f"✅ Model {selected_model['extract_to']} is ready to use!")
                print("🎯 You can now run the voice controller!")
                print("💡 The model will be automatically loaded when you start the app")
            else:
                print("❌ Extraction failed!")
                
        except Exception as e:
            print(f"❌ Extraction failed: {e}")
    else:
        print("💡 Please download manually from: https://alphacephei.com/vosk/models")
        print("💡 Extract to project directory and restart")

if __name__ == "__main__":
    main()
