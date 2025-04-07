import streamlit as st
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import toml
from pathlib import Path
from datetime import datetime

# Constants
DEPARTMENTS = ['Marketing','Sales','Operations','Accounts','Management']
MONTHS = ["January", "February", "March", "April", "May", "June",
          "July", "August", "September", "October", "November", "December"]
STATUS_OPTIONS = ["Not Started", "Working", "Completed", "Incomplete"]
STATUS_EMOJIS = {
    "Not Started": "⏳",
    "Working": "🔄",
    "Completed": "✅",
    "Incomplete": "❌"
}

# Initialize session state
def init_session_state():
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
    if "current_user" not in st.session_state:
        st.session_state.current_user = None
    if "current_user_fullname" not in st.session_state:
        st.session_state.current_user_fullname = None
    if "current_user_role" not in st.session_state:
        st.session_state.current_user_role = None
    if "edit_mode" not in st.session_state:
        st.session_state.edit_mode = False
    if "current_dept" not in st.session_state:
        st.session_state.current_dept = None
    if "add_task_mode" not in st.session_state:
        st.session_state.add_task_mode = False
    if "selected_month" not in st.session_state:
        st.session_state.selected_month = "March"
    if "last_update_date" not in st.session_state:
        st.session_state.last_update_date = None

def navigate_home():
    """Reset all modes to show the dashboard"""
    st.session_state.edit_mode = False
    st.session_state.add_task_mode = False
    st.session_state.current_dept = None
    st.rerun()

# Authentication
@st.cache_data(ttl=3600)
def get_user_credentials(_gc):
    try:
        sheet = _gc.open("DataCollection").worksheet("Credentials")
        records = sheet.get_all_records()
        
        credentials = {}
        for record in records:
            if "Username" in record and "Password" in record and "Name" in record:
                credentials[record["Username"]] = {
                    "password": record["Password"],
                    "fullname": record["Name"],
                    "role": record.get("Role", "User")
                }
        return credentials
    except Exception as e:
        st.error(f"Error retrieving credentials: {e}")
        return {}

def authenticate_user(_gc, username, password):
    credentials = get_user_credentials(_gc)
    if username in credentials:
        if credentials[username]["password"] == password:
            st.session_state.current_user_fullname = credentials[username]["fullname"]
            st.session_state.current_user_role = credentials[username]["role"]
            return True
    return False

def login_page():
    st.title("Task Management Login")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        
        if st.form_submit_button("Login"):
            gc = get_gc()
            if not gc:
                st.error("Failed to connect to Google Sheets. Please try again later.")
                st.stop()
            
            if authenticate_user(gc, username, password):
                st.session_state.authenticated = True
                st.session_state.current_user = username
                st.rerun()
            else:
                st.error("Invalid credentials")
    st.stop()

# Google Sheets connection
@st.cache_resource(ttl=300)
def get_gc():
    try:
        secrets = toml.load(Path(r'secret.toml'))
        creds = ServiceAccountCredentials.from_json_keyfile_dict(
            secrets["gcp_service_account"],
            ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        )
        return gspread.authorize(creds)
    except Exception as e:
        st.error(f"Connection error: {e}")
        return None

# Data operations
@st.cache_data(ttl=60, show_spinner="Loading tasks...")
def get_user_data(_gc, fullname, month):
    try:
        sheet = _gc.open("DataCollection").worksheet("Goals")
        records = sheet.get_all_records()
        
        data = [
            {
                "department": row["Department"],
                "goal": row["Main Goal"],
                "tasks": [
                    {
                        "desc": row[f"Task {i}"].strip(),
                        "status": row[f"Task {i} Status"].strip() or "Not Started"
                    }
                    for i in range(1, 6)
                    if row.get(f"Task {i}", "").strip() and row[f"Task {i}"].strip() != "--"
                ],
                "row": idx + 2
            }
            for idx, row in enumerate(records)
            if row["Name"] == fullname and row["Month"] == month
        ]
        
        return data
    except Exception as e:
        st.error(f"Data error: {e}")
        return []

def update_entire_row(_gc, row, department, goal, tasks):
    try:
        sheet = _gc.open("DataCollection").worksheet("Goals")
        row_data = [st.session_state.current_user_fullname, department, goal, st.session_state.selected_month]
        for i in range(1, 6):
            if i <= len(tasks):
                row_data.extend([tasks[i-1]["desc"], tasks[i-1]["status"]])
            else:
                row_data.extend(["--", ""])
        sheet.update(f"A{row}:N{row}", [row_data])
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Update failed: {e}")
        return False

