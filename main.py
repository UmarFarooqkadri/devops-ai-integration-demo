# main.py

import numpy as np
from sklearn.linear_model import LinearRegression

# Sample data
X = np.array([[1, 1], [1, 2], [2, 2], [2, 3]])
y = np.dot(X, np.array([1, 2])) + 3

# Train a simple linear regression model
model = LinearRegression().fit(X, y)

# Make a prediction
prediction = model.predict(np.array([[3, 5]]))
print(f"Prediction for input [3, 5]: {prediction}")
