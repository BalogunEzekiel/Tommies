import streamlit as st
from urllib.parse import quote_plus
import hashlib
import smtplib
from email.message import EmailMessage
from supabase import create_client

st.set_page_config(page_title="Tommies Fashion", layout="wide")

# --- Initialize Supabase client ---
supabase_url = st.secrets["supabase"]["url"]
supabase_key = st.secrets["supabase"]["key"]
supabase = create_client(supabase_url, supabase_key)

# --- Helper Functions ---

def hash_password(password: str) -> str:
    """Return SHA256 hash of the password."""
    return hashlib.sha256(password.encode()).hexdigest()

def get_user(email: str):
    """Fetch user by email from Supabase."""
    result = supabase.table("users").select("*").eq("email", email).execute()
    if result.data and len(result.data) > 0:
        return result.data[0]
    return None

def register_user(name, email, password, phone, address):
    """Register new user."""
    hashed = hash_password(password)
    result = supabase.table("users").insert({
        "full_name": name,
        "email": email,
        "password_hash": hashed,
        "phone": phone,
        "address": address
    }).execute()
    return result

def authenticate(email, password):
    """Authenticate user with email and password."""
    hashed = hash_password(password)
    user = get_user(email)
    if user and user["password_hash"] == hashed:
        return user
    return None

def fetch_products():
    """Fetch all products from Supabase."""
    result = supabase.table("products").select("*").execute()
    return result.data if result.data else []

def send_confirmation_email(email, order_id):
    """Send order confirmation email (setup with your SMTP details)."""
    try:
        msg = EmailMessage()
        msg.set_content(f"Thank you for your order #{order_id} from Tommies Fashion Store!")
        msg["Subject"] = "Order Confirmation"
        msg["From"] = "your-email@gmail.com"  # Replace with your sending email
        msg["To"] = email

        with smtplib.SMTP("smtp.gmail.com", 587) as smtp:
            smtp.starttls()
            smtp.login("your-email@gmail.com", "your-email-password")  # Use environment variables ideally
            smtp.send_message(msg)
    except Exception as e:
        st.warning(f"Email failed to send: {e}")

def create_order(user_id, cart):
    """Create an order and update product stock."""
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

        # Update stock quantity
        new_stock = item['stock_quantity'] - item['qty']
        supabase.table("products").update({
            "stock_quantity": new_stock
        }).eq("product_id", item['product_id']).execute()

    send_confirmation_email(st.session_state.user['email'], order_id)
    return order_id

# --- Session State Initialization ---

def init_session_state():
    """Initialize all necessary session state keys."""
    if "cart" not in st.session_state:
        st.session_state.cart = []
    if "logged_in" not in st.session_state:
        st.session_state.logged_in = False
    if "user" not in st.session_state:
        st.session_state.user = {}
    if "viewing_cart" not in st.session_state:
        st.session_state.viewing_cart = False

# --- UI Components ---

def registration_form():
    st.sidebar.subheader("📝 Register")
    name = st.sidebar.text_input("Full Name", key="reg_name")
    email = st.sidebar.text_input("Email", key="reg_email")
    phone = st.sidebar.text_input("Phone", key="reg_phone")
    address = st.sidebar.text_area("Address", key="reg_address")
    password = st.sidebar.text_input("Password", type="password", key="reg_password")

    if st.sidebar.button("Register"):
        if not all([name, email, phone, address, password]):
            st.sidebar.warning("Please fill in all fields")
            return
        if get_user(email):
            st.sidebar.error("Email already registered. Please login.")
            return
        result = register_user(name, email, password, phone, address)
        if result.status_code == 201:
            st.sidebar.success("✅ Registration successful! Please log in.")
            # Clear form fields
            for key in ["reg_name", "reg_email", "reg_phone", "reg_address", "reg_password"]:
                st.session_state[key] = ""
        else:
            st.sidebar.error("❌ Registration failed. Try again.")

def login_form():
    st.sidebar.subheader("🔐 Login")
    email = st.sidebar.text_input("Email", key="login_email")
    password = st.sidebar.text_input("Password", type="password", key="login_password")

    if st.sidebar.button("Login"):
        if not email or not password:
            st.sidebar.warning("Enter both email and password")
            return
        user = authenticate(email, password)
        if user:
            st.session_state.logged_in = True
            st.session_state.user = user
            st.sidebar.success(f"Welcome, {user['full_name']}!")
            # Clear login fields
            st.session_state["login_email"] = ""
            st.session_state["login_password"] = ""
        else:
            st.sidebar.error("Invalid credentials")

