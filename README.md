# Perfectfit Fashion Store

A fully functional PostgreSQL-powered online fashion store (e-commerce) web application built with Streamlit, featuring product display, a shopping cart, order management, checkout and Flutterwave payment gateway integration. Supabase powers authentication, database management, product handling, and order processing.

---

## 📦 Features

### 👥 User Authentication

* Secure **user registration and login**
* **Password hashing** using `bcrypt`
* **Session state** management for persistent login

### 🛍️ Product Catalog

* List of products with images, prices, sizes, and stock availability
* Dynamically retrieved from Supabase `products` table

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

* [Streamlit](https://streamlit.io)
* [Supabase](https://supabase.io)
* [PostgreSQL](https://www.postgresql.org)
* [Pandas](https://pandas.pydata.org)
* [Pillow (PIL)](https://python-pillow.org)

---

## 📬 Contact & Contributions

**Author:** [Ezekiel Balogun](https://www.linkedin.com/in/ezekiel-balogun-39a14438/)

**Emil:** ezekiel4true@yahoo.com

**Mobile Phone:** +234 806 2529 172 

Feel free to fork, improve or contribute by submitting a pull request.

I am open to opportunities in organizations that value hard work, uphold strong principles, encourage growth and advancement, and prioritize recognition and motivation. I look forward to collaborating with fellow Data Scientists and Analysts, Artificial Intelligence and Machine Learning Engineers, Workflow Automation specialists, and Business Intelligence experts on impactful projects.

---

## 📄 License

This project is licensed under the MIT License.

---

## ✅ To-Do (Suggestions)

* Email confirmations on successful orders
* Inventory management for admins
* Mobile UI responsiveness
* Product filters (price, size, category)
* Payment gateway integration

