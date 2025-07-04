import streamlit as st
from urllib.parse import quote_plus
import hashlib
import smtplib
from email.message import EmailMessage
from sqlalchemy import create_engine
from supabase import create_client, Client
import requests # For Flutterwave API calls
import uuid # For unique transaction references
import bcrypt
import pandas as pd
import numpy as np
from datetime import datetime
import time
from streamlit_image_gallery import streamlit_image_gallery
import plotly.express as px

st.set_page_config(page_title="Perfectfit Fashion", layout="wide")

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

if "supabase" not in st.session_state:
    st.session_state.supabase = supabase

# --- HEADER: Login and Signup buttons ---

# --- Initialize session state variables ---
if "show_login" not in st.session_state:
    st.session_state.show_login = False
if "show_register" not in st.session_state:
    st.session_state.show_register = False

# --- Header with Login and Register buttons ---
with st.container():
    col1, col2, col3 = st.columns([5, 1, 1])
    with col1:
        st.title("")
    with col2:
        if st.button("Login"):
            st.session_state.show_login = True
            st.session_state.show_register = False  # Hide register form
    with col3:
        if st.button("Register"):
            st.session_state.show_register = True
            st.session_state.show_login = False  # Hide login form

# --- Login Form Function ---
def hash_password(password):
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()

def check_password(password, hashed):
    if not password or not hashed:
        return False
    if isinstance(hashed, str):
        hashed = hashed.encode()
    return bcrypt.checkpw(password.encode(), hashed)

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

        if result.data:
            return result
        else:
            st.error("❌ Registration failed: No data returned from Supabase.")
            return None
    except Exception as e:
        st.error(f"❌ Database registration exception: {e}")
        return None

def authenticate(email, password):
    user = get_user(email)
    if user and check_password(password, user["password_hash"]):
        return user
    return None

def get_user(email):
    response = supabase.table("users").select("*").eq("email", email).execute()
    if response.data and len(response.data) > 0:
        return response.data[0]
    return None

def login_form():
    st.subheader("🔐 Login")
    email = st.text_input("Email", key="login_email")
    password = st.text_input("Password", type="password", key="login_password")

    if st.button("Login Now", key="main_login_btn"):
        if not email or not password:
            st.warning("Please enter both email and password.")
            return

        email = email.strip().lower()
        password = password.strip()

        user = authenticate(email, password)

        if user:
            st.session_state.user = user
            st.session_state.logged_in = True
            st.success("✅ Logged in successfully!")
            st.session_state.show_login = False
            time.sleep(1)  # Wait 2 seconds before rerun
            st.rerun()
        else:
            st.error("❌ Invalid credentials.")

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
                if key in st.session_state:
                    del st.session_state[key]

            st.rerun()
        else:
            st.error("❌ Registration failed. Please try again.")
            
