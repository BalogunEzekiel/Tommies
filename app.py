import streamlit as st
from urllib.parse import quote_plus
import hashlib
import smtplib
from email.message import EmailMessage
from sqlalchemy import create_engine
from supabase import create_client, Client
import requests # For Flutterwave API calls
import uuid # For unique transaction references

st.set_page_config(page_title="Tommies Fashion", layout="wide")

# --- Database Connection (Currently unused, primarily using Supabase Client) ---
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

# --- Supabase client setup ---
# Cache the Supabase client to avoid recreating it on every rerun
@st.cache_resource
def get_supabase_client():
    supabase_url = st.secrets["supabase"]["url"]
    supabase_key = st.secrets["supabase"]["key"]
    return create_client(supabase_url, supabase_key)

supabase = get_supabase_client()

# --- Helper Functions ---

def send_confirmation_email(email, order_id):
    try:
        msg = EmailMessage()
        msg.set_content(f"Thank you for your order #{order_id} from Tommies Fashion Store!")
        msg["Subject"] = "Order Confirmation"
        # Use a more appropriate 'From' address for automated emails
        # Ensure this email is correctly configured in your SMTP server for sending
        msg["From"] = "no-reply@tommiesfashion.com"
        msg["To"] = email

        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            # Use Streamlit secrets for email credentials
            smtp.login(st.secrets["email"]["username"], st.secrets["email"]["password"])
            smtp.send_message(msg)
    except Exception as e:
        st.warning(f"Email failed to send: {e}")
        # Consider logging the full exception for debugging in production

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_user(email):
    # Using `execute()` and checking `data` is the correct way
    response = supabase.table("users").select("*").eq("email", email).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

def register_user(name, email, password, phone, address):
    hashed = hash_password(password)
    try:
        result = supabase.table("users").insert({
            "full_name": name,
            "email": email,
            "password_hash": hashed,
            "phone": phone,
            "address": address,
            # "created_at" will default to CURRENT_TIMESTAMP if set in your Supabase table
        }).execute()

        # Supabase client returns a response object. Check 'data' for success.
        # status_code should be 201 for a successful insert
        if result.data and result.status_code == 201:
            return result
        else:
            # If insert was attempted but no data returned, or status not 201
            st.error(f"Supabase registration failed or returned unexpected data: {result.data}")
            return None
    except Exception as e:
        # Catch network errors, constraint violations, etc.
        # For a duplicate email, Supabase will typically return a status_code 409
        # but if an exception is raised before that, this catches it.
        st.error(f"Database registration error: {e}")
        return None

def authenticate(email, password):
    hashed = hash_password(password)
    user = get_user(email) # Reuse get_user to fetch user details
    if user and user["password_hash"] == hashed:
        return user
    return None

def fetch_products():
    result = supabase.table("products").select("*").execute()
    return result.data if result.data else []

def create_order(user_id, cart):
    total = sum(item['price'] * item['qty'] for item in cart) # Use 'qty' for consistency
    try:
        order_result = supabase.table("orders").insert({
            "user_id": user_id,
            "total_amount": total,
            "status": "pending" # Initial status
        }).execute()

        if not order_result.data:
            raise Exception("Failed to create order in database.")

        order_id = order_result.data[0]['order_id']

        for item in cart:
            supabase.table("order_items").insert({
                "order_id": order_id,
                "product_id": item['product_id'],
                "quantity": item['qty'], # Use 'qty'
                "price_at_purchase": item['price']
            }).execute()

            # Update product stock (careful with race conditions in real apps)
            supabase.table("products").update({
                "stock_quantity": item['stock_quantity'] - item['qty']
            }).eq("product_id", item['product_id']).execute()

        send_confirmation_email(st.session_state.user['email'], order_id)
        return order_id
    except Exception as e:
        st.error(f"Error creating order: {e}")
        return None

