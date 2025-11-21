# databases.py
from PIL import Image
import pandas as pd
import os
from datetime import datetime
import  smtplib
import qrcode
import cv2
import smtplib
from email.message import EmailMessage

# Excel File
file = "attendancecakes.xlsx"

# Default subjects
SUBJECTS = ["ITE-260", "ITE-366", "GEN-001", "GEN-002", "GEN-008", "MAT-152", "NST-015", "PED-030"]



#---[ DATABASE INIT ]---#
def init_db():
    if not os.path.exists(file):
        with pd.ExcelWriter(file, engine="openpyxl") as writer:
            students = pd.DataFrame(columns=[
                "Name", "Student ID", "Password",
                "Phinmaed Email", "QR Code"
            ])
            students.to_excel(writer, sheet_name="Students", index=False)

            for sheet in SUBJECTS:
                df = pd.DataFrame(columns=["Name", "Student ID", "Date & Time"])
                df.to_excel(writer, sheet_name=sheet, index=False)

        print("✔ Database created.")
    else:
        print("✔ Database already exists.")



#---[ READ/WRITE SHEET ]---#
def read_sheet(sheet):
    if not os.path.exists(file):
        init_db()

    try:
        return pd.read_excel(file, sheet_name=sheet)
    except ValueError:
        # Auto-create missing sheet
        df = pd.DataFrame(columns=["Name", "Student ID", "Date & Time"])
        write_sheet(sheet, df)
        return df


def write_sheet(sheet, df):
    with pd.ExcelWriter(file, mode="a", engine="openpyxl", if_sheet_exists="replace") as writer:
        df.to_excel(writer, sheet_name=sheet, index=False)



#---[ REGISTER USER ]---#
def register_user(name, student_id, phinmaed_acc, pw):
    students = read_sheet("Students")

    if str(student_id) in students["Student ID"].astype(str).values:
        return False

    # --- QR Code containing name, student_id, password ---
    qr_path = f"qr_codes/{name}.png"
    data = f"{student_id},{pw}"  # include password here
    qr = qrcode.make(data)
    os.makedirs("qr_codes", exist_ok=True)
    qr.save(qr_path)

    # --- Add user to Excel ---
    new_row = pd.DataFrame({
        "Name": [name],
        "Student ID": [student_id],
        "Password": [pw],
        "Phinmaed Email": [phinmaed_acc],
        "QR Code": [qr_path]
    })

    students = pd.concat([students, new_row], ignore_index=True)
    write_sheet("Students", students)
    return True



#---[ GET NAME ]---#
def get_canonical_name(student_id, password=None):
    # Assuming `read_sheet` is a function that loads the sheet as a pandas DataFrame.
    students = read_sheet("Students")

    # Try to find the student by ID
    row = students[students["Student ID"].astype(str) == str(student_id)]

    if not row.empty:
        # We return the student ID or canonical name (you might want to return other details, but for now, it's ID)
        return row.iloc[0]["Name"]
    return None  # Return None if no student is found


def verify_login(student_id, password):
    # Load the student database
    students = read_sheet("Students")

    # Try to find the student by their ID
    row = students[students["Student ID"].astype(str) == str(student_id)]

    if row.empty:
        return False  # Student not found in database

    # Compare the input password with the stored one
    real_password = str(row.iloc[0]["Password"])

    # Return whether the passwords match
    return real_password == str(password)



#---[ MARK ATTENDANCE FOR ONE SUBJECT ONLY ]---#
def mark_attendance(student_name, subject):
    if subject not in SUBJECTS:
        return False

    students = read_sheet("Students")
    student_row = students[students["Name"] == student_name]
    if student_row.empty:
        return False

    student_id = student_row.iloc[0]["Student ID"]
    now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    today = datetime.now().strftime("%d/%m/%Y")

    df = read_sheet(subject)
    df["Date & Time"] = df["Date & Time"].fillna("")

    # Already marked?
    if not df[(df["Student ID"] == student_id) &
              (df["Date & Time"].str.startswith(today))].empty:
        return False

    new_row = pd.DataFrame({
        "Name": [student_name],
        "Student ID": [student_id],
        "Date & Time": [now]
    })

    df = pd.concat([df, new_row], ignore_index=True)
    write_sheet(subject, df)
    return True



#---[ CHECK TODAY ]---#
def has_marked_attendance_today(student_name, subject):
    df = read_sheet(subject)
    if df.empty:
        return False

    df["Date & Time"] = pd.to_datetime(df["Date & Time"], errors="coerce")
    today = datetime.now().date()

    student_row = df[df["Name"] == student_name]
    if not student_row.empty and any(student_row["Date & Time"].dt.date == today):
        return True

    return False



#---[ VERIFY QR ]---#
def verify_qr(qr_path, subject):
    # Load image with OpenCV
    img = cv2.imread(qr_path)
    if img is None:
        return False, "QR image not found"

    detector = cv2.QRCodeDetector()
    data, bbox, _ = detector.detectAndDecode(img)

    if not data:
        return False, "QR not readable"

    try:
        name, student_id, password = data.split(",")
    except:
        return False, "Invalid QR format"

    # Compare with Excel
    students = read_sheet("Students")
    match = students[
        (students["Name"] == name) &
        (students["Student ID"].astype(str) == str(student_id)) &
        (students["Password"] == password)
    ]

    if match.empty:
        return False, "Invalid QR"

    # Optional: mark attendance
    if mark_attendance(name, subject):
        return True, f"Attendance marked for {name} in {subject}"
    else:
        return True, f"{name} already marked today"


def regenerate_qr(student_name, student_id, new_password):
    qr_path = f"qr_codes/{student_name}.png"
    data = f"{student_id},{new_password}"
    qr = qrcode.make(data)
    os.makedirs("qr_codes", exist_ok=True)
    qr.save(qr_path)
    return qr_path



# --- [ SEND QR EMAIL ] --- #
def send_qr_email(recipient_email, student_name, qr_path):
    try:
        # --- Gmail credentials ---
        sender_email = "qrcodesender123@gmail.com"
        sender_password = "jojd gtrl gvqd qqgj"  # Use App Password for Gmail 2FA

        # --- Create email ---
        msg = EmailMessage()
        msg["Subject"] = "Your Attendance QR Code"
        msg["From"] = sender_email
        msg["To"] = recipient_email
        msg.set_content(f"Hello {student_name},\n\nAttached is your QR code for attendance.\n\nBest regards,\nAttendance System")

        # --- Attach QR image ---
        with open(qr_path, "rb") as f:
            img_data = f.read()
        msg.add_attachment(img_data, maintype="image", subtype="png", filename=f"{student_name}_QR.png")

        # --- Send email via Gmail SMTP ---
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as smtp:
            smtp.login(sender_email, sender_password)
            smtp.send_message(msg)

        return True, "Email sent successfully"

    except Exception as e:
        return False, f"Failed to send email: {e}"

