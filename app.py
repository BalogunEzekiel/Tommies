import streamlit as st
from urllib.parse import quote_plus
import hashlib
import smtplib
from email.message import EmailMessage
from sqlalchemy import create_engine
from supabase import create_client, Client
import requests  # For Flutterwave API calls
import uuid  # For unique transaction references
import bcrypt

# --- Streamlit Page Setup ---
st.set_page_config(page_title="Tommies Fashion", layout="wide")

# --- Database Connection (SQLAlchemy - currently unused) ---
@st.cache_resource
def get_engine():
    try:
        host = st.secrets["supabase"]["host"]
        port = st.secrets["supabase"]["port"]
        database = st.secrets["supabase"]["database"]
        user = st.secrets["supabase"]["user"]
        password = st.secrets["supabase"]["password"]

        encoded_password = quote_plus(password)
        db_url = (
            f"postgresql+psycopg2://{user}:{encoded_password}@{host}:{port}/{database}?sslmode=require"
        )
        return create_engine(db_url)
    except KeyError as e:
        st.error(f"Missing secret key: {e}")
        st.stop()
    except Exception as e:
        st.error(f"Database connection error: {e}")
        st.stop()

# --- Supabase Client ---
@st.cache_resource
def get_supabase_client():
    supabase_url = st.secrets["supabase"]["url"]
    supabase_key = st.secrets["supabase"]["key"]
    return create_client(supabase_url, supabase_key)

supabase = get_supabase_client()

# --- Initialize Session State ---
default_state = {
    "cart": [],
    "logged_in": False,
    "user": {},
    "viewing_cart": False,
    "show_login": False,
    "show_register": False
}

for key, value in default_state.items():
    if key not in st.session_state:
        st.session_state[key] = value

# --- Page Header with Auth Buttons ---
with st.container():
    col1, col2, col3 = st.columns([5, 1, 1])
    with col1:
        st.title("")
    with col2:
        if st.button("Login"):
            st.session_state.show_login = True
            st.session_state.show_register = False
    with col3:
        if st.button("Register"):
            st.session_state.show_register = True
            st.session_state.show_login = False

# --- Authentication Functions ---
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, hashed):
    if not password or not hashed:
        return False
    if isinstance(hashed, str):
        hashed = hashed.encode()
    return bcrypt.checkpw(password.encode(), hashed)

def get_user(email):
    response = supabase.table("users").select("*").eq("email", email).execute()
    return response.data[0] if response.data else None

def register_user(name, email, password, phone, address):
    hashed = hash_password(password)
    try:
        result = supabase.table("users").insert({
            "full_name": name.strip(),
            "email": email.strip().lower(),
            "password_hash": hashed,
            "phone": phone.strip(),
            "address": address.strip(),
        }).execute()
        return result if result.data else None
    except Exception as e:
        st.error(f"❌ Database registration exception: {e}")
        return None

def authenticate(email, password):
    user = get_user(email)
    return user if user and check_password(password, user["password_hash"]) else None

# --- Login Form ---
def login_form():
    st.subheader("🔐 Login")
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login Now", key="main_login_btn"):
        if not email or not password:
            st.warning("Please enter both email and password.")
            return

        user = authenticate(email.strip().lower(), password.strip())
        if user:
            st.session_state.user = user
            st.session_state.logged_in = True
            st.success("✅ Logged in successfully!")
            st.session_state.show_login = False
            st.rerun()
        else:
            st.error("❌ Invalid credentials.")

