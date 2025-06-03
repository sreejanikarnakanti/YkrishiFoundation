from flask import Flask, render_template, request, redirect, url_for, flash, session,  get_flashed_messages , jsonify
from flasgger import Swagger , swag_from
from werkzeug.utils import secure_filename
import os
import sqlite3
from flask_bcrypt import Bcrypt
from flask_mail import Mail, Message
import traceback
import requests 
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()
from functools import wraps
from urllib.parse import urlparse, urljoin


app = Flask(__name__) 
app.secret_key = os.getenv('FLASK_SECRET_KEY')
bcrypt = Bcrypt(app)
swagger=Swagger(app)



    
    
#=========LOGIN/REGISTER=================

def get_db_connection():
     conn = sqlite3.connect('users.db')
     conn.row_factory = sqlite3.Row
     return conn

def is_safe_url(target):
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

@app.route('/login_register', methods=['GET', 'POST'])
def login_register():
    if 'user' in session:
        flash(f"User '{session['user']}' is already logged in.", "info")
        return redirect(url_for('home'))

    next_page = request.args.get('next')  # Get ?next= from URL

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
                cursor.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)",
                               (username, hashed_pw, 'user'))
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
                session['role'] = user['role']
                flash(f"Welcome, {user['username']}!", 'success')

                # 🔐 Secure redirection
                if next_page and is_safe_url(next_page):
                    return redirect(next_page)
                else:
                    return redirect(url_for('home'))
            else:
                flash("Invalid username or password", "danger")
                return redirect(url_for('login_register'))

    return render_template('login1.html')



@app.route('/')
def home():
    return render_template('index.html')


@app.route('/about')
def about():
    return render_template('about.html')


@app.route('/services')
def services():
    return render_template('services.html')

@app.route('/team')
def team():
    return render_template('team.html')


#=============Blog Posts==========================

@app.route('/blog')
def blog():
    conn = sqlite3.connect('users.db')
    c = conn.cursor()
    c.execute('SELECT id, title, content, author, image_url, created_at FROM blog ORDER BY created_at DESC')
    posts = [
        {
            'id': row[0],
            'title': row[1],
            'content': row[2],
            'author': row[3],
            'image_url': row[4],
            'created_at': row[5]
        } for row in c.fetchall()
    ]
    conn.close()
    return render_template('blog.html', posts=posts)


API_KEY = os.getenv('BLOG_API_KEY')

@app.route('/api/posts', methods=['GET', 'POST'])
@swag_from({
    'tags': ['Blog'],
    'consumes': ['multipart/form-data'],
    'parameters': [
        {
            'name': 'x-api-key',
            'in': 'header',
            'type': 'string',
            'required': False,
            'description': 'API key for authentication (required for POST)'
        },
        {
            'name': 'title',
            'in': 'formData',
            'type': 'string',
            'required': True,
            'description': 'Blog title'
        },
        {
            'name': 'content',
            'in': 'formData',
            'type': 'string',
            'required': True,
            'description': 'Blog content'
        },
        {
            'name': 'author',
            'in': 'formData',
            'type': 'string',
            'required': True,
            'description': 'Author name'
        },
        {
            'name': 'image_file',
            'in': 'formData',
            'type': 'file',
            'required': False,
            'description': 'Image file (optional)'
        }
    ],
    'responses': {
        200: {'description': 'List of blog posts (GET)'},
        201: {'description': 'Post added successfully (POST)'},
        400: {'description': 'Missing required fields'},
        401: {'description': 'Unauthorized'}
    }
})
def api_posts():
    if request.method == 'POST':
        # API key verification
        key = request.headers.get('x-api-key')
        if key != API_KEY:
            return jsonify({"error": "Unauthorized"}), 401

        # Get form data
        title = request.form.get('title')
        content = request.form.get('content')
        author = request.form.get('author')
        image_file = request.files.get('image_file')

        if not title or not content or not author:
            return jsonify({"error": "Missing required fields"}), 400

        # Save image if provided
        image_url = None
        if image_file and image_file.filename:
            filename = secure_filename(image_file.filename)
            image_path = os.path.join('static/img', filename)
            image_file.save(image_path)
            image_url = f'/static/img/{filename}'

        # Insert into DB
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('INSERT INTO blog (title, content, author, image_url) VALUES (?, ?, ?, ?)',
                  (title, content, author, image_url))
        conn.commit()
        conn.close()

        return jsonify({"message": "Post added successfully"}), 201

    elif request.method == 'GET':
        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('SELECT id, title, content, author, image_url FROM blog')
        rows = c.fetchall()
        conn.close()

        posts = []
        for row in rows:
            posts.append({
                "id": row[0],
                "title": row[1],
                "content": row[2],
                "author": row[3],
                "image_url": row[4]
            })

        return jsonify(posts)


