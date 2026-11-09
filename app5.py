import streamlit as st
import pandas as pd
import joblib
import matplotlib.pyplot as plt
import seaborn as sns
from PIL import Image
import plotly.express as px
from datetime import datetime
import requests
import logging
import hashlib 
import random
import string
import smtplib
import re
from email.mime.text import MIMEText
import mysql.connector
from mysql.connector import Error

logging.getLogger("streamlit.runtime.scriptrunner.script_runner").setLevel(logging.ERROR)

# ✅ Page config should be set before any other Streamlit command
st.set_page_config(page_title="Food Waste Prediction", layout="wide")

# ====== FIXED MYSQL DATABASE CONFIGURATION ======
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'Sindhu@2003',
    'database': 'food_waste_app',
    'port': 3306,
}

def init_db_connection():
    """Initialize MySQL connection"""
    try:
        conn = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            port=DB_CONFIG['port'],
            auth_plugin='mysql_native_password',
            connection_timeout=10
        )
        return conn
    except Error as e:
        st.sidebar.error(f"❌ MySQL Error: {e}")
        return None
    except Exception as e:
        st.sidebar.error(f"❌ Connection Error: {e}")
        return None

def create_tables_if_not_exists():
    """Create database tables if they don't exist"""
    try:
        # First connect without database to create it
        conn = mysql.connector.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            port=DB_CONFIG['port']
        )
        cursor = conn.cursor()
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {DB_CONFIG['database']}")
        cursor.execute(f"USE {DB_CONFIG['database']}")
        cursor.close()
        conn.close()
        
        # Now connect with database and create tables
        conn = mysql.connector.connect(**DB_CONFIG)
        cursor = conn.cursor()
        
        # Create users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) UNIQUE NOT NULL,
                email VARCHAR(100) UNIQUE NOT NULL,
                password_hash VARCHAR(64) NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # Create predictions table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions (
                id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(50) NOT NULL,
                ingredient VARCHAR(100),
                predicted_unsold_kg DECIMAL(10,2),
                uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        conn.commit()
        cursor.close()
        conn.close()
        
        st.sidebar.success("✅ Database tables created")
        return True
    except Exception as e:
        st.sidebar.warning(f"⚠️ Database setup: {str(e)[:50]}...")
        return False

# Initialize database tables
create_tables_if_not_exists()

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

# ====== REAL DATABASE FUNCTIONS ======
def save_user(username, email, password_hash):
    """Save user to MySQL database"""
    try:
        conn = init_db_connection()
        if conn is None:
            return False
            
        cursor = conn.cursor()
        
        # Check if user already exists
        cursor.execute("SELECT id FROM users WHERE username = %s", (username,))
        if cursor.fetchone():
            cursor.close()
            conn.close()
            return False
        
        # Insert new user
        cursor.execute(
            "INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)",
            (username, email, password_hash)
        )
        
        conn.commit()
        cursor.close()
        conn.close()
        return True
    except Exception as e:
        st.error(f"Database error: {str(e)[:100]}")
        return False
    finally:
        try:
            if 'conn' in locals():
                conn.close()
        except:
            pass

def get_user(username):
    """Get user from MySQL database"""
    try:
        conn = init_db_connection()
        if conn is None:
            return None
            
        cursor = conn.cursor(dictionary=True)
        cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
        user = cursor.fetchone()
        cursor.close()
        conn.close()
        return user
    except Exception:
        return None
    finally:
        try:
            if 'conn' in locals():
                conn.close()
        except:
            pass

def save_prediction_to_db(df, username):
    try:
        conn = init_db_connection()
        if conn is None:
            return False

        cursor = conn.cursor()

        # IMPORTANT: Clear old predictions for this user
        cursor.execute(
            "DELETE FROM predictions WHERE username = %s",
            (username,)
        )

        # Insert new predictions
        for _, row in df.iterrows():
            cursor.execute("""
                INSERT INTO predictions (username, ingredient, predicted_unsold_kg)
                VALUES (%s, %s, %s)
            """, (
                username,
                row["Ingredient"],
                float(row["Predicted_Unsold_kg"])
            ))

        conn.commit()
        cursor.close()
        conn.close()
        return True

    except Exception as e:
        st.error(f"Prediction save error: {e}")
        return False


