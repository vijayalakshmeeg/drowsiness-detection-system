import cv2
import mediapipe as mp
import math
import time
import pygame
import numpy as np
from datetime import datetime
from twilio.rest import Client
from django.shortcuts import render, redirect
from django.http import StreamingHttpResponse, JsonResponse
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import login, logout
from django.contrib.auth.models import User
from .models import EventLog

# ---------- CONFIG ----------
EAR_THRESHOLD = 0.25
MAR_THRESHOLD = 0.80
EYE_FRAMES = 20
YAWN_FRAMES = 8
ALERT_DURATION = 15
YAWN_COOLDOWN = 5

# ---------- SHARED STATS ----------
stats = {
    "ear": 0.35,
    "mar": 0.25,
    "is_drowsy": False,
    "is_yawning": False,
    "drowsy_count": 0,
    "yawn_count": 0,
}

# ---------- TWILIO ----------
import os
ACCOUNT_SID = os.environ.get('TWILIO_ACCOUNT_SID', 'ACXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX')
AUTH_TOKEN  = os.environ.get('TWILIO_AUTH_TOKEN', 'your_auth_token_here')
TWILIO_FROM = os.environ.get('TWILIO_FROM', '+15075196947')
ANUSHRI_NUMBER = os.environ.get('ANUSHRI_NUMBER', '+918310746762')

client = Client(ACCOUNT_SID, AUTH_TOKEN)

# ---------- AUDIO ----------
pygame.mixer.init()

def generate_beep(frequency=1000, duration=0.5, sample_rate=44100):
    t = np.linspace(0, duration, int(sample_rate * duration), False)
    wave = np.sin(frequency * 2 * np.pi * t)
    wave = (wave * 32767).astype(np.int16)
    return pygame.mixer.Sound(wave)

wakeup = generate_beep(800, 1.0)
yawn_beep = generate_beep(1200, 0.3)

# ---------- MEDIAPIPE ----------
mp_face = mp.solutions.face_mesh
face_mesh = mp_face.FaceMesh(refine_landmarks=True)

LEFT_EYE = [33, 160, 158, 133, 153, 144]
RIGHT_EYE = [362, 385, 387, 263, 373, 380]
MOUTH_UP, MOUTH_DOWN, MOUTH_LEFT, MOUTH_RIGHT = 13, 14, 87, 317

# ---------- FUNCTIONS ----------
def ear_ratio(lms, eye, w, h):
    pts = [(int(lms[i].x*w), int(lms[i].y*h)) for i in eye]
    A = math.dist(pts[1], pts[5])
    B = math.dist(pts[2], pts[4])
    C = math.dist(pts[0], pts[3])
    return (A+B)/(2*C)

def mar_ratio(lms, w, h):
    top = (int(lms[MOUTH_UP].x*w), int(lms[MOUTH_UP].y*h))
    bottom = (int(lms[MOUTH_DOWN].x*w), int(lms[MOUTH_DOWN].y*h))
    left = (int(lms[MOUTH_LEFT].x*w), int(lms[MOUTH_LEFT].y*h))
    right = (int(lms[MOUTH_RIGHT].x*w), int(lms[MOUTH_RIGHT].y*h))
    return math.dist(top,bottom)/math.dist(left,right)

def log_event_to_db(user_id, event_type, details=""):
    try:
        user = User.objects.get(id=user_id) if user_id else None
        EventLog.objects.create(user=user, event_type=event_type, details=details)
        print(f"Logged to DB: {event_type} - {details} (User: {user})")
    except Exception as e:
        print(f"Failed to log to DB: {e}")

def send_sms_to_anushri(user_id):
    message_body = (
        "⚠️ ALERT: Your family member/driver seems to be drowsy for 15 seconds. "
        "Please check or make a call immediately."
    )
    try:
        client.messages.create(
            body=message_body,
            from_=TWILIO_FROM,
            to=ANUSHRI_NUMBER
        )
        print(f"✅ SMS alert successfully sent to Anushri ({ANUSHRI_NUMBER})")
        log_event_to_db(user_id, "SMS_SENT", f"To: {ANUSHRI_NUMBER}")
    except Exception as e:
        print(f"⚠️ SMS sending failed: {e}")

