# predictive-food-waste-reduction
# 🍽️ Predictive Food Waste Reduction for Restaurants

## 📌 Project Overview

Predictive Food Waste Reduction for Restaurants is a Machine Learning-based application designed to predict unsold food quantities and minimize food wastage in restaurants.

The system analyzes historical sales, ingredient usage, weather conditions, holidays, and seasonal trends to estimate food requirements and support better ingredient purchasing decisions.

The application provides an interactive dashboard using Streamlit, allowing restaurant users to view predictions, analyze ingredient usage, and optimize food preparation.

## 🎯 Objectives

- Predict food waste using Machine Learning techniques.
- Reduce unnecessary food preparation and ingredient wastage.
- Optimize restaurant ingredient purchasing and inventory planning.
- Analyze historical sales and consumption patterns.
- Provide interactive visualizations and forecasting insights.

## 🛠️ Technologies Used

| Category | Technologies |
|---|---|
| Programming Language | Python |
| Machine Learning | Scikit-learn |
| Algorithm | Random Forest Regressor |
| Data Processing | Pandas, NumPy |
| Data Visualization | Plotly, Matplotlib, Seaborn |
| Frontend | Streamlit |
| Database | MySQL |
| Model Serialization | Joblib |
| Development Tools | VS Code, Jupyter Notebook |

## ⚙️ Key Features

### 1. Food Waste Prediction
- Predicts unsold food quantities using a trained Random Forest model.
- Analyzes historical sales and ingredient consumption.
- Identifies ingredients with higher wastage.

### 2. Preparation Forecast
- Estimates next-day food preparation requirements.
- Uses predicted sales and unsold quantities.
- Applies a preparation buffer to support demand planning.

### 3. Weather-Based Forecast Adjustment
- Adjusts preparation forecasts based on sudden weather changes.
- Supports scenarios such as unexpected rain, heatwaves, and temperature changes.

### 4. Ingredients Overview
- Displays ingredient usage and consumption summaries.
- Helps identify frequently used ingredients.
- Provides insights into food waste patterns.

### 5. Interactive Dashboard
- Built using Streamlit.
- Provides data visualizations and prediction results.
- Includes multiple pages for project analysis.

### 6. MySQL Database Integration
- Stores user inputs and prediction records.
- Supports historical prediction tracking.

## 🤖 Machine Learning Methodology

The project uses the Random Forest Regressor algorithm to predict food waste.

**Workflow:**

1. Data Collection
2. Data Cleaning and Preprocessing
3. Feature Engineering
4. Model Training
5. Hyperparameter Tuning
6. Model Evaluation
7. Prediction and Dashboard Integration

### Input Features

- Historical sales data
- Ingredient usage
- Weather conditions
- Holiday information
- Seasonal trends
- Recipe mapping

### Model Deployment

The trained model is saved using Joblib and integrated into the Streamlit application to generate predictions.

## 📂 Project Structure

```text
predictive-food-waste-reduction/
│
├── app.py
├── database.py
├── ingredient_waste_model.pkl
├── model_features.pkl
├── requirements.txt
├── README.md
├── LICENSE
├── .gitignore
│
├── pages/
├── data/
├── images/
└── notebooks/
```

*Note: Adjust this structure to match the actual files and folders in your repository.*

## 🚀 Installation and Execution

### Step 1: Clone the Repository

```bash
git clone https://github.com/sindhubhatkunki-tech/predictive-food-waste-reduction.git
```

### Step 2: Navigate to the Project Folder

```bash
cd predictive-food-waste-reduction
```

### Step 3: Install Required Libraries

```bash
pip install -r requirements.txt
```

### Step 4: Configure MySQL

Configure your MySQL database connection using environment variables or a local configuration file. Do not expose database credentials on GitHub.

### Step 5: Run the Application

```bash
streamlit run app.py
```

## 📊 Expected Outcomes

- Improved food waste prediction.
- Better ingredient purchasing decisions.
- Optimized food preparation planning.
- Reduced unnecessary food wastage.
- Data-driven restaurant management.

## 🔮 Future Enhancements

- Integrate real-time weather APIs.
- Improve prediction performance using advanced ML algorithms.
- Add automated inventory management.
- Develop cloud-based deployment.
- Provide advanced analytics and reporting.

## 👩‍💻 Developer

**Sindhu Bhat**

Master of Computer Applications (MCA) Graduate

Skills: Python | SQL | Machine Learning | Data Analytics | Streamlit

GitHub: https://github.com/sindhubhatkunki-tech

---

## 📄 License

This project is licensed under the MIT License. See the LICENSE file for details.

---

⭐ If you find this project useful, feel free to explore the repository and share your feedback.
