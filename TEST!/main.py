import customtkinter as ctk
from tkcalendar import Calendar
from datetime import datetime
import threading
import database
from database import send_qr_email
import re
import cv2
from PIL import Image, ImageTk

ctk.set_appearance_mode("transparent")

database.init_db()

class AttendanceAPP(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Attendance Dashboard")
        self.geometry("900x600")
        self.current_user = None
        self.qr_label = None
        self.login_attempts = 0
        self.max_attempts = 3
        self.login_page()


    def clear_window(self):
        for widget in self.winfo_children():
            widget.destroy()





    #---[ LOGIN PAGE ]---#
    def login_page(self):
        self.clear_window()
        self.geometry("{}x{}+0+0". format(self.winfo_screenwidth(), self.winfo_screenheight()))
        self.login_attempts = 0

        logincv_cover = Image.open("TEST!/univcv.png")
        login_cover = ImageTk.PhotoImage(logincv_cover)
        login_label = ctk.CTkLabel(self, image=login_cover, text="", bg_color="transparent", anchor="nw")
        login_label.place(x=0, y=0)

        ctk.CTkLabel(self, text="                               ", font=("Arial", 50, "bold"), height=725).place(x=560, y=30)

        show_btn = ctk.CTkImage(light_image=Image.open("TEST!/show.png"),
                                dark_image=Image.open("TEST!/show.png"), size=(40, 25))
        hide_btn = ctk.CTkImage(light_image=Image.open("TEST!/hide.png"),
                                dark_image=Image.open("TEST!/hide.png"), size=(40, 25))

        ctk.CTkLabel(self, text="Login", font=("Arial", 50, "bold")).pack(pady=50)

        #ctk.CTkLabel(self, text="", bg_color="transparent", width=500, height=2000, anchor="center").place(relx=0, rely=0)
        id_entry = ctk.CTkEntry(self, placeholder_text="Student ID", width=300)
        id_entry.pack(pady=5)

        password_entry = ctk.CTkEntry(self, placeholder_text="Password", show="*", width=300)
        password_entry.pack(pady=5)

        subject_menu = ctk.CTkOptionMenu(self, values=database.SUBJECTS, command=lambda s: setattr(self, "selected_subject", s))
        subject_menu.pack(pady=5)
        subject_menu.set("ITE-260")  # default
        self.selected_subject = subject_menu.get()

        message_label = ctk.CTkLabel(self, text="", anchor="center")
        message_label.pack(pady=5)
            

        def login_verify():
            try:
                if self.login_attempts >= self.max_attempts:
                    login_btn.configure(state="disabled")
                    self.after(30000, lambda: login_btn.configure(state="normal"))
                    message_label.configure(text="❌ Maximum attempts reached, wait 30 seconds.", text_color="red")
                    self.after(1500, lambda: message_label.configure(text=""))
                    return

                id = id_entry.get().strip()
                password = password_entry.get().strip()

                if not id or not password:
                    message_label.configure(text="❌ Enter Student ID and Password.", text_color="red")
                    self.after(1500, lambda: message_label.configure(text=""))
                    return

                # Credentials check only
                if not database.verify_login(id, password):
                    message_label.configure(text="❌ Incorrect ID or Password.", text_color="red")
                    self.after(1500, lambda: message_label.configure(text=""))
                    self.login_attempts += 1
                    return

                # Get student name
                canonical_name = database.get_canonical_name(id)
                self.current_user = canonical_name

                # DO NOT MARK ATTENDANCE HERE!
                self.show_dashboard()

            except Exception as e:
                message_label.configure(text=f"Error: {e}", text_color="red")
                self.after(1500, lambda: message_label.configure(text=""))



        def scan_qr():
            def qr_loop():
                cap = cv2.VideoCapture(0)
                detector = cv2.QRCodeDetector()

                try:
                    cv2.namedWindow("QR Scanner (Press Q to Exit)")
                    cv2.resizeWindow("QR Scanner (Press Q to Exit)", 800, 600)

                    while True:
                        ret, frame = cap.read()
                        if not ret:
                            break

                        # Flip camera for natural preview
                        frame = cv2.flip(frame, 1)

                        # Detect QR
                        data, bbox, _ = detector.detectAndDecode(frame)

                        if data:
                            try:
                                # FIX: QR only contains student_id, password
                                student_qr, password_qr = data.split(",")
                            except ValueError:
                                print("❌ QR format invalid. Expected: student_id,password")
                                continue

                            # Verify credentials
                            if not database.verify_login(student_qr, password_qr):
                                print("❌ Student ID or Password in QR is incorrect.")
                                continue

                            # Convert student ID → Name
                            canonical_name = database.get_canonical_name(student_qr)
                            if not canonical_name:
                                print("❌ Student not found in database.")
                                continue

                            # Subject selected in login page
                            subject = subject_menu.get()

                            # Check attendance
                            if database.has_marked_attendance_today(canonical_name, subject):
                                print("❌ Attendance already marked today.")
                                continue

                            # Mark attendance
                            if database.mark_attendance(canonical_name, subject):
                                self.current_user = canonical_name
                                cap.release()
                                cv2.destroyAllWindows()
                                self.show_dashboard()
                                return
                            else:
                                print("❌ Failed to mark attendance.")

                        cv2.imshow("QR Scanner (Press Q to Exit)", frame)

                        if cv2.waitKey(1) & 0xFF == ord('q'):
                            break

                except Exception as e:
                    message_label.configure(text=f"QR Scanner error: {e}", text_color="red")

                finally:
                    cap.release()
                    cv2.destroyAllWindows()

            threading.Thread(target=qr_loop, daemon=True).start()


        login_btn = ctk.CTkButton(self, text="Login", command=login_verify, width=200)
        login_btn.pack(pady=5)
        ctk.CTkButton(self, text="Scan QR Code", fg_color="green", command=scan_qr, width=200).pack(pady=5)
        ctk.CTkButton(self, text="Sign Up", fg_color="gray", command=self.signup_page, width=200).pack(pady=5)
        ctk.CTkButton(self, text="Forgot Password?", command=self.forgot_password, width=200).pack(pady=5)


        def show():
            password_entry.configure(show="")
            show_button.configure(image=hide_btn, command=hide)


        def hide():
            password_entry.configure(show="*")
            show_button.configure(image=show_btn, command=show)

        show_button = ctk.CTkButton(self, image=show_btn, text="", width=25, height=25, command=show, fg_color="transparent", bg_color="transparent", hover=False)
        show_button.place(x=920, y=200)





    #---[ RESET PASSWORD ]---#
    def forgot_password(self):
        win = ctk.CTkToplevel(self)
        win.title("Reset Password")
        win.geometry("{}x{}+0+0". format(self.winfo_screenwidth(), self.winfo_screenheight()))
        win.grab_set()

        show_btn = ctk.CTkImage(light_image=Image.open("TEST!/show.png"),
                                dark_image=Image.open("TEST!/show.png"), size=(40, 25))
        hide_btn = ctk.CTkImage(light_image=Image.open("TEST!/hide.png"),
                                dark_image=Image.open("TEST!/hide.png"), size=(40, 25))

        logincv_cover = Image.open("TEST!/univcv.png")
        login_cover = ImageTk.PhotoImage(logincv_cover)
        login_label = ctk.CTkLabel(win, image=login_cover, text="", bg_color="transparent", anchor="nw")
        login_label.place(x=0, y=0)

        ctk.CTkLabel(win, text="                               ", font=("Arial", 50, "bold"), height=725).place(x=560, y=30)
        ctk.CTkLabel(win, text="Reset Password", font=("Arial", 50, "bold")).pack(pady=50)

        id_entry = ctk.CTkEntry(win, placeholder_text="Student ID", width=250)
        id_entry.pack(pady=10)

        email_entry = ctk.CTkEntry(win, placeholder_text="Phinmaed Email", width=250)
        email_entry.pack(pady=10)


        def show():
            conf_entry.configure(show="")
            show_button.configure(image=hide_btn, command=hide)


        def hide():
            conf_entry.configure(show="*")
            show_button.configure(image=show_btn, command=show)


        newpass_entry = ctk.CTkEntry(win, placeholder_text="New Password", width=250, show="")
        newpass_entry.pack(pady=10)

        conf_entry = ctk.CTkEntry(win, placeholder_text="Confirm Password", width=250, show="*")
        conf_entry.pack(pady=10)

        message_label = ctk.CTkLabel(win, text="")
        message_label.pack(pady=5)

        def reset():
            sid = id_entry.get().strip()
            email = email_entry.get().strip()
            pw = newpass_entry.get().strip()
            cpw = conf_entry.get().strip()

            # Load DB
            students = database.read_sheet("Students")

            # Verify user exists
            row = students[(students["Student ID"].astype(str) == sid) &
                        (students["Phinmaed Email"].astype(str) == email)]
            if row.empty:
                message_label.configure(text="❌ No matching account.", text_color="red")
                return

            # Password match?
            if pw != cpw:
                message_label.configure(text="❌ Passwords do not match.", text_color="red")
                return

            # Password rule: 8 chars, must contain !?$#&@
            pattern = re.compile(r"^(?=.{8,}$)(?=.*[!?\$#&@]).+$")
            if not pattern.match(pw):
                message_label.configure(text="❌ Password must be 8+ chars & contain ! ? $ # & @", text_color="red")
                return

            # Update password in database
            students.loc[row.index, "Password"] = pw

            # Get student name + ID for QR regeneration
            student_name = row.iloc[0]["Name"]
            student_id = row.iloc[0]["Student ID"]

            # Regenerate QR with updated password
            new_qr = database.regenerate_qr(student_name, student_id, pw)

            # Send QR to email
            success, msg = send_qr_email(email, student_name, new_qr)
            if success:
                message_label.configure(text="✅ Password & QR emailed!", text_color="green")
            else:
                message_label.configure(text=f"✅ Password updated but email failed: {msg}", text_color="orange")

            database.write_sheet("Students", students)
            self.after(1500, win.destroy)  

        ctk.CTkButton(win, text="Reset Password", command=reset).pack(pady=10)
        ctk.CTkButton(win, text="Back to Login", fg_color="gray", command=lambda: win.destroy()).pack(pady=10)
        show_button = ctk.CTkButton(win, image=show_btn, text="", width=25, height=25, command=show, fg_color="transparent", bg_color="transparent", hover=False)
        show_button.place(x=895, y=313)
        




    #---[ SIGNUP PAGE]---#
    def signup_page(self):
        self.clear_window()
        self.geometry("{}x{}+0+0". format(self.winfo_screenwidth(), self.winfo_screenheight()))

        logincv_cover = Image.open("TEST!/univcv.png")
        login_cover = ImageTk.PhotoImage(logincv_cover)
        login_label = ctk.CTkLabel(self, image=login_cover, text="", bg_color="transparent", anchor="nw")
        login_label.place(x=0, y=0)

        ctk.CTkLabel(self, text="                               ", font=("Arial", 50, "bold"), height=725).place(x=560, y=30)

        show_btn = ctk.CTkImage(light_image=Image.open("TEST!/show.png"),
                                dark_image=Image.open("TEST!/show.png"), size=(40, 25))
        hide_btn = ctk.CTkImage(light_image=Image.open("TEST!/hide.png"),
                                dark_image=Image.open("TEST!/hide.png"), size=(40, 25))


        ctk.CTkLabel(self, text="Sign Up", font=("Arial", 50, "bold")).pack(pady=50)


        def force_uppercase1(event=None):
            text1 = last_entry.get()
            new_text1 = text1.upper()

            # Only update if needed (prevents cursor jump)
            if text1 != new_text1:
                last_entry.delete(0, "end")
                last_entry.insert(0, new_text1)

        last_entry = ctk.CTkEntry(self, placeholder_text="LAST NAME", width=300)
        last_entry.pack(pady=10)
        last_entry.bind("<KeyRelease>", force_uppercase1)


        def force_uppercase2(event=None):
            text2 = first_entry.get()
            new_text2 = text2.upper()
            # Only update if needed (prevents cursor jump)
            if text2 != new_text2:
                first_entry.delete(0, "end")
                first_entry.insert(0, new_text2)

        first_entry = ctk.CTkEntry(self, placeholder_text="FIRST NAME", width=300)
        first_entry.pack(pady=10)
        first_entry.bind("<KeyRelease>", force_uppercase2)


        def force_uppercase3(event=None):
            text3 = middle_entry.get()
            new_text3 = text3.upper()

            # Only update if needed (prevents cursor jump)
            if text3 != new_text3:
                middle_entry.delete(0, "end")
                middle_entry.insert(0, new_text3)

        middle_entry = ctk.CTkEntry(self, placeholder_text="MIDDLE NAME", width=300)
        middle_entry.pack(pady=10)
        middle_entry.bind("<KeyRelease>", force_uppercase3)


        def on_validate_student(new_value):
            # Allow empty string for deletion
            if len(new_value) <= 17:
                return True
            
            if all(c.isdigit() or c == "-" for c in new_value):
                return True
            return False


        vcmd_student = self.register(on_validate_student)
        student_entry = ctk.CTkEntry(self, placeholder_text="Student Number", width=300, validate="key", validatecommand=(vcmd_student, "%P"))
        student_entry.pack(pady=10)

        phinmaed_entry = ctk.CTkEntry(self, placeholder_text="Phinmaed Gmail", width=300)
        phinmaed_entry.pack(pady=10)

        phinmaed_label = ctk.CTkLabel(self, text="@phinmaed.com", height=8, fg_color="#343638", bg_color="#8c959c")
        phinmaed_label.place(x=815, y=370)


        password_entry = ctk.CTkEntry(self, placeholder_text="Password", width=300, show="")
        password_entry.pack(pady=10)

        cpassword_entry = ctk.CTkEntry(self, placeholder_text="Confirm Password", width=300, show="*")
        cpassword_entry.pack(pady=10)


        def show():
            cpassword_entry.configure(show="")
            show_button.configure(image=hide_btn, command=hide)


        def hide():
            cpassword_entry.configure(show="*")
            show_button.configure(image=show_btn, command=show)


        show_button = ctk.CTkButton(self, image=show_btn, text="", width=25, height=25, command=show, fg_color="transparent", bg_color="transparent", hover=False)
        show_button.place(x=920, y=460)
        
        message_label = ctk.CTkLabel(self, text="")
        message_label.pack(pady=5)

        pmessage_label = ctk.CTkLabel(self, text="")
        pmessage_label.pack(pady=5)

        # Password rule: at least 8 chars + must contain one of ! ? $ # & @
        pattern = re.compile(r"^(?=.{8,}$)(?=.*[!%^*(){}<>/.,=#&@]).+$")


        def signup():
            last = last_entry.get().strip()
            first = first_entry.get().strip()
            middle = middle_entry.get().strip()
            student = student_entry.get().strip()
            phinmaed = phinmaed_entry.get().strip()
            pw = password_entry.get().strip()
            cpw = cpassword_entry.get().strip()

            if not last or not first or not middle or not student or not phinmaed:
                message_label.configure(text="❌ Enter Information Needed.", text_color="red")
                self.after(1500, lambda: message_label.configure(text=""))
                return
            
            if len(student) != 17:
                message_label.configure(text="❌ Enter Valid Student ID.", text_color="red")
                self.after(1500, lambda: message_label.configure(text=""))
                return

            # Optionally, check a prefix pattern
            if not "03-01-2526-" in student:
                message_label.configure(text="❌ Enter Valid Phinmaed Student ID.", text_color="red")
                self.after(1500, lambda: message_label.configure(text=""))
                return
            
            if "@phinmaed.com" in phinmaed:
                message_label.configure(text="❌ Enter valid Phinmaed Uername.", text_color="red")
                self.after(1500, lambda: message_label.configure(text=""))
                return
            
            if "@" in phinmaed:
                message_label.configure(text="❌ Enter valid Phinmaed Uername.", text_color="red")
                self.after(1500, lambda: message_label.configure(text=""))
                return
            
            if ".com" in phinmaed:
                message_label.configure(text="❌ Enter valid Phinmaed Uername.", text_color="red")
                self.after(1500, lambda: message_label.configure(text=""))
                return
            
            name = (f"{last}, {first} {middle}")
            phinmaed_acc = phinmaed+"@phinmaed.com"
            
            # Passwords match?
            if pw != cpw:
                pmessage_label.configure(text="❌ Password does not match.", text_color="red")
                self.after(1500, lambda: pmessage_label.configure(text=""))
                return

            # Valid password format?
            if not pattern.match(pw):
                pmessage_label.configure(text="❌ Password must be 8+ chars and include one symbol.", text_color="red")
                self.after(1500, lambda: pmessage_label.configure(text=""))
                return

            if database.register_user(name, student, phinmaed_acc, pw):
                # Regenerate QR and send email
                qr_path = database.regenerate_qr(name, student, pw)
                success, msg = send_qr_email(phinmaed_acc, name, qr_path)
                if success:
                    message_label.configure(text="✅ Account created, Sending QR Code to your phinmaed gmail", text_color="green")
                else:
                    message_label.configure(text=f"❌ Account created but email failed: {msg}", text_color="red")
                self.after(1500, lambda: message_label.configure(text=""))
            else:
                message_label.configure(text="❌ Name already exists.", text_color="red")
                self.after(1500, lambda: message_label.configure(text=""))

        ctk.CTkButton(self, text="Register", command=signup, width=200).pack(pady=10)
        ctk.CTkButton(self, text="Back to Login", fg_color="gray", command=self.login_page, width=200).pack(pady=10)





    #---[ DASHBOARD ]---#
    def show_dashboard(self):
        self.clear_window()
        self.geometry("{}x{}+0+0". format(self.winfo_screenwidth(), self.winfo_screenheight()))

        header = ctk.CTkFrame(self, height=60)
        header.pack(fill="x")
        ctk.CTkLabel(header, text=f"Welcome, {self.current_user}", font=("Arial", 20, "bold")).pack(side="left", padx=20)

        self.clock_label = ctk.CTkLabel(header, font=("Arial", 18))
        self.clock_label.pack(side="right", padx=20)
        self.update_clock()

        main_frame = ctk.CTkFrame(self)
        main_frame.pack(expand=True, fill="both", padx=20, pady=20)

        # Calendar
        cal_frame = ctk.CTkFrame(main_frame, width=800)
        cal_frame.pack(side="left", fill="y", padx=10, pady=10)
        ctk.CTkLabel(cal_frame, text="Attendance Calendar", font=("Arial", 18, "bold")).pack(pady=10)
        cal = Calendar(cal_frame, selectmode='day', font=("Arial", 14))
        cal.pack(pady=10)

        # Controls
        control_frame = ctk.CTkFrame(main_frame, width=400)
        control_frame.pack(side="right", fill="both", expand=True, padx=10, pady=10)

        status_var = ctk.StringVar(value="Present")
        message_label = ctk.CTkLabel(control_frame, text="")
        message_label.pack(pady=5)
        ctk.CTkLabel(control_frame, text="Mark Attendance", font=("Arial", 16, "bold")).pack(pady=10)
        ctk.CTkRadioButton(control_frame, text="Present", variable=status_var, value="Present").pack(pady=5)
        ctk.CTkRadioButton(control_frame, text="Absent", variable=status_var, value="Absent").pack(pady=5)


        def mark():
            today = datetime.now().strftime("%d/%m/%Y")

            # Check with selected subject
            if database.has_marked_attendance_today(self.current_user, self.selected_subject):
                message_label.configure(text="❌ Attendance already marked today!", text_color="red")
                self.after(1500, lambda: message_label.configure(text=""))
                return

            # Mark attendance for selected subject
            database.mark_attendance(self.current_user, self.selected_subject)
            mark_check.configure(state="disabled")

            message_label.configure(text=f"✅ Attendance marked for {today}", text_color="green")
            self.after(1500, lambda: message_label.configure(text=""))


        mark_check = ctk.CTkButton(control_frame, text="Mark Attendance", command=mark, width=200)
        mark_check.pack(pady=20)
        login_back = ctk.CTkButton(control_frame, text="Logout", fg_color="red", command=self.login_page, width=200)
        login_back.pack(pady=20)


    # ---[ CLOCK ]---#
    def update_clock(self):
        now = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
        self.clock_label.configure(text=now)
        self.after(1000, self.update_clock)


if __name__ == "__main__":
    app = AttendanceAPP()
    app.mainloop()