def add_new_task(_gc, fullname, month, department, goal, tasks):
    try:
        sheet = _gc.open("DataCollection").worksheet("Goals")
        new_row = [fullname, department, goal, month]
        for i in range(1, 6):
            if i <= len(tasks):
                new_row.extend([tasks[i-1]["desc"], tasks[i-1]["status"]])
            else:
                new_row.extend(["--", ""])
        sheet.append_row(new_row)
        st.cache_data.clear()
        return True
    except Exception as e:
        st.error(f"Add task failed: {e}")
        return False

def log_daily_update(_gc, fullname, date, update_text):
    try:
        sheet = _gc.open("DataCollection").worksheet("Daily Updates")
        all_data = sheet.get_all_values()
        
        if not all_data:
            st.error("No data found in Daily Updates sheet")
            return False
            
        headers = all_data[0]
        data_rows = all_data[1:]
        
        try:
            col_index = headers.index(date) + 1
        except ValueError:
            st.error(f"Date column {date} not found in sheet")
            return False
        
        name_col_index = headers.index("Name") + 1 if "Name" in headers else 0
        if name_col_index == 0:
            st.error("'Name' column not found in sheet")
            return False
            
        row_found = False
        row_number = None
        
        for i, row in enumerate(data_rows, start=2):
            if len(row) > name_col_index - 1 and row[name_col_index - 1] == fullname:
                sheet.update_cell(i, col_index, update_text)
                row_found = True
                break
        
        if not row_found:
            new_row = [""] * len(headers)
            new_row[name_col_index - 1] = fullname
            new_row[col_index - 1] = update_text
            sheet.append_row(new_row)
        
        return True
        
    except Exception as e:
        st.error(f"Failed to log daily update: {e}")
        return False

# Master Dashboard Components
def master_dashboard_page():
    st.title("Master Dashboard")
    st.write(f"Welcome Master {st.session_state.current_user_fullname}")
    
    gc = get_gc()
    if not gc:
        st.error("Failed to connect to Google Sheets")
        return
    
    with st.expander("👥 User Management"):
        try:
            sheet = gc.open("DataCollection").worksheet("Credentials")
            users = sheet.get_all_records()
            # st.dataframe(users)
            
            col1, col2 = st.columns(2)
            with col1:
                with st.form("add_user_form"):
                    st.subheader("Add New User")
                    new_username = st.text_input("Username")
                    new_password = st.text_input("Password", type="password")
                    new_name = st.text_input("Full Name")
                    new_role = st.selectbox("Role", ["User", "Master"])
                    
                    if st.form_submit_button("Add User"):
                        if new_username and new_password and new_name:
                            sheet.append_row([new_username, new_password, new_name, new_role])
                            st.success("User added successfully!")
                            st.rerun()
                        else:
                            st.error("Please fill all fields")
            
            with col2:
                with st.form("delete_user_form"):
                    st.subheader("Delete User")
                    delete_username = st.selectbox(
                        "Select user to delete",
                        [user["Username"] for user in users]
                    )
                    
                    if st.form_submit_button("Delete User"):
                        cell = sheet.find(delete_username)
                        sheet.delete_rows(cell.row)
                        st.success("User deleted successfully!")
                        st.rerun()
                        
        except Exception as e:
            st.error(f"Error accessing user data: {e}")
    
    with st.expander("📊 All Tasks Overview"):
        try:
            sheet = gc.open("DataCollection").worksheet("Goals")
            all_tasks = sheet.get_all_records()
            st.dataframe(all_tasks)
        except Exception as e:
            st.error(f"Error accessing tasks: {e}")
    
    with st.expander("📅 Daily Updates Monitor"):
        try:
            sheet = gc.open("DataCollection").worksheet("Daily Updates")
            updates = sheet.get_all_records()
            st.dataframe(updates)
        except Exception as e:
            st.error(f"Error accessing daily updates: {e}")

# Regular User Components
def sidebar_content():
    with st.sidebar:
        st.header("Task Management")
        
        if st.button("🏠 Home"):
            navigate_home()
        
        st.session_state.selected_month = st.selectbox(
            "Month", 
            MONTHS,
            index=MONTHS.index(st.session_state.get("selected_month", "March")))
        
        if st.button("➕ Add New Task"):
            st.session_state.add_task_mode = True
            st.session_state.edit_mode = False
            st.rerun()
        
        gc = get_gc()
        if gc and st.session_state.current_user_fullname:
            data = get_user_data(gc, st.session_state.current_user_fullname, st.session_state.selected_month)
            
            if not data:
                st.info("No tasks found for selected month")
            else:
                for dept in data:
                    with st.expander(f"{dept['department']} - {dept['goal']}", expanded=False):
                        st.markdown("**Main Tasks:**")
                        for task in dept["tasks"]:
                            st.markdown(
                                f"<p style='font-size: 14px;'>{STATUS_EMOJIS.get(task['status'], '⏳')} {task['desc']}</p>", 
                                unsafe_allow_html=True
                            )
                        if st.button(f"✏️ Edit", key=f"edit_{dept['department']}"):
                            st.session_state.edit_mode = True
                            st.session_state.current_dept = dept
                            st.rerun()

        if st.button("🚪 Logout"):
            st.session_state.clear()
            st.rerun()