# --- Flutterwave Integration ---
def initiate_payment(amount, email):
    # Retrieve Flutterwave public key from Streamlit secrets
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

    # Generate a unique transaction reference
    tx_ref = f"TOMMIES_TX_{uuid.uuid4().hex}"

    payload = {
        "tx_ref": tx_ref,
        "amount": amount,
        "currency": "NGN",
        # Important: For deployment, replace localhost with your deployed Streamlit app URL
        # You'll need to figure out how to handle the callback to verify payment on Streamlit Cloud
        "redirect_url": "http://localhost:8501", # Redirect back to the app's base URL
        "customer": {
            "email": email,
            "name": st.session_state.user.get('full_name', 'Customer') # Get customer name if available
        },
        "customizations": {
            "title": "Tommies Fashion Store",
            "description": "Payment for fashion items"
        }
    }

    try:
        response = requests.post(payment_url, json=payload, headers=headers)
        response.raise_for_status() # Raise an HTTPError for bad responses (4xx or 5xx)
        response_json = response.json()

        if response_json['status'] == 'success':
            payment_link = response_json['data']['link']
            st.success("Payment initiated successfully! Click the link below to complete your payment.")
            st.markdown(f"**[Proceed to Payment]({payment_link})**")
            # Optionally, save tx_ref to session_state to check later
            st.session_state.current_tx_ref = tx_ref
        else:
            st.error(f"Failed to initiate payment: {response_json.get('message', 'Unknown error')}")
            # print(response_json) # For debugging
    except requests.exceptions.RequestException as e:
        st.error(f"Network or API error initiating payment: {e}")
    except Exception as e:
        st.error(f"An unexpected error occurred during payment initiation: {e}")


# --- Session State Initialization ---
if "cart" not in st.session_state:
    st.session_state.cart = []

if "logged_in" not in st.session_state:
    st.session_state.logged_in = False

if "user" not in st.session_state:
    st.session_state.user = {}

if "viewing_cart" not in st.session_state:
    st.session_state.viewing_cart = False

# --- UI Functions ---

def registration_form():
    st.sidebar.subheader("📝 Register")

    name = st.sidebar.text_input("Full Name", value=st.session_state.get("reg_name", ""), key="reg_name")
    email = st.sidebar.text_input("Email", value=st.session_state.get("reg_email", ""), key="reg_email")
    phone = st.sidebar.text_input("Phone", value=st.session_state.get("reg_phone", ""), key="reg_phone")
    address = st.sidebar.text_area("Address", value=st.session_state.get("reg_address", ""), key="reg_address")
    password = st.sidebar.text_input("Password", type="password", value=st.session_state.get("reg_password", ""), key="reg_password")

    if st.sidebar.button("Register"):
        if not all([name, email, phone, address, password]):
            st.sidebar.warning("Please fill in all fields")
            return

        # Check if user already exists
        if get_user(email):
            st.sidebar.error("Email already registered. Please login.")
            return

        result = register_user(name, email, password, phone, address)

        if result: # register_user returns None on failure, or a result object on success
            st.sidebar.success("✅ Registration successful! Please log in.")
            # Clear the form fields after success
            for key in ["reg_name", "reg_email", "reg_phone", "reg_address", "reg_password"]:
                st.session_state[key] = "" # Clear directly in session state
        else:
            st.sidebar.error("❌ Registration failed. Please try again.")

def login_form():
    st.sidebar.subheader("🔐 Login")

    # Use keys to bind inputs to session state, initialized to empty strings
    email = st.sidebar.text_input("Email", value=st.session_state.get("login_email", ""), key="login_email")
    password = st.sidebar.text_input("Password", type="password", value=st.session_state.get("login_password", ""), key="login_password")

    if st.sidebar.button("Login"):
        if not email or not password:
            st.sidebar.warning("Enter both email and password")
            return

        user = authenticate(email, password)

        if user:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.sidebar.success(f"Welcome, {user['full_name']}!")

            # Clear the input values in session state.
            # Streamlit will then render them empty in the next rerun.
            st.session_state["login_email"] = ""
            st.session_state["login_password"] = ""

            # No explicit rerun needed, Streamlit will rerun naturally due to state change
        else:
            st.sidebar.error("Invalid credentials")

