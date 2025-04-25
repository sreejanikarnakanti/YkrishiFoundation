from flask import Flask, render_template, request, redirect, url_for, flash, session,  get_flashed_messages
import os
import sqlite3
from werkzeug.utils import secure_filename
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message
import traceback
import requests 
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()



app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY')
bcrypt = Bcrypt(app)

#=========LOGIN/REGISTER=================

def get_db_connection():
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/login_register', methods=['GET', 'POST'])
def login_register():
    if 'user' in session:
        flash(f"User '{session['user']}' is already logged in.", "info")
        return  render_template("login1.html")

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        form_type = request.form['form_type']

        conn = get_db_connection()
        cursor = conn.cursor()

        if form_type == 'register':
            confirm_password = request.form.get('confirm_password')
            if password != confirm_password:
                flash('Passwords do not match', 'danger')
                return redirect(url_for('login_register'))

            hashed_pw = bcrypt.generate_password_hash(password).decode('utf-8')
            try:
                cursor.execute("INSERT INTO users (username, password) VALUES (?, ?)", (username, hashed_pw))
                conn.commit()
                flash('Registration successful! Please login.', 'success')
            except sqlite3.IntegrityError:
                flash('Username already exists.', 'danger')
            conn.close()
            return redirect(url_for('login_register'))

        elif form_type == 'login':
            user = cursor.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
            conn.close()
            if user and bcrypt.check_password_hash(user['password'], password):
                session['user'] = user['username']
                flash(f"Welcome, {user['username']}!", 'success')
                return redirect(url_for('homepage'))
            else:
                flash("Invalid username or password", "danger")
                return redirect(url_for('login_register'))

    return render_template('login1.html')

@app.route('/home')
def home():
    if 'user' in session:
        flash(f"You are now logged in.", "success")
        return render_template('index.html', username=session['user'])
    else:
        return redirect(url_for('login_register'))

# =================== MAIL CONFIG ===================
app.config['MAIL_SERVER'] = 'smtp.gmail.com'
app.config['MAIL_PORT'] = 587
app.config['MAIL_USE_TLS'] = True
app.config['MAIL_USE_SSL'] = False
app.config['MAIL_USERNAME'] = os.getenv('YKRISHI_EMAIL')
app.config['MAIL_PASSWORD'] = os.getenv('MAIL_PASSWORD')

# Replace with your actual app password
app.config['MAIL_DEFAULT_SENDER'] = ('YKrishi Foundation', os.getenv('YKRISHI_EMAIL'))
mail = Mail(app)


#===============detecting location================ 
# Add this function below the imports
def get_city_from_ip():
    try:
        ip_data = requests.get("https://ipinfo.io").json()
        return ip_data.get("city", "Hyderabad")  # fallback
    except:
        return "Hyderabad"
    
# ✅ PLACE YOUR CITY DATA HERE
city_data = {
    "Hyderabad": {
        "monthly_guide": [
            "🌱 Sow cotton, red gram, and maize this month.",
            "💧 Use mulching to conserve moisture during hot spells.",
            "🔍 Monitor leafhoppers and aphids weekly.",
        ],
        "pest_alert": (
            "🪲 **Red cotton bug** active in dry spells.<br>"
            "- Spray neem extract weekly.<br>"
            "- Install pheromone traps around the field."
        ),
        "fertilizer_tip": (
            "💧 Apply **DAP** during initial soil preparation.<br>"
            "- Use split doses of **urea** for better nitrogen efficiency.<br>"
            "- Add **zinc sulphate** for micronutrient boost."
        )
    },
    "Delhi": {
        "monthly_guide": [
            "🌿 Transplant tomatoes and chilies this month.",
            "🧑‍🌾 Prepare seedbeds with FYM (Farmyard Manure).",
            "💧 Irrigate every 7–10 days in sandy soils."
        ],
        "pest_alert": (
            "🪳 **Whitefly alert** on leafy vegetables.<br>"
            "- Deploy sticky yellow traps.<br>"
            "- Avoid excess nitrogen application."
        ),
        "fertilizer_tip": (
            "🔋 Apply **potash** for root crops like carrots and beets.<br>"
            "- Split **urea** in two doses: sowing + 15 days.<br>"
            "- Combine with **bone meal** for phosphorus."
        )
    },
    "Chennai": {
        "monthly_guide": [
            "🌾 Continue paddy transplanting in well-irrigated fields.",
            "🧪 Test soil pH before fertilizer application.",
            "☀️ Monitor for signs of early leaf blight."
        ],
        "pest_alert": (
            "🐛 **Stem borer** may appear in paddy.<br>"
            "- Use Tricho-cards (Trichogramma).<br>"
            "- Avoid late-night flood irrigation."
        ),
        "fertilizer_tip": (
            "💧 Use **urea** + **super phosphate** during planting.<br>"
            "- Add **potassium** to improve stem strength.<br>"
            "- Prefer organic inputs in water-logged areas."
        )
    }
}


