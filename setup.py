from flask import Flask, render_template

app = Flask(__name__) # init flask server

@app.route('/')
def home():
    return render_template('setup.html')
