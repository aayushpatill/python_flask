from flask import Flask, request, render_template, redirect, url_for, flash, session
from werkzeug.security import generate_password_hash, check_password_hash

import pandas as pd
import json
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your_secret_key'  # Replace with a strong secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///users.db'
db = SQLAlchemy(app)


# Load initial credentials from an Excel file
credential_file = 'credentials.xlsx'
try:
    credentials_df = pd.read_excel(credential_file)
    preset_credentials = dict(zip(credentials_df['Username'], credentials_df['Password']))
except FileNotFoundError:
    # Create an empty DataFrame if the file doesn't exist
    credentials_df = pd.DataFrame(columns=['Username', 'Password'])
    credentials_df.to_excel(credential_file, index=False)
    preset_credentials = {}

excel_file = r'sample_data_game_engine.xlsx'

# Read the Excel file into a DataFrame
df = pd.read_excel(excel_file)

# Specify the columns you want to include
selected_columns = ['Batch Date','Stream', 'Total Files (Annotated)', 'Quality', 'Annotator ID', 'Leave Status', 'No of iterations']

# Create a list of lists to store the selected column values
selected_data = []

# Iterate through the DataFrame rows and store selected column values in each row
for _, row in df.iterrows():
    selected_row = [row[column] for column in selected_columns]
    selected_data.append(selected_row)

# Now, 'selected_data' is a list of lists containing the specified column values
# Each inner list corresponds to a row with values in the specified columns
"""for selected_datas in selected_data:
    print("Batch Date", "      ", selected_datas[0])
    print("Stream","    ", selected_datas[1])
    print("Volume", "    ", selected_datas[2])
    print("Quality", "    ", selected_datas[3])
    print("Annotator ID", "    ", selected_datas[4])
    print("-------------------------")"""

def calculate_transaction_point(data):
    result = []

    for row in data:
        batch_date, stream, total_files, quality, annotator_id, leave_status, no_of_iteration = row
        transaction_point = 0

        if stream == "RM" and leave_status != "Leave" and leave_status != "Holiday":
            if int(total_files) >= 15:
                transaction_point = 10
                point_reason = "Volume Targets Achieved"
            else:
                transaction_point = -5
                point_reason = "Volume Not Targets Achieved"
        elif stream == "SOF" and leave_status != "Leave" and leave_status != "Holiday":
            if int(total_files) >= 25:
                transaction_point = 10
                point_reason = "Volume Targets Achieved"
            else:
                transaction_point = -5
                point_reason = "Volume Targets Not Achieved"
        else:
            # Default case when stream is not recognized
            pass

        result.append([batch_date, stream, total_files, quality, annotator_id, transaction_point, leave_status, point_reason])

    return result

def calculate_transaction_point_quality_volume(data):
    result = []

    for row in data:
        batch_date, stream, total_files, quality, annotator_id, leave_status, no_of_iteration = row
        transaction_point = 0

        if stream == "RM" and leave_status != "Leave" and leave_status != "Holiday":
            if int(no_of_iteration) == 1 and int(total_files) >= 15:
                transaction_point = 2
                point_reason = "Volume or quality is achieved"
            else:
                transaction_point = 0
                point_reason = "Volume or quality is not achieved"
        elif stream == "SOF" and leave_status != "Leave" and leave_status != "Holiday":
            if int(no_of_iteration) == 1 and int(total_files) >= 25:
                transaction_point = 2
                point_reason = "Volume or quality is achieved"
            else:
                transaction_point = 0
                point_reason = "Volume or quality is not achieved"
        else:
            # Default case when stream is not recognized
            pass

        result.append([batch_date, stream, total_files, quality, annotator_id, transaction_point, leave_status, point_reason])

    return result

