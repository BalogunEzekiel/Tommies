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
    # st.subheader("🔐 Login")
    login_form()  # Call your login form function here
elif st.session_state.show_register:
    # st.subheader("📝 Register")
    registration_form()  # Call your registration form function here

else:
    if st.button("View Cart"):
        st.session_state.viewing_cart = True

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
            st.rerun() # Rerun to show product list
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
                st.rerun() # Rerun to update total and display immediately
        with col3:
            if st.button("Remove", key=f"remove_{item['product_id']}"):
                remove_indices.append(i)

        total += item['qty'] * item['price']

    # Process removals
    for i in sorted(remove_indices, reverse=True):
        st.session_state.cart.pop(i)
        st.rerun() # Rerun to reflect immediate removal

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
        
    else:
        st.warning("Please log in or sign up to proceed with payment.")

    st.markdown("---") # Separator
    if st.button("🔙 Back to Products"):
        st.session_state.viewing_cart = False
        st.rerun() # Rerun to switch view

def admin_panel():
    st.subheader("🛠️ Admin Dashboard")

    tabs = st.tabs(["Overview", "Manage Users", "Manage Products", "View Orders"])

    # --- Overview Tab ---
    with tabs[0]:
        st.session_state.admin_dashboard_page = "Overview"
        st.subheader("🧰 Summary")
        st.info("Overview details will be displayed here.")

    # --- Manage Users Tab ---
    with tabs[1]:
        st.session_state.admin_dashboard_page = "Manage Users"
        st.subheader("👥 Customers Info Management")
        try:
            user_result = supabase.table("users").select("*").execute()
            users = user_result.data
            for user in users:
                st.write(f"- {user['user_name']} | {user['email']}")
        except Exception as e:
            st.error(f"Failed to fetch users: {e}")

    # --- Manage Products Tab ---
    with tabs[2]:
        st.session_state.admin_dashboard_page = "Manage Products"
        st.subheader("🛍️ Manage Products")
        try:
            product_result = supabase.table("products").select("*").execute()
            products = product_result.data
            for prod in products:
                st.write(f"- {prod['product_name']} | ₦{prod['price']:,.2f}")
        except Exception as e:
            st.error(f"Failed to fetch products: {e}")

    # --- View Orders Tab ---
    with tabs[3]:
        st.session_state.admin_dashboard_page = "View Orders"
        st.subheader("📦 Recent Orders")
        try:
            orders_result = supabase.table("orders").select(
                "*, users!inner(full_name, email), order_items(*)"
            ).order("created_at", desc=True).execute()
            orders = orders_result.data if orders_result.data else []
        except Exception as e:
            st.error(f"Error fetching orders: {e}")
            return

        if not orders:
            st.info("No orders found.")
            return

        for order in orders:
            st.markdown(f"**Order #{order['order_id']}**")
            st.write(f"**Customer:** {order['users']['full_name']} ({order['users']['email']})")
            st.write(f"**Date:** {order['created_at']}")
            st.write("**Items:**")

            if order['order_items']:
                for item in order['order_items']:
                    try:
                        prod_result = supabase.table("products").select("product_name").eq("product_id", item['product_id']).execute()
                        prod_name = prod_result.data[0]['product_name'] if prod_result.data else "Unknown Product"
                    except Exception as e:
                        prod_name = f"Error loading product: {e}"

                    st.write(f"- {item['quantity']} x {prod_name} at ₦{item['price_at_purchase']:,.2f}")
            else:
                st.write("- No items found for this order.")

            st.markdown(f"**Total: ₦{order['total_amount']:,.2f} | Status: {order.get('status', 'N/A')}**")
            st.divider()

def main():
    st.title("👗 Tommies Fashion Store")

    if "show_register" not in st.session_state:
        st.session_state.show_register = False

    with st.sidebar:
        if "user" in st.session_state:
            user = st.session_state.get("user", {})
            full_name = user.get("full_name", "Guest")
            st.success(f"👋 Welcome, {full_name}!")
            if st.button("Logout"):
                del st.session_state.user
                st.session_state.logged_in = False
                st.rerun()
            st.sidebar.markdown("---")

#    if st.session_state.viewing_cart:
#        view_cart()
#        # "Back to Products" button is now inside view_cart for consistency
#    else:
#        product_list()
        
    # Check if cart should be viewed
    if st.session_state.get("viewing_cart"):
        view_cart()
        return  # Prevent further rendering (like product_list or admin_panel)

    # Check if cart should be viewed
#    if st.session_state.get("viewing_cart"):
#        view_cart()
#        return  # Prevent further rendering (like product_list or admin_panel)

# Show Admin Panel or User Product List
    if st.session_state.get("logged_in"):
        if st.session_state.user["email"] == "admin@tommiesfashion.com":
            admin_panel()
        else:
            product_list()
            
if __name__ == "__main__":
    main()

# --- SIDEBAR CONTENT ---
def main():
    # Sidebar Branding
    st.sidebar.title("About Tommies 👗🧵")
    st.sidebar.info("Tommies is your one-stop fashion store offering premium styles at unbeatable prices.")

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
