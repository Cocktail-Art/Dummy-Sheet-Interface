import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import toml
from pathlib import Path
from datetime import datetime
import hashlib

# User credentials dictionary (username: password)
employees = [
    "Jitendra Ghormade", "Dinesh More", "Sankoch Ghadqhe", "Abhijit Jambhle",
    "Roshan Tamatta", "Sudhanshu Mane", "Omkar Chavan", "Shashi Shirsat", 
    "Saeed Shaikh", "Rahul Chaurasiya", "Disha Gokhlani", "Harsh Palavia",
    "Harsh Khurana", "Rishikesh Pawar", "Jesal Shah", "Rajendra Korgaonkar",
    "Darshana Bansode", "Vikram Bansode", "Anand Dhaware", "Maruti Tambe", "Garv Bhatia"
]

USER_CREDENTIALS = {}
for employee in employees:
    first_name, last_name = employee.split()
    email = f"{first_name[0].lower()}.{last_name.lower()}@123"
    USER_CREDENTIALS[employee] = email

def authenticate_user(username, password):
    """Check if username exists and password matches"""
    if username in USER_CREDENTIALS:
        return USER_CREDENTIALS[username] == password
    return False

for username, password in USER_CREDENTIALS.items():
    print(f"Username: {username}, Password: {password}")

# Initialize session state
if "authenticated" not in st.session_state:
    st.session_state.authenticated = False
if "current_user" not in st.session_state:
    st.session_state.current_user = None

# Login form
if not st.session_state.authenticated:
    st.title("Task Management Login")
    
    username = st.text_input("Username")
    password = st.text_input("Password", type="password")
    
    if st.button("Login"):
        if authenticate_user(username, password):
            st.session_state.authenticated = True
            st.session_state.current_user = username
            st.rerun()
        else:
            st.error("Invalid username or password")
    st.stop()

# Main application after successful login
def authenticate_google_sheets():
    try:
        secret_path = Path(r"secret.toml")
        secrets = toml.load(secret_path)
        
        scope = ["https://spreadsheets.google.com/feeds", 
                 "https://www.googleapis.com/auth/drive"]
        
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            secrets["gcp_service_account"], scope)
            
        client = gspread.authorize(creds)
        return client
        
    except FileNotFoundError:
        st.error("Secret file not found. Check the file path.")
        return None
    except Exception as e:
        st.error(f"Authentication failed: {str(e)}")
        return None

def get_current_tasks(gc, username):
    try:
        spreadsheet = gc.open("DataCollection")
        worksheet = spreadsheet.get_worksheet(0)
        records = worksheet.get_all_records()
        
        current_tasks = {}
        for row in reversed(records):
            name = row.get('Name', '')
            task = row.get('Key Task', '')
            if name == username and task:
                current_tasks[name] = task
                break  # Only need the latest task for the user
        return current_tasks
        
    except Exception as e:
        st.error(f"Error fetching tasks: {str(e)}")
        return {}

# Application header with logout
st.title(f"Task Management System - Welcome {st.session_state.current_user}")

# Rest of your existing application code
with st.sidebar:
    st.header("Current Focus")
    gc = authenticate_google_sheets()
    if gc:
        current_tasks = get_current_tasks(gc, st.session_state.current_user)
        if current_tasks:
            for name, task in current_tasks.items():
                st.markdown(f"""
                **{name}**  
                *Primary goal right now:*  
                {task}
                """)
                st.divider()
        else:
            st.info("No current tasks found")

with st.form("task_form"):
    name = st.session_state.current_user  # Automatically fill the name with the logged-in user
    key_task = st.text_input("Key Task")
    quantifiable_measures = st.text_input("Quantifiable Measures")
    
    submitted = st.form_submit_button("Submit Task")
    
    if submitted:
        gc = authenticate_google_sheets()
        if gc:
            try:
                spreadsheet = gc.open("DataCollection")
                worksheet = spreadsheet.get_worksheet(0)
                
                timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                worksheet.append_row([name, key_task, quantifiable_measures, timestamp])
                
                st.success("✅ Task successfully logged!")
                st.rerun()
                
            except Exception as e:
                st.error(f"Error: {str(e)}")
                
st.button("Logout", on_click=lambda: st.session_state.update({
    "authenticated": False,
    "current_user": None
}))
