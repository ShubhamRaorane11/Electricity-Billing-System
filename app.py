from flask import Flask, render_template, request, redirect, session, flash
from flask_mysqldb import MySQL
from config import MySQLConfig
from datetime import datetime

app = Flask(__name__)
app.secret_key = "secret123"

app.config.from_object(MySQLConfig)
mysql = MySQL(app)

@app.template_filter("format_month")
def format_month(value):
    try:
        dt = datetime.strptime(value, "%Y-%m")
        return dt.strftime("%B %Y")   
    except:
        return value

@app.template_filter("format_month_short")
def format_month_short(value):
    try:
        dt = datetime.strptime(value, "%Y-%m")
        return dt.strftime("%b %Y")   
    except:
        return value

# -------------------------------------------------------
# ✅ DEFAULT LOAD -> Go to Login Page
# -------------------------------------------------------
@app.route("/")
def home():
    return render_template("index.html")   

# -------------------------------------------------------
# ✅ LOGIN PAGE (UI)
# -------------------------------------------------------
@app.route("/login.html", methods=["GET"])
def login_page():
    return render_template("login.html")

# -------------------------------------------------------
# ✅ USER / ADMIN LOGIN PROCESS
# -------------------------------------------------------
@app.route("/login", methods=["POST"])
def login():
    email = request.form["email"]
    password = request.form["password"]

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, email, password, role FROM users WHERE email=%s", (email,))
    user = cur.fetchone()
    cur.close()

    if user and user[3] == password:
        session["user_id"] = user[0]
        session["username"] = user[1]
        session["role"] = user[4]

        if user[4] == "admin":
            return redirect("/admin-dashboard.html")
        else:
            return redirect("/user-dashboard.html")

    flash("Invalid email or password!", "danger")
    return redirect("/login.html")

# -------------------------------------------------------
# ✅ REGISTER USER FROM LOGIN PAGE (For normal users)
# -------------------------------------------------------
@app.route('/register.html')
def register_page():
    return render_template("register.html")

@app.route("/register", methods=["POST"])
def register():
    name = request.form["name"]
    email = request.form["email"]
    password = request.form["password"]

    cur = mysql.connection.cursor()
    cur.execute(
        "INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
        (name, email, password, "user")
    )
    mysql.connection.commit()
    cur.close()

    flash("Registration successful! Please login.", "success")
    return redirect("/login.html")

# -------------------------------------------------------
# ✅ USER DASHBOARD
# -------------------------------------------------------
@app.route("/user-dashboard.html")
def user_dashboard():

    if "user_id" not in session:
        return redirect("/login.html")

    user_id = session["user_id"]

    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT billing_month, units_consumed, amount, status, bill_id
        FROM bills WHERE user_id=%s ORDER BY bill_id DESC LIMIT 1
    """, (user_id,))
    current_bill = cur.fetchone()

    cur.execute("""
        SELECT billing_month, units_consumed, amount, status
        FROM bills WHERE user_id=%s ORDER BY bill_id DESC
    """, (user_id,))
    history = cur.fetchall()

    cur.execute("""
        SELECT billing_month, units_consumed
        FROM bills WHERE user_id=%s ORDER BY bill_id ASC
    """, (user_id,))
    graph_data = cur.fetchall()

    cur.close()

    return render_template("user-dashboard.html",
                           username=session["username"],
                           current_bill=current_bill,
                           history=history,
                           graph_data=graph_data)


# -------------------------------------------------------
# ✅ BILL HISTORY PAGE
# -------------------------------------------------------
@app.route("/bill-history.html")
def bill_history():

    if "user_id" not in session:
        return redirect("/login.html")

    user_id = session["user_id"]

    cur = mysql.connection.cursor()
    cur.execute("SELECT billing_month, units_consumed, amount, status FROM bills WHERE user_id=%s ORDER BY bill_id DESC",
                (user_id,))
    history = cur.fetchall()
    cur.close()

    return render_template("bill-history.html", history=history)


# -------------------------------------------------------
# ✅ PAY BILL
# -------------------------------------------------------
@app.route("/pay_bill", methods=["POST"])
def pay_bill():

    bill_id = request.form["bill_id"]

    cur = mysql.connection.cursor()
    cur.execute("UPDATE bills SET status='paid' WHERE bill_id=%s", (bill_id,))
    mysql.connection.commit()
    cur.close()

    flash("Payment successful!", "success")
    return redirect("/user-dashboard.html")


# -------------------------------------------------------
# ✅ COMPLAINT PAGE (USER)
# -------------------------------------------------------
@app.route("/complaint.html")
def complaint_page():
    if "user_id" not in session:
        return redirect("/login.html")

    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT complaint_id, subject, created_at, status, response
        FROM complaints
        WHERE user_id = %s
        ORDER BY complaint_id DESC
    """, (session["user_id"],))
    
    complaints = cur.fetchall()
    cur.close()

    return render_template("complaint.html", complaints=complaints)



