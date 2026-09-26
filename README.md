# Shree Dogada Farm V3
Full shopping/order version.

Features: cart, quantity controls, live calculation, checkout, automatic order IDs, SQLite orders, owner order dashboard, status workflow, delivery fees, customer contact/address, WhatsApp link, sales statistics, product price/visibility management, livestock inquiry and responsive mobile UI.

Run:
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run.py

Open http://127.0.0.1:5000
Owner: http://127.0.0.1:5000/owner/login
Username: owner
Password: ChangeMe123!

Change the owner password after first login.

Payment currently supports Cash on Delivery and Pay on confirmation. Live eSewa/Khalti APIs require merchant credentials and production configuration.
