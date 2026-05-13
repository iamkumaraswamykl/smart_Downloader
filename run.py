import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

from smart_organizer.web import create_app



app = create_app()


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False)

