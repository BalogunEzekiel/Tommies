# Tommies Fashion Store - Streamlit App with Full Integration

import streamlit as st
import pandas as pd
from PIL import Image
from supabase import create_client, Client
import hashlib
from datetime import datetime
from urllib.parse import quote_plus
import smtplib
from email.message import EmailMessage
from sqlalchemy import create_engine

# --- Database Connection ---
@st.cache_resource
def get_engine():
    try:
        host = st.secrets["supabase"]["host"]
        port = st.secrets["supabase"]["port"]
        database = st.secrets["supabase"]["database"]
        user = st.secrets["supabase"]["user"]
        password = st.secrets["supabase"]["password"]

        encoded_password = quote_plus(password)
        DATABASE_URL = (
            f"postgresql+psycopg2://{user}:{encoded_password}@{host}:{port}/{database}?sslmode=require"
        )

        return create_engine(DATABASE_URL)

    except KeyError as e:
        st.error(f"Missing secret key: {e}")
        st.stop()
    except Exception as e:
        st.error(f"Database connection error: {e}")
        st.stop()

engine = get_engine()
# --- Email Confirmation Function ---
def send_confirmation_email(email, order_id):
    try:
        msg = EmailMessage()
        msg.set_content(f"Thank you for your order #{order_id} from Tommies Fashion Store!")
        msg["Subject"] = "Order Confirmation"
        msg["From"] = "no-reply@tommiesfashion.com"
        msg["To"] = email

        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login("your-email@gmail.com", "your-email-password")
            smtp.send_message(msg)
    except Exception as e:
        st.warning("Email failed to send.")

# --- Helpers ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_user(email):
    return supabase.table("users").select("*").eq("email", email).execute()

def register_user(name, email, password, phone, address):
    hashed = hash_password(password)
    return supabase.table("users").insert({
        "full_name": name,
        "email": email,
        "password_hash": hashed,
        "phone": phone,
        "address": address
    }).execute()

def authenticate(email, password):
    hashed = hash_password(password)
    result = get_user(email)
    if result.data and result.data[0]['password_hash'] == hashed:
        return result.data[0]
    return None

def fetch_products():
    return supabase.table("products").select("*").execute().data

def create_order(user_id, cart):
    total = sum(item['price'] * item['qty'] for item in cart)
    order_result = supabase.table("orders").insert({
        "user_id": user_id,
        "total_amount": total
    }).execute()
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

