from flask import Flask, render_template

app = Flask(__name__)

@app.route('/')
def home():
    return 'Hello, World!'

@app.route('/test')
def test():
    return render_template("test.html")

@app.route('/about')
def about():
    return 'About'