def create_order(user_id, cart):
    total = sum(item['price'] * item['qty'] for item in cart)
    try:
        order_result = supabase.table("orders").insert({
            "user_id": user_id,
            "total_amount": total,
            "status": "Pending"
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

# --- APP FOOTER CONTENT ---
def app_footer():
    if not st.session_state.get('logged_in'):
        st.markdown("---")
        st.markdown("### 🤝 Supporters", unsafe_allow_html=True)
    
        logos = [
            "assets/BosunTijani1.jpg",
            "assets/Partner_3MTT.png",
            "assets/Partner_NITDA.jpg",
            "assets/Partner_DSN.png",
            "assets/Partner_DeepTech_Ready.png",
            "assets/Partner_Incubator.png",
            "assets/Partner_DSA.jpg",
            "assets/Partner_Google3.png",
            "assets/Partner_Microsoft2.png"
        ]
    
        # Display logos in rows of 4
        for i in range(0, len(logos), 4):
            cols = st.columns(4)
            for j, logo in enumerate(logos[i:i+4]):
                with cols[j]:
                    try:
                        st.image(logo, width=150)  # Adjust width as needed
                    except Exception as e:
                        st.warning(f"Could not load logo: {e}")

#if __name__ == "__main__":
#    main()
#   sidebar_content() # Ensure sidebar content is also called

# --- Email Confirmation ---
def send_confirmation_email(email, order_id):
    try:
        msg = EmailMessage()
        msg.set_content(f"Thank you for your order #{order_id} from Perfectfit Fashion Store!")
        msg["Subject"] = "Order Confirmation"
        msg["From"] = "ezekiel4true@gmail.com"
        msg["To"] = email

        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login(st.secrets["email"]["username"], st.secrets["email"]["password"])
            smtp.send_message(msg)
    except Exception as e:
        st.warning(f"Email failed to send: {e}")
        
# --- Flutterwave Integration ---
def initiate_payment(amount, email, cart, user_id): # Add cart and user_id as arguments
    # Retrieve Flutterwave public key from Streamlit secrets
    try:
        flutterwave_public_key = st.secrets["flutterwave"]["public_key"]
    except KeyError:
        st.error("Flutterwave public key not found in secrets.toml")
        return

    # Create the order in your database first
    order_id = create_order(user_id, cart)
    if not order_id:
        st.error("Failed to create order. Please try again.")
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
        "redirect_url": f"http://localhost:8501?tx_ref={tx_ref}&order_id={order_id}", # Pass order_id and tx_ref
        "customer": {
            "email": email,
            "name": st.session_state.user.get('full_name', 'Customer')
        },
        "customizations": {
            "title": "Perfectfit Fashion Store",
            "description": f"Payment for Order #{order_id}"
        }
    }

    try:
        response = requests.post(payment_url, json=payload, headers=headers)
        response.raise_for_status()
        response_json = response.json()

        if response_json['status'] == 'success':
            payment_link = response_json['data']['link']
            st.success("Payment initiated successfully! Click the link below to complete your payment.")
            st.markdown(f"**[Proceed to Payment]({payment_link})**")
            st.session_state.current_tx_ref = tx_ref
            st.session_state.current_order_id = order_id # Store the order ID for later verification
        else:
            st.error(f"Failed to initiate payment: {response_json.get('message', 'Unknown error')}")
            # If payment initiation fails, you might want to revert the order status or delete it
            supabase.table("orders").delete().eq("order_id", order_id).execute()
            st.error("Order creation rolled back due to payment initiation failure.")

    except requests.exceptions.RequestException as e:
        st.error(f"Network or API error initiating payment: {e}")
        supabase.table("orders").delete().eq("order_id", order_id).execute()
        st.error("Order creation rolled back due to network/API error.")
    except Exception as e:
        st.error(f"An unexpected error occurred during payment initiation: {e}")
        supabase.table("orders").delete().eq("order_id", order_id).execute()
        st.error("Order creation rolled back due to an unexpected error.")

# --- Initialize session state variables ---
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

# --- Example UI Logic ---

if st.session_state.show_login:
    login_form()  # Call your login form function here
elif st.session_state.show_register:
    registration_form()  # Call your registration form function here
else:
    # ✅ Show "View Cart" only to non-admin logged-in users
    if (
        st.session_state.get("logged_in") and
        "user" in st.session_state and
        st.session_state.user.get("email") != "tommiesfashion@gmail.com"
    ):
        if st.button("View Cart"):
            st.session_state.viewing_cart = True
            
#------------------------ Main Page --------------------------
st.title("👗 Perfectfit Fashion Store")

def fetch_products():
    """
    Fetches product data from the Supabase 'products' table.
    Handles potential errors during the fetch operation.
    """
    try:
        if 'supabase' not in st.session_state:
            st.error("Supabase client not initialized. Please set `st.session_state.supabase`.")
            return []

        response = st.session_state.supabase.table("products").select(
            "product_id, product_name, category, size, price, stock_quantity, description, image_url, image_gallery"
        ).execute()

        if hasattr(response, "status_code") and not (200 <= response.status_code < 300):
            st.error(f"Error fetching products: Status code {response.status_code}")
            return []

        return response.data if response.data else []

    except Exception as e:
        st.error(f"Failed to fetch products: {str(e)}")
        return []

def streamlit_image_gallery(images):
    """
    Displays a simple image gallery in Streamlit.
    """
    if not images:
        st.write("No images available for this product.")
        return

    num_images = len(images)
    cols = st.columns(min(num_images, 4))

    for i, image_url in enumerate(images):
        if i < len(cols):
            with cols[i]:
                st.image(image_url, use_container_width=True)
        else:
            st.image(image_url, use_container_width=True)

def get_product_by_id(product_id):
    try:
        product = (
            st.session_state.supabase
            .table("products")
            .select("*")
            .eq("product_id", product_id)
            .execute()
            .data
        )
        return product[0] if product else None
    except Exception as e:
        st.error(f"Error fetching product: {e}")
        return None

def product_list():
    # Handle query param to show a single product detail view
    query_params = st.query_params
    if "product_id" in query_params:
        product_id = query_params["product_id"][0]
        product = get_product_by_id(product_id)

        if product:
            st.subheader(f"🛍️ {product['product_name']}")
            st.image(product.get("image_url", ""), width=400)
            st.write(f"**Price:** ₦{product.get('price', 'N/A')}")
            st.write(product.get("description", "No description available."))
            if st.button("🔙 Back to Products"):
                st.query_params.clear()
                st.rerun()
        else:
            st.error("❌ Product not found.")
        return  # Stop further processing

    # --- List All Products ---
    st.subheader("🛍️ Available Products")

    # Initialize session state
    if 'cart' not in st.session_state:
        st.session_state.cart = []
    if 'liked_products' not in st.session_state:
        st.session_state.liked_products = set()
    if 'trigger_rerun' not in st.session_state:
        st.session_state.trigger_rerun = False
    if 'expander_states' not in st.session_state:
        st.session_state.expander_states = {}

    if 'supabase' not in st.session_state:
        st.error("Supabase client not initialized.")
        return

    if st.session_state.trigger_rerun:
        st.session_state.trigger_rerun = False
        st.rerun()

    products = fetch_products()
    if not products:
        st.info("No products available.")
        return

    # Filters
    categories = sorted([p['category'] for p in products if p.get('category')])
    sizes = sorted([p['size'] for p in products if p.get('size')])
    category_filter = st.selectbox("Category", ["All"] + categories, key="category_filter_sb")
    size_filter = st.selectbox("Size", ["All"] + sizes, key="size_filter_sb")
    price_range = st.slider("Price Range (₦)", 0, 100000, (0, 100000), key="price_range_slider")

    # Apply filters
    filtered = [
        p for p in products
        if (category_filter == "All" or p.get('category') == category_filter) and
           (size_filter == "All" or p.get('size') == size_filter) and
           (price_range[0] <= float(p.get('price', 0)) <= price_range[1])
    ]

    if not filtered:
        st.info("No products match your filters.")
        return

    cols_per_row = 3

    def toggle_wishlist(product_id, product_name, liked):
        if liked:
            st.session_state.liked_products.discard(product_id)
            st.toast(f"Removed {product_name} from wishlist!", icon="💔")
        else:
            st.session_state.liked_products.add(product_id)
            st.toast(f"Added {product_name} to wishlist!", icon="❤️")
        st.rerun()

    for i, p in enumerate(filtered):
        if i % cols_per_row == 0:
            cols = st.columns(cols_per_row)

        with cols[i % cols_per_row]:
            product_id = p.get('product_id')
            if not product_id:
                continue

            liked = product_id in st.session_state.liked_products
            heart_label = "❤️" if liked else "🤍"
            product_name = p.get('product_name', 'Product')
            share_url = f"https://perfectfit.streamlit.app/?product_id={product_id}"

            with st.container(border=True):
                st.image(p.get('image_url', 'https://via.placeholder.com/150'), use_container_width=True)
                st.markdown(f"**{product_name}**")
                st.markdown(f"₦{float(p.get('price', 0)):,.2f}")

                with st.expander("🔗Share"):
                    st.markdown(
                        f"""
                        <a href="https://api.whatsapp.com/send?text=Check out this product: {product_name} - {share_url}" target="_blank" rel="noopener noreferrer" style="margin-right: 10px;">
                            📲 WhatsApp
                        </a>
                        <a href="https://www.facebook.com/sharer/sharer.php?u={share_url}" target="_blank" rel="noopener noreferrer" style="margin-right: 10px;">
                            📘 Facebook
                        </a>
                        <a href="https://twitter.com/intent/tweet?text=Check out this product: {product_name}&url={share_url}" target="_blank" rel="noopener noreferrer" style="margin-right: 10px;">
                            🐦 Twitter
                        </a>
                        <a href="https://www.linkedin.com/sharing/share-offsite/?url={share_url}" target="_blank" rel="noopener noreferrer" style="margin-right: 10px;">
                            💼 LinkedIn
                        </a>
                        <a href="https://t.me/share/url?url={share_url}&text=Check out this product: {product_name}" target="_blank" rel="noopener noreferrer">
                            ✈️ Telegram
                        </a>
                        """,
                        unsafe_allow_html=True
                    )

                if st.button(heart_label, key=f"like_{product_id}"):
                    toggle_wishlist(product_id, product_name, liked)

                is_expanded = st.session_state.expander_states.get(product_id, False)
                with st.expander(f"🛍️ {product_name}", expanded=is_expanded):
                    images = p.get('image_gallery', [])
                    if images:
                        streamlit_image_gallery(images)
                    else:
                        st.image(p.get('image_url', 'https://via.placeholder.com/600'), use_container_width=True)

                    st.markdown(f"### {product_name}")
                    st.markdown(f"**Price:** ₦{float(p.get('price', 0)):,.2f}")
                    st.markdown(f"**Category:** {p.get('category', 'N/A')}")
                    st.markdown(f"**Size:** {p.get('size', 'N/A')}")
                    st.markdown(f"**Stock:** {int(p.get('stock_quantity', 0))}")
                    st.markdown("##### Description:")
                    st.write(p.get('description', 'No description provided.'))

                    stock = int(p.get('stock_quantity', 0))
                    if stock > 0:
                        qty_key = f"qty_modal_{product_id}"
                        if qty_key not in st.session_state:
                            st.session_state[qty_key] = 1
                        st.number_input("Quantity", min_value=1, max_value=stock, key=qty_key)

                        if st.button("🛒 Add to Cart", key=f"modal_cart_{product_id}", use_container_width=True):
                            if not st.session_state.get('logged_in', False):
                                st.warning("Please log in to add items to your cart.")
                            else:
                                qty = st.session_state[qty_key]
                                existing = next(
                                    (item for item in st.session_state.cart if item['product_id'] == product_id),
                                    None
                                )
                                if existing:
                                    new_qty = min(existing['qty'] + qty, stock)
                                    if new_qty == existing['qty']:
                                        st.warning(f"Cannot add more {p['product_name']}; stock limit reached.")
                                    else:
                                        existing['qty'] = new_qty
                                        st.success(f"Updated {p['product_name']} to {existing['qty']} in cart.")
                                else:
                                    st.session_state.cart.append({**p, 'qty': qty})
                                    st.success(f"Added {qty} x {p['product_name']} to cart.")
                                st.session_state.trigger_rerun = True
                                st.rerun()
                    else:
                        st.info("Out of Stock")

def view_cart():
    st.subheader("🛒 Your Cart")
    if not st.session_state.cart:
        st.info("Your cart is empty.")
        if st.button("🔙 Back to Products"):
            st.session_state.viewing_cart = False
            st.rerun()
        return

    total = 0
    remove_indices = []

    for i, item in enumerate(st.session_state.cart):
        try:
            col1, col2, col3 = st.columns([0.6, 0.2, 0.2])
            with col1:
                st.write(f"**{item.get('product_name', 'N/A')}**")
                st.write(f"{item['qty']} x ₦{float(item.get('price', 0)):,.2f} each")
            with col2:
                new_qty = st.number_input(
                    f"Qty for {item['product_name']}",
                    min_value=1,
                    max_value=int(item.get('stock_quantity', item['qty'])),
                    value=item['qty'],
                    key=f"cart_qty_{item['product_id']}"
                )
                if new_qty != item['qty']:
                    item['qty'] = new_qty
                    st.session_state.trigger_rerun = True
                    st.rerun()
            with col3:
                if st.button("Remove", key=f"remove_{item['product_id']}"):
                    remove_indices.append(i)

            total += item.get('qty', 1) * float(item.get('price', 0))
        except Exception as e:
            st.error(f"Error displaying cart item: {str(e)}")

    for i in sorted(remove_indices, reverse=True):
        st.session_state.cart.pop(i)
        st.session_state.trigger_rerun = True
        st.rerun()

    st.markdown("---")
    st.markdown(f"### 🧾 Total: ₦{total:,.2f}")
    st.markdown("---")

    if st.session_state.get('logged_in', False):
        if total > 0:
            if st.button("Proceed to Flutterwave Payment"):
                try:
                    initiate_payment(total, st.session_state.user['email'], st.session_state.cart, st.session_state.user['user_id'])
                except Exception as e:
                    st.error(f"Payment initiation failed: {str(e)}")
        else:
            st.warning("Cannot proceed with an empty cart.")
    else:
        st.warning("Please log in or sign up to proceed with payment.")

    if st.button("🔙 Back to Products"):
        st.session_state.viewing_cart = False
        st.session_state.trigger_rerun = True
        st.rerun()
                
def admin_panel():
    st.subheader("🛠️ Admin Dashboard")

    tabs = st.tabs(["Manage Users", "Manage Products", "View Orders", "History", "Analytics"])

    # --- Manage Users Tab ---
    with tabs[0]:
        st.subheader("👥 Customers Info Management")
        try:
            users = supabase.table("users").select("*").execute().data
            if users:
                df_users = pd.DataFrame(users)
                edited_df = st.data_editor(df_users, num_rows="dynamic", key="user_editor")
                if st.button("Save Changes to Users"):
                    for _, row in edited_df.iterrows():
                        supabase.table("users").update(row.to_dict()).eq("user_id", row["user_id"]).execute()
                    st.success("✅ Users updated successfully!")
            else:
                st.info("No users found.")
        except Exception as e:
            st.error(f"Failed to fetch users: {e}")

    # --- Manage Products Tab ---
    with tabs[1]:
        st.subheader("🛍️ Manage Products")
        try:
            products = supabase.table("products").select("*").execute().data
            if products:
                df_products = pd.DataFrame(products)
                edited_products = st.data_editor(df_products, num_rows="dynamic", key="product_editor")
                if st.button("Save Changes to Products"):
                    for _, row in edited_products.iterrows():
                        supabase.table("products").update(row.to_dict()).eq("product_id", row["product_id"]).execute()
                    st.success("✅ Products updated successfully!")
            else:
                st.info("No products available.")
        except Exception as e:
            st.error(f"Failed to fetch products: {e}")

    # --- View Orders Tab ---
    with tabs[2]:
        st.subheader("📦 Recent Orders")
        try:
            orders = supabase.table("orders").select(
                "*, users!inner(full_name, email), order_items(*)"
            ).order("created_at", desc=True).execute().data

            if not orders:
                st.info("No orders found.")
            else:
                active_orders = [order for order in orders if order.get("status", "").lower() != "delivered"]
                #active_orders = [order for order in orders if order.get("status") != "Delivered"]

                for order in active_orders:
                    with st.expander(f"🧾 Order #{order['order_id']} | ₦{order['total_amount']:,.2f} | {order.get('status', 'N/A')}"):
                        st.markdown(f"**👤 Customer:** {order['users']['full_name']} ({order['users']['email']})")
                        st.markdown(f"**🕒 Date:** {order['created_at']}")
                        st.markdown("**🧺 Items Ordered:**")

                        if order['order_items']:
                            for item in order['order_items']:
                                try:
                                    prod = supabase.table("products").select("product_name").eq("product_id", item["product_id"]).execute().data
                                    prod_name = prod[0]["product_name"] if prod else "Unknown"
                                except:
                                    prod_name = "Unknown"
                                st.markdown(f"- {item['quantity']} x **{prod_name}** @ ₦{item['price_at_purchase']:,.2f}")
                        else:
                            st.warning("No items found for this order.")

                        st.markdown("---")
                        current_status = order.get("status", "Pending").title()
                        status_options = ["Pending", "Confirmed", "Shipping", "Delivered", "Cancelled"]

                        if current_status in status_options:
                            next_statuses = status_options[status_options.index(current_status):]
                        else:
                            st.warning(f"Unknown status '{current_status}' for Order #{order['order_id']}")
                            next_statuses = status_options

                        new_status = st.selectbox(
                            f"🚚 Update Status for Order #{order['order_id']}",
                            options=next_statuses,
                            index=0,
                            key=f"status_select_{order['order_id']}"
                        )

                        if new_status != current_status:
                            if st.button(f"✅ Confirm Status Update to '{new_status}'", key=f"update_btn_{order['order_id']}"):
                                try:
                                    supabase.table("orders").update(
                                        {"status": new_status.lower()}
                                    ).eq("order_id", order["order_id"]).execute()
                                    st.success(f"Order #{order['order_id']} status updated to '{new_status}'")
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"Failed to update order status: {e}")

        except Exception as e:
            st.error(f"Error fetching orders: {e}")

    # --- History Tab (Delivered Orders) ---
    with tabs[3]:
        st.subheader("📜 Delivered Orders History")
        try:
            delivered_orders = supabase.table("orders").select(
                "*, users!inner(full_name, email), order_items(*)"
            ).eq("status", "delivered").order("created_at", desc=True).execute().data

            if not delivered_orders:
                st.info("No delivered orders yet.")
            else:
                for order in delivered_orders:
                    with st.expander(f"📦 Order #{order['order_id']} | ₦{order['total_amount']:,.2f}"):
                        st.markdown(f"**👤 Customer:** {order['users']['full_name']} ({order['users']['email']})")
                        st.markdown(f"**🕒 Date:** {order['created_at']}")
                        st.markdown("**🧺 Items:**")

                        if order['order_items']:
                            for item in order['order_items']:
                                try:
                                    prod = supabase.table("products").select("product_name").eq("product_id", item["product_id"]).execute().data
                                    prod_name = prod[0]["product_name"] if prod else "Unknown"
                                except:
                                    prod_name = "Unknown"
                                st.markdown(f"- {item['quantity']} x **{prod_name}** @ ₦{item['price_at_purchase']:,.2f}")
                        else:
                            st.warning("No items found for this order.")

                        st.markdown("**✅ Status:** Delivered")
                        st.markdown("---")
        except Exception as e:
            st.error(f"Error fetching delivered orders: {e}")

    # --- Analytics Tab ---
    with tabs[4]:
        try:
            import plotly.express as px
    
            # Fetch data
            users = st.session_state.supabase.table("users").select("*").execute().data
            orders = st.session_state.supabase.table("orders").select("*").execute().data
            products = st.session_state.supabase.table("products").select("*").execute().data
            order_items = st.session_state.supabase.table("order_items").select("*").execute().data
    
            # Convert to DataFrames
            df_users = pd.DataFrame(users) if users else pd.DataFrame()
            df_orders = pd.DataFrame(orders) if orders else pd.DataFrame()
            df_products = pd.DataFrame(products) if products else pd.DataFrame()
            df_order_items = pd.DataFrame(order_items) if order_items else pd.DataFrame()
    
            # Parse datetime
            if not df_orders.empty:
                df_orders['created_at'] = pd.to_datetime(df_orders['created_at'])
    
            # --- Filter Controls ---
            st.markdown("### 🔍 Filters")
            with st.expander("Filter Options"):
                col1, col2, col3 = st.columns(3)
    
                with col1:
                    selected_month = st.selectbox("Select Month", ["All"] + sorted(df_orders['created_at'].dt.strftime('%B').unique()) if not df_orders.empty else ["All"])
                with col2:
                    selected_year = st.selectbox("Select Year", ["All"] + sorted(df_orders['created_at'].dt.year.astype(str).unique()) if not df_orders.empty else ["All"])
                with col3:
                    selected_product_type = st.selectbox("Select Product Type", ["All"] + sorted(df_products['category'].dropna().unique()) if 'category' in df_products else ["All"])
    
                # Date range
                if not df_orders.empty:
                    min_date = df_orders['created_at'].min()
                    max_date = df_orders['created_at'].max()
                    start_date, end_date = st.date_input("Select Date Range", [min_date, max_date])
                else:
                    start_date, end_date = None, None
    
            # Apply filters to orders and items
            filtered_orders = df_orders.copy()
            if selected_month != "All":
                filtered_orders = filtered_orders[filtered_orders['created_at'].dt.strftime('%B') == selected_month]
            if selected_year != "All":
                filtered_orders = filtered_orders[filtered_orders['created_at'].dt.year.astype(str) == selected_year]
            if start_date and end_date:
                filtered_orders = filtered_orders[(filtered_orders['created_at'] >= pd.to_datetime(start_date)) & (filtered_orders['created_at'] <= pd.to_datetime(end_date))]
    
            # Filter order_items by filtered order_ids
            filtered_order_items = df_order_items[df_order_items['order_id'].isin(filtered_orders['order_id'])] if not df_orders.empty else pd.DataFrame()
    
            # Filter products by category
            if selected_product_type != "All" and 'category' in df_products:
                filtered_products = df_products[df_products['category'] == selected_product_type]
                filtered_order_items = filtered_order_items[filtered_order_items['product_id'].isin(filtered_products['product_id'])]
            else:
                filtered_products = df_products
    
            # --- Key Metrics ---
            total_customers = len(df_users)
            total_sales = len(filtered_orders)
            total_revenue = filtered_orders["total_amount"].sum() if "total_amount" in filtered_orders else 0
            total_products = len(filtered_products)
    
            st.markdown("#### 📊 Key Business Metrics")
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("##### 👥 Total Customers")
                st.markdown(f"<p style='color:blue; font-size:28px;'> {total_customers}</p>", unsafe_allow_html=True)
                st.markdown("##### 💰 Total Revenue")
                st.markdown(f"<p style='color:blue; font-size:28px;'> ₦{total_revenue:,.2f}</p>", unsafe_allow_html=True)
            with col2:
                st.markdown("##### 🛒 Total Sales")
                st.markdown(f"<p style='color:blue; font-size:28px;'> {total_sales}</p>", unsafe_allow_html=True)
                st.markdown("##### 🧾 Products Listed")
                st.markdown(f"<p style='color:blue; font-size:28px;'> {total_products}</p>", unsafe_allow_html=True)
    
            st.markdown("<hr style='border: 1px solid #000;'>", unsafe_allow_html=True)
    
            # --- Sales Trend ---
            st.markdown("##### 📈 Monthly Sales Trend")
            if not filtered_orders.empty:
                monthly_sales = filtered_orders.groupby(filtered_orders['created_at'].dt.to_period("M"))["total_amount"].sum().reset_index()
                monthly_sales['created_at'] = monthly_sales['created_at'].astype(str)
                st.line_chart(monthly_sales.set_index('created_at'))
            else:
                st.info("No filtered order data available for trend.")
    
            st.markdown("<hr style='border: 1px solid #000;'>", unsafe_allow_html=True)
    
            # --- Best-Selling Products ---
            st.markdown("##### 🏆 Top 5 Best-Selling Products")
            if not filtered_order_items.empty and not filtered_products.empty:
                top_products = filtered_order_items.groupby("product_id")["quantity"].sum().nlargest(5).reset_index()
                top_products = top_products.merge(filtered_products[["product_id", "product_name"]], on="product_id")
                st.bar_chart(top_products.set_index("product_name")["quantity"])
            else:
                st.info("No matching product sales data.")
    
            # --- Order Status Pie ---
            st.markdown("##### 📦 Order Status Distribution")
            if not filtered_orders.empty:
                status_counts = filtered_orders['status'].value_counts()
                st.plotly_chart(px.pie(names=status_counts.index, values=status_counts.values, title="Orders by Status"), use_container_width=True)
    
            # --- Revenue by Product Pie ---
            st.markdown("##### 💸 Revenue Share by Product")
            if not filtered_order_items.empty:
                filtered_order_items["revenue"] = filtered_order_items["quantity"] * filtered_order_items["price_at_purchase"]
                revenue_by_product = filtered_order_items.groupby("product_id")["revenue"].sum().reset_index()
                revenue_by_product = revenue_by_product.merge(filtered_products[["product_id", "product_name"]], on="product_id")
                revenue_by_product = revenue_by_product.sort_values(by="revenue", ascending=False).head(10)
                st.plotly_chart(px.pie(revenue_by_product, names="product_name", values="revenue", title="Revenue by Product"), use_container_width=True)
    
            # --- Customer Frequency ---
            st.markdown("##### 👤 Customer Order Frequency")
            if not filtered_orders.empty:
                order_freq = filtered_orders["user_id"].value_counts()
                st.plotly_chart(px.histogram(order_freq, nbins=20, title="Orders per Customer"), use_container_width=True)
    
            # --- Gender Pie Chart ---
            if "gender" in df_users.columns:
                st.markdown("##### 🧍 Gender Distribution")
                gender_dist = df_users["gender"].value_counts()
                st.plotly_chart(px.pie(names=gender_dist.index, values=gender_dist.values, title="Customer Gender Distribution"), use_container_width=True)
    
        except Exception as e:
            st.error(f"Error generating insights: {e}")
    
        st.markdown("<hr style='border: 1px solid #000;'>", unsafe_allow_html=True)
                      
