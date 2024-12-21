import cv2
from flask import Flask, render_template, Response, request, redirect, url_for, session
import time
from ultralytics import YOLO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from telegram import Bot, InputFile
from threading import Thread
import queue
import os
from datetime import datetime

app = Flask(__name__)
app.secret_key = os.getenv("SECRET_KEY", "your_secret_key")  # Secure secret key

# Load YOLO model
model = YOLO(r'C:\Users\darni\Downloads\yolo11s_segment.pt')

# Replace with your credentials and load from environment variables for security
USER_CREDENTIALS = {"admin": "password123"}
EMAIL_SENDER = os.getenv("EMAIL_SENDER", "22dm11@psgpolytech.ac.in")
EMAIL_RECEIVER = os.getenv("EMAIL_RECEIVER", "darnishcnpm@gmail.com")
#EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD", "fuck u tony")
EMAIL_PASSWORD = "kxml fjog ipep nays"  # Replace with your Gmail App Password

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8165959940:AAFF4ZkA6gL5Hm0JCGaNY2sPfheMoIeocP8")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "1028492554")

esp32_stream_url = "http://192.168.0.101:81/stream"  # Replace with your ESP32 stream URL

cap = None  # Initialize cap as None
frame_queue = queue.Queue(maxsize=5)  # Queue for YOLO processing
video_writer = None  # VideoWriter object for saving video clips
clip_duration = 60  # Duration of each video clip in seconds
clip_start_time = None  # Start time for the current video clip


def reconnect_stream(retries=5, delay=2):
    global cap
    for attempt in range(retries):
        if cap is not None:
            cap.release()
        cap = cv2.VideoCapture(esp32_stream_url, cv2.CAP_FFMPEG)
        if cap.isOpened():
            print("Reconnected to the stream successfully.")
            return
        print(f"Retrying connection... ({attempt + 1}/{retries})")
        time.sleep(delay)
    print("Failed to reconnect to the video stream.")


def send_email_notification(video_path):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_SENDER
    msg['To'] = EMAIL_RECEIVER
    msg['Subject'] = 'Animal Detected in Stream'
    body = f"An animal was detected in the stream. Video file: {video_path}"
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_SENDER, EMAIL_PASSWORD)
        text = msg.as_string()
        server.sendmail(EMAIL_SENDER, EMAIL_RECEIVER, text)
        server.quit()
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")


def send_to_telegram(video_path):
    bot = Bot(token=TELEGRAM_TOKEN)
    try:
        with open(video_path, 'rb') as video_file:
            bot.send_video(chat_id=TELEGRAM_CHAT_ID, video=InputFile(video_file, filename='animal_detection_video.mp4'))
        print(f"Video sent to Telegram: {video_path}")
    except Exception as e:
        print(f"Failed to send video: {e}")


def save_and_notify():
    global video_writer, clip_start_time
    if video_writer is not None:
        video_writer.release()
        video_writer = None
        clip_start_time = None

        # Generate a timestamped filename
        video_filename = f"animal_detection_{int(time.time())}.mp4"
        
        # Verify if the file exists before sending notifications
        if os.path.exists(video_filename):
            print(f"Sending notifications for file: {video_filename}")
            send_email_notification(video_filename)
            send_to_telegram(video_filename)
        else:
            print(f"Error: File not found - {video_filename}")


def generate_frames():
    global cap, video_writer, clip_start_time
    while True:
        if cap is None or not cap.isOpened():
            reconnect_stream()

        ret, frame = cap.read()
        if not ret:
            print("Failed to read frame, reconnecting...")
            reconnect_stream()
            continue

        # Add timestamp to the frame
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cv2.putText(frame, timestamp, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 255), 2)

        # Start a new video clip if needed
        if video_writer is None or (time.time() - clip_start_time) >= clip_duration:
            if video_writer is not None:
                save_and_notify()
            clip_start_time = time.time()
            frame_height, frame_width, _ = frame.shape
            video_filename = f"animal_detection_{int(clip_start_time)}.mp4"
            video_writer = cv2.VideoWriter(video_filename, cv2.VideoWriter_fourcc(*'mp4v'), 20.0, (frame_width, frame_height))
            print(f"Started new video clip: {video_filename}")

        # Write frame to video
        if video_writer is not None:
            video_writer.write(frame)

        # Perform object detection
        results = model(frame)
        for result in results:
            boxes = result.boxes
            for box in boxes:
                x1, y1, x2, y2 = map(int, box.xyxy[0])  # Bounding box corners
                cls = int(box.cls[0])  # Class index
                conf = box.conf[0].item()  # Confidence score
                
                # Check if the detected object is an animal (replace with actual classes)
                if cls in [0, 16, 17]:
                    label = f"{model.names[cls]} {conf:.2f}"
                    color = (0, 255, 0)  # Box color (green)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

        # Encode the frame for streaming
        ret, jpeg = cv2.imencode('.jpg', frame)
        if not ret:
            print("Error: Failed to encode frame")
            break

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + jpeg.tobytes() + b'\r\n\r\n')


@app.route('/')
def welcome():
    return render_template('welcome.html', title="Welcome")


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        user_id = request.form['user_id']
        password = request.form['password']
        if user_id in USER_CREDENTIALS and USER_CREDENTIALS[user_id] == password:
            session['user'] = user_id
            return redirect(url_for('index'))
        else:
            return "Invalid credentials. Please try again.", 401
    return render_template('login.html', title="Login")


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))


@app.route('/index')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('index.html', title="Video Stream")


@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == "__main__":
    reconnect_stream()
    app.run(debug=True, host="0.0.0.0", port=5000)
