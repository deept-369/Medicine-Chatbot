from flask import Flask, render_template, request, jsonify
import json
import re
import os

app = Flask(__name__, static_folder='static', static_url_path='/static')

# Load JSON data
with open('health_problems.json', 'r', encoding='utf-8') as f:
    health_data = json.load(f)

with open('questions.json', 'r', encoding='utf-8') as f:
    questions_data = json.load(f)

with open('solutions.json', 'r', encoding='utf-8') as f:
    solutions_data = json.load(f)

# Store user sessions (in production, use proper session management)
user_sessions = {}

def find_health_problem(user_input):
    """Find matching health problem from user input"""
    user_input_lower = user_input.lower()
    
    for problem in health_data['health_problems']:
        # Check main name
        if problem['name'] in user_input_lower:
            return problem['name']
        
        # Check synonyms
        for synonym in problem['synonyms']:
            if synonym.lower() in user_input_lower:
                return problem['name']
    
    return None

def get_questions(health_problem):
    """Get questions for a specific health problem"""
    # Normalize the health problem name
    problem_key = health_problem.replace(' ', '_')
    
    if problem_key in questions_data['questions']:
        return questions_data['questions'][problem_key]
    
    return None

def get_prescription(health_problem, answers):
    """Generate prescription based on health problem and answers"""
    problem_key = health_problem.replace(' ', '_')
    prescription_key = f"{problem_key}_prescription_logic"
    
    if prescription_key not in solutions_data['solutions']:
        return None
    
    prescriptions = solutions_data['solutions'][prescription_key]
    
    # Collect all categories from answers
    categories = []
    for answer in answers:
        if 'category' in answer:
            categories.append(answer['category'])
    
    # Find the best matching prescription
    # Priority: specific category match > general category
    best_prescription = None
    
    for category in categories:
        if category in prescriptions:
            best_prescription = prescriptions[category]
            break
    
    # If no specific match, try to find a general one
    if not best_prescription and categories:
        # Use the first category as fallback
        if categories[0] in prescriptions:
            best_prescription = prescriptions[categories[0]]
    
    return best_prescription

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/start', methods=['POST'])
def start_chat():
    """Start a new chat session"""
    data = request.json
    user_input = data.get('message', '')
    session_id = data.get('session_id', 'default')
    
    # Find health problem
    health_problem = find_health_problem(user_input)
    
    if not health_problem:
        return jsonify({
            'status': 'not_found',
            'message': 'I could not identify your health concern. Please describe your symptoms more clearly. For example: "I have a headache", "I have fever", "I have stomach pain", etc.'
        })
    
    # Get questions
    questions = get_questions(health_problem)
    
    if not questions:
        return jsonify({
            'status': 'no_questions',
            'message': f'I identified that you may have {health_problem}, but I don\'t have detailed questions for this condition yet.'
        })
    
    # Store session
    user_sessions[session_id] = {
        'health_problem': health_problem,
        'questions': questions,
        'current_question': 0,
        'answers': []
    }
    
    return jsonify({
        'status': 'questions',
        'health_problem': health_problem,
        'message': f'I understand you may be experiencing {health_problem}. Let me ask you a few questions to provide better guidance.',
        'question': questions[0]['question'],
        'options': questions[0]['options'],
        'question_number': 1,
        'total_questions': len(questions)
    })

@app.route('/api/answer', methods=['POST'])
def process_answer():
    """Process user answer and return next question or prescription"""
    data = request.json
    session_id = data.get('session_id', 'default')
    answer_index = data.get('answer_index')
    
    if session_id not in user_sessions:
        return jsonify({
            'status': 'error',
            'message': 'Session expired. Please start again.'
        })
    
    session = user_sessions[session_id]
    current_q_index = session['current_question']
    questions = session['questions']
    
    # Store answer
    selected_option = questions[current_q_index]['options'][answer_index]
    session['answers'].append(selected_option)
    
    # Move to next question
    session['current_question'] += 1
    
    # Check if more questions
    if session['current_question'] < len(questions):
        next_question = questions[session['current_question']]
        return jsonify({
            'status': 'questions',
            'question': next_question['question'],
            'options': next_question['options'],
            'question_number': session['current_question'] + 1,
            'total_questions': len(questions)
        })
    
    # All questions answered - generate prescription
    prescription = get_prescription(session['health_problem'], session['answers'])
    
    if not prescription:
        return jsonify({
            'status': 'error',
            'message': 'Unable to generate prescription. Please consult a doctor.'
        })
    
    response = {
        'status': 'prescription',
        'health_problem': session['health_problem'],
        'prescription': prescription
    }
    
    # Clear session
    del user_sessions[session_id]
    
    return jsonify(response)

@app.route('/api/list_problems', methods=['GET'])
def list_problems():
    """List all available health problems"""
    problems = [problem['name'] for problem in health_data['health_problems']]
    return jsonify({'problems': problems})

if __name__ == '__main__':
    app.run(debug=True, port=5000)