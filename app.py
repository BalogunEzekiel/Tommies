
import streamlit as st
from PIL import Image
import pandas as pd
import supabase_py

# Placeholder for Supabase connection
# from supabase import create_client, Client
# supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# Simulated login
def login():
    st.sidebar.header("Login")
    username = st.sidebar.text_input("Username")
    password = st.sidebar.text_input("Password", type="password")
    if st.sidebar.button("Login"):
        if username == "admin" and password == "admin":
            st.session_state['logged_in'] = True
            st.success("Logged in as Admin")
        else:
            st.warning("Invalid credentials")

# Product catalog
def display_products():
    st.title("🛍️ Tommies Fashion Store")
    st.markdown("### Trending Products")
    products = [
        {"name": "Senator Wear", "price": 15000, "image": "images/senator.jpg"},
        {"name": "Ankara Gown", "price": 12000, "image": "images/ankara.jpg"},
        {"name": "Casual Shirt", "price": 8000, "image": "images/shirt.jpg"}
    ]
    cols = st.columns(3)
    for idx, product in enumerate(products):
        with cols[idx]:
            st.image(product["image"], use_column_width=True)
            st.text(product["name"])
            st.text(f"₦{product['price']:,}")
            if st.button(f"Add to Cart - {product['name']}", key=idx):
                st.session_state["cart"].append(product)

# View shopping cart
def view_cart():
    st.subheader("🛒 Shopping Cart")
    total = 0
    for item in st.session_state["cart"]:
        st.write(f"{item['name']} - ₦{item['price']:,}")
        total += item["price"]
    st.write(f"**Total: ₦{total:,}**")
    if st.button("Checkout"):
        st.success("✅ Order placed successfully! (Simulation)")
        st.session_state["cart"] = []

# Main app flow
if "cart" not in st.session_state:
    st.session_state["cart"] = []
if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

login()
if st.session_state["logged_in"]:
    display_products()
    st.sidebar.button("View Cart", on_click=view_cart)
