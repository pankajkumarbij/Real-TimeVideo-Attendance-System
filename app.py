from flask import *
from flask_mysqldb import MySQL
from flask_session import Session
import cv2
import numpy as np
import face_recognition
import os
from datetime import datetime
from werkzeug.utils import secure_filename

UPLOAD_FOLDER = '/home/pankajkumarbij/projects/Real-Time Video-Based Attendance System'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg'}

ALLOWED_EXTENSIONS1 = {'mp4', 'avi', 'webm', 'flv', 'mkv', 'mov', 'wmv', 'avchd'}

app=Flask(__name__)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = 'Pankaj@123'
app.config['MYSQL_DB'] = 'vams'

mysql = MySQL(app)

app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"

Session(app)

path = 'regImg'
images = []
classNames = []
classRolls = []
myList = os.listdir(path)

for cl in myList:
    currImg = cv2.imread(f'{path}/{cl}')
    images.append(currImg)
    filename = os.path.splitext(cl)[0]
    fn = filename.split(".")
    classNames.append(fn[0])
    classRolls.append(fn[1])

def findEncodings(images):
    encodeList = []
    for img in images:
        img = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        encode = face_recognition.face_encodings(img)[0]
        encodeList.append(encode)
    return encodeList

encodeListKnown = findEncodings(images)

def makeAttendence(name, roll, email, batch, sem, subject):
    with app.test_request_context():
        now = datetime.now()
        dtString = now.strftime('%H:%M:%S')
        date = now.strftime("%Y-%m-%d")
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM attendence where email=%s and date=%s and batch=%s and sem=%s and roll=%s and subject=%s", (email, date, batch, sem, roll, subject))
        data = cur.fetchall()
        if len(data)==0:
            cur.execute("INSERT INTO attendence(email, date, batch, sem, name, roll, subject, time) VALUES (%s ,%s, %s, %s, %s, %s, %s, %s)", (email, date, batch, sem, name, roll, subject, dtString))
        mysql.connection.commit()
        cur.close()

class Video(object):
    def __init__(self, email, batch, sem, subject, video):
        self.video=cv2.VideoCapture(video)
        self.email=email
        self.batch=batch
        self.sem=sem
        self.subject=subject
    def __del__(self):
        self.video.release()
    def get_frame(self):
        ret,img=self.video.read()
        imgS = cv2.resize(img,(0,0),None,0.25,0.25)
        imgS = cv2.cvtColor(imgS, cv2.COLOR_BGR2RGB)
        facesCurrFrame= face_recognition.face_locations(imgS)
        encodeCurrFrame = face_recognition.face_encodings(imgS, facesCurrFrame)
    
        for encodeFace,faceLoc in zip(encodeCurrFrame, facesCurrFrame):
            matches = face_recognition.compare_faces(encodeListKnown, encodeFace)
            faceDist = face_recognition.face_distance(encodeListKnown, encodeFace)
            matchIndex = np.argmin(faceDist)

            if(matches[matchIndex]):
                name  = classNames[matchIndex].upper()
                roll = classRolls[matchIndex]
                y1,x2,y2,x1 = faceLoc
                y1,x2,y2,x1 = y1*4,x2*4,y2*4,x1*4;
                cv2.rectangle(img,(x1,y1),(x2,y2),(0,255,0),2)
                cv2.rectangle(img,(x1,y2-35),(x2,y2),(0,255,0),cv2.FILLED)
                cv2.putText(img,name,(x1+6,y2-6),cv2.FONT_HERSHEY_COMPLEX,1,(255,255,255),2)
                makeAttendence(name, roll, self.email, self.batch, self.sem, self.subject)
        ret,jpg=cv2.imencode('.jpg',img)
        return jpg.tobytes()

@app.route('/')
def index():
    return render_template('index.html')

def gen(camera):
    while True:
        frame=camera.get_frame()
        yield(b'--frame\r\n'
        b'Content-Type:  image/jpeg\r\n\r\n' + frame +
        b'\r\n\r\n')

@app.route('/video')