def product_list():
    st.subheader("🛍️ Available Products")
    products = fetch_products()
    if not products:
        st.info("No products available at the moment.")
        return

    categories = sorted(list(set(p['category'] for p in products if p['category'])))
    sizes = sorted(list(set(p['size'] for p in products if p['size'])))
    category_filter = st.selectbox("Category", ["All"] + categories)
    size_filter = st.selectbox("Size", ["All"] + sizes)
    price_range = st.slider("Price Range (₦)", 0, 100000, (0, 100000))

    filtered = [
        p for p in products
        if (category_filter == "All" or p.get('category') == category_filter) and
           (size_filter == "All" or p.get('size') == size_filter) and
           (price_range[0] <= float(p.get('price', 0)) <= price_range[1]) # Safely handle missing price
    ]

    if not filtered:
        st.info("No products match your filters.")
        return

    # Use columns for a better product display
    cols_per_row = 3 # You can adjust this
    cols = st.columns(cols_per_row)
    for i, p in enumerate(filtered):
        with cols[i % cols_per_row]:
            # Add a unique key for each expander if you use them, or just display directly
            st.image(p.get('image_url', 'https://via.placeholder.com/150'), use_column_width=True) # Default image
            st.markdown(f"**{p.get('product_name', 'N/A')}** \n₦{float(p.get('price', 0)):,.2f}")
            st.markdown(f"Stock: {p.get('stock_quantity', 0)} | Size: {p.get('size', 'N/A')} | Category: {p.get('category', 'N/A')}")

            # Only show quantity input and add to cart button if stock > 0
            if p.get('stock_quantity', 0) > 0:
                qty = st.number_input(
                    "Qty", min_value=1, max_value=p['stock_quantity'], key=f"qty_{p['product_id']}", value=1
                )
                if st.button("Add to Cart", key=f"cart_{p['product_id']}"):
                    if not st.session_state.logged_in:
                        st.warning("Please log in or sign up to add items to your cart.")
                    else:
                        existing = next((item for item in st.session_state.cart if item['product_id'] == p['product_id']), None)
                        if existing:
                            # If item exists, update quantity instead of adding new entry
                            existing['qty'] += qty
                            st.success(f"Updated quantity of {p['product_name']} in cart to {existing['qty']}.")
                        else:
                            st.session_state.cart.append({**p, 'qty': qty}) # Use 'qty' here
                            st.success(f"Added {qty} x {p['product_name']} to cart.")
            else:
                st.info("Out of Stock")