# =================== FILE UPLOAD CONFIG ===================
UPLOAD_FOLDER = "static/uploads"
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'pdf', 'docx'}
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# =================== ROUTES ===================
@app.route('/')
def homepage():
    files = os.listdir(app.config["UPLOAD_FOLDER"])
    return render_template('index.html', files=files)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route("/upload", methods=["GET", "POST"])
def upload_file():
    if request.method == "POST":
        if "file" not in request.files:
            flash("No file part", "danger")
            return redirect(request.url)

        file = request.files["file"]
        if file.filename == "":
            flash("No selected file", "danger")
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            file_path = os.path.join(app.config["UPLOAD_FOLDER"], filename)
            file.save(file_path)
            flash("File successfully uploaded", "success")
        else:
            flash("Invalid file type.", "danger")
            return redirect(request.url)

    files = os.listdir(app.config["UPLOAD_FOLDER"])
    return render_template("upload.html", files=files)

@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/team')
def team():
    return render_template('team.html')

#@app.route('/blog')
#def blog():
  #return render_template('blog.html')

@app.route('/blog1')
def blog1():
    return render_template('blog1.html')

@app.route('/blog2')
def blog2():
    return render_template('blog2.html')

@app.route('/blog3')
def blog3():
    return render_template('blog3.html')

@app.route('/portfolio-details')
def portfolio_details():
    return render_template('portfolio-details.html')



@app.route('/contact', methods=['GET', 'POST'])
def contact():
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')

        print(f"Name: {name}, Email: {email}, Subject: {subject}, Message: {message}")

        # Send confirmation email
        try:
            msg = Message(
                subject="Thank You for Contacting YKrishi Foundation!",
                recipients=[email],  # send to user who filled the form
            )
            msg.body = f"""Dear {name},

Thank you for reaching out to YKrishi Foundation. We have received your message and will get back to you shortly.

Here’s what you submitted:
Subject: {subject}
Message: {message}

Warm regards,  
YKrishi Foundation Team
"""
            mail.send(msg)
            flash("Message sent and confirmation email delivered!", "success")
        except Exception as e:
            print("Email sending failed:", e)
            traceback.print_exc()  # ✅ This will show the exact cause in your terminal
            flash("Message submitted but failed to send confirmation email.", "danger")
        return render_template('contact.html', success=True)

    return render_template('contact.html')

@app.route('/test_email')
def test_email():
    try:
        msg = Message(
            subject="Test Email from YKrishi Foundation",
            recipients=["sreejanichikki20@gmail.com"],  # replace with your Gmail
            body="This is a test email sent via Flask."
        )
        mail.send(msg)
        return "✅ Test email sent successfully!"
    except Exception as e:
        import traceback
        traceback.print_exc()
        return f"❌ Error sending email: {e}"




@app.route('/blog_details')
def blog_details():
    return render_template('blog-details.html')  

#==============crop advisory====================#

