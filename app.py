import os
import json
import random
import redis
import uuid
import boto3
from flask import Flask, render_template, session, g
from flask_socketio import SocketIO
from flask_session import Session

# Initialization and AWS Configuration
app = Flask(__name__)
app.secret_key = os.urandom(24)
# app.config['SESSION_PERMANENT'] = True
# app.config['SESSION_TYPE'] = 'filesystem'

app.config['SESSION_TYPE'] = 'redis'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['SESSION_KEY_PREFIX'] = 'ghostbuster:'
app.config['SESSION_REDIS'] = redis.from_url(os.environ.get('REDIS_URL') or 'redis://localhost:6379')

Session(app)
socketio = SocketIO(app)  # Allow all origins

# Try to get AWS credentials from environment variables first
aws_access_key_id = os.environ.get('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.environ.get('AWS_SECRET_ACCESS_KEY')
region_name = os.environ.get('AWS_REGION_NAME')

# If environment variables are not set, fall back to config.json
if not aws_access_key_id or not aws_secret_access_key or not region_name:
    try:
        with open('config.json', 'r') as f:
            config = json.load(f)
            aws_access_key_id = config.get('AWS_ACCESS_KEY_ID')
            aws_secret_access_key = config.get('AWS_SECRET_ACCESS_KEY')
            region_name=config['AWS_REGION_NAME']
    except FileNotFoundError:
        print("Error: config.json not found.")
    except json.JSONDecodeError:
        print("Error: config.json is not a valid JSON file.")
    except KeyError:
        print("Error: AWS keys not found in config.json.")

# At this point, if the AWS keys are None, you might want to handle it appropriately,
# maybe raise an exception, or log an error message, depending on your use case.
if not aws_access_key_id or not aws_secret_access_key or not region_name:
    raise ValueError("AWS credentials not found in environment variables or config.json.")

# Setting up S3 client
s3 = boto3.client('s3',
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    region_name=region_name
)

def load_essays(folder):
    essays = []
    for filename in os.listdir(folder):
        with open(os.path.join(folder, filename), 'r') as f:
            essays.append({'text': f.read(), 'source': folder})
    return essays

all_essays = load_essays('human') + load_essays('ai')
random.shuffle(all_essays)

user_logs = {}

@app.route("/")
def index():
    session_id = session.get('session_id')
    print("session_id type before: ", type(session_id))
    if isinstance(session_id, bytes):
        session_id = session_id.decode('utf-8')
    if not session_id:
        session_id = str(uuid.uuid4())
        print(f"Setting session_id: {session_id}, Type: {type(session_id)}")  # Debugging line
        session['session_id'] = session_id
    print("session_id type after: ", type(session_id))
    # session_id = str(session.get('session_id', uuid.uuid4()))
    # session['session_id'] = session_id
    if session_id not in user_logs:
        user_logs[session_id] = {'essays': [], 'total_accuracy': 0, 'correct_guesses': 0, 'current_index': 0}
        
        # You can shuffle and pick the first essay here if needed or just pick the first one from the all_essays list.
        current_essay = random.choice(all_essays)
        next_essay_index = (all_essays.index(current_essay) + 1) % len(all_essays)
        next_essay = all_essays[next_essay_index]
    else:
        user_log = user_logs[session_id]
        current_index = user_log['current_index']
        current_essay = all_essays[current_index]
        next_essay = all_essays[(current_index + 1) % len(all_essays)]

    print("About to return!")
    return render_template('index.html', current_essay=current_essay, next_essay=next_essay)

def upload_to_s3(session_id):
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


@socketio.on('make_guess')
def handle_guess(data):
    print("Received guess: " + str(data))
    session_id = session.get('session_id')
    user_log = user_logs[session_id]

    guess = data.get('guess')
    current_index = user_log['current_index']
    current_essay = all_essays[current_index]

    correct = (guess == current_essay['source'])
    user_log['correct_guesses'] += correct
    user_log['essays'].append({'essay': current_essay['text'], 'guess': guess, 'correct': correct})
    user_log['current_index'] += 1

    next_index = user_log['current_index']
    next_essay = all_essays[next_index] if next_index < len(all_essays) else None

    accuracy = (user_log['correct_guesses'] / user_log['current_index']) * 100
    
    # Call upload_to_s3 after processing each guess
    upload_to_s3(session_id)
    
    socketio.emit('result', {'correct': correct, 'next_essay': next_essay, 'accuracy': accuracy, 'guess': guess, 'current_index': current_index})

# Remove or comment out the app.teardown_request decorator as it's not needed anymore.
# @app.teardown_request
# def upload_log(exception=None):
#     # Function body here...


# @app.before_request
# def before_request():
#     if 'session_id' not in session:
#         session_id = str(uuid.uuid4())
#         session['session_id'] = session_id  # store session_id in session to access it in other routes
#         user_logs[session_id] = {'essays': [], 'total_accuracy': 0, 'correct_guesses': 0, 'current_index': 0}
#         print(f"New session_id created: {session_id}")
#     else:
#         session_id = session['session_id']
#     g.session_id = session_id

# @app.teardown_request
# def upload_log(exception=None):
#     session_id = g.get('session_id')
#     if session_id:
#         user_log = user_logs.get(session_id)
#         if user_log and user_log['essays']:
#             user_log['total_accuracy'] = "%.1f" % ((user_log['correct_guesses'] / (user_log['current_index'] or 1)) * 100)
#             log_json = json.dumps(user_log)
#             bucket_name = 'ghostbuster'
#             key = f"user_logs/{session_id}.json"  # unique for each user session
#             try:
#                 s3.put_object(Bucket=bucket_name, Key=key, Body=log_json, ContentType='application/json')
#             except Exception as e:
#                 app.logger.error("Unable to upload log to S3: %s", e)
#         # Remove the log from the dictionary after uploading to S3.
#         # user_logs.pop(session_id, None)

if __name__ == "__main__":
    socketio.run(app, debug=True)