def has_post_access(username):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM authorised_posters WHERE LOWER(username) = LOWER(?)",(username,))
    result = cursor.fetchone()
    conn.close()
    return bool(result)


@app.route('/add-post', methods=['GET', 'POST'])
def add_post():
    if 'user' not in session:
        return redirect(url_for('login_register'))
    
    username = session.get('user')
    if not has_post_access(username):
        flash("Access denied: You are not authorised to add posts.", "danger")
        return redirect(url_for('blog'))
    

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        author = session.get('user')
        image_file = request.files.get('image_file')
        image_url = None

        if image_file and image_file.filename != '':
            filename = secure_filename(image_file.filename)
            upload_path = os.path.join('static/img', filename)
            image_file.save(upload_path)
            image_url = f'/static/img/{filename}'

        conn = sqlite3.connect('users.db')
        c = conn.cursor()
        c.execute('INSERT INTO blog (title, content, author, image_url) VALUES (?, ?, ?, ?)',
                  (title, content, author, image_url))
        conn.commit()
        conn.close()

        flash('Post added successfully!', 'success')
        return redirect(url_for('blog'))

    return render_template('add_post.html')   

@app.context_processor
def inject_access_checker():
    return dict(has_post_access=has_post_access)



@app.route('/edit/<int:post_id>', methods=['GET', 'POST'])
def edit_post(post_id):
    conn = sqlite3.connect('users.db')
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    if request.method == 'POST':
        title = request.form['title']
        content = request.form['content']
        image_file = request.files.get('image_file')

        # Get current image_url in case no new file is uploaded
        cursor.execute("SELECT image_url FROM blog WHERE id=?", (post_id,))
        existing = cursor.fetchone()
        image_url = existing['image_url'] if existing else None

        # If new image uploaded, save it and update path
        if image_file and image_file.filename != '':
            filename = secure_filename(image_file.filename)
            image_path = os.path.join('static/img', filename)
            image_file.save(image_path)
            image_url = f'/static/img/{filename}'

        # Update the blog post
        cursor.execute(
            "UPDATE blog SET title=?, content=?, image_url=? WHERE id=?",
            (title, content, image_url, post_id)
        )
        conn.commit()
        conn.close()
        return redirect(url_for('blog'))

    # Handle GET
    cursor.execute("SELECT * FROM blog WHERE id=?", (post_id,))
    post = cursor.fetchone()
    conn.close()
    return render_template('edit_post.html', post=post)


@app.route('/delete/<int:post_id>', methods=['GET'])
def delete_post(post_id):
    conn = sqlite3.connect('users.db')
    cursor = conn.cursor()

    # First fetch the post (before deleting)
    cursor.execute("SELECT * FROM blog WHERE id=?", (post_id,))
    post = cursor.fetchone()

    if post:
        # Get column names
        column_names = [desc[0] for desc in cursor.description]
        post_dict = dict(zip(column_names, post))

        # Store post in session
        session['deleted_post'] = post_dict

        # Now delete the post
        cursor.execute("DELETE FROM blog WHERE id=?", (post_id,))
        conn.commit()

        flash('Post deleted. <a href="/undo-delete" style="color:blue; text-decoration:underline;">Undo</a>', 'success')
    else:
        flash('Post not found.', 'error')

    conn.close()
    return redirect(url_for('blog'))

 
@app.route('/undo-delete')
def undo_delete():
    post = session.get('deleted_post')

    if post:
        conn = sqlite3.connect('users.db')
        cursor = conn.cursor()

        # Insert only the existing columns (no date_posted)
        cursor.execute("""
            INSERT INTO blog (id, title, content, author, image_url)
            VALUES (?, ?, ?, ?, ?)
        """, (
            post['id'],
            post['title'],
            post['content'],
            post['author'],
            post['image_url']
        ))

        conn.commit()
        conn.close()

        session.pop('deleted_post', None)
        flash('Post restored successfully.', 'success')
    else:
        flash('Nothing to undo.', 'error')

    return redirect(url_for('blog'))


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
            traceback.print_exc()  #  This will show the exact cause in your terminal
            flash("Message submitted but failed to send confirmation email.", "danger")
        return render_template('contact.html', success=True)

    return render_template('contact.html')

