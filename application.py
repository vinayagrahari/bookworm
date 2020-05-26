import os
import requests

from flask import Flask, session, request, render_template, redirect, url_for, jsonify
from flask_session import Session
from sqlalchemy import create_engine
from sqlalchemy.orm import scoped_session, sessionmaker
import simplejson as json
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "hello"
# set DATABASE_URL=postgres://jgnwsgdnhugfum:6660b9d161aab6a3b7123e3b63b7afea15111a4d75bc66971e7f8b297535ac4d@ec2-35-171-31-33.compute-1.amazonaws.com:5432/dbtg4mc7af63vo
# Check for environment variable

# Configure session to use filesystem
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Set up database
engine = create_engine("postgres://jgnwsgdnhugfum:6660b9d161aab6a3b7123e3b63b7afea15111a4d75bc66971e7f8b297535ac4d@ec2-35-171-31-33.compute-1.amazonaws.com:5432/dbtg4mc7af63vo")
db = scoped_session(sessionmaker(bind=engine))


@app.route("/")
def index():
    return render_template ("index.html")

@app.route('/feature')
def feature():
    return render_template('feature.html')

@app.route("/login", methods = ['get', 'post'])
def login():
    if request.method == 'POST':
        user = request.form.get("username")
        user_id = db.execute("SELECT id FROM users where username = :username", {"username": user})
        if user_id.rowcount == 0:
            return render_template ('error.html', message='Incorrect Username')
        else:
            user_id = user_id.fetchone()[0]
        data_password = db.execute("SELECT password FROM users WHERE id = :id", {"id": user_id}).fetchone()[0]
        password = request.form.get('password')
        if check_password_hash(data_password, password):
            session['username'] = user
            return redirect(url_for('user',username = user))
        return render_template ("error.html", message='Wrong password')
    else:
        return render_template("login.html")
        

@app.route('/signup', methods = ['get', 'post'])
def signup():
    if request.method == 'POST':
        name = request.form.get('name')
        username = request.form.get('username')
        password = request.form.get('password')
        password = generate_password_hash(password, "sha256")
        db.execute("INSERT INTO users (name, username, password) VALUES (:name, :username, :password)",
                        {'name': name, 'username': username, 'password': password})
        db.commit()
        session['username'] = username
        return redirect(url_for('user',username = username))
        
    else:
        return render_template('signup.html')


@app.route('/user/<username>')
def user(username):
    
    if session['username'] == username:
        user = session['username']
        return render_template('search.html', username=user)
    else:
        return render_template('signup.html')
@app.route('/logout')
def logout():
    session.pop("username", None)
    return redirect('/')

@app.route('/search', methods = ['POST'])
def search():
    key = request.form.get('key')
    key = '%' + key + '%'
    list = db.execute("SELECT * FROM books where title ilike :key or author ilike :key or isbn like :key", {'key':key})
    if list.rowcount == 0:
        return render_template('error.html', message='Sorry! No results found')
    list = list.fetchall()
    return render_template('list.html', list=list)

@app.route('/books/<int:book_id>', methods = ['GET', 'POST'])
def books(book_id):
    if request.method == 'GET':
        if 'username' in session:
            book = db.execute("SELECT * FROM books where id = :id", {'id':book_id}).fetchone()
            isbn = book.isbn
            res = requests.get("https://www.goodreads.com/book/review_counts.json", params={"key": "CTX21HbA6Q8QObENZAu6g", "isbns": isbn})
            if res.status_code != 200:
                return render_template('book_1.html', book=book)
            data = res.json()
            return render_template('book.html', book=book, data=data)
        return redirect('/signup')
    else:
        rating = request.form.get('star')
        review = request.form.get('detailed_review')
        user = db.execute("SELECT * FROM users where username = :username", {'username':session['username']}).fetchone()
        user_id = user.id
        book_rate = db.execute("SELECT * FROM review WHERE user_id = :user_id AND book_id = :book_id",
                                {'user_id':user_id, 'book_id':book_id})
        
        if book_rate.rowcount == 0:
            db.execute("INSERT INTO review (book_id, user_id, ratings, detail) VALUES (:book_id, :user_id, :rating, :review)",
                        {'book_id':book_id, 'user_id':user_id, 'rating':rating, 'review':review})
            db.commit()
        else:
            db.execute("UPDATE review SET ratings = :rating, detail = :review WHERE user_id = :user_id AND book_id = :book_id",
                        {'rating':rating, 'review':review, 'user_id':user_id, 'book_id':book_id})
            db.commit()
        user = user.username
        return render_template('search.html', username=user)

@app.route('/book_review/<int:book_id>')
def book_review(book_id):
    if 'username' in session:
        book = db.execute("SELECT * from books WHERE id = :id", {'id':book_id}).fetchone()
        review = db.execute('SELECT * from review join users on review.user_id = users.id where book_id = :id', {'id':book_id}).fetchall()
    
        return render_template('review.html', book=book, review=review)
    return redirect('/signup')

@app.errorhandler(500)
def errors(e):
    return render_template('500.html')

@app.route('/api/<string:book_isbn>')
def api_book(book_isbn):
    book = db.execute("SELECT * FROM books WHERE isbn = :isbn", {'isbn':book_isbn}).fetchone()
    if book is None:
        return jsonify({"error": "Invalid ISBN number"}), 404
    id = book.id
    review_count = db.execute("SELECT count(*) FROM review WHERE book_id = :id", {'id':id}).fetchone()[0]
    average_score = db.execute("SELECT avg(ratings) FROM review WHERE book_id = :id", {'id':id}).fetchone()[0]
    average_score = round(average_score, 2)
    return jsonify({
            "title": book.title,
            "author": book.author,
            "year": book.year,
            "isbn": book.isbn,
            "review_count": review_count,
            "average_score": average_score
        })
