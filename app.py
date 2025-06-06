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
def fetch_products():
    result = supabase.table("products").select("*").execute()
    return result.data if result.data else []

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

# --- UI Functions ---

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

def product_list():
    st.subheader("🛍️ Available Products")

    if 'cart' not in st.session_state:
        st.session_state.cart = []

    products = fetch_products()

    if not products:
        st.info("No products available at the moment.")
        return

    categories = sorted({p.get('category') for p in products if p.get('category')})
    sizes = sorted({p.get('size') for p in products if p.get('size')})

    category_filter = st.selectbox("Category", ["All"] + categories)
    size_filter = st.selectbox("Size", ["All"] + sizes)
    price_range = st.slider("Price Range (₦)", 0, 100000, (0, 100000))

    filtered = [
        p for p in products
        if (category_filter == "All" or p.get('category') == category_filter) and
           (size_filter == "All" or p.get('size') == size_filter) and
           (price_range[0] <= float(p.get('price', 0) or 0) <= price_range[1])
    ]

    if not filtered:
        st.info("No products match your filters.")
        return

    cols_per_row = 3
    cols = st.columns(cols_per_row)

    for i, p in enumerate(filtered):
        with cols[i % cols_per_row]:
            st.image(p.get('image_url', 'https://via.placeholder.com/150'), use_container_width=True)
            st.markdown(f"**{p.get('product_name', 'N/A')}**")
            price = float(p.get('price', 0) or 0)
            st.markdown(f"₦{price:,.2f}")
            stock = int(p.get('stock_quantity', 0) or 0)
            st.markdown(f"Stock: {stock} | Size: {p.get('size', 'N/A')} | Category: {p.get('category', 'N/A')}")

            if stock > 0:
                qty = st.number_input(
                    "Qty", min_value=1, max_value=stock, key=f"qty_{p['product_id']}", value=1
                )
                if st.button("Add to Cart", key=f"cart_{p['product_id']}"):
                    if not st.session_state.get('logged_in', False):
                        st.warning("Please log in or sign up to add items to your cart.")
                    else:
                        existing = next((item for item in st.session_state.cart if item['product_id'] == p['product_id']), None)
                        if existing:
                            existing['qty'] += qty
                            st.success(f"Updated quantity of {p['product_name']} in cart to {existing['qty']}.")
                        else:
                            st.session_state.cart.append({**p, 'qty': qty})
                            st.success(f"Added {qty} x {p['product_name']} to cart.")
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

    # Show cart items
    for i, item in enumerate(st.session_state.cart):
        col1, col2, col3 = st.columns([0.6, 0.2, 0.2])
        with col1:
            st.write(f"**{item.get('product_name', 'N/A')}**")
            st.write(f"{item['qty']} x ₦{item['price']:,.2f} each")
        with col2:
            new_qty = st.number_input(
                f"Qty for {item['product_name']}",
                min_value=1,
                max_value=item.get('stock_quantity', item['qty']),
                value=item['qty'],
                key=f"cart_qty_{item['product_id']}"
            )
            if new_qty != item['qty']:
                item['qty'] = new_qty
                st.rerun()
        with col3:
            if st.button("Remove", key=f"remove_{item['product_id']}"):
                remove_indices.append(i)

        total += item.get('qty', 1) * item.get('price', 0)

    for i in sorted(remove_indices, reverse=True):
        st.session_state.cart.pop(i)
        st.rerun()

    st.markdown("---")
    st.markdown(f"### 🧾 Total: ₦{total:,.2f}")
    st.markdown("---")

    if st.session_state.logged_in:
        if total > 0:
            if st.button("Proceed to Flutterwave Payment"):
                initiate_payment(total, st.session_state.user['email'], st.session_state.cart, st.session_state.user['user_id']) # Pass cart and user_id
        else:
            st.warning("Cannot proceed with an empty cart.")
    else:
        st.warning("Please log in or sign up to proceed with payment.")
        
    if st.button("🔙 Back to Products"):
        st.session_state.viewing_cart = False
        st.rerun()

