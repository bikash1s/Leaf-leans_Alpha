import os
import tensorflow as tf
import numpy as np
from flask import flash, send_from_directory
from flask import Flask, render_template, request, redirect, url_for, session, make_response, jsonify
from flask_mysqldb import MySQL
import MySQLdb.cursors
import re

app = Flask(__name__)

# MySQL Configuration
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_PORT'] = 3307
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = ''
app.config['MYSQL_DB'] = 'mydatabase'
app.secret_key = 'key'

mysql = MySQL(app)

# Prevent caching
@app.after_request
def add_header(response):
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, public, max-age=0"
    response.headers["Pragma"] = "no-cache"
    response.headers["Expires"] = "0"
    return response


#-----------------Login/ SignIn-------------------
@app.route('/', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST' and 'username' in request.form and 'password' in request.form:
        username = request.form['username']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s AND password = %s', (username, password,))
        account = cursor.fetchone()

        if account:
            session['loggedin'] = True
            session['id'] = account['id']
            session['username'] = account['username']
            return render_template('index.html', msg="Login successful!", msg_icon="success", msg_title="Welcome", redirect_url=url_for('index'))
        else:
            return render_template('index.html', msg="Incorrect username/password!", msg_icon="error", msg_title="Login Failed")

    return render_template('index.html')


#---------------Logout------------
@app.route('/logout')
def logout():
    # Clear session data
    session.pop('loggedin', None)
    session.pop('id', None)
    session.pop('username', None)
    
    # Create a response to redirect to the sign-in page
    response = make_response(redirect(url_for('signin')))
    
    # Add headers to prevent caching
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate, public, max-age=0'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    
    # Add script to clear browser history
    response.set_data(response.get_data(as_text=True) + "<script>window.history.replaceState({}, '', '/signin');</script>")
    
    return response



#-------------------Register/ SignUp-----------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    msg = ''
    msg_icon = ''
    msg_title = ''
    redirect_url = None
    
    if request.method == 'POST' and 'username' in request.form and 'email' in request.form and 'password' in request.form:
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
        account = cursor.fetchone()
        
        cursor.execute('SELECT * FROM users WHERE email = %s', (email,))
        email_account = cursor.fetchone()

        if account:
            msg = 'Account with this username already exists!'
            msg_icon = 'error'
            msg_title = 'Sign Up Failed'
            redirect_url = url_for('signup')
        
        elif email_account:
            msg = 'An account with this email already exists!'
            msg_icon = 'error'
            msg_title = 'Sign Up Failed'
            redirect_url = url_for('signup')

        elif not re.match(r'[^@]+@[^@]+\.[^@]+', email):
            msg = 'Invalid email address!'
            msg_icon = 'error'
            msg_title = 'Sign Up Failed'
            redirect_url = url_for('signup')

        elif not re.match(r'[A-Za-z0-9]+', username):
            msg = 'Username must contain only characters and numbers!'
            msg_icon = 'error'
            msg_title = 'Sign Up Failed'
            redirect_url = url_for('signup')

        elif not username or not password or not email:
            msg = 'Please fill out the form!'
            msg_icon = 'error'
            msg_title = 'Sign Up Failed'
            redirect_url = url_for('signup')
        else:
            cursor.execute('INSERT INTO users (username, email, password) VALUES (%s, %s, %s)', (username, email, password))
            mysql.connection.commit()
            msg = 'You have successfully registered!'
            msg_icon = 'success'
            msg_title = 'Sign Up Successful'
            redirect_url = url_for('signin')
    
    elif request.method == 'POST':
        msg = 'Please fill out the form!'
        msg_icon = 'error'
        msg_title = 'Sign Up Failed'
    
    return render_template('user_signup.html', msg=msg, msg_icon=msg_icon, msg_title=msg_title, redirect_url=redirect_url)


#---------------Home page----------------
@app.route('/home')
def index():
    if 'loggedin' in session:
        return render_template('home.html', username=session['username'])
    else:
        return redirect(url_for('signin'))

#---------------User profile-------------
@app.route('/user_profile')
def user_profile():
    # Check if the user is logged in
    if 'loggedin' in session:
        # We need all the account info for the user so we can display it on the profile page
        cursor = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        cursor.execute('SELECT * FROM users WHERE id = %s', (session['id'],))
        account = cursor.fetchone()
        # Show the profile page with account info
        return render_template('user_profile.html', account=account)
    # User is not logged in redirect to login page
    return redirect(url_for('index'))

#--------Diagnosis--------------
# Load the TensorFlow model
model = tf.keras.models.load_model('trained_model.keras')

@app.route('/diagnosis', methods=['GET', 'POST'])
def diagnosis():
    if request.method == 'POST':
        test_image = request.files['image']
        image_path = os.path.join('uploads', test_image.filename)
        test_image.save(image_path)
        
        # Get the prediction result
        result_index = model_prediction(image_path)
        class_name = ['Corn(maize) Cercospora Gray leaf spot',
                     'Corn(maize) healthy',
                     'Mango Powdery mildew',
                     'Mango healthy',
                     'Potato Early blight',
                     'Potato healthy',
                     'Rice Brown Spot',
                     'Rice healthy']
        prediction = class_name[result_index]

        # Pass the image filename to the template
        return render_template('diagnosis.html', prediction=prediction, uploaded_image=test_image.filename)

    return render_template('diagnosis.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory('uploads', filename)

def model_prediction(test_image):
    image = tf.keras.preprocessing.image.load_img(test_image, target_size=(128, 128))
    input_arr = tf.keras.preprocessing.image.img_to_array(image)
    input_arr = np.array([input_arr]) 
    predictions = model.predict(input_arr)
    return np.argmax(predictions)

@app.route('/service')
def service():
    return render_template('service.html')

@app.route('/blog', methods=['GET'])
def blog():
    # Fetch the list of blog posts from the database
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM blog_posts ORDER BY date_posted DESC")
    blog_posts = cur.fetchall()
    
    # Render the blog page with the list of blog posts
    return render_template('blog.html', blog_posts=blog_posts)

@app.route('/about')
def about():
    return render_template('about.html')

@app.route('/contact')
def contact():
    return render_template('contact.html')

#---------APPLE---------
@app.route('/apple')
def apple():
    return render_template('apple.html')

@app.route('/cedarapplerust')
def cedarapplerust():
    return render_template('Cedar_Apple_Rust.html')

#------------MANGO-----------
@app.route('/mango')
def mango():
    return render_template('mango.html')

@app.route('/mango_powdery_mildew')
def mango_powdery_mildew():
    return render_template('mango_powdery_mildew.html')

#------------RICE-----------
@app.route('/rice')
def rice():
    return render_template('rice.html')

@app.route('/rice_brown_spot')
def rice_brown_spot():
    return render_template('rice_brown_spot.html')

#---------TOMATO---------
@app.route('/tomato')
def tomato():
    return render_template('tomato.html')

@app.route('/tomato_septoria_leaf_spot')
def tomato_septoria_leaf_spot():
    return render_template('Tomato_Septoria_Leaf_Spot.html')

#---------GRAPE---------
@app.route('/grape')
def grape():
    return render_template('grape.html')

@app.route('/grape_leaf_blight')
def grape_leaf_blight():
    return render_template('grape_leaf_blight.html')

#-----------cherry---------
@app.route('/cherry')
def cherry():
    return render_template('cherry.html')

@app.route('/cherry_powdery_mildew')
def cherrypowderymildew():
    return render_template('cherry_powdery_mildew.html')

#-------CORN-------------
@app.route('/corn')
def corn():
    return render_template('corn.html')

@app.route('/corn_grey_leaf_spot')
def corn_grey_leaf_spot():
    return render_template('corn_grey_leaf_spot.html')

#---------STRAWBERRY---------
@app.route('/strawberry')
def strawberry():
    return render_template('strawberry.html')

@app.route('/strawberry_leaf_scorch')
def strawberry_leaf_scorch():
    return render_template('strawberry_leaf_scorch.html')

#---------POTATO---------
@app.route('/potato')
def potato():
    return render_template('potato.html')

@app.route('/potato-early_blight')
def potato_early_blight():
    return render_template('potato-early_blight.html')

#---------SOYBEAN---------
@app.route('/soybean')
def soybean():
    return render_template('soybean.html')

@app.route('/soybean_cercospora_leaf_blight')
def soybean_cercospora_leaf_blight():
    return render_template('Soybean_Cercospora_Leaf_Blight.html')

#---------SQUASH---------
@app.route('/squash')
def squash():
    return render_template('squash.html')

@app.route('/squash_powdery_mildew')
def squashpowderymildew():
    return render_template('squash_powdery_mildew.html')

#---------ORANGE---------
@app.route('/orange')
def orange():
    return render_template('orange.html')

@app.route('/Orange_Haunglongbing')
def Orange_Haunglongbing():
    return render_template('Orange_Haunglongbing(Citrus_greening).html')

#-------------------------------ADMIN----------------------------------
@app.route('/admin', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Query the database to check if the admin exists
        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM admin WHERE username = %s AND password = %s", (username, password))
        admin = cur.fetchone()
        
        if admin:
            session['loggedin'] = True
            session['admin_id'] = admin[0]  # Access the first element of the tuple (id)
            session['username'] = admin[1]  # Access the second element of the tuple (username)
            return redirect(url_for('admin_dashboard'))
        else:
            # Failed login attempt, trigger SweetAlert with error message
            return render_template('admin/admin_login.html', 
                                   msg="Incorrect username or password!", 
                                   msg_icon="error", 
                                   msg_title="Login Failed")
    return render_template('admin/admin_login.html')


@app.route('/admin/dashboard')
def admin_dashboard():
    if 'loggedin' in session:
        admin_id = session['admin_id']
        # Query the database to retrieve the admin's username
        cur = mysql.connection.cursor()
        cur.execute("SELECT username FROM admin WHERE id = %s", (admin_id,))
        admin_username = cur.fetchone()[0]
        
        # Fetch the count of blog posts
        cur.execute("SELECT COUNT(*) FROM blog_posts")
        blog_count = cur.fetchone()[0]
        
        # Fetch the count of users
        cur.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        
        # Render the admin dashboard page with the admin's username, blog count, and user count
        flash('Welcome, ' + admin_username + '!')
        return render_template('admin/dashboard.html', current_user={'username': admin_username, 'blog_count': blog_count, 'user_count': user_count})
    else:
        flash('You are not logged in. Please log in to access the dashboard.')
        return redirect(url_for('admin_login'))
    
@app.route('/admin/logout', methods=['GET', 'POST'])
def admin_logout():
    # Handle the logout logic here
    session.pop('loggedin', None)
    session.pop('admin_id', None)
    flash('Logged out successfully!')
    return redirect(url_for('admin_login'))  # Redirect to admin_login page

#--------------Users---------------
@app.route('/adminuser', methods=['GET', 'POST'])
def adminuser():
     cur = mysql.connection.cursor()
     cur.execute("SELECT id, username, email, password FROM users")
     users = cur.fetchall()  # Fetch all users from the database
     cur.close()

    # Pass the user data to the template
    
     return render_template('admin/table.html', users=users)

@app.route("/update/<int:user_id>", methods=["GET", "POST"])
def update_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    if request.method == "POST":
        username = request.form["username"]
        email = request.form["email"]
        password = request.form["password"]
        cur.execute("UPDATE users SET username = %s, email = %s, password = %s WHERE id = %s", (username, email, password, user_id))
        mysql.connection.commit()
        return redirect(url_for("adminuser"))
    return render_template("admin/update_user.html", user=user)

@app.route("/delete/<int:user_id>", methods=["GET"])
def delete_user(**kwargs):
    user_id = kwargs.get('user_id')
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", (user_id,))
    user = cur.fetchone()
    if user is None:
        return jsonify({"error": "User not found"}), 404

    cur.execute("DELETE FROM users WHERE id = %s", (user_id,))
    mysql.connection.commit()
    return redirect(url_for("adminuser"))

#--------------Blog---------------
@app.route('/blog_form', methods=['GET', 'POST'])
def blog_form():
    if request.method == 'POST':
        # Get the form data
        title = request.form['title']
        content = request.form['content']
        
        # Insert the new blog post into the database
        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO blog_posts (title, content, date_posted) VALUES (%s, %s, NOW())", (title, content))
        mysql.connection.commit()
        
        # Redirect to the blog page
        return redirect(url_for('blog_form'))
    
    # Render the blog form page
    return render_template('admin/blog_form.html')


if __name__ == "__main__":
    app.run(debug=True, port=8000)