# --- Session Init ---
for key in ["cart", "logged_in", "user", "viewing_cart"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key == "cart" else False if key != "user" else {}

# --- UI Functions ---
def registration_form():
    st.sidebar.subheader("📝 Register")
    name = st.sidebar.text_input("Full Name")
    email = st.sidebar.text_input("Email")
    phone = st.sidebar.text_input("Phone")
    address = st.sidebar.text_area("Address")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Register"):
        result = register_user(name, email, password, phone, address)
        if result.status_code == 201:
            st.success("✅ Registration successful! Please log in.")
        else:
            st.error("❌ Registration failed. Email might already be used.")

def login_form():
    st.sidebar.subheader("🔐 Login")
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        user = authenticate(email, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.success(f"✅ Welcome {user['full_name']}")
        else:
            st.error("❌ Invalid credentials")

def product_list():
    st.subheader("🛍️ Available Products")
    products = fetch_products()

    # --- Filters ---
    categories = list(set(p['category'] for p in products))
    sizes = list(set(p['size'] for p in products))
    category_filter = st.selectbox("Category", ["All"] + categories)
    size_filter = st.selectbox("Size", ["All"] + sizes)
    price_range = st.slider("Price Range (₦)", 0, 100000, (0, 100000))

    filtered = [p for p in products if
                (category_filter == "All" or p['category'] == category_filter) and
                (size_filter == "All" or p['size'] == size_filter) and
                (price_range[0] <= float(p['price']) <= price_range[1])]

    for p in filtered:
        st.image(p['image_url'], use_container_width=True)
        st.markdown(f"**{p['product_name']}**\n₦{float(p['price']):,.2f}")
        qty = st.number_input("Qty", 1, p['stock_quantity'], key=f"qty_{p['product_id']}")
        if st.button("Add to Cart", key=f"cart_{p['product_id']}"):
            st.session_state.cart.append({**p, 'qty': qty})
            st.success(f"✅ Added {qty} x {p['product_name']}")

def view_cart():
    st.subheader("🛒 Your Cart")
    if not st.session_state.cart:
        st.info("Your cart is empty.")
        return
    total = 0
    for item in st.session_state.cart:
        st.write(f"{item['qty']} x {item['product_name']} - ₦{item['price']:,} each")
        total += item['qty'] * item['price']
    st.markdown(f"**Total: ₦{total:,.2f}**")
    if st.button("🧾 Place Order"):
        order_id = create_order(st.session_state.user['user_id'], st.session_state.cart)
        st.success(f"✅ Order #{order_id} placed! Confirmation sent to your email.")
        st.session_state.cart = []

# --- Admin Panel ---
def admin_panel():
    st.title("🛠️ Admin Dashboard")
    orders = supabase.table("orders").select("*, users(*), order_items(*)").order("created_at", desc=True).execute().data
    for order in orders:
        st.markdown(f"**Order #{order['order_id']}** by {order['users']['full_name']} on {order['created_at']}")
        for item in order['order_items']:
            prod = supabase.table("products").select("product_name").eq("product_id", item['product_id']).execute().data[0]
            st.write(f"- {item['quantity']} x {prod['product_name']} at ₦{item['price_at_purchase']} each")
        st.markdown(f"**Total: ₦{order['total_amount']} | Status: {order['status']}**")
        st.divider()

# --- Main App ---
def main():
    st.set_page_config(page_title="Tommies Fashion", layout="wide")
    st.title("👗 Tommies Fashion Store")

    if st.session_state.logged_in:
        if st.session_state.user['email'] == 'admin@tommies.com':
            admin_panel()
            return

        if st.sidebar.button("🛒 View Cart"):
            st.session_state.viewing_cart = True

        if st.sidebar.button("Logout"):
            for key in ["logged_in", "user", "cart", "viewing_cart"]:
                st.session_state[key] = False if key != "cart" else []
            st.experimental_rerun()

        if st.session_state.viewing_cart:
            view_cart()
            if st.button("🔙 Back to Products"):
                st.session_state.viewing_cart = False
                st.experimental_rerun()
        else:
            product_list()
    else:
        login_form()
        st.sidebar.markdown("---")
        registration_form()

if __name__ == "__main__":
    main()
# Tommies Fashion Store - Streamlit App (Full Integration)

import streamlit as st
import pandas as pd
from PIL import Image
from supabase import create_client, Client
import hashlib
from datetime import datetime

# --- Supabase Config ---
# --- Database Connection ---
@st.cache_resource
def get_engine():
    try:
        host = st.secrets["supabase"]["host"]
        port = st.secrets["supabase"]["port"]
        database = st.secrets["supabase"]["database"]
        user = st.secrets["supabase"]["user"]
        password = st.secrets["supabase"]["password"]

        encoded_password = quote_plus(password)
        DATABASE_URL = (
            f"postgresql+psycopg2://{user}:{encoded_password}@{host}:{port}/{database}?sslmode=require"
        )

        return create_engine(DATABASE_URL)

    except KeyError as e:
        st.error(f"Missing secret key: {e}")
        st.stop()
    except Exception as e:
        st.error(f"Database connection error: {e}")
        st.stop()

engine = get_engine()

# --- Helpers ---
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_user(email):
    return supabase.table("users").select("*").eq("email", email).execute()

def register_user(name, email, password, phone, address):
    hashed = hash_password(password)
    return supabase.table("users").insert({
        "full_name": name,
        "email": email,
        "password_hash": hashed,
        "phone": phone,
        "address": address
    }).execute()

def authenticate(email, password):
    hashed = hash_password(password)
    result = get_user(email)
    if result.data and result.data[0]['password_hash'] == hashed:
        return result.data[0]
    return None

def fetch_products():
    return supabase.table("products").select("*").execute().data

def create_order(user_id, cart):
    total = sum(item['price'] * item['qty'] for item in cart)
    order_result = supabase.table("orders").insert({
        "user_id": user_id,
        "total_amount": total
    }).execute()
    order_id = order_result.data[0]['order_id']
    for item in cart:
        supabase.table("order_items").insert({
            "order_id": order_id,
            "product_id": item['product_id'],
            "quantity": item['qty'],
            "price_at_purchase": item['price']
        }).execute()
    return order_id

# --- Session Init ---
for key in ["cart", "logged_in", "user", "viewing_cart"]:
    if key not in st.session_state:
        st.session_state[key] = [] if key == "cart" else False if key != "user" else {}

# --- UI Functions ---
def registration_form():
    st.sidebar.subheader("📝 Register")
    name = st.sidebar.text_input("Full Name")
    email = st.sidebar.text_input("Email")
    phone = st.sidebar.text_input("Phone")
    address = st.sidebar.text_area("Address")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Register"):
        result = register_user(name, email, password, phone, address)
        if result.status_code == 201:
            st.success("✅ Registration successful! Please log in.")
        else:
            st.error("❌ Registration failed. Email might already be used.")

def login_form():
    st.sidebar.subheader("🔐 Login")
    email = st.sidebar.text_input("Email")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        user = authenticate(email, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.success(f"✅ Welcome {user['full_name']}")
        else:
            st.error("❌ Invalid credentials")

def product_list():
    st.subheader("🛍️ Available Products")
    products = fetch_products()
    cols = st.columns(3)
    for idx, p in enumerate(products):
        with cols[idx % 3]:
            st.image(p['image_url'], use_container_width=True)
            st.markdown(f"**{p['product_name']}**\n₦{float(p['price']):,.2f}")
            qty = st.number_input("Qty", 1, p['stock_quantity'], key=f"qty_{p['product_id']}")
            if st.button("Add to Cart", key=f"cart_{p['product_id']}"):
                st.session_state.cart.append({**p, 'qty': qty})
                st.success(f"✅ Added {qty} x {p['product_name']}")

def view_cart():
    st.subheader("🛒 Your Cart")
    if not st.session_state.cart:
        st.info("Your cart is empty.")
        return
    total = 0
    for item in st.session_state.cart:
        st.write(f"{item['qty']} x {item['product_name']} - ₦{item['price']:,} each")
        total += item['qty'] * item['price']
    st.markdown(f"**Total: ₦{total:,.2f}**")
    if st.button("🧾 Place Order"):
        order_id = create_order(st.session_state.user['user_id'], st.session_state.cart)
        st.success(f"✅ Order #{order_id} placed!")
        st.session_state.cart = []

# --- Admin Panel ---
def admin_panel():
    st.title("🛠️ Admin Dashboard")
    orders = supabase.table("orders").select("*, users(*), order_items(*)").order("created_at", desc=True).execute().data
    for order in orders:
        st.markdown(f"**Order #{order['order_id']}** by {order['users']['full_name']} on {order['created_at']}")
        for item in order['order_items']:
            prod = supabase.table("products").select("product_name").eq("product_id", item['product_id']).execute().data[0]
            st.write(f"- {item['quantity']} x {prod['product_name']} at ₦{item['price_at_purchase']} each")
        st.markdown(f"**Total: ₦{order['total_amount']} | Status: {order['status']}**")
        st.divider()

# --- Main App ---
def main():
    st.title("👗 Tommies Fashion")

    if st.session_state.logged_in:
        if st.session_state.user['email'] == 'admin@tommies.com':
            admin_panel()
            return

        if st.sidebar.button("🛒 View Cart"):
            st.session_state.viewing_cart = True

        if st.sidebar.button("Logout"):
            for key in ["logged_in", "user", "cart", "viewing_cart"]:
                st.session_state[key] = False if key != "cart" else []
            st.experimental_rerun()

        if st.session_state.viewing_cart:
            view_cart()
            if st.button("🔙 Back to Products"):
                st.session_state.viewing_cart = False
                st.experimental_rerun()
        else:
            product_list()

    else:
        login_form()
        st.sidebar.markdown("---")
        registration_form()

if __name__ == "__main__":
    main()
