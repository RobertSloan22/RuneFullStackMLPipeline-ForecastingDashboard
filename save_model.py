import tensorflow as tf
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, LSTM, AdditiveAttention, Permute, Reshape, Multiply, Flatten, Dense

def build_model(input_shape):
    inputs = Input(shape=input_shape)
    x = LSTM(units=50, return_sequences=True)(inputs)
    x = LSTM(units=50, return_sequences=True)(x)

    attention = AdditiveAttention(name="attention_weight")
    permuted = Permute((2, 1))(x)
    reshaped = Reshape((-1, input_shape[0]))(permuted)
    attention_result = attention([reshaped, reshaped])
    multiplied = Multiply()([reshaped, attention_result])
    permuted_back = Permute((2, 1))(multiplied)
    reshaped_back = Reshape((-1, 50))(permuted_back)

    flattened = Flatten()(reshaped_back)
    outputs = Dense(1)(flattened)

    model = Model(inputs=inputs, outputs=outputs)
    model.compile(optimizer="adam", loss="mean_squared_error")
    return model

# Define the input shape
input_shape = (30, 10)  # Example shape, replace with your actual input shape

# Build and save the model
model = build_model(input_shape)
model.save('modelconvert.h5')
