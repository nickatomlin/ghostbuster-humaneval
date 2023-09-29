import boto3
import json
import os
import random
import uuid

from flask import Flask, render_template, session, request, g
from flask_session import Session

with open("config.json", "r") as file:
    config = json.load(file)

s3 = boto3.client('s3',
    aws_access_key_id=config['AWS_ACCESS_KEY_ID'],
    aws_secret_access_key=config['AWS_SECRET_ACCESS_KEY'],
    region_name=config['AWS_REGION_NAME']
)

app = Flask(__name__)
app.secret_key = os.urandom(24)
app.config['SESSION_PERMANENT'] = True
app.config['SESSION_TYPE'] = 'filesystem'  # or you can use 'redis', 'memcached', etc.
Session(app)

user_logs = {}

def load_essays(folder):
    essays = []
    for filename in os.listdir(folder):
        with open(os.path.join(folder, filename), 'r') as f:
            essays.append({'text': f.read(), 'source': folder})
    return essays

all_essays = load_essays('human') + load_essays('ai')
random.shuffle(all_essays)

@app.route("/", methods=['GET', 'POST'])
def index():
    session_id = g.session_id  # Get the session_id stored in the global object
    print(f"Session ID: {session_id}")
    print(f"User Logs Keys: {user_logs.keys()}")
    
    user_log = user_logs.get(session_id)
    if user_log is None:
        print("User log not found, initializing...")
        user_logs[session_id] = {'essays': [], 'total_accuracy': 0, 'correct_guesses': 0, 'current_index': 0}
        user_log = user_logs[session_id]
    
    current_index = user_log['current_index']    
    
    if current_index >= len(all_essays):
        accuracy = (user_log['correct_guesses'] / len(all_essays)) * 100
        return render_template('index.html', end=True, accuracy=accuracy, examples_seen=len(all_essays))
        
    current_essay = all_essays[current_index]
    
    if request.method == 'POST':
        guess = request.form.get('guess')
        correct = (guess == current_essay['source'])
        
        if correct:
            user_log['correct_guesses'] += 1
        
        user_log['essays'].append({
            'essay': current_essay['text'],
            'guess': guess,
            'correct': correct
        })
        
        user_log['current_index'] += 1  # move to the next essay
        
        if user_log['current_index'] < len(all_essays):
            next_essay = all_essays[user_log['current_index']]
            accuracy = (user_log['correct_guesses'] / user_log['current_index']) * 100
            return render_template('index.html', correct=correct, current_essay=current_essay, next_essay=next_essay, accuracy=accuracy, examples_seen=user_log['current_index'])
        else:
            accuracy = (user_log['correct_guesses'] / len(all_essays)) * 100
            return render_template('index.html', end=True, correct=correct, current_essay=current_essay, accuracy=accuracy, examples_seen=len(all_essays))
    
    next_essay = all_essays[user_log['current_index']]
    return render_template('index.html', correct=None, current_essay=current_essay, next_essay=next_essay, accuracy=0, examples_seen=user_log['current_index'])


@app.before_request
def before_request():
    if 'session_id' not in session:
        session_id = str(uuid.uuid4())
        session['session_id'] = session_id  # store session_id in session to access it in other routes
        user_logs[session_id] = {'essays': [], 'total_accuracy': 0, 'correct_guesses': 0, 'current_index': 0}
        print(f"New session_id created: {session_id}")
    else:
        session_id = session['session_id']
    g.session_id = session_id


@app.teardown_request
def upload_log(exception=None):
    session_id = g.get('session_id')
    if session_id:
        user_log = user_logs.get(session_id)
        if user_log and user_log['essays']:
            user_log['total_accuracy'] = "%.1f" % ((user_log['correct_guesses'] / (user_log['current_index'] or 1)) * 100)
            log_json = json.dumps(user_log)
            bucket_name = 'ghostbuster'
            key = f"user_logs/{session_id}.json"  # unique for each user session
            try:
                s3.put_object(Bucket=bucket_name, Key=key, Body=log_json, ContentType='application/json')
            except Exception as e:
                app.logger.error("Unable to upload log to S3: %s", e)
        # Remove the log from the dictionary after uploading to S3.
        # user_logs.pop(session_id, None)

if __name__ == "__main__":
    app.run(debug=True)
