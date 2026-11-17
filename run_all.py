"""
run_all.py
----------
الملف الرئيسي لتشغيل الكاميرا والذكاء الاصطناعي مع فتح الداش بورد في المتصفح تلقائياً بضغطة زر واحدة.
"""

import os
import sys

# إضافة جذر المشروع
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.append(ROOT_DIR)

if __name__ == "__main__":
    print("=" * 60)
    print(" 🚀 جاري تشغيل نظام المواقف الذكي (الكاميرا + الذكاء الاصطناعي + الداش بورد)...")
    print("=" * 60)
    
    # استدعاء ملف النظام الحي
    from src import live_system
