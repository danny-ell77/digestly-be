from mangum import Mangum

# Import the FastAPI app from the main module
from main import app

# Create handler for AWS Lambda
handler = Mangum(app)