@app.route("/crop-advisory")
def crop_advisory():
    city = request.args.get('city')
    if city:
        city = city.strip().title()
    else:
        city = get_city_from_ip()

    api_key = "3f44e391e85821f7634676e916b9babc"

    # 🌐 Get coordinates of the city for One Call API
    geo_url = f"http://api.openweathermap.org/geo/1.0/direct?q={city}&limit=1&appid={api_key}"
    geo_data = requests.get(geo_url).json()

    if geo_data:
        lat = geo_data[0]['lat']
        lon = geo_data[0]['lon']
    else:
        print("❌ Could not fetch lat/lon for city")
        lat, lon = 17.385, 78.4867  # fallback to Hyderabad

    weather_url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric"
    response = requests.get(weather_url).json()

    print("City:", city)
    print("Weather API Response:", response)

    temperature = 30
    weather_desc = "not available"
    weather_icon = "Unknown"

    if response.get("cod") == 200:
        temperature = response['main']['temp']
        weather_desc = response['weather'][0]['description']
        weather_icon = response['weather'][0]['main']
    else:
        print("⚠️ Error fetching weather for", city)

    # 📅 Get 5-day forecast using One Call API
    from datetime import datetime

    forecast_url = f"https://api.openweathermap.org/data/2.5/onecall?lat={lat}&lon={lon}&exclude=minutely,hourly,current,alerts&appid={api_key}&units=metric"

    forecast_data = requests.get(forecast_url).json()
    print("One Call Forecast Response:", forecast_data)


    daily_forecast = []
    alerts = []

    if "daily" in forecast_data:
        for day in forecast_data['daily'][:5]:
            date_str = datetime.utcfromtimestamp(day['dt']).strftime('%a, %d %b')
            day_forecast = {
                'date': date_str,
                'temp_day': day['temp']['day'],
                'humidity': day['humidity'],
                'wind_speed': day['wind_speed'],
                'rain': day.get('rain', 0)
            }
            daily_forecast.append(day_forecast)

            if day_forecast['rain'] > 10:
                alerts.append(f"{date_str}: 🌧️ Heavy rain expected. Delay irrigation.")
            if day_forecast['wind_speed'] > 10:
                alerts.append(f"{date_str}: 🌬️ High wind. Avoid pesticide spraying.")

    # Crop suggestions based on temperature
    if 28 <= temperature <= 35:
        crops = ['Maize', 'Cotton', 'Paddy']
    elif temperature < 28:
        crops = ['Wheat', 'Barley']
    else:
        crops = ['Millets', 'Sorghum']

    # 🌾 Default fallback content
    monthly_guide = [
        "🌱 General advice: Prepare land and check irrigation systems.",
        "💧 Apply organic compost before sowing."
    ]
    pest_alert = (
        "⚠️ General pest watch:<br>"
        "- Check for aphids or leaf spot weekly.<br>"
        "- Use neem-based sprays if needed."
    )
    fertilizer_tip = (
        "💧 Add nitrogen-based fertilizer 15 days after sowing.<br>"
        "- Avoid over-fertilizing. Use compost where possible."
    )

    # ✅ Use city-specific tips if available in city_data
    if city in city_data:
        print("✅ City-specific tips loaded for:", city)
        monthly_guide = city_data[city]["monthly_guide"]
        pest_alert = city_data[city]["pest_alert"]
        fertilizer_tip = city_data[city]["fertilizer_tip"]
    else:
        print("❌ No specific data for", city)
        
    print("Forecast data being sent to template:", daily_forecast)
    print("Advisory alerts:", alerts)

    return render_template("crop_advisory.html",
                           temperature=temperature,
                           weather_desc=weather_desc,
                           weather_icon=weather_icon,
                           city=city,
                           crops=crops,
                           monthly_guide=monthly_guide,
                           pest_alert=pest_alert,
                           fertilizer_tip=fertilizer_tip,
                           forecast=daily_forecast,
                           alerts=alerts)




#==========================================================#

@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form['email']
    print("New subscriber:", email)
    # You can save it to a file or database here
    flash("You are successfully subscribed!")
    return redirect('footer.html')


# =================== DISABLE CACHE FOR DEV ===================
@app.after_request
def disable_caching(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response

# =================== RUN APP ===================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)