def generate_frames(user_id=None):
    cap = cv2.VideoCapture(0)
    if not cap.isOpened():
        print("❌ Camera not found.")
        return

    closed_frames = 0
    yawn_frames = 0
    drowsy_start = None
    last_yawn_time = 0
    alert_active = False
    sms_sent = False
    drowsy_flagged = False

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        h, w, _ = frame.shape
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        res = face_mesh.process(rgb)

        if res.multi_face_landmarks:
            lms = res.multi_face_landmarks[0].landmark
            ear_l = ear_ratio(lms, LEFT_EYE, w, h)
            ear_r = ear_ratio(lms, RIGHT_EYE, w, h)
            ear_avg = (ear_l + ear_r) / 2
            mar_val = mar_ratio(lms, w, h)

            stats["ear"] = ear_avg
            stats["mar"] = mar_val

            # ----- DROWSINESS -----
            if ear_avg < EAR_THRESHOLD:
                closed_frames += 1
                if closed_frames > EYE_FRAMES:
                    cv2.putText(frame, "⚠️ DROWSY! KEEP EYES OPEN", (80, 100),
                                cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 3)
                    stats["is_drowsy"] = True
                    if not alert_active:
                        if wakeup: wakeup.play(-1)
                        alert_active = True
                        drowsy_start = time.time()
                        if not drowsy_flagged:
                            stats["drowsy_count"] += 1
                            drowsy_flagged = True
                    elif time.time() - drowsy_start >= ALERT_DURATION and not sms_sent:
                        send_sms_to_anushri(user_id)
                        sms_sent = True
                        if wakeup: wakeup.stop()
                        log_event_to_db(user_id, "SMS_ALERT_CONTINUE", "SMS sent, continuing detection")

            else:
                closed_frames = 0
                stats["is_drowsy"] = False
                drowsy_flagged = False
                if alert_active:
                    if wakeup: wakeup.stop()
                    alert_active = False
                sms_sent = False

            # ----- YAWNING -----
            if mar_val > MAR_THRESHOLD:
                if time.time() - last_yawn_time > YAWN_COOLDOWN:
                    yawn_frames += 1
                    if yawn_frames > YAWN_FRAMES:
                        cv2.putText(frame, "😮 Yawning detected — Be aware!",
                                    (70, 170), cv2.FONT_HERSHEY_SIMPLEX, 0.9,
                                    (0, 165, 255), 3)
                        stats["is_yawning"] = True
                        stats["yawn_count"] += 1
                        if yawn_beep: yawn_beep.play()
                        log_event_to_db(user_id, "YAWNING_DETECTED")
                        last_yawn_time = time.time()
            else:
                yawn_frames = 0
                stats["is_yawning"] = False

            cv2.putText(frame, f"EAR:{ear_avg:.2f}  MAR:{mar_val:.2f}",
                        (20, 40), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)

        ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

# ---------- DJANGO VIEWS ----------
@login_required(login_url='login')
def index(request):
    return render(request, 'index.html')

@login_required(login_url='login')
def video_feed(request):
    return StreamingHttpResponse(generate_frames(request.user.id), content_type='multipart/x-mixed-replace; boundary=frame')

@login_required(login_url='login')
def get_stats(request):
    return JsonResponse(stats)

def register_view(request):
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect('index')
    else:
        form = UserCreationForm()
    return render(request, 'register.html', {'form': form})

def login_view(request):
    if request.method == 'POST':
        form = AuthenticationForm(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            return redirect('index')
    else:
        form = AuthenticationForm()
    return render(request, 'login.html', {'form': form})

def logout_view(request):
    logout(request)
    return redirect('login')