# --- Registration Form ---
def registration_form():
    st.subheader("📝 Register")
    name = st.text_input("Full Name", key="reg_name_input")
    email = st.text_input("Email", key="reg_email_input")
    phone = st.text_input("Phone", key="reg_phone_input")
    address = st.text_area("Address", key="reg_address_input")
    password = st.text_input("Password", type="password", key="reg_password_input")

    if st.button("Register", key="main_register_btn"):
        if not all([name, email, phone, address, password]):
            st.warning("Please fill in all fields")
            return

        if get_user(email):
            st.error("Email already registered. Please login.")
            return

        result = register_user(name, email, password, phone, address)
        if result:
            st.success("✅ Registration successful! Please log in.")
            st.session_state.show_register = False
            st.session_state.show_login = True
            for key in ["reg_name_input", "reg_email_input", "reg_phone_input", "reg_address_input", "reg_password_input"]:
                st.session_state.pop(key, None)
            st.rerun()
        else:
            st.error("❌ Registration failed. Please try again.")

# --- Fetch Product List ---
def fetch_products():
    result = supabase.table("products").select("*").execute()
    return result.data if result.data else []

# --- Order Creation ---
def create_order(user_id, cart):
    total = sum(item['price'] * item['qty'] for item in cart)
    try:
        order_result = supabase.table("orders").insert({
            "user_id": user_id,
            "total_amount": total,
            "status": "pending"
        }).execute()

        if not order_result.data:
            raise Exception("Failed to create order in database.")

        order_id = order_result.data[0]['order_id']
        for item in cart:
            supabase.table("order_items").insert({
                "order_id": order_id,
                "product_id": item['product_id'],
                "quantity": item['qty'],
                "price_at_purchase": item['price']
            }).execute()
            supabase.table("products").update({
                "stock_quantity": item['stock_quantity'] - item['qty']
            }).eq("product_id", item['product_id']).execute()

        send_confirmation_email(st.session_state.user['email'], order_id)
        return order_id
    except Exception as e:
        st.error(f"Error creating order: {e}")
        return None

# --- Email Confirmation ---
def send_confirmation_email(email, order_id):
    try:
        msg = EmailMessage()
        msg.set_content(f"Thank you for your order #{order_id} from Tommies Fashion Store!")
        msg["Subject"] = "Order Confirmation"
        msg["From"] = "no-reply@tommiesfashion.com"
        msg["To"] = email

        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(st.secrets["email"]["username"], st.secrets["email"]["password"])
            smtp.send_message(msg)
    except Exception as e:
        st.warning(f"Email failed to send: {e}")

# --- Payment via Flutterwave ---
def initiate_payment(amount, email):
    try:
        flutterwave_public_key = st.secrets["flutterwave"]["public_key"]
    except KeyError:
        st.error("Flutterwave public key not found in secrets.toml")
        return

    payment_url = "https://api.flutterwave.com/v3/payments"
    headers = {
        "Authorization": f"Bearer {flutterwave_public_key}",
        "Content-Type": "application/json"
    }

    tx_ref = f"TOMMIES_TX_{uuid.uuid4().hex}"
    payload = {
        "tx_ref": tx_ref,
        "amount": amount,
        "currency": "NGN",
        "redirect_url": "http://localhost:8501",
        "customer": {
            "email": email,
            "name": st.session_state.user.get('full_name', 'Customer')
        },
        "customizations": {
            "title": "Tommies Fashion Store",
            "description": "Payment for fashion items"
        }
    }

    try:
        response = requests.post(payment_url, json=payload, headers=headers)
        response.raise_for_status()
        response_json = response.json()

        if response_json['status'] == 'success':
            payment_link = response_json['data']['link']
            st.success("Payment initiated successfully! Click below to complete payment.")
            st.markdown(f"**[Proceed to Payment]({payment_link})**")
            st.session_state.current_tx_ref = tx_ref
        else:
            st.error(f"Failed to initiate payment: {response_json.get('message', 'Unknown error')}")
    except requests.exceptions.RequestException as e:
        st.error(f"Network/API error: {e}")
    except Exception as e:
        st.error(f"Unexpected error during payment initiation: {e}")

# --- Main UI Logic ---
if st.session_state.show_login:
    login_form()
elif st.session_state.show_register:
    registration_form()
else:
    if st.button("View Cart"):
        st.session_state.viewing_cart = True

# Optional: Add your `main()` logic here if you want to expand further