def admin_panel():
    st.subheader("🛠️ Admin Dashboard")

    tabs = st.tabs(["Overview", "Manage Users", "Manage Products", "View Orders", "Orders Confirmation", "Insights"])

    # --- Overview Tab ---
    with tabs[0]:
        st.subheader("🧰 Summary")
        st.info("Overview details will be displayed here.")

    # --- Manage Users Tab ---
    with tabs[1]:
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
    with tabs[2]:
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
    with tabs[3]:
        st.subheader("📦 Recent Orders")
        try:
            orders = supabase.table("orders").select("*, users!inner(full_name, email), order_items(*)").order("created_at", desc=True).execute().data
            if not orders:
                st.info("No orders found.")
            for order in orders:
                st.markdown(f"**Order #{order['order_id']}**")
                st.write(f"**Customer:** {order['users']['full_name']} ({order['users']['email']})")
                st.write(f"**Date:** {order['created_at']}")
                st.write("**Items:**")

                if order['order_items']:
                    for item in order['order_items']:
                        prod_name = "Unknown"
                        try:
                            prod = supabase.table("products").select("product_name").eq("product_id", item["product_id"]).execute().data
                            if prod:
                                prod_name = prod[0]["product_name"]
                        except:
                            pass
                        st.write(f"- {item['quantity']} x {prod_name} @ ₦{item['price_at_purchase']:,.2f}")
                else:
                    st.write("- No items found.")
                st.markdown(f"**Total: ₦{order['total_amount']:,.2f} | Status: {order.get('status', 'N/A')}**")
                st.divider()
        except Exception as e:
            st.error(f"Error fetching orders: {e}")

    # --- Orders Confirmation Tab ---
    with tabs[4]:
        st.subheader("🚚 Update Order Status")
        try:
            orders = supabase.table("orders").select("*").eq("status", "Pending").execute().data
            if orders:
                for order in orders:
                    st.write(f"Order #{order['order_id']} - Total: ₦{order['total_amount']:,.2f}")
                    new_status = st.selectbox(
                        f"Update status for Order #{order['order_id']}",
                        options=["Pending", "Confirmed", "Shipping", "Delivered"],
                        index=["Pending", "Confirmed", "Shipping", "Delivered"].index(order.get("status", "Pending")),
                        key=f"status_{order['order_id']}"
                    )
                    if st.button(f"Save Status for Order #{order['order_id']}"):
                        supabase.table("orders").update({"status": new_status}).eq("order_id", order["order_id"]).execute()
                        st.success(f"✅ Order #{order['order_id']} status updated to {new_status}")
            else:
                st.info("No pending orders.")
        except Exception as e:
            st.error(f"Error updating orders: {e}")

    # --- Insights Tab ---
    with tabs[5]:
        st.subheader("📊 Business Insights")
        try:
            users = supabase.table("users").select("*").execute().data
            orders = supabase.table("orders").select("*").execute().data
            products = supabase.table("products").select("*").execute().data
            order_items = supabase.table("order_items").select("*").execute().data

#            df_orders = pd.DataFrame(orders)
#            df_users = pd.DataFrame(users)
#            df_products = pd.DataFrame(products)
#            df_order_items = pd.DataFrame(order_items)

            total_customers = len(users)
            total_orders = len(orders)
            total_revenue = sum(order["total_amount"] for order in orders)
            total_products = len(products)
                
            total_customers = len(df_users)
            total_sales = len(df_orders)
            total_revenue = df_orders["total_amount"].sum()

            st.metric("👥 Total Customers", total_customers)
            st.metric("📦 Total Sales", total_sales)
            st.metric("💰 Total Revenue", f"₦{total_revenue:,.2f}")
            st.metric("🧾 Products Listed", total_products)

            st.metric("👥 Total Customers", total_customers)
            st.metric("🛒 Total Sales", total_sales)
            st.metric("💰 Total Revenue", f"₦{total_revenue:,.2f}")

            # Monthly sales trend
            df_orders['created_at'] = pd.to_datetime(df_orders['created_at'])
            monthly_sales = df_orders.groupby(df_orders['created_at'].dt.to_period("M"))["total_amount"].sum().reset_index()
            monthly_sales['created_at'] = monthly_sales['created_at'].astype(str)
            st.line_chart(monthly_sales.set_index('created_at'))

            # Top 5 Products
            order_items = supabase.table("order_items").select("*").execute().data
            if order_items:
                df_items = pd.DataFrame(order_items)
                top_products = df_items.groupby("product_id")["quantity"].sum().nlargest(5).reset_index()
                top_products = top_products.merge(df_products[["product_id", "product_name"]], on="product_id")
                st.bar_chart(top_products.set_index("product_name")["quantity"])
        except Exception as e:
            st.error(f"Error generating insights: {e}")

                      
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

if __name__ == "__main__":
    main()

# --- SIDEBAR CONTENT ---
def main():
    # Sidebar Branding
    st.sidebar.title("About Perfectfit 👗🧵")
    st.sidebar.info("***.....fast and reliable.***")
    st.sidebar.info("Perfectfit is your one-stop fashion store offering premium styles at unbeatable prices.")

if __name__ == "__main__":
    main()

# --- APP DEVELOPER INFO ---
st.sidebar.markdown("---")
st.sidebar.markdown("### 👨‍💻 App Developer")
st.sidebar.markdown(
    """
**Ezekiel BALOGUN**  
_Data Scientist / Data Analyst_  
_AI / Machine Learning Engineer_  
_Automation / Business Intelligence Expert_  

📧 [ezekiel4true@yahoo.com](mailto:ezekiel4true@yahoo.com)  
🔗 [LinkedIn Profile](https://www.linkedin.com/in/ezekiel-balogun-39a14438)  
📞 +2348062529172
"""
)