def view_cart():
    st.subheader("🛒 Your Cart")
    if not st.session_state.cart:
        st.info("Your cart is empty.")
        if st.button("🔙 Back to Products"):
            st.session_state.viewing_cart = False
            st.experimental_rerun() # Rerun to show product list
        return

    total = 0
    remove_indices = []
    
    # Display cart items and allow removal
    for i, item in enumerate(st.session_state.cart):
        col1, col2, col3 = st.columns([0.6, 0.2, 0.2])
        with col1:
            st.write(f"**{item.get('product_name', 'N/A')}**")
            st.write(f"{item['qty']} x ₦{item['price']:,.2f} each")
        with col2:
            # Allow adjusting quantity directly in cart
            new_qty = st.number_input("Change Qty", min_value=1, max_value=item.get('stock_quantity', item['qty']), value=item['qty'], key=f"cart_qty_{item['product_id']}")
            if new_qty != item['qty']:
                item['qty'] = new_qty
                st.experimental_rerun() # Rerun to update total and display immediately
        with col3:
            if st.button("Remove", key=f"remove_{item['product_id']}"):
                remove_indices.append(i)

        total += item['qty'] * item['price']

    # Process removals
    for i in sorted(remove_indices, reverse=True):
        st.session_state.cart.pop(i)
        st.experimental_rerun() # Rerun to reflect immediate removal

    st.markdown("---") # Separator
    st.markdown(f"**Total: ₦{total:,.2f}**")
    st.markdown("---") # Separator

    # Checkout Options
    if st.session_state.logged_in:
        if st.button("Proceed to Flutterwave Payment"):
            if not st.session_state.cart:
                st.warning("Your cart is empty!")
                return
            initiate_payment(total, st.session_state.user['email'])
        
        # You could also keep a "Place Order" button that bypasses Flutterwave if needed
        # but typically you'd go through the payment gateway.
        # For simplicity, if payment is required, remove this direct "Place Order" button
        # if st.button("🧾 Place Order (Manual Order)"):
        #     if not st.session_state.cart:
        #         st.warning("Your cart is empty!")
        #         return
        #     if st.session_state.user:
        #         order_id = create_order(st.session_state.user['user_id'], st.session_state.cart)
        #         if order_id:
        #             st.success(f"✅ Order #{order_id} placed! Confirmation sent to your email.")
        #             st.session_state.cart = []
        #             st.experimental_rerun()
        #         else:
        #             st.error("Failed to place order. Please try again.")

    else:
        st.warning("Please log in or sign up to proceed with payment.")

    st.markdown("---") # Separator
    if st.button("🔙 Back to Products"):
        st.session_state.viewing_cart = False
        st.experimental_rerun() # Rerun to switch view

def admin_panel():
    st.title("🛠️ Admin Dashboard")
    st.subheader("Recent Orders")

    try:
        # Ensure 'users' table is joined correctly for full_name
        orders_result = supabase.table("orders").select("*, users!inner(full_name, email), order_items(*)").order("created_at", desc=True).execute()
        orders = orders_result.data if orders_result.data else []
    except Exception as e:
        st.error(f"Error fetching orders: {e}")
        orders = []

    if not orders:
        st.info("No orders found.")
        return

    for order in orders:
        st.markdown(f"**Order #{order['order_id']}**")
        st.write(f"**Customer:** {order['users']['full_name']} ({order['users']['email']})")
        st.write(f"**Date:** {order['created_at']}")
        st.write("---")
        st.write("**Items:**")
        
        if order['order_items']:
            for item in order['order_items']:
                # Fetch product name for each item
                prod_result = supabase.table("products").select("product_name").eq("product_id", item['product_id']).execute()
                prod_name = prod_result.data[0]['product_name'] if prod_result.data else "Unknown Product"
                st.write(f"- {item['quantity']} x {prod_name} at ₦{item['price_at_purchase']:,.2f}")
        else:
            st.write("- No items found for this order.")
            
        st.markdown(f"**Total: ₦{order['total_amount']:,.2f} | Status: {order.get('status', 'N/A')}**")
        st.divider() # Horizontal line separator

# --- Main App Logic ---
def main():
    st.title("👗 Tommies Fashion Store")

    # Display user info if logged in (moved from end of file for better placement)
    if st.session_state.logged_in and st.session_state.user:
        st.sidebar.markdown(f"👤 Logged in as: **{st.session_state.user.get('full_name', 'User')}**")
        st.sidebar.markdown("---") # Separator

    if st.session_state.logged_in:
        # Admin Panel
        if st.session_state.user.get('email') == 'admin@tommies.com':
            admin_panel()
            return # Stop here for admin view

        # User options
        if st.sidebar.button("🛒 View Cart"):
            st.session_state.viewing_cart = True

        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.user = {}
            st.session_state.cart = []
            st.session_state.viewing_cart = False
            # No explicit rerun needed, Streamlit will rerun naturally

        if st.session_state.viewing_cart:
            view_cart()
            # "Back to Products" button is now inside view_cart for consistency
        else:
            product_list()
    else:
        # Not logged in
        product_list() # Show products even when not logged in
        st.sidebar.markdown("---")
        login_form()
        st.sidebar.markdown("---")
        registration_form()

if __name__ == "__main__":
    main()
