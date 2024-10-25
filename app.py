from flask import Flask, render_template, request, redirect, url_for, flash, Response
from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
import csv
from io import StringIO

app = Flask(__name__)
app.secret_key = "your_secret_key"

# MySQL configurations
app.config['MYSQL_HOST'] = 'localhost'
app.config['MYSQL_USER'] = 'root'
app.config['MYSQL_PASSWORD'] = '752002'
app.config['MYSQL_DB'] = 'omsai_hardware_db'

mysql = MySQL(app)
bcrypt = Bcrypt(app)

# Flask-Login setup
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

class User(UserMixin):
    def __init__(self, id, username, email):
        self.id = id
        self.username = username
        self.email = email

@login_manager.user_loader
def load_user(user_id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM users WHERE id = %s", [user_id])
    user = cur.fetchone()
    if user:
        return User(user[0], user[1], user[2])
    return None

@app.route('/')
def index():
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM hardware_items")
    items = cur.fetchall()
    cur.close()
    return render_template('index.html', items=items)

# User Registration
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        password_hash = bcrypt.generate_password_hash(password).decode('utf-8')

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
                    (username, email, password_hash))
        mysql.connection.commit()
        flash('Your account has been created! You can now log in', 'success')
        return redirect(url_for('login'))
    return render_template('register.html')

# User Login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']

        cur = mysql.connection.cursor()
        cur.execute("SELECT * FROM users WHERE email = %s", [email])
        user = cur.fetchone()

        if user and bcrypt.check_password_hash(user[3], password):
            user_obj = User(user[0], user[1], user[2])
            login_user(user_obj)
            flash('Login successful!', 'success')
            return redirect(url_for('index'))
        else:
            flash('Login failed! Check email and password', 'danger')
    return render_template('login.html')

# User Logout
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('You have been logged out!', 'info')
    return redirect(url_for('login'))

@app.route('/add_item', methods=['GET', 'POST'])
@login_required
def add_item():
    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        quantity = request.form['quantity']
        price = request.form['price']
        supplier = request.form['supplier']

        cur = mysql.connection.cursor()
        cur.execute("INSERT INTO hardware_items (name, category, quantity, price, supplier) VALUES (%s, %s, %s, %s, %s)", 
                    (name, category, quantity, price, supplier))
        mysql.connection.commit()
        flash('Item added successfully!')
        return redirect(url_for('index'))

    return render_template('add_item.html')

@app.route('/delete_item/<int:id>')
@login_required
def delete_item(id):
    cur = mysql.connection.cursor()
    cur.execute("DELETE FROM hardware_items WHERE id = %s", [id])
    mysql.connection.commit()
    flash('Item deleted successfully!')
    return redirect(url_for('index'))

@app.route('/edit_item/<int:id>', methods=['GET', 'POST'])
@login_required
def edit_item(id):
    cur = mysql.connection.cursor()
    cur.execute("SELECT * FROM hardware_items WHERE id = %s", [id])
    item = cur.fetchone()

    if request.method == 'POST':
        name = request.form['name']
        category = request.form['category']
        quantity = request.form['quantity']
        price = request.form['price']
        supplier = request.form['supplier']

        cur.execute("""
        UPDATE hardware_items
        SET name = %s, category = %s, quantity = %s, price = %s, supplier = %s
        WHERE id = %s
        """, (name, category, quantity, price, supplier, id))
        mysql.connection.commit()
        flash('Item updated successfully!')
        return redirect(url_for('index'))

    return render_template('edit_item.html', item=item)

@app.route('/sale', methods=['GET', 'POST'])
@login_required
def sale():
    cur = mysql.connection.cursor()

    if request.method == 'GET':
        cur.execute("SELECT * FROM hardware_items")
        items = cur.fetchall()
        return render_template('sale.html', items=items)

    if request.method == 'POST':
        item_id = request.form['item_id']
        quantity_sold = int(request.form['quantity_sold'])
        sale_price = float(request.form['sale_price'])

        cur.execute("SELECT quantity FROM hardware_items WHERE id = %s", [item_id])
        item = cur.fetchone()
        current_quantity = item[0]

        if current_quantity < quantity_sold:
            flash('Not enough stock available for this sale.')
            return redirect(url_for('sale'))

        new_quantity = current_quantity - quantity_sold
        cur.execute("UPDATE hardware_items SET quantity = %s WHERE id = %s", (new_quantity, item_id))

        cur.execute("INSERT INTO sales (item_id, quantity_sold, sale_price) VALUES (%s, %s, %s)",
                    (item_id, quantity_sold, sale_price))

        mysql.connection.commit()
        flash('Sale recorded successfully!')
        return redirect(url_for('index'))

@app.route('/sales_history')
@login_required
def sales_history():
    cur = mysql.connection.cursor()
    cur.execute("""
        SELECT s.id, h.name, s.quantity_sold, s.sale_price, s.sale_date
        FROM sales s
        JOIN hardware_items h ON s.item_id = h.id
    """)
    sales = cur.fetchall()
    return render_template('sales_history.html', sales=sales)

@app.route('/report')
@login_required
def report():
    cur = mysql.connection.cursor()

    cur.execute("SELECT COUNT(*), SUM(quantity_sold), SUM(sale_price) FROM sales")
    total_sales = cur.fetchone()

    cur.execute("SELECT name, quantity FROM hardware_items")
    inventory = cur.fetchall()

    cur.execute("SELECT name, quantity FROM hardware_items WHERE quantity < 5")
    low_stock = cur.fetchall()

    return render_template('report.html', total_sales=total_sales, inventory=inventory, low_stock=low_stock)

@app.route('/restock', methods=['GET', 'POST'])
@login_required
def restock():
    cur = mysql.connection.cursor()

    if request.method == 'GET':
        cur.execute("SELECT * FROM hardware_items")
        items = cur.fetchall()
        return render_template('restock.html', items=items)

    if request.method == 'POST':
        item_id = request.form['item_id']
        quantity = int(request.form['quantity'])
        supplier = request.form['supplier']

        cur.execute("UPDATE hardware_items SET quantity = quantity + %s WHERE id = %s", (quantity, item_id))
        cur.execute("INSERT INTO restock (item_id, quantity, supplier) VALUES (%s, %s, %s)", (item_id, quantity, supplier))

        mysql.connection.commit()
        flash('Restock recorded successfully!')
        return redirect(url_for('index'))

# Export reports to CSV
@app.route('/export_report')
@login_required
def export_report():
    cur = mysql.connection.cursor()

    cur.execute("""
        SELECT s.id, h.name, s.quantity_sold, s.sale_price, s.sale_date
        FROM sales s
        JOIN hardware_items h ON s.item_id = h.id
    """)
    sales = cur.fetchall()

    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['ID', 'Item Name', 'Quantity Sold', 'Sale Price', 'Date'])

    for sale in sales:
        writer.writerow(sale)

    output = si.getvalue()
    si.close()
    response = Response(output, mimetype='text/csv')
    response.headers["Content-Disposition"] = "attachment; filename=sales_report.csv"
    return response

if __name__ == '__main__':
    app.run(debug=True)
