# 🚗 Drowsiness Detection System

## 📌 Project Overview
The Drowsiness Detection System is a real-time web application that detects driver drowsiness using computer vision. It monitors eye movements through webcam and triggers an alarm when signs of drowsiness are detected. This helps prevent accidents and improves road safety.

---

## 🛠️ Technologies Used
- Python
- Django
- OpenCV
- MediaPipe
- NumPy
- Pygame
- HTML
- CSS

---

## ⚙️ Features
- Real-time eye detection using webcam
- Drowsiness detection using eye blinking analysis
- Alarm alert when user feels sleepy
- Live video streaming using Django
- Simple and user-friendly interface

---

## 📥 Installation & Setup

### 1. Install Python
Make sure Python 3.10+ is installed.

Check version:
```bash
python --version

2. Create Virtual Environment
python -m venv venv

Activate environment:

Windows:

venv\Scripts\activate

Mac/Linux:

source venv/bin/activate
3. Install Required Libraries
pip install django opencv-python mediapipe numpy pygame
Go to Project Directory
cd your_project_folder
5. Run Migrations
python manage.py migrate
6. Create Superuser (Optional)
python manage.py createsuperuser
7. Run Server
python manage.py runserver
🌐 Open Project in Browser
http://127.0.0.1:8000/