def video():
    video = session.get("video")
    email = session.get("email")
    batch = session.get("batch")
    sem = session.get("sem")
    subject = session.get("sub")
    if video==None:
        video=0
    return Response(gen(Video(email, batch, sem, subject, video)),
    mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == "POST":
        details = request.form
        name = details['name']
        email = details['email']
        password = details['password']
        cpassword = details['cpassword']
        sc = details['sc']
        if(sc!='12345'):
            return render_template('register.html', message="Error!! You are not auth to register", success=False)
        if(password!=cpassword):
            return render_template('register.html', message="Error!! Password is not matched", success=False)
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO user(name, email, password) VALUES (%s, %s, %s)", (name, email, password))
        mysql.connection.commit()
        cur.close()
        return render_template('login.html', message="Success!! Registered, Now you can login", success=True)
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == "POST":
        details = request.form
        email = details['email']
        password = details['password']
        cur = mysql.connection.cursor()
        cur.execute("SELECT email, password FROM user")
        data = cur.fetchall()
        for row in data:
            if email == row[0] and password == row[1]:
                session['email'] = email
                return render_template('index.html', message="Success!! logined", success=True)
        return render_template('login.html', message="Error!! Data is not matched", success=False)
    return render_template('login.html')

def allowed_file2(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS1

@app.route('/makeattendence', methods=['GET', 'POST'])
def make_attendence():
    if not session.get("email"):
        return redirect("/login")
    if request.method == 'POST':
        file = request.files['file']
        if file and allowed_file2(file.filename):
            filename = secure_filename("video."+file.filename.rsplit('.', 1)[1].lower())
            os.remove('video/'+filename)
            file.save(os.path.join(app.config['UPLOAD_FOLDER']+"/video", filename))
            session['video'] = "video/"+filename
        details = request.form
        batch = details['batch']
        sem = details['sem']
        sub = details['sub']
        session['batch'] = batch
        session['sem'] = sem
        session['sub'] = sub
    return render_template('make_attendence.html')

@app.route('/viewattendence')
def view_attendence():
    if not session.get("email"):
        return redirect("/login")
    if not session.get("batch"):
        return render_template('view_attendence.html')
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    email = session.get("email")
    batch = session.get("batch")
    sem = session.get("sem")
    sub = session.get("sub")
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM attendence where email=%s and date=%s and batch=%s and sem=%s and subject=%s", (email, date, batch, sem, sub))
    data = cur.fetchall()
    rolls = []
    for row in data:
        rolls.append(row[6])
    tcur = mysql.connection.cursor()
    tcur.execute("SELECT * FROM student where batch=%s and roll not in %s", (batch, rolls))
    tdata = tcur.fetchall()
    return render_template('view_attendence.html', data=data, total=len(data), tdata=tdata, ttotal=len(tdata))

@app.route('/viewallattendence')
def view_all_attendence():
    if not session.get("email"):
        return redirect("/login")
    email = session.get("email")
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM attendence where email=%s", [email])
    data = cur.fetchall()
    return render_template('view_all_attendence.html', data=data)

def allowed_file(filename):
    return '.' in filename and \
           filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@app.route('/registerstudent',methods=['GET', 'POST'])
def register_student():
    if not session.get("email"):
        return redirect("/login")
    if request.method == 'POST':
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)
        details = request.form
        name = details['name']
        roll = details['roll']
        batch = details['batch']
        file = request.files['file']
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)
        if file and allowed_file(file.filename):
            filename = secure_filename(name+"."+roll+"."+file.filename.rsplit('.', 1)[1].lower())
            file.save(os.path.join(app.config['UPLOAD_FOLDER']+"/regImg", filename))
            cur = mysql.connection.cursor()
            cur.execute("INSERT INTO student(name, roll, batch) VALUES (%s, %s, %s)", (name, roll, batch))
            mysql.connection.commit()
            cur.close()
            return render_template('index.html', message="Student Successfully Registered", success=True)
    return render_template('register_student.html')
    
@app.route("/logout")
def logout():
    session["email"] = None
    session['batch'] = None
    session['sem'] = None
    session['sub'] = None
    session['video'] = None
    return redirect("/")

@app.route("/clearattendenceinfo")
def clear_attendence_info():
    session['batch'] = None
    session['sem'] = None
    session['sub'] = None
    session['video'] = None
    return redirect('/makeattendence')

if __name__ == '__main__':
    app.run(debug=True)