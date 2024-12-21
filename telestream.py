import cv2
from flask import Flask, render_template, Response, request, redirect, url_for, session
import time
from ultralytics import YOLO
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from telegram import Bot
from telegram import InputFile

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Replace with a secure random string

# Load YOLO model
model = YOLO(r'C:\Users\darni\Downloads\yolo11s_segment.pt')

USER_CREDENTIALS = {"admin": "password123"}  # Replace with your credentials

esp32_stream_url = "http://192.168.0.101:81/stream"  # Replace with your ESP32 stream URL

cap = None  # Initialize cap as None

# Retry function for reconnecting the video capture if the stream is interrupted
def reconnect_stream():
    global cap  # Ensure we're modifying the global cap variable
    cap.release() if cap is not None else None
    time.sleep(2)  # Wait before trying again
    cap = cv2.VideoCapture(esp32_stream_url, cv2.CAP_FFMPEG)

def send_email_notification():
    sender_email = "22dm11@psgpolytech.ac.in"
    receiver_email = "darnishcnpm@gmail.com"
    password = "fuck u tony"
    
    msg = MIMEMultipart()
    msg['From'] = sender_email
    msg['To'] = receiver_email
    msg['Subject'] = 'Animal Detected in Stream'
    
    body = "An animal was detected in the stream. Please check the video feed."
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(sender_email, password)
        text = msg.as_string()
        server.sendmail(sender_email, receiver_email, text)
        server.quit()
        print("Email sent successfully.")
    except Exception as e:
        print(f"Failed to send email: {e}")

def send_to_telegram(video_path):
    telegram_token = '8165959940:AAFF4ZkA6gL5Hm0JCGaNY2sPfheMoIeocP8'
    chat_id = '1028492554'
    
    bot = Bot(token=telegram_token)
    try:
        with open(video_path, 'rb') as video_file:
            bot.send_video(chat_id=chat_id, video=InputFile(video_file, filename='animal_detection_video.mp4'))
        print(f"Video sent to Telegram: {video_path}")
    except Exception as e:
        print(f"Failed to send video: {e}")

def generate_frames():
    global cap  # Ensure we're using the global cap
    while True:
        if cap is None or not cap.isOpened():
            reconnect_stream()  # Reconnect if cap is not valid
        
        ret, frame = cap.read()
        if not ret:
            print("Error: Failed to read frame, reconnecting...")
            reconnect_stream()
            continue

        # Perform object detection on the frame using YOLO
        results = model(frame)

        # Flag to track if animal is detected
        animal_detected = False

        # Loop through detected objects and draw boxes
        for result in results:
            boxes = result.boxes  # Extract bounding box information
            
            # Annotate each detected object
            for box in boxes:
                # Get coordinates, class, and confidence
                x1, y1, x2, y2 = map(int, box.xyxy[0])  # Bounding box corners
                cls = int(box.cls[0])  # Class index
                conf = box.conf[0].item()  # Confidence score
                
                # Check if the detected object is an animal (assuming you know the class indexes)
                if cls in [0, 16, 17]:  # Example: classes for animals, replace with actual ones
                    label = f"{model.names[cls]} {conf:.2f}"
                    # Draw the bounding box and label
                    color = (0, 255, 0)  # Box color (green)
                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                    cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, color, 2)

                    animal_detected = True  # Set the flag if animal is detected

        # Save the video if animal is detected
        if animal_detected:
            timestamp = time.time()
            video_filename = f"animal_detection_{int(timestamp)}.mp4"
            out = cv2.VideoWriter(video_filename, cv2.VideoWriter_fourcc(*'mp4v'), 20.0, (640, 480))
            out.write(frame)
            out.release()
            send_email_notification()  # Send email notification
            send_to_telegram(video_filename)  # Send video to Telegram bot

        # Encode frame as JPEG
        ret, jpeg = cv2.imencode('.jpg', frame)
        if not ret:
            print("Error: Failed to encode frame")
            break

        # Yield the frame for streaming
        frame = jpeg.tobytes()
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n\r\n')

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

# Video feed with object detection
@app.route('/video_feed')
def video_feed():
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

if __name__ == "__main__":
    reconnect_stream()  # Ensure the stream is established before running the app
    app.run(debug=True, host="0.0.0.0", port=5000)