def product_list():
    st.subheader("🛍️ Available Products")
    products = fetch_products()
    if not products:
        st.info("No products available at the moment.")
        return

    categories = sorted({p['category'] for p in products if p['category']})
    sizes = sorted({p['size'] for p in products if p['size']})

    category_filter = st.selectbox("Category", ["All"] + categories)
    size_filter = st.selectbox("Size", ["All"] + sizes)
    price_range = st.slider("Price Range (₦)", 0, 100000, (0, 100000))

    filtered = [
        p for p in products
        if (category_filter == "All" or p['category'] == category_filter)
        and (size_filter == "All" or p['size'] == size_filter)
        and (price_range[0] <= float(p['price']) <= price_range[1])
    ]

    for p in filtered:
        st.image(p['image_url'], use_container_width=True)
        st.markdown(f"**{p['product_name']}**  \n₦{float(p['price']):,.2f}")
        st.markdown(f"Stock: {p['stock_quantity']} | Size: {p['size']} | Category: {p['category']}")

        if st.session_state.logged_in:
            qty = st.number_input(
                "Qty", min_value=1, max_value=p['stock_quantity'], key=f"qty_{p['product_id']}", value=1
            )
            if st.button("Add to Cart", key=f"cart_{p['product_id']}"):
                existing = next((item for item in st.session_state.cart if item['product_id'] == p['product_id']), None)
                if existing:
                    st.warning("Item already in cart. Adjust quantity in cart view.")
                else:
                    st.session_state.cart.append({**p, 'qty': qty})
                    st.success(f"Added {qty} x {p['product_name']} to cart.")
        else:
            st.info("Login to add to cart.")

def view_cart():
    st.subheader("🛒 Your Cart")
    if not st.session_state.cart:
        st.info("Your cart is empty.")
        return

    total = 0
    remove_indices = []

    for i, item in enumerate(st.session_state.cart):
        st.write(f"{item['qty']} x {item['product_name']} - ₦{item['price']:,.2f} each")
        total += item['qty'] * item['price']

        if st.button(f"Remove {item['product_name']}", key=f"remove_{item['product_id']}"):
            remove_indices.append(i)

    for i in sorted(remove_indices, reverse=True):
        st.session_state.cart.pop(i)
        st.experimental_rerun()

    st.markdown(f"**Total: ₦{total:,.2f}**")

    if st.button("🧾 Place Order"):
        if not st.session_state.cart:
            st.warning("Your cart is empty!")
            return
        order_id = create_order(st.session_state.user['user_id'], st.session_state.cart)
        st.success(f"✅ Order #{order_id} placed! Confirmation sent to your email.")
        st.session_state.cart = []

def admin_panel():
    st.title("🛠️ Admin Dashboard")
    orders_result = supabase.table("orders").select("*, users(*), order_items(*)").order("created_at", desc=True).execute()
    orders = orders_result.data if orders_result.data else []

    for order in orders:
        st.markdown(f"**Order #{order['order_id']}** by {order['users']['full_name']} on {order['created_at']}")
        for item in order['order_items']:
            prod_result = supabase.table("products").select("product_name").eq("product_id", item['product_id']).execute()
            prod_name = prod_result.data[0]['product_name'] if prod_result.data else "Unknown Product"
            st.write(f"- {item['quantity']} x {prod_name} at ₦{item['price_at_purchase']}")
        st.markdown(f"**Total: ₦{order['total_amount']} | Status: {order.get('status', 'N/A')}**")
        st.divider()

# --- Main App ---

def main():
    init_session_state()
    st.title("👗 Tommies Fashion Store")

    if st.session_state.logged_in:
        # Admin check
        if st.session_state.user.get('email') == 'admin@tommies.com':
            admin_panel()
            return

        # User navigation buttons
        if st.sidebar.button("🛒 View Cart"):
            st.session_state.viewing_cart = True

        if st.sidebar.button("Logout"):
            st.session_state.logged_in = False
            st.session_state.user = {}
            st.session_state.cart = []
            st.session_state.viewing_cart = False
            st.experimental_rerun()

        # View cart or product list
        if st.session_state.viewing_cart:
            view_cart()
            if st.button("🔙 Back to Products"):
                st.session_state.viewing_cart = False
                st.experimental_rerun()
        else:
            product_list()

    else:
        product_list()
        st.sidebar.markdown("---")
        login_form()
        st.sidebar.markdown("New user? Register below:")
        registration_form()

if __name__ == "__main__":
    main()