#----------------------- Main Logic --------------------------
def main():
    if "show_register" not in st.session_state:
        st.session_state.show_register = False

    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    
    with st.sidebar:
        if st.session_state.get("logged_in") and "user" in st.session_state:
            user = st.session_state["user"]
            full_name = user.get("full_name", "Guest")
            st.success(f"👋 Welcome, {full_name}!")
    
            if st.button("Logout"):
                st.session_state.pop("user", None)
                st.session_state.logged_in = False
                st.rerun()
        else:
            st.info("👋 Welcome, Guest!")
            st.markdown("---")

    if st.session_state.get("viewing_cart"):
        view_cart()
        return

    # ✅ Always show the product list to non-admin users
    if st.session_state.get("logged_in") and st.session_state.user.get("email") == "tommiesfashion@gmail.com":
        admin_panel()
    else:
        product_list()

    # Call the footer function at the very end of main()
    app_footer()

if __name__ == "__main__":
    main()

# --- SIDEBAR CONTENT ---
def main():
    # Sidebar Branding
    st.sidebar.title("About Perfectfit 👗")

    st.sidebar.info(
        "***.....fast, reliable & elegant!***\n\n"
        "Perfectfit is your one-stop fashion store offering premium styles at unbeatable prices."
    )

    st.sidebar.markdown("**📞 Contact Us:**")
    st.sidebar.markdown(
        "- [💬 Chat with Sales Team](https://wa.me/2348136894472)\n"
        "- [💬 Chat with Customer Support](https://wa.me/2348062529172)"
    )

if __name__ == "__main__":
    main()

# --- APP DEVELOPER INFO ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 👨‍💻 App Developer")
st.sidebar.markdown(
    """
**Ezekiel BALOGUN**  
* _Data Scientist / Data Analyst_  
* _AI / Machine Learning Engineer_  
* _Automation / Business Intelligence Expert_  

📧 [ezekiel4true@yahoo.com](mailto:ezekiel4true@yahoo.com)  
🔗 [LinkedIn Profile](https://www.linkedin.com/in/ezekiel-balogun-39a14438)  
📞 +2348062529172
"""
)