def calculate_transaction_point_quality(data):
    result = []

    for row in data:
        batch_date, stream, total_files, quality, annotator_id, leave_status, no_of_iteration = row
        transaction_point = 0

        if stream == "RM" and leave_status != "Leave" and leave_status != "Holiday":
            if int(no_of_iteration) == 1:
                transaction_point = 10
                point_reason = "Quality Targets Achieved"
            elif int(no_of_iteration) == 2:
                transaction_point = 0
                point_reason = "Quality Targets Not Achieved - 1 Iteration"
            elif int(no_of_iteration) >= 3:
                transaction_point = -10
                point_reason = "Quality Targets Not Achieved - 2+ Iteration"
        elif stream == "SOF" and leave_status != "Leave" and leave_status != "Holiday":
            if int(no_of_iteration) == 1:
                transaction_point = 10
                point_reason = "Quality Targets Achieved"
            elif int(no_of_iteration) == 2:
                transaction_point = 0
                point_reason = "Quality Targets Not Achieved - 1 Iteration"
            elif int(no_of_iteration) >= 3:
                transaction_point = -10
                point_reason = "Quality Targets Not Achieved - 2+ Iteration"
        else:
            # Default case when stream is not recognized
            pass

        result.append([batch_date, stream, total_files, quality, annotator_id, transaction_point, leave_status, point_reason])

    return result


def calculate_transaction_point_quality_volume_consecutive(data):
    result = []

    # Create dictionaries to track the last recorded date for each annotator for Volume and Quality
    last_recorded_volume_date = {}
    last_recorded_quality_date = {}

    for row in data:
        batch_date, stream, total_files, quality, annotator_id, leave_status, no_of_iteration = row
        transaction_point = 0

        # Convert batch_date to a datetime object
        batch_date = batch_date

        if stream == "RM" and leave_status != "Leave" and leave_status != "Holiday":
            if int(no_of_iteration) == 1:
                if int(total_files) >= 15:
                    transaction_point += 10
        elif stream == "SOF" and leave_status != "Leave" and leave_status != "Holiday":
            if int(no_of_iteration) == 1:
                if int(total_files) >= 25:
                    transaction_point += 10
        else:
            # Default case when stream is not recognized
            pass

        # Check for consecutive Volume points
        if (
            annotator_id in last_recorded_volume_date
            and (batch_date - last_recorded_volume_date[annotator_id]).days == 1
        ):
            transaction_point += 1
        else:
            # Reset consecutive days if it's not a consecutive day
            last_recorded_volume_date[annotator_id] = batch_date

        # Check for consecutive Quality points
        if (
            annotator_id in last_recorded_quality_date
            and (batch_date - last_recorded_quality_date[annotator_id]).days == 1
        ):
            if int(no_of_iteration) == 1:
                transaction_point += 2
        else:
            # Reset consecutive days if it's not a consecutive day
            last_recorded_quality_date[annotator_id] = batch_date

        point_reason = "Consecutive Volume and quality"
        result.append([batch_date, stream, total_files, quality, annotator_id, transaction_point, leave_status, point_reason])

    return result

def summarize_transaction_points(input_excel):
    # Read the input Excel file into a DataFrame
    df = pd.read_excel(input_excel)

    # Group the data by 'Annotator ID' and calculate the sum of 'Transaction Point'
    summary_df = df.groupby('Annotator ID')['Transaction Point'].sum().reset_index()

    # Create a new Excel file with the summary data
    #summary_df.to_excel(output_excel, index=False)
    return summary_df

result = calculate_transaction_point(selected_data)
result1 = calculate_transaction_point_quality(selected_data)
result = result + result1
result3 = calculate_transaction_point_quality_volume(selected_data)
result = result + result3

result2 = calculate_transaction_point_quality_volume(selected_data)
result = result + result2
df = pd.DataFrame(result, columns=['Batch Date', 'Stream', 'Total Files (Annotated)', 'Quality', 'Annotator ID', 'Transaction Point', 'Leave Status', "Point Reason"])

# Save the DataFrame to an Excel file
output_file = r'transaction_points-pre.xlsx'
df.to_excel(output_file, index=False)