#=======================detecting location================ 
 # Add this function below the imports
def get_city_from_ip():
    try:
        response = requests.get("https://ipinfo.io", timeout=3)
        ip_data = response.json()
        return ip_data.get("city", "Hyderabad")  # fallback
    except:
        return "Hyderabad"
                                                                                
# PLACE YOUR CITY DATA HERE
city_data = {
    "Hyderabad": {
        "monthly_guide": [
            " Sow cotton, red gram, and maize this month.",
            " Use mulching to conserve moisture during hot spells.",
            " Monitor leafhoppers and aphids weekly."
        ],
        "pest_alert": (
            "- **Red cotton bug** active in dry spells.<br>"
            "- Spray neem extract weekly.<br>"
            "- Install pheromone traps around the field."
        ),
        "fertilizer_tip": (
            "- Apply **DAP** during initial soil preparation.<br>"
            "- Use split doses of **urea** for better nitrogen efficiency.<br>"
            "- Add **zinc sulphate** for micronutrient boost."
        )
    },
    "Delhi": {
        "monthly_guide": [
            " Transplant tomatoes and chilies this month.",
            " Prepare seedbeds with FYM (Farmyard Manure).",
            " Irrigate every 7–10 days in sandy soils."
        ],
        "pest_alert": (
            "- **Whitefly alert** on leafy vegetables.<br>"
            "- Deploy sticky yellow traps.<br>"
            "- Avoid excess nitrogen application."
        ),
        "fertilizer_tip": (
            "- Apply **potash** for root crops like carrots and beets.<br>"
            "- Split **urea** in two doses: sowing + 15 days.<br>"
            "- Combine with **bone meal** for phosphorus."
        )
    },
    "Chennai": {
        "monthly_guide": [
            " Continue paddy transplanting in well-irrigated fields.",
            " Test soil pH before fertilizer application.",
            " Monitor for signs of early leaf blight."
        ],
        "pest_alert": (
            "- **Stem borer** may appear in paddy.<br>"
            "- Use Tricho-cards (Trichogramma).<br>"
            "- Avoid late-night flood irrigation."
        ),
        "fertilizer_tip": (
            "- Use **urea** + **super phosphate** during planting.<br>"
            "- Add **potassium** to improve stem strength.<br>"
            "- Prefer organic inputs in water-logged areas."
        )
    }
}


#==============crop advisory====================#

@app.route("/crop-advisory")
def crop_advisory():
    city = request.args.get('city')
    if city:
        city = city.strip().title()
    else:
        city = get_city_from_ip()

    api_key = "3f44e391e85821f7634676e916b9babc"

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
        print(" Error fetching weather for", city)

    # Crop suggestions based on temperature
    if 28 <= temperature <= 35:
        crops = ['Maize', 'Cotton', 'Paddy']
    elif temperature < 28:
        crops = ['Wheat', 'Barley']
    else:
        crops = ['Millets', 'Sorghum']


    #  Use city-specific tips if available in city_data
    if city in city_data:
        print(" City-specific tips loaded for:", city)
        monthly_guide = city_data[city]["monthly_guide"]
        pest_alert = city_data[city]["pest_alert"]
        fertilizer_tip = city_data[city]["fertilizer_tip"]
    else:
        print(" No specific data for", city)

        # 🌾 Default fallback content
        monthly_guide = [
            "- General advice: Prepare land and check irrigation systems.",
            "- Apply organic compost before sowing."
        ]
        pest_alert = (
            "- General pest watch:<br>"
            "- Check for aphids or leaf spot weekly.<br>"
            "- Use neem-based sprays if needed."
        )
        fertilizer_tip = (
            "- Add nitrogen-based fertilizer 15 days after sowing.<br>"
            "- Avoid over-fertilizing. Use compost where possible."
        )

          

    return render_template("crop_advisory.html",
                           temperature=temperature,
                           weather_desc=weather_desc,
                           weather_icon=weather_icon,
                           city=city,
                           crops=crops,
                           monthly_guide=monthly_guide,
                           pest_alert=pest_alert,
                           fertilizer_tip=fertilizer_tip)





@app.route('/subscribe', methods=['POST'])
def subscribe():
    email = request.form['email']
    return_url = request.form.get('return_url', url_for('home'))
    
    print("New subscriber:", email)
    flash("You are successfully subscribed!")
    
    return redirect(return_url)

# =================== RUN APP ===================
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)