# ================= FETCH LATEST PREDICTIONS FOR MENU =================
def get_user_predictions(username):
    """
    Fetch latest predictions for menu generation
    ALWAYS returns: ingredient, waste_kg
    """
    try:
        conn = init_db_connection()
        if conn is None:
            return pd.DataFrame()

        query = """
            SELECT ingredient,
                   predicted_unsold_kg AS waste_kg
            FROM predictions
            WHERE username = %s
            ORDER BY uploaded_at DESC
            LIMIT 50
        """

        df = pd.read_sql(query, conn, params=[username])
        return df

    except Exception as e:
        return pd.DataFrame()

    finally:
        try:
            conn.close()
        except:
            pass


def get_demand_score(df_predictions):
    """Calculate demand score: LOW WASTE = HIGH DEMAND"""
    if df_predictions.empty:
        return pd.DataFrame()
    
    if df_predictions['avg_waste'].max() > 0:
        df_predictions['demand_score'] = 10 * (1 - (df_predictions['avg_waste'] / df_predictions['avg_waste'].max()))
    else:
        df_predictions['demand_score'] = 5.0
    
    df_predictions['demand_score'] = df_predictions['demand_score'].round(2)
    df_predictions['demand_rank'] = range(1, len(df_predictions) + 1)
    return df_predictions

# ------------------ SESSION STATE INIT ------------------
# ====== SESSION STATE ======
if 'users' not in st.session_state:
    st.session_state.users = {}
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False
if 'username' not in st.session_state:
    st.session_state.username = ""
if 'user_email' not in st.session_state:
    st.session_state.user_email = ""
if 'auth_page' not in st.session_state:
    st.session_state.auth_page = "📝 Create Account"