def add_task_form():
    st.title("Add New Task")
    
    with st.form("add_task_form"):
        department = st.selectbox("Department", DEPARTMENTS, index=0)
        goal = st.text_input("Main Goal")
        
        st.markdown("**Tasks:**")
        tasks = []
        for i in range(5):
            cols = st.columns([4, 1])
            task_desc = cols[0].text_input(
                f"Task {i+1}",
                key=f"new_task_{i}",
                placeholder="Enter task description"
            )
            task_status = cols[1].selectbox(
                "Status",
                STATUS_OPTIONS,
                index=0,
                key=f"new_status_{i}"
            )
            if task_desc.strip():
                tasks.append({"desc": task_desc, "status": task_status})
        
        col1, col2 = st.columns(2)
        if col1.form_submit_button("💾 Save"):
            if not goal.strip():
                st.error("Please enter a main goal")
            elif not tasks:
                st.error("Please add at least one task")
            else:
                gc = get_gc()
                if gc and add_new_task(gc, st.session_state.current_user_fullname, 
                                      st.session_state.selected_month, department, goal, tasks):
                    st.session_state.add_task_mode = False
                    st.rerun()
        
        if col2.form_submit_button("✖️ Cancel"):
            st.session_state.add_task_mode = False
            st.rerun()

def edit_task_form():
    st.title(f"Edit {st.session_state.current_dept['department']} Tasks")
    
    with st.form("edit_form"):
        st.text_input("Department", value=st.session_state.current_dept['department'], disabled=True)
        goal = st.text_input("Main Goal", value=st.session_state.current_dept['goal'], key="edit_goal")
        
        st.markdown("**Tasks:**")
        tasks = st.session_state.current_dept["tasks"]
        edited_tasks = []
        
        for i in range(5):
            if i < len(tasks):
                task = tasks[i]
            else:
                task = {"desc": "", "status": "Not Started"}
            
            cols = st.columns([4, 1])
            task_desc = cols[0].text_input(
                f"Task {i+1}",
                value=task["desc"],
                key=f"edit_task_{i}",
                placeholder="Enter task description"
            )
            task_status = cols[1].selectbox(
                "Status",
                STATUS_OPTIONS,
                index=STATUS_OPTIONS.index(task["status"]),
                key=f"edit_status_{i}"
            )
            if task_desc.strip():
                edited_tasks.append({"desc": task_desc, "status": task_status})
        
        col1, col2 = st.columns(2)
        if col1.form_submit_button("💾 Save"):
            gc = get_gc()
            if gc and update_entire_row(
                gc,
                st.session_state.current_dept["row"],
                st.session_state.current_dept['department'],
                goal,
                edited_tasks
            ):
                st.session_state.edit_mode = False
                st.session_state.current_dept = None
                st.rerun()
        
        if col2.form_submit_button("✖️ Cancel"):
            st.session_state.edit_mode = False
            st.session_state.current_dept = None
            st.rerun()

def dashboard_page():
    st.title("Overview Dashboard")
    st.write(f"Welcome, {st.session_state.current_user_fullname or st.session_state.current_user}")
    
    if "last_update_date" not in st.session_state or not st.session_state.last_update_date:
        st.write("Use the sidebar to manage your tasks or click 'Add New Task' to get started")
    
    with st.form("daily_update_form"):
        today = st.date_input("Date", value="today")
        update_text = st.text_area("What did you work on today?", 
                                 placeholder="Enter your daily update here...")
        
        if st.form_submit_button("Submit Daily Update"):
            if update_text.strip():
                gc = get_gc()
                if gc and log_daily_update(gc, 
                                         st.session_state.current_user_fullname, 
                                         today.strftime("%d-%b-%Y"), 
                                         update_text):
                    st.success("Daily update logged successfully!")
                    st.session_state.last_update_date = today.strftime("%d-%b-%Y")
                    st.rerun()
            else:
                st.warning("Please enter your update before submitting")

# Main App
def main():    
    init_session_state()
    
    if not st.session_state.authenticated:
        login_page()
    
    # Role-based routing
    if st.session_state.get("current_user_role") == "Master":
        master_dashboard_page()
        return
    
    # Regular user flow
    sidebar_content()
    
    if st.session_state.add_task_mode:
        add_task_form()
    elif st.session_state.edit_mode:
        edit_task_form()
    else:
        dashboard_page()

if __name__ == "__main__":
    main()
