from flask import Flask
from threading import Thread

app = Flask('')

@app.route('/')
def home():
    return "NEXUS SYSTEM: System is Online and Running!"

def run():
    # Render ya Repl.it ke liye port 8080 best rehta hai
    app.run(host='0.0.0.0', port=8080)

def keep_alive():
    t = Thread(target=run)
    t.daemon = True
    t.start()
