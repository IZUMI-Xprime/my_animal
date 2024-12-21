from flask import Flask, render_template, request, redirect, url_for, session, Response
import cv2

app = Flask(__name__)
app.secret_key = "your_secret_key"  # Replace with a secure random string

camera = cv2.VideoCapture(0)  # Replace 0 with a video file path if needed

USER_CREDENTIALS = {"admin": "password123"}  # Replace with your credentials


def generate_frames():
    while True:
        success, frame = camera.read()
        if not success:
            break
        else:
            ret, buffer = cv2.imencode('.jpg', frame)
            frame = buffer.tobytes()
            yield (b'--frame\r\n'
                   b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')


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
    if 'user' not in session:
        return redirect(url_for('login'))
    return Response(generate_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
