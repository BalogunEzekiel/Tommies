
import streamlit as st
from PIL import Image
import pandas as pd
from supabase import create_client, Client

# Placeholder for Supabase connection
# from supabase import create_client, Client
# supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Sample products
PRODUCTS = [
    {"name": "Senator Wear", "price": 15000, "image": "images/senator.jpg"},
    {"name": "Ankara Gown", "price": 12000, "image": "images/ankara.jpg"},
    {"name": "Casual Shirt", "price": 8000, "image": "images/shirt.jpg"},
]

# --- Session initialization ---
if "cart" not in st.session_state:
    st.session_state["cart"] = []
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False
if "username" not in st.session_state:
    st.session_state["username"] = ""

# --- Login form ---
def login_form():
    st.sidebar.subheader("🔐 Login to Continue")
    username = st.sidebar.text_input("Username", key="login_user")
    password = st.sidebar.text_input("Password", type="password", key="login_pass")
    if st.sidebar.button("Login"):
        if username == "admin" and password == "admin":  # Replace with real auth
            st.session_state["logged_in"] = True
            st.session_state["username"] = username
            st.success("✅ Successfully logged in!")
        else:
            st.warning("❌ Invalid username or password")

# --- Landing Page ---
def landing_page():
    st.title("👗 Tommies Fashion Store")
    st.markdown("Welcome to the trendiest online fashion hub! Browse our latest styles below.")

# --- Display Products ---
def display_products():
    st.subheader("🛍️ Trending Products")
    cols = st.columns(3)
    for idx, product in enumerate(PRODUCTS):
        with cols[idx]:
            st.image(product["image"], use_column_width=True)
            st.markdown(f"**{product['name']}**")
            st.markdown(f"₦{product['price']:,}")
            if st.button(f"Add to Cart", key=f"add_{idx}"):
                if not st.session_state["logged_in"]:
                    st.warning("⚠️ Please log in to add items to your cart.")
                else:
                    st.session_state["cart"].append(product)
                    st.success(f"✅ {product['name']} added to cart.")

# --- View Cart ---
def view_cart():
    if not st.session_state["logged_in"]:
        st.sidebar.warning("🛒 Login required to view your cart.")
        return
    st.subheader("🛒 Your Shopping Cart")
    if not st.session_state["cart"]:
        st.info("Your cart is empty.")
        return
    total = 0
    for item in st.session_state["cart"]:
        st.write(f"- {item['name']} - ₦{item['price']:,}")
        total += item["price"]
    st.write(f"**Total: ₦{total:,}**")
    if st.button("Checkout"):
        st.success("✅ Order placed successfully! (Simulated)")
        st.session_state["cart"] = []

# --- Main App Logic ---
def main():
    landing_page()
    display_products()
    if st.sidebar.button("🛒 View Cart"):
        view_cart()

    if not st.session_state["logged_in"]:
        login_form()
    else:
        st.sidebar.markdown(f"👋 Logged in as: **{st.session_state['username']}**")
        if st.sidebar.button("Logout"):
            st.session_state["logged_in"] = False
            st.session_state["username"] = ""
            st.session_state["cart"] = []
            st.experimental_rerun()

# Run the app
if __name__ == "__main__":
    main()
