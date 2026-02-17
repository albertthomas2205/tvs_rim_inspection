🛞 TVS RIM Inspection System

A real-time RIM inspection backend system built using Django + ASGI + Daphne + Celery, designed for handling inspection workflows, background processing, and real-time communication.

🚀 Tech Stack

Backend Framework: Django (ASGI enabled)

ASGI Server: Daphne

Task Queue: Celery

Message Broker: Redis

Real-time Communication: Django Channels (WebSocket)

Database: PostgreSQL / SQLite (based on environment)

Python Version: 3.x

📁 Project Structure
RIM_INSPECTION-main/
│
├── rim_inseption/        # Django project folder
│   ├── asgi.py
│   ├── settings.py
│   ├── urls.py
│   └── ...
│
├── manage.py
├── requirements.txt
└── README.md

⚙️ Setup Instructions
1️⃣ Clone the Repository
git clone https://github.com/albertthomas2205/tvs_rim_inspection.git
cd RIM_INSPECTION-main

2️⃣ Create Virtual Environment
python3 -m venv venv
source venv/bin/activate

3️⃣ Install Dependencies
pip install -r requirements.txt

4️⃣ Setup Environment Variables

Create a .env file (if required) and configure:

DEBUG=True
SECRET_KEY=your_secret_key
DATABASE_URL=your_database_url
REDIS_URL=redis://127.0.0.1:6379/0

5️⃣ Run Migrations
python manage.py migrate

▶️ Running the Project
🔹 Start ASGI Server (Daphne)
python3 -m daphne -b 0.0.0.0 -p 8002 rim_inseption.asgi:application

🔹 Start Celery Worker
celery -A rim_inseption worker -l info

🔹 (Optional) Start Redis Server
redis-server

🔄 Real-Time Communication

WebSocket enabled using Django Channels

ASGI powered via Daphne

Used for real-time inspection status updates

Example WebSocket format:

ws://<server-ip>:8002/ws/<endpoint>/

🧠 Features

✅ RIM inspection workflow management

✅ Real-time status updates via WebSocket

✅ Background task execution using Celery

✅ Scalable ASGI architecture

✅ Production-ready deployment structure

🛠 Development Commands
# Create superuser
python manage.py createsuperuser

# Run Django dev server (for debugging only)
python manage.py runserver

# Collect static files
python manage.py collectstatic

📦 Production Deployment Notes

Use Daphne behind Nginx

Use Supervisor / Systemd to manage:

Daphne

Celery worker

Redis

Set DEBUG=False

Configure proper ALLOWED_HOSTS

👨‍💻 Author

Albert Thomas
GitHub: https://github.com/albertthomas2205
