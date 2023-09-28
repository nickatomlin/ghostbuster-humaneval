from flask import Flask, render_template, session, request
import os
import random

app = Flask(__name__)
app.secret_key = os.urandom(24)

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
    if 'current_index' not in session or session['current_index'] >= len(all_essays):
        session['current_index'] = 0
        session['correct_guesses'] = 0
    
    current_essay = all_essays[session['current_index']]
    if request.method == 'POST':
        guess = request.form.get('guess')
        correct = (guess == current_essay['source'])
        if correct:
            session['correct_guesses'] += 1

        session['current_index'] += 1  # move to the next essay
        if session['current_index'] < len(all_essays):
            next_essay = all_essays[session['current_index']]
            accuracy = (session['correct_guesses'] / session['current_index']) * 100
            return render_template('index.html', correct=correct, current_essay=current_essay, next_essay=next_essay, accuracy=accuracy, examples_seen=session['current_index'])
        else:
            accuracy = (session['correct_guesses'] / len(all_essays)) * 100
            return render_template('index.html', end=True, correct=correct, current_essay=current_essay, accuracy=accuracy, examples_seen=len(all_essays))

    next_essay = all_essays[session['current_index']]
    return render_template('index.html', correct=None, current_essay=current_essay, next_essay=next_essay, accuracy=0)

if __name__ == "__main__":
    app.run(debug=True)