@app.route('/', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Check if the entered username exists in the preset credentials
        if username in preset_credentials:
            # Check if the entered password matches the preset password
            if password == preset_credentials[username]:
                flash('Login successful!', 'success')
                session['username'] = username  # Store username in session
                return redirect(url_for('welcome'))
            else:
                flash('Incorrect password. Please try again.', 'danger')
        else:
            flash('User does not exist. Please check your username.', 'danger')

    return render_template('login.html')


@app.route('/welcome', methods=['GET'])
def welcome():
    # Check if the username is stored in the session
    if 'username' in session:
        username = session['username']

        # Load the Excel data into a DataFrame
        excel_file = r'sample_data_game_engine.xlsx'
        df = pd.read_excel(excel_file)

        # Specify the columns you want to include
        selected_columns = ['Batch Date', 'Stream', 'Total Files (Annotated)', 'Quality', 'Annotator ID',
                            'Leave Status', 'No of iterations']

        # Create a list of lists to store the selected column values
        selected_data = []

        # Iterate through the DataFrame rows and store selected column values in each row
        for _, row in df.iterrows():
            selected_row = [row[column] for column in selected_columns]
            selected_data.append(selected_row)

        # Calculate transaction points
        result = calculate_transaction_point(selected_data)
        result1 = calculate_transaction_point_quality(selected_data)
        result = result + result1

        result2 = calculate_transaction_point_quality_volume(selected_data)
        result = result + result2
        result3 = calculate_transaction_point_quality_volume_consecutive(selected_data)
        result = result + result3

        # Create a DataFrame with the calculated transaction points
        df_result = pd.DataFrame(result,
                                 columns=['Batch Date', 'Stream', 'Total Files (Annotated)', 'Quality', 'Annotator ID',
                                          'Transaction Point', 'Leave Status', 'Point Reason'])

        # Save the DataFrame to an Excel file
        output_file = r'transaction_points-pre.xlsx'
        df_result.to_excel(output_file, index=False)

        # Load the summarized transaction points from the Excel file
        transaction_points = summarize_transaction_points(output_file)

        # Get the transaction point for the logged-in user's "Annotator ID"
        user_transaction_point = None

        matching_row = transaction_points[transaction_points['Annotator ID'] == username]

        if not matching_row.empty:
            # Extract the corresponding "Transaction Point" value
            user_transaction_point = matching_row.iloc[0]['Transaction Point']

        # Get the current date and time
        current_datetime = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Filter transaction history for the current user
        transaction_history = df_result[df_result['Annotator ID'] == username]

        return render_template('welcome.html', username=username, user_transaction_point=user_transaction_point,
                               current_datetime=current_datetime, transaction_history=transaction_history)

    else:
        return 'Please log in first.'


@app.route('/change_password', methods=['GET', 'POST'])
def change_password():
    if 'username' not in session:
        flash('Please log in first.', 'danger')
        return redirect(url_for('login'))

    if request.method == 'POST':
        username = session['username']
        old_password = request.form['old_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        # Check if the provided username exists in the preset_credentials dictionary
        if username in preset_credentials:
            if preset_credentials[username] == old_password:
                if new_password == confirm_password:
                    # Update the password in the preset_credentials dictionary
                    preset_credentials[username] = new_password
                    flash('Password changed successfully!', 'success')

                    # Update the Excel file with the new password
                    credentials_df.loc[credentials_df['Username'] == username, 'Password'] = new_password
                    credentials_df.to_excel(credential_file, index=False)

                    return redirect(url_for('password_changed'))
                else:
                    flash('New passwords do not match. Please try again.', 'danger')
            else:
                flash('Incorrect old password. Please try again.', 'danger')
        else:
            flash('User does not exist. Please check your username.', 'danger')

    return render_template('change_password.html')

@app.route('/password_changed', methods=['GET'])
def password_changed():
    return render_template('password_changed.html')

@app.route('/logout', methods=['GET'])
def logout():
    # Clear the username from the session when logging out
    session.pop('username', None)
    flash('You have been logged out.', 'info')
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True)
