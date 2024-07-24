import unittest
from FlaskApiForecasting import app


class FlaskAppTests(unittest.TestCase):

    def setUp(self):
        self.app = app.test_client()
        self.app.testing = True

    def test_predict_endpoint(self):
        # Example payload
        payload = {"rune_name": "BILLION•DOLLAR•CAT"}
        response = self.app.post("/predict", json=payload)

        self.assertEqual(response.status_code, 200)
        # Ensure the response contains a prediction field
        self.assertIn("prediction", response.json)

    def test_predict_endpoint_error_handling(self):
        # Sending request without rune_name to test error handling
        response = self.app.post("/predict", json={})
        self.assertEqual(response.status_code, 400)
        self.assertIn("error", response.json)
        self.assertEqual(response.json["error"], "Missing rune_name")


if __name__ == "__main__":
    unittest.main()