# ✅ SUBMIT COMPLAINT
@app.route("/submit-complaint", methods=["POST"])
def submit_complaint():
    user_id = session["user_id"]
    complaint_type = request.form["complaint_type"]
    complaint_text = request.form["complaint_text"]

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO complaints (user_id, subject, description, status)
        VALUES (%s, %s, %s, 'open')
    """, (user_id, complaint_type, complaint_text))
    mysql.connection.commit()
    cur.close()

    flash("Complaint submitted!", "success")
    return redirect("/complaint.html")


# -------------------------------------------------------
# ✅ ADMIN DASHBOARD
# -------------------------------------------------------
@app.route("/admin-dashboard.html")
def admin_dashboard():
    if "user_id" not in session or session.get("role") != "admin":
        return redirect("/login")

    cur = mysql.connection.cursor()

    # ✅ Fetch count summary
    cur.execute("SELECT COUNT(*) FROM users")
    total_users = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM bills")
    total_bills = cur.fetchone()[0]

    cur.execute("SELECT COUNT(*) FROM complaints WHERE status != 'resolved'")
    pending_complaints = cur.fetchone()[0]

    # ✅ Fetch complaints with user info (fixing the date issue)
    cur.execute("""
        SELECT 
            c.complaint_id,
            c.subject,
            c.description,
            c.status,
            c.created_at,
            u.name
        FROM complaints c
        INNER JOIN users u ON c.user_id = u.id
        ORDER BY c.created_at DESC
    """)
    complaints = cur.fetchall()

    cur.close()

    return render_template(
        "admin-dashboard.html",
        total_users=total_users,
        total_bills=total_bills,
        pending_complaints=pending_complaints,
        complaints=complaints
    )


# ✅ Resolve complaint
@app.route("/resolve-complaint", methods=["POST"])
def resolve_complaint():
    complaint_id = request.form["complaint_id"]
    response_text = request.form["response"]  

    cur = mysql.connection.cursor()
    cur.execute("""
        UPDATE complaints
        SET status='resolved', response=%s
        WHERE complaint_id=%s
    """, (response_text, complaint_id))

    mysql.connection.commit()
    cur.close()

    flash("✅ Complaint resolved and reply sent to user!", "success")
    return redirect("/admin-dashboard.html")


# -------------------------------------------------------
# ✅ ADMIN → ADD USER PAGE (FORM)
# -------------------------------------------------------
@app.route("/add-user-page")
def add_user_page():
    return render_template("add-user.html")

# ✅ ADMIN → SAVE USER TO DB
@app.route("/add-user", methods=["POST"])
def add_user():
    name = request.form["name"]
    email = request.form["email"]
    password = request.form["password"]
    role = request.form["role"]

    cur = mysql.connection.cursor()
    cur.execute("INSERT INTO users (name, email, password, role) VALUES (%s, %s, %s, %s)",
                (name, email, password, role))
    mysql.connection.commit()
    cur.close()

    flash("✅ User added successfully!", "success")
    return redirect("/admin-dashboard.html")

# ✅ ADMIN – Add Bill Page (UI)
@app.route("/add-bill-page")
def add_bill_page():
    if session.get("role") != "admin":
        return redirect("/login.html")

    cur = mysql.connection.cursor()
    cur.execute("SELECT id, name, email FROM users")
    users = cur.fetchall()
    cur.close()

    return render_template("add-bill.html", users=users)


# ✅ ADMIN – Save Bill into DB
@app.route("/add-bill", methods=["POST"])
def add_bill():
    user_id = request.form["user_id"]
    month = request.form["billing_month"]
    units = request.form["units"]
    amount = request.form["amount"]

    cur = mysql.connection.cursor()
    cur.execute("""
        INSERT INTO bills (user_id, billing_month, units_consumed, amount, status)
        VALUES (%s, %s, %s, %s, 'unpaid')
    """, (user_id, month, units, amount))

    mysql.connection.commit()
    cur.close()

    flash("✅ Bill added successfully!", "success")
    return redirect("/admin-dashboard.html")



# -------------------------------------------------------
# ✅ LOGOUT
# -------------------------------------------------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login.html")


# -------------------------------------------------------
# ✅ Start App
# -------------------------------------------------------
if __name__ == "__main__":
    app.run(debug=True)
