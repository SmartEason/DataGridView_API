# DataGridView_API

A web-based application integrated with a MySQL database and multiple government open data APIs (Ministry of Environment, Central Weather Administration, and MOTC TDX) to display and manage real-time environmental and transportation data grid views.

## Features
* **Dynamic Data Grid:** Interactive data visualization and efficient management interface.
* **API Integration:** Real-time data synchronization with official government open data platforms.
* **Database Driven:** Robust backend structured and powered by MySQL.
* **Responsive UI:** Modern web layouts built with templates and static assets.

## Prerequisites
Before running this project, ensure you have the following installed on your local machine:
* Python 3.8 or higher
* MySQL Server (Localhost or a remote instance)

## Installation & Setup

Follow these steps to get your development environment running:

### 1. Download the Latest Release
1. Navigate to the **[Releases](../../releases)** section on the right side of this repository's homepage.
2. Download the latest release package (e.g., `Source code (zip)`).
3. Extract the downloaded `.zip` file to your preferred directory.
4. Open your terminal (or command prompt) and navigate to the extracted folder:
   ```bash
   cd path/to/your/extracted/folder
2. Set Up the Virtual Environment
Create and activate a virtual environment to isolate project dependencies:

Bash
# Create a virtual environment named 'venv'
python -m venv venv

# Activate the virtual environment (Windows)
venv\Scripts\activate

# Activate the virtual environment (macOS/Linux)
source venv/bin/activate
3. Install Dependencies
Install all the required Python packages listed in requirements.txt:

Bash
pip install -r requirements.txt
4. Database Schema Setup
Open your preferred MySQL client (e.g., MySQL Workbench, phpMyAdmin, or command line).

Create a new database (e.g., env_live_data).

Import the provided API.sql file to automatically initialize the required table structures:

SQL
SOURCE path/to/API.sql;
5. Configure Environment Variables
This project uses environment variables to secure sensitive API credentials and database access.

Duplicate the .env.example file and rename it to .env:

Bash
# You can manually rename it or use the command below:
cp .env.example .env
Open the newly created .env file and replace the placeholders with your actual credentials:

Plaintext
DB_HOST=127.0.0.1
DB_PORT=3306
DB_USER=root
DB_PASSWORD=your_actual_mysql_password
DB_DATABASE=env_live_data

ENV_API_KEY=your_actual_moenv_api_key
CWA_API_KEY=your_actual_cwa_api_key

TDX_CLIENT_ID=your_actual_tdx_client_id
TDX_CLIENT_SECRET=your_actual_tdx_client_secret
Running the Application
Once the configuration is complete, launch the application by running:

Bash
python main.py
After starting the server, open your web browser and navigate to the local address (typically http://127.0.0.1:5000 or the specific port configured in your script).

Customization & Modifications
This project is structured to be easily customizable:

Frontend Customization: Modify the HTML structures within the templates/ folder and update custom styles or assets inside the static/ folder.

Backend Logic & Endpoints: Adjust API fetch behaviors, data intervals, or grid logic directly in main.py.
