# 👗 Perfectfit Fashion Store

I developed a fully functional AI-Powered e-commerce web application for an online fashion store powered by PostgreSQL via Supabase, designed to provide a seamless and intuitive shopping experience—from product discovery to secure checkout.

Built with Streamlit, the platform features a rich product display, dynamic shopping cart, order management system and a streamlined checkout flow. It integrates ***Flutterwave for secure online payments***, ensuring fast and reliable transactions.

The backend is powered by PostgreSQL via Supabase, which handles:

Authentication

Database management

Product catalog and inventory

Order tracking and processing

This robust architecture ensures a scalable, responsive, and user-friendly shopping platform tailored for modern online retail.

I developed a fully functional e-commerce web application, PostgreSQL-powered via Supabase for an online fashion store, designed to deliver a seamless shopping experience from browsing to checkout. The application is built with Streamlit, powered by PostgreSQL via Supabase, and integrated with Flutterwave for secure online payments.

### Preview
![image](https://github.com/user-attachments/assets/c4d44115-2105-429d-95bd-3ae8ba70f72d)

* ***[Check out The Perfectfit Fashore Store](https://tommies.streamlit.app/)***

## 🛍️ Core Features
**Product Display:** Clean and intuitive UI for showcasing a variety of fashion products with images, descriptions, prices, and categories.

**Shopping Cart System:** Dynamic shopping cart that allows users to add, remove, and update items with real-time price calculations.

**Order Management:** Customers can review their orders before finalizing, and all transactions are securely tracked in the backend.

**Checkout Process:** Streamlined, user-friendly checkout interface to collect delivery details and summarize order details before payment.

**Payment Gateway Integration:** Integrated with Flutterwave to enable secure, fast, and reliable online transactions.

## 🔐 Backend & Infrastructure
* ### Supabase Integration:

* **Authentication:** Handles user registration, login, and session management.

* **Database Management:** Real-time PostgreSQL database used for storing user data, product catalogs, order history, and inventory.

* **Product Management:** CRUD operations for managing the product list, categories, sizes, prices, and stock levels.

* **Order Processing:** Orders are automatically recorded and updated in the database upon payment confirmation.

## 🔧 Advanced Functionalities Implemented
✅ **Email Confirmations:**
Automatic email notifications are sent to users upon successful order placement, improving communication and reliability.

✅ **Inventory Management for Admins:**
An admin dashboard enables authorized users to manage product inventory, update listings, and monitor sales data in real time.

✅ **Mobile-Responsive UI:**
Optimized for all screen sizes, ensuring a smooth shopping experience on smartphones, tablets, and desktops.

✅ **Product Filters:**
Users can filter the product catalog by price, size, and category, making it easy to find desired items quickly.

✅ **Secure Payments:**
All payment interactions are encrypted and securely handled through the Flutterwave payment gateway, ensuring user trust and safety.

## 💻 Tech Stack
**Frontend:** Streamlit (custom components, styled UI)

**Backend:** Supabase (PostgreSQL, Auth, Storage, Realtime)

**Payments:** Flutterwave API

**Email Notifications:** Supabase functions or third-party SMTP integration (e.g., SendGrid)

**Deployment:** Streamlit Cloud / Custom Hosting

## 🚀 Outcome
This project demonstrates how modern tools like Streamlit and Supabase can be combined to build robust, scalable, and production-ready web applications—even outside of traditional use cases like dashboards or data apps. It showcases the ability to integrate full e-commerce capabilities into a Python-powered frontend, along with real-time data sync and secure payments.

---

## 📦 Features Showcase

### 👥 User Authentication

* Secure **user registration and login**
* **Password hashing** using `bcrypt`
* **Session state** management for persistent login
 <table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/3c4bd12a-ac9e-43bf-9480-bc8511c91f73" width="400"/></td>
    <td><img src="https://github.com/user-attachments/assets/dc4e23aa-2fdd-450c-bf25-8b3227d6438a" width="400"/></td>
  </tr>
</table>

### 🛍️ Product Catalog

* List of products with images, prices, sizes, and stock availability
* Dynamically retrieved from Supabase `products` table
<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/de98ee48-242a-4ef5-95fc-76103073bbd8" width="400"/></td>
    <td><img src="https://github.com/user-attachments/assets/bf871abf-46d9-4e1d-a91e-2d095c1dfca1" width="400"/></td>
  </tr>
</table>

### 🛒 Shopping Cart

* Add to cart functionality
* Quantity control per item
* Dynamic price calculation
* Remove items from cart

### 💳 Checkout and Orders

* Order summary and total amount
* On checkout, orders are saved to Supabase (`orders` and `order_items`)
* Displays order receipt after placement

### 🛠️ Admin Panel

* Admin login (`admin@tommies.com`) for internal dashboard
* View all orders and customers
* Extendable to manage stock and product listings
<table>
  <tr>
    <td><img src="https://github.com/user-attachments/assets/68e2152d-75f0-4e9b-8f79-9bf2d310c116" width="400"/></td>
    <td><img src="https://github.com/user-attachments/assets/73a2d039-468d-4541-866e-a07d13714391" width="400"/></td>
  </tr>
</table>

---

## 🗃️ Database Schema (Supabase SQL)

Four main tables:

### `products`

Stores all product details.

```sql
CREATE TABLE products (
    product_id SERIAL PRIMARY KEY,
    product_name TEXT NOT NULL,
    description TEXT NOT NULL,
    price NUMERIC(10, 2) NOT NULL CHECK (price >= 0),
    category TEXT NOT NULL,
    size TEXT NOT NULL,
    color TEXT NOT NULL,
    image_url TEXT NOT NULL,
    stock_quantity INTEGER NOT NULL CHECK (stock_quantity >= 0),
    added_on DATE NOT NULL DEFAULT CURRENT_DATE
);
```

### `users`

Stores registered users.

```sql
CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    full_name TEXT NOT NULL,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    address TEXT,
    phone TEXT NOT NULL,
    registered_on DATE NOT NULL DEFAULT CURRENT_DATE
);
```

### `orders`

Stores summary data of customer orders.

```sql
CREATE TABLE orders (
    order_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL,
    total_amount NUMERIC(10, 2) NOT NULL CHECK (total_amount >= 0),
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'cancelled', 'completed')),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_user_order FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
);
```

### `order_items`

Stores individual items in an order.

```sql
CREATE TABLE order_items (
    order_item_id SERIAL PRIMARY KEY,
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity > 0),
    price_at_purchase NUMERIC(10, 2) NOT NULL CHECK (price_at_purchase >= 0),
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    CONSTRAINT fk_order FOREIGN KEY (order_id) REFERENCES orders(order_id) ON DELETE CASCADE,
    CONSTRAINT fk_product FOREIGN KEY (product_id) REFERENCES products(product_id) ON DELETE CASCADE
);
```

### `password_resets`

Resets users password.

```sql
CREATE TABLE password_resets (
    password_reset_id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    token_hash TEXT NOT NULL UNIQUE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at TIMESTAMPTZ NOT NULL,
    used BOOLEAN NOT NULL DEFAULT FALSE
);
```

---

* **[View Perfectfit Store](https://tommies.streamlit.app/)**

---

## 🚀 Setup Instructions

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/tommies-fashion.git
cd tommies-fashion
```

### 2. Install Dependencies

```bash
pip install -r requirements.txt
```

### 3. Configure Supabase

Create a `.env` file in the project root:

```
SUPABASE_URL=https://your-supabase-url.supabase.co
SUPABASE_KEY=your-service-role-key
```

Or directly update the credentials in the `config.py` file if hardcoded.

### 4. Run the App

```bash
streamlit run app.py
```

---

## 🌐 Deployment

### Recommended: Streamlit Cloud

1. Push the repo to GitHub.
2. Go to [Streamlit Cloud](https://streamlit.io/cloud).
3. Connect your GitHub repo.
4. Set up the `SUPABASE_URL` and `SUPABASE_KEY` secrets under Settings > Secrets.
5. Click Deploy.

### Alternative: Render, Railway or VPS (Heroku, DigitalOcean)

---

## 🧪 Usage Guide

### 🔐 Register/Login

* Use the sidebar to register or log in.
* Admin credentials: `@` with custom password (stored manually or via seed).

### 🛍️ Shopping

* Browse products, add them to your cart.
* Adjust quantities.
* Checkout and generate receipt.

### 🧾 Orders

* Orders are stored in Supabase with item-level breakdown.
* Admins can view all orders from the dashboard.

---

## 🔒 Security

* Passwords are stored hashed using `bcrypt`
* Session data is kept in `st.session_state`
* Inputs are sanitized before writing to Supabase

---

## 🔧 Tech Stack

* [Streamlit](https://tommies.streamlit.app/)
* [Supabase](https://supabase.io)
* [PostgreSQL](https://www.postgresql.org)
* [Python, Pandas](https://github.com/BalogunEzekiel/Perfectfit/blob/main/app.py)
* [Pillow (PIL)](https://python-pillow.org)

---

## 📬 Contact

**Developer:** [Ezekiel Balogun](https://www.linkedin.com/in/ezekiel-balogun-39a14438/)

**Emil:** ezekiel4true@yahoo.com

**Mobile Phone:** +234 806 2529 172 

Feel free to fork, improve or contribute by submitting a pull request.

***I am open to opportunities in organizations that value hard work, uphold strong principles, encourage growth and advancement and prioritize recognition and motivation. I look forward to collaborating with fellow Data Scientists and Analysts, Artificial Intelligence and Machine Learning Engineers, Workflow Automation Specialists, and Business Intelligence Experts on impactful data-driven and AI-powered projects.***

---

## 📄 License

This project is licensed under the MIT License.