# ====== CREATE ACCOUNT (WITH DATABASE) ======
def create_account():
    st.markdown("<h2 style='text-align: center; color:#28a745;'>📝 Create Account</h2>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 3])
    
    with col2:
        new_user = st.text_input("👤 Username", key="create_user")
        new_email = st.text_input("📧 Email", key="create_email")
        new_pass = st.text_input("🔒 Password", type="password", key="create_pass")
        confirm_pass = st.text_input("🔒 Confirm Password", type="password", key="confirm_pass")
        
        if st.button(" Create Account", type="primary"):
            if not all([new_user, new_email, new_pass, confirm_pass]):
                st.error("❌ All fields required!")
            elif new_pass != confirm_pass:
                st.error("❌ Passwords don't match!")
            elif len(new_pass) < 6:
                st.error("❌ Password must be at least 6 characters!")
            else:
                # Hash the password
                password_hash = hash_password(new_pass)
                
                # Save to session state
                st.session_state.users[new_user] = {
                    'password': password_hash,
                    'email': new_email
                }
                
                # Save to MySQL database
                if save_user(new_user, new_email, password_hash):
                    st.success(f"✅ Account '{new_user}' saved to database! 🎉")
                    
                    # Verify the user was saved
                    with st.expander("🔍 Verify Database Entry"):
                        saved_user = get_user(new_user)
                        if saved_user:
                            st.write(f"*User ID:* {saved_user['id']}")
                            st.write(f"*Username:* {saved_user['username']}")
                            st.write(f"*Email:* {saved_user['email']}")
                            st.write(f"*Created:* {saved_user['created_at']}")
                            st.success("✅ Verified in database!")
                        else:
                            st.error("❌ User not found in database")
                else:
                    st.warning(f"⚠️ Could not save to database. User '{new_user}' created locally only.")
                    st.success(f"✅ Account '{new_user}' created locally! 🎉")
                
                st.balloons()
                st.session_state.auth_page = "🔐 Login"
                st.rerun()
# ====== LOGIN (WITH DATABASE CHECK) ======
def login():
    st.markdown("<h2 style='text-align: center; color:#007bff;'>🔐 Login</h2>", unsafe_allow_html=True)
    
    col1, col2 = st.columns([1, 3])
    
    with col1:
        st.markdown("")
    
    with col2:
        user = st.text_input("👤 Username", key="login_user")
        pwd = st.text_input("🔒 Password", type="password", key="login_pass")
        
        if st.button(" Login", type="primary"):
            if not user or not pwd:
                st.error("❌ Please enter username and password")
            else:
                # First check session state (local)
                if user in st.session_state.users:
                    if st.session_state.users[user]['password'] == hash_password(pwd):
                        login_success(user)
                    else:
                        st.error("❌ Wrong password!")
                else:
                    # Check MySQL database
                    db_user = get_user(user)
                    if db_user and db_user['password_hash'] == hash_password(pwd):
                        # Add to session state from database
                        st.session_state.users[user] = {
                            'password': db_user['password_hash'],
                            'email': db_user['email']
                        }
                        login_success(user)
                    else:
                        st.error("❌ Username not found or incorrect password!")

def login_success(user):
    st.session_state.logged_in = True
    st.session_state.username = user
    st.session_state.user_email = st.session_state.users[user]['email']
    st.success(f"✅ Welcome, {user}! ")
    st.balloons()
    st.rerun()

def logout():
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.user_email = ""
    st.rerun()

# ====== MAIN FLOW ======
if not st.session_state.logged_in:
    st.sidebar.title("🔐 Authentication")
    page = st.sidebar.radio("Choose", ["📝 Create Account", "🔐 Login"], 
                           index=0 if st.session_state.auth_page == "📝 Create Account" else 1)
    
    if page == "📝 Create Account":
        create_account()
    else:
        login()
    st.stop()
else:
    st.sidebar.success(f"👤 **{st.session_state.username}**")
    st.sidebar.info(f"📧 {st.session_state.user_email}")
    
    if st.sidebar.button("🚪 Logout"):
        logout()

# ====== LOAD MODELS ======
try:
    model = joblib.load("ingredient_waste_model.pkl")
    features = joblib.load("model_features.pkl")
    st.sidebar.success("✅ Model loaded successfully")
except FileNotFoundError:
    model, features = None, []
    st.sidebar.warning("⚠️ Model files not found. Using demo mode.")
except Exception as e:
    model, features = None, []
    st.sidebar.error(f"❌ Error loading model: {e}")

# ====== SIDEBAR NAVIGATION ======
st.sidebar.image("https://cdn-icons-png.flaticon.com/512/1046/1046784.png", width=80)
st.sidebar.title("📊 Navigation")

app_mode = st.sidebar.radio(
    "Go to",
    [
        "🏠 Home",
        "📄 About",
        "📊 Predictions",
        "🍽️ Preparation Forecast",
        "⚠️ Sudden Weather Change Adjustment",
        "📋 Menu",
        "🥕 Ingredients Overview",
        "📬 Contact"
    ]
)

# ====== MENU MAPPING ======
MENU_MAP = {
    'Chicken': ['Chicken Biryani', 'Butter Chicken', 'Chicken Tikka Masala', 'Chicken 65'],
    'Tomatoes': ['Paneer Tikka Masala', 'Dal Makhani', 'Tomato Soup', 'Veg Kolhapuri'],
    'Onions': ['Onion Rings', 'Veg Biryani', 'Pulao', 'Onion Pakoda'],
    'Paneer': ['Paneer Butter Masala', 'Palak Paneer', 'Paneer Tikka', 'Shahipaneer'],
    'Rice': ['Veg Biryani', 'Jeera Rice', 'Pulao', 'Fried Rice'],
    'Dal': ['Dal Makhani', 'Dal Tadka', 'Dal Fry', 'Dal Soup'],
    'Butter': ['Butter Naan', 'Butter Roti', 'Garlic Butter Naan', 'Butter Chicken']
}

# ====== HOME PAGE ======
if app_mode == "🏠 Home":
    st.markdown("<h1 style='text-align: center; color: #F63366;'>🍽️ Food Waste Prediction System</h1>", unsafe_allow_html=True)
    
    try:
        st.image("background_img.jpg", use_column_width=True)
    except:
        st.image("https://images.unsplash.com/photo-1546069901-ba9599a7e63c?w=1200", 
                caption="Food Waste Reduction", 
                use_column_width=True)

    st.markdown("""
    <div style='text-align: center; font-size:18px; padding:10px 0 20px 0;'>
    Welcome to the <b>Food Waste Forecasting System</b> — your smart kitchen assistant to reduce ingredient waste and save money! 🌱
    </div>
    """, unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    col1.metric("Predicted Waste Saved", "120 kg", "+30%")
    col2.metric("Cost Reduction", "₹ 18,500", "+15%")
    col3.metric("Model Accuracy", "92.4%", "↑")

    st.markdown("""
    ---
    ### ✅ Key Features
    - 📈 Predict unsold ingredients
    - 💰 Optimize inventory cost
    - 📅 Use calendar features (holidays, weather)
    - 🧠 Machine learning powered forecasts
    - 💾 MySQL database storage
    """)

    st.markdown("""
    ---
    ### 🚀 How it Works
    1. Create account (stored in MySQL)
    2. Upload historical data (sales + purchase)
    3. Get AI-powered predictions
    4. Save predictions to database
    5. Generate optimized menus
    """)
    st.markdown("---")
    st.info("🔎 Use the sidebar to explore predictions, preparation forecast, weather adjustments, and project details.")

# ====== ABOUT PAGE ======
elif app_mode == "📄 About":
    st.markdown("<h2 style='text-align: center; color:#F63366;'>🔍 About the Project</h2>", unsafe_allow_html=True)
    st.markdown("""
    <div style='text-align: justify; font-size: 16px;'>
    <br>
    <b>Food Waste Prediction in Restaurants</b> is a smart forecasting system designed to reduce ingredient waste and optimize cost in restaurant kitchens.
    Using machine learning models trained on historical sales, inventory, and calendar data, it predicts which ingredients are likely to remain unsold on a given day.
    <br><br>
    The goal is to help restaurants reduce over-purchasing, minimize food wastage, and increase operational efficiency. 🌿
    </div>
    """, unsafe_allow_html=True)

    with st.expander("📁 Dataset Overview"):
        st.markdown("""
        - **Sales Data**: Daily dish-wise sales log  
        - **Waste Data**: Ingredient purchase, usage & wastage tracking  
        - **Calendar Data**: Holiday, weather & weekend impact  
        - **Recipe Mapping**: Dish-to-ingredient quantity mapping  
        """)

    with st.expander("🧠 Technologies Used"):
        st.markdown("""
        - **Python**  
        - **Pandas, NumPy**  
        - **Scikit-learn**  
        - **Streamlit**  
        - **Matplotlib, Seaborn, Plotly**  
        - **MySQL Database**  
        - **Joblib** for model serialization
        """)

   
# ====== PREDICTIONS PAGE ======
elif app_mode == "📊 Predictions":
    import streamlit as st
    import pandas as pd
    import joblib

    st.markdown(
        "<h2 style='text-align:center;color:#F63366;'>📊 Ingredient Waste Prediction</h2>",
        unsafe_allow_html=True
    )
    st.markdown("Upload a CSV file to forecast **ingredient-wise unsold quantities** 🍽️")

    # --------------------------------------------------
    # Upload CSV
    # --------------------------------------------------
    uploaded_file = st.file_uploader("📤 Upload CSV File", type=["csv"])

    if uploaded_file is None:
        st.info("Please upload a CSV file to continue")
        st.stop()

    # --------------------------------------------------
    # Read CSV
    # --------------------------------------------------
    try:
        df = pd.read_csv(uploaded_file)
    except Exception as e:
        st.error(f"❌ Error reading CSV file: {e}")
        st.stop()

    st.subheader("📋 Uploaded Data Preview")
    st.dataframe(df.head())

    # --------------------------------------------------
    # Required Columns Validation
    # --------------------------------------------------
    required_columns = [
        "Ingredient",
        "Qty_Prepared_kg",
        "Avg_Last7_Usage_kg",
        "Shelf_Life_Days",
        "Day",
        "Weather",
        "Is_Holiday"
    ]

    missing_cols = [col for col in required_columns if col not in df.columns]
    if missing_cols:
        st.error(f"❌ Missing required columns: {missing_cols}")
        st.stop()

    # --------------------------------------------------
    # Load Model & Feature List
    # --------------------------------------------------
    try:
        model = joblib.load("ingredient_waste_model.pkl")
        features = joblib.load("model_features.pkl")
    except Exception as e:
        st.error(f"❌ Model loading error: {e}")
        st.stop()

    # --------------------------------------------------
    # Encode Categorical Columns (Same as Training)
    # --------------------------------------------------
    df_encoded = pd.get_dummies(
        df,
        columns=["Ingredient", "Day", "Weather", "Is_Holiday"]
    )

    # --------------------------------------------------
    # Align Features with Training
    # --------------------------------------------------
    for col in features:
        if col not in df_encoded.columns:
            df_encoded[col] = 0

    df_encoded = df_encoded[features]

    # --------------------------------------------------
    # Prediction
    # --------------------------------------------------
    try:
        predictions = model.predict(df_encoded)
        df["Predicted_Unsold_kg"] = predictions.round(2)
        st.success("✅ Prediction completed successfully!")
    except Exception as e:
        st.error(f"❌ Prediction error: {e}")
        st.stop()

    # --------------------------------------------------
    # Ingredient-wise Aggregation (IMPORTANT FIX)
    # --------------------------------------------------
    ingredient_summary = (
        df.groupby("Ingredient", as_index=False)["Predicted_Unsold_kg"]
          .mean()
    )

    ingredient_summary["Predicted_Unsold_kg"] = ingredient_summary["Predicted_Unsold_kg"].round(2)

    # --------------------------------------------------
    # Metrics
    # --------------------------------------------------
    total_waste = ingredient_summary["Predicted_Unsold_kg"].sum()
    avg_waste = ingredient_summary["Predicted_Unsold_kg"].mean()

    col1, col2 = st.columns(2)
    col1.metric("📦 Total Predicted Waste", f"{total_waste:.2f} kg")
    col2.metric("📉 Avg Waste per Ingredient", f"{avg_waste:.2f} kg")

    # --------------------------------------------------
    # Results Table
    # --------------------------------------------------
    st.subheader("📦 Ingredient-wise Prediction Results")

    st.dataframe(
        ingredient_summary
        .sort_values("Predicted_Unsold_kg", ascending=False)
        .style.background_gradient(cmap="YlOrRd", subset=["Predicted_Unsold_kg"])
    )

    # --------------------------------------------------
    # Download CSV
    # --------------------------------------------------
    csv = ingredient_summary.to_csv(index=False)

    st.download_button(
        label="📥 Download Prediction Results",
        data=csv,
        file_name="ingredient_wise_predicted_unsold.csv",
        mime="text/csv",
        key="download_prediction_results"
    )


    # Save to MySQL database
    if save_prediction_to_db(df, st.session_state.username):
        st.success("✅ Predictions saved to database!")
    else:
        st.warning("⚠️ Could not save predictions to database")
    
    # Display results
    total_predicted = df["Predicted_Unsold_kg"].sum()
    avg_predicted = df["Predicted_Unsold_kg"].mean()
    
    col1, col2 = st.columns(2)
    col1.metric("📦 Total Predicted Waste", f"{total_predicted:.2f} kg")
    col2.metric("📉 Average Waste / Ingredient", f"{avg_predicted:.2f} kg")
    
    if "Ingredient" in df.columns:
        top_ingredient = df.loc[df["Predicted_Unsold_kg"].idxmax(), "Ingredient"]
        st.metric(" Highest Waste Ingredient", top_ingredient)
    
    st.markdown("---")
    
# ====== PREPARATION FORECAST ======
elif app_mode == "🍽️ Preparation Forecast":
    st.markdown("<h2 style='text-align: center; color:#FF8C00;'>🍽️ Preparation Forecast</h2>", unsafe_allow_html=True)
    st.write("Upload a CSV file to forecast the next-day **food preparation quantity** based on sales and unsold data.")

    prep_file = st.file_uploader("📤 Upload CSV File for Preparation Forecast", type=["csv"])

    if prep_file is not None:
        df_prep = pd.read_csv(prep_file)
    else:
        demo_data = {
            'Ingredient': ['Chicken', 'Tomatoes', 'Onions', 'Paneer', 'Rice'],
            'Sold_Quantity': [50, 80, 100, 40, 120],
            'Unsold_Quantity': [5, 8, 3, 6, 4]
        }
        df_prep = pd.DataFrame(demo_data)
        st.info("Using demo data. Upload your own CSV for real calculations.")
    
    st.markdown("---")
    st.subheader("📋 Data Preview")
    st.dataframe(df_prep.head())

    # Check columns
    required_cols = ["Ingredient", "Sold_Quantity", "Unsold_Quantity"]
    missing = [col for col in required_cols if col not in df_prep.columns]
    
    if missing:
        st.warning(f"Missing columns: {missing}. Using demo names.")
        for i, col in enumerate(['Ingredient', 'Sold_Quantity', 'Unsold_Quantity']):
            if i < len(df_prep.columns):
                df_prep = df_prep.rename(columns={df_prep.columns[i]: col})

    # Calculate forecast
    df_prep["Total_Required_kg"] = df_prep["Sold_Quantity"] + df_prep["Unsold_Quantity"]
    df_prep["Preparation_Forecast_kg"] = (df_prep["Total_Required_kg"] * 1.05).round(2)

    st.success("✅ Preparation forecast generated successfully!")

    # Metrics
    total_prep = df_prep["Preparation_Forecast_kg"].sum()
    avg_prep = df_prep["Preparation_Forecast_kg"].mean()
    
    col1, col2, col3 = st.columns(3)
    col1.metric("📦 Total Prep Needed", f"{total_prep:.2f} kg")
    col2.metric("📉 Average Prep / Ingredient", f"{avg_prep:.2f} kg")
    
    if "Ingredient" in df_prep.columns:
        top_ing = df_prep.loc[df_prep["Preparation_Forecast_kg"].idxmax(), "Ingredient"]
        col3.metric(" Highest Prep Ingredient", top_ing)

    st.markdown("---")
    st.subheader("📦 Next-Day Preparation Forecast Table")
    
    display_df = df_prep[["Ingredient", "Sold_Quantity", "Unsold_Quantity", "Preparation_Forecast_kg"]]
    st.dataframe(display_df.style.background_gradient(cmap="Blues", subset=["Preparation_Forecast_kg"]))

    # Download button
    csv_download = df_prep.to_csv(index=False)
    st.download_button("📥 Download Preparation Forecast CSV",
                       csv_download,
                       "preparation_forecast.csv",
                       "text/csv")

# ====== WEATHER ADJUSTMENT ======
elif app_mode == "⚠️ Sudden Weather Change Adjustment":
    st.markdown("<h2 style='text-align: center; color:#FF0000;'>⚠️ Sudden Weather Change Adjustment</h2>", unsafe_allow_html=True)

    st.write("Adjust preparation forecasts based on sudden weather changes.")

    sudden_weather = st.selectbox(
        "Choose the sudden weather effect:",
        [
            "Rain Started Suddenly",
            "Unexpected Heatwave",
            "Sudden Drop in Temperature",
            "Storm Warning",
            "Normal – No sudden change"
        ]
    )

    uploaded_adj = st.file_uploader("Upload Preparation Forecast CSV", type=["csv"])
    
    if uploaded_adj is not None:
        df_adj = pd.read_csv(uploaded_adj)
    else:
        demo_data = {
            'Ingredient': ['Chicken', 'Tomatoes', 'Onions'],
            'Preparation_Forecast_kg': [50, 80, 100]
        }
        df_adj = pd.DataFrame(demo_data)
        st.info("Using demo data. Upload your own CSV for real adjustments.")

    st.subheader("📄 Current Forecast (Before Adjustment)")
    st.dataframe(df_adj.head())

    # Adjustment factors
    adjust_map = {
        "Rain Started Suddenly": 1.15,
        "Unexpected Heatwave": 0.90,
        "Sudden Drop in Temperature": 1.10,
        "Storm Warning": 0.80,
        "Normal – No sudden change": 1.00
    }

    sudden_factor = adjust_map.get(sudden_weather, 1.00)
    df_adj["Adjusted_Forecast_kg"] = (df_adj["Preparation_Forecast_kg"] * sudden_factor).round(2)

    st.success("✅ Weather adjustment applied!")
    
    st.subheader("📦 Updated Forecast After Weather Change")
    st.dataframe(
        df_adj[["Ingredient", "Preparation_Forecast_kg", "Adjusted_Forecast_kg"]]
        .style.background_gradient(cmap="OrRd", subset=["Adjusted_Forecast_kg"])
    )

# ====== MENU PAGE (FIXED) ======
elif app_mode == "📋 Menu":
    st.markdown("<h2 style='text-align: center; color:#FF69B4;'>📋 Automated Menu Generator</h2>", unsafe_allow_html=True)

    # Fetch latest predictions from database
    predictions_df = get_user_predictions(st.session_state.username)

    if predictions_df.empty:
        st.warning("⚠️ No recent predictions found. Please generate predictions first (📊 Predictions page).")
        st.stop()

    # Rename for clarity
    predictions_df = predictions_df.rename(columns={"predicted_unsold_kg": "waste_kg"})

    #  FIXED: Calculate demand score properly (LOW waste = HIGH demand)
    if predictions_df['waste_kg'].max() > 0:
        predictions_df['demand_score'] = 10 * (1 - (predictions_df['waste_kg'] / predictions_df['waste_kg'].max()))
    else:
        predictions_df['demand_score'] = 5.0
    
    predictions_df['demand_score'] = predictions_df['demand_score'].round(2)
    predictions_df = predictions_df.sort_values(by="demand_score", ascending=False).reset_index(drop=True)
    predictions_df["demand_rank"] = predictions_df.index + 1

    # ✅ IMPROVED MENU MAPPING - More comprehensive
    MENU_MAP = {
        'chicken': ['Chicken Biryani', 'Butter Chicken', 'Chicken Tikka Masala', 'Chicken 65', 'Chicken Curry'],
        'tomato': ['Paneer Tikka Masala', 'Dal Makhani', 'Tomato Soup', 'Veg Kolhapuri'],
        'tomatoes': ['Paneer Tikka Masala', 'Dal Makhani', 'Tomato Soup', 'Veg Kolhapuri'],
        'onion': ['Onion Rings', 'Veg Biryani', 'Pulao', 'Onion Pakoda'],
        'onions': ['Onion Rings', 'Veg Biryani', 'Pulao', 'Onion Pakoda'],
        'paneer': ['Paneer Butter Masala', 'Palak Paneer', 'Paneer Tikka', 'Shahipaneer', 'Paneer 65'],
        'rice': ['Veg Biryani', 'Jeera Rice', 'Pulao', 'Fried Rice', 'Chicken Biryani'],
        'dal': ['Dal Makhani', 'Dal Tadka', 'Dal Fry', 'Dal Soup'],
        'butter': ['Butter Naan', 'Butter Roti', 'Garlic Butter Naan', 'Butter Chicken'],
        'potato': ['Aloo Fry', 'Aloo Gobi', 'Aloo Paratha'],
        'veg': ['Veg Biryani', 'Veg Kolhapuri', 'Veg Pulao']
    }

    # Generate menu items from TOP 5 ingredients
    top_ingredients = predictions_df.head(5)["ingredient"].str.lower().tolist()
    menu_items = []

    st.success(f"✅ Menu generated from **TOP 5** predictions for **{st.session_state.username}**")

    # Create 2-column layout
    col1, col2 = st.columns([1, 2])

    # LEFT: High-Demand Ingredients (with metrics)
    with col1:
        st.subheader(" High-Demand Ingredients")
        for _, row in predictions_df.head(5).iterrows():
            st.metric(
                label=f"#{int(row['demand_rank'])} {row['ingredient']}",
                value=f"{row['waste_kg']:.2f} kg waste",
                delta=f"Demand: {row['demand_score']:.1f}"
            )

    # RIGHT: Recommended Menu Items
    with col2:
        st.subheader("🍽️ Recommended Menu")

        # Generate menu items using improved mapping
        for ingredient in top_ingredients:
            ingredient_lower = ingredient.lower().strip()
            for key, dishes in MENU_MAP.items():
                if key in ingredient_lower:
                    menu_items.extend(dishes[:2])  # Take top 2 dishes per ingredient
                    break

        # Remove duplicates while preserving order
        unique_menu = list(dict.fromkeys(menu_items))
        
        if not unique_menu:
            st.warning("⚠️ No matching menu items found. Try generating predictions first.")
        else:
            # Display menu with numbering
            for i, dish in enumerate(unique_menu[:8], 1):  # Show top 8
                st.markdown(f"**{i}. {dish}** ")
            
            st.metric("📋 Total Menu Items", len(unique_menu))

    # DOWNLOAD BUTTON (outside columns)
    if unique_menu:
        menu_df = pd.DataFrame({
            "Rank": range(1, len(unique_menu) + 1),
            "Ingredient": top_ingredients[:len(unique_menu)] + [""] * (len(unique_menu) - len(top_ingredients)),
            "Menu Item": unique_menu,
            "Demand Score": predictions_df.head(len(unique_menu))['demand_score'].tolist()
        })
        
        st.download_button(
            label="📥 Download Menu CSV",
            data=menu_df.to_csv(index=False),
            file_name=f"{st.session_state.username}_menu_recommendations.csv",
            mime="text/csv"
        )
    
    # ====== INGREDIENTS OVERVIEW PAGE (WITH IMAGES) ======
elif app_mode == "🥕 Ingredients Overview":
    st.markdown("<h2 style='text-align: center; color:#32CD32;'>🥕 Ingredients Overview & Analytics</h2>", unsafe_allow_html=True)
    

    # Add image at the top
    try:
        # Try to load local image first
        try:
            img = Image.open("img.jpg")
            st.image(img, use_container_width=True, caption="Fresh Ingredients for Your Kitchen")
        except:
            # If local image not found, use a URL
            st.image("https://images.unsplash.com/photo-1414235077428-338989a2e8c0?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxwaG90by1wYWdlfHx8fGVufDB8fHx8fA%3D%3D&auto=format&fit=crop&w=2070&q=80", 
                    use_container_width=True, 
                    caption="Fresh Ingredients for Your Kitchen")
    except Exception as e:
        st.info("Image could not be loaded. Continuing with the overview...")
    
    col1, col2, col3 = st.columns(3)
    col1.metric("🌾 Top Used", "Rice (130 kg)")
    col2.metric("🍅 Most Common Veg", "Tomatoes (95 kg)")
    col3.metric("🍗 Most Common Non-Veg", "Chicken (120 kg)")
    
    st.markdown("---")
    
    # Ingredients data
    ingredient_list = ["Chicken", "Tomatoes", "Onions", "Paneer", "Butter", "Rice", "Dal"]
    usage_kg = [120, 95, 110, 60, 85, 130, 105]
    waste_kg = [15, 8, 12, 6, 10, 5, 7]
    
    # Create a dataframe
    df_ingredients = pd.DataFrame({
        'Ingredient': ingredient_list,
        'Usage (kg)': usage_kg,
        'Waste (kg)': waste_kg,
        'Efficiency (%)': [round((1 - w/u)*100, 1) for u, w in zip(usage_kg, waste_kg)]
    })
    
    # Display the table
    st.subheader("📊 Ingredient Usage & Waste Analysis")
    st.dataframe(
        df_ingredients.style.background_gradient(
            cmap="RdYlGn", 
            subset=['Efficiency (%)']
        ).format({'Efficiency (%)': '{:.1f}%'})
    )
    
    # Create two columns for charts
    chart_col1, chart_col2 = st.columns(2)
    
    with chart_col1:
        # Bar chart for usage
        fig1 = px.bar(
            df_ingredients,
            x='Ingredient',
            y='Usage (kg)',
            color='Usage (kg)',
            title="Ingredient Usage (kg)",
            color_continuous_scale="YlOrRd",
            height=400
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    with chart_col2:
        # Bar chart for waste
        fig2 = px.bar(
            df_ingredients,
            x='Ingredient',
            y='Waste (kg)',
            color='Waste (kg)',
            title="Ingredient Waste (kg)",
            color_continuous_scale="OrRd",
            height=400
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    # Add some insights
    st.markdown("---")
    st.subheader("📈 Key Insights")
    
    insight_col1, insight_col2 = st.columns(2)
    
    with insight_col1:
        st.markdown("""
        **✅ Best Performing:**
        - Rice: 96.2% efficiency
        - Tomatoes: 91.6% efficiency  
        - Onions: 89.1% efficiency
        """)
    
    with insight_col2:
        st.markdown("""
        **⚠️ Needs Improvement:**
        - Butter: 88.2% efficiency
        - Chicken: 87.5% efficiency
        - Paneer: 90.0% efficiency
        """)
    
    # Add a pie chart for waste distribution
    st.markdown("---")
    st.subheader("🥧 Waste Distribution by Ingredient")
    
    fig3 = px.pie(
        names=ingredient_list,
        values=waste_kg,
        title="Percentage of Total Waste by Ingredient",
        color=ingredient_list,
        color_discrete_sequence=px.colors.sequential.RdBu
    )
    st.plotly_chart(fig3, use_container_width=True)

# ====== CONTACT PAGE ======
elif app_mode == "📬 Contact":
    st.title("📬 Contact Us")
    st.markdown("""
    For any queries or feedback, please reach out:
    - **Email**: team@foodwasteprediction.com  
    - **Phone**: +91 9876543210  
    - **Address**: 123 Kitchen St, Food City, India  
    """)